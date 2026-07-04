from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# ==========================================
# User Auth Schemas
# ==========================================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: str = Field(..., pattern="^(PATIENT|DOCTOR|PHARMACIST|HOSPITAL|ADMIN)$")

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
    full_name: str = Field(..., min_length=1, max_length=100)
    relation: str = Field(..., min_length=1, max_length=50)
    age: int = Field(..., ge=0, le=150)
    gender: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    photo_url: Optional[str] = None
    color_tag: Optional[str] = None

class FamilyProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    relation: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    photo_url: Optional[str] = None
    color_tag: Optional[str] = None

class FamilyProfileResponse(FamilyProfileCreate):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

# ==========================================
# Doctor Directory Schemas
# ==========================================
class DoctorProfileUpdate(BaseModel):
    specialty: Optional[str] = None
    qualifications: Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0, le=80)
    consultation_fee: Optional[float] = Field(None, ge=0)
    bio: Optional[str] = None
    languages: Optional[str] = None
    is_available: Optional[bool] = None

class DoctorPublic(BaseModel):
    """What patients see when choosing a doctor (planning doc: specialty,
    experience, fee must be visible before booking)."""
    id: int                      # user id (used for booking)
    full_name: str
    specialty: str
    qualifications: Optional[str] = None
    experience_years: int
    consultation_fee: float
    languages: Optional[str] = None
    is_available: bool

class SlotCreate(BaseModel):
    start_time: datetime
    end_time: datetime

class SlotResponse(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    is_booked: bool

    model_config = {"from_attributes": True}

# ==========================================
# Appointment Schemas
# ==========================================
class AppointmentCreate(BaseModel):
    doctor_id: int
    slot_id: Optional[int] = None            # book against a published slot
    scheduled_at: Optional[datetime] = None  # legacy free-time path (used when doctor has no slots)
    triage_summary: Optional[str] = None
    family_profile_id: Optional[int] = None
    # The verified payment order that authorizes this booking. Optional only
    # for free consultations (fee == 0).
    payment_order_id: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(PENDING|CONFIRMED|COMPLETED|CANCELLED)$")
    consultation_notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    family_profile_id: Optional[int] = None
    doctor_id: int
    scheduled_at: datetime
    status: str
    triage_summary: Optional[str]
    consultation_notes: Optional[str]
    payment_id: Optional[int] = None
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
    family_profile_id: Optional[int] = None
    medicines: List[MedicineItem]
    dosage_instructions: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None

class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: Optional[int]
    patient_id: int
    family_profile_id: Optional[int] = None
    doctor_id: int
    medicines: List[Dict[str, Any]]
    dosage_instructions: Optional[str]
    diagnosis: Optional[str]
    notes: Optional[str]
    is_fulfilled: bool
    created_at: datetime

    model_config = {"from_attributes": True}

# ==========================================
# EHR / Health Wallet Schemas
# ==========================================
class EHRRecordCreate(BaseModel):
    """A record created by the patient themself (e.g. OCR-scanned outside
    prescription or lab report)."""
    record_type: str = Field(..., pattern="^(prescription|lab_report|triage_log|vaccination|scan|note)$")
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    payload: Optional[Dict[str, Any]] = None
    doctor_name: Optional[str] = None
    family_profile_id: Optional[int] = None
    client_uuid: Optional[str] = None
    record_date: Optional[datetime] = None

class EHRRecordResponse(BaseModel):
    id: int
    patient_id: int
    family_profile_id: Optional[int] = None
    record_type: str
    title: Optional[str] = None
    content: str
    payload: Optional[Dict[str, Any]] = None
    doctor_name: Optional[str] = None
    client_uuid: Optional[str] = None
    record_date: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class EHRSyncItem(EHRRecordCreate):
    """One offline-queued record in a sync batch. client_uuid is REQUIRED
    here — it is what makes the sync idempotent."""
    client_uuid: str = Field(..., min_length=8, max_length=64)

class EHRSyncRequest(BaseModel):
    records: List[EHRSyncItem] = Field(..., max_length=100)

class EHRSyncResult(BaseModel):
    synced: List[str]      # client_uuids newly stored
    duplicates: List[str]  # client_uuids already present (safe no-ops)

# ==========================================
# Payment Schemas
# ==========================================
class PaymentResponse(BaseModel):
    id: int
    order_id: str
    patient_id: int
    amount: float
    currency: str
    status: str
    gateway: str
    created_at: datetime

    model_config = {"from_attributes": True}

# ==========================================
# Pharmacy Schemas
# ==========================================
class PharmacyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    address: Optional[str] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    phone: Optional[str] = None

class PharmacyResponse(PharmacyCreate):
    id: int
    owner_user_id: int
    is_active: bool

    model_config = {"from_attributes": True}

class PharmacyItemCreate(BaseModel):
    medicine_name: str = Field(..., min_length=1, max_length=120)
    generic_group: Optional[str] = None
    stock_count: int = Field(0, ge=0)
    price: float = Field(0.0, ge=0)
    requires_prescription: bool = False
    expiry_date: Optional[date] = None
    batch_number: Optional[str] = None

class PharmacyItemResponse(PharmacyItemCreate):
    id: int
    pharmacy_id: Optional[int] = None
    status: str = "Optimal"

    model_config = {"from_attributes": True}

class NearbyPharmacyResult(BaseModel):
    pharmacy_id: int
    pharmacy_name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    distance_km: Optional[float] = None
    available: bool                      # green/red indicator (planning doc)
    medicine_name: Optional[str] = None
    price: Optional[float] = None
    substitutes: List[str] = []          # generic substitutes when unavailable

# ==========================================
# Emergency SOS Schemas
# ==========================================
class EmergencySOSCreate(BaseModel):
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_text: Optional[str] = None
    voice_note: Optional[str] = Field(None, max_length=2000)
    severity: str = "CRITICAL"
    family_profile_id: Optional[int] = None

class EmergencySOSUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|RESPONDED|RESOLVED)$")

class EmergencySOSResponse(EmergencySOSCreate):
    id: int
    patient_id: int
    status: str
    responded_by: Optional[int]
    escalation_level: Optional[int] = 0
    assigned_hospital_id: Optional[int] = None
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}

class EmergencyContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20)
    relation: Optional[str] = None

class EmergencyContactResponse(EmergencyContactCreate):
    id: int
    user_id: int

    model_config = {"from_attributes": True}

# ==========================================
# Triage Log Schemas
# ==========================================
class TriageLogCreate(BaseModel):
    patient_id: Optional[int] = None
    family_profile_id: Optional[int] = None
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
