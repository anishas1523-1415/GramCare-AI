"""Doctor directory, professional profiles and availability slots.

Planning doc requirements served here:
- Patients see a doctor list with specialty / experience / fee before
  booking ("டாக்டர்களோட சிறப்பு, அனுபவம், அப்புறம் கட்டணம் எல்லாமே தெரியும்").
- Doctors publish their availability calendar; bookings only happen against
  published slots ("அந்த நேரத்துலதான் யூசர்ஸ் அப்பாயின்ட்மென்ட் புக் செய்ய முடியும்").
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user, require_role

router = APIRouter()


def _ensure_profile(user: models.User, db: Session) -> models.DoctorProfile:
    """Get-or-create the DoctorProfile for a DOCTOR user. Auto-creating a
    default profile keeps pre-existing doctor accounts (seeded before this
    entity existed) working without a manual backfill step."""
    profile = (
        db.query(models.DoctorProfile)
        .filter(models.DoctorProfile.user_id == user.id)
        .first()
    )
    if profile is None:
        profile = models.DoctorProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _to_public(user: models.User, profile: models.DoctorProfile) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name or user.username,
        "specialty": profile.specialty or "General Medicine",
        "qualifications": profile.qualifications,
        "experience_years": profile.experience_years or 0,
        "consultation_fee": profile.consultation_fee if profile.consultation_fee is not None else 150.0,
        "languages": profile.languages,
        "is_available": bool(profile.is_available),
    }


@router.get("", response_model=List[schemas.DoctorPublic])
@router.get("/", response_model=List[schemas.DoctorPublic], include_in_schema=False)
async def list_doctors(
    specialty: Optional[str] = Query(None, description="Filter by specialty (case-insensitive)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Public doctor directory (authenticated users). Doctors without an
    explicit profile appear with sensible defaults."""
    doctors = (
        db.query(models.User)
        .filter(models.User.role == "DOCTOR", models.User.is_active == True)  # noqa: E712
        .offset(skip)
        .limit(limit)
        .all()
    )
    results = []
    for doc in doctors:
        profile = _ensure_profile(doc, db)
        public = _to_public(doc, profile)
        if specialty and specialty.lower() not in public["specialty"].lower():
            continue
        results.append(public)
    return results


@router.get("/me", response_model=schemas.DoctorPublic)
async def my_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    return _to_public(current_user, _ensure_profile(current_user, db))


@router.put("/me", response_model=schemas.DoctorPublic)
async def update_my_profile(
    update: schemas.DoctorProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    profile = _ensure_profile(current_user, db)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return _to_public(current_user, profile)


# ==========================================================
# Availability slots
# ==========================================================

@router.get("/{doctor_id}/slots", response_model=List[schemas.SlotResponse])
async def list_slots(
    doctor_id: int,
    include_booked: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Upcoming slots for a doctor. Patients see open slots to book;
    the doctor themself can pass include_booked=true to manage their diary."""
    doctor = (
        db.query(models.User)
        .filter(models.User.id == doctor_id, models.User.role == "DOCTOR")
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    profile = _ensure_profile(doctor, db)

    is_self = current_user.id == doctor_id or current_user.role == "ADMIN"
    q = (
        db.query(models.AvailabilitySlot)
        .filter(
            models.AvailabilitySlot.doctor_profile_id == profile.id,
            models.AvailabilitySlot.start_time >= datetime.now(timezone.utc).replace(tzinfo=None),
        )
        .order_by(models.AvailabilitySlot.start_time)
    )
    if not (include_booked and is_self):
        q = q.filter(models.AvailabilitySlot.is_booked == False)  # noqa: E712
    return q.limit(200).all()


@router.post("/me/slots", response_model=List[schemas.SlotResponse], status_code=201)
async def create_slots(
    slots: List[schemas.SlotCreate],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    """Publish one or more availability windows."""
    if not slots or len(slots) > 50:
        raise HTTPException(status_code=400, detail="Provide 1–50 slots per request")
    profile = _ensure_profile(current_user, db)

    created: List[models.AvailabilitySlot] = []
    for s in slots:
        if s.end_time <= s.start_time:
            raise HTTPException(status_code=400, detail="Slot end_time must be after start_time")
        exists = (
            db.query(models.AvailabilitySlot)
            .filter(
                models.AvailabilitySlot.doctor_profile_id == profile.id,
                models.AvailabilitySlot.start_time == s.start_time.replace(tzinfo=None),
            )
            .first()
        )
        if exists:
            continue  # idempotent: publishing the same window twice is a no-op
        slot = models.AvailabilitySlot(
            doctor_profile_id=profile.id,
            start_time=s.start_time.replace(tzinfo=None),
            end_time=s.end_time.replace(tzinfo=None),
        )
        db.add(slot)
        created.append(slot)
    db.commit()
    for slot in created:
        db.refresh(slot)
    return created


@router.delete("/me/slots/{slot_id}", status_code=204)
async def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    profile = _ensure_profile(current_user, db)
    slot = (
        db.query(models.AvailabilitySlot)
        .filter(
            models.AvailabilitySlot.id == slot_id,
            models.AvailabilitySlot.doctor_profile_id == profile.id,
        )
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.is_booked:
        raise HTTPException(status_code=400, detail="Cannot delete a booked slot — cancel the appointment first")
    db.delete(slot)
    db.commit()
    return None
