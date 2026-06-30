from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
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
    role = Column(String) # 'PATIENT', 'DOCTOR', 'PHARMACIST', 'ADMIN'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    
    # Relationships
    family_profiles = relationship("FamilyProfile", back_populates="user")
    appointments_as_patient = relationship("Appointment", foreign_keys="[Appointment.patient_id]", back_populates="patient")
    appointments_as_doctor = relationship("Appointment", foreign_keys="[Appointment.doctor_id]", back_populates="doctor")

class FamilyProfile(Base):
    __tablename__ = "family_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    full_name = Column(String)
    relation = Column(String)
    age = Column(Integer)
    gender = Column(String)
    blood_group = Column(String, nullable=True)
    allergies = Column(Text, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    
    user = relationship("User", back_populates="family_profiles")

class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"))
    scheduled_at = Column(DateTime)
    status = Column(String, default="PENDING") # PENDING/CONFIRMED/COMPLETED/CANCELLED
    triage_summary = Column(Text, nullable=True)
    consultation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    
    patient = relationship("User", foreign_keys=[patient_id], back_populates="appointments_as_patient")
    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="appointments_as_doctor")
    prescriptions = relationship("Prescription", back_populates="appointment")

class Prescription(Base):
    __tablename__ = "prescriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("users.id")) # Keep direct reference for easy lookup
    doctor_id = Column(Integer, ForeignKey("users.id"))
    medicines = Column(JSON) # Store list of dicts for medicines
    dosage_instructions = Column(Text, nullable=True)
    diagnosis = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_fulfilled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    
    appointment = relationship("Appointment", back_populates="prescriptions")

class EmergencySOS(Base):
    __tablename__ = "emergency_sos"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    location_text = Column(String, nullable=True)
    severity = Column(String, default="CRITICAL")
    status = Column(String, default="ACTIVE") # ACTIVE/RESPONDED/RESOLVED
    responded_by = Column(Integer, ForeignKey("users.id"), nullable=True) # Doctor ID
    created_at = Column(DateTime, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)

class TriageLog(Base):
    __tablename__ = "triage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Optional, can be GUEST
    symptoms_text = Column(Text)
    ai_severity_score = Column(Integer)
    ai_predicted_condition = Column(String)
    ai_confidence = Column(Float)
    ai_explanation = Column(Text)
    language_detected = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

class EHRRecord(Base):
    __tablename__ = "ehr_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True) # using String to match legacy code, maybe change to Integer if possible, but keep string for compatibility if it's external ID
    record_type = Column(String) # e.g., 'prescription', 'lab_report'
    content = Column(String)
    doctor_name = Column(String)
    created_at = Column(DateTime, default=_utcnow)

class PharmacyItem(Base):
    __tablename__ = "pharmacy_inventory"

    id = Column(Integer, primary_key=True, index=True)
    pharmacy_id = Column(String, index=True)
    medicine_name = Column(String, index=True)
    stock_count = Column(Integer, default=0)
    price = Column(Float, default=0.0)
    requires_prescription = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=_utcnow)

class IoTVitals(Base):
    __tablename__ = "iot_vitals"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    device_id = Column(String)
    heart_rate = Column(Integer)
    spo2 = Column(Integer)
    temperature = Column(Float)
    timestamp = Column(DateTime, default=_utcnow)
