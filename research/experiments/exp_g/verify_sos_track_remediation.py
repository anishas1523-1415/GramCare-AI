"""Direct check of the /sos/track remediation: redaction inside the grace
window, 404 outside it, and the rate limit actually firing."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

SERVICE = r"D:\PROJECTS\GramCare AI\backend\python_service"
sys.path.insert(0, SERVICE)
_T = tempfile.mkdtemp(prefix="gramcare_track_")
os.environ["DATABASE_URL"] = "sqlite:///%s/t.db" % _T.replace("\\", "/")
os.environ.setdefault("JWT_SECRET_KEY", "track-secret-not-for-production")
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


def ck(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + detail if detail else ""))
    if not cond:
        fails.append(label)


def mk(u, role):
    ratelimit.reset_for_tests()
    payload = {"username": u, "email": "%s@trk.gramcare.in" % u, "password": PW,
               "full_name": u.title(), "role": role}
    if role in ("DOCTOR", "HOSPITAL"):
        ph = "+9194%08d" % (abs(hash(u)) % 100000000)
        s = SessionLocal()
        s.add(models.PhoneOTP(phone=ph, otp_code="000000", is_used=True,
                              expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                              + timedelta(minutes=10)))
        s.commit(); s.close()
        payload["phone"] = ph
    c.post(API + "/auth/register", json=payload)
    s = SessionLocal()
    uu = s.query(models.User).filter(models.User.username == u).first()
    uu.is_verified = True
    s.commit(); uid = uu.id; s.close()
    ratelimit.reset_for_tests()
    t = c.post(API + "/auth/login", data={"username": u, "password": PW}).json()["access_token"]
    return t, uid


print("=" * 72)
print("/sos/track remediation - direct check")
print("=" * 72)

pat_t, pat_id = mk("trk_patient", "PATIENT")
hos_t, hos_id = mk("trk_hosp", "HOSPITAL")
c.post(API + "/hospital/register", headers={"Authorization": "Bearer " + hos_t},
       json={"name": "Trk Hospital", "address": "X", "lat": 11.0, "lng": 77.0,
             "phone": "+919000009999"})
s = SessionLocal()
h = s.query(models.Hospital).filter(models.Hospital.owner_user_id == hos_id).first()
h.verification_status = "APPROVED"; s.commit(); s.close()

ratelimit.reset_for_tests()
r = c.post(API + "/sos/trigger", headers={"Authorization": "Bearer " + pat_t},
           json={"location_lat": 11.0, "location_lng": 77.0,
                 "location_text": "TRACKMARK village", "voice_note": "TRACKMARK collapsed",
                 "severity": "CRITICAL"})
sos_id = r.json()["id"]
s = SessionLocal()
tok = s.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first().public_token
s.close()
print("  sos=%s token_len=%d" % (sos_id, len(tok)))

print()
print("1. ACTIVE - the relative must see everything")
ratelimit.reset_for_tests()
r = c.get("%s/sos/track/%s" % (API, tok))
j = r.json() if r.status_code == 200 else {}
ck("200 while active", r.status_code == 200, str(r.status_code))
ck("  location present", j.get("location_lat") is not None)
ck("  location_text present", bool(j.get("location_text")))
ck("  voice_note present", bool(j.get("voice_note")))

print()
print("2. RESOLVED, inside the 24h grace window - redacted but still readable")
c.put("%s/sos/%s/resolve" % (API, sos_id), headers={"Authorization": "Bearer " + pat_t})
ratelimit.reset_for_tests()
r = c.get("%s/sos/track/%s" % (API, tok))
j = r.json() if r.status_code == 200 else {}
ck("200 inside the grace window", r.status_code == 200, str(r.status_code))
ck("  status says RESOLVED", j.get("status") == "RESOLVED", str(j.get("status")))
ck("  location_lat REDACTED", j.get("location_lat") is None, repr(j.get("location_lat")))
ck("  location_lng REDACTED", j.get("location_lng") is None, repr(j.get("location_lng")))
ck("  location_text REDACTED", j.get("location_text") is None, repr(j.get("location_text")))
ck("  voice_note REDACTED", j.get("voice_note") is None, repr(j.get("voice_note")))
ck("  voice_audio_url REDACTED", j.get("voice_audio_url") is None, repr(j.get("voice_audio_url")))
ck("  no canary anywhere in the body", "TRACKMARK" not in r.text, r.text[:90])

print()
print("3. RESOLVED, past the grace window - link stops resolving")
s = SessionLocal()
row = s.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first()
row.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=30)
s.commit(); s.close()
ratelimit.reset_for_tests()
r = c.get("%s/sos/track/%s" % (API, tok))
ck("404 past the grace window", r.status_code == 404, str(r.status_code))
ck("  no canary in the 404 body", "TRACKMARK" not in r.text, r.text[:90])

print()
print("4. rate limit actually fires above the configured threshold")
ratelimit.reset_for_tests()
codes = [c.get("%s/sos/track/%s" % (API, "z" * 30 + "%03d" % i)).status_code
         for i in range(140)]
first = codes.index(429) + 1 if 429 in codes else None
ck("/sos/track throttles within 140 attempts", 429 in codes,
   "first 429 at attempt %s" % first)
ratelimit.reset_for_tests()
codes = [c.get("%s/files/%s" % (API, "z" * 30 + "%03d" % i)).status_code
         for i in range(140)]
first = codes.index(429) + 1 if 429 in codes else None
ck("/files throttles within 140 attempts", 429 in codes,
   "first 429 at attempt %s" % first)

print()
print("5. a legitimate viewer polling every 15s is NOT throttled")
ratelimit.reset_for_tests()
codes = [c.get("%s/sos/track/%s" % (API, tok)).status_code for i in range(20)]
ck("20 polls (5 minutes at 15s) all served", 429 not in codes,
   "codes=%s" % sorted(set(codes)))

print()
print("=" * 72)
if fails:
    print("FAILED (%d):" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("All checks passed.")
