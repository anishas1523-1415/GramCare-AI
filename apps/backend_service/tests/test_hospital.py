"""Hospital self-registration (modules/hospital/router.py).

Data-collection only, instant access — no government approval gate, unlike
DoctorProfile. See tests/test_doctor_verification.py for the doctor case.
"""
from tests.conftest import auth, _register_and_login


def test_hospital_me_requires_registration_first(client):
    token = _register_and_login(client, "hosp_unregistered", "HOSPITAL")
    res = client.get("/api/v1/hospital/me", headers=auth(token))
    assert res.status_code == 409


def test_hospital_registration_captures_rich_fields_and_is_instant_access(client):
    token = _register_and_login(client, "hosp_richform", "HOSPITAL")
    res = client.post("/api/v1/hospital/register", headers=auth(token), json={
        "name": "Grama General Hospital",
        "address": "Bypass Road, Madurai",
        "lat": 9.9252, "lng": 78.1198,
        "phone": "+91-9000000010",
        "established_year": 1998,
        "service_timing": "24/7",
        "specializations": "General Medicine, Pediatrics, Orthopedics",
        "license_number": "TN-HOSP-2026-0042",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Grama General Hospital"
    assert body["established_year"] == 1998
    assert body["service_timing"] == "24/7"
    assert body["specializations"] == "General Medicine, Pediatrics, Orthopedics"
    assert body["license_number"] == "TN-HOSP-2026-0042"
    # No approval gate: /me works immediately, same request.
    me = client.get("/api/v1/hospital/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["owner_user_id"] is not None


def test_hospital_registration_is_update_not_duplicate(client):
    token = _register_and_login(client, "hosp_update", "HOSPITAL")
    first = client.post("/api/v1/hospital/register", headers=auth(token), json={"name": "First Name"})
    assert first.status_code == 200
    hospital_id = first.json()["id"]

    second = client.post("/api/v1/hospital/register", headers=auth(token), json={"name": "Updated Name"})
    assert second.status_code == 200
    assert second.json()["id"] == hospital_id
    assert second.json()["name"] == "Updated Name"
