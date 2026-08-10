"""Hospital self-registration and profile management.

Previously Hospital rows existed only as internally-managed data (seeded/
looked-up by modules/emergency/router.py's nearest-hospital SOS routing) —
no HOSPITAL-role user could register or manage their own hospital's record
at all. This mirrors the exact self-registration pattern already
established for PHARMACIST (modules/pharmacy_inventory/router.py's
/pharmacy/register + /pharmacy/me) and LAB (modules/lab/router.py's
/lab/register + /lab/me): one owned record per account, get via /me,
create-or-update via /register.

Data-collection only for now — instant access, no government approval
gate (unlike DoctorProfile's verification_status). If that changes later,
the gate belongs here plus a corresponding check in
modules.auth.router (mirroring require_approved_doctor).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import require_role
from core.cloudinary_service import cloudinary_client

router = APIRouter()


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
    else:
        hospital = models.Hospital(owner_user_id=current_user.id, **body.model_dump())
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
