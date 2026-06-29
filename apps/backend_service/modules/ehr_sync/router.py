from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
import models
from database import get_db
from modules.auth.router import get_current_user

router = APIRouter()

class Prescription(BaseModel):
    patient_id: str
    doctor_id: str
    medicines: str # Simplified to string for now to match DB schema
    notes: str

class PrescriptionResponse(Prescription):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True

@router.post("/issue_prescription", response_model=PrescriptionResponse)
async def issue_prescription(prescription: Prescription, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Called by the Doctor Suite.
    Saves the prescription to the persistent EHR database.
    """
    db_record = models.EHRRecord(
        patient_id=prescription.patient_id,
        record_type="prescription",
        content=f"Medicines: {prescription.medicines} | Notes: {prescription.notes}",
        doctor_name=prescription.doctor_id
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    
    return {
        "id": db_record.id,
        "patient_id": db_record.patient_id,
        "doctor_id": db_record.doctor_name,
        "medicines": prescription.medicines,
        "notes": prescription.notes,
        "timestamp": db_record.created_at
    }

@router.get("/patient/{patient_id}", response_model=List[PrescriptionResponse])
async def get_patient_records(patient_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Called by the Patient App (Health Wallet).
    Retrieves all records for a specific patient.
    """
    records = db.query(models.EHRRecord).filter(models.EHRRecord.patient_id == patient_id).all()
    
    responses = []
    for r in records:
        responses.append({
            "id": r.id,
            "patient_id": r.patient_id,
            "doctor_id": r.doctor_name,
            "medicines": r.content,
            "notes": "",
            "timestamp": r.created_at
        })
    return responses

class VitalsPayload(BaseModel):
    patient_id: str
    device_id: str
    heart_rate: int
    spo2: int
    temperature: float

@router.post("/vitals")
async def store_vitals(payload: VitalsPayload, db: Session = Depends(get_db)):
    """
    Called by the Patient App to persist streaming IoT vitals.
    """
    db_vital = models.IoTVitals(
        patient_id=payload.patient_id,
        device_id=payload.device_id,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        temperature=payload.temperature
    )
    db.add(db_vital)
    db.commit()
    return {"status": "success"}
