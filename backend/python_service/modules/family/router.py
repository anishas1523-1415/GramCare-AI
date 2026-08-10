"""Family Profiles — the planning doc's "one box per family member".

Every profile is owned by (scoped to) the authenticated account: a user can
only ever see or modify their own family members. Downstream features
(triage, EHR, appointments, vitals) reference these profiles via
family_profile_id; `resolve_owned_profile` is the shared guard they use to
verify a client-supplied profile id actually belongs to the caller.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user
from core.cloudinary_service import cloudinary_client

router = APIRouter()


def resolve_owned_profile(
    family_profile_id: Optional[int],
    user: models.User,
    db: Session,
) -> Optional[models.FamilyProfile]:
    """Shared ownership guard used by every profile-scoped feature.

    Returns the profile if `family_profile_id` is set and owned by `user`;
    returns None if `family_profile_id` is None (meaning: the account owner
    themself); raises 403/404 otherwise.
    """
    if family_profile_id is None:
        return None
    profile = (
        db.query(models.FamilyProfile)
        .filter(models.FamilyProfile.id == family_profile_id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Family profile not found")
    if profile.user_id != user.id and user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not your family profile")
    return profile


@router.get("", response_model=List[schemas.FamilyProfileResponse])
@router.get("/", response_model=List[schemas.FamilyProfileResponse], include_in_schema=False)
async def list_profiles(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.FamilyProfile)
        .filter(models.FamilyProfile.user_id == current_user.id)
        .order_by(models.FamilyProfile.created_at)
        .all()
    )


@router.post("", response_model=schemas.FamilyProfileResponse, status_code=201)
@router.post("/", response_model=schemas.FamilyProfileResponse, status_code=201, include_in_schema=False)
async def create_profile(
    profile: schemas.FamilyProfileCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = (
        db.query(models.FamilyProfile)
        .filter(models.FamilyProfile.user_id == current_user.id)
        .count()
    )
    if count >= 15:
        raise HTTPException(status_code=400, detail="Family profile limit reached (15)")

    db_profile = models.FamilyProfile(user_id=current_user.id, **profile.model_dump())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


@router.put("/{profile_id}", response_model=schemas.FamilyProfileResponse)
async def update_profile(
    profile_id: int,
    update: schemas.FamilyProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = resolve_owned_profile(profile_id, current_user, db)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/{profile_id}/photo", response_model=schemas.FamilyProfileResponse)
async def upload_profile_photo(
    profile_id: int,
    body: schemas.ImageUploadRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Uploads a family member's photo to Cloudinary and sets it as their
    profile picture in one call — used as the low-literacy "photo button"
    for family-member selection (planning doc: "எழுத்து படிக்க தெரியாதவங்க
    கூட புகைப்படத்தைப் பார்த்து தேர்ந்தெடுக்கலாம்")."""
    # profile_id is a required path param (never None here), so
    # resolve_owned_profile always either returns the owned profile or
    # raises 403/404 — it never falls through the "None = caller themself"
    # branch that a null family_profile_id would take elsewhere.
    profile = resolve_owned_profile(profile_id, current_user, db)

    uploaded = cloudinary_client.upload_base64(
        body.image_base64, folder=f"gramcare/family_photos/{current_user.id}"
    )
    if not uploaded:
        raise HTTPException(status_code=503, detail="Photo upload is temporarily unavailable.")

    profile.photo_url = uploaded["url"]
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = resolve_owned_profile(profile_id, current_user, db)
    # Health records for this member are intentionally KEPT (planning doc:
    # records must never be silently lost); they simply become unscoped.
    db.query(models.EHRRecord).filter(
        models.EHRRecord.family_profile_id == profile_id
    ).update({models.EHRRecord.family_profile_id: None})
    db.delete(profile)
    db.commit()
    return None
