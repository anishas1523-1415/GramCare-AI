"""Doctor directory, professional profiles and availability slots.

Planning doc requirements served here:
- Patients see a doctor list with specialty / experience / fee before
  booking ("டாக்டர்களோட சிறப்பு, அனுபவம், அப்புறம் கட்டணம் எல்லாமே தெரியும்").
- Doctors publish their availability calendar; bookings only happen against
  published slots ("அந்த நேரத்துலதான் யூசர்ஸ் அப்பாயின்ட்மென்ட் புக் செய்ய முடியும்").
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user, require_role, require_approved_doctor
from core.cloudinary_service import cloudinary_client
from core.email_service import get_email_service, EmailService

router = APIRouter()
logger = logging.getLogger("gramcare.doctors")


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
        "bio": profile.bio,
        "languages": profile.languages,
        "is_available": bool(profile.is_available),
        "photo_url": profile.photo_url,
    }


def _to_self(user: models.User, profile: models.DoctorProfile) -> dict:
    """Like _to_public, plus the government verification state — only ever
    returned to the doctor themself (GET/PUT /doctors/me), never to
    patients browsing the directory."""
    return {
        **_to_public(user, profile),
        "license_number": profile.license_number,
        "license_document_url": profile.license_document_url,
        "service_hours": profile.service_hours,
        "verification_status": profile.verification_status or "PENDING",
        "rejection_reason": profile.rejection_reason,
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
    """Public doctor directory (authenticated users). Only APPROVED doctors
    appear — an unverified doctor must not be bookable, however complete
    their profile looks (planning doc: government approval prevents fake
    doctors from reaching patients)."""
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
        if profile.verification_status != "APPROVED":
            continue
        public = _to_public(doc, profile)
        if specialty and specialty.lower() not in public["specialty"].lower():
            continue
        results.append(public)
    return results


@router.get("/me", response_model=schemas.DoctorSelfResponse)
async def my_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    """A doctor's own profile, including their verification status — always
    accessible regardless of PENDING/REJECTED, so the app can show an
    "application under review" screen instead of the dashboard."""
    return _to_self(current_user, _ensure_profile(current_user, db))


@router.put("/me", response_model=schemas.DoctorSelfResponse)
async def update_my_profile(
    update: schemas.DoctorProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    """Editable even while PENDING/REJECTED — a doctor must be able to fix
    and resubmit their application details. verification_status itself is
    not in DoctorProfileUpdate, so it can't be self-approved."""
    profile = _ensure_profile(current_user, db)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return _to_self(current_user, profile)


@router.post("/me/photo", response_model=schemas.DoctorSelfResponse)
async def upload_my_photo(
    body: schemas.ImageUploadRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    """Uploads the doctor's own profile photo, shown in the patient-facing
    directory alongside specialty/experience/fee (planning doc booking flow)."""
    profile = _ensure_profile(current_user, db)
    uploaded = cloudinary_client.upload_base64(
        body.image_base64, folder=f"gramcare/doctor_photos/{current_user.id}"
    )
    if not uploaded:
        raise HTTPException(status_code=503, detail="Photo upload is temporarily unavailable.")

    profile.photo_url = uploaded["url"]
    db.commit()
    db.refresh(profile)
    return _to_self(current_user, profile)


@router.post("/me/license-document", response_model=schemas.DoctorSelfResponse)
async def upload_my_license_document(
    request: Request,
    body: schemas.ImageUploadRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    """Uploads a scan of the doctor's medical registration/license — the
    document a government reviewer checks before approving. Re-uploading
    while PENDING/REJECTED is allowed (fixing a bad scan and resubmitting)."""
    profile = _ensure_profile(current_user, db)
    uploaded = cloudinary_client.upload_base64(
        body.image_base64,
        folder=f"gramcare/doctor_license_documents/{current_user.id}",
        resource_type="auto",  # image or PDF scan
    )
    if not uploaded:
        raise HTTPException(status_code=503, detail="Document upload is temporarily unavailable.")

    profile.license_document_url = uploaded["url"]
    db.commit()
    db.refresh(profile)

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="UPLOAD",
        resource="DoctorLicenseDocument",
        resource_id=str(profile.id),
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return _to_self(current_user, profile)


# ==========================================================
# Government verification (ADMIN-only)
# ==========================================================

@router.get("/pending", response_model=List[schemas.DoctorSelfResponse])
async def list_pending_doctors(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("ADMIN")),
):
    """Doctor applications awaiting government review, oldest first. Iterates
    DOCTOR users (not the DoctorProfile table directly) and lazily creates
    a profile via _ensure_profile for any that don't have one yet — a
    freshly-registered doctor who hasn't touched /doctors/me at all is
    still PENDING and must show up here, the same way list_doctors already
    handles doctors with no explicit profile."""
    doctors = (
        db.query(models.User)
        .filter(models.User.role == "DOCTOR", models.User.is_active == True)  # noqa: E712
        .all()
    )
    results = []
    for user in doctors:
        profile = _ensure_profile(user, db)
        if profile.verification_status == "PENDING":
            results.append((profile.created_at, _to_self(user, profile)))
    results.sort(key=lambda pair: pair[0])
    return [r for _, r in results]


async def _notify_doctor(email_service: EmailService, user: models.User, approved: bool, reason: Optional[str] = None):
    subject = "Your GramCare AI doctor application has been approved" if approved else "Your GramCare AI doctor application was not approved"
    if approved:
        body = f"<p>Hello Dr. {user.full_name},</p><p>Your doctor account has been verified and approved. You can now log in to the Doctor app and Hospital+Doctor Web portal.</p>"
    else:
        body = f"<p>Hello Dr. {user.full_name},</p><p>Your doctor application was not approved.</p><p><strong>Reason:</strong> {reason}</p><p>You can update your application details and resubmit.</p>"
    try:
        await email_service.send_email(to_email=user.email, subject=subject, html_content=body)
    except Exception as e:  # best-effort — must never block the approval/rejection itself
        logger.warning("Failed to send doctor verification email to %s: %s", user.email, e)


@router.put("/{doctor_id}/approve", response_model=schemas.DoctorSelfResponse)
async def approve_doctor(
    doctor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("ADMIN")),
    email_service: EmailService = Depends(get_email_service),
):
    user = db.query(models.User).filter(models.User.id == doctor_id, models.User.role == "DOCTOR").first()
    if not user:
        raise HTTPException(status_code=404, detail="Doctor not found")
    profile = _ensure_profile(user, db)

    profile.verification_status = "APPROVED"
    profile.rejection_reason = None
    profile.reviewed_by_user_id = current_user.id
    profile.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(profile)

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="APPROVE",
        resource="DoctorProfile",
        resource_id=str(profile.id),
        details={"doctor_user_id": user.id, "license_number": profile.license_number},
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    await _notify_doctor(email_service, user, approved=True)
    return _to_self(user, profile)


@router.put("/{doctor_id}/reject", response_model=schemas.DoctorSelfResponse)
async def reject_doctor(
    doctor_id: int,
    body: schemas.DoctorApprovalAction,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("ADMIN")),
    email_service: EmailService = Depends(get_email_service),
):
    user = db.query(models.User).filter(models.User.id == doctor_id, models.User.role == "DOCTOR").first()
    if not user:
        raise HTTPException(status_code=404, detail="Doctor not found")
    profile = _ensure_profile(user, db)

    profile.verification_status = "REJECTED"
    profile.rejection_reason = body.reason
    profile.reviewed_by_user_id = current_user.id
    profile.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(profile)

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="REJECT",
        resource="DoctorProfile",
        resource_id=str(profile.id),
        details={"doctor_user_id": user.id, "reason": body.reason},
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    await _notify_doctor(email_service, user, approved=False, reason=body.reason)
    return _to_self(user, profile)


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
    current_user: models.User = Depends(require_approved_doctor()),
):
    """Publish one or more availability windows. Requires an APPROVED
    doctor — publishing a slot immediately makes it bookable by patients."""
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
