"""Hospital self-registration and profile management.

Previously Hospital rows existed only as internally-managed data (seeded/
looked-up by modules/emergency/router.py's nearest-hospital SOS routing) —
no HOSPITAL-role user could register or manage their own hospital's record
at all. This mirrors the exact self-registration pattern already
established for PHARMACIST (modules/pharmacy_inventory/router.py's
/pharmacy/register + /pharmacy/me) and LAB (modules/lab/router.py's
/lab/register + /lab/me): one owned record per account, get via /me,
create-or-update via /register.

Registration is gated the same way doctors are: a new hospital starts
PENDING and stays invisible to SOS routing (see
modules/emergency/router.py's _nearest_hospital) until an ADMIN approves
it. Before this gate existed, registering an account with role=HOSPITAL
was enough to start receiving live emergency alerts carrying a patient's
name, GPS coordinates and voice recording.
"""
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import require_role
from core.cloudinary_service import cloudinary_client

router = APIRouter()
logger = logging.getLogger("gramcare.hospital")


def _my_hospital(user: models.User, db: Session) -> models.Hospital:
    hospital = (
        db.query(models.Hospital)
        .filter(models.Hospital.owner_user_id == user.id)
        .first()
    )
    if not hospital:
        raise HTTPException(
            status_code=409,
            detail="No hospital registered for this account yet. POST /hospital/register first.",
        )
    return hospital


@router.post("/register", response_model=schemas.HospitalResponse)
async def register_hospital(
    body: schemas.HospitalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("HOSPITAL")),
):
    """Create or update the caller's hospital profile (one per account)."""
    hospital = (
        db.query(models.Hospital)
        .filter(models.Hospital.owner_user_id == current_user.id)
        .first()
    )
    is_new = hospital is None
    if hospital:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(hospital, field, value)
        # Editing the details a reviewer approved sends it back for review:
        # an approved record must not be a way to swap in a different
        # hospital's name, address or coordinates after the fact.
        if hospital.verification_status == "APPROVED":
            hospital.verification_status = "PENDING"
            hospital.verification_notes = "Re-submitted after an edit to approved details."
    else:
        hospital = models.Hospital(
            owner_user_id=current_user.id,
            verification_status="PENDING",
            **body.model_dump(),
        )
        db.add(hospital)
    db.commit()
    db.refresh(hospital)

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="CREATE" if is_new else "UPDATE",
        resource="Hospital",
        resource_id=str(hospital.id),
        details={"name": hospital.name},
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return hospital


@router.get("/me", response_model=schemas.HospitalResponse)
async def my_hospital(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("HOSPITAL")),
):
    return _my_hospital(current_user, db)


@router.post("/me/license-document", response_model=schemas.HospitalResponse)
async def upload_license_document(
    body: schemas.ImageUploadRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("HOSPITAL")),
):
    """Uploads a scan of the hospital's registration/license document."""
    hospital = _my_hospital(current_user, db)
    uploaded = cloudinary_client.upload_base64(
        body.image_base64,
        folder=f"gramcare/hospital_license_documents/{current_user.id}",
        resource_type="auto",
        db=db,
    )
    if not uploaded:
        raise HTTPException(status_code=503, detail="Document upload is temporarily unavailable.")

    hospital.license_document_url = uploaded["url"]
    db.commit()
    db.refresh(hospital)

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="UPLOAD",
        resource="HospitalLicenseDocument",
        resource_id=str(hospital.id),
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return hospital


# ==========================================================
# Government review — the gate SOS routing depends on
# ==========================================================

@router.get("/pending", response_model=List[schemas.HospitalResponse])
async def pending_hospitals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("ADMIN")),
):
    """Hospitals waiting on review, oldest first."""
    return (
        db.query(models.Hospital)
        .filter(models.Hospital.verification_status == "PENDING")
        .order_by(models.Hospital.created_at.asc())
        .all()
    )


def _review(hospital_id: int, status: str, notes, reviewer, request, db):
    hospital = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    hospital.verification_status = status
    hospital.verification_notes = notes
    hospital.reviewed_by_user_id = reviewer.id
    hospital.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(hospital)

    db.add(models.AuditLog(
        user_id=reviewer.id,
        action=status,
        resource="Hospital",
        resource_id=str(hospital.id),
        details={"name": hospital.name, "notes": notes},
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()
    logger.info("Hospital %d (%s) marked %s by admin %d.",
                hospital.id, hospital.name, status, reviewer.id)
    return hospital


@router.put("/{hospital_id}/approve", response_model=schemas.HospitalResponse)
async def approve_hospital(
    hospital_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("ADMIN")),
):
    """Make a hospital visible to SOS routing.

    This is the only thing that puts a hospital in front of a real
    emergency, so it is deliberately an explicit human decision rather than
    anything automatic.
    """
    return _review(hospital_id, "APPROVED", None, current_user, request, db)


@router.put("/{hospital_id}/reject", response_model=schemas.HospitalResponse)
async def reject_hospital(
    hospital_id: int,
    body: schemas.HospitalApprovalAction,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("ADMIN")),
):
    return _review(hospital_id, "REJECTED", body.reason, current_user, request, db)
