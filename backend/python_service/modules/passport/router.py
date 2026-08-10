"""Digital Health Passport — a minimal emergency-response profile (blood
group, allergies, chronic conditions, emergency contacts, recent
medicines) readable via QR code without an account or login. An EMT or
hospital front desk scanning a patient's phone/wristband has no GramCare
credentials, so this has to work unauthenticated.

Privacy: the public lookup is keyed by a high-entropy capability token
(secrets.token_urlsafe, not the user's id), not by username or email, so
knowing someone's GramCare account tells you nothing about their passport
URL, and the passport URL can't be enumerated. Deliberately minimal
response shape — no email, username, or address, only what's useful in
an emergency. Owners can regenerate the token to invalidate a lost/shared
QR code.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from modules.auth.router import require_role
from core.ratelimit import rate_limit

router = APIRouter()


@router.get("/me", response_model=schemas.PassportSelfResponse)
def get_my_passport(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    return current_user


@router.put("/me", response_model=schemas.PassportSelfResponse)
def update_my_passport(
    update: schemas.PassportUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    if update.blood_group is not None:
        current_user.blood_group = update.blood_group or None
    if update.allergies is not None:
        current_user.allergies = update.allergies or None
    if update.chronic_conditions is not None:
        current_user.chronic_conditions = update.chronic_conditions or None
    # First save generates the sharable token — a passport with nothing
    # filled in yet has no reason to be scannable.
    if not current_user.passport_token:
        current_user.passport_token = secrets.token_urlsafe(24)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/regenerate-token", response_model=schemas.PassportSelfResponse)
def regenerate_passport_token(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """Invalidates any previously shared/printed QR code — e.g. after
    losing a physical card or wristband with the old code on it."""
    current_user.passport_token = secrets.token_urlsafe(24)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get(
    "/{token}",
    response_model=schemas.PassportPublicResponse,
    dependencies=[Depends(rate_limit("passport_lookup", 20, 60))],
)
def view_passport(token: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.passport_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Passport not found.")

    contacts = (
        db.query(models.EmergencyContact)
        .filter(models.EmergencyContact.user_id == user.id)
        .all()
    )
    recent_prescriptions = (
        db.query(models.Prescription)
        .filter(models.Prescription.patient_id == user.id)
        .order_by(models.Prescription.created_at.desc())
        .limit(3)
        .all()
    )
    medicines = []
    for rx in recent_prescriptions:
        for m in (rx.medicines or []):
            medicines.append(schemas.PassportMedicine(
                name=m.get("name", ""),
                dosage=m.get("dosage"),
                frequency=m.get("frequency"),
            ))

    return schemas.PassportPublicResponse(
        full_name=user.full_name,
        blood_group=user.blood_group,
        allergies=user.allergies,
        chronic_conditions=user.chronic_conditions,
        emergency_contacts=[
            schemas.PassportEmergencyContact(name=c.name, phone=c.phone, relation=c.relation)
            for c in contacts
        ],
        recent_medicines=medicines,
    )
