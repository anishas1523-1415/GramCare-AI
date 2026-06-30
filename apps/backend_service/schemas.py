from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# ==========================================
# User Auth Schemas
# ==========================================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: str = Field(..., pattern="^(PATIENT|DOCTOR|PHARMACIST|ADMIN)$")

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

# ==========================================
# Family Profile Schemas
# ==========================================
class FamilyProfileCreate(BaseModel):
    full_name: str
    relation: str
    age: int = Field(..., ge=0, le=150)
    gender: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None

class FamilyProfileResponse(FamilyProfileCreate):
    id: int
    user_id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}

# ==========================================
# Appointment Schemas
# ==========================================
class AppointmentCreate(BaseModel):
    doctor_id: int
    scheduled_at: datetime
    triage_summary: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(PENDING|CONFIRMED|COMPLETED|CANCELLED)$")
    consultation_notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    scheduled_at: datetime
    status: str
    triage_summary: Optional[str]
    consultation_notes: Optional[str]
    created_at: datetime
    
    model_config = {"from_attributes": True}

# ==========================================
# Prescription Schemas
# ==========================================
class MedicineItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str

class PrescriptionCreate(BaseModel):
    appointment_id: Optional[int] = None
    patient_id: int
    medicines: List[MedicineItem]
    dosage_instructions: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None

class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: Optional[int]
    patient_id: int
    doctor_id: int
    medicines: List[Dict[str, Any]]
    dosage_instructions: Optional[str]
    diagnosis: Optional[str]
    notes: Optional[str]
    is_fulfilled: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}

# ==========================================
# Emergency SOS Schemas
# ==========================================
class EmergencySOSCreate(BaseModel):
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_text: Optional[str] = None
    severity: str = "CRITICAL"

class EmergencySOSUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|RESPONDED|RESOLVED)$")

class EmergencySOSResponse(EmergencySOSCreate):
    id: int
    patient_id: int
    status: str
    responded_by: Optional[int]
    created_at: datetime
    resolved_at: Optional[datetime]
    
    model_config = {"from_attributes": True}

# ==========================================
# Triage Log Schemas
# ==========================================
class TriageLogCreate(BaseModel):
    patient_id: Optional[int] = None
    symptoms_text: str
    ai_severity_score: int
    ai_predicted_condition: str
    ai_confidence: float
    ai_explanation: str
    language_detected: Optional[str] = None

class TriageLogResponse(TriageLogCreate):
    id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}
