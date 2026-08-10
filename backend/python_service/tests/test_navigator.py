"""AI Care Navigator contract tests: each signal surfaces its own item with
the right priority/reason/cta, and the aggregated list is CRITICAL-first.
Rows are inserted directly via the ORM (mirrors tests/test_appointment_reminders.py
and tests/test_phase6_emergency.py) — the point here is next-steps' own
aggregation/ranking logic, not the booking/appointment/SOS creation flows
those other modules already cover.
"""
from datetime import datetime, timedelta, timezone

import models
from tests.conftest import auth, _register_and_login


def _user_id(client, token):
    return client.get("/api/v1/auth/me", headers=auth(token)).json()["id"]


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_empty_state_all_caught_up(client, db):
    token = _register_and_login(client, "nav_empty_patient", "PATIENT")
    res = client.get("/api/v1/navigator/next-steps", headers=auth(token))
    assert res.status_code == 200, res.text
    items = res.json()
    assert len(items) == 1
    assert items[0]["category"] == "all_clear"
    assert items[0]["priority"] == "LOW"
    assert items[0]["reason"] == "You're all caught up — no urgent actions right now"
    assert items[0]["cta_label"] is None


def test_active_sos_surfaces_as_critical(client, db):
    token = _register_and_login(client, "nav_sos_patient", "PATIENT")
    patient_id = _user_id(client, token)

    db.add(models.EmergencySOS(patient_id=patient_id, status="ACTIVE"))
    db.commit()

    res = client.get("/api/v1/navigator/next-steps", headers=auth(token))
    assert res.status_code == 200, res.text
    items = res.json()
    sos_items = [i for i in items if i["category"] == "sos"]
    assert len(sos_items) == 1
    assert sos_items[0]["priority"] == "CRITICAL"
    assert sos_items[0]["reason"] == "You have an active emergency alert"
    assert sos_items[0]["cta_route"] == "/sos"
    # CRITICAL must be first in the aggregated, ranked list.
    assert items[0]["category"] == "sos"


def test_report_ready_lab_booking_surfaces(client, db):
    token = _register_and_login(client, "nav_lab_patient", "PATIENT")
    patient_id = _user_id(client, token)

    lab_token = _register_and_login(client, "nav_lab_center", "LAB")
    lab_reg = client.post("/api/v1/lab/register", headers=auth(lab_token), json={
        "name": "Nav Test Diagnostics",
    })
    assert lab_reg.status_code == 200, lab_reg.text
    lab_id = lab_reg.json()["id"]

    db.add(models.LabBooking(
        patient_id=patient_id,
        lab_center_id=lab_id,
        test_name="Complete Blood Count (CBC)",
        status="REPORT_READY",
        report_ready_at=_now(),
    ))
    # A COMPLETED booking must NOT surface (already actioned).
    db.add(models.LabBooking(
        patient_id=patient_id,
        lab_center_id=lab_id,
        test_name="Lipid Profile",
        status="COMPLETED",
        report_ready_at=_now(),
    ))
    db.commit()

    res = client.get("/api/v1/navigator/next-steps", headers=auth(token))
    assert res.status_code == 200, res.text
    items = res.json()
    lab_items = [i for i in items if i["category"] == "lab"]
    assert len(lab_items) == 1
    assert lab_items[0]["priority"] == "HIGH"
    assert "Complete Blood Count (CBC)" in lab_items[0]["reason"]
    assert lab_items[0]["cta_route"] == "/lab-tests"


def test_upcoming_confirmed_appointment_surfaces(client, db):
    token = _register_and_login(client, "nav_appt_patient", "PATIENT")
    doctor_token = _register_and_login(client, "nav_appt_doctor", "DOCTOR")
    patient_id = _user_id(client, token)
    doctor_id = _user_id(client, doctor_token)

    db.add(models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=_now() + timedelta(hours=6),  # inside the 48h window
        status="CONFIRMED",
    ))
    # Far outside the 48h window — must NOT surface.
    db.add(models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=_now() + timedelta(days=10),
        status="CONFIRMED",
    ))
    # PENDING (not yet confirmed) — must NOT surface.
    db.add(models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=_now() + timedelta(hours=3),
        status="PENDING",
    ))
    db.commit()

    res = client.get("/api/v1/navigator/next-steps", headers=auth(token))
    assert res.status_code == 200, res.text
    items = res.json()
    appt_items = [i for i in items if i["category"] == "appointment"]
    assert len(appt_items) == 1
    assert appt_items[0]["priority"] == "HIGH"
    assert "nav_appt_doctor" in appt_items[0]["reason"].lower()
    assert appt_items[0]["cta_route"] == "/book"


def test_unfulfilled_prescription_surfaces_when_stale(client, db):
    token = _register_and_login(client, "nav_rx_patient", "PATIENT")
    doctor_token = _register_and_login(client, "nav_rx_doctor", "DOCTOR")
    patient_id = _user_id(client, token)
    doctor_id = _user_id(client, doctor_token)

    # Older than 2 days -> must surface.
    db.add(models.Prescription(
        patient_id=patient_id,
        doctor_id=doctor_id,
        medicines=[{"name": "Paracetamol", "dosage": "500mg", "frequency": "BD", "duration": "5d"}],
        is_fulfilled=False,
        created_at=_now() - timedelta(days=5),
    ))
    # Too recent (< 2 days old) -> must NOT surface yet.
    db.add(models.Prescription(
        patient_id=patient_id,
        doctor_id=doctor_id,
        medicines=[{"name": "Cetrizine", "dosage": "10mg", "frequency": "OD", "duration": "3d"}],
        is_fulfilled=False,
        created_at=_now(),
    ))
    # Already fulfilled -> must NOT surface.
    db.add(models.Prescription(
        patient_id=patient_id,
        doctor_id=doctor_id,
        medicines=[{"name": "Amoxicillin", "dosage": "250mg", "frequency": "TDS", "duration": "7d"}],
        is_fulfilled=True,
        created_at=_now() - timedelta(days=10),
    ))
    db.commit()

    res = client.get("/api/v1/navigator/next-steps", headers=auth(token))
    assert res.status_code == 200, res.text
    items = res.json()
    rx_items = [i for i in items if i["category"] == "prescription"]
    assert len(rx_items) == 1
    assert rx_items[0]["priority"] == "MEDIUM"
    assert rx_items[0]["reason"] == "You have an unfulfilled prescription — find a pharmacy"
    assert rx_items[0]["cta_route"] == "/pharmacy"


def test_priority_ordering_critical_first_then_high_then_medium(client, db):
    token = _register_and_login(client, "nav_order_patient", "PATIENT")
    doctor_token = _register_and_login(client, "nav_order_doctor", "DOCTOR")
    patient_id = _user_id(client, token)
    doctor_id = _user_id(client, doctor_token)

    lab_token = _register_and_login(client, "nav_order_lab", "LAB")
    lab_reg = client.post("/api/v1/lab/register", headers=auth(lab_token), json={
        "name": "Nav Order Diagnostics",
    })
    lab_id = lab_reg.json()["id"]

    # Insert in reverse-priority order to prove sorting isn't accidental.
    db.add(models.Prescription(
        patient_id=patient_id,
        doctor_id=doctor_id,
        medicines=[{"name": "Ibuprofen", "dosage": "400mg", "frequency": "BD", "duration": "3d"}],
        is_fulfilled=False,
        created_at=_now() - timedelta(days=5),
    ))
    db.add(models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=_now() + timedelta(hours=6),
        status="CONFIRMED",
    ))
    db.add(models.LabBooking(
        patient_id=patient_id,
        lab_center_id=lab_id,
        test_name="Thyroid Panel",
        status="REPORT_READY",
        report_ready_at=_now(),
    ))
    db.add(models.EmergencySOS(patient_id=patient_id, status="RESPONDED"))
    db.commit()

    res = client.get("/api/v1/navigator/next-steps", headers=auth(token))
    assert res.status_code == 200, res.text
    items = res.json()

    priorities = [i["priority"] for i in items]
    order_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranks = [order_rank[p] for p in priorities]
    assert ranks == sorted(ranks), f"Items not priority-sorted: {priorities}"
    assert items[0]["category"] == "sos"
    assert items[0]["priority"] == "CRITICAL"
    # Both HIGH items (lab + appointment) must outrank the MEDIUM prescription.
    categories_by_rank = {i["category"] for i in items if i["priority"] == "HIGH"}
    assert categories_by_rank == {"lab", "appointment"}
    assert any(i["category"] == "prescription" and i["priority"] == "MEDIUM" for i in items)


def test_navigator_requires_patient_role(client, db):
    doctor_token = _register_and_login(client, "nav_forbidden_doctor", "DOCTOR")
    res = client.get("/api/v1/navigator/next-steps", headers=auth(doctor_token))
    assert res.status_code == 403
