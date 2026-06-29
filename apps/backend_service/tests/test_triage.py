from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to sys.path to import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)

def test_triage_engine():
    """
    Test the AI Triage Endpoint to ensure it returns the correct JSON structure.
    Since we might not have a GEMINI_API_KEY in the CI environment, 
    we expect the 'Fallback Mock Response' to trigger, which is perfectly fine for structural testing.
    """
    payload = {
        "symptoms_text": "I have a severe headache and fever.",
        "patient_id": "patient123",
        "age": 30
    }
    
    response = client.post("/api/v1/triage/analyze", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Assert all required keys are present in the response
    assert "severity_score" in data
    assert "predicted_condition" in data
    assert "home_remedies" in data
    assert "doctor_recommendation" in data
    assert "recovery_time" in data
    assert "status" in data
    assert "confidence_score" in data
    assert "explanation" in data
    
    # Assert types
    assert isinstance(data["severity_score"], int)
    assert isinstance(data["confidence_score"], float)

def test_pharmacy_stock():
    """
    Test the Pharmacy Inventory endpoint.
    """
    response = client.get("/api/v1/pharmacy/stock")
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    if len(data) > 0:
        assert "name" in data[0]
        assert "stock_quantity" in data[0]
        assert "status" in data[0]
