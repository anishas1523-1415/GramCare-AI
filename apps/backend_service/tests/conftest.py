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
