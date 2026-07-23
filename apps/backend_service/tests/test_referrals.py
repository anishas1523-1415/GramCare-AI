"""Referral Network contract tests: specific-doctor + open referrals, the
incoming/sent/mine listings, accept/decline/complete, and the authorization
rules gating who may act on a referral."""
from tests.conftest import auth, _register_and_login


def _current_user_id(client, token) -> int:
    return client.get("/api/v1/auth/me", headers=auth(token)).json()["id"]


def _setup_doctor(client, username, specialty="General Medicine"):
    token = _register_and_login(client, username, "DOCTOR")
    res = client.put("/api/v1/doctors/me", headers=auth(token), json={"specialty": specialty})
    assert res.status_code == 200, res.text
    return token, _current_user_id(client, token)


def test_create_referral_to_specific_doctor(client):
    referring_token, referring_id = _setup_doctor(client, "ref_doc_a", "General Medicine")
    target_token, target_id = _setup_doctor(client, "ref_doc_b", "Cardiology")
    patient_token = _register_and_login(client, "ref_patient_1", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    res = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": target_id,
        "specialty": "Cardiology",
        "reason": "Suspected arrhythmia, needs specialist evaluation.",
        "notes": "Patient reports palpitations for 2 weeks.",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "PENDING"
    assert body["referring_doctor_id"] == referring_id
    assert body["referred_to_doctor_id"] == target_id
    assert body["patient_id"] == patient_id
    assert body["resolved_at"] is None


def test_create_open_referral_no_target_doctor(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_c", "General Medicine")
    patient_token = _register_and_login(client, "ref_patient_2", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    res = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "specialty": "Dermatology",
        "reason": "Persistent rash, needs a dermatologist.",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["referred_to_doctor_id"] is None
    assert body["status"] == "PENDING"


def test_cannot_refer_patient_to_self(client):
    referring_token, referring_id = _setup_doctor(client, "ref_doc_d", "General Medicine")
    patient_token = _register_and_login(client, "ref_patient_3", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    res = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": referring_id,
        "specialty": "General Medicine",
        "reason": "Self-referral attempt.",
    })
    assert res.status_code == 400


def test_patient_cannot_create_referral(client, patient_token):
    res = client.post("/api/v1/referrals", headers=auth(patient_token), json={
        "patient_id": _current_user_id(client, patient_token),
        "specialty": "Cardiology",
        "reason": "Trying to self-refer as a patient.",
    })
    assert res.status_code == 403


def test_referral_requires_patient_or_family_profile(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_e", "General Medicine")
    res = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "specialty": "Cardiology",
        "reason": "Missing patient reference.",
    })
    assert res.status_code == 400


def test_incoming_sent_and_mine_listings(client):
    referring_token, referring_id = _setup_doctor(client, "ref_doc_f", "General Medicine")
    target_token, target_id = _setup_doctor(client, "ref_doc_g", "Orthopedics")
    other_specialty_token, _ = _setup_doctor(client, "ref_doc_h", "Neurology")
    patient_token = _register_and_login(client, "ref_patient_4", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    specific = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": target_id,
        "specialty": "Orthopedics",
        "reason": "Knee pain, possible ligament tear.",
    }).json()

    open_ref = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "specialty": "Orthopedics",
        "reason": "Back pain, needs orthopedic review.",
    }).json()

    # Target doctor sees both: the one addressed to them directly, and the
    # open one matching their specialty.
    incoming = client.get("/api/v1/referrals/incoming", headers=auth(target_token)).json()
    incoming_ids = {r["id"] for r in incoming}
    assert specific["id"] in incoming_ids
    assert open_ref["id"] in incoming_ids

    # A doctor of a different specialty sees neither.
    other_incoming = client.get("/api/v1/referrals/incoming", headers=auth(other_specialty_token)).json()
    other_ids = {r["id"] for r in other_incoming}
    assert specific["id"] not in other_ids
    assert open_ref["id"] not in other_ids

    # Referring doctor's sent list has both.
    sent = client.get("/api/v1/referrals/sent", headers=auth(referring_token)).json()
    sent_ids = {r["id"] for r in sent}
    assert specific["id"] in sent_ids
    assert open_ref["id"] in sent_ids

    # Patient sees both referrals made about them, newest first.
    mine = client.get("/api/v1/referrals/mine", headers=auth(patient_token)).json()
    mine_ids = [r["id"] for r in mine]
    assert specific["id"] in mine_ids
    assert open_ref["id"] in mine_ids
    assert mine_ids.index(open_ref["id"]) < mine_ids.index(specific["id"])  # newest first


def test_accept_specific_referral(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_i", "General Medicine")
    target_token, target_id = _setup_doctor(client, "ref_doc_j", "ENT")
    patient_token = _register_and_login(client, "ref_patient_5", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    referral = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": target_id,
        "specialty": "ENT",
        "reason": "Chronic sinusitis.",
    }).json()

    res = client.put(f"/api/v1/referrals/{referral['id']}/accept", headers=auth(target_token))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "ACCEPTED"
    assert res.json()["referred_to_doctor_id"] == target_id


def test_wrong_doctor_cannot_accept_specific_referral(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_k", "General Medicine")
    target_token, target_id = _setup_doctor(client, "ref_doc_l", "Pediatrics")
    bystander_token, _ = _setup_doctor(client, "ref_doc_m", "Pediatrics")
    patient_token = _register_and_login(client, "ref_patient_6", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    referral = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": target_id,
        "specialty": "Pediatrics",
        "reason": "Growth concerns.",
    }).json()

    # Even though bystander shares the same specialty, this referral is NOT
    # open (it has a specific target) so only that target may act on it.
    res = client.put(f"/api/v1/referrals/{referral['id']}/accept", headers=auth(bystander_token))
    assert res.status_code == 403


def test_open_referral_claimed_on_accept(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_n", "General Medicine")
    claimer_token, claimer_id = _setup_doctor(client, "ref_doc_o", "Psychiatry")
    non_matching_token, _ = _setup_doctor(client, "ref_doc_p", "Radiology")
    patient_token = _register_and_login(client, "ref_patient_7", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    open_ref = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "specialty": "Psychiatry",
        "reason": "Anxiety management.",
    }).json()

    # A non-matching-specialty doctor cannot accept it.
    denied = client.put(f"/api/v1/referrals/{open_ref['id']}/accept", headers=auth(non_matching_token))
    assert denied.status_code == 403

    accepted = client.put(f"/api/v1/referrals/{open_ref['id']}/accept", headers=auth(claimer_token))
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "ACCEPTED"
    assert body["referred_to_doctor_id"] == claimer_id

    # Now claimed — no longer shows up as an open match for other Psychiatry doctors.
    other_psych_token, _ = _setup_doctor(client, "ref_doc_q", "Psychiatry")
    incoming = client.get("/api/v1/referrals/incoming", headers=auth(other_psych_token)).json()
    assert all(r["id"] != open_ref["id"] for r in incoming)


def test_decline_referral(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_r", "General Medicine")
    target_token, target_id = _setup_doctor(client, "ref_doc_s", "Oncology")
    patient_token = _register_and_login(client, "ref_patient_8", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    referral = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": target_id,
        "specialty": "Oncology",
        "reason": "Needs oncology consult.",
    }).json()

    res = client.put(f"/api/v1/referrals/{referral['id']}/decline", headers=auth(target_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "DECLINED"
    assert body["resolved_at"] is not None

    # Terminal — cannot be accepted afterwards.
    reaccept = client.put(f"/api/v1/referrals/{referral['id']}/accept", headers=auth(target_token))
    assert reaccept.status_code == 400


def test_complete_referral_requires_accept_first(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_t", "General Medicine")
    target_token, target_id = _setup_doctor(client, "ref_doc_u", "Urology")
    patient_token = _register_and_login(client, "ref_patient_9", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    referral = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": target_id,
        "specialty": "Urology",
        "reason": "Needs urology consult.",
    }).json()

    # Cannot complete while still PENDING.
    too_early = client.put(f"/api/v1/referrals/{referral['id']}/complete", headers=auth(target_token))
    assert too_early.status_code == 400

    accept = client.put(f"/api/v1/referrals/{referral['id']}/accept", headers=auth(target_token))
    assert accept.status_code == 200, accept.text

    complete = client.put(f"/api/v1/referrals/{referral['id']}/complete", headers=auth(target_token))
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["status"] == "COMPLETED"
    assert body["resolved_at"] is not None


def test_only_owning_doctor_can_complete(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_v", "General Medicine")
    target_token, target_id = _setup_doctor(client, "ref_doc_w", "Gastroenterology")
    bystander_token, _ = _setup_doctor(client, "ref_doc_x", "Gastroenterology")
    patient_token = _register_and_login(client, "ref_patient_10", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    referral = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "patient_id": patient_id,
        "referred_to_doctor_id": target_id,
        "specialty": "Gastroenterology",
        "reason": "Needs GI consult.",
    }).json()
    client.put(f"/api/v1/referrals/{referral['id']}/accept", headers=auth(target_token))

    res = client.put(f"/api/v1/referrals/{referral['id']}/complete", headers=auth(bystander_token))
    assert res.status_code == 404


def test_referral_via_family_profile(client):
    referring_token, _ = _setup_doctor(client, "ref_doc_y", "General Medicine")
    patient_token = _register_and_login(client, "ref_patient_11", "PATIENT")
    patient_id = _current_user_id(client, patient_token)

    family = client.post("/api/v1/family", headers=auth(patient_token), json={
        "full_name": "Referral Kid",
        "relation": "Child",
        "age": 8,
        "gender": "Male",
    })
    assert family.status_code == 201, family.text
    family_id = family.json()["id"]

    res = client.post("/api/v1/referrals", headers=auth(referring_token), json={
        "family_profile_id": family_id,
        "specialty": "Pediatrics",
        "reason": "Fever workup for child.",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["family_profile_id"] == family_id
    assert body["patient_id"] == patient_id  # derived from the profile's owning account
