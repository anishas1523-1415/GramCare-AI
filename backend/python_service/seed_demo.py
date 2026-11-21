#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Demo dataset for the GramCare review walkthrough.

Creates a coherent cast across every role, plus the clinical records that make
each screen show something real instead of an empty state.

Design notes
------------
* **Idempotent.** Every row is looked up before it is created, keyed on a
  natural identifier (email, pharmacy name, etc.). Re-running before the demo
  tops the data up; it never duplicates.
* **Obviously demo data.** Every account sits on @demo.gramcare.me and every
  display name carries a real-looking but fictional person. Nothing here
  should ever be mistaken for a real patient record.
* **Operator accounts are pre-verified.** Non-PATIENT roles cannot log in
  until ``is_verified`` is true (see models.User), so the script sets it.
  Doctors and hospitals are also set APPROVED, because an unapproved doctor
  does not appear in the booking list and an unverified hospital is invisible
  to SOS routing — the two failures most likely to derail a live demo.

Usage
-----
    python seed_demo.py                  # uses DATABASE_URL from the environment
    python seed_demo.py --wipe-demo      # removes previously seeded demo rows first

The password for every account is written to the credentials sheet the script
prints at the end; it is not embedded in any other output.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine
from modules.auth.utils import get_password_hash

DEMO_DOMAIN = "demo.gramcare.me"
DEMO_PASSWORD = "GramCare#Demo2026"

# Salem district, Tamil Nadu — the deployment area the project targets.
# Coordinates are real places so the SOS map renders sensibly.
SALEM = (11.6643, 78.1460)


def utcnow() -> datetime:
    """Naive UTC, matching how this codebase stores timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def nearby(km_north: float, km_east: float) -> tuple[float, float]:
    """Offset from Salem centre, in kilometres, as (lat, lng)."""
    return (SALEM[0] + km_north / 111.0,
            SALEM[1] + km_east / (111.0 * 0.978))


# --------------------------------------------------------------------- helpers
def get_or_create_user(db: Session, *, username: str, email: str, full_name: str,
                       role: str, phone: str, verified: bool = True,
                       blood_group: str | None = None) -> models.User:
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        # Keep the demo usable even if an older seed left the account unverified.
        user.is_verified = verified or user.is_verified
        user.is_active = True
        return user
    user = models.User(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        phone=phone,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        is_active=True,
        is_verified=verified,
        phone_verified=True,
    )
    if blood_group and hasattr(models.User, "blood_group"):
        user.blood_group = blood_group
    db.add(user)
    db.flush()
    return user


def first_or_create(db: Session, model, defaults: dict, **lookup):
    row = db.query(model).filter_by(**lookup).first()
    if row:
        return row, False
    row = model(**{**lookup, **defaults})
    db.add(row)
    db.flush()
    return row, True


# ------------------------------------------------------------------ the cast
PATIENTS = [
    # (first name for username, display name, phone, blood group, age context)
    ("lakshmi",  "Lakshmi Ravi",        "9842100101", "O+"),
    ("murugan",  "Murugan Subramani",   "9842100102", "B+"),
    ("kavitha",  "Kavitha Selvam",      "9842100103", "A+"),
    ("arun",     "Arun Prakash",        "9842100104", "AB+"),
    ("meena",    "Meenakshi Duraisamy", "9842100105", "O-"),
]

FAMILY = {
    "lakshmi": [("Ravi Kannan", "Spouse", 46, "Male", "B+", "Penicillin",
                 "Type 2 diabetes"),
                ("Divya Ravi", "Daughter", 9, "Female", "O+", "None", "Asthma")],
    "murugan": [("Sarasu Subramani", "Mother", 71, "Female", "A+", "Sulfa drugs",
                 "Hypertension, arthritis")],
    "kavitha": [("Selvam Natarajan", "Spouse", 38, "Male", "O+", "None", "None"),
                ("Hari Selvam", "Son", 6, "Male", "A+", "Peanuts", "None")],
    "meena":   [("Duraisamy Pillai", "Father", 68, "Male", "O-", "None",
                 "Chronic kidney disease")],
}

DOCTORS = [
    ("drpriya",  "Dr. Priya Narayanan", "9842100201", "General Medicine",
     "MBBS, MD (General Medicine)", 12, 250.0, "Tamil, English",
     "TN-MC-48217"),
    ("drkarthik", "Dr. Karthik Rajan",  "9842100202", "Paediatrics",
     "MBBS, DCH", 8, 300.0, "Tamil, English, Telugu", "TN-MC-51904"),
    ("drfathima", "Dr. Fathima Begum",  "9842100203", "Obstetrics & Gynaecology",
     "MBBS, DGO", 15, 350.0, "Tamil, English, Urdu", "TN-MC-39552"),
]

HOSPITALS = [
    ("salemgh", "Salem Government Headquarters Hospital", "9842100301",
     "Omalur Main Road, Salem 636001", 1.2, -0.8, 1952,
     "24x7 Emergency", "Emergency, General Surgery, Obstetrics", "TN-HOSP-0041"),
    ("nangavalli_phc", "Nangavalli Primary Health Centre", "9842100302",
     "Main Road, Nangavalli, Salem 636454", -6.0, -9.5, 1987,
     "08:00-20:00", "General Medicine, Maternal Health", "TN-HOSP-1188"),
]

PHARMACIES = [
    ("arokiapharm", "Arokia Medicals", "9842100401",
     "Bazaar Street, Nangavalli, Salem 636454", -6.1, -9.3, False),
    ("janaushadhi_salem", "Jan Aushadhi Kendra, Salem", "9842100402",
     "Opposite GH, Omalur Main Road, Salem 636001", 1.1, -0.7, True),
]

LABS = [
    ("sakthilab", "Sakthi Diagnostics", "9842100501",
     "Cherry Road, Salem 636007", 0.9, 0.4, True),
    ("nangavallilab", "Nangavalli Collection Centre", "9842100502",
     "Main Road, Nangavalli, Salem 636454", -6.0, -9.4, False),
]

MEDICINES = [
    # (name, generic group, stock, price, needs Rx, days until expiry)
    ("Paracetamol 500mg",      "Analgesic",      240, 1.20, False, 540),
    ("Amoxicillin 500mg",      "Antibiotic",      80, 6.50, True,  300),
    ("Metformin 500mg",        "Antidiabetic",   150, 2.10, True,  420),
    ("Amlodipine 5mg",         "Antihypertensive", 120, 1.80, True, 365),
    ("ORS Sachet",             "Rehydration",    300, 9.00, False, 600),
    ("Salbutamol Inhaler",     "Bronchodilator",  25, 128.0, True, 240),
    ("Iron + Folic Acid",      "Supplement",     200, 0.95, False, 500),
    ("Cetirizine 10mg",        "Antihistamine",  160, 1.10, False, 450),
    ("Azithromycin 500mg",     "Antibiotic",      18, 24.00, True,  25),   # expiring
    ("Pantoprazole 40mg",      "Antacid",         12, 3.40, True,   18),   # expiring
    ("Insulin Glargine",       "Antidiabetic",     9, 320.0, True,   40),  # low + expiring
]


def seed(db: Session, verbose: bool = True) -> dict:
    created = {k: 0 for k in
               ("patients", "family", "doctors", "hospitals", "pharmacies",
                "labs", "chw", "admin", "stock", "triage", "appointments",
                "prescriptions", "sos", "lab_bookings", "records", "vitals",
                "contacts")}
    now = utcnow()

    # ---------------------------------------------------------------- patients
    patient_users: dict[str, models.User] = {}
    for key, name, phone, blood in PATIENTS:
        u = get_or_create_user(
            db, username=f"{key}.demo", email=f"{key}@{DEMO_DOMAIN}",
            full_name=name, role="PATIENT", phone=phone, verified=True,
            blood_group=blood)
        patient_users[key] = u
        created["patients"] += 1

        _, made = first_or_create(
            db, models.EmergencyContact,
            {"name": "Village ASHA worker", "phone": "9842100999",
             "relation": "Community health worker"},
            user_id=u.id, name="Village ASHA worker")
        created["contacts"] += int(made)

    # ------------------------------------------------------------ family members
    family_rows: dict[str, list[models.FamilyProfile]] = {}
    for key, members in FAMILY.items():
        owner = patient_users[key]
        family_rows[key] = []
        for full_name, relation, age, gender, blood, allergies, chronic in members:
            row, made = first_or_create(
                db, models.FamilyProfile,
                {"relation": relation, "age": age, "gender": gender,
                 "blood_group": blood, "allergies": allergies,
                 "chronic_conditions": chronic,
                 "color_tag": random.choice(
                     ["#0e7c66", "#1e5f8b", "#6b3fa0", "#b16a09"])},
                user_id=owner.id, full_name=full_name)
            family_rows[key].append(row)
            created["family"] += int(made)

    # ----------------------------------------------------------------- doctors
    doctor_profiles: list[models.DoctorProfile] = []
    for key, name, phone, specialty, quals, years, fee, langs, lic in DOCTORS:
        u = get_or_create_user(
            db, username=f"{key}.demo", email=f"{key}@{DEMO_DOMAIN}",
            full_name=name, role="DOCTOR", phone=phone, verified=True)
        prof, made = first_or_create(
            db, models.DoctorProfile,
            {"specialty": specialty, "qualifications": quals,
             "experience_years": years, "consultation_fee": fee,
             "languages": langs, "is_available": True,
             "license_number": lic,
             "bio": f"{specialty} with {years} years of practice in Salem "
                    f"district. Consults in {langs}.",
             "service_hours": "09:00-13:00, 16:00-20:00",
             # APPROVED matters: an unapproved doctor never appears in the
             # patient's booking list, which looks like a broken feature.
             "verification_status": "APPROVED",
             "reviewed_at": now},
            user_id=u.id)
        doctor_profiles.append(prof)
        created["doctors"] += int(made)

        # Bookable slots for the next three days.
        for day in range(1, 4):
            for hour in (10, 11, 17):
                start = (now + timedelta(days=day)).replace(
                    hour=hour, minute=0, second=0, microsecond=0)
                first_or_create(
                    db, models.AvailabilitySlot,
                    {"end_time": start + timedelta(minutes=30),
                     "is_booked": False},
                    doctor_profile_id=prof.id, start_time=start)

    # --------------------------------------------------------------- hospitals
    hospital_rows: list[models.Hospital] = []
    for key, name, phone, address, kn, ke, year, timing, specs, lic in HOSPITALS:
        u = get_or_create_user(
            db, username=f"{key}.demo", email=f"{key}@{DEMO_DOMAIN}",
            full_name=f"{name} (Emergency Desk)", role="HOSPITAL",
            phone=phone, verified=True)
        lat, lng = nearby(kn, ke)
        row, made = first_or_create(
            db, models.Hospital,
            {"owner_user_id": u.id, "address": address, "lat": lat, "lng": lng,
             "phone": phone, "established_year": year, "service_timing": timing,
             "specializations": specs, "license_number": lic,
             # APPROVED matters: SOS routing only considers verified hospitals.
             "verification_status": "APPROVED",
             "emergency_desk_user_id": u.id, "reviewed_at": now},
            name=name)
        hospital_rows.append(row)
        created["hospitals"] += int(made)

    # -------------------------------------------------------------- pharmacies
    pharmacy_rows: list[models.Pharmacy] = []
    for key, name, phone, address, kn, ke, jan in PHARMACIES:
        u = get_or_create_user(
            db, username=f"{key}.demo", email=f"{key}@{DEMO_DOMAIN}",
            full_name=f"{name} (Pharmacist)", role="PHARMACIST",
            phone=phone, verified=True)
        lat, lng = nearby(kn, ke)
        row, made = first_or_create(
            db, models.Pharmacy,
            {"owner_user_id": u.id, "address": address, "lat": lat, "lng": lng,
             "phone": phone, "is_active": True, "is_jan_aushadhi": jan},
            name=name)
        pharmacy_rows.append(row)
        created["pharmacies"] += int(made)

        for med, group, stock, price, rx, days in MEDICINES:
            _, s_made = first_or_create(
                db, models.PharmacyItem,
                {"generic_group": group,
                 "stock_count": stock if not jan else int(stock * 0.7),
                 "price": price if not jan else round(price * 0.4, 2),
                 "requires_prescription": rx,
                 "expiry_date": (now + timedelta(days=days)).date(),
                 "batch_number": f"B{random.randint(10000, 99999)}",
                 "last_updated": now},
                pharmacy_id=row.id, medicine_name=med)
            created["stock"] += int(s_made)

    # -------------------------------------------------------------------- labs
    lab_rows: list[models.LabCenter] = []
    for key, name, phone, address, kn, ke, home in LABS:
        u = get_or_create_user(
            db, username=f"{key}.demo", email=f"{key}@{DEMO_DOMAIN}",
            full_name=f"{name} (Technician)", role="LAB",
            phone=phone, verified=True)
        lat, lng = nearby(kn, ke)
        row, made = first_or_create(
            db, models.LabCenter,
            {"owner_user_id": u.id, "address": address, "lat": lat, "lng": lng,
             "phone": phone, "offers_home_collection": home, "is_active": True},
            name=name)
        lab_rows.append(row)
        created["labs"] += int(made)

    # --------------------------------------------------------- CHW + admin
    get_or_create_user(db, username="asha.demo", email=f"asha@{DEMO_DOMAIN}",
                       full_name="Vasanthi Murugesan (ASHA)", role="CHW",
                       phone="9842100601", verified=True)
    created["chw"] += 1
    get_or_create_user(db, username="dho.demo", email=f"dho@{DEMO_DOMAIN}",
                       full_name="District Health Officer, Salem", role="ADMIN",
                       phone="9842100701", verified=True)
    created["admin"] += 1

    db.flush()

    # ------------------------------------------------- clinical activity
    lakshmi = patient_users["lakshmi"]
    murugan = patient_users["murugan"]
    kavitha = patient_users["kavitha"]
    arun = patient_users["arun"]
    meena = patient_users["meena"]

    # Triage history, deliberately clustered so the outbreak view has a signal:
    # four febrile presentations in Nangavalli within a week.
    triage_seed = [
        (lakshmi, "Fever for three days with body ache and chills", 70,
         "Possible viral fever (e.g. dengue or malaria)", 0.78, "Nangavalli", 2),
        (murugan, "High fever and severe headache since yesterday", 68,
         "Possible viral fever", 0.74, "Nangavalli", 3),
        (kavitha, "Fever with joint pain, feeling very weak", 66,
         "Possible viral fever (chikungunya cannot be excluded)", 0.71,
         "Nangavalli", 4),
        (arun, "Mild fever and sore throat", 42,
         "Upper respiratory tract infection", 0.69, "Nangavalli", 5),
        (meena, "Loose stools since morning, mild dehydration", 55,
         "Acute gastroenteritis", 0.81, "Salem", 1),
    ]
    for user, text, score, cond, conf, place, days_ago in triage_seed:
        _, made = first_or_create(
            db, models.TriageLog,
            {"ai_severity_score": score, "ai_predicted_condition": cond,
             "ai_confidence": conf, "language_detected": "en",
             "ai_explanation": "Seeded demo triage. Advisory only; not a "
                               "diagnosis.",
             "location_text": place,
             "created_at": now - timedelta(days=days_ago)},
            patient_id=user.id, symptoms_text=text)
        created["triage"] += int(made)

    # One upcoming confirmed appointment and one completed consultation.
    appt_upcoming, made = first_or_create(
        db, models.Appointment,
        {"doctor_id": doctor_profiles[0].user_id,
         "status": "CONFIRMED",
         "triage_summary": "Fever for three days with body ache and chills",
         "triage_severity_score": 70,
         "created_at": now - timedelta(days=1)},
        patient_id=lakshmi.id,
        scheduled_at=(now + timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0))
    created["appointments"] += int(made)

    appt_done, made = first_or_create(
        db, models.Appointment,
        {"doctor_id": doctor_profiles[0].user_id,
         "status": "COMPLETED",
         "triage_summary": "Loose stools since morning, mild dehydration",
         "triage_severity_score": 55,
         "consultation_notes": "Mild acute gastroenteritis. Oral rehydration "
                               "advised. Review if symptoms persist beyond 48h.",
         "created_at": now - timedelta(days=2)},
        patient_id=meena.id,
        scheduled_at=(now - timedelta(days=1)).replace(
            hour=11, minute=0, second=0, microsecond=0))
    created["appointments"] += int(made)

    # Prescription waiting in the pharmacy queue (unfulfilled, so it shows up).
    _, made = first_or_create(
        db, models.Prescription,
        {"patient_id": meena.id, "doctor_id": doctor_profiles[0].user_id,
         # Prescription.medicines is Column(JSON) and the UI expects a list of
         # {name, dosage, frequency, duration}. A bare string is valid JSON but
         # renders as one unreadable blob in the pharmacy queue.
         "medicines": [
             {"name": "ORS Sachet", "dosage": "1 sachet",
              "frequency": "After each loose stool", "duration": "5 days"},
             {"name": "Pantoprazole 40mg", "dosage": "1 tablet",
              "frequency": "Once daily before food", "duration": "5 days"},
         ],
         "dosage_instructions": "ORS after each loose stool. Pantoprazole 40mg "
                                "once daily before food for 5 days.",
         "diagnosis": "Acute gastroenteritis",
         "is_fulfilled": False,
         "created_at": now - timedelta(days=1)},
        appointment_id=appt_done.id)
    created["prescriptions"] += int(made)

    # One live SOS, routed to the nearest verified hospital.
    sos_lat, sos_lng = nearby(-6.2, -9.6)
    _, made = first_or_create(
        db, models.EmergencySOS,
        {"location_lat": sos_lat, "location_lng": sos_lng,
         "location_text": "Near Nangavalli bus stand",
         "severity": "HIGH", "status": "PENDING", "escalation_level": 0,
         "assigned_hospital_id": hospital_rows[1].id,
         "created_at": now - timedelta(minutes=4)},
        patient_id=murugan.id, voice_note="Chest pain and breathlessness")
    created["sos"] += int(made)

    # Lab work: one awaiting collection, one with a result ready.
    _, made = first_or_create(
        db, models.LabBooking,
        {"lab_center_id": lab_rows[0].id, "home_collection": True,
         "status": "PENDING",
         "scheduled_at": now + timedelta(days=1),
         "notes": "Fasting sample required.",
         "created_at": now - timedelta(hours=6)},
        patient_id=lakshmi.id, test_name="Complete Blood Count (CBC)")
    created["lab_bookings"] += int(made)

    _, made = first_or_create(
        db, models.LabBooking,
        {"lab_center_id": lab_rows[0].id, "home_collection": False,
         "status": "COMPLETED",
         "scheduled_at": now - timedelta(days=2),
         # LabBooking.report_payload is Column(JSON); same reasoning as above.
         "report_payload": {
             "summary": "Suboptimal glycaemic control.",
             "results": [
                 {"analyte": "Random blood glucose", "value": "182",
                  "unit": "mg/dL", "reference": "70-140", "flag": "HIGH"},
                 {"analyte": "HbA1c", "value": "7.9", "unit": "%",
                  "reference": "<7.0", "flag": "HIGH"},
             ],
         },
         "report_ready_at": now - timedelta(days=1),
         "created_at": now - timedelta(days=3)},
        patient_id=murugan.id, test_name="Blood Glucose + HbA1c")
    created["lab_bookings"] += int(made)

    # EHR history so the patient timeline is not empty.
    for user, rtype, title, content, days_ago in [
        (lakshmi, "CONSULTATION", "Fever consultation",
         "Seen at Nangavalli PHC. Advised rest, fluids, paracetamol.", 2),
        (murugan, "LAB_REPORT", "Blood glucose + HbA1c",
         "RBS 182 mg/dL, HbA1c 7.9%. Metformin dose reviewed.", 1),
        (kavitha, "VACCINATION", "Td booster",
         "Tetanus-diphtheria booster administered at PHC.", 30),
        (meena, "CONSULTATION", "Gastroenteritis",
         "ORS advised. Review in 48h if unresolved.", 1),
    ]:
        _, made = first_or_create(
            db, models.EHRRecord,
            {"content": content, "doctor_name": "Dr. Priya Narayanan",
             "record_date": (now - timedelta(days=days_ago)).date(),
             "client_uuid": f"demo-{user.id}-{rtype.lower()}",
             "created_at": now - timedelta(days=days_ago)},
            patient_id=user.id, record_type=rtype, title=title)
        created["records"] += int(made)

    # Vitals from a paired BLE device, so the vitals chart has a series.
    # Anchored to midnight rather than "now", so re-running the seed matches the
    # existing rows instead of appending a fresh series every time.
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(8):
        ts = midnight - timedelta(hours=i * 6)
        _, made = first_or_create(
            db, models.IoTVitals,
            {"heart_rate": random.randint(68, 94),
             "spo2": random.randint(95, 99),
             "temperature": round(random.uniform(36.6, 38.4), 1),
             "steps": random.randint(900, 5200),
             "sleep_deep_hours": round(random.uniform(0.8, 2.4), 1),
             "sleep_light_hours": round(random.uniform(3.0, 5.5), 1)},
            patient_id=lakshmi.id, device_id="DEMO-BP-01", timestamp=ts)
        created["vitals"] += int(made)

    db.commit()
    return created


def wipe_demo(db: Session) -> int:
    """Remove rows created by a previous run of this script."""
    users = db.query(models.User).filter(
        models.User.email.like(f"%@{DEMO_DOMAIN}")).all()
    ids = [u.id for u in users]
    if not ids:
        return 0
    for model, col in [
        (models.IoTVitals, "patient_id"), (models.EHRRecord, "patient_id"),
        (models.LabBooking, "patient_id"), (models.EmergencySOS, "patient_id"),
        (models.Prescription, "patient_id"), (models.Appointment, "patient_id"),
        (models.TriageLog, "patient_id"), (models.FamilyProfile, "user_id"),
        (models.EmergencyContact, "user_id"),
    ]:
        db.query(model).filter(getattr(model, col).in_(ids)).delete(
            synchronize_session=False)
    for prof in db.query(models.DoctorProfile).filter(
            models.DoctorProfile.user_id.in_(ids)).all():
        db.query(models.AvailabilitySlot).filter(
            models.AvailabilitySlot.doctor_profile_id == prof.id).delete(
            synchronize_session=False)
    for pharm in db.query(models.Pharmacy).filter(
            models.Pharmacy.owner_user_id.in_(ids)).all():
        db.query(models.PharmacyItem).filter(
            models.PharmacyItem.pharmacy_id == pharm.id).delete(
            synchronize_session=False)
    for model in (models.DoctorProfile, models.Hospital, models.Pharmacy,
                  models.LabCenter):
        col = "user_id" if model is models.DoctorProfile else "owner_user_id"
        db.query(model).filter(getattr(model, col).in_(ids)).delete(
            synchronize_session=False)
    db.query(models.User).filter(models.User.id.in_(ids)).delete(
        synchronize_session=False)
    db.commit()
    return len(ids)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wipe-demo", action="store_true",
                    help="delete previously seeded demo rows first")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        host = str(engine.url.host or "?")
        print(f"target database host: {host}")
        if args.wipe_demo:
            n = wipe_demo(db)
            print(f"removed {n} previously seeded demo account(s)")
        created = seed(db)
    finally:
        db.close()

    print("\nseeded:")
    for k, v in created.items():
        print(f"  {k:14s} {v}")
    print(f"\n{len(PATIENTS)} patients, {len(DOCTORS)} doctors, "
          f"{len(HOSPITALS)} hospitals, {len(PHARMACIES)} pharmacies, "
          f"{len(LABS)} labs, 1 CHW, 1 admin")
    print(f"all accounts: <name>@{DEMO_DOMAIN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
