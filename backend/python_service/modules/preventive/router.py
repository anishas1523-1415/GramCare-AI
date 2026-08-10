"""Preventive AI — rule-based screening & vaccination reminders.

Patient-facing only (see require_role("PATIENT") below): for the caller
themself, or one family member they own, this computes "you're due for X"
reminders on the fly from that person's age/gender/chronic conditions
(core/preventive_rules.py's curated ruleset) plus their existing EHRRecord
history — no ML, no cached table (see that module's docstring for why).

Scope note — User has no age/gender column (only FamilyProfile does; see
models.py): when `family_profile_id` is omitted (reminders for the account
owner), age/gender-gated rules never apply and are simply absent from the
result; chronic-condition-only rules (e.g. an existing diabetes diagnosis)
still fire off User.chronic_conditions.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import require_role
from modules.family.router import resolve_owned_profile
from core.preventive_rules import compute_reminders

router = APIRouter()


@router.get("/reminders", response_model=List[schemas.PreventiveReminder])
async def get_reminders(
    family_profile_id: Optional[int] = Query(None),
    include_upcoming: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """Preventive-care reminders for the caller, or an owned family member.

    By default only returns reminders that are actually due; pass
    `include_upcoming=true` to also see applicable-but-not-yet-due ones.
    """
    # resolve_owned_profile raises 403/404 if family_profile_id is set but
    # not owned by the caller — same guard every other profile-scoped
    # feature (lab bookings, EHR records, vitals) already uses.
    profile = resolve_owned_profile(family_profile_id, current_user, db)

    if profile is not None:
        age = profile.age
        gender = profile.gender
        chronic_conditions = profile.chronic_conditions
    else:
        # Account owner: User has no age/gender field at all (only
        # FamilyProfile does), so age/gender-gated rules won't apply — see
        # the module docstring above.
        age = None
        gender = None
        chronic_conditions = current_user.chronic_conditions

    records_query = db.query(models.EHRRecord).filter(
        models.EHRRecord.patient_id == current_user.id
    )
    if profile is not None:
        records_query = records_query.filter(models.EHRRecord.family_profile_id == profile.id)
    else:
        # Strictly the account owner's own records — a family member's lab
        # report must never count toward the owner's own screening history.
        records_query = records_query.filter(models.EHRRecord.family_profile_id.is_(None))
    records = records_query.all()

    reminders = compute_reminders(
        age=age,
        gender=gender,
        chronic_conditions=chronic_conditions,
        ehr_records=records,
    )

    if not include_upcoming:
        reminders = [r for r in reminders if r["due"]]

    return reminders
