"""Shared test fixtures.

Each test session runs against a throwaway SQLite database built directly
from the SQLAlchemy metadata (create_all). Migration correctness is covered
separately by test_migrations.py, which runs the real alembic chain.
"""
import os
import sys
import tempfile

import pytest

# Make the service root importable regardless of pytest invocation dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point the app at a fresh temp DB BEFORE importing database/main
_TMPDIR = tempfile.mkdtemp(prefix="gramcare_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
# Set to EMPTY (not pop): the app modules call load_dotenv(), which would
# re-populate popped keys from apps/backend_service/.env. An existing (even
# empty) env var wins over .env, forcing the mock AI/payment paths.
os.environ["GEMINI_API_KEY"] = ""
os.environ["RAZORPAY_KEY_ID"] = ""
os.environ["RAZORPAY_KEY_SECRET"] = ""
# Fixed test secret so tests/test_payments.py can compute valid webhook
# signatures with plain hmac — gateway keys stay empty above (mock-mode
# payments), but the webhook secret is a genuinely separate credential in
# real Razorpay (see modules/payments/router.py), so it's exercised here
# independently of mock vs. real gateway mode.
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_not_for_production")
os.environ["TESTING"] = "1"  # disables the SOS escalation background loop

from fastapi.testclient import TestClient  # noqa: E402

import models  # noqa: E402
from database import engine  # noqa: E402
from core import ratelimit  # noqa: E402
from main import app  # noqa: E402

models.Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Rate limits must never bleed between tests."""
    ratelimit.reset_for_tests()
    yield
    ratelimit.reset_for_tests()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture()
def db():
    """A direct SQLAlchemy session against the same test database `client`
    talks to through the app — for tests that need to assert on rows the API
    doesn't expose directly (e.g. tests/test_notifications.py checking
    UserPushToken.is_active). Function-scoped and always closed, mirroring
    database.get_db()'s per-request lifecycle rather than leaking a
    session across the whole test session.
    """
    from database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _register_and_login(client, username, role, email=None, phone=None):
    """Test-only account creation. A few roles need a side channel around the
    real (intentionally restricted) public API:

    - ADMIN accounts can no longer self-register via POST /auth/register at
      all (that hole is closed) — the only real path is
      POST /auth/register/government, gated by a whitelist tests don't
      populate. Callers that need an ADMIN token are testing *other*
      endpoints (e.g. batch recall issuance), not the whitelist itself, so
      this writes the User row directly.
    - DOCTOR accounts now start PENDING and are blocked from patient-facing
      actions (appointment queue, prescriptions, SOS response, publishing
      slots — see require_approved_doctor) until a government reviewer
      approves them. Every test using doctor_token / this helper predates
      that gate and expects an immediately-usable doctor, so this
      auto-approves right after registration. Tests that specifically
      exercise the approval workflow itself (pending/approve/reject) should
      NOT go through this helper for that part — they register normally
      and drive the real /doctors/pending, /doctors/{id}/approve,
      /doctors/{id}/reject endpoints instead.
    - Every non-PATIENT role now must verify its email before /auth/login
      succeeds (see login() in modules/auth/router.py). Real registration
      sends a token by email, which tests can't click through, so this
      flips is_verified on directly after registration — the same kind of
      test-only bypass as the DOCTOR auto-approve above, not a bypass in
      the app itself. DOCTOR/HOSPITAL additionally require a verified
      phone at registration time; a `phone` kwarg lets a test supply one,
      and this seeds a matching already-used PhoneOTP row so the real
      registration endpoint's check passes without going through SMS.
    """
    from database import SessionLocal

    if role == "ADMIN":
        session = SessionLocal()
        try:
            if not session.query(models.User).filter(models.User.username == username).first():
                from modules.auth.utils import get_password_hash
                session.add(models.User(
                    username=username,
                    email=email or f"{username}@test.gramcare.in",
                    hashed_password=get_password_hash("strongpass123"),
                    full_name=username.title(),
                    role="ADMIN",
                    is_verified=True,
                ))
                session.commit()
        finally:
            session.close()
    else:
        payload = {
            "username": username,
            "email": email or f"{username}@test.gramcare.in",
            "password": "strongpass123",
            "full_name": username.title(),
            "role": role,
        }
        if role in ("DOCTOR", "HOSPITAL"):
            from datetime import datetime, timezone, timedelta
            test_phone = phone or f"+91900000{abs(hash(username)) % 10000:04d}"
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
            payload["phone"] = test_phone

        # Deliberately NOT asserting this succeeded: several call sites
        # (e.g. test_phase4_booking.py's _setup_doctor_with_slot) call this
        # helper multiple times with the same username across different
        # test functions, relying on "already registered" (400) being a
        # harmless no-op that falls through to reusing the existing account
        # below — that register-or-reuse idempotency predates this
        # verification/phone logic and must keep working. Only a genuinely
        # unexpected failure (e.g. the phone-verification check itself
        # rejecting the seeded PhoneOTP) should surface, which the register
        # response no longer being trustworthy here doesn't hide — the
        # subsequent login assert below still fails loudly if the account
        # never ended up in a usable state.
        client.post("/api/v1/auth/register", json=payload)

        session = SessionLocal()
        try:
            user = session.query(models.User).filter(models.User.username == username).first()
            if user:
                user.is_verified = True
                if role == "DOCTOR":
                    profile = (
                        session.query(models.DoctorProfile)
                        .filter(models.DoctorProfile.user_id == user.id)
                        .first()
                    )
                    if not profile:
                        profile = models.DoctorProfile(user_id=user.id)
                        session.add(profile)
                    profile.verification_status = "APPROVED"
                session.commit()
        finally:
            session.close()

    res = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "strongpass123"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="session")
def patient_token(client):
    return _register_and_login(client, "t_patient", "PATIENT")


@pytest.fixture(scope="session")
def doctor_token(client):
    return _register_and_login(client, "t_doctor", "DOCTOR")


@pytest.fixture(scope="session")
def pharmacist_token(client):
    return _register_and_login(client, "t_pharma", "PHARMACIST")


def auth(token):
    return {"Authorization": f"Bearer {token}"}
