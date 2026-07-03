"""Canonical demo/dev seed script (the former seed_data.py has been merged
into this file — there is exactly one seed path now).

Usage:
    python seed.py

Idempotent: safe to run repeatedly. Assumes the schema already exists
(run `alembic upgrade head` first; the Docker/render start commands do this
automatically).

Demo credentials (all passwords: password123):
    patient1  / PATIENT   (Ramesh Kumar)
    doctor1   / DOCTOR    (Dr. Sarah Jenkins, General Medicine)
    doctor2   / DOCTOR    (Dr. Anand Krishnan, Dermatology)
    pharma1   / PHARMACIST (Grama Medicals, Sivaganga)
"""
from datetime import datetime, timedelta, date

import models
from database import SessionLocal
from modules.auth.utils import get_password_hash


def _get_or_create_user(db, username, email, full_name, role):
    user = db.query(models.User).filter_by(username=username).first()
    if not user:
        user = models.User(
            username=username,
            email=email,
            hashed_password=get_password_hash("password123"),
            full_name=full_name,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created {role} user: {username}")
    return user


def seed():
    db = SessionLocal()
    try:
        # 1. Users
        patient = _get_or_create_user(db, "patient1", "patient1@gramcare.in", "Ramesh Kumar", "PATIENT")
        doctor1 = _get_or_create_user(db, "doctor1", "dr.sarah@gramcare.in", "Dr. Sarah Jenkins", "DOCTOR")
        doctor2 = _get_or_create_user(db, "doctor2", "dr.anand@gramcare.in", "Dr. Anand Krishnan", "DOCTOR")
        pharmacist = _get_or_create_user(db, "pharma1", "pharma@gramcare.in", "Murugan", "PHARMACIST")

        # 2. Doctor profiles + availability slots
        if not db.query(models.DoctorProfile).filter_by(user_id=doctor1.id).first():
            db.add(models.DoctorProfile(
                user_id=doctor1.id, specialty="General Medicine",
                qualifications="MBBS, MD", experience_years=12,
                consultation_fee=150.0, languages="Tamil,English",
            ))
        if not db.query(models.DoctorProfile).filter_by(user_id=doctor2.id).first():
            db.add(models.DoctorProfile(
                user_id=doctor2.id, specialty="Dermatology",
                qualifications="MBBS, DDVL", experience_years=8,
                consultation_fee=250.0, languages="Tamil,English,Hindi",
            ))
        db.commit()

        for doc in (doctor1, doctor2):
            profile = db.query(models.DoctorProfile).filter_by(user_id=doc.id).first()
            if not db.query(models.AvailabilitySlot).filter_by(doctor_profile_id=profile.id).count():
                base = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
                for day in range(3):
                    for hour in (9, 10, 11, 16, 17):
                        start = base.replace(hour=hour) + timedelta(days=day)
                        db.add(models.AvailabilitySlot(
                            doctor_profile_id=profile.id,
                            start_time=start,
                            end_time=start + timedelta(minutes=30),
                        ))
                db.commit()
                print(f"Published demo slots for {doc.full_name}")

        # 3. Family profiles for the demo patient
        if not db.query(models.FamilyProfile).filter_by(user_id=patient.id).count():
            db.add_all([
                models.FamilyProfile(
                    user_id=patient.id, full_name="Sita Devi", relation="Mother",
                    age=55, gender="Female", chronic_conditions="Hypertension",
                    color_tag="#f59e0b",
                ),
                models.FamilyProfile(
                    user_id=patient.id, full_name="Arjun Kumar", relation="Son",
                    age=12, gender="Male", color_tag="#10b981",
                ),
            ])
            db.commit()
            print("Family profiles seeded.")

        # 4. Pharmacy + inventory (geo: Sivaganga district, rural Tamil Nadu)
        pharmacy = db.query(models.Pharmacy).filter_by(owner_user_id=pharmacist.id).first()
        if not pharmacy:
            pharmacy = models.Pharmacy(
                owner_user_id=pharmacist.id, name="Grama Medicals",
                address="Main Road, Sivaganga", lat=9.8433, lng=78.4809,
                phone="+91-9000000001",
            )
            db.add(pharmacy)
            db.commit()
            db.refresh(pharmacy)
            print("Pharmacy seeded.")

        if not db.query(models.PharmacyItem).count():
            today = date.today()
            db.add_all([
                models.PharmacyItem(pharmacy_id=pharmacy.id, medicine_name="Paracetamol 500mg",
                                    generic_group="paracetamol-500", stock_count=1200, price=20.0,
                                    expiry_date=today + timedelta(days=400)),
                models.PharmacyItem(pharmacy_id=pharmacy.id, medicine_name="Dolo 650",
                                    generic_group="paracetamol-650", stock_count=300, price=32.0,
                                    expiry_date=today + timedelta(days=200)),
                models.PharmacyItem(pharmacy_id=pharmacy.id, medicine_name="Amoxicillin 250mg",
                                    generic_group="amoxicillin-250", stock_count=12, price=45.0,
                                    requires_prescription=True,
                                    expiry_date=today + timedelta(days=60)),  # near expiry + low stock
                models.PharmacyItem(pharmacy_id=pharmacy.id, medicine_name="Insulin Glargine",
                                    generic_group="insulin-glargine", stock_count=0, price=350.0,
                                    requires_prescription=True),
                models.PharmacyItem(pharmacy_id=pharmacy.id, medicine_name="Cetirizine 10mg",
                                    generic_group="cetirizine-10", stock_count=450, price=15.0,
                                    expiry_date=today + timedelta(days=500)),
                models.PharmacyItem(pharmacy_id=pharmacy.id, medicine_name="Metformin 500mg",
                                    generic_group="metformin-500", stock_count=600, price=30.0,
                                    requires_prescription=True,
                                    expiry_date=today + timedelta(days=700)),
            ])
            db.commit()
            print("Pharmacy inventory seeded.")

        # 5. Hospital with an emergency desk account
        if not db.query(models.Hospital).count():
            desk = _get_or_create_user(
                db, "gh_sivaganga", "emergency@ghsivaganga.in",
                "GH Sivaganga Emergency Desk", "HOSPITAL",
            )
            db.add(models.Hospital(
                name="Government Hospital Sivaganga",
                address="Hospital Road, Sivaganga", lat=9.8470, lng=78.4820,
                phone="+91-4575-240000", emergency_desk_user_id=desk.id,
            ))
            db.commit()
            print("Hospital seeded.")

        # 6. Sample wallet records for the demo patient
        if not db.query(models.EHRRecord).count():
            db.add_all([
                models.EHRRecord(
                    patient_id=patient.id, record_type="prescription",
                    title="Viral fever",
                    content="Diagnosis: Viral fever | Medicines: Paracetamol 500mg 1-0-1 (5 days) | Notes: Take after food.",
                    payload={"medicines": [{"name": "Paracetamol 500mg", "dosage": "500mg",
                                            "frequency": "1-0-1", "duration": "5 days"}]},
                    doctor_name="Dr. Sarah Jenkins",
                ),
                models.EHRRecord(
                    patient_id=patient.id, record_type="triage_log",
                    title="AI Symptom Check",
                    content="Symptoms: High fever and cough. AI Predicted: Viral Infection. Severity: 40/100.",
                    doctor_name="GramCare AI",
                ),
            ])
            db.commit()
            print("EHR records seeded.")

        print("Seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
