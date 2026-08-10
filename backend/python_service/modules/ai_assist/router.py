"""AI Doctor Assistant — pre-consultation patient summary.

Planning doc: "டாக்டர்ஸ் பேஷன்ட்ட பாக்குறதுக்கு முன்னாடியே, அவங்களோட
டிஜிட்டல் ரெக்கார்ட்ஸ், AI சிம்டம் செக்கர் டேட்டா, அப்புறம் அவங்க
சாப்பிட்டுட்டு இருக்கிற மருந்துகள் — எல்லாத்தையும் அனலைஸ் பண்ணி ஒரு சம்மரி
ரிப்போர்ட்டை தயார் செஞ்சுடும்."

Data ordering follows the discussed rules: records sorted by timestamp
(newest first), and "active medicines" are detected from prescription start
dates + parsed durations rather than guessed.

The summary text is deterministic (rule-based) by default and upgraded by
Gemini when an API key is configured — the endpoint always works offline/
keyless, and the structured data accompanies the prose either way.
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from ai import AITask, get_ai_manager
from database import get_db
from modules.auth.router import require_approved_doctor

# Previously imported `gemini_client` directly from modules.ai_triage.router
# — a second, informal AI entry point that bypassed any central provider
# selection, health checking, or fallback policy, and required this module
# to know Gemini's SDK response shape (`res.text`) itself. Now goes through
# AIManager like every other AI-backed feature.
ai_manager = get_ai_manager()

router = APIRouter()
logger = logging.getLogger("gramcare.ai_assist")


class ActiveMedicine(BaseModel):
    name: str
    dosage: str
    frequency: str
    started: str
    days_remaining: int


class PatientSummary(BaseModel):
    patient_id: int
    patient_name: str
    age_hint: Optional[int] = None
    risk_flag: str  # LOW / MODERATE / HIGH
    summary_text: str
    active_medicines: List[ActiveMedicine]
    recent_conditions: List[str]
    latest_vitals: Optional[dict] = None
    chronic_conditions: Optional[str] = None
    allergies: Optional[str] = None
    generated_by: str  # 'rules' | 'gemini'


_DURATION_RE = re.compile(r"(\d+)\s*(day|week|month)", re.IGNORECASE)


def _parse_duration_days(duration: str) -> int:
    m = _DURATION_RE.search(duration or "")
    if not m:
        return 5  # sensible default course length
    n = int(m.group(1))
    unit = m.group(2).lower()
    return n * {"day": 1, "week": 7, "month": 30}[unit]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/patient-summary/{patient_id}", response_model=PatientSummary)
async def patient_summary(
    patient_id: int,
    family_profile_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    patient = (
        db.query(models.User)
        .filter(models.User.id == patient_id, models.User.role == "PATIENT")
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    profile = None
    if family_profile_id is not None:
        profile = (
            db.query(models.FamilyProfile)
            .filter(
                models.FamilyProfile.id == family_profile_id,
                models.FamilyProfile.user_id == patient_id,
            )
            .first()
        )

    # --- Active medicines from prescriptions (start date + duration) ------
    prescriptions = (
        db.query(models.Prescription)
        .filter(models.Prescription.patient_id == patient_id)
        .order_by(models.Prescription.created_at.desc())
        .limit(20)
        .all()
    )
    active: List[ActiveMedicine] = []
    for rx in prescriptions:
        for med in (rx.medicines or []):
            days = _parse_duration_days(med.get("duration", ""))
            end = rx.created_at + timedelta(days=days)
            remaining = (end - _now()).days
            if remaining >= 0:
                active.append(ActiveMedicine(
                    name=med.get("name", "?"),
                    dosage=med.get("dosage", ""),
                    frequency=med.get("frequency", ""),
                    started=rx.created_at.date().isoformat(),
                    days_remaining=remaining,
                ))

    # --- Recent triage history (timestamp-ordered) -------------------------
    triage_q = db.query(models.TriageLog).filter(models.TriageLog.patient_id == patient_id)
    if family_profile_id is not None:
        triage_q = triage_q.filter(models.TriageLog.family_profile_id == family_profile_id)
    triages = triage_q.order_by(models.TriageLog.created_at.desc()).limit(5).all()
    recent_conditions = [t.ai_predicted_condition for t in triages if t.ai_predicted_condition]
    max_severity = max((t.ai_severity_score or 0 for t in triages), default=0)

    # --- Latest vitals ------------------------------------------------------
    vitals = (
        db.query(models.IoTVitals)
        .filter(models.IoTVitals.patient_id == patient_id)
        .order_by(models.IoTVitals.timestamp.desc())
        .first()
    )
    latest_vitals = None
    if vitals:
        latest_vitals = {
            "heart_rate": vitals.heart_rate,
            "spo2": vitals.spo2,
            "temperature": vitals.temperature,
            "at": vitals.timestamp.isoformat(),
        }

    risk_flag = "HIGH" if max_severity >= 75 else "MODERATE" if max_severity >= 50 else "LOW"

    # --- Deterministic summary ----------------------------------------------
    name = profile.full_name if profile else (patient.full_name or patient.username)
    parts = [f"{name}"]
    if profile:
        parts.append(f"{profile.age} yrs, {profile.gender}")
        if profile.chronic_conditions:
            parts.append(f"chronic: {profile.chronic_conditions}")
        if profile.allergies:
            parts.append(f"allergies: {profile.allergies}")
    if recent_conditions:
        parts.append(f"recent AI assessments: {', '.join(recent_conditions[:3])} (max severity {max_severity}/100)")
    if active:
        parts.append(f"currently on: {', '.join(m.name for m in active[:5])}")
    if latest_vitals:
        parts.append(f"latest vitals HR {latest_vitals['heart_rate']}, SpO2 {latest_vitals['spo2']}%")
    summary_text = " | ".join(parts)
    generated_by = "rules"

    # --- Optional AI narrative upgrade --------------------------------------
    # Deterministic `summary_text` above is always returned even if every AI
    # provider (including Mock) somehow fails validation — this upgrade is
    # best-effort and never blocks the response, matching the module's
    # documented "always works offline/keyless" guarantee.
    try:
        prompt = (
            "You are assisting a rural telemedicine doctor. Summarize this "
            "patient context in 3 concise clinical sentences (no advice, "
            "no diagnosis, English). Respond in JSON as "
            '{"summary_text": "..."}: \n' + summary_text
        )
        outcome = await ai_manager.run(AITask.DOCTOR_SUMMARY, prompt=prompt)
        upgraded = (outcome.data or {}).get("summary_text")
        if upgraded and not outcome.used_mock:
            summary_text = str(upgraded).strip()
            generated_by = outcome.provider_used
    except Exception as e:  # graceful degradation
        logger.warning("AI summary upgrade failed, using rules summary: %s", e)

    return PatientSummary(
        patient_id=patient_id,
        patient_name=name,
        age_hint=profile.age if profile else None,
        risk_flag=risk_flag,
        summary_text=summary_text,
        active_medicines=active,
        recent_conditions=recent_conditions,
        latest_vitals=latest_vitals,
        chronic_conditions=profile.chronic_conditions if profile else None,
        allergies=profile.allergies if profile else None,
        generated_by=generated_by,
    )

class ParsePrescriptionRequest(BaseModel):
    dictation_text: str

class ParsedMedicine(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str

class ParsePrescriptionResponse(BaseModel):
    diagnosis: str
    notes: str
    medicines: List[ParsedMedicine]

PARSE_PROMPT = """
You are a medical AI parsing a doctor's dictated prescription.
Extract the diagnosis, clinical notes, and a list of medicines.

Respond only in JSON format matching this structure exactly (do not wrap in markdown):
{
  "diagnosis": "<Extracted primary diagnosis, or empty if none>",
  "notes": "<Any other clinical observations or instructions>",
  "medicines": [
    {
      "name": "<Medicine name>",
      "dosage": "<e.g. 500mg, 10ml>",
      "frequency": "<e.g. 1-0-1, 1-1-1, SOS, etc>",
      "duration": "<e.g. 5 days, 1 week>"
    }
  ]
}

Dictation to parse:
"{dictation_text}"
"""

@router.post("/parse-prescription", response_model=ParsePrescriptionResponse)
async def parse_prescription(
    body: ParsePrescriptionRequest,
    current_user: models.User = Depends(require_approved_doctor()),
):
    """Parses raw Voice-to-Text dictation into structured prescription data."""
    if not body.dictation_text or len(body.dictation_text.strip()) < 5:
        return ParsePrescriptionResponse(diagnosis="", notes="", medicines=[])
        
    prompt = PARSE_PROMPT.format(dictation_text=body.dictation_text)
    
    try:
        outcome = await ai_manager.run(AITask.PARSE_PRESCRIPTION, prompt=prompt)
        data = dict(outcome.data)
        
        return ParsePrescriptionResponse(
            diagnosis=data.get("diagnosis", ""),
            notes=data.get("notes", ""),
            medicines=[
                ParsedMedicine(
                    name=m.get("name", ""),
                    dosage=m.get("dosage", ""),
                    frequency=m.get("frequency", ""),
                    duration=m.get("duration", "")
                )
                for m in data.get("medicines", [])
            ]
        )
    except Exception as e:
        logger.error("Failed to parse dictation: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to parse dictation.")
