"""Consultation payments — Razorpay-backed with a full mock mode.

Every order is now persisted as a Payment row with an explicit state
machine (CREATED -> PAID -> CONSUMED / REFUNDED), which is what lets the
appointments module enforce the planning doc's rule server-side: the fee is
paid BEFORE the call, and refunded if the doctor never attends. Previously
orders lived only in the gateway/mock ether — the backend had no record,
so booking couldn't verify payment at all.
"""
import os
import time
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
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

razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        logger.info("Razorpay client initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize Razorpay client: {e}")
else:
    logger.warning("Razorpay credentials not found. Payments will operate in MOCK mode.")

# ============================================================
# Schemas
# ============================================================
class OrderCreateRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = "INR"

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
    ))
    db.commit()

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
    only accept orders that have passed through here."""
    payment = (
        db.query(models.Payment)
        .filter(models.Payment.order_id == request.razorpay_order_id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Unknown order id.")
    if payment.patient_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not your payment order.")
    if payment.status == "PAID":
        return VerifyPaymentResponse(status="SUCCESS", message="Payment already verified.")
    if payment.status not in ("CREATED", "FAILED"):
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
    payment = db.query(models.Payment).filter(models.Payment.order_id == order_id).first()
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
    """Shared refund routine, also used by appointment cancellation."""
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
