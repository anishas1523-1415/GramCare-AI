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


def test_sos_voice_recording_attaches_and_is_served(client, patient_token):
    """The patient's actual recording, not just the transcript.

    A responder listens for distress, breathlessness or a third party
    speaking — none of which survive speech-to-text. The recording is
    uploaded after the alert fires, because the microphone is busy during
    the press and an SOS must not wait on it.
    """
    import base64

    res = client.post("/api/v1/sos/trigger", headers=auth(patient_token), json={
        "location_lat": 11.05, "location_lng": 77.08,
        "location_text": "Test village", "severity": "CRITICAL",
    })
    assert res.status_code == 200, res.text
    sos = res.json()
    assert sos["voice_audio_url"] is None

    # A minimal well-formed WAV header — enough for the mime sniffing the
    # uploader does, without embedding a real clip in the test suite.
    wav = base64.b64encode(
        b"RIFF$\x00\x00\x00WAVEfmt " + b"\x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    ).decode()

    attached = client.post(
        f"/api/v1/sos/{sos['id']}/voice",
        headers=auth(patient_token),
        json={"voice_audio_base64": f"data:audio/wav;base64,{wav}"},
    )
    assert attached.status_code == 200, attached.text
    url = attached.json()["voice_audio_url"]
    assert url, "the recording must come back addressable"

    # It must actually be retrievable, as audio — a URL that 404s would let
    # a responder tap play and hear nothing.
    token = url.rsplit("/", 1)[-1]
    served = client.get(f"/api/v1/files/{token}")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("audio/")


def test_sos_voice_recording_rejects_another_patients_alert(client, patient_token):
    """One patient must never be able to put words in another's emergency."""
    res = client.post("/api/v1/sos/trigger", headers=auth(patient_token), json={
        "location_lat": 11.05, "location_lng": 77.08, "severity": "CRITICAL",
    })
    sos_id = res.json()["id"]

    intruder = _register_and_login(client, "p6_voice_intruder", "PATIENT")
    denied = client.post(
        f"/api/v1/sos/{sos_id}/voice",
        headers=auth(intruder),
        json={"voice_audio_base64": "data:audio/wav;base64,UklGRg=="},
    )
    assert denied.status_code == 404, denied.text


def test_sos_public_tracking_link_shows_family_what_they_need(client, patient_token, db_session=None):
    """The link an emergency contact receives by SMS.

    Contacts are phone numbers, not accounts, so this has to work with no
    auth at all — and must still carry distance and ETA, which is the first
    thing a relative asks.
    """
    from database import SessionLocal
    import models

    with SessionLocal() as db:
        hosp_token, hospital_id = _make_hospital(client, db, "GH Track", 11.10, 77.10, "p6_hosp_track")

    res = client.post("/api/v1/sos/trigger", headers=auth(patient_token), json={
        "location_lat": 11.05, "location_lng": 77.08,
        "location_text": "Track village", "severity": "CRITICAL",
        "voice_note": "chest pain",
    })
    assert res.status_code == 200, res.text
    sos_id = res.json()["id"]

    with SessionLocal() as db:
        token = db.query(models.EmergencySOS).filter(
            models.EmergencySOS.id == sos_id).first().public_token
    assert token, "every alert must be trackable by its contacts"

    # No Authorization header at all — this is the whole point.
    page = client.get(f"/api/v1/sos/track/{token}")
    assert page.status_code == 200, page.text
    body = page.json()

    assert body["status"] == "ACTIVE"
    assert body["voice_note"] == "chest pain"
    assert body["location_lat"] == 11.05
    # Distance must be a real kilometre figure, not raw degrees: the
    # hospital is roughly 6 km away, so anything near 0.05 (the degree
    # delta) would mean the haversine never ran.
    assert body["distance_km"] is not None
    assert 3 < body["distance_km"] < 15, body["distance_km"]
    assert body["eta_minutes"] and body["eta_minutes"] > 0
    assert body["hospital_name"] == "GH Track"

    # Nothing clinical or identifying leaks through a link that travels by SMS.
    for leaked in ("patient_id", "id", "allergies", "chronic_conditions"):
        assert leaked not in body, leaked


def test_sos_tracking_rejects_an_unknown_token(client):
    assert client.get("/api/v1/sos/track/not-a-real-token").status_code == 404


def test_sos_accepts_a_recording_in_the_container_android_actually_writes(client, patient_token):
    """Android's MediaMuxer stamps MPEG-4 with brand "isom"/"mp42", which
    sniffs as video/mp4 rather than audio/mp4. An allow-list written from
    what the format is called instead of what the sniffer returns rejected
    every voice note the app recorded.
    """
    import base64

    res = client.post("/api/v1/sos/trigger", headers=auth(patient_token), json={
        "location_lat": 11.05, "location_lng": 77.08, "severity": "CRITICAL",
    })
    sos_id = res.json()["id"]

    # Minimal ftyp box carrying the brand a phone really writes.
    header = bytes([0, 0, 0, 0x20]) + b"ftypisom" + bytes([0, 0, 2, 0])
    mp4 = base64.b64encode(header + b"isomiso2mp41" + bytes(32)).decode()

    attached = client.post(
        f"/api/v1/sos/{sos_id}/voice",
        headers=auth(patient_token),
        json={"voice_audio_base64": mp4},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["voice_audio_url"]


def test_sos_trigger_returns_the_family_tracking_link(client, patient_token):
    """The phone composes the SMS and WhatsApp message itself, because those
    work with nothing configured. They used to carry only a map pin, so the
    family never reached the page with the hospital, ETA and recording."""
    res = client.post("/api/v1/sos/trigger", headers=auth(patient_token), json={
        "location_lat": 11.05, "location_lng": 77.08, "severity": "CRITICAL",
    })
    assert res.status_code == 200, res.text
    url = res.json()["tracking_url"]
    assert url and "/sos/track/" in url

    token = url.rsplit("/", 1)[-1]
    page = client.get(f"/api/v1/sos/track/{token}")
    assert page.status_code == 200, "the link the phone sends must actually open"

    mine = client.get("/api/v1/sos/mine", headers=auth(patient_token)).json()
    assert mine[0]["tracking_url"] == url
