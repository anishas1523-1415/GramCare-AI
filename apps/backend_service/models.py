from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text, JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


def _utcnow():
    """Return timezone-aware UTC datetime (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String)  # 'PATIENT', 'DOCTOR', 'PHARMACIST', 'HOSPITAL', 'ADMIN'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    family_profiles = relationship("FamilyProfile", back_populates="user")
    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False)
    pharmacy = relationship("Pharmacy", back_populates="owner", uselist=False)
    appointments_as_patient = relationship("Appointment", foreign_keys="[Appointment.patient_id]", back_populates="patient")
    appointments_as_doctor = relationship("Appointment", foreign_keys="[Appointment.doctor_id]", back_populates="doctor")


class FamilyProfile(Base):
    __tablename__ = "family_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    full_name = Column(String)
    relation = Column(String)
    age = Column(Integer)
    gender = Column(String)
    blood_group = Column(String, nullable=True)
    allergies = Column(Text, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    # Optional photo used as the profile's "button" for low-literacy users
    # (planning doc: "அவங்களுடைய போட்டோவையே ஒரு பட்டனா"). Stored as a client
    # asset path / URL, not a blob.
    photo_url = Column(String, nullable=True)
    # Accent color used for the profile chip in clients (accessibility aid).
    color_tag = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="family_profiles")


class DoctorProfile(Base):
    """Public-facing professional profile for a DOCTOR user.

    Required by the planning doc's booking flow: patients must see specialty,
    experience and consultation fee before choosing a doctor. The absence of
    this entity was why the web portal hardcoded DOCTOR_ID = 2.
    """
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    specialty = Column(String, default="General Medicine", index=True)
    qualifications = Column(String, nullable=True)
    experience_years = Column(Integer, default=0)
    consultation_fee = Column(Float, default=150.0)  # INR
    bio = Column(Text, nullable=True)
    languages = Column(String, nullable=True)  # comma-separated, e.g. "Tamil,English"
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="doctor_profile")
    slots = relationship("AvailabilitySlot", back_populates="doctor_profile")


class AvailabilitySlot(Base):
    """A bookable consultation window published by a doctor.

    Planning doc: "டாக்டர்கள் தங்களுடைய கால அட்டவணையை ஆப்ல அப்டேட் பண்ணி
    வச்சிருப்பாங்க. அந்த நேரத்துலதான் யூசர்ஸ் அப்பாயின்ட்மென்ட் புக் செய்ய
    முடியும்." — bookings must happen against published availability, not
    arbitrary datetimes.
    """
    __tablename__ = "availability_slots"
    __table_args__ = (
        # A doctor cannot publish two slots starting at the same instant —
        # also the guard used to prevent double-booking races.
        UniqueConstraint("doctor_profile_id", "start_time", name="uq_slot_doctor_start"),
    )

    id = Column(Integer, primary_key=True, index=True)
    doctor_profile_id = Column(Integer, ForeignKey("doctor_profiles.id"), index=True)
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime)
    is_booked = Column(Boolean, default=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    doctor_profile = relationship("DoctorProfile", back_populates="slots")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    # The specific family member this consultation is for (nullable = the
    # account owner themself). Planning doc: every feature is scoped to the
    # selected family-member "box".
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), index=True)
    scheduled_at = Column(DateTime)
    status = Column(String, default="PENDING")  # PENDING/CONFIRMED/COMPLETED/CANCELLED
    triage_summary = Column(Text, nullable=True)
    consultation_notes = Column(Text, nullable=True)
    # Server-side link to the verified payment that authorized this booking
    # (planning doc: fee must be paid BEFORE the call; refund if unattended).
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    patient = relationship("User", foreign_keys=[patient_id], back_populates="appointments_as_patient")
    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="appointments_as_doctor")
    prescriptions = relationship("Prescription", back_populates="appointment")
    payment = relationship("Payment", foreign_keys=[payment_id])


class Payment(Base):
    """Payment state machine backing consultation bookings.

    CREATED  -> order created with the gateway (or mock), nothing charged yet
    PAID     -> signature verified; funds captured (held on our ledger)
    CONSUMED -> a booking was created against this payment
    REFUNDED -> doctor no-show / cancellation refund issued
    FAILED   -> verification failed

    This is the pragmatic implementation of the escrow discussion in the
    planning doc: money is only "released" (CONSUMED) when the consultation
    is actually booked/held, and is refundable until then or on no-show.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount = Column(Float)  # INR rupees
    currency = Column(String, default="INR")
    status = Column(String, default="CREATED", index=True)
    gateway = Column(String, default="mock")  # 'razorpay' | 'mock'
    gateway_payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True)
    doctor_id = Column(Integer, ForeignKey("users.id"))
    medicines = Column(JSON)  # list of {name, dosage, frequency, duration}
    dosage_instructions = Column(Text, nullable=True)
    diagnosis = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_fulfilled = Column(Boolean, default=False)
    fulfilled_by_pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    appointment = relationship("Appointment", back_populates="prescriptions")


class EmergencySOS(Base):
    __tablename__ = "emergency_sos"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    location_text = Column(String, nullable=True)
    severity = Column(String, default="CRITICAL")
    status = Column(String, default="ACTIVE")  # ACTIVE/RESPONDED/RESOLVED
    responded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)


class TriageLog(Base):
    """Every AI triage analysis, persisted.

    This is the data backbone for the AI Doctor Assistant (pre-consult
    summaries) and Community Health Intelligence (regional symptom
    clustering) described in the planning doc. Previously the model existed
    but /triage/analyze never wrote to it, discarding every analysis.
    """
    __tablename__ = "triage_logs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = guest
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True)
    symptoms_text = Column(Text)
    ai_severity_score = Column(Integer)
    ai_predicted_condition = Column(String)
    ai_confidence = Column(Float)
    ai_explanation = Column(Text)
    language_detected = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class EHRRecord(Base):
    """A single entry in a patient's Family Health Wallet.

    Redesigned from the legacy shape (string patient_id, one unstructured
    content blob): patient_id is now a real integer FK, records are scoped to
    an optional family member, carry a structured JSON payload alongside the
    human-readable content, and have a client-generated UUID enabling
    idempotent offline sync (planning doc: offline-first with cloud sync).
    """
    __tablename__ = "ehr_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True, index=True)
    record_type = Column(String, index=True)  # 'prescription' | 'lab_report' | 'triage_log' | 'vaccination' | 'scan' | 'note'
    title = Column(String, nullable=True)
    content = Column(Text)                    # human-readable summary (also used for voice playback)
    payload = Column(JSON, nullable=True)     # structured data (e.g. parsed medicines)
    doctor_name = Column(String, nullable=True)
    # Client-generated UUID for offline-created records. Unique so the sync
    # endpoint is idempotent: re-sending the same queued record can never
    # create a duplicate.
    client_uuid = Column(String, unique=True, nullable=True, index=True)
    record_date = Column(DateTime, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)


class Pharmacy(Base):
    """A registered pharmacy (shop) with a geolocation.

    Required by the planning doc's nearby-medicine search: "பக்கத்துல இருக்கற
    எந்த பார்மசியில அந்த மருந்து இருக்குன்னு காட்டும்". Previously inventory
    rows carried only a free-string pharmacy tag with no location, making
    geo search structurally impossible.
    """
    __tablename__ = "pharmacies"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    name = Column(String)
    address = Column(String, nullable=True)
    lat = Column(Float, nullable=True, index=True)
    lng = Column(Float, nullable=True, index=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    owner = relationship("User", back_populates="pharmacy")
    items = relationship("PharmacyItem", back_populates="pharmacy")


class PharmacyItem(Base):
    __tablename__ = "pharmacy_inventory"

    id = Column(Integer, primary_key=True, index=True)
    pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"), nullable=True, index=True)
    medicine_name = Column(String, index=True)
    # Medicines in the same generic_group are therapeutically interchangeable
    # — backs the planning doc's "Generic Substitutes" feature.
    generic_group = Column(String, nullable=True, index=True)
    stock_count = Column(Integer, default=0)
    price = Column(Float, default=0.0)
    requires_prescription = Column(Boolean, default=False)
    expiry_date = Column(Date, nullable=True)   # backs "Expiry Alerts"
    batch_number = Column(String, nullable=True)  # backs "Batch Recall Alerts" (V2)
    last_updated = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    pharmacy = relationship("Pharmacy", back_populates="items")


class Hospital(Base):
    """A hospital with an emergency desk, for SOS routing/escalation.

    Planning doc: SOS alerts go to the hospital's central emergency desk
    (not individual doctors), with escalation to the next-nearest hospital
    if unacknowledged.
    """
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    address = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    phone = Column(String, nullable=True)
    emergency_desk_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    created_at = Column(DateTime, default=_utcnow)


class IoTVitals(Base):
    __tablename__ = "iot_vitals"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True)
    device_id = Column(String)
    heart_rate = Column(Integer)
    spo2 = Column(Integer)
    temperature = Column(Float)
    timestamp = Column(DateTime, default=_utcnow)
