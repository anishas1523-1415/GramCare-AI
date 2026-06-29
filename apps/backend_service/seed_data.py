import os
from sqlalchemy.orm import Session
from database import engine, SessionLocal
import models
from datetime import datetime
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed():
    print("Seeding database with mock data...")
    db = SessionLocal()
    
    # 1. Create Mock Users (Patient, Doctor, Pharmacist)
    if not db.query(models.User).filter_by(username="patient1").first():
        patient = models.User(
            username="patient1",
            email="patient1@gramcare.in",
            hashed_password=pwd_context.hash("password123"),
            full_name="Ramesh Kumar",
            role="PATIENT"
        )
        doctor = models.User(
            username="doctor1",
            email="dr.sarah@gramcare.in",
            hashed_password=pwd_context.hash("password123"),
            full_name="Dr. Sarah Jenkins",
            role="DOCTOR"
        )
        pharmacist = models.User(
            username="pharma1",
            email="pharma@gramcare.in",
            hashed_password=pwd_context.hash("password123"),
            full_name="Main Branch Pharmacy",
            role="PHARMACIST"
        )
        db.add_all([patient, doctor, pharmacist])
        db.commit()
        print("Mock Users created.")

    # 2. Seed Pharmacy Inventory
    if db.query(models.PharmacyItem).count() == 0:
        inventory = [
            models.PharmacyItem(pharmacy_id="pharma1", medicine_name="Paracetamol 500mg", stock_count=1200, price=20.0, requires_prescription=False),
            models.PharmacyItem(pharmacy_id="pharma1", medicine_name="Amoxicillin 250mg", stock_count=12, price=45.0, requires_prescription=True), # Low Stock Alert
            models.PharmacyItem(pharmacy_id="pharma1", medicine_name="Insulin Glargine", stock_count=0, price=350.0, requires_prescription=True), # Out of Stock
            models.PharmacyItem(pharmacy_id="pharma1", medicine_name="Cetirizine 10mg", stock_count=450, price=15.0, requires_prescription=False),
            models.PharmacyItem(pharmacy_id="pharma1", medicine_name="Metformin 500mg", stock_count=600, price=30.0, requires_prescription=True)
        ]
        db.add_all(inventory)
        db.commit()
        print("Pharmacy Inventory seeded.")

    # 3. Seed EHR Records
    if db.query(models.EHRRecord).count() == 0:
        records = [
            models.EHRRecord(
                patient_id="patient1",
                record_type="prescription",
                content="Medicines: Paracetamol 500mg (1-0-1), Amoxicillin 250mg (1-1-1) | Notes: Take after food for 5 days.",
                doctor_name="dr.sarah"
            ),
            models.EHRRecord(
                patient_id="patient1",
                record_type="triage_log",
                content="Symptoms: High fever and cough. AI Predicted: Viral Infection. Severity: 40/100.",
                doctor_name="GramCare AI"
            )
        ]
        db.add_all(records)
        db.commit()
        print("EHR Records seeded.")
    
    db.close()
    print("Seeding Complete!")

if __name__ == "__main__":
    # Ensure tables exist
    models.Base.metadata.create_all(bind=engine)
    seed()
