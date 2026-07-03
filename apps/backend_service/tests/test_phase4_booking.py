"""Phase 4 contract tests: payment state machine + slot-based booking.

The core planning-doc invariant under test: a consultation cannot be booked
without a server-verified payment, the same payment cannot be used twice,
and cancellation refunds automatically.
"""
from datetime import datetime, timedelta

from tests.conftest import auth, _register_and_login


def _future(hours):
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _setup_doctor_with_slot(client):
    token = _register_and_login(client, "p4_doctor", "DOCTOR")
    client.put("/api/v1/doctors/me", headers=auth(token),
               json={"specialty": "General Medicine", "consultation_fee": 150})
    slots = client.post("/api/v1/doctors/me/slots", headers=auth(token), json=[
        {"start_time": _future(24), "end_time": _future(25)},
        {"start_time": _future(48), "end_time": _future(49)},
    ])
    assert slots.status_code == 201, slots.text
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    return token, me["id"], [s["id"] for s in slots.json()]


def _pay(client, token, amount=150.0):
    order = client.post("/api/v1/payments/create-order",
                        headers=auth(token), json={"amount": amount})
    assert order.status_code == 200, order.text
    order_id = order.json()["order_id"]
    assert order.json()["is_mock"] is True
    verify = client.post("/api/v1/payments/verify", headers=auth(token), json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "mock_pay_x",
        "razorpay_signature": f"mock_sig_{order_id}_valid",
    })
    assert verify.status_code == 200, verify.text
    return order_id


def test_booking_requires_payment(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slot(client)
    patient = _register_and_login(client, "p4_patient", "PATIENT")

    res = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0],
    })
    assert res.status_code == 402  # pay first


def test_paid_booking_flow_and_double_use_protection(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slot(client)
    patient = _register_and_login(client, "p4_patient2", "PATIENT")

    order_id = _pay(client, patient)

    booked = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0],
        "payment_order_id": order_id, "triage_summary": "fever",
    })
    assert booked.status_code == 200, booked.text
    appt = booked.json()
    assert appt["status"] == "CONFIRMED"
    assert appt["payment_id"] is not None

    # Same payment cannot buy a second booking
    again = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[1],
        "payment_order_id": order_id,
    })
    assert again.status_code == 409

    # Same slot cannot be booked twice (new payment, same slot)
    order2 = _pay(client, patient)
    clash = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0],
        "payment_order_id": order2,
    })
    assert clash.status_code == 409


def test_forged_mock_signature_rejected(client):
    patient = _register_and_login(client, "p4_patient3", "PATIENT")
    order = client.post("/api/v1/payments/create-order",
                        headers=auth(patient), json={"amount": 150})
    order_id = order.json()["order_id"]
    res = client.post("/api/v1/payments/verify", headers=auth(patient), json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "x",
        "razorpay_signature": "mock_sig_valid",  # not derived from order id
    })
    assert res.status_code == 400


def test_underpayment_rejected(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slot(client)
    patient = _register_and_login(client, "p4_patient4", "PATIENT")
    order_id = _pay(client, patient, amount=10.0)  # fee is 150

    res = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[1],
        "payment_order_id": order_id,
    })
    assert res.status_code == 402


def test_cancellation_refunds_and_frees_slot(client):
    doctor_token, doctor_id, slot_ids = _setup_doctor_with_slot(client)
    patient = _register_and_login(client, "p4_patient5", "PATIENT")
    order_id = _pay(client, patient)

    booked = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0],
        "payment_order_id": order_id,
    }).json()

    cancelled = client.put(f"/api/v1/appointments/{booked['id']}",
                           headers=auth(patient), json={"status": "CANCELLED"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    # Payment is refunded
    import models
    from database import SessionLocal
    db = SessionLocal()
    try:
        payment = db.query(models.Payment).filter(
            models.Payment.order_id == order_id).first()
        assert payment.status == "REFUNDED"
        slot = db.query(models.AvailabilitySlot).filter(
            models.AvailabilitySlot.id == slot_ids[0]).first()
        assert slot.is_booked is False
    finally:
        db.close()

    # The freed slot is bookable again with a fresh payment
    order2 = _pay(client, patient)
    rebook = client.post("/api/v1/appointments/book", headers=auth(patient), json={
        "doctor_id": doctor_id, "slot_id": slot_ids[0],
        "payment_order_id": order2,
    })
    assert rebook.status_code == 200, rebook.text
