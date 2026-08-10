"""Seeds fixed, fully-usable test accounts for the Playwright E2E suite
(apps/web_portal/e2e/) against a real running backend + database.

Not pytest's conftest.py: that fixture path never touches a real HTTP
server (TestClient calls the ASGI app in-process). This script is for the
other kind of test — a real browser driving a real Next.js server against a
real FastAPI server — which needs the accounts to already exist in the
database before either server starts.

Same reasoning as conftest.py's _register_and_login for why direct DB
writes are legitimate test setup here rather than a bypass of the app
itself: DOCTOR/HOSPITAL email+phone verification and the government
approval gate exist to stop *unverified strangers* from reaching
patient-facing actions — a fixed, source-controlled E2E fixture account is
neither unverified nor a stranger. Idempotent: safe to run repeatedly
against the same database (upserts rather than erroring on conflict).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal  # noqa: E402
import models  # noqa: E402
from modules.auth.utils import get_password_hash  # noqa: E402

E2E_PASSWORD = "E2ETestPass123!"


def _upsert_user(db, username, email, role, full_name):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = models.User(username=username, email=email, role=role, full_name=full_name)
        db.add(user)
    user.hashed_password = get_password_hash(E2E_PASSWORD)
    user.role = role
    user.full_name = full_name
    user.is_active = True
    user.is_verified = True  # Skip email verification for fixed E2E fixtures.
    db.commit()
    db.refresh(user)
    return user


def seed():
    db = SessionLocal()
    try:
        patient = _upsert_user(db, "e2e_patient", "e2e_patient@example.test", "PATIENT", "E2E Patient")

        doctor = _upsert_user(db, "e2e_doctor", "e2e_doctor@example.test", "DOCTOR", "E2E Doctor")
        profile = db.query(models.DoctorProfile).filter(models.DoctorProfile.user_id == doctor.id).first()
        if not profile:
            profile = models.DoctorProfile(user_id=doctor.id)
            db.add(profile)
        profile.specialty = "General Medicine"
        profile.verification_status = "APPROVED"  # Skip the government review gate for this fixture.
        db.commit()

        hospital_owner = _upsert_user(db, "e2e_hospital", "e2e_hospital@example.test", "HOSPITAL", "E2E Hospital Owner")
        hospital = db.query(models.Hospital).filter(models.Hospital.owner_user_id == hospital_owner.id).first()
        if not hospital:
            hospital = models.Hospital(owner_user_id=hospital_owner.id, name="E2E Test Hospital")
            db.add(hospital)
        db.commit()

        print(f"Seeded E2E accounts (password: {E2E_PASSWORD}): "
              f"e2e_patient, e2e_doctor (APPROVED), e2e_hospital")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
