"""Referral Network — doctor-to-doctor patient hand-offs.

Planning-doc intent: while treating a patient, a doctor can hand off care
either to a specific colleague already in the doctor directory, or open a
referral to any doctor practicing a target specialty (e.g. "this patient
needs a Cardiologist" with no particular doctor picked yet). The receiving
doctor — or, for an open referral, any doctor of the matching specialty —
can accept it (claiming it if it was open), decline it, or mark it complete
once the hand-off consultation has actually happened. The patient can always
see what's been referred about them and its current status, mirroring the
transparency already given for lab bookings and prescriptions elsewhere in
the app.

Status lifecycle: PENDING -> ACCEPTED -> COMPLETED, or PENDING -> DECLINED.
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, update as sa_update
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import require_role, require_approved_doctor
from core.notifications import NotificationService

router = APIRouter()


def _doctor_specialty(doctor_user_id: int, db: Session) -> str:
    """Same default ("General Medicine") used by modules/doctors/router.py's
    _ensure_profile, so an un-onboarded doctor's specialty matches an open
    referral the same way it would once they've actually set up a profile."""
    profile = (
        db.query(models.DoctorProfile)
        .filter(models.DoctorProfile.user_id == doctor_user_id)
        .first()
    )
    return (profile.specialty if profile and profile.specialty else "General Medicine")


def _is_open_specialty_match(referral: models.Referral, doctor: models.User, db: Session) -> bool:
    """True for an open referral (no doctor assigned yet) whose target
    specialty matches `doctor`'s own specialty, case-insensitively."""
    if referral.referred_to_doctor_id is not None:
        return False
    specialty = _doctor_specialty(doctor.id, db)
    return referral.specialty.strip().lower() == specialty.strip().lower()


def _owned_or_claimable(referral_id: int, current_user: models.User, db: Session) -> models.Referral:
    """The ownership rule shared by accept/decline: the referral must either
    be addressed directly to this doctor, or be open and match their
    specialty (in which case accepting claims it)."""
    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")
    is_target = referral.referred_to_doctor_id == current_user.id
    if not (is_target or _is_open_specialty_match(referral, current_user, db)):
        raise HTTPException(status_code=403, detail="This referral isn't addressed to you")
    return referral


@router.post("", response_model=schemas.ReferralResponse, status_code=201)
@router.post("/", response_model=schemas.ReferralResponse, status_code=201, include_in_schema=False)
async def create_referral(
    body: schemas.ReferralCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    if not body.patient_id and not body.family_profile_id:
        raise HTTPException(status_code=400, detail="patient_id or family_profile_id is required")

    family_profile = None
    patient_id = body.patient_id
    if body.family_profile_id:
        family_profile = (
            db.query(models.FamilyProfile)
            .filter(models.FamilyProfile.id == body.family_profile_id)
            .first()
        )
        if not family_profile:
            raise HTTPException(status_code=404, detail="Family profile not found")
        # The account this family member belongs to is the source of truth
        # for who the patient is — a client-supplied patient_id is only
        # trusted when no family_profile_id is given at all.
        patient_id = family_profile.user_id

    patient = (
        db.query(models.User)
        .filter(models.User.id == patient_id, models.User.role == "PATIENT")
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if body.referred_to_doctor_id is not None:
        if body.referred_to_doctor_id == current_user.id:
            raise HTTPException(status_code=400, detail="You cannot refer a patient to yourself")
        target = (
            db.query(models.User)
            .filter(models.User.id == body.referred_to_doctor_id, models.User.role == "DOCTOR")
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail="Target doctor not found")

    referral = models.Referral(
        patient_id=patient.id,
        family_profile_id=family_profile.id if family_profile else None,
        referring_doctor_id=current_user.id,
        referred_to_doctor_id=body.referred_to_doctor_id,
        specialty=body.specialty,
        reason=body.reason,
        notes=body.notes,
        status="PENDING",
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    if referral.referred_to_doctor_id:
        try:
            NotificationService(db).send_notification(
                user_id=referral.referred_to_doctor_id,
                title="New Patient Referral",
                body=f"Dr. {current_user.full_name or current_user.username} referred a patient to you ({referral.specialty}).",
                data={"type": "referral", "referral_id": str(referral.id)},
            )
        except Exception:
            pass  # notification failure must never block the referral being created

    return referral


@router.get("/incoming", response_model=List[schemas.ReferralResponse])
async def incoming_referrals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    """PENDING referrals this doctor needs to act on: addressed directly to
    them, or open (no doctor assigned) and matching their own specialty."""
    specialty = _doctor_specialty(current_user.id, db).strip().lower()
    return (
        db.query(models.Referral)
        .filter(
            models.Referral.status == "PENDING",
            or_(
                models.Referral.referred_to_doctor_id == current_user.id,
                (
                    models.Referral.referred_to_doctor_id.is_(None)
                    & (func.lower(models.Referral.specialty) == specialty)
                ),
            ),
        )
        .order_by(models.Referral.created_at.desc())
        .all()
    )


@router.get("/sent", response_model=List[schemas.ReferralResponse])
async def sent_referrals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    """Referrals this doctor created, regardless of status."""
    return (
        db.query(models.Referral)
        .filter(models.Referral.referring_doctor_id == current_user.id)
        .order_by(models.Referral.created_at.desc())
        .all()
    )


@router.get("/mine", response_model=List[schemas.ReferralResponse])
async def my_referrals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """A patient's own view of every referral made about them, newest first."""
    return (
        db.query(models.Referral)
        .filter(models.Referral.patient_id == current_user.id)
        .order_by(models.Referral.created_at.desc())
        .all()
    )


@router.put("/{referral_id}/accept", response_model=schemas.ReferralResponse)
async def accept_referral(
    referral_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    referral = _owned_or_claimable(referral_id, current_user, db)
    if referral.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Referral already {referral.status.lower()}")

    # Atomic claim: the UPDATE only matches (rowcount becomes 1) if status is
    # STILL "PENDING" at the moment this statement executes — closes the race
    # where two doctors of the same specialty both pass the PENDING check
    # above for the same open referral and could otherwise both "win" it.
    result = db.execute(
        sa_update(models.Referral)
        .where(models.Referral.id == referral.id, models.Referral.status == "PENDING")
        .values(status="ACCEPTED", referred_to_doctor_id=current_user.id)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This referral was just accepted or claimed by someone else.")
    db.commit()
    db.refresh(referral)

    try:
        NotificationService(db).send_notification(
            user_id=referral.referring_doctor_id,
            title="Referral Accepted",
            body=f"Dr. {current_user.full_name or current_user.username} accepted your referral.",
            data={"type": "referral", "referral_id": str(referral.id)},
        )
    except Exception:
        pass

    return referral


@router.put("/{referral_id}/decline", response_model=schemas.ReferralResponse)
async def decline_referral(
    referral_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    referral = _owned_or_claimable(referral_id, current_user, db)
    if referral.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Referral already {referral.status.lower()}")

    result = db.execute(
        sa_update(models.Referral)
        .where(models.Referral.id == referral.id, models.Referral.status == "PENDING")
        .values(status="DECLINED", resolved_at=datetime.utcnow())
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This referral was just resolved by someone else.")
    db.commit()
    db.refresh(referral)

    try:
        NotificationService(db).send_notification(
            user_id=referral.referring_doctor_id,
            title="Referral Declined",
            body=f"Dr. {current_user.full_name or current_user.username} declined your referral.",
            data={"type": "referral", "referral_id": str(referral.id)},
        )
    except Exception:
        pass

    return referral


@router.put("/{referral_id}/complete", response_model=schemas.ReferralResponse)
async def complete_referral(
    referral_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    """Only the doctor the referral now belongs to (referred_to_doctor_id)
    can close it out — an open referral must be accepted (which assigns it)
    before it can be completed."""
    referral = (
        db.query(models.Referral)
        .filter(
            models.Referral.id == referral_id,
            models.Referral.referred_to_doctor_id == current_user.id,
        )
        .first()
    )
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")
    if referral.status != "ACCEPTED":
        raise HTTPException(status_code=400, detail="Only an accepted referral can be marked complete")
    referral.status = "COMPLETED"
    referral.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(referral)
    return referral
