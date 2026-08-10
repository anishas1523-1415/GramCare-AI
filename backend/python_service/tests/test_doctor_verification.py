"""Doctor government-verification workflow + government whitelist gate.

Covers the anti-fake-doctor requirement: a newly registered doctor starts
PENDING and is blocked from patient-facing actions and the public directory
until a government (ADMIN) reviewer approves them; ADMIN accounts can only
ever be created via the whitelist-gated /auth/register/government route.
"""
import models
from tests.conftest import auth


def _register_doctor_raw(client, username, email=None):
    """Registers a DOCTOR WITHOUT the conftest auto-approve side channel —
    this test module exists specifically to exercise the real PENDING state,
    so it must not go through _register_and_login's DOCTOR auto-approval.
    Still has to satisfy the (unrelated to PENDING/APPROVED) phone- and
    email-verification gates every registration goes through now, so this
    seeds a pre-verified PhoneOTP and flips is_verified directly — same
    test-only bypass conftest's _register_and_login uses."""
    from datetime import datetime, timezone, timedelta
    from database import SessionLocal

    test_phone = f"+91900001{abs(hash(username)) % 10000:04d}"
    session = SessionLocal()
    try:
        session.add(models.PhoneOTP(
            phone=test_phone,
            otp_code="000000",
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10),
            is_used=True,
        ))
        session.commit()
    finally:
        session.close()

    res = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@test.gramcare.in",
            "password": "strongpass123",
            "full_name": username.title(),
            "role": "DOCTOR",
            "phone": test_phone,
        },
    )
    assert res.status_code == 200, res.text

    session = SessionLocal()
    try:
        user = session.query(models.User).filter(models.User.username == username).first()
        user.is_verified = True
        session.commit()
    finally:
        session.close()

    login = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "strongpass123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _whitelist_email(db, email):
    db.add(models.AuthorizedGovernmentEmail(email=email.lower()))
    db.commit()


def _register_government(client, username, email, password="govpass123"):
    return client.post(
        "/api/v1/auth/register/government",
        json={"username": username, "email": email, "password": password, "full_name": "Health Ministry"},
    )


def test_generic_register_rejects_admin_role(client):
    """The public /auth/register endpoint must never accept role=ADMIN —
    this was a real, closed vulnerability (anyone could self-register as a
    government/ADMIN account)."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "sneaky_admin",
            "email": "sneaky_admin@test.gramcare.in",
            "password": "strongpass123",
            "full_name": "Sneaky",
            "role": "ADMIN",
        },
    )
    assert res.status_code == 422


def test_government_registration_requires_whitelisted_email(client, db):
    rejected = _register_government(client, "gov_not_whitelisted", "not_on_list@example.com")
    assert rejected.status_code == 403

    _whitelist_email(db, "whitelisted.official@example.com")
    accepted = _register_government(client, "gov_whitelisted", "whitelisted.official@example.com")
    assert accepted.status_code == 200, accepted.text

    # This test's purpose is the whitelist gate, not email verification —
    # bypass the latter the same way conftest's _register_and_login does.
    gov_user = db.query(models.User).filter(models.User.username == "gov_whitelisted").first()
    gov_user.is_verified = True
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "gov_whitelisted", "password": "govpass123"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "ADMIN"


def test_government_whitelist_check_is_case_insensitive_exact_match(client, db):
    """Also guards against the LIKE-wildcard bug class: '%'/'_' in the
    submitted email must never act as SQL wildcards against the whitelist."""
    _whitelist_email(db, "Case.Test@Example.com")
    res = _register_government(client, "gov_case_test", "case.test@example.com")
    assert res.status_code == 200, res.text

    # A wildcard-shaped email must NOT match unless literally whitelisted.
    wildcard_attempt = _register_government(client, "gov_wildcard_attempt", "%@example.com")
    assert wildcard_attempt.status_code == 403


def test_pending_doctor_blocked_from_sensitive_actions(client):
    doctor_token = _register_doctor_raw(client, "pending_doc_1")

    # Can view/edit their own profile while pending.
    me = client.get("/api/v1/doctors/me", headers=auth(doctor_token))
    assert me.status_code == 200
    assert me.json()["verification_status"] == "PENDING"

    # Cannot publish availability slots yet.
    from datetime import datetime, timedelta
    future = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    future_end = (datetime.utcnow() + timedelta(hours=25)).isoformat()
    slots_res = client.post(
        "/api/v1/doctors/me/slots",
        headers=auth(doctor_token),
        json=[{"start_time": future, "end_time": future_end}],
    )
    assert slots_res.status_code == 403


def test_pending_doctor_excluded_from_public_directory(client):
    _register_doctor_raw(client, "pending_doc_2")

    from tests.conftest import _register_and_login
    patient_token = _register_and_login(client, "dir_test_patient", "PATIENT")
    directory = client.get("/api/v1/doctors", headers=auth(patient_token))
    assert directory.status_code == 200
    names = [d["full_name"] for d in directory.json()]
    assert "Pending_Doc_2" not in names


def test_admin_can_approve_and_reject_doctors(client, db):
    from tests.conftest import _register_and_login

    admin_token = _register_and_login(client, "verif_admin", "ADMIN")
    doctor_token = _register_doctor_raw(client, "verif_doc_approve")
    doctor_id = db.query(models.User).filter(models.User.username == "verif_doc_approve").first().id

    # Shows up in the pending queue.
    pending = client.get("/api/v1/doctors/pending", headers=auth(admin_token))
    assert pending.status_code == 200
    assert any(d["id"] == doctor_id for d in pending.json())

    approved = client.put(f"/api/v1/doctors/{doctor_id}/approve", headers=auth(admin_token))
    assert approved.status_code == 200, approved.text
    assert approved.json()["verification_status"] == "APPROVED"

    # Now visible in the public directory and able to publish slots.
    patient_token = _register_and_login(client, "verif_patient", "PATIENT")
    directory = client.get("/api/v1/doctors", headers=auth(patient_token))
    assert any(d["id"] == doctor_id for d in directory.json())

    from datetime import datetime, timedelta
    future = (datetime.utcnow() + timedelta(hours=48)).isoformat()
    future_end = (datetime.utcnow() + timedelta(hours=49)).isoformat()
    slots_res = client.post(
        "/api/v1/doctors/me/slots",
        headers=auth(doctor_token),
        json=[{"start_time": future, "end_time": future_end}],
    )
    assert slots_res.status_code == 201, slots_res.text

    # A second, separately-registered doctor gets rejected with a reason.
    doctor_token_2 = _register_doctor_raw(client, "verif_doc_reject")
    user2 = db.query(models.User).filter(models.User.username == "verif_doc_reject").first()
    rejected = client.put(
        f"/api/v1/doctors/{user2.id}/reject",
        headers=auth(admin_token),
        json={"reason": "License number could not be verified."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["verification_status"] == "REJECTED"
    assert rejected.json()["rejection_reason"] == "License number could not be verified."

    # The rejected doctor sees the reason on their own profile.
    me2 = client.get("/api/v1/doctors/me", headers=auth(doctor_token_2))
    assert me2.json()["rejection_reason"] == "License number could not be verified."
