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


def _register_and_login(client, username, role, email=None):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@test.gramcare.in",
            "password": "strongpass123",
            "full_name": username.title(),
            "role": role,
        },
    )
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
