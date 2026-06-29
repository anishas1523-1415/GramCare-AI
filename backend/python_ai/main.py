import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="GramCare AI Engine", version="1.0.0")

# Enable CORS for all frontend apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini SDK
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')
else:
    model = None

class TriageResponse(BaseModel):
    severity: str
    department: str
    recommendation: str
    home_remedies: list[str]

@app.post("/api/triage", response_model=TriageResponse)
async def triage_symptoms(
    symptoms: str = Form(...),
    image: Optional[UploadFile] = File(None)
):
    if not model:
        # Fallback Mock Response for development without API key
        return TriageResponse(
            severity="MODERATE",
            department="General Medicine",
            recommendation="Please consult a doctor soon based on the described symptoms.",
            home_remedies=["Rest", "Drink plenty of fluids"]
        )

    prompt = f"""
    You are an expert AI medical assistant for the GramCare AI platform, designed to help rural patients.
    Analyze the following symptoms and provide a triage assessment.
    
    Symptoms: {symptoms}
    
    Respond in JSON format exactly like this, and do not include any other text:
    {{
        "severity": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
        "department": "Name of the medical department to visit (e.g. Cardiology, General Medicine)",
        "recommendation": "A clear, simple recommendation for the patient",
        "home_remedies": ["remedy 1", "remedy 2"]
    }}
    """
    
    try:
        # If there's an image, we can pass it to Gemini, but for MVP we process text.
        response = model.generate_content(prompt)
        # In a production scenario, we'd parse the JSON properly. 
        # For this prototype, we'll extract the JSON.
        import json
        import re
        
        response_text = response.text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            data = json.loads(json_match.group(0))
            return TriageResponse(**data)
        else:
            raise HTTPException(status_code=500, detail="Failed to parse AI response")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy", "ai_ready": model is not None}
