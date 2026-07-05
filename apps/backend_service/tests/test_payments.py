"""Comprehensive Razorpay payment integration tests.

Covers the full payment lifecycle end to end: order creation, signature
verification (success/failure/tampering/replay), doctor consultation
booking, refunds, webhooks (the client-independent safety net), payment
history, DB consistency, authorization, amount tampering, idempotency, and
concurrency. Gateway credentials are empty in the test environment (see
conftest.py), so the "razorpay" branch of each endpoint runs in mock mode —
the mock signature scheme (`mock_sig_{order_id}_...`) is deliberately
order-id-bound so it exercises the same tamper/replay-resistance properties
a real HMAC signature would.

Webhook tests use a real HMAC-SHA256 signature computed with the fixed test
RAZORPAY_WEBHOOK_SECRET set in conftest.py — that verification path is
gateway-independent (razorpay.Utility() needs no API client), so it's
exercised fully even though the gateway itself is mocked.
"""
import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta

import models
from database import SessionLocal
from tests.conftest import auth, _register_and_login

WEBHOOK_SECRET = os.environ["RAZORPAY_WEBHOOK_SECRET"]


# ============================================================
# Helpers
# ============================================================
def _future(hours):
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _setup_doctor_with_slots(client, suffix, n=2, fee=150):
    token = _register_and_login(client, f"pay_doctor_{suffix}", "DOCTOR")
    client.put("/api/v1/doctors/me", headers=auth(token),
               json={"specialty": "General Medicine", "consultation_fee": fee})
    slots_payload = [
        {"start_time": _future(24 + i), "end_time": _future(24 + i + 1)}
        for i in range(n)
    ]
    slots = client.post("/api/v1/doctors/me/slots", headers=auth(token), json=slots_payload)
    assert slots.status_code == 201, slots.text
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    return token, me["id"], [s["id"] for s in slots.json()]


def _create_order(client, token, amount=150.0, idempotency_key=None):
    payload = {"amount": amount}
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    res = client.post("/api/v1/payments/create-order", headers=auth(token), json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def _pay(client, token, amount=150.0, idempotency_key=None):
    """Create an order and verify it with a valid mock signature. Returns the order_id."""
    order = _create_order(client, token, amount=amount, idempotency_key=idempotency_key)
    order_id = order["order_id"]
    assert order["is_mock"] is True
    verify = client.post("/api/v1/payments/verify", headers=auth(token), json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:8]}",
        "razorpay_signature": f"mock_sig_{order_id}_valid",
    })
    assert verify.status_code == 200, verify.text
    assert verify.json()["status"] == "SUCCESS"
    return order_id


def _payment_row(order_id):
    db = SessionLocal()
    try:
        return db.query(models.Payment).filter(models.Payment.order_id == order_id).first()
    finally:
        db.close()


def _webhook_sig(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _send_webhook(client, event: str, payload: dict, secret_override=None):
    body = json.dumps({"event": event, "payload": payload}).encode()
    secret = secret_override if secret_override is not None else WEBHOOK_SECRET
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )


# ============================================================
# 1 & 2 & 3 — full workflow / doctor consultation / success
# ============================================================
def test_full_consultation_payment_and_booking_flow(client):
    """End-to-end: create order -> verify -> book -> payment CONSUMED,
    appointment CONFIRMED with the payment linked."""
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "e2e")
    patient = _register_and_login(client, "pay_patient_e2e", "PATIENT")

    order_id = _pay(client, patient, amount=150.0)
    payment = _payment_row(order_id)
    assert payment.status == "PAID"
    assert payment.gateway_payment_id is not None

    booked = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0],
        "payment_order_id": order_id, "triage_summary": "fever",
    })
    assert booked.status_code == 200, booked.text
    appt = booked.json()
    assert appt["status"] == "CONFIRMED"
    assert appt["payment_id"] is not None

    payment = _payment_row(order_id)
    assert payment.status == "CONSUMED"


# ============================================================
# 4 — payment failure (and recovery via retry)
# ============================================================
def test_payment_failure_then_successful_retry(client):
    patient = _register_and_login(client, "pay_patient_fail", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]

    # Wrong signature -> FAILED
    bad = client.post("/api/v1/payments/verify", headers=auth(patient), json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "mock_pay_bad",
        "razorpay_signature": "totally_wrong_signature",
    })
    assert bad.status_code == 400
    assert _payment_row(order_id).status == "FAILED"

    # A FAILED order is NOT a dead end — same order_id can be retried with a
    # correct signature (e.g. user re-attempts the same Razorpay checkout).
    retry = client.post("/api/v1/payments/verify", headers=auth(patient), json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "mock_pay_retry_ok",
        "razorpay_signature": f"mock_sig_{order_id}_valid",
    })
    assert retry.status_code == 200, retry.text
    assert _payment_row(order_id).status == "PAID"


# ============================================================
# 5 — payment cancellation
# ============================================================
def test_cancelled_payment_stays_created_and_is_inert(client):
    """Cancellation (closing the Razorpay modal) never reaches the backend —
    there is no API call to make. The invariant to prove is that an order
    left CREATED (never verified) cannot be used to book, refund, or leak
    any access, and does not block the patient from starting a fresh
    payment attempt afterwards."""
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "cancel")
    patient = _register_and_login(client, "pay_patient_cancel", "PATIENT")

    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]
    assert _payment_row(order_id).status == "CREATED"

    # Cannot book against an unverified (cancelled) order.
    res = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    })
    assert res.status_code == 402

    # Cannot refund an order that was never paid.
    refund = client.post(f"/api/v1/payments/refund/{order_id}", headers=auth(patient))
    assert refund.status_code == 400

    # The patient can simply start over with a fresh order.
    order2_id = _pay(client, patient, amount=150.0)
    booked = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order2_id,
    })
    assert booked.status_code == 200, booked.text


# ============================================================
# 6 — signature verification
# ============================================================
def test_forged_mock_signature_rejected(client):
    patient = _register_and_login(client, "pay_patient_forge", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]
    res = client.post("/api/v1/payments/verify", headers=auth(patient), json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "x",
        "razorpay_signature": "mock_sig_valid",  # not derived from order id at all
    })
    assert res.status_code == 400
    assert _payment_row(order_id).status == "FAILED"


def test_signature_valid_for_one_order_rejected_for_another(client):
    """A signature is bound to the specific order it was issued for — using
    a genuine signature from order A against order B must fail (this is the
    mock-mode analog of Razorpay's HMAC being computed over order_id|payment_id,
    so it can't be replayed across orders)."""
    patient = _register_and_login(client, "pay_patient_xorder", "PATIENT")
    order_a = _create_order(client, patient, amount=100.0)
    order_b = _create_order(client, patient, amount=100.0)

    signature_for_a = f"mock_sig_{order_a['order_id']}_valid"

    res = client.post("/api/v1/payments/verify", headers=auth(patient), json={
        "razorpay_order_id": order_b["order_id"],
        "razorpay_payment_id": "mock_pay_cross",
        "razorpay_signature": signature_for_a,
    })
    assert res.status_code == 400
    assert _payment_row(order_b["order_id"]).status == "FAILED"
    # order A remains untouched (still CREATED, was never itself verified)
    assert _payment_row(order_a["order_id"]).status == "CREATED"


# ============================================================
# 7 — duplicate payment prevention
# ============================================================
def test_paid_order_cannot_fund_two_bookings(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "dup", n=2)
    patient = _register_and_login(client, "pay_patient_dup", "PATIENT")
    order_id = _pay(client, patient)

    first = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    })
    assert first.status_code == 200, first.text

    second = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[1], "payment_order_id": order_id,
    })
    assert second.status_code == 409


# ============================================================
# 8 — webhook handling
# ============================================================
def test_webhook_payment_captured_marks_paid(client):
    patient = _register_and_login(client, "pay_patient_wh1", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]
    assert _payment_row(order_id).status == "CREATED"

    res = _send_webhook(client, "payment.captured", {
        "payment": {"entity": {"id": "pay_webhook_1", "order_id": order_id, "status": "captured"}}
    })
    assert res.status_code == 200, res.text
    payment = _payment_row(order_id)
    assert payment.status == "PAID"
    assert payment.gateway_payment_id == "pay_webhook_1"


def test_webhook_invalid_signature_rejected(client):
    patient = _register_and_login(client, "pay_patient_wh2", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]

    body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_x", "order_id": order_id}}},
    }).encode()
    res = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"X-Razorpay-Signature": "0" * 64, "Content-Type": "application/json"},
    )
    assert res.status_code == 400
    assert _payment_row(order_id).status == "CREATED"  # untouched


def test_webhook_missing_signature_header_rejected(client):
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    res = client.post("/api/v1/payments/webhook", content=body,
                       headers={"Content-Type": "application/json"})
    assert res.status_code == 400


def test_webhook_rejects_when_secret_not_configured(client):
    import modules.payments.router as payments_router
    original = payments_router.RAZORPAY_WEBHOOK_SECRET
    payments_router.RAZORPAY_WEBHOOK_SECRET = None
    try:
        body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
        res = client.post(
            "/api/v1/payments/webhook", content=body,
            headers={"X-Razorpay-Signature": "irrelevant", "Content-Type": "application/json"},
        )
        assert res.status_code == 503
    finally:
        payments_router.RAZORPAY_WEBHOOK_SECRET = original


def test_webhook_payment_failed_event(client):
    patient = _register_and_login(client, "pay_patient_wh3", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]

    res = _send_webhook(client, "payment.failed", {
        "payment": {"entity": {"id": "pay_failed_1", "order_id": order_id}}
    })
    assert res.status_code == 200
    assert _payment_row(order_id).status == "FAILED"


def test_webhook_refund_processed_event(client):
    patient = _register_and_login(client, "pay_patient_wh4", "PATIENT")
    order_id = _pay(client, patient)
    payment = _payment_row(order_id)
    gateway_payment_id = payment.gateway_payment_id
    assert payment.status == "PAID"

    res = _send_webhook(client, "refund.processed", {
        "refund": {"entity": {"id": "rfnd_1", "payment_id": gateway_payment_id}}
    })
    assert res.status_code == 200
    assert _payment_row(order_id).status == "REFUNDED"


def test_webhook_unknown_event_type_ignored_gracefully(client):
    patient = _register_and_login(client, "pay_patient_wh5", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]

    res = _send_webhook(client, "order.paid", {"order": {"entity": {"id": order_id}}})
    assert res.status_code == 200
    assert _payment_row(order_id).status == "CREATED"  # no handler for this event; no-op


def test_webhook_replay_is_idempotent(client):
    """Razorpay redelivers on any non-2xx and can duplicate-deliver
    regardless — replaying the SAME event must never double-apply a side
    effect (e.g. never re-refund, never flip an already-CONSUMED payment
    back to PAID)."""
    patient = _register_and_login(client, "pay_patient_wh6", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]

    payload = {"payment": {"entity": {"id": "pay_replay_1", "order_id": order_id}}}
    first = _send_webhook(client, "payment.captured", payload)
    second = _send_webhook(client, "payment.captured", payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert _payment_row(order_id).status == "PAID"
    assert _payment_row(order_id).gateway_payment_id == "pay_replay_1"


def test_webhook_recovers_payment_client_never_verified(client):
    """Item 15/16 — API failure / offline recovery. Simulates a client that
    successfully paid on Razorpay's side but crashed/lost connectivity
    before its own /verify call landed. The webhook is the ONLY thing that
    marks this payment PAID in that scenario — prove it does, independent of
    any client action."""
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "recover")
    patient = _register_and_login(client, "pay_patient_recover", "PATIENT")

    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]
    # Note: NO call to /payments/verify at all — simulating the dropped
    # client connection. Order sits at CREATED.
    assert _payment_row(order_id).status == "CREATED"

    _send_webhook(client, "payment.captured", {
        "payment": {"entity": {"id": "pay_recovered", "order_id": order_id}}
    })
    assert _payment_row(order_id).status == "PAID"

    # The recovered payment is now fully usable for booking, exactly as if
    # /verify had succeeded normally.
    booked = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    })
    assert booked.status_code == 200, booked.text


# ============================================================
# 9 — refund flow
# ============================================================
def test_refund_by_patient(client):
    patient = _register_and_login(client, "pay_patient_refund1", "PATIENT")
    order_id = _pay(client, patient)
    res = client.post(f"/api/v1/payments/refund/{order_id}", headers=auth(patient))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "REFUNDED"


def test_refund_already_refunded_is_idempotent(client):
    patient = _register_and_login(client, "pay_patient_refund2", "PATIENT")
    order_id = _pay(client, patient)
    first = client.post(f"/api/v1/payments/refund/{order_id}", headers=auth(patient))
    second = client.post(f"/api/v1/payments/refund/{order_id}", headers=auth(patient))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "REFUNDED"


def test_refund_by_unrelated_user_rejected(client):
    patient = _register_and_login(client, "pay_patient_refund3", "PATIENT")
    stranger = _register_and_login(client, "pay_stranger_refund3", "PATIENT")
    order_id = _pay(client, patient)
    res = client.post(f"/api/v1/payments/refund/{order_id}", headers=auth(stranger))
    assert res.status_code == 403


def test_refund_by_appointment_doctor_allowed(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "docrefund")
    patient = _register_and_login(client, "pay_patient_docrefund", "PATIENT")
    order_id = _pay(client, patient)
    client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    })
    res = client.post(f"/api/v1/payments/refund/{order_id}", headers=auth(doctor_token))
    assert res.status_code == 200, res.text


def test_cancellation_refunds_and_frees_slot(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "cancelrefund")
    patient = _register_and_login(client, "pay_patient_cancelrefund", "PATIENT")
    order_id = _pay(client, patient)

    booked = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    }).json()

    cancelled = client.put(f"/api/v1/appointments/{booked['id']}",
                            headers=auth(patient), json={"status": "CANCELLED"})
    assert cancelled.status_code == 200
    assert _payment_row(order_id).status == "REFUNDED"


# ============================================================
# 10 — payment history
# ============================================================
def test_payment_history_returns_only_own_payments(client):
    patient_a = _register_and_login(client, "pay_patient_hist_a", "PATIENT")
    patient_b = _register_and_login(client, "pay_patient_hist_b", "PATIENT")

    order_a1 = _create_order(client, patient_a, amount=100.0)["order_id"]
    order_a2 = _create_order(client, patient_a, amount=200.0)["order_id"]
    order_b1 = _create_order(client, patient_b, amount=300.0)["order_id"]

    history_a = client.get("/api/v1/payments/my", headers=auth(patient_a))
    assert history_a.status_code == 200
    order_ids_a = {p["order_id"] for p in history_a.json()}
    assert order_a1 in order_ids_a
    assert order_a2 in order_ids_a
    assert order_b1 not in order_ids_a

    history_b = client.get("/api/v1/payments/my", headers=auth(patient_b))
    order_ids_b = {p["order_id"] for p in history_b.json()}
    assert order_b1 in order_ids_b
    assert order_a1 not in order_ids_b


def test_payment_history_requires_auth(client):
    res = client.get("/api/v1/payments/my")
    assert res.status_code == 401


# ============================================================
# 11 — transaction DB consistency
# ============================================================
def test_db_consistency_across_booking_and_refund(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "consist")
    patient = _register_and_login(client, "pay_patient_consist", "PATIENT")
    order_id = _pay(client, patient)

    booked = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    }).json()

    db = SessionLocal()
    try:
        payment = db.query(models.Payment).filter(models.Payment.order_id == order_id).first()
        appointment = db.query(models.Appointment).filter(models.Appointment.id == booked["id"]).first()
        assert appointment.payment_id == payment.id
        assert payment.status == "CONSUMED"
        slot = db.query(models.AvailabilitySlot).filter(models.AvailabilitySlot.id == slot_ids[0]).first()
        assert slot.is_booked is True
        assert slot.appointment_id == appointment.id
    finally:
        db.close()

    cancelled = client.put(f"/api/v1/appointments/{booked['id']}",
                            headers=auth(patient), json={"status": "CANCELLED"})
    assert cancelled.status_code == 200

    db = SessionLocal()
    try:
        payment = db.query(models.Payment).filter(models.Payment.order_id == order_id).first()
        assert payment.status == "REFUNDED"
        slot = db.query(models.AvailabilitySlot).filter(models.AvailabilitySlot.id == slot_ids[0]).first()
        assert slot.is_booked is False
        assert slot.appointment_id is None
        appointment = db.query(models.Appointment).filter(models.Appointment.id == booked["id"]).first()
        assert appointment.status == "CANCELLED"
    finally:
        db.close()


# ============================================================
# 12 — security
# ============================================================
def test_payment_endpoints_require_auth(client):
    assert client.post("/api/v1/payments/create-order", json={"amount": 100}).status_code == 401
    assert client.post("/api/v1/payments/verify", json={
        "razorpay_order_id": "x", "razorpay_payment_id": "y", "razorpay_signature": "z",
    }).status_code == 401
    assert client.post("/api/v1/payments/refund/some_order").status_code == 401
    assert client.get("/api/v1/payments/some_order/status").status_code == 401


def test_cannot_verify_or_check_status_of_others_payment(client):
    patient = _register_and_login(client, "pay_patient_sec1", "PATIENT")
    stranger = _register_and_login(client, "pay_stranger_sec1", "PATIENT")
    order_id = _create_order(client, patient, amount=100.0)["order_id"]

    verify = client.post("/api/v1/payments/verify", headers=auth(stranger), json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "mock_pay",
        "razorpay_signature": f"mock_sig_{order_id}_valid",
    })
    assert verify.status_code == 403

    status = client.get(f"/api/v1/payments/{order_id}/status", headers=auth(stranger))
    assert status.status_code == 403


def test_webhook_has_no_auth_dependency_but_needs_valid_signature(client):
    """The webhook is intentionally callable with no Authorization header
    (Razorpay has no user JWT) — but an invalid/missing signature must still
    be rejected, which is the only line of defense for this open endpoint."""
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    no_sig = client.post("/api/v1/payments/webhook", content=body,
                          headers={"Content-Type": "application/json"})
    assert no_sig.status_code == 400  # not 401 — no auth required, but signature is

    valid_sig = _webhook_sig(body)
    ok = client.post("/api/v1/payments/webhook", content=body,
                      headers={"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"})
    assert ok.status_code == 200  # succeeds with NO Authorization header at all


# ============================================================
# 13 — replay attack prevention
# ============================================================
def test_verify_replay_is_idempotent_no_double_charge_effect(client):
    patient = _register_and_login(client, "pay_patient_replay", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]
    sig = f"mock_sig_{order_id}_valid"

    first = client.post("/api/v1/payments/verify", headers=auth(patient), json={
        "razorpay_order_id": order_id, "razorpay_payment_id": "mock_pay_r1", "razorpay_signature": sig,
    })
    second = client.post("/api/v1/payments/verify", headers=auth(patient), json={
        "razorpay_order_id": order_id, "razorpay_payment_id": "mock_pay_r1", "razorpay_signature": sig,
    })
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["message"] == "Payment already verified."
    assert _payment_row(order_id).status == "PAID"


# (test_signature_valid_for_one_order_rejected_for_another above also covers
#  cross-order replay — signatures are bound to a specific order id.)


# ============================================================
# 14 — amount tampering prevention
# ============================================================
def test_underpayment_cannot_fund_booking(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "underpay", fee=150)
    patient = _register_and_login(client, "pay_patient_underpay", "PATIENT")
    order_id = _pay(client, patient, amount=10.0)  # fee is 150

    res = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    })
    assert res.status_code == 402


def test_overpayment_is_accepted_patient_can_still_book(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "overpay", fee=150)
    patient = _register_and_login(client, "pay_patient_overpay", "PATIENT")
    order_id = _pay(client, patient, amount=500.0)  # fee is 150, patient overpays

    res = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0], "payment_order_id": order_id,
    })
    assert res.status_code == 200, res.text


def test_amount_above_sanity_cap_rejected(client):
    patient = _register_and_login(client, "pay_patient_capcheck", "PATIENT")
    res = client.post("/api/v1/payments/create-order", headers=auth(patient),
                       json={"amount": 999_999.0})
    assert res.status_code == 422  # pydantic validation, never reaches the gateway


def test_negative_or_zero_amount_rejected(client):
    patient = _register_and_login(client, "pay_patient_zerocheck", "PATIENT")
    assert client.post("/api/v1/payments/create-order", headers=auth(patient),
                        json={"amount": 0}).status_code == 422
    assert client.post("/api/v1/payments/create-order", headers=auth(patient),
                        json={"amount": -50}).status_code == 422


# ============================================================
# 15 & 16 — API failure recovery / offline handling
# (test_webhook_recovers_payment_client_never_verified above covers the
#  server-side recovery; this covers the client-side polling half.)
# ============================================================
def test_status_endpoint_lets_client_poll_for_recovery(client):
    patient = _register_and_login(client, "pay_patient_poll", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]

    # Client "lost connectivity" right after paying — checks status instead
    # of blindly re-charging.
    status = client.get(f"/api/v1/payments/{order_id}/status", headers=auth(patient))
    assert status.status_code == 200
    assert status.json()["status"] == "CREATED"

    # Webhook lands independently (server-to-server) while the client is
    # still offline/retrying.
    _send_webhook(client, "payment.captured", {
        "payment": {"entity": {"id": "pay_poll_1", "order_id": order_id}}
    })

    # Client comes back online and polls again — sees PAID without ever
    # having called /verify itself, so it can proceed straight to booking.
    status2 = client.get(f"/api/v1/payments/{order_id}/status", headers=auth(patient))
    assert status2.status_code == 200
    assert status2.json()["status"] == "PAID"


def test_status_endpoint_404_for_unknown_order(client):
    patient = _register_and_login(client, "pay_patient_poll404", "PATIENT")
    res = client.get("/api/v1/payments/order_does_not_exist/status", headers=auth(patient))
    assert res.status_code == 404


# ============================================================
# 17 — idempotency
# ============================================================
def test_create_order_idempotency_key_returns_same_order(client):
    patient = _register_and_login(client, "pay_patient_idem", "PATIENT")
    key = f"idem-{uuid.uuid4().hex}"

    first = _create_order(client, patient, amount=150.0, idempotency_key=key)
    second = _create_order(client, patient, amount=150.0, idempotency_key=key)
    assert first["order_id"] == second["order_id"]

    db = SessionLocal()
    try:
        total_with_key = db.query(models.Payment).filter(
            models.Payment.idempotency_key == key
        ).count()
        assert total_with_key == 1  # no duplicate row was created
    finally:
        db.close()


def test_create_order_without_idempotency_key_creates_distinct_orders(client):
    patient = _register_and_login(client, "pay_patient_noidem", "PATIENT")
    first = _create_order(client, patient, amount=150.0)
    second = _create_order(client, patient, amount=150.0)
    assert first["order_id"] != second["order_id"]


def test_different_users_can_reuse_the_same_idempotency_key(client):
    """The dedup key is scoped per-patient (patient_id, idempotency_key) —
    it must not let one user's key collide with another's."""
    patient_a = _register_and_login(client, "pay_patient_idem_a", "PATIENT")
    patient_b = _register_and_login(client, "pay_patient_idem_b", "PATIENT")
    key = "shared-key-value"

    order_a = _create_order(client, patient_a, amount=150.0, idempotency_key=key)
    order_b = _create_order(client, patient_b, amount=150.0, idempotency_key=key)
    assert order_a["order_id"] != order_b["order_id"]


# ============================================================
# 18 — concurrency
# ============================================================
def test_concurrent_bookings_with_same_payment_only_one_succeeds(client):
    """Two threads race to book DIFFERENT slots using the SAME payment
    order. Without row-locking, both could read status="PAID" before either
    commits and both would succeed, consuming one payment for two
    appointments. Exactly one must win."""
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slots(client, "concurrent", n=2)
    patient = _register_and_login(client, "pay_patient_concurrent", "PATIENT")
    order_id = _pay(client, patient)

    results = {}

    def _book(slot_id, key):
        res = client.post("/api/v1/appointments/book", headers=auth(patient), json={
            "doctor_id": doctor_id, "slot_id": slot_id, "payment_order_id": order_id,
        })
        results[key] = res.status_code

    t1 = threading.Thread(target=_book, args=(slot_ids[0], "a"))
    t2 = threading.Thread(target=_book, args=(slot_ids[1], "b"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    statuses = sorted(results.values())
    assert statuses == [200, 409], f"expected exactly one 200 and one 409, got {results}"

    db = SessionLocal()
    try:
        payment = db.query(models.Payment).filter(models.Payment.order_id == order_id).first()
        appt_count = db.query(models.Appointment).filter(
            models.Appointment.payment_id == payment.id
        ).count()
        assert appt_count == 1, "the same payment funded more than one appointment"
    finally:
        db.close()


def test_concurrent_verify_calls_converge_to_single_paid_state(client):
    """Two threads call /verify for the same order at (nearly) the same
    time with a valid signature. Both should succeed (idempotent), and the
    payment must end up in exactly one consistent state — never corrupted
    or left oscillating."""
    patient = _register_and_login(client, "pay_patient_concverify", "PATIENT")
    order = _create_order(client, patient, amount=150.0)
    order_id = order["order_id"]
    sig = f"mock_sig_{order_id}_valid"

    results = {}

    def _verify(key, payment_id):
        res = client.post("/api/v1/payments/verify", headers=auth(patient), json={
            "razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": sig,
        })
        results[key] = res.status_code

    t1 = threading.Thread(target=_verify, args=("a", "mock_pay_conc_a"))
    t2 = threading.Thread(target=_verify, args=("b", "mock_pay_conc_b"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert list(results.values()) == [200, 200]
    assert _payment_row(order_id).status == "PAID"


def test_concurrent_refund_attempts_do_not_double_refund(client):
    patient = _register_and_login(client, "pay_patient_concrefund", "PATIENT")
    order_id = _pay(client, patient)

    results = {}

    def _refund(key):
        res = client.post(f"/api/v1/payments/refund/{order_id}", headers=auth(patient))
        results[key] = res.status_code

    threads = [threading.Thread(target=_refund, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(code == 200 for code in results.values())
    assert _payment_row(order_id).status == "REFUNDED"
