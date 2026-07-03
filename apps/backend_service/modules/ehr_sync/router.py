"""EHR / Family Health Wallet endpoints.

Contract summary (all under /api/v1/ehr):
- POST /issue_prescription  (DOCTOR)   structured prescription -> pharmacy queue + wallet record
- GET  /patient/{id}        (owner/DOCTOR/ADMIN) wallet records for a patient
- GET  /prescriptions/my    (PATIENT)  structured prescriptions for the caller
- GET  /records             (DOCTOR/ADMIN) recent records across patients (directory feed)
- POST /record              (auth)     patient-created record (OCR scan / note)
- POST /sync                (auth)     idempotent batch upload of offline-created records
- POST /vitals              (auth)     IoT vitals ingestion
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user, require_role
from modules.family.router import resolve_owned_profile

router = APIRouter()


@router.post("/issue_prescription", response_model=schemas.PrescriptionResponse)
async def issue_prescription(
    prescription: schemas.PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("DOCTOR")),
):
    """Called by the Doctor portal when a consultation ends. Writes the
    structured Prescription row (read by the pharmacy queue) plus a
    human-readable wallet record with a structured payload."""
    patient = (
        db.query(models.User)
        .filter(models.User.id == prescription.patient_id, models.User.role == "PATIENT")
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    medicines_list = [m.model_dump() for m in prescription.medicines]

    db_prescription = models.Prescription(
        appointment_id=prescription.appointment_id,
        patient_id=prescription.patient_id,
        family_profile_id=prescription.family_profile_id,
        doctor_id=current_user.id,
        medicines=medicines_list,
        dosage_instructions=prescription.dosage_instructions,
        diagnosis=prescription.diagnosis,
        notes=prescription.notes,
    )
    db.add(db_prescription)

    medicines_summary = "; ".join(
        f"{m.name} {m.dosage} ({m.frequency}, {m.duration})" for m in prescription.medicines
    ) or "No medicines listed"
    ehr_record = models.EHRRecord(
        patient_id=prescription.patient_id,
        family_profile_id=prescription.family_profile_id,
        record_type="prescription",
        title=prescription.diagnosis or "Prescription",
        content=(
            f"Diagnosis: {prescription.diagnosis or 'N/A'} | "
            f"Medicines: {medicines_summary} | Notes: {prescription.notes or ''}"
        ),
        payload={
            "medicines": medicines_list,
            "dosage_instructions": prescription.dosage_instructions,
            "diagnosis": prescription.diagnosis,
        },
        doctor_name=current_user.full_name or current_user.username,
    )
    db.add(ehr_record)
    db.commit()
    db.refresh(db_prescription)
    return db_prescription


@router.get("/patient/{patient_id}", response_model=List[schemas.EHRRecordResponse])
async def get_patient_records(
    patient_id: int,
    family_profile_id: Optional[int] = Query(None),
    record_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Health Wallet read path. Previously any authenticated user could read
    ANY patient's records; now restricted to the record owner, doctors, and
    admins."""
    if current_user.id != patient_id and current_user.role not in ("DOCTOR", "ADMIN"):
        raise HTTPException(status_code=403, detail="Not authorized to view these records")

    q = db.query(models.EHRRecord).filter(models.EHRRecord.patient_id == patient_id)
    if family_profile_id is not None:
        q = q.filter(models.EHRRecord.family_profile_id == family_profile_id)
    if record_type:
        q = q.filter(models.EHRRecord.record_type == record_type)
    return (
        q.order_by(models.EHRRecord.record_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/prescriptions/my", response_model=List[schemas.PrescriptionResponse])
async def my_prescriptions(
    family_profile_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Structured prescriptions for the logged-in patient (web portal's
    patient-facing prescriptions page)."""
    q = db.query(models.Prescription).filter(
        models.Prescription.patient_id == current_user.id
    )
    if family_profile_id is not None:
        resolve_owned_profile(family_profile_id, current_user, db)
        q = q.filter(models.Prescription.family_profile_id == family_profile_id)
    return (
        q.order_by(models.Prescription.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/records", response_model=List[schemas.EHRRecordResponse])
async def list_recent_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Recent records across all patients — feeds the doctor portal's
    patient directory. (The directory page previously called this route
    while it didn't exist; every request 404'd.)"""
    if current_user.role not in ("DOCTOR", "ADMIN"):
        raise HTTPException(status_code=403, detail="Doctors only")
    return (
        db.query(models.EHRRecord)
        .order_by(models.EHRRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/record", response_model=schemas.EHRRecordResponse, status_code=201)
async def create_record(
    record: schemas.EHRRecordCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Patient-created wallet record — the save step of the OCR camera flow
    ("outside prescription photo -> AI reads it -> confirm -> saved"), and
    manual notes."""
    resolve_owned_profile(record.family_profile_id, current_user, db)

    if record.client_uuid:
        existing = (
            db.query(models.EHRRecord)
            .filter(models.EHRRecord.client_uuid == record.client_uuid)
            .first()
        )
        if existing:
            return existing  # idempotent re-submission

    db_record = models.EHRRecord(
        patient_id=current_user.id,
        family_profile_id=record.family_profile_id,
        record_type=record.record_type,
        title=record.title,
        content=record.content,
        payload=record.payload,
        doctor_name=record.doctor_name,
        client_uuid=record.client_uuid,
        record_date=record.record_date,
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@router.post("/sync", response_model=schemas.EHRSyncResult)
async def sync_offline_records(
    batch: schemas.EHRSyncRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Idempotent batch upload of offline-created records.

    The mobile app queues records in Hive while offline and posts them here
    when connectivity returns. Each record carries a client-generated UUID;
    records whose UUID already exists are acknowledged as duplicates (safe
    no-ops), so retries and double-sends can never duplicate data.
    (This endpoint previously did not exist — the mobile sync path 404'd
    forever, silently defeating the offline-first design.)
    """
    synced: List[str] = []
    duplicates: List[str] = []

    for item in batch.records:
        resolve_owned_profile(item.family_profile_id, current_user, db)
        existing = (
            db.query(models.EHRRecord)
            .filter(models.EHRRecord.client_uuid == item.client_uuid)
            .first()
        )
        if existing:
            duplicates.append(item.client_uuid)
            continue
        db.add(
            models.EHRRecord(
                patient_id=current_user.id,
                family_profile_id=item.family_profile_id,
                record_type=item.record_type,
                title=item.title,
                content=item.content,
                payload=item.payload,
                doctor_name=item.doctor_name,
                client_uuid=item.client_uuid,
                record_date=item.record_date,
            )
        )
        synced.append(item.client_uuid)

    db.commit()
    return schemas.EHRSyncResult(synced=synced, duplicates=duplicates)


class VitalsPayload(BaseModel):
    device_id: str
    family_profile_id: Optional[int] = None
    heart_rate: int = Field(..., gt=0, lt=300)
    spo2: int = Field(..., ge=0, le=100)
    temperature: float = Field(..., gt=25.0, lt=45.0)


@router.post("/vitals")
async def store_vitals(
    payload: VitalsPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Persist streaming IoT vitals for the caller. patient_id is taken from
    the authenticated user (previously it was a client-supplied string,
    letting anyone attribute readings to anyone)."""
    resolve_owned_profile(payload.family_profile_id, current_user, db)
    db_vital = models.IoTVitals(
        patient_id=current_user.id,
        family_profile_id=payload.family_profile_id,
        device_id=payload.device_id,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        temperature=payload.temperature,
    )
    db.add(db_vital)
    db.commit()
    return {"status": "success"}
