import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from database import get_db
import models
import schemas
from modules.auth.router import get_current_user

router = APIRouter()
logger = logging.getLogger("gramcare.emergency")

@router.post("/trigger", response_model=schemas.EmergencySOSResponse)
async def trigger_sos(
    sos_data: schemas.EmergencySOSCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Trigger an Emergency SOS alert (Patient only)."""
    if current_user.role != "PATIENT":
        raise HTTPException(status_code=403, detail="Only patients can trigger SOS.")
        
    db_sos = models.EmergencySOS(
        patient_id=current_user.id,
        location_lat=sos_data.location_lat,
        location_lng=sos_data.location_lng,
        location_text=sos_data.location_text,
        severity=sos_data.severity,
        status="ACTIVE"
    )
    db.add(db_sos)
    db.commit()
    db.refresh(db_sos)
    logger.info("SOS %d triggered by patient %d.", db_sos.id, current_user.id)
    return db_sos

@router.get("/active", response_model=List[schemas.EmergencySOSResponse])
async def get_active_emergencies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all active SOS emergencies (Doctor/Admin only)."""
    if current_user.role not in ["DOCTOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized to view active emergencies.")
        
    emergencies = db.query(models.EmergencySOS).filter(
        models.EmergencySOS.status == "ACTIVE"
    ).order_by(models.EmergencySOS.created_at.desc()).all()
    return emergencies

@router.put("/{sos_id}/respond", response_model=schemas.EmergencySOSResponse)
async def respond_to_sos(
    sos_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """A doctor responds to an active SOS."""
    if current_user.role != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can respond to SOS.")
        
    sos = db.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS not found.")
        
    if sos.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="SOS is already being handled or resolved.")
        
    sos.status = "RESPONDED"
    sos.responded_by = current_user.id
    db.commit()
    db.refresh(sos)
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
    return sos
