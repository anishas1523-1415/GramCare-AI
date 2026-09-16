"""Community Health Intelligence + operational analytics.

This module had no coverage at all, despite being the one that returned a
500 on every single request for months: TriageLog.location_text existed on
the model but no migration ever added the column, and the dashboard's
generic error handling reported it as "Not authorized". A test that
actually selects over that column is what would have caught it, so these
tests exercise the real queries rather than only the auth gates.
"""
from datetime import datetime, timedelta

import models
from tests.conftest import auth, _register_and_login


def _seed_triage(db, *, condition, location, severity, days_ago=1, patient_id=None):
    row = models.TriageLog(
        patient_id=patient_id,
        symptoms_text="seeded for analytics tests",
        ai_severity_score=severity,
        ai_predicted_condition=condition,
        location_text=location,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(row)
    db.commit()
    return row


def test_health_clusters_rejects_a_patient(client):
    token = _register_and_login(client, "an_patient_1", "PATIENT")
    r = client.get("/api/v1/analytics/health-clusters", headers=auth(token))
    assert r.status_code == 403


def test_analytics_requires_authentication(client):
    assert client.get("/api/v1/analytics/overview").status_code == 401


def test_health_clusters_groups_by_condition_and_location(client, db):
    token = _register_and_login(client, "an_doctor_1", "DOCTOR")
    for _ in range(3):
        _seed_triage(db, condition="Dengue", location="Thiruvallur", severity=80)
    _seed_triage(db, condition="Dengue", location="Erode", severity=40)

    r = client.get(
        "/api/v1/analytics/health-clusters?days=30&min_cases=3", headers=auth(token)
    )
    assert r.status_code == 200, r.text

    by_location = {c["location"]: c for c in r.json()}
    cluster = by_location["Thiruvallur"]
    assert cluster["condition"] == "dengue"  # grouped case-insensitively
    assert cluster["case_count"] == 3
    assert cluster["alert"] is True

    # Same condition, different place, below the threshold — a separate row
    # that must not be folded in or flagged.
    assert by_location["Erode"]["case_count"] == 1
    assert by_location["Erode"]["alert"] is False


def test_health_clusters_excludes_readings_outside_the_window(client, db):
    token = _register_and_login(client, "an_doctor_2", "DOCTOR")
    _seed_triage(db, condition="Cholera", location="Salem", severity=90, days_ago=40)

    recent = client.get("/api/v1/analytics/health-clusters?days=7", headers=auth(token))
    assert "cholera" not in [c["condition"] for c in recent.json()]

    wide = client.get("/api/v1/analytics/health-clusters?days=90", headers=auth(token))
    assert "cholera" in [c["condition"] for c in wide.json()]


def test_health_clusters_skips_logs_the_ai_could_not_classify(client, db):
    token = _register_and_login(client, "an_doctor_3", "DOCTOR")
    _seed_triage(db, condition=None, location="Karur", severity=10)
    _seed_triage(db, condition="", location="Karur", severity=10)

    r = client.get("/api/v1/analytics/health-clusters?days=30", headers=auth(token))
    assert r.status_code == 200
    assert "Karur" not in [c["location"] for c in r.json()]


def test_overview_counts_only_the_requested_window(client, db):
    token = _register_and_login(client, "an_doctor_4", "DOCTOR")
    _seed_triage(db, condition="Fever", location="Ooty", severity=80, days_ago=2)
    _seed_triage(db, condition="Fever", location="Ooty", severity=20, days_ago=2)
    _seed_triage(db, condition="Fever", location="Ooty", severity=95, days_ago=60)

    r = client.get("/api/v1/analytics/overview?days=7", headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_days"] == 7
    assert body["total_assessments"] >= 2
    # Severity >= 75 counts as critical; the 60-day-old one is out of window.
    assert body["critical_assessments"] >= 1


def test_overview_rejects_an_out_of_range_window(client):
    token = _register_and_login(client, "an_doctor_5", "DOCTOR")
    assert client.get("/api/v1/analytics/overview?days=0", headers=auth(token)).status_code == 422
    assert client.get("/api/v1/analytics/overview?days=91", headers=auth(token)).status_code == 422


def test_resource_forecasting_returns_a_list(client, db):
    token = _register_and_login(client, "an_doctor_6", "DOCTOR")
    r = client.get("/api/v1/analytics/resource-forecasting", headers=auth(token))
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_clusters_carry_no_patient_identifiers(client, db):
    """The module's whole premise is anonymised aggregates."""
    patient_token = _register_and_login(client, "an_patient_2", "PATIENT")
    me = client.get("/api/v1/auth/me", headers=auth(patient_token)).json()
    _seed_triage(
        db, condition="Malaria", location="Vellore", severity=70, patient_id=me["id"]
    )

    token = _register_and_login(client, "an_doctor_7", "DOCTOR")
    r = client.get("/api/v1/analytics/health-clusters?days=30", headers=auth(token))
    assert r.status_code == 200
    serialised = r.text
    assert "patient_id" not in serialised
    assert str(me["id"]) not in [c.get("condition") for c in r.json()]
