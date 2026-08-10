"""PUT /auth/me/phone — lets an existing PATIENT account add/change the
phone number SMS appointment reminders go to. Registration never collects
a phone for PATIENT (deliberately low-friction, see modules/auth/router.py
register_user), so this is the only path for a patient who registered
before this field mattered.
"""
from tests.conftest import auth, _register_and_login


def test_patient_can_set_and_update_own_phone(client, db):
    token = _register_and_login(client, "phone_patient", "PATIENT")

    res = client.put("/api/v1/auth/me/phone", headers=auth(token), json={"phone": "+919000099999"})
    assert res.status_code == 200, res.text
    assert res.json()["phone"] == "+919000099999"

    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    assert me["phone"] == "+919000099999"

    # Updating again overwrites rather than requiring the field to be empty.
    res2 = client.put("/api/v1/auth/me/phone", headers=auth(token), json={"phone": "+919000088888"})
    assert res2.status_code == 200, res2.text
    me2 = client.get("/api/v1/auth/me", headers=auth(token)).json()
    assert me2["phone"] == "+919000088888"


def test_non_patient_cannot_use_patient_phone_endpoint(client, doctor_token):
    res = client.put("/api/v1/auth/me/phone", headers=auth(doctor_token), json={"phone": "+919000077777"})
    assert res.status_code == 403


def test_phone_update_rejects_too_short_value(client):
    token = _register_and_login(client, "phone_patient_short", "PATIENT")
    res = client.put("/api/v1/auth/me/phone", headers=auth(token), json={"phone": "123"})
    assert res.status_code == 422


def test_phone_update_requires_auth(client):
    res = client.put("/api/v1/auth/me/phone", json={"phone": "+919000066666"})
    assert res.status_code == 401
