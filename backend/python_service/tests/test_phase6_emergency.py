"""Phase 6 tests: SOS lifecycle with voice note + hospital assignment,
emergency contacts CRUD, escalation chain."""
from tests.conftest import auth, _register_and_login


def _make_hospital(client, db, name, lat, lng, username):
    """Hospitals are seeded via ORM (no public create endpoint by design —
    hospital onboarding is an admin/ops action)."""
    import models
    desk = None
    token = _register_and_login(client, username, "HOSPITAL")
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    h = models.Hospital(name=name, lat=lat, lng=lng, emergency_desk_user_id=me["id"])
    db.add(h)
    db.commit()
    db.refresh(h)
    return token, h.id


def test_sos_full_lifecycle_and_contacts(client, patient_token, doctor_token):
    import models
    from database import SessionLocal
    db = SessionLocal()
    try:
        hosp_token, hospital_id = _make_hospital(client, db, "GH Near", 9.85, 78.48, "p6_hosp1")

        # Contacts CRUD
        c = client.post("/api/v1/sos/contacts", headers=auth(patient_token),
                        json={"name": "Sita", "phone": "+919000000009", "relation": "Mother"})
        assert c.status_code == 201, c.text
        contacts = client.get("/api/v1/sos/contacts", headers=auth(patient_token)).json()
        assert any(x["name"] == "Sita" for x in contacts)

        # Trigger with GPS + voice note -> auto-assigned to nearest hospital
        res = client.post("/api/v1/sos/trigger", headers=auth(patient_token), json={
            "location_lat": 9.85, "location_lng": 78.48,
            "location_text": "Near the temple",
            "voice_note": "My father collapsed suddenly",
            "severity": "CRITICAL",
        })
        assert res.status_code == 200, res.text
        sos = res.json()
        assert sos["assigned_hospital_id"] == hospital_id
        assert sos["voice_note"] == "My father collapsed suddenly"

        # Patient sees own status ("Help En Route" tracking)
        mine = client.get("/api/v1/sos/mine", headers=auth(patient_token)).json()
        assert any(s["id"] == sos["id"] for s in mine)

        # Hospital desk can view + respond
        active = client.get("/api/v1/sos/active", headers=auth(hosp_token))
        assert active.status_code == 200
        responded = client.put(f"/api/v1/sos/{sos['id']}/respond", headers=auth(hosp_token))
        assert responded.status_code == 200
        assert responded.json()["status"] == "RESPONDED"

        # Second respond attempt is blocked (double-dispatch prevention)
        again = client.put(f"/api/v1/sos/{sos['id']}/respond", headers=auth(doctor_token))
        assert again.status_code == 400

        # Contact cleanup
        cid = contacts[0]["id"]
        assert client.delete(f"/api/v1/sos/contacts/{cid}",
                             headers=auth(patient_token)).status_code == 204
    finally:
        db.close()


def test_sos_escalates_to_next_hospital(client, patient_token):
    import models
    from database import SessionLocal
    from datetime import datetime, timedelta, timezone
    from modules.emergency.router import escalate_stale_sos

    db = SessionLocal()
    try:
        _, near_id = _make_hospital(client, db, "GH A", 10.00, 78.00, "p6_hosp2")
        _, far_id = _make_hospital(client, db, "GH B", 10.20, 78.20, "p6_hosp3")

        res = client.post("/api/v1/sos/trigger", headers=auth(patient_token), json={
            "location_lat": 10.00, "location_lng": 78.00, "severity": "CRITICAL",
        })
        sos_id = res.json()["id"]
        first_hospital = res.json()["assigned_hospital_id"]

        # Age the alert past the escalation window, then run the watchdog
        from sqlalchemy import update
        original_created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
        db.execute(
            update(models.EmergencySOS)
            .where(models.EmergencySOS.id == sos_id)
            .values(created_at=original_created_at)
        )
        db.commit()

        escalated = escalate_stale_sos(db)
        assert escalated >= 1

        sos = db.get(models.EmergencySOS, sos_id)
        assert sos.escalation_level >= 1
        assert sos.assigned_hospital_id != first_hospital
        # Audit-trail guarantee: created_at must NOT be overwritten by
        # escalation; the escalation clock lives on last_escalated_at.
        assert sos.created_at == original_created_at
        assert sos.last_escalated_at is not None
        assert sos.last_escalated_at > original_created_at
    finally:
        db.close()


def test_enriched_triage_fields_present(client):
    res = client.post("/api/v1/triage/analyze", json={
        "symptoms_text": "skin rash and itching for a week",
        "patient_id": "GUEST", "age": 25,
    })
    assert res.status_code == 200
    body = res.json()
    for field in ("possible_causes", "first_aid", "side_effects",
                  "treatment_options", "untreated_outcome",
                  "specialist_type", "language_detected"):
        assert field in body


def test_assist_summary_requires_doctor(client, patient_token, doctor_token):
    me = client.get("/api/v1/auth/me", headers=auth(patient_token)).json()
    # Patients cannot read assist summaries
    assert client.get(f"/api/v1/assist/patient-summary/{me['id']}",
                      headers=auth(patient_token)).status_code == 403
    # Doctors can
    res = client.get(f"/api/v1/assist/patient-summary/{me['id']}",
                     headers=auth(doctor_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["patient_id"] == me["id"]
    assert body["generated_by"] in ["rules", "gemini", "openai", "groq", "anthropic"]  # CI may have real keys
    assert "summary_text" in body


def test_health_clusters_role_gate_and_shape(client, patient_token, doctor_token):
    # Generate a few triage logs for clustering
    for _ in range(3):
        client.post("/api/v1/triage/analyze", headers=auth(patient_token), json={
            "symptoms_text": "fever and body pain", "patient_id": "self", "age": 30,
        })

    assert client.get("/api/v1/analytics/health-clusters",
                      headers=auth(patient_token)).status_code == 403

    res = client.get("/api/v1/analytics/health-clusters?days=7&min_cases=3",
                     headers=auth(doctor_token))
    assert res.status_code == 200, res.text
    clusters = res.json()
    assert len(clusters) >= 1
    assert {"condition", "case_count", "avg_severity", "alert"} <= set(clusters[0].keys())

    overview = client.get("/api/v1/analytics/overview", headers=auth(doctor_token))
    assert overview.status_code == 200
    assert overview.json()["total_assessments"] >= 3
