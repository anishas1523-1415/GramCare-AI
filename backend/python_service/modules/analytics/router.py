"""Community Health Intelligence + operational analytics.

Planning doc: "ஒரே பகுதியில் உள்ள பலர் ஒரே மாதிரியான சிம்டம்ஸை குறிப்பிட்ட
நாட்களில் பதிவு செஞ்சாங்கன்னா, அதை ஒரு கிளஸ்டராகவும், நோய் பரவல்
அபாயமாகவும் AI கண்டுபிடிச்சிடும்" — clusters of similar AI-assessed
conditions inside a time window, surfaced to health authorities.

All data is aggregated and anonymized: no patient identifiers leave this
endpoint ("இந்த டேட்டா எல்லாமே அனனிமைஸ் செய்யப்பட்டு").
"""
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from database import get_db
from modules.auth.router import get_current_user

router = APIRouter()

AUTHORIZED_ROLES = ("ADMIN", "HOSPITAL", "DOCTOR")


class HealthCluster(BaseModel):
    condition: str
    location: str
    case_count: int
    avg_severity: float
    max_severity: int
    first_seen: datetime
    last_seen: datetime
    alert: bool  # True when the cluster crosses the outbreak threshold

class ResourceForecast(BaseModel):
    resource_type: str # 'ambulance' | 'medicines'
    recommended_location: str
    urgency: str # 'HIGH' | 'MEDIUM' | 'LOW'
    reason: str


class OverviewStats(BaseModel):
    window_days: int
    total_assessments: int
    critical_assessments: int
    active_sos: int
    unfulfilled_prescriptions: int
    registered_pharmacies: int


def _authorize(user: models.User, db: Session):
    if user.role not in AUTHORIZED_ROLES:
        raise HTTPException(status_code=403, detail="Health-authority roles only")
    if user.role == "DOCTOR":
        profile = (
            db.query(models.DoctorProfile)
            .filter(models.DoctorProfile.user_id == user.id)
            .first()
        )
        if not profile or profile.verification_status != "APPROVED":
            raise HTTPException(
                status_code=403,
                detail="Your doctor account is pending government verification and cannot perform this action yet.",
            )


# Syndromic grouping for outbreak detection.
#
# Grouping on the model's exact wording never detects anything: the same
# outbreak comes back as "possible viral fever (e.g. dengue or malaria)",
# "acute febrile illness" and "fever with rash" on three consecutive
# patients, so six real cases presented as six clusters of one. Public
# health surveillance (IDSP) does not group by diagnosis either — it groups
# by syndrome, then investigates. The buckets below follow that, and the
# raw condition is kept as an example so a clinician can still see what the
# assessments actually said.
_SYNDROMES: list[tuple[str, tuple[str, ...]]] = [
    ("Acute febrile illness", ("fever", "febrile", "dengue", "malaria",
                               "typhoid", "chikungunya", "viral fever")),
    ("Acute diarrhoeal illness", ("diarrhoea", "diarrhea", "loose stool",
                                  "gastroenteritis", "cholera", "dysentery",
                                  "vomiting and loose")),
    ("Acute respiratory illness", ("cough", "respiratory", "breathless",
                                   "asthma", "pneumonia", "bronchitis",
                                   "sore throat", "covid", "influenza")),
    ("Skin and rash presentations", ("rash", "skin", "measles", "chickenpox",
                                     "dermatitis", "scabies")),
    ("Jaundice / hepatic", ("jaundice", "hepatitis", "liver")),
    ("Neurological", ("seizure", "convulsion", "encephalitis", "meningitis",
                      "stroke", "paralysis")),
    ("Cardiac / chest pain", ("chest pain", "cardiac", "heart attack",
                              "myocardial", "angina")),
    ("Maternal and child health", ("pregnan", "antenatal", "postnatal",
                                   "neonat", "obstetric")),
]


def _syndrome_of(condition: str) -> str:
    """Map a free-text AI condition to a surveillance syndrome."""
    text = (condition or "").lower()
    for label, keywords in _SYNDROMES:
        if any(k in text for k in keywords):
            return label
    return "Other presentations"


@router.get("/health-clusters", response_model=List[HealthCluster])
async def health_clusters(
    days: int = Query(7, ge=1, le=90),
    min_cases: int = Query(3, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Anonymized clusters of similar AI-assessed conditions within the
    window. `alert=True` marks clusters at/above the outbreak threshold."""
    _authorize(current_user, db)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    # location_text was declared on the TriageLog model from the start but
    # the migration to actually add the column was never written — every
    # call here threw psycopg2.errors.UndefinedColumn, a 500 on every
    # single request, masked by the frontend's generic "Not authorized"
    # catch-all. Fixed for real via alembic/versions/
    # d3f8a91c5e02_add_triage_log_location_text.py rather than dropping the
    # location dimension this endpoint was always meant to have.
    rows = (
        db.query(
            func.lower(models.TriageLog.ai_predicted_condition).label("cond"),
            func.coalesce(models.TriageLog.location_text, "Unknown").label("loc"),
            func.count(models.TriageLog.id).label("n"),
            func.avg(models.TriageLog.ai_severity_score).label("avg_sev"),
            func.max(models.TriageLog.ai_severity_score).label("max_sev"),
            func.min(models.TriageLog.created_at).label("first_seen"),
            func.max(models.TriageLog.created_at).label("last_seen"),
        )
        .filter(
            models.TriageLog.created_at >= cutoff,
            models.TriageLog.ai_predicted_condition != None,  # noqa: E711
            models.TriageLog.ai_predicted_condition != "",
            ~models.is_placeholder_triage(),
        )
        .group_by(
            func.lower(models.TriageLog.ai_predicted_condition),
            func.coalesce(models.TriageLog.location_text, "Unknown"),
        )
        .order_by(func.count(models.TriageLog.id).desc())
        .limit(500)
        .all()
    )

    # Re-aggregate the per-wording rows into syndrome buckets per locality.
    buckets: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (_syndrome_of(r.cond), r.loc)
        b = buckets.setdefault(key, {
            "n": 0, "sev_sum": 0.0, "max_sev": 0,
            "first": r.first_seen, "last": r.last_seen, "examples": [],
        })
        b["n"] += r.n
        b["sev_sum"] += float(r.avg_sev or 0) * r.n
        b["max_sev"] = max(b["max_sev"], int(r.max_sev or 0))
        if r.first_seen and (b["first"] is None or r.first_seen < b["first"]):
            b["first"] = r.first_seen
        if r.last_seen and (b["last"] is None or r.last_seen > b["last"]):
            b["last"] = r.last_seen
        if len(b["examples"]) < 3:
            b["examples"].append(r.cond)

    out = [
        HealthCluster(
            condition=syndrome,
            location=loc,
            case_count=b["n"],
            avg_severity=round(b["sev_sum"] / b["n"], 1) if b["n"] else 0.0,
            max_severity=b["max_sev"],
            first_seen=b["first"],
            last_seen=b["last"],
            alert=b["n"] >= min_cases,
        )
        for (syndrome, loc), b in buckets.items()
    ]
    out.sort(key=lambda c: c.case_count, reverse=True)
    return out


@router.get("/overview", response_model=OverviewStats)
async def overview(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Operational snapshot for dashboards/reports."""
    _authorize(current_user, db)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    total = (
        db.query(models.TriageLog)
        .filter(models.TriageLog.created_at >= cutoff, ~models.is_placeholder_triage())
        .count()
    )
    critical = (
        db.query(models.TriageLog)
        .filter(models.TriageLog.created_at >= cutoff,
                models.TriageLog.ai_severity_score >= 75)
        .count()
    )
    active_sos = db.query(models.EmergencySOS).filter(models.EmergencySOS.status == "ACTIVE").count()
    pending_rx = db.query(models.Prescription).filter(models.Prescription.is_fulfilled == False).count()  # noqa: E712
    pharmacies = db.query(models.Pharmacy).filter(models.Pharmacy.is_active == True).count()  # noqa: E712

    return OverviewStats(
        window_days=days,
        total_assessments=total,
        critical_assessments=critical,
        active_sos=active_sos,
        unfulfilled_prescriptions=pending_rx,
        registered_pharmacies=pharmacies,
    )

@router.get("/resource-forecasting", response_model=List[ResourceForecast])
async def resource_forecasting(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Predictive analytics for resource allocation."""
    _authorize(current_user, db)
    forecasts = []
    
    # 1. Ambulance Dispatch Forecast (Based on recent active SOS density)
    sos_rows = (
        db.query(
            func.coalesce(models.EmergencySOS.location_text, "Unknown Region").label("loc"),
            func.count(models.EmergencySOS.id).label("n")
        )
        .filter(models.EmergencySOS.status == "ACTIVE")
        .group_by(func.coalesce(models.EmergencySOS.location_text, "Unknown Region"))
        .order_by(func.count(models.EmergencySOS.id).desc())
        .limit(5)
        .all()
    )
    
    for r in sos_rows:
        if r.n >= 2:
            forecasts.append(ResourceForecast(
                resource_type="ambulance",
                recommended_location=r.loc,
                urgency="HIGH" if r.n >= 5 else "MEDIUM",
                reason=f"{r.n} active SOS signals detected in {r.loc}."
            ))
            
    # 2. Medicine Restocking Forecast (Based on recurring high-severity triage logs)
    #
    # location_text is real now — see alembic/versions/
    # d3f8a91c5e02_add_triage_log_location_text.py and the note in
    # health_clusters() above for the full story.
    triage_rows = (
        db.query(
            func.lower(models.TriageLog.ai_predicted_condition).label("cond"),
            func.coalesce(models.TriageLog.location_text, "Unknown Region").label("loc"),
            func.count(models.TriageLog.id).label("n")
        )
        .filter(models.TriageLog.ai_severity_score >= 60, ~models.is_placeholder_triage())
        .group_by(
            func.lower(models.TriageLog.ai_predicted_condition),
            func.coalesce(models.TriageLog.location_text, "Unknown Region"),
        )
        .order_by(func.count(models.TriageLog.id).desc())
        .limit(5)
        .all()
    )

    for r in triage_rows:
        if r.n >= 5:
            forecasts.append(ResourceForecast(
                resource_type="medicines",
                recommended_location=r.loc,
                urgency="HIGH" if r.n >= 15 else "MEDIUM",
                reason=f"Spike in {r.cond} ({r.n} severe cases). Restock relevant generic medicines."
            ))

    return forecasts

