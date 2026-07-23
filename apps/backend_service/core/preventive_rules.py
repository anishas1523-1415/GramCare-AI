"""Preventive AI — rule-based screening & vaccination reminders.

IMPORTANT: this is a deterministic RULESET, not a trained machine-learning
model. Every entry below is a plain Python predicate over age/gender/chronic
conditions plus a keyword match against the patient's existing EHRRecord
history — there is no inference step, no model weights, nothing learned from
data. "AI" in the feature name refers to the product area (automated
clinical decision support), not the implementation technique.

Design mirrors core/lab_tests.py: a small curated, real, commonly-used
catalog (standard adult screening intervals; the Indian Universal
Immunization Programme's core childhood schedule) rather than an exhaustive
clinical registry, kept in one reviewable file.

Nothing here is cached. `compute_reminders()` is called fresh on every
request against the patient/family member's current age, gender and chronic
conditions plus their live EHRRecord history — a precomputed table would go
stale the instant a new lab report, consultation note or vaccination record
is added, which is worse than the cost of recomputing a handful of predicates
per request.

--- Known data-precision limitation (child vaccination checkpoints) -------
FamilyProfile.age is a whole number of *years*, not a date of birth. Real
vaccination guidelines key checkpoints off weeks/months (e.g. "6-14 weeks",
"9-12 months"), which this data model cannot resolve. Rather than pretend to
a precision the data doesn't have, every child-vaccination rule below is
gated only on the coarse "age < 5" band from the planning spec, and (because
there's no way to tell "this 2-year-old is missing their birth dose" from
"this 2-year-old already had it recorded under a different title") all
applicable checkpoints are surfaced together whenever no matching
EHRRecord is found — over-reminding on paperwork is the safer failure mode
than silently dropping a real, missed dose.

--- Known data-precision limitation (User vs FamilyProfile) ---------------
`User` (the account owner) has no `age`/`gender` columns at all — only
`FamilyProfile` rows carry them (see models.py). So when reminders are
computed for the account owner (family_profile_id=None), every age/gender
gated rule below simply never `applies()` (age/gender come through as None),
while the chronic-condition-only paths (e.g. an existing diabetes diagnosis)
still fire off `User.chronic_conditions`. This is a deliberate, documented
scope decision (see modules/preventive/router.py) rather than a bug.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, TypedDict


class ReminderDict(TypedDict):
    key: str
    title: str
    category: str  # "screening" | "vaccination"
    reason: str
    due: bool
    last_done_date: Optional[str]  # ISO date string, or None if never recorded
    suggested_action: str  # "lab_test" -> /lab-tests | "consultation" -> /book


@dataclass(frozen=True)
class Subject:
    """The person reminders are being computed for — either the account
    owner (age/gender always None, per the limitation above) or a
    FamilyProfile (age/gender always present)."""
    age: Optional[int]
    gender: Optional[str]
    conditions_text: str  # chronic_conditions, lowercased; "" if none recorded


@dataclass(frozen=True)
class PreventiveRule:
    key: str
    title: str
    category: str  # "screening" | "vaccination"
    applies: Callable[[Subject], bool]
    reason: Callable[[Subject], str]
    # None = one-time (vaccination-style): due until ever recorded, then
    # never due again. Otherwise: due once more than this many days have
    # passed since the most recent matching record.
    interval_days: Callable[[Subject], Optional[int]]
    keywords: Sequence[str]  # matched case-insensitively against title/content
    # Restrict the EHRRecord search to these record_type values; None = search
    # every record_type (used for things like blood pressure that could be
    # logged as a consultation note, a lab report, or a plain note).
    record_types: Optional[Sequence[str]] = None
    suggested_action: str = "consultation"


def _has_any(text: str, *keywords: str) -> bool:
    return any(k in text for k in keywords)


def _is_female(subject: Subject) -> bool:
    return (subject.gender or "").strip().lower() in ("female", "f")


def _age_at_least(subject: Subject, minimum: int) -> bool:
    return subject.age is not None and subject.age >= minimum


# ==========================================================
# Adult screening rules
# ==========================================================

RULES: List[PreventiveRule] = [
    PreventiveRule(
        key="blood_pressure_check",
        title="Blood Pressure Check",
        category="screening",
        applies=lambda s: _age_at_least(s, 40),
        reason=lambda s: "Recommended annually for adults 40+ to catch hypertension early.",
        interval_days=lambda s: 365,
        keywords=["blood pressure", "bp check", "hypertension"],
        suggested_action="consultation",
    ),
    PreventiveRule(
        key="diabetes_screening",
        title="Diabetes Screening (HbA1c)",
        category="screening",
        applies=lambda s: _has_any(s.conditions_text, "diabetes") or _age_at_least(s, 45),
        reason=lambda s: (
            "Recommended every 3 months to monitor your existing diabetes."
            if _has_any(s.conditions_text, "diabetes")
            else "Recommended annually for adults 45+ to screen for diabetes early."
        ),
        interval_days=lambda s: 90 if _has_any(s.conditions_text, "diabetes") else 365,
        keywords=["hba1c", "diabetes screening", "fasting blood sugar", "blood sugar", "fbs"],
        suggested_action="lab_test",
    ),
    PreventiveRule(
        key="lipid_profile",
        title="Lipid Profile",
        category="screening",
        applies=lambda s: _age_at_least(s, 20),
        reason=lambda s: (
            "Recommended annually because your health record mentions a heart/cholesterol-related condition."
            if _has_any(s.conditions_text, "heart", "cardiac", "cholesterol")
            else "Recommended every 5 years for adults 20+ to screen for cardiovascular risk."
        ),
        interval_days=lambda s: 365 if _has_any(s.conditions_text, "heart", "cardiac", "cholesterol") else 1825,
        keywords=["lipid profile", "cholesterol"],
        suggested_action="lab_test",
    ),
    PreventiveRule(
        key="cervical_screening",
        title="Cervical Screening (Pap Smear)",
        category="screening",
        applies=lambda s: _is_female(s) and s.age is not None and 25 <= s.age <= 65,
        reason=lambda s: "Recommended every 3 years for women aged 25-65 to screen for cervical cancer.",
        interval_days=lambda s: 1095,
        keywords=["pap smear", "cervical screening", "pap test"],
        suggested_action="consultation",
    ),
    PreventiveRule(
        key="breast_screening",
        title="Breast Screening",
        category="screening",
        applies=lambda s: _is_female(s) and _age_at_least(s, 40),
        reason=lambda s: "Recommended annually for women 40+ to screen for breast cancer.",
        interval_days=lambda s: 365,
        keywords=["breast screening", "mammogram", "breast exam", "clinical breast exam"],
        suggested_action="consultation",
    ),
    PreventiveRule(
        key="eye_exam",
        title="Eye Exam",
        category="screening",
        applies=lambda s: _age_at_least(s, 40),
        reason=lambda s: "Recommended every 2 years for adults 40+ to catch vision changes and eye conditions early.",
        interval_days=lambda s: 730,
        keywords=["eye exam", "vision test", "eye check", "ophthalmology"],
        suggested_action="consultation",
    ),

    # ==========================================================
    # Child vaccination schedule (age < 5) — see the module docstring's
    # "known data-precision limitation" note above for why these are gated
    # only on the coarse age band, not exact weeks/months.
    # ==========================================================
    PreventiveRule(
        key="child_bcg",
        title="BCG Vaccination (Tuberculosis)",
        category="vaccination",
        applies=lambda s: s.age is not None and s.age < 5,
        reason=lambda s: "Given at birth to protect against tuberculosis — recommended before the child turns 1, if not already given.",
        interval_days=lambda s: None,
        keywords=["bcg"],
        record_types=["vaccination"],
        suggested_action="consultation",
    ),
    PreventiveRule(
        key="child_primary_series",
        title="OPV / Pentavalent Primary Series (Polio, DPT, Hepatitis B, Hib)",
        category="vaccination",
        applies=lambda s: s.age is not None and s.age < 5,
        reason=lambda s: "Given as 3 doses starting at 6-14 weeks of age to protect against polio, diphtheria, pertussis, tetanus, hepatitis B and Hib.",
        interval_days=lambda s: None,
        keywords=["pentavalent", "opv", "polio", "hepatitis b"],
        record_types=["vaccination"],
        suggested_action="consultation",
    ),
    PreventiveRule(
        key="child_measles_mmr1",
        title="Measles / MMR — 1st Dose",
        category="vaccination",
        applies=lambda s: s.age is not None and s.age < 5,
        reason=lambda s: "Recommended at 9-12 months of age to protect against measles, mumps and rubella.",
        interval_days=lambda s: None,
        keywords=["measles", "mmr"],
        record_types=["vaccination"],
        suggested_action="consultation",
    ),
    PreventiveRule(
        key="child_booster1",
        title="DPT/OPV Booster & MMR — 2nd Dose",
        category="vaccination",
        applies=lambda s: s.age is not None and s.age < 5,
        reason=lambda s: "Recommended at 16-24 months as a booster dose to maintain immunity.",
        interval_days=lambda s: None,
        keywords=["booster"],
        record_types=["vaccination"],
        suggested_action="consultation",
    ),
    PreventiveRule(
        key="child_dpt_booster2",
        title="DPT Booster (2nd, around 5 years)",
        category="vaccination",
        applies=lambda s: s.age is not None and s.age < 5,
        reason=lambda s: "Recommended around 5 years of age as the second DPT booster.",
        interval_days=lambda s: None,
        keywords=["dpt booster 2", "second booster", "5-year booster", "five year booster", "booster 2", "booster-2"],
        record_types=["vaccination"],
        suggested_action="consultation",
    ),
]


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _most_recent_match(rule: PreventiveRule, ehr_records: Sequence[Any]) -> Optional[Any]:
    """Most recent EHRRecord matching this rule's keywords (and, if set,
    record_type restriction), or None if the patient/family member has no
    such record yet."""
    matches = []
    for record in ehr_records:
        if rule.record_types is not None and getattr(record, "record_type", None) not in rule.record_types:
            continue
        title = getattr(record, "title", None) or ""
        content = getattr(record, "content", None) or ""
        haystack = f"{title} {content}".lower()
        if any(kw in haystack for kw in rule.keywords):
            matches.append(record)
    if not matches:
        return None
    return max(matches, key=lambda r: _as_date(getattr(r, "record_date", None)) or date.min)


def compute_reminders(
    *,
    age: Optional[int],
    gender: Optional[str],
    chronic_conditions: Optional[str],
    ehr_records: Sequence[Any],
) -> List[ReminderDict]:
    """Evaluate every applicable rule for one patient/family member.

    Returns ALL applicable rules (both due and not-yet-due) — callers
    (modules/preventive/router.py) filter down to due=True by default, with
    an `include_upcoming` opt-in to see the rest. Rules that don't apply to
    this subject at all (wrong age/gender/no matching condition) are simply
    omitted, not returned with due=False.
    """
    subject = Subject(age=age, gender=gender, conditions_text=(chronic_conditions or "").lower())

    reminders: List[ReminderDict] = []
    for rule in RULES:
        if not rule.applies(subject):
            continue

        last_record = _most_recent_match(rule, ehr_records)
        last_done_date = _as_date(getattr(last_record, "record_date", None)) if last_record else None
        interval = rule.interval_days(subject)

        if interval is None:
            due = last_record is None
        elif last_done_date is None:
            due = True
        else:
            due = (date.today() - last_done_date).days > interval

        reminders.append(
            ReminderDict(
                key=rule.key,
                title=rule.title,
                category=rule.category,
                reason=rule.reason(subject),
                due=due,
                last_done_date=last_done_date.isoformat() if last_done_date else None,
                suggested_action=rule.suggested_action,
            )
        )

    return reminders
