"""Community Health Worker (CHW) tooling contract tests: registering a
walk-in patient, the ownership boundary on proxy actions, and that proxy
triage/booking attribute their result to the PATIENT, not the CHW."""
from datetime import datetime, timedelta

from tests.conftest import auth, _register_and_login


def _future(hours):
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _setup_chw(client, username="chw_a"):
    return _register_and_login(client, username, "CHW")


def _register_walkin_patient(client, chw_token, full_name="Walkin Villager"):
    res = client.post("/api/v1/chw/register-patient", headers=auth(chw_token), json={
        "full_name": full_name,
        "age": 45,
        "gender": "Female",
        "phone": "9999900000",
        "address_note": "Near the village well",
    })
    assert res.status_code == 201, res.text
    return res.json()


def test_chw_registers_walkin_patient(client):
    chw_token = _setup_chw(client, "chw_reg_a")
    body = _register_walkin_patient(client, chw_token)
    assert body["role"] == "PATIENT"
    assert body["full_name"] == "Walkin Villager"
    assert body["temporary_password"]
    assert body["username"]

    # The generated credentials actually log in as a real PATIENT account.
    login = client.post("/api/v1/auth/login", data={
        "username": body["username"], "password": body["temporary_password"],
    })
    assert login.status_code == 200, login.text


def test_non_chw_cannot_register_patient(client, patient_token):
    res = client.post("/api/v1/chw/register-patient", headers=auth(patient_token), json={
        "full_name": "Someone", "age": 30, "gender": "Male",
    })
    assert res.status_code == 403


def test_my_patients_lists_only_own_registrations(client):
    chw_a = _setup_chw(client, "chw_list_a")
    chw_b = _setup_chw(client, "chw_list_b")
    reg_a = _register_walkin_patient(client, chw_a, "Patient Of A")
    reg_b = _register_walkin_patient(client, chw_b, "Patient Of B")

    mine_a = client.get("/api/v1/chw/my-patients", headers=auth(chw_a)).json()
    ids_a = {p["id"] for p in mine_a}
    assert reg_a["id"] in ids_a
    assert reg_b["id"] not in ids_a


def test_chw_can_triage_own_patient(client):
    chw_token = _setup_chw(client, "chw_triage_a")
    patient = _register_walkin_patient(client, chw_token, "Triage Patient")

    res = client.post(
        f"/api/v1/chw/patients/{patient['id']}/triage",
        headers=auth(chw_token),
        json={"symptoms_text": "Fever and body ache for two days", "age": 45},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "severity_score" in body
    assert "disclaimer" in body


def test_chw_cannot_triage_patient_registered_by_another_chw(client):
    chw_a = _setup_chw(client, "chw_triage_b")
    chw_b = _setup_chw(client, "chw_triage_c")
    patient = _register_walkin_patient(client, chw_a, "Not Yours")

    res = client.post(
        f"/api/v1/chw/patients/{patient['id']}/triage",
        headers=auth(chw_b),
        json={"symptoms_text": "Cough and cold", "age": 45},
    )
    assert res.status_code == 403


def test_chw_triage_is_attributed_to_the_patient_not_the_chw(client, db):
    import models

    chw_token = _setup_chw(client, "chw_triage_attr")
    patient = _register_walkin_patient(client, chw_token, "Attribution Patient")

    res = client.post(
        f"/api/v1/chw/patients/{patient['id']}/triage",
        headers=auth(chw_token),
        json={"symptoms_text": "Persistent headache for a week", "age": 45},
    )
    assert res.status_code == 200, res.text

    log = (
        db.query(models.TriageLog)
        .filter(models.TriageLog.patient_id == patient["id"])
        .order_by(models.TriageLog.id.desc())
        .first()
    )
    assert log is not None
    assert log.patient_id == patient["id"]


def test_chw_can_book_free_consultation_for_own_patient(client):
    chw_token = _setup_chw(client, "chw_book_a")
    patient = _register_walkin_patient(client, chw_token, "Booking Patient")

    doctor_token = _register_and_login(client, "chw_book_doctor_a", "DOCTOR")
    client.put("/api/v1/doctors/me", headers=auth(doctor_token),
               json={"specialty": "General Medicine", "consultation_fee": 0})
    slots = client.post("/api/v1/doctors/me/slots", headers=auth(doctor_token), json=[
        {"start_time": _future(24), "end_time": _future(25)},
    ])
    assert slots.status_code == 201, slots.text
    slot_id = slots.json()[0]["id"]

    res = client.post(
        f"/api/v1/chw/patients/{patient['id']}/book",
        headers=auth(chw_token),
        json={"doctor_id": doctor_token and client.get('/api/v1/auth/me', headers=auth(doctor_token)).json()["id"], "slot_id": slot_id},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["patient_id"] == patient["id"]
    assert body["status"] == "CONFIRMED"


def test_chw_booking_for_unowned_patient_is_forbidden(client):
    chw_a = _setup_chw(client, "chw_book_b")
    chw_b = _setup_chw(client, "chw_book_c")
    patient = _register_walkin_patient(client, chw_a, "Not Yours Either")

    doctor_token = _register_and_login(client, "chw_book_doctor_b", "DOCTOR")
    client.put("/api/v1/doctors/me", headers=auth(doctor_token),
               json={"specialty": "General Medicine", "consultation_fee": 0})
    slots = client.post("/api/v1/doctors/me/slots", headers=auth(doctor_token), json=[
        {"start_time": _future(24), "end_time": _future(25)},
    ])
    doctor_id = client.get('/api/v1/auth/me', headers=auth(doctor_token)).json()["id"]

    res = client.post(
        f"/api/v1/chw/patients/{patient['id']}/book",
        headers=auth(chw_b),
        json={"doctor_id": doctor_id, "slot_id": slots.json()[0]["id"]},
    )
    assert res.status_code == 403


def test_chw_paid_booking_still_requires_patients_own_payment(client):
    """The module's documented contract: a CHW cannot pay "as themselves"
    and consume it on the patient's behalf — a paid doctor still requires a
    payment_order_id whose Payment.patient_id matches the target patient."""
    chw_token = _setup_chw(client, "chw_book_paid")
    patient = _register_walkin_patient(client, chw_token, "Paid Booking Patient")

    doctor_token = _register_and_login(client, "chw_book_doctor_paid", "DOCTOR")
    client.put("/api/v1/doctors/me", headers=auth(doctor_token),
               json={"specialty": "Cardiology", "consultation_fee": 200})
    slots = client.post("/api/v1/doctors/me/slots", headers=auth(doctor_token), json=[
        {"start_time": _future(24), "end_time": _future(25)},
    ])
    doctor_id = client.get('/api/v1/auth/me', headers=auth(doctor_token)).json()["id"]

    res = client.post(
        f"/api/v1/chw/patients/{patient['id']}/book",
        headers=auth(chw_token),
        json={"doctor_id": doctor_id, "slot_id": slots.json()[0]["id"]},
    )
    assert res.status_code == 402
