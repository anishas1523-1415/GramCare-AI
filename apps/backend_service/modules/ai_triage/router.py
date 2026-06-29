from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import random

router = APIRouter()

class TriageRequest(BaseModel):
    symptoms_text: str
    patient_id: str
    age: int

class TriageResponse(BaseModel):
    severity_score: int
    predicted_condition: str
    home_remedies: str
    doctor_recommendation: str
    recovery_time: str
    status: str

@router.post("/analyze", response_model=TriageResponse)
async def analyze_symptoms(request: TriageRequest):
    """
    Simulates the AI Triage Engine.
    In production, this would pass request.symptoms_text to a localized HuggingFace / TensorFlow Lite model.
    """
    
    # Mock AI Logic based on keywords
    symptoms = request.symptoms_text.lower()
    
    if "chest pain" in symptoms or "breathing" in symptoms:
        return TriageResponse(
            severity_score=92,
            predicted_condition="Possible Cardiac Event (இதயக் கோளாறு)",
            home_remedies="Do not attempt home remedies. Sit upright and stay calm.",
            doctor_recommendation="URGENT: Proceed to the nearest Hospital immediately.",
            recovery_time="N/A",
            status="Critical"
        )
    elif "fever" in symptoms and "103" in symptoms:
        return TriageResponse(
            severity_score=75,
            predicted_condition="High Viral Fever (கடுமையான காய்ச்சல்)",
            home_remedies="Apply a cool, damp cloth to the forehead. Drink plenty of fluids.",
            doctor_recommendation="Consult a doctor today via Telehealth or in-person.",
            recovery_time="3-5 Days",
            status="Warning"
        )
    else:
        return TriageResponse(
            severity_score=random.randint(15, 35),
            predicted_condition="Minor Infection / Allergy (சிறு ஒவ்வாமை)",
            home_remedies="Wash the area with clean water. Avoid scratching.",
            doctor_recommendation="Visit a local clinic if symptoms persist for 2 days.",
            recovery_time="1-2 Days",
            status="Normal"
        )

class OCRRequest(BaseModel):
    image_base64: str

@router.post("/ocr")
async def extract_prescription_text(request: OCRRequest):
    """
    Extracts text from a prescription image.
    In production, this would use a real OCR library like pytesseract or easyocr.
    """
    import time
    
    # Simulate processing delay
    time.sleep(1.5)
    
    # In a real scenario, we would decode request.image_base64 and pass it to an ML model.
    # We will simulate the extraction of common medicines for the demo.
    
    return {
        "extracted_text": "Rx\nPatient: P1\nDr. Sarah Jenkins\n\n1. Paracetamol 500mg (1-0-1)\n2. Amoxicillin 250mg (1-1-1)\n\nNotes: Take after food.",
        "medicines_parsed": [
            "Paracetamol 500mg (1-0-1)",
            "Amoxicillin 250mg (1-1-1)"
        ],
        "confidence": 0.94
    }
