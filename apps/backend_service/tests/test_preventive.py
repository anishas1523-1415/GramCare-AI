"""Preventive AI — rule-based screening/vaccination reminders.

Covers: age-gated rules, gender-gated rules, chronic-condition-gated rules,
"not due" once a matching EHRRecord exists, and family-profile ownership
scoping (including the User-has-no-age/gender scope decision documented in
core/preventive_rules.py and modules/preventive/router.py).
"""
from datetime import datetime, timedelta

from tests.conftest import auth, _register_and_login


def _create_family_profile(client, token, **overrides):
    body = {
        "full_name": "Test Member",
        "relation": "Self",
        "age": 45,
        "gender": "Female",
    }
    body.update(overrides)
    res = client.post("/api/v1/family", headers=auth(token), json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_ehr_record(client, token, *, record_type, title, content, family_profile_id=None, record_date=None):
    body = {
        "record_type": record_type,
        "title": title,
        "content": content,
        "family_profile_id": family_profile_id,
    }
    if record_date is not None:
        body["record_date"] = record_date
    res = client.post("/api/v1/ehr/record", headers=auth(token), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _reminders(client, token, family_profile_id=None, include_upcoming=False):
    params = {"include_upcoming": str(include_upcoming).lower()}
    if family_profile_id is not None:
        params["family_profile_id"] = family_profile_id
    res = client.get("/api/v1/preventive/reminders", headers=auth(token), params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _by_key(reminders, key):
    return next((r for r in reminders if r["key"] == key), None)


def test_age_based_rule_fires_for_family_member_over_40(client):
    token = _register_and_login(client, "prev_age", "PATIENT")
    profile_id = _create_family_profile(client, token, age=52, gender="Male")

    reminders = _reminders(client, token, family_profile_id=profile_id)
    bp = _by_key(reminders, "blood_pressure_check")
    assert bp is not None, reminders
    assert bp["due"] is True
    assert bp["last_done_date"] is None
    assert "40" in bp["reason"]


def test_age_based_rule_absent_for_young_family_member(client):
    token = _register_and_login(client, "prev_young", "PATIENT")
    profile_id = _create_family_profile(client, token, age=22, gender="Male")

    reminders = _reminders(client, token, family_profile_id=profile_id, include_upcoming=True)
    # Under 40, under 45, under 20-... blood pressure/diabetes/eye rules
    # shouldn't apply at all (not merely due=False — absent entirely).
    assert _by_key(reminders, "blood_pressure_check") is None
    assert _by_key(reminders, "diabetes_screening") is None
    assert _by_key(reminders, "eye_exam") is None
    # Lipid profile DOES apply from age 20 onward.
    assert _by_key(reminders, "lipid_profile") is not None


def test_gender_restricted_rules_respect_gender(client):
    token = _register_and_login(client, "prev_gender", "PATIENT")
    male_id = _create_family_profile(client, token, full_name="Male Member", age=50, gender="Male")
    female_id = _create_family_profile(client, token, full_name="Female Member", age=50, gender="Female")

    male_reminders = _reminders(client, token, family_profile_id=male_id, include_upcoming=True)
    female_reminders = _reminders(client, token, family_profile_id=female_id, include_upcoming=True)

    assert _by_key(male_reminders, "breast_screening") is None
    assert _by_key(male_reminders, "cervical_screening") is None

    assert _by_key(female_reminders, "breast_screening") is not None
    assert _by_key(female_reminders, "cervical_screening") is not None
    assert _by_key(female_reminders, "breast_screening")["due"] is True


def test_chronic_condition_based_rule_fires_regardless_of_age(client):
    token = _register_and_login(client, "prev_condition", "PATIENT")
    # Age 30 is below the age>=45 diabetes-screening threshold, so this rule
    # should only apply because of the diabetes condition, on the 3-month
    # (not annual) interval.
    profile_id = _create_family_profile(
        client, token, age=30, gender="Male", chronic_conditions="Type 2 Diabetes, on Metformin",
    )

    reminders = _reminders(client, token, family_profile_id=profile_id)
    diabetes = _by_key(reminders, "diabetes_screening")
    assert diabetes is not None
    assert diabetes["due"] is True
    assert "3 months" in diabetes["reason"]


def test_rule_not_due_when_recent_matching_record_exists(client):
    token = _register_and_login(client, "prev_recent", "PATIENT")
    profile_id = _create_family_profile(client, token, age=50, gender="Male")

    recent_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
    _add_ehr_record(
        client, token,
        record_type="lab_report",
        title="Lipid Profile",
        content="Lipid Profile — all values within normal range.",
        family_profile_id=profile_id,
        record_date=recent_date,
    )

    reminders = _reminders(client, token, family_profile_id=profile_id, include_upcoming=True)
    lipid = _by_key(reminders, "lipid_profile")
    assert lipid is not None
    assert lipid["due"] is False
    assert lipid["last_done_date"] is not None

    # Blood pressure was never recorded for this profile, so it's still due.
    bp = _by_key(reminders, "blood_pressure_check")
    assert bp["due"] is True


def test_family_profile_scoping_rejects_non_owned_profile(client):
    owner_token = _register_and_login(client, "prev_owner", "PATIENT")
    other_token = _register_and_login(client, "prev_intruder", "PATIENT")
    profile_id = _create_family_profile(client, owner_token, age=45, gender="Female")

    # The actual owner can read it fine.
    ok = client.get(
        "/api/v1/preventive/reminders",
        headers=auth(owner_token),
        params={"family_profile_id": profile_id},
    )
    assert ok.status_code == 200, ok.text

    # A different patient must not be able to read someone else's family
    # member's reminders.
    forbidden = client.get(
        "/api/v1/preventive/reminders",
        headers=auth(other_token),
        params={"family_profile_id": profile_id},
    )
    assert forbidden.status_code == 403, forbidden.text

    missing = client.get(
        "/api/v1/preventive/reminders",
        headers=auth(owner_token),
        params={"family_profile_id": 999999},
    )
    assert missing.status_code == 404, missing.text


def test_self_scope_uses_user_chronic_conditions_not_age(client):
    """User has no age/gender column (only FamilyProfile does — see
    core/preventive_rules.py), so for the account owner (no
    family_profile_id) age/gender-gated rules must never appear, while a
    chronic-condition-only rule can still fire off User.chronic_conditions."""
    token = _register_and_login(client, "prev_self", "PATIENT")

    # No age/gender exists on User at all, so nothing age-gated should ever
    # show up for the bare account owner.
    reminders = _reminders(client, token, include_upcoming=True)
    assert _by_key(reminders, "blood_pressure_check") is None
    assert _by_key(reminders, "eye_exam") is None
    assert _by_key(reminders, "lipid_profile") is None

    # Record a diabetes diagnosis against the account owner via the Health
    # Passport (User.chronic_conditions) — the condition-only path should
    # now fire even though there's no age at all.
    update = client.put(
        "/api/v1/passport/me",
        headers=auth(token),
        json={"chronic_conditions": "Type 1 Diabetes"},
    )
    assert update.status_code == 200, update.text

    reminders_after = _reminders(client, token, include_upcoming=True)
    diabetes = _by_key(reminders_after, "diabetes_screening")
    assert diabetes is not None
    assert diabetes["due"] is True


def test_child_vaccination_checkpoints_apply_under_age_5(client):
    token = _register_and_login(client, "prev_child", "PATIENT")
    child_id = _create_family_profile(client, token, full_name="Baby", age=1, gender="Female")

    reminders = _reminders(client, token, family_profile_id=child_id, include_upcoming=True)
    bcg = _by_key(reminders, "child_bcg")
    assert bcg is not None
    assert bcg["category"] == "vaccination"
    assert bcg["due"] is True

    # Record the BCG dose; it should drop off the due list (one-time rule).
    _add_ehr_record(
        client, token,
        record_type="vaccination",
        title="BCG",
        content="BCG vaccination administered.",
        family_profile_id=child_id,
    )
    reminders_after = _reminders(client, token, family_profile_id=child_id, include_upcoming=True)
    bcg_after = _by_key(reminders_after, "child_bcg")
    assert bcg_after["due"] is False
    assert bcg_after["last_done_date"] is not None

    # Adult-only rules must never apply to a 1-year-old.
    assert _by_key(reminders_after, "blood_pressure_check") is None
