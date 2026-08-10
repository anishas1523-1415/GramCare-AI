"""AI Care Navigator — a patient-facing aggregation layer that answers "what
should I do next?" by combining several existing signals into a single
ranked list, each item carrying an explainability `reason` and a suggested
`cta` (label + frontend route).

Signals, in priority order:
1. Active/responded EmergencySOS               -> CRITICAL
2. Lab reports that are ready but not viewed    -> HIGH
3. Confirmed appointments within the next 48h   -> HIGH
4. Unfulfilled prescriptions older than 2 days  -> MEDIUM
5. Preventive-care reminders (best-effort)      -> MEDIUM
6. Nothing applies -> a single friendly "all caught up" LOW item.

This feature is being built in parallel with a separate Preventive AI
reminders endpoint (GET /preventive/reminders) that may not yet be merged
into this branch. `_preventive_items` below is deliberately defensive: it
tries a couple of plausible integration points and swallows ImportError
(module doesn't exist here yet), AttributeError (signature differs), or any
other runtime error (e.g. a table that hasn't been migrated in) so a
partner team's in-flight work can never break this endpoint — that category
is simply omitted rather than the whole request failing.
"""
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import require_role

router = APIRouter()

# Lower number = surfaced first.
_PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# How far ahead a CONFIRMED appointment counts as "upcoming" for this widget.
_APPOINTMENT_WINDOW_HOURS = 48

# How long a prescription must sit unfulfilled before it's nagged about —
# gives the patient a couple of days before we surface it as an action item.
_PRESCRIPTION_STALE_AFTER_DAYS = 2


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sos_items(patient_id: int, db: Session) -> List[schemas.NavigatorItem]:
    rows = (
        db.query(models.EmergencySOS)
        .filter(
            models.EmergencySOS.patient_id == patient_id,
            models.EmergencySOS.status.in_(["ACTIVE", "RESPONDED"]),
        )
        .order_by(models.EmergencySOS.created_at.desc())
        .all()
    )
    return [
        schemas.NavigatorItem(
            category="sos",
            priority="CRITICAL",
            title="Active emergency alert",
            reason="You have an active emergency alert",
            cta_label="View SOS status",
            cta_route="/sos",
        )
        for _ in rows
    ]


def _lab_items(patient_id: int, db: Session) -> List[schemas.NavigatorItem]:
    rows = (
        db.query(models.LabBooking)
        .filter(
            models.LabBooking.patient_id == patient_id,
            models.LabBooking.status == "REPORT_READY",
        )
        .order_by(models.LabBooking.created_at.desc())
        .all()
    )
    return [
        schemas.NavigatorItem(
            category="lab",
            priority="HIGH",
            title="Lab report ready",
            reason=f"Your lab report for {b.test_name} is ready",
            cta_label="View report",
            cta_route="/lab-tests",
        )
        for b in rows
    ]


def _appointment_items(patient_id: int, db: Session) -> List[schemas.NavigatorItem]:
    now = _now()
    window_end = now + timedelta(hours=_APPOINTMENT_WINDOW_HOURS)
    rows = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.patient_id == patient_id,
            models.Appointment.status == "CONFIRMED",
            models.Appointment.scheduled_at >= now,
            models.Appointment.scheduled_at <= window_end,
        )
        .order_by(models.Appointment.scheduled_at.asc())
        .all()
    )
    items = []
    for appt in rows:
        doctor = db.query(models.User).filter(models.User.id == appt.doctor_id).first()
        doctor_name = doctor.full_name if doctor and doctor.full_name else "your doctor"
        when = appt.scheduled_at.strftime("%d %b, %I:%M %p") if appt.scheduled_at else "soon"
        items.append(
            schemas.NavigatorItem(
                category="appointment",
                priority="HIGH",
                title="Upcoming appointment",
                reason=f"Upcoming appointment with Dr. {doctor_name} on {when}",
                cta_label="View details",
                cta_route="/book",
            )
        )
    return items


def _prescription_items(patient_id: int, db: Session) -> List[schemas.NavigatorItem]:
    cutoff = _now() - timedelta(days=_PRESCRIPTION_STALE_AFTER_DAYS)
    rows = (
        db.query(models.Prescription)
        .filter(
            models.Prescription.patient_id == patient_id,
            models.Prescription.is_fulfilled == False,  # noqa: E712
            models.Prescription.created_at <= cutoff,
        )
        .order_by(models.Prescription.created_at.asc())
        .all()
    )
    return [
        schemas.NavigatorItem(
            category="prescription",
            priority="MEDIUM",
            title="Unfulfilled prescription",
            reason="You have an unfulfilled prescription — find a pharmacy",
            cta_label="Find medicine",
            cta_route="/pharmacy",
        )
        for _ in rows
    ]


def _preventive_items(current_user: models.User, db: Session) -> List[schemas.NavigatorItem]:
    """Integration with the Preventive AI reminders feature
    (core/preventive_rules.py, merged after this module was first
    written — see module docstring history). Scoped to the account owner
    only, not family members: a family member's own reminders are already
    visible on /preventive-care via its profile switcher, and this widget
    is inherently about "you, the logged-in patient." Any failure here
    (module missing, ruleset signature changes, an unmigrated column)
    degrades to "no preventive items" rather than a 500 — this endpoint's
    job is to always return something useful even if one signal source
    is unavailable.
    """
    try:
        from core.preventive_rules import compute_reminders
    except ImportError:
        return []

    try:
        records = (
            db.query(models.EHRRecord)
            .filter(
                models.EHRRecord.patient_id == current_user.id,
                models.EHRRecord.family_profile_id.is_(None),
            )
            .all()
        )
        reminders = compute_reminders(
            age=None,
            gender=None,
            chronic_conditions=current_user.chronic_conditions,
            ehr_records=records,
        )
    except Exception:
        return []

    try:
        return [
            schemas.NavigatorItem(
                category="preventive",
                priority="MEDIUM",
                title=r["title"],
                reason=r["reason"],
                cta_label="Book",
                cta_route="/lab-tests" if r["suggested_action"] == "lab_test" else "/preventive-care",
            )
            for r in reminders
            if r["due"]
        ]
    except Exception:
        return []


@router.get("/next-steps", response_model=List[schemas.NavigatorItem])
async def next_steps(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """Aggregated, ranked "what should I do next" for the calling patient.

    Combines active SOS alerts, ready lab reports, upcoming confirmed
    appointments, stale unfulfilled prescriptions, and (when available)
    preventive-care reminders into one CRITICAL-first list. Always returns
    at least one item — a friendly "all caught up" placeholder when nothing
    else applies.
    """
    items: List[schemas.NavigatorItem] = []
    items.extend(_sos_items(current_user.id, db))
    items.extend(_lab_items(current_user.id, db))
    items.extend(_appointment_items(current_user.id, db))
    items.extend(_prescription_items(current_user.id, db))
    items.extend(_preventive_items(current_user, db))

    if not items:
        items.append(
            schemas.NavigatorItem(
                category="all_clear",
                priority="LOW",
                title="All caught up",
                reason="You're all caught up — no urgent actions right now",
                cta_label=None,
                cta_route=None,
            )
        )

    items.sort(key=lambda i: _PRIORITY_ORDER.get(i.priority, 99))
    return items
