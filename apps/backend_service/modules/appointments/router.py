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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from modules.auth.router import get_current_user
from modules.family.router import resolve_owned_profile
from modules.payments.router import _do_refund

router = APIRouter()
logger = logging.getLogger("gramcare.appointments")


def _doctor_fee(db: Session, doctor_id: int) -> float:
    profile = (
        db.query(models.DoctorProfile)
        .filter(models.DoctorProfile.user_id == doctor_id)
        .first()
    )
    return profile.consultation_fee if profile and profile.consultation_fee is not None else 150.0


@router.post("/book", response_model=schemas.AppointmentResponse)
async def book_appointment(
    appointment: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Book a consultation as a patient."""
    if current_user.role != "PATIENT":
        raise HTTPException(status_code=403, detail="Only patients can book appointments.")

    doctor = (
        db.query(models.User)
        .filter(models.User.id == appointment.doctor_id, models.User.role == "DOCTOR")
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")

    resolve_owned_profile(appointment.family_profile_id, current_user, db)

    # ---- Slot resolution ------------------------------------------------
    slot = None
    if appointment.slot_id is not None:
        doctor_profile = (
            db.query(models.DoctorProfile)
            .filter(models.DoctorProfile.user_id == doctor.id)
            .first()
        )
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
        if not payment or payment.patient_id != current_user.id:
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
        patient_id=current_user.id,
        family_profile_id=appointment.family_profile_id,
        doctor_id=appointment.doctor_id,
        scheduled_at=scheduled_at,
        triage_summary=appointment.triage_summary,
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
                db_appointment.id, current_user.id,
                payment.order_id if payment else "free", slot.id if slot else "legacy")
    return db_appointment


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
    current_user: models.User = Depends(get_current_user),
):
    """Get the queue of upcoming appointments for a doctor."""
    if current_user.role not in ["DOCTOR", "ADMIN"] or (
        current_user.role == "DOCTOR" and current_user.id != doctor_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized to view this doctor's queue.")

    return (
        db.query(models.Appointment)
        .filter(
            models.Appointment.doctor_id == doctor_id,
            models.Appointment.status.in_(["PENDING", "CONFIRMED"]),
        )
        .order_by(models.Appointment.scheduled_at)
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
        if update_data.status == "CANCELLED" and appointment.status in ("PENDING", "CONFIRMED"):
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
