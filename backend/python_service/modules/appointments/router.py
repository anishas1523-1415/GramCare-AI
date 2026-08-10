"""Appointments — slot-based booking with server-side payment enforcement.

Planning doc rules implemented here:
- "பீஸ் செலுத்தின பிறகே அப்பாயின்ட்மென்ட் கன்ஃபார்ம் ஆகும்" — a paid,
  verified Payment row is REQUIRED to book (fee > 0). Previously the client
  called /book after payment with no server-side check, so a direct API call
  could book without paying.
- Bookings happen against the doctor's published availability slots; the
  legacy free-datetime path remains only for doctors with no published slots.
- Cancellation refunds the linked payment automatically (the escrow
  discussion's practical implementation).
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, update as sa_update
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from modules.auth.router import get_current_user, require_role, require_approved_doctor
from modules.family.router import resolve_owned_profile
from modules.payments.router import _do_refund
from core.ratelimit import rate_limit
from core.sms_service import SMSService

router = APIRouter()
logger = logging.getLogger("gramcare.appointments")

REMINDER_HOURS_BEFORE = float(os.getenv("APPOINTMENT_REMINDER_HOURS_BEFORE", "24"))


def _doctor_fee(db: Session, doctor_id: int) -> float:
    profile = (
        db.query(models.DoctorProfile)
        .filter(models.DoctorProfile.user_id == doctor_id)
        .first()
    )
    return profile.consultation_fee if profile and profile.consultation_fee is not None else 150.0


async def send_due_appointment_reminders(db: Session) -> int:
    """SMS reminder for every CONFIRMED appointment now within
    REMINDER_HOURS_BEFORE hours of its scheduled_at that hasn't been
    reminded yet. Called by the startup background loop and directly
    testable. Returns the number of SMS actually sent — a patient with no
    phone on file is marked reminded (nothing to retry) but not counted.

    Fires "at least once with enough lead time" rather than at a precise
    T-minus mark, which is robust to the poll loop running late or the
    process having restarted mid-window.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_end = now + timedelta(hours=REMINDER_HOURS_BEFORE)
    due = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.status == "CONFIRMED",
            models.Appointment.reminder_sent_at.is_(None),
            models.Appointment.scheduled_at > now,
            models.Appointment.scheduled_at <= window_end,
        )
        .all()
    )
    if not due:
        return 0

    sms_service = SMSService()
    sent = 0
    for appt in due:
        patient = db.query(models.User).filter(models.User.id == appt.patient_id).first()
        if not patient or not patient.phone:
            appt.reminder_sent_at = now
            continue

        doctor = db.query(models.User).filter(models.User.id == appt.doctor_id).first()
        time_str = appt.scheduled_at.strftime("%I:%M %p on %b %d")
        message = (
            f"GramCare AI: Reminder - you have an appointment with "
            f"Dr. {doctor.full_name if doctor else 'your doctor'} at {time_str}."
        )
        try:
            await sms_service.send_sms(patient.phone, message)
        except Exception as e:
            # Leave reminder_sent_at unset so the next poll retries — a
            # provider outage shouldn't permanently silence the reminder.
            logger.error("Failed to send appointment reminder SMS for appointment %d: %s", appt.id, e)
            continue
        appt.reminder_sent_at = now
        sent += 1

    db.commit()
    return sent


async def _book_appointment_core(
    appointment: schemas.AppointmentCreate,
    db: Session,
    patient: models.User,
) -> models.Appointment:
    """Core booking logic, shared by POST /appointments/book below and the
    CHW proxy endpoint (modules/chw/router.py's
    POST /chw/patients/{patient_id}/book) that books on behalf of a
    CHW-registered patient.

    `patient` is whoever the appointment is booked FOR (and billed to) —
    for the CHW proxy that is the patient themself, never the CHW driving
    the call, so ownership/payment checks below are identical to a patient
    booking for themselves. This is the exact same rule enforced here as
    always: a paid doctor requires a payment_order_id whose Payment.patient_id
    already matches `patient.id` (i.e. the patient — or someone signed in as
    the patient — must have completed /payments/create-order + /payments/verify
    themselves first; a CHW cannot pay "as themselves" and consume it on the
    patient's behalf).
    """
    doctor = (
        db.query(models.User)
        .filter(models.User.id == appointment.doctor_id, models.User.role == "DOCTOR")
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")

    # The public doctor directory (GET /doctors) already hides any doctor
    # whose DoctorProfile.verification_status isn't APPROVED, but that's a
    # UI-level filter, not access control — a client that already knows a
    # doctor_id (enumeration, a stale bookmark, direct API use) must not be
    # able to book/pay an unapproved doctor just because the UI wouldn't
    # have shown them one.
    doctor_profile = (
        db.query(models.DoctorProfile)
        .filter(models.DoctorProfile.user_id == doctor.id)
        .first()
    )
    if not doctor_profile or doctor_profile.verification_status != "APPROVED":
        raise HTTPException(status_code=404, detail="Doctor not found.")

    resolve_owned_profile(appointment.family_profile_id, patient, db)

    # ---- Slot resolution ------------------------------------------------
    slot = None
    if appointment.slot_id is not None:
        slot = (
            db.query(models.AvailabilitySlot)
            .filter(
                models.AvailabilitySlot.id == appointment.slot_id,
                models.AvailabilitySlot.doctor_profile_id == (doctor_profile.id if doctor_profile else -1),
            )
            .with_for_update()
            .first()
        )
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found for this doctor.")
        if slot.is_booked:
            raise HTTPException(status_code=409, detail="This slot has just been booked. Please pick another.")
        scheduled_at = slot.start_time
    elif appointment.scheduled_at is not None:
        # Legacy path for doctors who haven't published slots yet.
        has_slots = (
            db.query(models.AvailabilitySlot)
            .join(models.DoctorProfile, models.AvailabilitySlot.doctor_profile_id == models.DoctorProfile.id)
            .filter(models.DoctorProfile.user_id == doctor.id)
            .count() > 0
        )
        if has_slots:
            raise HTTPException(
                status_code=400,
                detail="This doctor uses published slots — pass slot_id instead of a free time.",
            )
        scheduled_at = appointment.scheduled_at.replace(tzinfo=None)
    else:
        raise HTTPException(status_code=400, detail="Provide slot_id or scheduled_at.")

    # ---- Payment enforcement --------------------------------------------
    fee = _doctor_fee(db, doctor.id)
    payment = None
    if fee > 0:
        if not appointment.payment_order_id:
            raise HTTPException(
                status_code=402,
                detail=f"Consultation fee is INR {fee:.0f}. Pay first, then book with payment_order_id.",
            )
        # with_for_update() serializes concurrent readers on databases that
        # honor row locks (Postgres, production). It is a documented no-op
        # on SQLite though — two concurrent requests can each read
        # status="PAID" here before either writes — so the actual
        # correctness guarantee against double-consuming one payment is the
        # atomic `UPDATE ... WHERE status='PAID'` + rowcount check further
        # below, which is safe on both backends regardless of isolation
        # level. This read is kept for the early validation (ownership,
        # amount) and for the Postgres fast-path where it avoids wasted work.
        payment = (
            db.query(models.Payment)
            .filter(models.Payment.order_id == appointment.payment_order_id)
            .with_for_update()
            .first()
        )
        if not payment or payment.patient_id != patient.id:
            raise HTTPException(status_code=403, detail="Payment order not found for your account.")
        if payment.status == "CONSUMED":
            raise HTTPException(status_code=409, detail="This payment was already used for a booking.")
        if payment.status != "PAID":
            raise HTTPException(status_code=402, detail=f"Payment not verified (status {payment.status}).")
        if payment.amount + 0.01 < fee:
            raise HTTPException(
                status_code=402,
                detail=f"Paid amount (INR {payment.amount:.0f}) is less than the fee (INR {fee:.0f}).",
            )

    db_appointment = models.Appointment(
        patient_id=patient.id,
        family_profile_id=appointment.family_profile_id,
        doctor_id=appointment.doctor_id,
        scheduled_at=scheduled_at,
        triage_summary=appointment.triage_summary,
        triage_severity_score=appointment.triage_severity_score,
        status="CONFIRMED",
        payment_id=payment.id if payment else None,
    )
    db.add(db_appointment)
    db.flush()  # obtain id before linking slot/payment

    # Atomic claim of the payment: the UPDATE only matches (and only then
    # does rowcount become 1) if status is STILL "PAID" at the moment this
    # statement executes, which SQLite and Postgres both guarantee is
    # serialized against any other concurrent UPDATE on the same row —
    # unlike the plain read-then-write above, this is immune to the
    # check-then-act race regardless of whether the DB honors row locks.
    # If we lose the race, roll back everything (including the
    # already-flushed Appointment insert) so no orphaned row is left behind.
    if payment:
        result = db.execute(
            sa_update(models.Payment)
            .where(models.Payment.id == payment.id, models.Payment.status == "PAID")
            .values(status="CONSUMED")
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="This payment was already used for a booking.")

    # Same atomic-claim pattern for the slot — two concurrent bookings
    # against the same slot_id must not both succeed.
    if slot:
        slot_result = db.execute(
            sa_update(models.AvailabilitySlot)
            .where(models.AvailabilitySlot.id == slot.id, models.AvailabilitySlot.is_booked == False)  # noqa: E712
            .values(is_booked=True, appointment_id=db_appointment.id)
        )
        if slot_result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="This slot has just been booked. Please pick another.")

    db.commit()
    db.refresh(db_appointment)
    logger.info("Appointment %d booked by patient %d (payment=%s, slot=%s).",
                db_appointment.id, patient.id,
                payment.order_id if payment else "free", slot.id if slot else "legacy")

    try:
        from core.notifications import NotificationService
        time_str = scheduled_at.strftime("%I:%M %p on %b %d")
        NotificationService(db).notify_appointment_reminder(
            user_id=patient.id,
            doctor_name=doctor.full_name or "Doctor",
            time_str=time_str
        )
    except Exception as e:
        logger.error(f"Failed to send appointment notification: {e}")

    return db_appointment


@router.post("/book", response_model=schemas.AppointmentResponse, dependencies=[Depends(rate_limit("appointment_book", 5, 300))])
async def book_appointment(
    appointment: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """Book a consultation as a patient."""
    return await _book_appointment_core(appointment, db, current_user)


@router.get("/my", response_model=List[schemas.AppointmentResponse])
async def my_appointments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The caller's own appointments (patient view)."""
    return (
        db.query(models.Appointment)
        .filter(models.Appointment.patient_id == current_user.id)
        .order_by(models.Appointment.scheduled_at.desc())
        .limit(100)
        .all()
    )


@router.get("/doctor/{doctor_id}/queue", response_model=List[schemas.AppointmentResponse])
async def get_doctor_queue(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    """Get the queue of upcoming appointments for a doctor."""
    if current_user.role == "DOCTOR" and current_user.id != doctor_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this doctor's queue.")

    # Predictive Risk Stratification (planning doc): high-severity patients
    # surface first, regardless of slot order, so a doctor triages the
    # riskiest case first rather than working strictly chronologically.
    # Appointments with no AI severity data (walk-ins, legacy bookings)
    # sort after any scored ones, then everything falls back to time.
    severity_rank = func.coalesce(models.Appointment.triage_severity_score, -1)
    return (
        db.query(models.Appointment)
        .filter(
            models.Appointment.doctor_id == doctor_id,
            models.Appointment.status.in_(["PENDING", "CONFIRMED"]),
        )
        .order_by(severity_rank.desc(), models.Appointment.scheduled_at)
        .all()
    )


@router.put("/{appointment_id}", response_model=schemas.AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    update_data: schemas.AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update status / consultation notes.

    Doctors: their own appointments only. Patients: may CANCEL their own
    appointment. Cancelling an appointment with a linked payment triggers an
    automatic refund and frees the slot.
    """
    appointment = (
        db.query(models.Appointment)
        .filter(models.Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    if current_user.role == "DOCTOR":
        if appointment.doctor_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this appointment.")
        doctor_profile = (
            db.query(models.DoctorProfile)
            .filter(models.DoctorProfile.user_id == current_user.id)
            .first()
        )
        if not doctor_profile or doctor_profile.verification_status != "APPROVED":
            raise HTTPException(
                status_code=403,
                detail="Your doctor account is pending government verification and cannot perform this action yet.",
            )
    elif current_user.role == "PATIENT":
        if appointment.patient_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your appointment.")
        if update_data.status and update_data.status != "CANCELLED":
            raise HTTPException(status_code=403, detail="Patients can only cancel their appointments.")
        if update_data.consultation_notes:
            raise HTTPException(status_code=403, detail="Only doctors write consultation notes.")
    elif current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorized.")

    if update_data.status:
        # CANCELLED and COMPLETED are terminal — once an appointment lands
        # there (refunded-and-freed, or actually consulted), no further
        # status transition is legal. Without this guard a doctor could
        # "un-cancel" an already-refunded appointment back to CONFIRMED with
        # no new payment enforced, or silently CANCEL a COMPLETED
        # appointment with no refund firing (the refund block below only
        # fires from PENDING/CONFIRMED).
        if appointment.status in ("CANCELLED", "COMPLETED"):
            raise HTTPException(
                status_code=400,
                detail=f"This appointment is already {appointment.status.lower()} and its status cannot be changed further.",
            )
        if update_data.status == "CANCELLED":
            # Refund + free the slot (planning doc: no money lost on no-show)
            if appointment.payment_id:
                payment = (
                    db.query(models.Payment)
                    .filter(models.Payment.id == appointment.payment_id)
                    .with_for_update()
                    .first()
                )
                if payment and payment.status in ("PAID", "CONSUMED"):
                    _do_refund(payment, db)
            slot = (
                db.query(models.AvailabilitySlot)
                .filter(models.AvailabilitySlot.appointment_id == appointment.id)
                .first()
            )
            if slot:
                slot.is_booked = False
                slot.appointment_id = None
        appointment.status = update_data.status
    if update_data.consultation_notes:
        appointment.consultation_notes = update_data.consultation_notes

    db.commit()
    db.refresh(appointment)
    return appointment
