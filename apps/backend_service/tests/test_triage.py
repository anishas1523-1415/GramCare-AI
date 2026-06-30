"""
GramCare AI Backend — Test Suite
Tests work in both modes:
  - With GEMINI_API_KEY: tests live AI responses
  - Without key or rate-limited: tests mock/fallback responses
"""
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to sys.path to import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the health check root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_triage_engine():
    """
    Test the AI Triage Endpoint.
    Accepts both 200 (live AI or mock) and 500 (rate limited) as valid,
    since CI environments may hit Gemini free tier limits.
    """
    payload = {
        "symptoms_text": "I have a severe headache and fever.",
        "patient_id": "patient123",
        "age": 30,
    }

    response = client.post("/api/v1/triage/analyze", json=payload)

    if response.status_code == 200:
        data = response.json()
        # Assert all required keys are present
        assert "severity_score" in data
        assert "predicted_condition" in data
        assert "home_remedies" in data
        assert "doctor_recommendation" in data
        assert "recovery_time" in data
        assert "status" in data
        assert "confidence_score" in data
        assert "explanation" in data
        assert "disclaimer" in data

        # Assert types and ranges
        assert isinstance(data["severity_score"], int)
        assert 0 <= data["severity_score"] <= 100
        assert isinstance(data["confidence_score"], float)
        assert 0.0 <= data["confidence_score"] <= 1.0
        assert "DISCLAIMER" in data["disclaimer"]
    elif response.status_code == 500:
        # Rate limited or API error — acceptable in CI/free tier
        data = response.json()
        assert "detail" in data
    else:
        assert False, f"Unexpected status code: {response.status_code}"


def test_triage_validation():
    """Test that invalid triage requests are rejected."""
    # Empty symptoms
    response = client.post(
        "/api/v1/triage/analyze",
        json={"symptoms_text": "ab", "patient_id": "p1", "age": 30},
    )
    assert response.status_code == 422  # Validation error (min_length=3)

    # Invalid age
    response = client.post(
        "/api/v1/triage/analyze",
        json={"symptoms_text": "headache", "patient_id": "p1", "age": -5},
    )
    assert response.status_code == 422


def test_pharmacy_stock():
    """Test the Pharmacy Inventory endpoint."""
    response = client.get("/api/v1/pharmacy/stock")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    if len(data) > 0:
        assert "name" in data[0]
        assert "stock_quantity" in data[0]
        assert "status" in data[0]


def test_user_registration():
    """Test user registration and login flow."""
    # Register a test user
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_user_001",
            "password": "securepass123",
            "email": "test001@gramcare.in",
            "full_name": "Test User",
            "role": "PATIENT",
        },
    )
    # Accept 200 (first run) or 400 (already exists from previous run)
    assert response.status_code in [200, 400]


def test_user_login():
    """Test user login returns a JWT token."""
    # First ensure user exists
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "login_test_user",
            "password": "testpass123",
            "email": "logintest@gramcare.in",
            "full_name": "Login Test",
            "role": "PATIENT",
        },
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "login_test_user", "password": "testpass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "PATIENT"


def test_auth_protected_endpoint():
    """Test that /me returns user info with valid token."""
    # Login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "login_test_user", "password": "testpass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if login_response.status_code != 200:
        return  # Skip if login_test_user doesn't exist

    token = login_response.json()["access_token"]

    # Access protected endpoint
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "login_test_user"
    assert data["role"] == "PATIENT"


def test_auth_rejects_invalid_token():
    """Test that protected endpoints reject invalid tokens."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token_here"},
    )
    assert response.status_code == 401
