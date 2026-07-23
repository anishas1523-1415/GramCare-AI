"""Clinical Decision Support (CDS) — POST /cds/check. Covers the three new
heuristic checks (allergy cross-check, duplicate-therapy, dosage-sanity)
layered on top of the existing drug-interaction check, and the explainable-AI
contract that every alert (whatever check produced it) carries a non-empty
`explanation` field.
"""
from datetime import datetime, timedelta

from tests.conftest import auth, _register_and_login


def _new_patient(client, username):
    token = _register_and_login(client, username, "PATIENT")
    patient_id = client.get("/api/v1/auth/me", headers=auth(token)).json()["id"]
    return token, patient_id


def test_only_doctors_can_run_cds_check(client, patient_token):
    _, patient_id = _new_patient(client, "cds_role_patient")
    res = client.post(
        "/api/v1/cds/check",
        headers=auth(patient_token),
        json={"patient_id": patient_id, "medicines": [{"name": "Paracetamol", "dosage": "500mg"}]},
    )
    assert res.status_code == 403


def test_allergy_cross_check_fires(client, doctor_token):
    patient_token, patient_id = _new_patient(client, "cds_allergy_patient")

    # Record the allergy via the Digital Health Passport, which stores it on
    # User.allergies — the same free-text field the allergy heuristic reads.
    updated = client.put(
        "/api/v1/passport/me",
        headers=auth(patient_token),
        json={"allergies": "Penicillin, Peanuts"},
    )
    assert updated.status_code == 200, updated.text

    res = client.post(
        "/api/v1/cds/check",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Penicillin V 250mg", "dosage": "250mg"}],
        },
    )
    assert res.status_code == 200, res.text
    alerts = res.json()["alerts"]
    allergy_alerts = [a for a in alerts if a["category"] == "ALLERGY"]
    assert len(allergy_alerts) == 1
    assert allergy_alerts[0]["severity"] == "CRITICAL"
    assert "penicillin" in allergy_alerts[0]["explanation"].lower()


def test_duplicate_therapy_fires_against_active_prescription(client, doctor_token):
    _, patient_id = _new_patient(client, "cds_duplicate_patient")

    # Issue a prescription with a long enough course that it's still active.
    rx = client.post(
        "/api/v1/ehr/issue_prescription",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Amlodipine 5mg", "dosage": "5mg", "frequency": "1-0-0", "duration": "30 days"}],
            "diagnosis": "Hypertension",
        },
    )
    assert rx.status_code == 200, rx.text

    res = client.post(
        "/api/v1/cds/check",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Amlodipine 5mg", "dosage": "5mg"}],
        },
    )
    assert res.status_code == 200, res.text
    alerts = res.json()["alerts"]
    dup_alerts = [a for a in alerts if a["category"] == "DUPLICATE_THERAPY"]
    assert len(dup_alerts) == 1
    assert "amlodipine" in dup_alerts[0]["message"].lower()
    assert dup_alerts[0]["explanation"]


def test_dosage_change_flag_fires_on_prior_different_dosage(client, doctor_token, db):
    import models

    _, patient_id = _new_patient(client, "cds_dosage_patient")

    rx = client.post(
        "/api/v1/ehr/issue_prescription",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Metformin", "dosage": "500mg", "frequency": "1-0-1", "duration": "5 days"}],
            "diagnosis": "Diabetes follow-up",
        },
    )
    assert rx.status_code == 200, rx.text

    # Backdate the prescription well past its 5-day course so the
    # duplicate-therapy check (which only looks at ACTIVE prescriptions)
    # stays out of the way here — this test isolates the dosage-sanity
    # heuristic, which deliberately looks at *all* history regardless of
    # whether the course already ended.
    db_rx = db.query(models.Prescription).filter(models.Prescription.id == rx.json()["id"]).first()
    db_rx.created_at = datetime.utcnow() - timedelta(days=30)
    db.commit()

    res = client.post(
        "/api/v1/cds/check",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Metformin", "dosage": "1000mg"}],
        },
    )
    assert res.status_code == 200, res.text
    alerts = res.json()["alerts"]
    dosage_alerts = [a for a in alerts if a["category"] == "DOSAGE_CHANGE"]
    assert len(dosage_alerts) == 1
    assert "500mg" in dosage_alerts[0]["message"] and "1000mg" in dosage_alerts[0]["message"]
    assert dosage_alerts[0]["explanation"]
    # The now-expired course is correctly NOT flagged as an active duplicate.
    assert not any(a["category"] == "DUPLICATE_THERAPY" for a in alerts)


def test_no_alert_case_for_clean_prescription(client, doctor_token):
    _, patient_id = _new_patient(client, "cds_clean_patient")

    res = client.post(
        "/api/v1/cds/check",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Vitamin C 500mg", "dosage": "500mg"}],
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["alerts"] == []


def test_every_alert_includes_an_explanation(client, doctor_token):
    patient_token, patient_id = _new_patient(client, "cds_explain_patient")
    client.put(
        "/api/v1/passport/me",
        headers=auth(patient_token),
        json={"allergies": "Aspirin"},
    )
    rx = client.post(
        "/api/v1/ehr/issue_prescription",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Warfarin", "dosage": "5mg", "frequency": "1-0-0", "duration": "30 days"}],
            "diagnosis": "Atrial fibrillation",
        },
    )
    assert rx.status_code == 200, rx.text

    # This second check combines: an interaction (Warfarin + Aspirin),
    # an allergy conflict (Aspirin), and a duplicate-therapy hit is avoided
    # since Warfarin isn't repeated here — the point is simply that whatever
    # mix of checks fires, every alert in the list carries `explanation`.
    res = client.post(
        "/api/v1/cds/check",
        headers=auth(doctor_token),
        json={
            "patient_id": patient_id,
            "medicines": [{"name": "Aspirin", "dosage": "75mg"}],
        },
    )
    assert res.status_code == 200, res.text
    alerts = res.json()["alerts"]
    assert len(alerts) >= 2  # at least the INTERACTION and ALLERGY alerts
    categories = {a["category"] for a in alerts}
    assert "INTERACTION" in categories
    assert "ALLERGY" in categories
    for alert in alerts:
        assert isinstance(alert["explanation"], str)
        assert len(alert["explanation"]) > 0
        assert alert["severity"] in ("INFO", "WARNING", "CRITICAL")
