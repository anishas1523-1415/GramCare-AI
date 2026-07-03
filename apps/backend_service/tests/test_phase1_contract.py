"""Phase 1 contract tests: auth validation, role gates, family profiles,
doctor directory, EHR sync idempotency, triage persistence."""
from tests.conftest import auth, _register_and_login


# ---------------------------------------------------------------- auth ----

def test_root(client):
    assert client.get("/").status_code == 200


def test_register_rejects_weak_password(client):
    res = client.post("/api/v1/auth/register", json={
        "username": "weakpw", "email": "weak@x.in",
        "password": "short", "full_name": "W", "role": "PATIENT",
    })
    assert res.status_code == 422


def test_register_rejects_unknown_role(client):
    res = client.post("/api/v1/auth/register", json={
        "username": "badrole", "email": "badrole@x.in",
        "password": "strongpass123", "full_name": "B", "role": "SUPERADMIN",
    })
    assert res.status_code == 422


def test_me_includes_id(client, patient_token):
    res = client.get("/api/v1/auth/me", headers=auth(patient_token))
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["id"], int)
    assert body["role"] == "PATIENT"


def test_login_rate_limit(client):
    for _ in range(15):
        client.post("/api/v1/auth/login", data={"username": "nobody", "password": "x"})
    res = client.post("/api/v1/auth/login", data={"username": "nobody", "password": "x"})
    assert res.status_code == 429


# ------------------------------------------------------- family profiles ----

def test_family_crud_and_ownership(client, patient_token, doctor_token):
    created = client.post("/api/v1/family", headers=auth(patient_token), json={
        "full_name": "Sita Devi", "relation": "Mother", "age": 55, "gender": "Female",
    })
    assert created.status_code == 201, created.text
    pid = created.json()["id"]

    listed = client.get("/api/v1/family", headers=auth(patient_token))
    assert any(p["id"] == pid for p in listed.json())

    # Another user cannot touch this profile
    other = client.put(f"/api/v1/family/{pid}", headers=auth(doctor_token),
                       json={"age": 60})
    assert other.status_code == 403

    updated = client.put(f"/api/v1/family/{pid}", headers=auth(patient_token),
                         json={"age": 56})
    assert updated.json()["age"] == 56

    assert client.delete(f"/api/v1/family/{pid}",
                         headers=auth(patient_token)).status_code == 204


def test_family_requires_auth(client):
    assert client.get("/api/v1/family").status_code == 401


# ------------------------------------------------------ doctor directory ----

def test_doctor_directory_lists_doctors_with_defaults(client, patient_token, doctor_token):
    res = client.get("/api/v1/doctors", headers=auth(patient_token))
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) >= 1
    d = next(d for d in docs if d["full_name"] == "T_Doctor")
    assert d["specialty"] == "General Medicine"
    assert d["consultation_fee"] == 150.0


def test_doctor_updates_own_profile(client, doctor_token):
    res = client.put("/api/v1/doctors/me", headers=auth(doctor_token), json={
        "specialty": "Cardiology", "experience_years": 9, "consultation_fee": 300,
    })
    assert res.status_code == 200
    assert res.json()["specialty"] == "Cardiology"


def test_patient_cannot_update_doctor_profile(client, patient_token):
    res = client.put("/api/v1/doctors/me", headers=auth(patient_token),
                     json={"specialty": "Hacker"})
    assert res.status_code == 403


# ------------------------------------------------------------- EHR sync ----

def test_ehr_sync_is_idempotent(client, patient_token):
    batch = {"records": [{
        "client_uuid": "test-uuid-0001-aaaa",
        "record_type": "note",
        "title": "Offline note",
        "content": "Created while offline",
    }]}
    first = client.post("/api/v1/ehr/sync", headers=auth(patient_token), json=batch)
    assert first.status_code == 200, first.text
    assert first.json()["synced"] == ["test-uuid-0001-aaaa"]

    second = client.post("/api/v1/ehr/sync", headers=auth(patient_token), json=batch)
    assert second.json()["duplicates"] == ["test-uuid-0001-aaaa"]
    assert second.json()["synced"] == []


def test_patient_records_are_private(client, patient_token):
    me = client.get("/api/v1/auth/me", headers=auth(patient_token)).json()
    stranger = _register_and_login(client, "t_stranger", "PATIENT")
    res = client.get(f"/api/v1/ehr/patient/{me['id']}", headers=auth(stranger))
    assert res.status_code == 403


def test_doctor_records_feed_requires_doctor(client, patient_token, doctor_token):
    assert client.get("/api/v1/ehr/records", headers=auth(patient_token)).status_code == 403
    assert client.get("/api/v1/ehr/records", headers=auth(doctor_token)).status_code == 200


# ------------------------------------------------------ triage persistence ----

def test_triage_mock_persists_log(client, patient_token):
    res = client.post("/api/v1/triage/analyze",
                      headers=auth(patient_token),
                      json={"symptoms_text": "fever and headache",
                            "patient_id": "self", "age": 30})
    assert res.status_code == 200, res.text
    body = res.json()
    assert 0 <= body["severity_score"] <= 100
    assert "disclaimer" in body

    # The analysis must have been written to TriageLog
    import models
    from database import SessionLocal
    db = SessionLocal()
    try:
        me = client.get("/api/v1/auth/me", headers=auth(patient_token)).json()
        logs = db.query(models.TriageLog).filter(
            models.TriageLog.patient_id == me["id"]).all()
        assert len(logs) >= 1
        assert logs[-1].symptoms_text == "fever and headache"
    finally:
        db.close()


def test_triage_allows_guests(client):
    res = client.post("/api/v1/triage/analyze",
                      json={"symptoms_text": "cough for two days",
                            "patient_id": "GUEST", "age": 25})
    assert res.status_code == 200


def test_vitals_requires_auth_and_bounds(client, patient_token):
    assert client.post("/api/v1/ehr/vitals", json={
        "device_id": "d1", "heart_rate": 80, "spo2": 98, "temperature": 36.6,
    }).status_code == 401

    bad = client.post("/api/v1/ehr/vitals", headers=auth(patient_token), json={
        "device_id": "d1", "heart_rate": -5, "spo2": 98, "temperature": 36.6,
    })
    assert bad.status_code == 422

    ok = client.post("/api/v1/ehr/vitals", headers=auth(patient_token), json={
        "device_id": "d1", "heart_rate": 80, "spo2": 98, "temperature": 36.6,
    })
    assert ok.status_code == 200
