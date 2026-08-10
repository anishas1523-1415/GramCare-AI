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
    # ADMIN deliberately excluded — previously any unauthenticated caller
    # could self-register as ADMIN via this endpoint (real vulnerability,
    # closed here). The only path to an ADMIN account is now
    # POST /auth/register/government, gated by AuthorizedGovernmentEmail.
    # CHW is included here (unlike ADMIN) so the endpoint can create one via
    # direct API access — the web portal's registration role-picker simply
    # never offers it as an option, the same "separate portal / admin-created
    # account" convention already used for PHARMACIST/LAB.
    role: str = Field(..., pattern="^(PATIENT|DOCTOR|PHARMACIST|HOSPITAL|LAB|CHW)$")
    # Required for DOCTOR/HOSPITAL (checked in the router, since Pydantic
    # can't cleanly express "required only when role=X"), optional for the
    # rest. Must match a phone that completed POST /auth/phone/verify-otp
    # in the last 15 minutes.
    phone: Optional[str] = None

class VerifyEmailRequest(BaseModel):
    token: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class PhoneSendOTPRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=15)

class PhoneVerifyOTPRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=15)
    otp: str = Field(..., min_length=4, max_length=8)

class PhoneUpdate(BaseModel):
    phone: str = Field(..., min_length=8, max_length=15)

class GovernmentRegisterCreate(BaseModel):
    """Government Portal registration — the caller's email must already be
    present in AuthorizedGovernmentEmail (pre-provisioned, no self-serve
    application flow)."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str

class GovernmentWhitelistEntryCreate(BaseModel):
    """ADMIN-only: pre-authorize an email for /auth/register/government.
    Previously the ONLY way to add an entry was the GOVERNMENT_WHITELIST_EMAILS
    env var read once at process startup — this is the admin-UI equivalent,
    for adding entries without a Render redeploy."""
    email: EmailStr
    note: Optional[str] = Field(None, max_length=200)

class GovernmentWhitelistEntryResponse(BaseModel):
    id: int
    email: str
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    phone: Optional[str] = None
    phone_verified: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    role: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

class UserSessionResponse(BaseModel):
    """One row of GET /auth/sessions — lets a user see and revoke their own
    logged-in devices without needing that device's refresh token (the only
    way /auth/logout could revoke a session before this existed)."""
    id: int
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class FCMTokenRegistration(BaseModel):
    fcm_token: str = Field(..., min_length=1)
    device_id: Optional[str] = None
    platform: str = Field(..., pattern="^(android|ios|web)$")

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
    """Self-editable fields. verification_status/rejection_reason/
    reviewed_by/reviewed_at are deliberately absent — only the government
    approve/reject endpoints (modules/doctors/router.py) may change those."""
    specialty: Optional[str] = None
    qualifications: Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0, le=80)
    consultation_fee: Optional[float] = Field(None, ge=0)
    bio: Optional[str] = None
    languages: Optional[str] = None
    is_available: Optional[bool] = None
    photo_url: Optional[str] = None
    license_number: Optional[str] = Field(None, max_length=80)
    service_hours: Optional[str] = Field(None, max_length=200)

class DoctorPublic(BaseModel):
    """What patients see when choosing a doctor (planning doc: specialty,
    experience, fee must be visible before booking). Only ever populated
    for APPROVED doctors — GET /doctors filters unverified ones out
    entirely, so there's no verification_status field here to leak."""
    id: int                      # user id (used for booking)
    full_name: str
    specialty: str
    qualifications: Optional[str] = None
    experience_years: int
    consultation_fee: float
    bio: Optional[str] = None
    languages: Optional[str] = None
    is_available: bool
    photo_url: Optional[str] = None

class DoctorSelfResponse(DoctorPublic):
    """GET/PUT /doctors/me — the doctor's own view of their profile,
    additionally showing the government verification state that
    DoctorPublic hides from patients."""
    license_number: Optional[str] = None
    license_document_url: Optional[str] = None
    service_hours: Optional[str] = None
    verification_status: str = "PENDING"
    rejection_reason: Optional[str] = None

class DoctorApprovalAction(BaseModel):
    """Government reviewer's rejection reason (approve needs no body)."""
    reason: str = Field(..., min_length=3, max_length=500)

# ==========================================
# Hospital Schemas
# ==========================================
class HospitalCreate(BaseModel):
    """Self-registration for a HOSPITAL-role account (modules/hospital/router.py).
    Data-collection only for now — instant access, no government approval
    gate (unlike DoctorProfile)."""
    name: str = Field(..., min_length=2, max_length=150)
    address: Optional[str] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    phone: Optional[str] = None
    established_year: Optional[int] = Field(None, ge=1800, le=2100)
    service_timing: Optional[str] = Field(None, max_length=200)
    specializations: Optional[str] = Field(None, max_length=500)
    license_number: Optional[str] = Field(None, max_length=80)

class HospitalResponse(HospitalCreate):
    id: int
    owner_user_id: Optional[int] = None
    license_document_url: Optional[str] = None
    emergency_desk_user_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}

# ==========================================
# File Upload Schemas (Cloudinary — core/cloudinary_service.py)
# ==========================================
class ImageUploadRequest(BaseModel):
    image_base64: str = Field(..., min_length=10, description="Raw base64 or data-URI encoded image")

class ImageUploadResponse(BaseModel):
    url: str
    public_id: str

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
    triage_severity_score: Optional[int] = Field(None, ge=0, le=100)
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
    triage_severity_score: Optional[int] = None
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

# Medicine Interaction Alerts / Clinical Decision Support (CDS): the shape
# core.drug_interactions.check_interactions() returns per warning. Previously
# this rode along untyped as Dict[str, Any]; now given a real schema so the
# `explanation` field (Explainable AI: the plain-language "why" behind the
# alert, added alongside the pre-existing `description`) is documented and
# validated rather than silently passed through. All fields it always
# returned (drug_a/drug_b/severity/description) are unchanged — only the new
# `explanation` field was added, so no existing caller breaks.
class InteractionWarningSchema(BaseModel):
    drug_a: str
    drug_b: str
    severity: str  # HIGH / MODERATE
    description: str
    explanation: str

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
    # Populated only by POST /ehr/issue_prescription (planning doc: "Medicine
    # Interaction Alerts" — checked against the patient's other active
    # medicines at the moment of issuing). Not a stored column; other
    # read paths (pharmacy queue, wallet) simply omit it.
    interaction_warnings: Optional[List[InteractionWarningSchema]] = None

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
    is_jan_aushadhi: bool = False

class PharmacyResponse(PharmacyCreate):
    id: int
    owner_user_id: int
    is_active: bool

    model_config = {"from_attributes": True}


class BatchRecallCreate(BaseModel):
    medicine_name: str = Field(..., min_length=1, max_length=120)
    batch_number: str = Field(..., min_length=1, max_length=80)
    reason: str = Field(..., min_length=3, max_length=500)
    # Optional scanned official circular, uploaded to Cloudinary and stored
    # as notice_url — never itself persisted (write-only, like file_base64
    # elsewhere).
    notice_base64: Optional[str] = None

class BatchRecallResponse(BaseModel):
    id: int
    medicine_name: str
    batch_number: str
    reason: str
    notice_url: Optional[str] = None
    issued_by_user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MedicinePreorderCreate(BaseModel):
    pharmacy_id: int
    medicine_name: str = Field(..., min_length=1, max_length=120)
    quantity: int = Field(1, ge=1, le=50)

class MedicinePreorderResponse(BaseModel):
    id: int
    patient_id: int
    pharmacy_id: int
    medicine_name: str
    quantity: int
    status: str
    created_at: datetime
    fulfilled_at: Optional[datetime] = None

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
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_jan_aushadhi: bool = False        # government low-cost pharmacy badge

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

# ==========================================
# Laboratory Schemas
# ==========================================
class LabCenterCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    address: Optional[str] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    phone: Optional[str] = None
    offers_home_collection: bool = True

class LabCenterResponse(LabCenterCreate):
    id: int
    owner_user_id: int
    is_active: bool

    model_config = {"from_attributes": True}

class LabTestInfo(BaseModel):
    """A catalog entry from the curated test-reference table (core/lab_tests.py)
    — name plus patient-facing prep instructions (planning doc: "Pre-test
    preparation instructions e.g. fasting requirements")."""
    name: str
    category: str
    prep_instructions: str
    typical_turnaround_hours: int
    sample_type: str

class LabBookingCreate(BaseModel):
    lab_center_id: int
    test_name: str = Field(..., min_length=2, max_length=120)
    family_profile_id: Optional[int] = None
    home_collection: bool = False
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None

class LabResultValue(BaseModel):
    parameter: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None  # NORMAL / LOW / HIGH — pharmacist/lab-entered

class LabReportSubmit(BaseModel):
    values: List[LabResultValue] = []
    summary: Optional[str] = None
    # Either pass an already-hosted URL directly, or a base64 scan/PDF to be
    # uploaded to Cloudinary server-side (core/cloudinary_service.py) — the
    # latter takes precedence if both are supplied.
    file_url: Optional[str] = None
    file_base64: Optional[str] = None

class LabBookingResponse(BaseModel):
    id: int
    patient_id: int
    family_profile_id: Optional[int] = None
    lab_center_id: int
    test_name: str
    home_collection: bool
    scheduled_at: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    report_payload: Optional[Dict[str, Any]] = None
    report_ready_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

# ==========================================
# Digital Health Passport
# ==========================================
class PassportUpdate(BaseModel):
    """A patient's own edit of their emergency-response profile."""
    blood_group: Optional[str] = Field(None, max_length=10)
    allergies: Optional[str] = Field(None, max_length=1000)
    chronic_conditions: Optional[str] = Field(None, max_length=1000)

class PassportSelfResponse(BaseModel):
    """What the owning patient sees on their own /passport page —
    includes the token so the client can build the shareable QR/URL."""
    full_name: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    passport_token: Optional[str] = None

class PassportMedicine(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None

class PassportEmergencyContact(BaseModel):
    name: str
    phone: str
    relation: Optional[str] = None

class PassportPublicResponse(BaseModel):
    """What GET /passport/{token} returns — no auth, meant to be read by
    whoever scans the QR code (EMT, hospital desk). Deliberately minimal:
    no email, username, address, or anything beyond what's useful in an
    emergency."""
    full_name: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    emergency_contacts: List[PassportEmergencyContact] = []
    recent_medicines: List[PassportMedicine] = []

# ==========================================
# Preventive AI Schemas
# ==========================================
class PreventiveReminder(BaseModel):
    """One rule-based screening/vaccination reminder — see
    core/preventive_rules.py. Not an ML prediction: `reason` is a static
    explanation template, `due` is a deterministic date/keyword check."""
    key: str
    title: str
    category: str  # "screening" | "vaccination"
    reason: str
    due: bool
    last_done_date: Optional[str] = None
    suggested_action: str  # "lab_test" -> /lab-tests | "consultation" -> /book

# ==========================================
# AI Care Navigator
# ==========================================
class NavigatorItem(BaseModel):
    """One prioritized "what to do next" item surfaced to a patient, with
    explainability (`reason`) and a suggested action the frontend can render
    as a button/link (`cta_label` + `cta_route`). `category` identifies which
    signal produced the item (sos/lab/appointment/prescription/preventive/
    all_clear) so clients can key icons/analytics off it without parsing
    `reason` text."""
    category: str
    priority: str = Field(..., pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$")
    title: str
    reason: str
    cta_label: Optional[str] = None
    cta_route: Optional[str] = None

# ==========================================
# Referral Network
# ==========================================
class ReferralCreate(BaseModel):
    """A doctor's referral of a patient, either to a specific colleague
    (referred_to_doctor_id set) or open to any doctor of `specialty`
    (referred_to_doctor_id omitted). Exactly one of patient_id /
    family_profile_id identifies who the referral is about — when
    family_profile_id is given, the patient is derived from the profile's
    owning account rather than trusted from the client."""
    patient_id: Optional[int] = None
    family_profile_id: Optional[int] = None
    referred_to_doctor_id: Optional[int] = None
    specialty: str = Field(..., min_length=2, max_length=120)
    reason: str = Field(..., min_length=2, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)

class ReferralResponse(BaseModel):
    id: int
    patient_id: int
    family_profile_id: Optional[int] = None
    referring_doctor_id: int
    referred_to_doctor_id: Optional[int] = None
    specialty: str
    reason: str
    notes: Optional[str] = None
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

# ==========================================
# Community Health Worker (CHW) Schemas
# ==========================================
class CHWPatientRegister(BaseModel):
    """A CHW registering a walk-in villager who may have no phone, email,
    or literacy to self-register. Age/gender/address are collected for
    context (and written to the audit trail) but — unlike FamilyProfile —
    are not stored as queryable columns on the new User account; nothing in
    the rest of the platform reads a patient's age off their account, it is
    always supplied fresh per-request (see TriageRequest.age), the same
    contract this preserves for CHW-assisted patients."""
    full_name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., min_length=1, max_length=20)
    phone: Optional[str] = Field(None, min_length=8, max_length=15)
    address_note: Optional[str] = Field(None, max_length=500)

class CHWPatientRegisterResponse(BaseModel):
    """Returned once, immediately after registration — this is the CHW's
    only chance to see the temporary password in plaintext (it is hashed
    before storage, same as any other account)."""
    id: int
    username: str
    temporary_password: str
    full_name: str
    role: str = "PATIENT"
    message: str = (
        "Write down these credentials for the patient, or continue managing "
        "their care yourself from 'My Registered Patients' below."
    )

class CHWPatientSummary(BaseModel):
    """One row of GET /chw/my-patients."""
    id: int
    username: str
    full_name: str
    phone: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class CHWTriageRequest(BaseModel):
    """Body for POST /chw/patients/{patient_id}/triage — patient_id itself
    comes from the path (and is ownership-checked against the caller), so
    unlike the public TriageRequest this carries no patient_id field."""
    symptoms_text: str = Field(..., min_length=3, max_length=2000)
    age: int = Field(..., ge=0, le=150)
    family_profile_id: Optional[int] = None
    image_base64: Optional[str] = None
