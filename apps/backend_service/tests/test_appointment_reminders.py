"""SMS appointment-reminder watchdog (send_due_appointment_reminders).

Mirrors how tests/test_phase6_emergency.py tests the SOS escalation
watchdog: appointments are inserted directly via the ORM (booking's payment
enforcement is irrelevant to reminder selection), and the watchdog function
is called directly rather than through the (nonexistent) HTTP surface —
this is a background job, not an endpoint.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from tests.conftest import auth


def _user_id(client, token):
    return client.get("/api/v1/auth/me", headers=auth(token)).json()["id"]


def test_reminder_sent_for_appointment_in_window(client, db, patient_token, doctor_token):
    import models
    from modules.appointments.router import send_due_appointment_reminders

    patient_id = _user_id(client, patient_token)
    doctor_id = _user_id(client, doctor_token)

    patient = db.get(models.User, patient_id)
    patient.phone = "+919000011111"
    db.commit()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appt = models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=now + timedelta(hours=2),  # well inside the default 24h window
        status="CONFIRMED",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    sent = asyncio.run(send_due_appointment_reminders(db))
    assert sent >= 1

    db.refresh(appt)
    assert appt.reminder_sent_at is not None


def test_reminder_skipped_for_appointment_outside_window(client, db, patient_token, doctor_token):
    import models
    from modules.appointments.router import send_due_appointment_reminders

    patient_id = _user_id(client, patient_token)
    doctor_id = _user_id(client, doctor_token)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appt = models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=now + timedelta(days=10),  # far outside the default 24h window
        status="CONFIRMED",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    asyncio.run(send_due_appointment_reminders(db))

    db.refresh(appt)
    assert appt.reminder_sent_at is None


def test_reminder_marked_but_not_counted_when_patient_has_no_phone(client, db, patient_token, doctor_token):
    import models
    from modules.appointments.router import send_due_appointment_reminders, REMINDER_HOURS_BEFORE

    patient_id = _user_id(client, patient_token)
    doctor_id = _user_id(client, doctor_token)

    patient = db.get(models.User, patient_id)
    patient.phone = None
    db.commit()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appt = models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=now + timedelta(hours=3),
        status="CONFIRMED",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    # Snapshot of everything the watchdog will consider "due" right before
    # it runs — used below to prove our phoneless appointment didn't add to
    # the sent count, without assuming this is the only due row in the DB.
    due_before = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.status == "CONFIRMED",
            models.Appointment.reminder_sent_at.is_(None),
            models.Appointment.scheduled_at > now,
            models.Appointment.scheduled_at <= now + timedelta(hours=REMINDER_HOURS_BEFORE),
        )
        .count()
    )
    assert due_before >= 1  # at least our own phoneless appointment

    sent = asyncio.run(send_due_appointment_reminders(db))

    db.refresh(appt)
    # Marked as handled (nothing to retry) even though no SMS went out.
    assert appt.reminder_sent_at is not None
    # Our phoneless appointment was one of the due rows but contributed
    # nothing to the count.
    assert sent < due_before


def test_reminder_not_sent_twice_across_two_runs(client, db, patient_token, doctor_token):
    import models
    from modules.appointments.router import send_due_appointment_reminders

    patient_id = _user_id(client, patient_token)
    doctor_id = _user_id(client, doctor_token)

    patient = db.get(models.User, patient_id)
    patient.phone = "+919000022222"
    db.commit()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appt = models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=now + timedelta(hours=1),
        status="CONFIRMED",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    asyncio.run(send_due_appointment_reminders(db))
    db.refresh(appt)
    first_stamp = appt.reminder_sent_at
    assert first_stamp is not None

    asyncio.run(send_due_appointment_reminders(db))
    db.refresh(appt)
    # Untouched by the second run — still the same timestamp, not re-stamped.
    assert appt.reminder_sent_at == first_stamp


def test_reminder_ignores_non_confirmed_appointments(client, db, patient_token, doctor_token):
    import models
    from modules.appointments.router import send_due_appointment_reminders

    patient_id = _user_id(client, patient_token)
    doctor_id = _user_id(client, doctor_token)

    patient = db.get(models.User, patient_id)
    patient.phone = "+919000033333"
    db.commit()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appt = models.Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=now + timedelta(hours=2),
        status="PENDING",  # not yet confirmed — must not be reminded
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    asyncio.run(send_due_appointment_reminders(db))

    db.refresh(appt)
    assert appt.reminder_sent_at is None
