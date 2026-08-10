"""Digital Health Passport — patient-owned emergency profile, readable via
a public capability-token URL without login."""
from tests.conftest import auth, _register_and_login


def test_passport_starts_empty_and_unshared(client, patient_token):
    res = client.get("/api/v1/passport/me", headers=auth(patient_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passport_token"] is None
    assert body["blood_group"] is None


def test_updating_passport_generates_a_token(client):
    token = _register_and_login(client, "passport_patient1", "PATIENT")

    res = client.put(
        "/api/v1/passport/me",
        headers=auth(token),
        json={"blood_group": "O+", "allergies": "Penicillin", "chronic_conditions": "Asthma"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["blood_group"] == "O+"
    assert body["passport_token"] is not None
    assert len(body["passport_token"]) > 20


def test_public_passport_lookup_returns_minimal_emergency_data(client):
    token = _register_and_login(client, "passport_patient2", "PATIENT")

    update = client.put(
        "/api/v1/passport/me",
        headers=auth(token),
        json={"blood_group": "AB-", "allergies": "None known", "chronic_conditions": "Diabetes"},
    )
    passport_token = update.json()["passport_token"]

    client.post(
        "/api/v1/sos/contacts",
        headers=auth(token),
        json={"name": "Meena", "phone": "+919000011111", "relation": "Sister"},
    )

    # Public lookup — no Authorization header at all.
    res = client.get(f"/api/v1/passport/{passport_token}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["blood_group"] == "AB-"
    assert body["chronic_conditions"] == "Diabetes"
    assert any(c["name"] == "Meena" for c in body["emergency_contacts"])
    # Deliberately minimal — no account identifiers leak through.
    assert "email" not in body
    assert "username" not in body


def test_unknown_token_returns_404(client):
    res = client.get("/api/v1/passport/this-token-does-not-exist")
    assert res.status_code == 404


def test_regenerating_token_invalidates_the_old_one(client):
    token = _register_and_login(client, "passport_patient3", "PATIENT")
    first = client.put(
        "/api/v1/passport/me", headers=auth(token), json={"blood_group": "B+"}
    ).json()["passport_token"]

    regen = client.post("/api/v1/passport/me/regenerate-token", headers=auth(token))
    assert regen.status_code == 200, regen.text
    second = regen.json()["passport_token"]
    assert second != first

    # Old code no longer resolves; new one does.
    assert client.get(f"/api/v1/passport/{first}").status_code == 404
    assert client.get(f"/api/v1/passport/{second}").status_code == 200


def test_non_patient_cannot_access_passport_endpoints(client, doctor_token):
    res = client.get("/api/v1/passport/me", headers=auth(doctor_token))
    assert res.status_code == 403
