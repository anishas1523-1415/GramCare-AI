"""Clinical Decision Support (CDS) — planning doc: doctors get a single
combined safety check, POST /cds/check, run at prescription-writing time.

Contract summary (all under /api/v1/cds):
- POST /check (DOCTOR)  { patient_id, family_profile_id?, medicines: [{name, dosage}] }
                         -> { alerts: [{category, severity, message, explanation}] }

This combines the existing drug-drug interaction check
(core/drug_interactions.check_interactions) with three new heuristic checks
in core/clinical_decision_support.py (allergy cross-check, duplicate-therapy,
dosage-sanity). Every alert — interaction or CDS — comes back in the same
shape and always carries `explanation`: the plain-language "why", so the
doctor sees the reasoning behind each flag rather than a bare label. This is
the same explainability contract /triage/analyze already ships
(`explanation` + `confidence_score` on TriageResponse).

Severity note: the interaction table's own severities (HIGH/MODERATE — see
core/drug_interactions.py) are left untouched at their source so existing
callers (POST /pharmacy/interactions/check, POST /ehr/issue_prescription)
keep the exact response shape they've always returned. Here, where alerts
from four different checks share one list, interaction severities are
mapped onto the same INFO/WARNING/CRITICAL scale the new checks use
(HIGH -> CRITICAL, MODERATE -> WARNING) purely for a consistent
severity vocabulary in this combined endpoint.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db
from modules.auth.router import require_approved_doctor
from modules.ai_assist.router import _parse_duration_days
from core.drug_interactions import check_interactions
from core.clinical_decision_support import (
    CdsAlert,
    check_allergy_conflicts,
    check_dosage_changes,
    check_duplicate_therapy,
)

router = APIRouter()

_INTERACTION_SEVERITY_MAP = {"HIGH": "CRITICAL", "MODERATE": "WARNING"}


class CdsMedicineInput(BaseModel):
    name: str
    dosage: str = ""


class CdsCheckRequest(BaseModel):
    patient_id: int
    family_profile_id: Optional[int] = None
    medicines: List[CdsMedicineInput]


class CdsAlertResponse(BaseModel):
    category: str
    severity: str
    message: str
    explanation: str


class CdsCheckResponse(BaseModel):
    alerts: List[CdsAlertResponse]


def _interaction_alerts_as_cds(medicine_names: List[str]) -> List[CdsAlert]:
    """Normalizes core.drug_interactions.check_interactions()'s
    {drug_a, drug_b, severity, description, explanation} shape into this
    endpoint's shared {category, severity, message, explanation} alert
    shape — see the module docstring's severity-mapping note."""
    alerts: List[CdsAlert] = []
    for w in check_interactions(medicine_names):
        alerts.append({
            "category": "INTERACTION",
            "severity": _INTERACTION_SEVERITY_MAP.get(w["severity"], w["severity"]),
            "message": f"{w['drug_a']} + {w['drug_b']}: {w['description']}",
            "explanation": w["explanation"],
        })
    return alerts


@router.post("/check", response_model=CdsCheckResponse)
async def run_cds_check(
    body: CdsCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor()),
):
    """Runs the drug-interaction check plus the three new CDS heuristics
    against a patient's stored allergies, active prescriptions, and
    prescription history, and returns one combined, explained alert list."""
    patient = (
        db.query(models.User)
        .filter(models.User.id == body.patient_id, models.User.role == "PATIENT")
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    allergies_text = patient.allergies
    if body.family_profile_id is not None:
        profile = (
            db.query(models.FamilyProfile)
            .filter(
                models.FamilyProfile.id == body.family_profile_id,
                models.FamilyProfile.user_id == patient.id,
            )
            .first()
        )
        if not profile:
            raise HTTPException(status_code=404, detail="Family profile not found for this patient")
        allergies_text = profile.allergies

    new_names = [m.name for m in body.medicines if m.name and m.name.strip()]

    # Same "active medicines" detection as POST /ehr/issue_prescription
    # (modules/ehr_sync/router.py) and the AI Doctor Assistant's
    # patient-summary (modules/ai_assist/router.py:_parse_duration_days) —
    # a medicine counts as active if start date + parsed course duration
    # hasn't elapsed yet. Also doubles as this patient's prescription
    # history for the dosage-sanity check below.
    now = datetime.utcnow()
    prior_rx = (
        db.query(models.Prescription)
        .filter(models.Prescription.patient_id == body.patient_id)
        .order_by(models.Prescription.created_at.desc())
        .limit(50)
        .all()
    )
    active_names: List[str] = []
    history_items: List[dict] = []
    for rx in prior_rx:
        for med in (rx.medicines or []):
            history_items.append(med)
            days = _parse_duration_days(med.get("duration", ""))
            if (rx.created_at + timedelta(days=days)) >= now:
                active_names.append(med.get("name", ""))

    alerts: List[CdsAlert] = []
    alerts.extend(_interaction_alerts_as_cds(new_names + active_names))
    alerts.extend(check_allergy_conflicts(allergies_text, new_names))
    alerts.extend(check_duplicate_therapy(new_names, active_names))
    alerts.extend(check_dosage_changes(
        [m.model_dump() for m in body.medicines],
        history_items,
    ))

    return CdsCheckResponse(alerts=alerts)
