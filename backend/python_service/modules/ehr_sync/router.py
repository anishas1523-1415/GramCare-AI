"""EHR / Family Health Wallet endpoints.

Contract summary (all under /api/v1/ehr):
- POST /issue_prescription  (DOCTOR)   structured prescription -> pharmacy queue + wallet record
- GET  /patient/{id}        (owner/DOCTOR/ADMIN) wallet records for a patient
- GET  /prescriptions/my    (PATIENT)  structured prescriptions for the caller
- GET  /records             (DOCTOR/ADMIN) recent records across patients (directory feed)
- POST /record              (auth)     patient-created record (OCR scan / note)
- POST /sync                (auth)     idempotent batch upload of offline-created records
- POST /vitals              (auth)     IoT vitals ingestion
- POST /upload               (auth)     Cloudinary image upload; returns a URL to embed
                                        in a record's `payload` (e.g. the original
                                        prescription/lab photo alongside its OCR text)
- GET  /fhir-export         (PATIENT/family owner) FHIR-R4-*shaped* export of the
                                        Family Health Wallet — see core/fhir_export.py's
                                        module docstring for exactly what that does and
                                        does not mean (not a FHIR server, no SMART auth).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user, require_role, require_approved_doctor
from modules.family.router import resolve_owned_profile

# How far ahead of the server's clock a client-supplied record_date may sit.
# A device whose clock is wrong produces wrong clinical dates, and the wallet
# orders by record_date desc, so a skewed clock silently reorders a patient's
# history. Experiment A (finding F-A4) measured dates ten years either way
# being accepted verbatim. A small forward tolerance covers ordinary clock
# drift without letting a record claim to be from the future.
RECORD_DATE_FUTURE_TOLERANCE = timedelta(hours=24)


def clamp_record_date(value, now=None):
    """Return a record_date that cannot be in the future beyond tolerance.

    A missing date becomes the server's now. A date further ahead than the
    tolerance is pulled back to now. Past dates are left alone: a patient
    legitimately records something that happened days ago while offline, and
    there is no defensible lower bound to impose on a clinical history.
    """
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if value is None:
        return now
    naive = value.replace(tzinfo=None) if value.tzinfo else value
    if naive > now + RECORD_DATE_FUTURE_TOLERANCE:
        return now
    return naive

from core.drug_interactions import check_interactions
from core.cloudinary_service import cloudinary_client
from core.fhir_export import build_fhir_bundle
from modules.ai_assist.router import _parse_duration_days

router = APIRouter()


@router.post("/issue_prescription", response_model=schemas.PrescriptionResponse)
async def issue_prescription(
    request: Request,
    prescription: schemas.PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
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

    # A doctor writes prescriptions for any patient, but a claimed
    # family_profile_id must actually belong to THAT patient's own account —
    # same ownership guard every other family-scoped endpoint in this file
    # uses. Without this, a mislabeled family_profile_id (client bug or a
    # malicious doctor) would attach a prescription/EHR record to a
    # different patient's family member.
    resolve_owned_profile(prescription.family_profile_id, patient, db)

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
    
    # Audit log
    db.add(models.AuditLog(
        user_id=current_user.id,
        action="CREATE",
        resource="Prescription",
        resource_id=str(db_prescription.id),
        details={"patient_id": prescription.patient_id, "diagnosis": prescription.diagnosis},
        ip_address=request.client.host if request.client else None
    ))
    db.commit()

    # Medicine Interaction Alerts: check the newly-prescribed medicines
    # against whatever else this patient is currently, actively taking
    # (same start-date + duration logic as the AI Doctor Assistant's
    # patient-summary "active medicines" detection).
    now = datetime.utcnow()
    other_rx = (
        db.query(models.Prescription)
        .filter(
            models.Prescription.patient_id == prescription.patient_id,
            models.Prescription.id != db_prescription.id,
        )
        .order_by(models.Prescription.created_at.desc())
        .limit(20)
        .all()
    )
    currently_active_names: List[str] = []
    for rx in other_rx:
        for med in (rx.medicines or []):
            days = _parse_duration_days(med.get("duration", ""))
            if (rx.created_at + timedelta(days=days)) >= now:
                currently_active_names.append(med.get("name", ""))

    new_names = [m.name for m in prescription.medicines]
    db_prescription.interaction_warnings = check_interactions(new_names + currently_active_names)

    return db_prescription


@router.get("/patient/{patient_id}", response_model=List[schemas.EHRRecordResponse])
async def get_patient_records(
    patient_id: int,
    request: Request,
    family_profile_id: Optional[int] = Query(None),
    record_type: Optional[str] = Query(None),
    # Incremental/low-bandwidth sync: a mobile client that already has every
    # record created before its last successful sync can pass that
    # timestamp back here instead of re-downloading the entire wallet every
    # time (low-bandwidth optimization for rural connectivity).
    since: Optional[datetime] = Query(
        None, description="Only return records created after this UTC timestamp (incremental sync)."
    ),
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
    if since is not None:
        q = q.filter(models.EHRRecord.created_at > since)

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="READ",
        resource="EHRRecord",
        details={"patient_id": patient_id, "family_profile_id": family_profile_id},
        ip_address=request.client.host if request.client else None
    ))
    db.commit()
    
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
    current_user: models.User = Depends(require_approved_doctor("ADMIN")),
):
    """Recent records for patients this doctor actually has a relationship
    with — the doctor portal's patient directory.

    Found by the cross-tenant isolation matrix (research/experiments/exp_g):
    this returned recent records across EVERY patient in the system to any
    approved doctor, up to 200 at a time, with no care relationship and —
    unlike GET /ehr/patient/{id} — no audit row. A doctor in one district
    could page through the wallet contents of patients they had never met.

    A relationship is an appointment with, or a prescription from, this
    doctor. ADMIN keeps the unscoped view, which is the role's purpose.
    """
    q = db.query(models.EHRRecord)

    if current_user.role != "ADMIN":
        mine = (
            db.query(models.Appointment.patient_id)
            .filter(models.Appointment.doctor_id == current_user.id)
            .union(
                db.query(models.Prescription.patient_id)
                .filter(models.Prescription.doctor_id == current_user.id)
            )
            .subquery()
        )
        q = q.filter(models.EHRRecord.patient_id.in_(select(mine)))

    return (
        q.order_by(models.EHRRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/upload", response_model=schemas.ImageUploadResponse)
async def upload_wallet_image(
    body: schemas.ImageUploadRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Uploads an image (e.g. a photographed prescription or lab report) to
    Cloudinary for the Family Health Wallet. Returns a URL the client embeds
    in `payload.image_url` when creating the record via POST /record or
    /sync — keeping the original scan retrievable alongside its OCR text,
    which was previously discarded once /triage/ocr finished reading it."""
    uploaded = cloudinary_client.upload_base64(
        body.image_base64, folder=f"gramcare/health_wallet/{current_user.id}", db=db
    )
    if not uploaded:
        raise HTTPException(status_code=503, detail="Image upload is temporarily unavailable.")
    db.commit()
    return schemas.ImageUploadResponse(url=uploaded["url"], public_id=uploaded["public_id"])


@router.post("/record", response_model=schemas.EHRRecordResponse, status_code=201)
async def create_record(
    request: Request,
    record: schemas.EHRRecordCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Patient-created wallet record — the save step of the OCR camera flow
    ("outside prescription photo -> AI reads it -> confirm -> saved"), and
    manual notes."""
    resolve_owned_profile(record.family_profile_id, current_user, db)

    if record.client_uuid:
        # Scoped to the caller. Without the patient_id predicate this matched
        # another patient's row and silently swallowed this one (Experiment A,
        # finding F-A3).
        existing = (
            db.query(models.EHRRecord)
            .filter(models.EHRRecord.patient_id == current_user.id,
                    models.EHRRecord.client_uuid == record.client_uuid)
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
        record_date=clamp_record_date(record.record_date),
    )
    db.add(db_record)
    try:
        db.commit()
    except IntegrityError:
        # client_uuid is UNIQUE, so two retries of the same queued record
        # racing past the check above collide here. That is the exact case
        # the idempotency key exists for, so return the row that won rather
        # than handing the patient's phone a 500 for a successful sync.
        db.rollback()
        existing = (
            db.query(models.EHRRecord)
            .filter(models.EHRRecord.patient_id == current_user.id,
                    models.EHRRecord.client_uuid == record.client_uuid)
            .first()
        )
        if existing is None:
            raise
        return existing
    db.refresh(db_record)
    
    db.add(models.AuditLog(
        user_id=current_user.id,
        action="CREATE",
        resource="EHRRecord",
        resource_id=str(db_record.id),
        details={"type": record.record_type, "title": record.title},
        ip_address=request.client.host if request.client else None
    ))
    db.commit()
    
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
    rejected: List[schemas.EHRSyncRejection] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for item in batch.records:
        # Two different failures hide behind resolve_owned_profile, and they
        # deserve opposite treatment (Experiment A, finding F-A2):
        #
        #   404 - the profile is GONE. Ordinary: a family member deleted on
        #         another device while this one was offline. The record is
        #         unresolvable forever, so reject that one item and let the
        #         rest of the queue through. Letting this propagate is what
        #         discarded 9 valid records behind 1 stale one and blocked
        #         the queue indefinitely.
        #
        #   403 - the profile belongs to SOMEONE ELSE. A legitimate client
        #         never does this. Refuse the whole request, as before, so
        #         the authorization signal is not downgraded to a 200 and the
        #         response cannot be used to enumerate other households'
        #         profile ids in bulk.
        try:
            resolve_owned_profile(item.family_profile_id, current_user, db)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            rejected.append(schemas.EHRSyncRejection(
                client_uuid=item.client_uuid,
                reason="That family member no longer exists on this account.",
            ))
            continue
        existing = (
            db.query(models.EHRRecord)
            .filter(models.EHRRecord.patient_id == current_user.id,
                    models.EHRRecord.client_uuid == item.client_uuid)
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
                record_date=clamp_record_date(item.record_date, now),
            )
        )
        synced.append(item.client_uuid)

    try:
        db.commit()
    except IntegrityError:
        # client_uuid is UNIQUE, so a record that raced past the check above
        # collides here and takes the whole batch down with it. A patient's
        # offline queue can hold days of records, so re-apply them one at a
        # time and count the collisions as the duplicates they are.
        db.rollback()
        synced, duplicates = [], []
        for item in batch.records:
            if any(r.client_uuid == item.client_uuid for r in rejected):
                continue
            if db.query(models.EHRRecord).filter(
                    models.EHRRecord.patient_id == current_user.id,
                    models.EHRRecord.client_uuid == item.client_uuid).first():
                duplicates.append(item.client_uuid)
                continue
            db.add(models.EHRRecord(
                patient_id=current_user.id,
                family_profile_id=item.family_profile_id,
                record_type=item.record_type,
                title=item.title,
                content=item.content,
                payload=item.payload,
                doctor_name=item.doctor_name,
                client_uuid=item.client_uuid,
                record_date=clamp_record_date(item.record_date, now),
            ))
            try:
                db.commit()
                synced.append(item.client_uuid)
            except IntegrityError:
                db.rollback()
                duplicates.append(item.client_uuid)
    return schemas.EHRSyncResult(synced=synced, duplicates=duplicates,
                                 rejected=rejected)


class VitalsPayload(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=120)
    family_profile_id: Optional[int] = None
    # Each measurement is optional but at least one is required. A Bluetooth
    # heart-rate strap reports only heart rate and a thermometer only
    # temperature; requiring all three forced clients to invent the rest, and
    # the app used to save a fixed 36.8°C with every reading.
    heart_rate: Optional[int] = Field(None, gt=0, lt=300)
    spo2: Optional[int] = Field(None, ge=0, le=100)
    temperature: Optional[float] = Field(None, gt=25.0, lt=45.0)
    steps: Optional[int] = Field(None, ge=0, le=200000)
    sleep_deep_hours: Optional[float] = Field(None, ge=0, le=24)
    sleep_light_hours: Optional[float] = Field(None, ge=0, le=24)

    @model_validator(mode="after")
    def _require_a_measurement(self):
        if all(v is None for v in (
            self.heart_rate, self.spo2, self.temperature,
            self.steps, self.sleep_deep_hours, self.sleep_light_hours,
        )):
            raise ValueError("A vitals reading needs at least one measurement.")
        return self


class VitalsResponse(BaseModel):
    id: int
    family_profile_id: Optional[int] = None
    device_id: str
    heart_rate: Optional[int] = None
    spo2: Optional[int] = None
    temperature: Optional[float] = None
    steps: Optional[int] = None
    sleep_deep_hours: Optional[float] = None
    sleep_light_hours: Optional[float] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


@router.post("/vitals", response_model=VitalsResponse)
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
        steps=payload.steps,
        sleep_deep_hours=payload.sleep_deep_hours,
        sleep_light_hours=payload.sleep_light_hours,
    )
    db.add(db_vital)
    db.commit()
    db.refresh(db_vital)
    return db_vital


@router.get("/vitals/history", response_model=List[VitalsResponse])
async def vitals_history(
    family_profile_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Recent vitals for the Health Vitals Tracker dashboard (graphs/trends),
    scoped to the caller and optionally to one family member."""
    resolve_owned_profile(family_profile_id, current_user, db)
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = db.query(models.IoTVitals).filter(
        models.IoTVitals.patient_id == current_user.id,
        models.IoTVitals.timestamp >= cutoff,
    )
    if family_profile_id is not None:
        q = q.filter(models.IoTVitals.family_profile_id == family_profile_id)
    return q.order_by(models.IoTVitals.timestamp.desc()).limit(200).all()


@router.get("/fhir-export")
async def export_fhir_bundle(
    family_profile_id: Optional[int] = Query(
        None, description="Export this family member's records instead of the caller's own."
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """FHIR-R4-*shaped* export of the caller's (or their family member's)
    Family Health Wallet, for handoff to a receiving hospital/EHR system.

    Scope, plainly: this returns correctly-structured FHIR R4 resources
    (Patient / AllergyIntolerance / MedicationStatement / DiagnosticReport /
    Immunization / Observation) wrapped in a `Bundle` — it is NOT a FHIR
    server, does not do SMART-on-FHIR auth, and does not push/sync to any
    external system. See core/fhir_export.py's module docstring for the
    full honest scope statement. Access control here is GramCare's own JWT
    auth (require_role("PATIENT"), same as every other patient-only route),
    plus the same ownership check every other family-scoped endpoint in
    this router uses (resolve_owned_profile).
    """
    subject: models.User | models.FamilyProfile = current_user
    if family_profile_id is not None:
        # Raises 403/404 if this family_profile_id isn't the caller's own —
        # identical guard used by /prescriptions/my, /vitals, /sync above.
        subject = resolve_owned_profile(family_profile_id, current_user, db)

    q = db.query(models.EHRRecord).filter(models.EHRRecord.patient_id == current_user.id)
    if family_profile_id is not None:
        q = q.filter(models.EHRRecord.family_profile_id == family_profile_id)
    else:
        q = q.filter(models.EHRRecord.family_profile_id.is_(None))
    records = q.order_by(models.EHRRecord.record_date.asc()).all()

    bundle = build_fhir_bundle(subject, records)

    return JSONResponse(
        content=bundle,
        headers={
            "Content-Disposition": 'attachment; filename="gramcare_health_records_fhir.json"',
        },
    )
