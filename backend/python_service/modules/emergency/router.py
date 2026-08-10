"""Emergency SOS — trigger, respond, resolve, contacts, hospital escalation.

Planning-doc rules implemented here:
- SOS carries GPS/location, an optional transcribed voice note, and the
  family member concerned.
- Emergency contacts are stored per account and returned to clients so the
  mobile app can run its offline SMS fallback.
- Unacknowledged SOS alerts escalate: after ESCALATION_AFTER_SECONDS the
  alert is (re)assigned to the next-nearest hospital and its escalation
  level increments ("ரெஸ்பான்ஸ் வரலைன்னா அலர்ட் அடுத்த ஹாஸ்பிடலுக்கு
  தானாகவே மாற்றப்படும்").
- Acceptance flips status to RESPONDED — the "Help En Route" state that
  stops double dispatch.
"""
import logging
import math
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from database import get_db
import models
import schemas
from modules.auth.router import get_current_user, require_role, require_approved_doctor
from modules.family.router import resolve_owned_profile
from core.maps import maps_client
from core.ratelimit import rate_limit

router = APIRouter()
logger = logging.getLogger("gramcare.emergency")

ESCALATION_AFTER_SECONDS = int(os.getenv("SOS_ESCALATION_AFTER_SECONDS", "180"))


def _nearest_hospital(
    db: Session,
    lat: Optional[float],
    lng: Optional[float],
    exclude_ids: List[int],
) -> Optional[models.Hospital]:
    q = db.query(models.Hospital)
    if exclude_ids:
        q = q.filter(~models.Hospital.id.in_(exclude_ids))
    hospitals = q.all()
    if not hospitals:
        return None
    if lat is None or lng is None:
        return hospitals[0]

    # Coarse filter (math) to get top 5 before hitting the API
    def dist(h: models.Hospital) -> float:
        if h.lat is None or h.lng is None:
            return 1e9
        return math.hypot(h.lat - lat, h.lng - lng)

    top_hospitals = sorted(hospitals, key=dist)[:5]

    # Distance Matrix API for exact driving time
    dest_list = [{"id": h.id, "lat": h.lat, "lng": h.lng} for h in top_hospitals if h.lat and h.lng]
    best = maps_client.get_nearest_destination(lat, lng, dest_list)

    if best:
        # Return the actual Hospital object corresponding to best['id']
        return next((h for h in top_hospitals if h.id == best['id']), top_hospitals[0])

    # Fallback to straight line math if API fails
    return top_hospitals[0]


def escalate_stale_sos(db: Session) -> int:
    """Escalate every ACTIVE SOS that has waited too long without a
    response. Called by the startup background loop and directly testable.
    Returns the number of alerts escalated."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(seconds=ESCALATION_AFTER_SECONDS)
    # The escalation clock is last_escalated_at once escalated, else created_at.
    # created_at is never mutated, preserving the true creation time for audit.
    stale = (
        db.query(models.EmergencySOS)
        .filter(
            models.EmergencySOS.status == "ACTIVE",
            func.coalesce(
                models.EmergencySOS.last_escalated_at,
                models.EmergencySOS.created_at,
            )
            <= cutoff,
        )
        .all()
    )
    count = 0
    for sos in stale:
        exclude = [sos.assigned_hospital_id] if sos.assigned_hospital_id else []
        next_hospital = _nearest_hospital(db, sos.location_lat, sos.location_lng, exclude)
        if next_hospital and next_hospital.id != sos.assigned_hospital_id:
            sos.assigned_hospital_id = next_hospital.id
            sos.escalation_level = (sos.escalation_level or 0) + 1
            # Reset the escalation clock only — the new hospital gets a full
            # window — without destroying created_at.
            sos.last_escalated_at = now
            count += 1
            logger.warning(
                "SOS %d escalated to level %d -> hospital %s",
                sos.id, sos.escalation_level, next_hospital.name,
            )
    if count:
        db.commit()
    return count


# ==========================================================
# SOS lifecycle
# ==========================================================

@router.post("/trigger", response_model=schemas.EmergencySOSResponse, dependencies=[Depends(rate_limit("sos_trigger", 3, 60))])
async def trigger_sos(
    sos_data: schemas.EmergencySOSCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT"))
):
    """Trigger an Emergency SOS alert (Patient only). Immediately assigned
    to the nearest hospital's emergency desk."""

    resolve_owned_profile(sos_data.family_profile_id, current_user, db)
    hospital = _nearest_hospital(db, sos_data.location_lat, sos_data.location_lng, [])

    loc_text = sos_data.location_text
    if (not loc_text or loc_text == "GPS unavailable" or loc_text == "location unknown") and sos_data.location_lat and sos_data.location_lng:
        geo = maps_client.reverse_geocode(sos_data.location_lat, sos_data.location_lng)
        if geo:
            loc_text = geo

    db_sos = models.EmergencySOS(
        patient_id=current_user.id,
        family_profile_id=sos_data.family_profile_id,
        location_lat=sos_data.location_lat,
        location_lng=sos_data.location_lng,
        location_text=loc_text,
        voice_note=sos_data.voice_note,
        severity=sos_data.severity,
        status="ACTIVE",
        escalation_level=0,
        assigned_hospital_id=hospital.id if hospital else None,
    )
    db.add(db_sos)
    db.commit()
    db.refresh(db_sos)
    logger.info("SOS %d triggered by patient %d (hospital=%s).",
                db_sos.id, current_user.id, hospital.name if hospital else "none")
    return db_sos


@router.get("/active", response_model=List[schemas.EmergencySOSResponse])
async def get_active_emergencies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor("HOSPITAL"))
):
    """All active SOS emergencies (Doctor/Hospital desk/Admin)."""

    return (
        db.query(models.EmergencySOS)
        .filter(models.EmergencySOS.status == "ACTIVE")
        .order_by(models.EmergencySOS.created_at.desc())
        .all()
    )


@router.get("/mine", response_model=List[schemas.EmergencySOSResponse])
async def my_sos_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The caller's own SOS alerts — lets the patient app show delivery/
    "Help En Route" status."""
    return (
        db.query(models.EmergencySOS)
        .filter(models.EmergencySOS.patient_id == current_user.id)
        .order_by(models.EmergencySOS.created_at.desc())
        .limit(20)
        .all()
    )


@router.put("/{sos_id}/respond", response_model=schemas.EmergencySOSResponse)
async def respond_to_sos(
    sos_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor("HOSPITAL"))
):
    """A doctor or hospital desk accepts an SOS ("Help En Route")."""

    sos = db.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS not found.")

    if sos.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="SOS is already being handled or resolved.")

    sos.status = "RESPONDED"
    sos.responded_by = current_user.id
    db.commit()
    db.refresh(sos)
    
    from core.notifications import NotificationService
    NotificationService(db).notify_sos_alert(
        user_id=sos.patient_id,
        hospital_name=current_user.full_name or "Emergency Desk",
        status="RESPONDED"
    )
    
    return sos


@router.put("/{sos_id}/resolve", response_model=schemas.EmergencySOSResponse)
async def resolve_sos(
    sos_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark an SOS as resolved."""
    sos = db.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS not found.")

    if current_user.role not in ["ADMIN"] and sos.responded_by != current_user.id and sos.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to resolve this SOS.")

    sos.status = "RESOLVED"
    sos.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sos)
    
    from core.notifications import NotificationService
    NotificationService(db).notify_sos_alert(
        user_id=sos.patient_id,
        hospital_name=current_user.full_name or "Emergency Desk",
        status="RESOLVED"
    )
    
    return sos


# ==========================================================
# Emergency contacts
# ==========================================================

@router.get("/contacts", response_model=List[schemas.EmergencyContactResponse])
async def list_contacts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.EmergencyContact)
        .filter(models.EmergencyContact.user_id == current_user.id)
        .order_by(models.EmergencyContact.created_at)
        .all()
    )


@router.post("/contacts", response_model=schemas.EmergencyContactResponse, status_code=201)
async def add_contact(
    contact: schemas.EmergencyContactCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = (
        db.query(models.EmergencyContact)
        .filter(models.EmergencyContact.user_id == current_user.id)
        .count()
    )
    if count >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 emergency contacts.")
    db_contact = models.EmergencyContact(user_id=current_user.id, **contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    contact = (
        db.query(models.EmergencyContact)
        .filter(
            models.EmergencyContact.id == contact_id,
            models.EmergencyContact.user_id == current_user.id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return None
