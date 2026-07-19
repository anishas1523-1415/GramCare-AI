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
    role = Column(String)  # 'PATIENT', 'DOCTOR', 'PHARMACIST', 'HOSPITAL', 'ADMIN', 'LAB'
    is_active = Column(Boolean, default=True)
    # Every non-PATIENT role (DOCTOR/HOSPITAL/PHARMACIST/LAB/ADMIN) must
    # verify their email before /auth/login succeeds — closes "register
    # under an email you don't own" for every operator-facing account.
    # PATIENT stays ungated deliberately: low-friction access matters more
    # than email verification for rural self-service registration, and a
    # patient account can't approve doctors, dispense medicine, or touch
    # government data. New rows default False; existing rows are backfilled
    # to True by the migration that adds this column so no one already
    # registered gets retroactively locked out.
    is_verified = Column(Boolean, default=False)
    phone = Column(String, nullable=True)
    phone_verified = Column(Boolean, default=False)
    # Digital Health Passport: a minimal emergency-response profile (blood
    # group, allergies, chronic conditions) readable via QR code without
    # logging in — an EMT or hospital desk scanning it has no GramCare
    # account. passport_token is a high-entropy capability token (not the
    # user's id) so the public endpoint can't be enumerated; unset until
    # the patient first fills in their passport.
    blood_group = Column(String, nullable=True)
    allergies = Column(Text, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    passport_token = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    family_profiles = relationship("FamilyProfile", back_populates="user")
    doctor_profile = relationship(
        "DoctorProfile", back_populates="user", uselist=False,
        foreign_keys="[DoctorProfile.user_id]",
    )
    pharmacy = relationship("Pharmacy", back_populates="owner", uselist=False)
    lab_center = relationship("LabCenter", back_populates="owner", uselist=False)
    hospital = relationship(
        "Hospital", back_populates="owner", uselist=False,
        foreign_keys="[Hospital.owner_user_id]",
    )
    appointments_as_patient = relationship("Appointment", foreign_keys="[Appointment.patient_id]", back_populates="patient")
    appointments_as_doctor = relationship("Appointment", foreign_keys="[Appointment.doctor_id]", back_populates="doctor")
    push_tokens = relationship("UserPushToken", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")


class UserPushToken(Base):
    __tablename__ = "user_push_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    device_id = Column(String, nullable=True)
    platform = Column(String)  # 'android', 'ios', 'web'
    # Uniqueness is enforced at the DB level only among ACTIVE rows via a
    # partial unique index (see alembic/versions/8757c24a7b38_add_user_push_tokens.py) —
    # a plain column-level unique=True would reject legitimate cross-account
    # reuse of the same physical device token, since the fcm-token
    # registration endpoint deactivates rather than deletes the previous
    # owner's row.
    fcm_token = Column(String, index=True)
    is_active = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="push_tokens")


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
    # Cloudinary-hosted profile photo, shown in the patient-facing doctor
    # directory (schemas.DoctorPublic) — mirrors FamilyProfile.photo_url.
    photo_url = Column(String, nullable=True)

    # --- Government verification (anti-fake-doctor gate) --------------------
    # A doctor account exists and can log in the moment it's registered, but
    # cannot reach patient-facing actions (appointment queue, prescriptions,
    # SOS response, publishing slots) or appear in the public directory
    # until a government reviewer approves it. See
    # modules.auth.router.require_approved_doctor and
    # modules/doctors/router.py's approve/reject endpoints.
    license_number = Column(String, nullable=True, unique=True, index=True)
    license_document_url = Column(String, nullable=True)  # Cloudinary scan of the license/ID
    service_hours = Column(String, nullable=True)  # free text, e.g. "Mon-Sat 9am-1pm"
    verification_status = Column(String, default="PENDING", index=True)  # PENDING/APPROVED/REJECTED
    rejection_reason = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="doctor_profile", foreign_keys=[user_id])
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
    # AI Symptom Checker severity (0-100), carried over at booking time so
    # the doctor's queue can be risk-sorted without an AI call per
    # appointment (planning doc: "Predictive Risk Stratification" —
    # high-risk patients surfaced to doctor attention first).
    triage_severity_score = Column(Integer, nullable=True)
    consultation_notes = Column(Text, nullable=True)
    # Server-side link to the verified payment that authorized this booking
    # (planning doc: fee must be paid BEFORE the call; refund if unattended).
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    # Set once the pre-appointment SMS reminder has been sent (or attempted
    # with nothing to send to, e.g. no phone on file) so the reminder
    # watchdog never double-sends. NULL = not yet due / not yet attempted.
    reminder_sent_at = Column(DateTime, nullable=True)

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
    # Client-supplied dedup key (e.g. a UUID generated once per "Pay" button
    # press and reused across retries) so a network retry of create-order
    # returns the SAME order instead of minting a second one. Unique only
    # among rows where it's actually set (partial index — see the migration)
    # so NULL (the common case for older/other clients that don't send one)
    # never collides.
    idempotency_key = Column(String, nullable=True, index=True)
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
    # Transcribed voice description of the emergency (planning doc: the user
    # can SAY what happened; the text rides along with the alert).
    voice_note = Column(Text, nullable=True)
    severity = Column(String, default="CRITICAL")
    status = Column(String, default="ACTIVE")  # ACTIVE/RESPONDED/RESOLVED
    responded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Escalation chain (planning doc: if the first hospital doesn't respond,
    # the alert moves to the next-nearest one).
    escalation_level = Column(Integer, default=0)
    assigned_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    # Escalation clock, kept separate so the true creation time is never
    # overwritten (preserves the medical-audit trail).
    last_escalated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class EmergencyContact(Base):
    """Family/neighbour contacts alerted on SOS (planning doc: "எமர்ஜென்சி
    காண்டாக்ட்ஸ்க்கு, அதாவது குடும்பத்தினருக்கு, ஒரு தானியங்கி SMS போகும்").
    The mobile client uses these for the offline SMS fallback."""
    __tablename__ = "emergency_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String)
    phone = Column(String)
    relation = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


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
    # Cloudinary URL of the submitted symptom photo, if any — previously the
    # image was sent to the AI for analysis and then discarded; this keeps it
    # retrievable (e.g. for a doctor to later verify what the AI actually saw).
    image_url = Column(String, nullable=True)
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
    # Jan Aushadhi Kendra flag (planning doc: "ஜன் ஆஷாதி கேந்திராஸ் அப்படின்னு
    # எல்லாருமே இந்த நெட்வொர்க்ல இணையலாம்") — surfaced in search results so
    # patients can prefer low-cost, quality-assured government pharmacies.
    is_jan_aushadhi = Column(Boolean, default=False)
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


class BatchRecall(Base):
    """Batch Recall Alerts (planning doc): "இந்த ப்ரிஸ்கிரிப்ஷன்ல ... அப்புறம்
    வந்து Batch Recall Alerts — கவர்மெண்ட் ஒரு மருந்து பேட்சை ரீகால் பண்ணா,
    பார்மசிஸ்ட்களும் யூசர்களும் உடனே அலர்ட் ஆகணும்." Raised by an ADMIN
    account (regulator/health-authority role) against a medicine name +
    batch number; pharmacists are matched against their own inventory.
    """
    __tablename__ = "batch_recalls"

    id = Column(Integer, primary_key=True, index=True)
    medicine_name = Column(String, index=True)
    batch_number = Column(String, index=True)
    reason = Column(String)
    # Cloudinary URL of a scanned official recall circular/notice, if the
    # issuing authority attaches one (Government Portal).
    notice_url = Column(String, nullable=True)
    issued_by_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)


class MedicinePreorder(Base):
    """Medicine Pre-order (planning doc): "மருந்து இல்லாட்டி பேஷன்ட்ஸ்
    ப்ரீ-ஆர்டர் பண்ணி, ரீஸ்டாக் ஆனதும் வாங்கலாம்." A patient reserves an
    out-of-stock medicine at a specific pharmacy; the pharmacist fulfills it
    once restocked.
    """
    __tablename__ = "medicine_preorders"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"), index=True)
    medicine_name = Column(String)
    quantity = Column(Integer, default=1)
    status = Column(String, default="PENDING")  # PENDING / READY / FULFILLED / CANCELLED
    created_at = Column(DateTime, default=_utcnow)
    fulfilled_at = Column(DateTime, nullable=True)


class Hospital(Base):
    """A hospital with an emergency desk, for SOS routing/escalation.

    Planning doc: SOS alerts go to the hospital's central emergency desk
    (not individual doctors), with escalation to the next-nearest hospital
    if unacknowledged.

    Previously seeded/managed only internally (no HOSPITAL-role user ever
    owned or self-registered one) — owner_user_id + the richer profile
    fields below back the new self-service registration flow
    (modules/hospital/router.py), mirroring Pharmacy/LabCenter's existing
    owner-registers-their-own-record pattern. Data-collection only for now
    (instant access, no government approval gate) — unlike DoctorProfile.
    """
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True, index=True)
    name = Column(String)
    address = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    phone = Column(String, nullable=True)
    established_year = Column(Integer, nullable=True)
    service_timing = Column(String, nullable=True)  # e.g. "24/7" or "Mon-Sat 8am-8pm"
    specializations = Column(String, nullable=True)  # comma-separated departments
    license_number = Column(String, nullable=True)
    license_document_url = Column(String, nullable=True)  # Cloudinary scan
    emergency_desk_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    created_at = Column(DateTime, default=_utcnow)

    owner = relationship("User", back_populates="hospital", foreign_keys=[owner_user_id])


class LabCenter(Base):
    """A diagnostic laboratory (planning doc: "Laboratory ended up being
    split into its own separate standalone web app" — LAB is a role like
    PHARMACIST/HOSPITAL, one center per account, geo-indexed for nearby
    search + home-collection routing).
    """
    __tablename__ = "lab_centers"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    name = Column(String)
    address = Column(String, nullable=True)
    lat = Column(Float, nullable=True, index=True)
    lng = Column(Float, nullable=True, index=True)
    phone = Column(String, nullable=True)
    offers_home_collection = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    owner = relationship("User", back_populates="lab_center")
    bookings = relationship("LabBooking", back_populates="lab_center")


class LabBooking(Base):
    """Lab Test Booking and Reports (planning doc): "யூசர்ஸ் நெருங்கிய
    லேப்களில் அல்லது ஹோம் சாம்பிள் கலெக்ஷன் மூலம் லேப் டெஸ்ட்களை
    பதிவு செய்யலாம் ... ரிப்போர்ட் தயாராக உள்ளது என அறிவிப்பு அனுப்பப்படும்."

    Status lifecycle: BOOKED -> SAMPLE_COLLECTED -> PROCESSING -> REPORT_READY
    (report attached) -> COMPLETED (patient/doctor has viewed it), or
    CANCELLED at any point before SAMPLE_COLLECTED.
    """
    __tablename__ = "lab_bookings"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True)
    lab_center_id = Column(Integer, ForeignKey("lab_centers.id"), index=True)
    test_name = Column(String, index=True)
    home_collection = Column(Boolean, default=False)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String, default="BOOKED", index=True)
    notes = Column(String, nullable=True)
    # Structured report payload once ready: {"values": [{"parameter":..,
    # "value":.., "unit":.., "reference_range":..}], "summary": "...",
    # "file_url": Optional[str]}
    report_payload = Column(JSON, nullable=True)
    report_ready_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    lab_center = relationship("LabCenter", back_populates="bookings")


class IoTVitals(Base):
    __tablename__ = "iot_vitals"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), index=True)
    family_profile_id = Column(Integer, ForeignKey("family_profiles.id"), nullable=True)
    device_id = Column(String)
    heart_rate = Column(Integer)
    spo2 = Column(Integer)
    temperature = Column(Float)
    # Health Vitals Tracker (planning doc): "Steps Tracker, Sleep Analysis
    # (deep sleep vs light sleep breakdown)" — logged alongside HR/SpO2 so
    # doctors can see one combined long-term trend per patient.
    steps = Column(Integer, nullable=True)
    sleep_deep_hours = Column(Float, nullable=True)
    sleep_light_hours = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=_utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    refresh_token = Column(String, unique=True, index=True)
    device_info = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    expires_at = Column(DateTime)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    # Was missing entirely — modules/auth/router.py's reset_password() reads
    # token_entry.user directly, which raised AttributeError on every real
    # (non-enumeration-guarded) password reset attempt. Unidirectional is
    # enough; User doesn't need a back-reference to its reset tokens.
    user = relationship("User")


class EmailVerificationToken(Base):
    """Mirrors PasswordResetToken exactly — same shape, different purpose:
    proves the caller controls the email address on a newly-registered
    account before that account (if non-PATIENT) can log in."""
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User")


class PhoneOTP(Base):
    """Short-lived OTP proving control of a phone number, delivered via
    core.sms_service (MSG91). A verified row (is_used=True) within the last
    15 minutes is the proof /auth/register checks before attaching `phone`
    to a new DOCTOR/HOSPITAL account — same pattern as email verification,
    but phone-first since MSG91's OTP API generates/tracks the code
    itself; we still keep our own row to rate-limit and to check "was THIS
    phone verified recently" at registration time."""
    __tablename__ = "phone_otps"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, index=True)
    otp_code = Column(String)
    expires_at = Column(DateTime)
    is_used = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, index=True)
    resource = Column(String, index=True)
    resource_id = Column(String, nullable=True, index=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class AuthorizedGovernmentEmail(Base):
    """Whitelist gating Government Portal (ADMIN role) account creation.

    Registering as ADMIN through the public /auth/register endpoint is
    disallowed entirely (schemas.UserCreate.role no longer accepts it) —
    the ONLY way to obtain an ADMIN account is POST /auth/register/government,
    which requires the caller's email to already exist in this table.
    Pre-provisioned (there is no self-serve "apply to be a government
    official" flow, unlike doctors) — seeded via
    GOVERNMENT_WHITELIST_EMAILS in .env at startup (see main.py) and
    otherwise managed directly against this table.
    """
    __tablename__ = "authorized_government_emails"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

