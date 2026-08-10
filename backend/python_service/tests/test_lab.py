"""Laboratory module contract tests: registration, test catalog search,
booking lifecycle, report submission -> Health Wallet auto-save."""
from tests.conftest import auth, _register_and_login


def _setup_lab(client, username="lab_a"):
    token = _register_and_login(client, username, "LAB")
    reg = client.post("/api/v1/lab/register", headers=auth(token), json={
        "name": f"Grama Diagnostics {username}",
        "address": "Bypass Road, Madurai",
        "lat": 9.9252, "lng": 78.1198,
        "phone": "+91-9000000002",
        "offers_home_collection": True,
    })
    assert reg.status_code == 200, reg.text
    return token, reg.json()["id"]


def test_catalog_search_returns_prep_instructions(client):
    token = _register_and_login(client, "lab_patient_catalog", "PATIENT")
    res = client.get("/api/v1/lab/tests?query=fasting", headers=auth(token))
    assert res.status_code == 200, res.text
    results = res.json()
    assert any("Fasting Blood Sugar" in r["name"] for r in results)
    assert all(r["prep_instructions"] for r in results)


def test_lab_requires_registration_first(client):
    token = _register_and_login(client, "lab_unregistered", "LAB")
    res = client.get("/api/v1/lab/me", headers=auth(token))
    assert res.status_code == 409


def test_booking_lifecycle_and_wallet_sync(client):
    lab_token, lab_id = _setup_lab(client)
    patient_token = _register_and_login(client, "lab_patient_1", "PATIENT")

    # Patient books a test at the lab, with home collection
    booked = client.post("/api/v1/lab/bookings", headers=auth(patient_token), json={
        "lab_center_id": lab_id,
        "test_name": "Complete Blood Count (CBC)",
        "home_collection": True,
    })
    assert booked.status_code == 201, booked.text
    booking_id = booked.json()["id"]
    assert booked.json()["status"] == "BOOKED"

    # Shows up in the patient's own list
    mine = client.get("/api/v1/lab/bookings/mine", headers=auth(patient_token)).json()
    assert any(b["id"] == booking_id for b in mine)

    # Shows up in the lab's queue
    queue = client.get("/api/v1/lab/bookings/queue", headers=auth(lab_token)).json()
    assert any(b["id"] == booking_id for b in queue)

    # Lab progresses the booking through the lifecycle
    step1 = client.put(
        f"/api/v1/lab/bookings/{booking_id}/status?status=SAMPLE_COLLECTED",
        headers=auth(lab_token),
    )
    assert step1.status_code == 200, step1.text
    step2 = client.put(
        f"/api/v1/lab/bookings/{booking_id}/status?status=PROCESSING",
        headers=auth(lab_token),
    )
    assert step2.status_code == 200, step2.text

    # Lab submits the report
    report = client.post(f"/api/v1/lab/bookings/{booking_id}/report", headers=auth(lab_token), json={
        "values": [
            {"parameter": "Hemoglobin", "value": "13.5", "unit": "g/dL", "reference_range": "13-17", "flag": "NORMAL"},
        ],
        "summary": "All values within normal range.",
    })
    assert report.status_code == 200, report.text
    assert report.json()["status"] == "REPORT_READY"
    assert report.json()["report_payload"]["summary"] == "All values within normal range."

    # Now off the lab's active queue (only non-completed/cancelled)
    queue_after = client.get("/api/v1/lab/bookings/queue", headers=auth(lab_token)).json()
    assert all(b["id"] != booking_id for b in queue_after)

    # Report auto-synced into the patient's Family Health Wallet
    records = client.get(
        f"/api/v1/ehr/patient/{_current_user_id(client, patient_token)}",
        headers=auth(patient_token),
    ).json()
    lab_records = [r for r in records if r["record_type"] == "lab_report"]
    assert len(lab_records) == 1
    assert lab_records[0]["title"] == "Complete Blood Count (CBC)"

    # Patient acknowledges completion
    complete = client.put(f"/api/v1/lab/bookings/{booking_id}/complete", headers=auth(patient_token))
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "COMPLETED"


def test_home_collection_rejected_when_not_offered(client):
    token = _register_and_login(client, "lab_no_home", "LAB")
    reg = client.post("/api/v1/lab/register", headers=auth(token), json={
        "name": "No Home Collection Diagnostics",
        "offers_home_collection": False,
    })
    assert reg.status_code == 200
    lab_id = reg.json()["id"]

    patient_token = _register_and_login(client, "lab_patient_2", "PATIENT")
    res = client.post("/api/v1/lab/bookings", headers=auth(patient_token), json={
        "lab_center_id": lab_id,
        "test_name": "Lipid Profile",
        "home_collection": True,
    })
    assert res.status_code == 400


def _current_user_id(client, token) -> int:
    return client.get("/api/v1/auth/me", headers=auth(token)).json()["id"]
