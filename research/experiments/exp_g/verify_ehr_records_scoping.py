"""Verify the /ehr/records scoping fix actually works rather than 500ing.

The isolation matrix only inspects HTTP 200 responses for a canary, so an
endpoint that started returning 500 would show up as "no finding" — a false
pass. This checks the positive case explicitly: the doctor who HAS a
relationship with the patient must still see the record.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

SERVICE = r"D:\PROJECTS\GramCare AI\backend\python_service"
sys.path.insert(0, SERVICE)

_T = tempfile.mkdtemp(prefix="gramcare_verify_")
os.environ["DATABASE_URL"] = "sqlite:///%s/v.db" % _T.replace("\\", "/")
os.environ.setdefault("JWT_SECRET_KEY", "verify-secret-not-for-production")
for v in ("GEMINI_API_KEY", "GEMINI_API_KEYS", "OPENAI_API_KEY", "OPENAI_API_KEYS",
          "GROQ_API_KEY", "GROQ_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
          "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_CLOUD_NAME",
          "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY",
          "MSG91_AUTH_KEY", "RESEND_API_KEY"):
    os.environ[v] = ""
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
import models  # noqa: E402
from database import engine, SessionLocal  # noqa: E402
from core import ratelimit  # noqa: E402
from main import app  # noqa: E402

models.Base.metadata.create_all(bind=engine)
c = TestClient(app)
API = "/api/v1"
PW = "strongpass123"
fails = []


def mk(username, role):
    ratelimit.reset_for_tests()
    payload = {"username": username, "email": "%s@verify.gramcare.in" % username,
               "password": PW, "full_name": username.title(), "role": role}
    if role in ("DOCTOR", "HOSPITAL"):
        phone = "+9191%08d" % (abs(hash(username)) % 100000000)
        s = SessionLocal()
        s.add(models.PhoneOTP(phone=phone, otp_code="000000", is_used=True,
                              expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                              + timedelta(minutes=10)))
        s.commit()
        s.close()
        payload["phone"] = phone
    c.post(API + "/auth/register", json=payload)
    s = SessionLocal()
    u = s.query(models.User).filter(models.User.username == username).first()
    u.is_verified = True
    if role == "DOCTOR":
        p = s.query(models.DoctorProfile).filter(
            models.DoctorProfile.user_id == u.id).first()
        if not p:
            p = models.DoctorProfile(user_id=u.id)
            s.add(p)
        p.verification_status = "APPROVED"
    s.commit()
    uid = u.id
    s.close()
    ratelimit.reset_for_tests()
    r = c.post(API + "/auth/login", data={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], uid


def H(t):
    return {"Authorization": "Bearer %s" % t}


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + detail if detail else ""))
    if not cond:
        fails.append(label)


print("=" * 72)
print("Verifying the /ehr/records scoping fix (positive and negative cases)")
print("=" * 72)

pat_t, pat_id = mk("v_patient", "PATIENT")
doc_mine_t, doc_mine_id = mk("v_doctor_mine", "DOCTOR")
doc_other_t, doc_other_id = mk("v_doctor_other", "DOCTOR")
admin_s = SessionLocal()
from modules.auth.utils import get_password_hash  # noqa: E402
admin_s.add(models.User(username="v_admin", email="v_admin@verify.gramcare.in",
                        hashed_password=get_password_hash(PW), full_name="V Admin",
                        role="ADMIN", is_verified=True))
admin_s.commit()
admin_s.close()
ratelimit.reset_for_tests()
admin_t = c.post(API + "/auth/login",
                 data={"username": "v_admin", "password": PW}).json()["access_token"]

# The patient creates a wallet record.
r = c.post(API + "/ehr/record", headers=H(pat_t),
           json={"record_type": "note", "title": "VERIFYMARK note",
                 "content": "VERIFYMARK content", "client_uuid": "verify-0001"})
check("patient can create a wallet record", r.status_code in (200, 201), str(r.status_code))

# doc_mine establishes a relationship by issuing a prescription.
r = c.post(API + "/ehr/issue_prescription", headers=H(doc_mine_t),
           json={"patient_id": pat_id,
                 "medicines": [{"name": "VerifyMed", "dosage": "1", "frequency": "1-0-1",
                                "duration": "3 days"}],
                 "diagnosis": "verify"})
check("related doctor can issue a prescription", r.status_code in (200, 201), str(r.status_code))

print()
print("GET /ehr/records:")

r = c.get(API + "/ehr/records", headers=H(doc_mine_t))
body = r.text
check("200 for the doctor WITH a relationship", r.status_code == 200,
      "status=%s" % r.status_code)
check("  and it CONTAINS that patient's record", "VERIFYMARK" in body,
      "(len=%d)" % len(body))

r = c.get(API + "/ehr/records", headers=H(doc_other_t))
check("200 for the doctor WITHOUT a relationship", r.status_code == 200,
      "status=%s" % r.status_code)
check("  and it does NOT contain the record", "VERIFYMARK" not in r.text,
      "body=%s" % r.text[:80])

r = c.get(API + "/ehr/records", headers=H(admin_t))
check("200 for ADMIN", r.status_code == 200, "status=%s" % r.status_code)
check("  and ADMIN still sees everything", "VERIFYMARK" in r.text,
      "(len=%d)" % len(r.text))

print()
print("Pagination still works (the fix added a subquery filter):")
for skip, limit in ((0, 1), (0, 200), (5, 10)):
    r = c.get(API + "/ehr/records?skip=%d&limit=%d" % (skip, limit), headers=H(doc_mine_t))
    check("skip=%d limit=%d" % (skip, limit), r.status_code == 200, "status=%s" % r.status_code)

print()
print("=" * 72)
if fails:
    print("FAILED (%d): %s" % (len(fails), fails))
    sys.exit(1)
print("All checks passed. The scoping fix works and does not error.")
