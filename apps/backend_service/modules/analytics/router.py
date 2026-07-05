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
    case_count: int
    avg_severity: float
    max_severity: int
    first_seen: datetime
    last_seen: datetime
    alert: bool  # True when the cluster crosses the outbreak threshold


class OverviewStats(BaseModel):
    window_days: int
    total_assessments: int
    critical_assessments: int
    active_sos: int
    unfulfilled_prescriptions: int
    registered_pharmacies: int


def _authorize(user: models.User):
    if user.role not in AUTHORIZED_ROLES:
        raise HTTPException(status_code=403, detail="Health-authority roles only")


@router.get("/health-clusters", response_model=List[HealthCluster])
async def health_clusters(
    days: int = Query(7, ge=1, le=90),
    min_cases: int = Query(3, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Anonymized clusters of similar AI-assessed conditions within the
    window. `alert=True` marks clusters at/above the outbreak threshold."""
    _authorize(current_user)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    rows = (
        db.query(
            func.lower(models.TriageLog.ai_predicted_condition).label("cond"),
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
        )
        .group_by(func.lower(models.TriageLog.ai_predicted_condition))
        .order_by(func.count(models.TriageLog.id).desc())
        .limit(50)
        .all()
    )

    return [
        HealthCluster(
            condition=r.cond,
            case_count=r.n,
            avg_severity=round(float(r.avg_sev or 0), 1),
            max_severity=int(r.max_sev or 0),
            first_seen=r.first_seen,
            last_seen=r.last_seen,
            alert=r.n >= min_cases,
        )
        for r in rows
    ]


@router.get("/overview", response_model=OverviewStats)
async def overview(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Operational snapshot for dashboards/reports."""
    _authorize(current_user)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    total = db.query(models.TriageLog).filter(models.TriageLog.created_at >= cutoff).count()
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
