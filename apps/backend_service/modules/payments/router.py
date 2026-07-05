"""Consultation payments — Razorpay-backed with a full mock mode.

Every order is persisted as a Payment row with an explicit state machine
(CREATED -> PAID -> CONSUMED / REFUNDED, or CREATED -> FAILED -> retry),
which is what lets the appointments module enforce the planning doc's rule
server-side: the fee is paid BEFORE the call, and refunded if the doctor
never attends.

Reliability notes (why the extra endpoints/locking below exist):
- The client's /verify call is not the only way a payment becomes PAID.
  If the app loses connectivity or crashes right after Razorpay captures
  the charge but before /verify lands, the payment would otherwise be
  stuck CREATED forever even though the patient was charged. /webhook is
  the server-to-server safety net for exactly that case, and /status lets
  a recovering client poll instead of re-charging.
- Every status transition (verify, refund, webhook) locks the Payment row
  with SELECT ... FOR UPDATE before checking/changing its status, so two
  concurrent requests for the same order can't both pass a stale check
  (double-verify, double-refund, or two bookings racing to consume one
  payment). This is a no-op on SQLite (used in tests) and a real row lock
  on Postgres (production) — same idiom already used for AvailabilitySlot.
"""
import os
import time
import uuid
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import razorpay

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user

router = APIRouter()
logger = logging.getLogger("gramcare.payments")

# ============================================================
# Initialize Razorpay Client
# ============================================================
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
# Separate credential from KEY_ID/KEY_SECRET (this is what Razorpay signs
# webhook payloads with — configured independently in the dashboard's
# Webhooks section). Verification needs no authenticated API client, so it
# works even when the gateway itself is running in mock mode.
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        logger.info("Razorpay client initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize Razorpay client: {e}")
else:
    logger.warning("Razorpay credentials not found. Payments will operate in MOCK mode.")

_webhook_utility = razorpay.Utility()

# Sane upper bound on a single consultation payment — defense-in-depth
# against a fat-fingered or malicious client sending an absurd amount (e.g.
# an extra zero). Well above any realistic specialist consultation fee.
MAX_PAYMENT_AMOUNT_INR = 100_000

# Payment.status values that a webhook/verify call is allowed to move OUT
# of. PAID/CONSUMED/REFUNDED are terminal-ish w.r.t. capture; only CREATED
# and FAILED (a previous verification attempt that didn't take) are open.
_VERIFIABLE_STATUSES = ("CREATED", "FAILED")

# ============================================================
# Schemas
# ============================================================
class OrderCreateRequest(BaseModel):
    amount: float = Field(..., gt=0, le=MAX_PAYMENT_AMOUNT_INR)
    currency: str = "INR"
    # Optional client-generated key (e.g. a UUID minted once per "Pay"
    # button press, reused across retries of the SAME attempt). Lets a
    # network retry of create-order return the existing order instead of
    # minting a second, orphaned one.
    idempotency_key: Optional[str] = Field(None, max_length=100)

class OrderResponse(BaseModel):
    order_id: str
    amount: int  # paise
    currency: str
    is_mock: bool = False

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class VerifyPaymentResponse(BaseModel):
    status: str
    message: str

# ============================================================
# Endpoints
# ============================================================
@router.post("/create-order", response_model=OrderResponse)
async def create_order(
    request: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a payment order for a consultation. The order is always for
    the CALLER's own account (the old client-supplied patient_id field is
    gone — it invited impersonation)."""
    if request.idempotency_key:
        existing = (
            db.query(models.Payment)
            .filter(
                models.Payment.patient_id == current_user.id,
                models.Payment.idempotency_key == request.idempotency_key,
            )
            .first()
        )
        if existing:
            return OrderResponse(
                order_id=existing.order_id,
                amount=int(existing.amount * 100),
                currency=existing.currency,
                is_mock=(existing.gateway == "mock"),
            )

    amount_in_paise = int(request.amount * 100)

    if razorpay_client:
        try:
            order = razorpay_client.order.create(data={
                "amount": amount_in_paise,
                "currency": request.currency,
                "receipt": f"rcpt_{uuid.uuid4().hex[:8]}",
                "payment_capture": 1,
            })
            order_id = order["id"]
            gateway = "razorpay"
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            raise HTTPException(status_code=502, detail="Payment gateway error.")
    else:
        time.sleep(0.3)
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        gateway = "mock"

    db.add(models.Payment(
        order_id=order_id,
        patient_id=current_user.id,
        amount=request.amount,
        currency=request.currency,
        status="CREATED",
        gateway=gateway,
        idempotency_key=request.idempotency_key,
    ))
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent identical request (same
        # idempotency_key) — the other request's row won. Return ITS order
        # rather than erroring, so whichever caller is retrying succeeds
        # transparently instead of surfacing a spurious 500/409.
        db.rollback()
        winner = (
            db.query(models.Payment)
            .filter(
                models.Payment.patient_id == current_user.id,
                models.Payment.idempotency_key == request.idempotency_key,
            )
            .first()
        )
        if winner:
            return OrderResponse(
                order_id=winner.order_id,
                amount=int(winner.amount * 100),
                currency=winner.currency,
                is_mock=(winner.gateway == "mock"),
            )
        raise

    return OrderResponse(
        order_id=order_id,
        amount=amount_in_paise,
        currency=request.currency,
        is_mock=(gateway == "mock"),
    )


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    request: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Verify the gateway signature and mark the Payment PAID. Booking will
    only accept orders that have passed through here (or been marked PAID
    by the /webhook safety net)."""
    payment = (
        db.query(models.Payment)
        .filter(models.Payment.order_id == request.razorpay_order_id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Unknown order id.")
    if payment.patient_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not your payment order.")
    if payment.status in ("PAID", "CONSUMED"):
        # Idempotent: a replayed/duplicate verify call (retry after a flaky
        # response, or the webhook having already landed first) is a no-op
        # success, not an error.
        return VerifyPaymentResponse(status="SUCCESS", message="Payment already verified.")
    if payment.status not in _VERIFIABLE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Order is not verifiable (status {payment.status}).")

    if razorpay_client and payment.gateway == "razorpay":
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': request.razorpay_order_id,
                'razorpay_payment_id': request.razorpay_payment_id,
                'razorpay_signature': request.razorpay_signature,
            })
        except razorpay.errors.SignatureVerificationError:
            payment.status = "FAILED"
            db.commit()
            raise HTTPException(status_code=400, detail="Payment verification failed: Invalid signature.")
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            raise HTTPException(status_code=502, detail="Payment verification error.")
    else:
        # Mock mode: the signature must be derived from the order id (a bare
        # constant like "mock_sig_valid" is rejected).
        expected_prefix = f"mock_sig_{request.razorpay_order_id}_"
        if not request.razorpay_signature.startswith(expected_prefix):
            payment.status = "FAILED"
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid mock signature.")

    payment.status = "PAID"
    payment.gateway_payment_id = request.razorpay_payment_id
    db.commit()
    return VerifyPaymentResponse(status="SUCCESS", message="Payment verified successfully.")


@router.get("/my", response_model=List[schemas.PaymentResponse])
async def my_payments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Payment history for the caller (patient wallet / receipts view)."""
    return (
        db.query(models.Payment)
        .filter(models.Payment.patient_id == current_user.id)
        .order_by(models.Payment.created_at.desc())
        .limit(200)
        .all()
    )


@router.get("/{order_id}/status", response_model=schemas.PaymentResponse)
async def payment_status(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Poll the current state of an order. Lets a client that lost
    connectivity right after paying (before it could call /verify) recover
    without re-charging: if the webhook already landed, this already
    reflects PAID and the client can proceed straight to booking."""
    payment = db.query(models.Payment).filter(models.Payment.order_id == order_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Unknown order id.")
    if payment.patient_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not your payment order.")
    return payment


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Server-to-server notification from Razorpay — the safety net for
    payments that were actually captured but whose client never (or not
    yet) called /verify. Intentionally has NO auth dependency (Razorpay
    calls this directly, with no user JWT); the HMAC signature check below
    is the only — and sufficient — line of defense.

    Every branch is idempotent: replaying the same event (Razorpay retries
    on any non-2xx, and can also redeliver) only re-applies a status
    transition that a status check has already guarded, so it's always
    safe to re-process.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not RAZORPAY_WEBHOOK_SECRET:
        logger.error("Webhook received but RAZORPAY_WEBHOOK_SECRET is not configured; rejecting.")
        raise HTTPException(status_code=503, detail="Webhook not configured.")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header.")

    try:
        _webhook_utility.verify_webhook_signature(raw_body.decode("utf-8"), signature, RAZORPAY_WEBHOOK_SECRET)
    except razorpay.errors.SignatureVerificationError:
        logger.warning("Webhook signature verification failed — rejecting payload.")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    try:
        payload = json.loads(raw_body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed webhook payload.")

    event = payload.get("event", "")
    entity = payload.get("payload", {})

    if event == "payment.captured":
        pe = entity.get("payment", {}).get("entity", {})
        order_id = pe.get("order_id")
        gateway_payment_id = pe.get("id")
        if order_id:
            payment = (
                db.query(models.Payment)
                .filter(models.Payment.order_id == order_id)
                .with_for_update()
                .first()
            )
            if payment and payment.status in _VERIFIABLE_STATUSES:
                payment.status = "PAID"
                payment.gateway_payment_id = gateway_payment_id
                db.commit()
                logger.info("Webhook: order %s marked PAID via payment.captured.", order_id)
            elif not payment:
                logger.warning("Webhook payment.captured for unknown order_id=%s", order_id)

    elif event == "payment.failed":
        pe = entity.get("payment", {}).get("entity", {})
        order_id = pe.get("order_id")
        if order_id:
            payment = (
                db.query(models.Payment)
                .filter(models.Payment.order_id == order_id)
                .with_for_update()
                .first()
            )
            if payment and payment.status == "CREATED":
                payment.status = "FAILED"
                db.commit()
                logger.info("Webhook: order %s marked FAILED via payment.failed.", order_id)

    elif event == "refund.processed":
        re_entity = entity.get("refund", {}).get("entity", {})
        gateway_payment_id = re_entity.get("payment_id")
        if gateway_payment_id:
            payment = (
                db.query(models.Payment)
                .filter(models.Payment.gateway_payment_id == gateway_payment_id)
                .with_for_update()
                .first()
            )
            if payment and payment.status in ("PAID", "CONSUMED"):
                payment.status = "REFUNDED"
                db.commit()
                logger.info("Webhook: payment %s marked REFUNDED via refund.processed.", gateway_payment_id)

    else:
        logger.info("Webhook: unhandled event type '%s' (ignored).", event)

    # Razorpay only cares about the HTTP status (retries on non-2xx) — the
    # body content is not inspected.
    return {"status": "ok"}


@router.post("/refund/{order_id}", response_model=schemas.PaymentResponse)
async def refund_payment(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Refund a payment (planning doc: money returns to the patient if the
    doctor never attends). Callable by the paying patient, the appointment's
    doctor, or an admin; the appointments module calls this logic on
    cancellation."""
    payment = (
        db.query(models.Payment)
        .filter(models.Payment.order_id == order_id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Unknown order id.")

    authorized = (
        current_user.role == "ADMIN"
        or payment.patient_id == current_user.id
        or (
            current_user.role == "DOCTOR"
            and db.query(models.Appointment)
            .filter(
                models.Appointment.payment_id == payment.id,
                models.Appointment.doctor_id == current_user.id,
            )
            .first() is not None
        )
    )
    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized to refund this payment.")

    return _do_refund(payment, db)


def _do_refund(payment: models.Payment, db: Session) -> models.Payment:
    """Shared refund routine, also used by appointment cancellation.

    Callers that already hold a row lock (fetched via .with_for_update())
    on `payment` may call this directly; refund_payment() above does so
    itself, and modules/appointments/router.py's cancellation path locks
    the row before calling in too.
    """
    if payment.status == "REFUNDED":
        return payment
    if payment.status not in ("PAID", "CONSUMED"):
        raise HTTPException(status_code=400, detail=f"Payment not refundable (status {payment.status}).")

    if razorpay_client and payment.gateway == "razorpay" and payment.gateway_payment_id:
        try:
            razorpay_client.payment.refund(
                payment.gateway_payment_id,
                {"amount": int(payment.amount * 100)},
            )
        except Exception as e:
            logger.error(f"Razorpay refund failed for {payment.order_id}: {e}")
            raise HTTPException(status_code=502, detail="Gateway refund failed; try again later.")

    payment.status = "REFUNDED"
    db.commit()
    db.refresh(payment)
    return payment
