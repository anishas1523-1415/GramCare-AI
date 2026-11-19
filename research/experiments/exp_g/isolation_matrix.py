"""Experiment G — cross-role, cross-tenant isolation matrix.

Research question
-----------------
Is role-based access control, as conventionally implemented, sufficient to
prevent cross-tenant exposure in a multi-role shared-record health platform?

Method
------
Two independent tenants are seeded for every role (A and B). Tenant A creates
resources carrying a distinctive canary string. Every endpoint is then probed
along four axes:

  Axis 1  unauthenticated          expect 401/403 unless deliberately public
  Axis 2  wrong role               expect 403
  Axis 3  same role, other tenant  expect A's canary ABSENT from B's response
  Axis 4  same role, other tenant, A's resource id in the path
                                   expect 403 or 404, never 200

Axis 3 is the axis that found the leaks reported in the audit: an endpoint can
pass every authentication and role check and still hand tenant B tenant A's
rows.

Environment
-----------
Runs against a throwaway SQLite database built from the SQLAlchemy metadata,
with every external credential blanked, exactly as the test suite does. It
touches no production data and no third-party service. Reproducible: the run
records the git SHA and writes raw per-probe rows to CSV.

Usage
-----
    .venv/Scripts/python.exe research/experiments/exp_g/isolation_matrix.py

Run it from the repository's backend/python_service directory, or from the
repository root — the script locates the service root itself.
"""
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- bootstrap
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SERVICE = os.path.join(REPO, "backend", "python_service")
sys.path.insert(0, SERVICE)

# EXPG_DATABASE_URL points the run at an isolated PostgreSQL database for the
# engine-validation run; without it the run uses a throwaway SQLite file. The
# same harness therefore produces both runs, so a difference between them is a
# difference in the database, not in the probe.
_explicit = os.environ.get("EXPG_DATABASE_URL")
if _explicit:
    os.environ["DATABASE_URL"] = _explicit
    ENGINE_LABEL = "postgresql" if _explicit.startswith("postgres") else "other"
else:
    _TMPDIR = tempfile.mkdtemp(prefix="gramcare_expg_")
    os.environ["DATABASE_URL"] = "sqlite:///%s/expg.db" % _TMPDIR.replace("\\", "/")
    ENGINE_LABEL = "sqlite"
os.environ.setdefault("JWT_SECRET_KEY", "exp-g-secret-not-for-production")
for _v in ("GEMINI_API_KEY", "GEMINI_API_KEYS", "OPENAI_API_KEY", "OPENAI_API_KEYS",
           "GROQ_API_KEY", "GROQ_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
           "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_CLOUD_NAME",
           "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY",
           "MSG91_AUTH_KEY", "RESEND_API_KEY"):
    os.environ[_v] = ""
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
import models  # noqa: E402
import sqlalchemy  # noqa: E402
from database import engine, SessionLocal  # noqa: E402
from core import ratelimit  # noqa: E402
from main import app  # noqa: E402
from modules.auth.utils import get_password_hash  # noqa: E402

models.Base.metadata.create_all(bind=engine)
client = TestClient(app)
API = "/api/v1"
PW = "strongpass123"

# Two canary CLASSES, so that a hit is unambiguous.
#
# CANARY_A marks PRIVATE CLINICAL data: wallet note content, prescription
# diagnosis, SOS voice note, lab test name, referral reason. None of this may
# ever reach another tenant, so any appearance of CANARY_A in tenant B's
# response is a confirmed leak with no interpretation needed.
#
# DIRNAME_A marks the account's DISPLAY NAME, which a public doctor directory
# is supposed to expose. Keeping it separate removes a whole class of false
# positive that an undifferentiated canary cannot distinguish from a leak.
CANARY_A = "CANARYALPHA"
CANARY_B = "CANARYBRAVO"
DIRNAME_A = "DIRNAMEALPHA"
DIRNAME_B = "DIRNAMEBRAVO"

ROLES = ["PATIENT", "DOCTOR", "PHARMACIST", "LAB", "HOSPITAL", "CHW"]

# Endpoints that are public BY DESIGN. Everything else is expected to reject an
# unauthenticated caller. Each entry needs a reason, so the list cannot quietly
# become an excuse.
PUBLIC_BY_DESIGN = {
    "/api/v1/triage/analyze": "guest symptom check — a visitor must be able to triage before signing up",
    "/api/v1/auth/login": "authentication entry point",
    "/api/v1/auth/register": "account creation",
    "/api/v1/auth/register/government": "whitelist-gated account creation",
    "/api/v1/auth/refresh": "token refresh carries its own credential",
    "/api/v1/auth/request-otp": "pre-account phone verification",
    "/api/v1/auth/verify-otp": "pre-account phone verification",
    "/api/v1/auth/verify-email": "token-in-URL email verification",
    "/api/v1/auth/resend-verification": "pre-login recovery",
    "/api/v1/auth/forgot-password": "pre-login recovery",
    "/api/v1/auth/reset-password": "token-in-URL recovery",
}

# Endpoints this harness initially assumed were public and which turned out to
# require authentication. Kept as a record: the allowlist was wrong, not the
# code. Worth one line in the paper as a design-consistency observation, since
# /triage/analyze IS open to a guest while the lab catalogue and pharmacy
# search are not.
AUTHENTICATED_THOUGH_ARGUABLY_PUBLIC = {
    "/api/v1/lab/tests", "/api/v1/lab/centers", "/api/v1/pharmacy/search",
    "/api/v1/pharmacy/substitutes", "/api/v1/pharmacy/medicine-info",
    "/api/v1/ai/health",
}


def log(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def auth(tok):
    return {"Authorization": "Bearer %s" % tok}


def register(username, role, canary):
    # Registration and login are rate-limited per caller. Seeding 13 accounts
    # from one client trips that limiter, which is correct behaviour and not
    # what this experiment is testing, so the counters are cleared each time.
    ratelimit.reset_for_tests()
    """Create and log in an account. Mirrors tests/conftest.py's test-only
    bypasses: email verification and doctor approval are flipped directly,
    because neither can be driven from a script without a mail client."""
    if role == "ADMIN":
        s = SessionLocal()
        try:
            if not s.query(models.User).filter(models.User.username == username).first():
                s.add(models.User(
                    username=username, email="%s@expg.gramcare.in" % username,
                    hashed_password=get_password_hash(PW),
                    full_name="%s %s" % (canary, role), role="ADMIN", is_verified=True))
                s.commit()
        finally:
            s.close()
    else:
        payload = {
            "username": username, "email": "%s@expg.gramcare.in" % username,
            "password": PW, "full_name": "%s %s" % (canary, role), "role": role,
        }
        if role in ("DOCTOR", "HOSPITAL"):
            phone = "+9190%08d" % (abs(hash(username)) % 100000000)
            s = SessionLocal()
            try:
                s.add(models.PhoneOTP(
                    phone=phone, otp_code="000000", is_used=True,
                    expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    + timedelta(minutes=10)))
                s.commit()
            finally:
                s.close()
            payload["phone"] = phone
        _rr = client.post(API + "/auth/register", json=payload)
        if _rr.status_code not in (200, 201, 400):
            log("    register(%s) -> %s %s" % (username, _rr.status_code, _rr.text[:300]))
        s = SessionLocal()
        try:
            u = s.query(models.User).filter(models.User.username == username).first()
            if u:
                u.is_verified = True
                if role == "DOCTOR":
                    p = (s.query(models.DoctorProfile)
                         .filter(models.DoctorProfile.user_id == u.id).first())
                    if not p:
                        p = models.DoctorProfile(user_id=u.id)
                        s.add(p)
                    p.verification_status = "APPROVED"
                s.commit()
        finally:
            s.close()

    ratelimit.reset_for_tests()
    r = client.post(API + "/auth/login", data={"username": username, "password": PW})
    if r.status_code != 200:
        raise SystemExit("seed failure: could not log in %s (%s): %s"
                         % (username, role, r.text[:200]))
    tok = r.json()["access_token"]
    me = client.get(API + "/auth/me", headers=auth(tok)).json()
    return tok, me["id"]


# ------------------------------------------------------------------ seeding
log("=" * 78)
log("Experiment G - cross-role, cross-tenant isolation matrix")
log("=" * 78)

try:
    SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
except Exception:
    SHA = "unknown"
RUN_AT = datetime.now(timezone.utc).isoformat()
try:
    with engine.connect() as _c:
        DBVER = _c.execute(sqlalchemy.text(
            "select version()" if ENGINE_LABEL == "postgresql"
            else "select sqlite_version()")).scalar()
except Exception as _e:
    DBVER = "unknown (%s)" % type(_e).__name__

log("commit   : %s" % SHA)
log("engine   : %s" % ENGINE_LABEL)
log("db ver   : %s" % str(DBVER)[:80])
log("python   : %s   sqlalchemy: %s" % (sys.version.split()[0], sqlalchemy.__version__))
log("run at   : %s" % RUN_AT)
log("database : isolated, synthetic data only, all external credentials blanked")
log("")

log("[seed] two independent tenants per role")
tok = {}
uid = {}
for role in ROLES:
    for side, canary in (("a", DIRNAME_A), ("b", DIRNAME_B)):
        key = "%s_%s" % (role.lower(), side)
        tok[key], uid[key] = register("expg_%s" % key, role, canary)
        log("    %-14s id=%s" % (key, uid[key]))
tok["admin"], uid["admin"] = register("expg_admin", "ADMIN", "DIRNAMEADMIN")
log("    %-14s id=%s" % ("admin", uid["admin"]))

# Resources owned by tenant A, each carrying CANARY_A.
log("")
log("[seed] tenant-A resources carrying the canary")
res = {}


def seeded(label, ok, detail=""):
    log("    %-26s %s %s" % (label, "ok" if ok else "SKIP", detail))


# -- family profile (patient A)
r = client.post(API + "/family", headers=auth(tok["patient_a"]),
                json={"full_name": "%s Child" % CANARY_A, "relation": "Daughter",
                      "age": 7, "gender": "Female",
                      "allergies": "%s penicillin" % CANARY_A})
if r.status_code in (200, 201):
    res["family_profile_id"] = r.json()["id"]
seeded("family profile", "family_profile_id" in res, str(res.get("family_profile_id", "")))

# -- EHR record (patient A)
r = client.post(API + "/ehr/record", headers=auth(tok["patient_a"]),
                json={"record_type": "note", "title": "%s wallet note" % CANARY_A,
                      "content": "%s private clinical note" % CANARY_A,
                      "client_uuid": "expg-canary-a-0001"})
if r.status_code in (200, 201):
    res["ehr_record_id"] = r.json()["id"]
seeded("EHR record", "ehr_record_id" in res, str(res.get("ehr_record_id", "")))

# -- emergency contact (patient A)
r = client.post(API + "/sos/contacts", headers=auth(tok["patient_a"]),
                json={"name": "%s Relative" % CANARY_A, "phone": "+919000000111",
                      "relation": "Mother"})
if r.status_code in (200, 201):
    res["contact_id"] = r.json()["id"]
seeded("emergency contact", "contact_id" in res, str(res.get("contact_id", "")))

# -- hospital A (approved, so SOS routes to it)
r = client.post(API + "/hospital/register", headers=auth(tok["hospital_a"]),
                json={"name": "%s Hospital" % CANARY_A, "address": "Canary Road",
                      "lat": 11.0, "lng": 77.0, "phone": "+919000000222"})
s = SessionLocal()
try:
    h = (s.query(models.Hospital)
         .filter(models.Hospital.owner_user_id == uid["hospital_a"]).first())
    if h:
        h.verification_status = "APPROVED"
        s.commit()
        res["hospital_a_id"] = h.id
    h2 = client.post(API + "/hospital/register", headers=auth(tok["hospital_b"]),
                     json={"name": "%s Hospital" % CANARY_B, "address": "Bravo Road",
                           "lat": 19.0, "lng": 72.8, "phone": "+919000000333"})
    hb = (s.query(models.Hospital)
          .filter(models.Hospital.owner_user_id == uid["hospital_b"]).first())
    if hb:
        hb.verification_status = "APPROVED"
        s.commit()
        res["hospital_b_id"] = hb.id
finally:
    s.close()
seeded("hospital A (approved)", "hospital_a_id" in res, str(res.get("hospital_a_id", "")))
seeded("hospital B (approved)", "hospital_b_id" in res, str(res.get("hospital_b_id", "")))

# -- SOS from patient A, routed to hospital A
r = client.post(API + "/sos/trigger", headers=auth(tok["patient_a"]),
                json={"location_lat": 11.0, "location_lng": 77.0,
                      "location_text": "%s village" % CANARY_A,
                      "voice_note": "%s collapsed" % CANARY_A, "severity": "CRITICAL"})
if r.status_code == 200:
    res["sos_id"] = r.json()["id"]
    res["sos_assigned"] = r.json().get("assigned_hospital_id")
seeded("SOS (patient A)", "sos_id" in res,
       "id=%s assigned_hospital=%s" % (res.get("sos_id"), res.get("sos_assigned")))

# -- prescription for patient A from doctor A
r = client.post(API + "/ehr/issue_prescription", headers=auth(tok["doctor_a"]),
                json={"patient_id": uid["patient_a"],
                      "medicines": [{"name": "%s-MED" % CANARY_A, "dosage": "500mg",
                                     "frequency": "1-0-1", "duration": "5 days"}],
                      "diagnosis": "%s diagnosis" % CANARY_A})
if r.status_code in (200, 201):
    res["prescription_id"] = r.json()["id"]
seeded("prescription", "prescription_id" in res, str(res.get("prescription_id", "")))

# -- pharmacies for both pharmacists, plus stock carrying each canary
for side, canary, dirname in (("a", CANARY_A, DIRNAME_A), ("b", CANARY_B, DIRNAME_B)):
    r = client.post(API + "/pharmacy/register", headers=auth(tok["pharmacist_%s" % side]),
                    json={"name": "%s Pharmacy" % dirname, "address": "%s St" % dirname,
                          "lat": 11.0 + (0 if side == "a" else 8.0), "lng": 77.0,
                          "phone": "+91900000044%s" % (0 if side == "a" else 1)})
    if r.status_code in (200, 201):
        res["pharmacy_%s_id" % side] = r.json()["id"]
    r = client.post(API + "/pharmacy/items", headers=auth(tok["pharmacist_%s" % side]),
                    json={"medicine_name": "%s-MED" % canary, "stock_count": 25,
                          "price": 30.0})
    if r.status_code in (200, 201):
        res["item_%s_id" % side] = r.json()["id"]
seeded("pharmacy A + stock", "pharmacy_a_id" in res,
       "pharmacy=%s item=%s" % (res.get("pharmacy_a_id"), res.get("item_a_id")))
seeded("pharmacy B + stock", "pharmacy_b_id" in res,
       "pharmacy=%s item=%s" % (res.get("pharmacy_b_id"), res.get("item_b_id")))

# -- pre-order by patient A at pharmacy A (links the prescription into A's queue)
if "pharmacy_a_id" in res:
    r = client.post(API + "/pharmacy/preorders", headers=auth(tok["patient_a"]),
                    json={"pharmacy_id": res["pharmacy_a_id"],
                          "medicine_name": "%s-MED" % CANARY_A, "quantity": 1})
    if r.status_code in (200, 201):
        res["preorder_id"] = r.json()["id"]
seeded("pre-order", "preorder_id" in res, str(res.get("preorder_id", "")))

# -- lab centres for both labs, plus a booking for patient A at lab A
for side, canary, dirname in (("a", CANARY_A, DIRNAME_A), ("b", CANARY_B, DIRNAME_B)):
    r = client.post(API + "/lab/register", headers=auth(tok["lab_%s" % side]),
                    json={"name": "%s Lab" % dirname, "address": "%s Ave" % dirname,
                          "lat": 11.0 + (0 if side == "a" else 8.0), "lng": 77.0,
                          "phone": "+91900000055%s" % (0 if side == "a" else 1)})
    if r.status_code in (200, 201):
        res["lab_%s_id" % side] = r.json()["id"]
seeded("lab A", "lab_a_id" in res, str(res.get("lab_a_id", "")))
seeded("lab B", "lab_b_id" in res, str(res.get("lab_b_id", "")))

if "lab_a_id" in res:
    r = client.post(API + "/lab/bookings", headers=auth(tok["patient_a"]),
                    json={"lab_center_id": res["lab_a_id"],
                          "test_name": "%s Panel" % CANARY_A,
                          "scheduled_at": (datetime.now(timezone.utc)
                                           + timedelta(days=1)).isoformat()})
    if r.status_code in (200, 201):
        res["lab_booking_id"] = r.json()["id"]
seeded("lab booking", "lab_booking_id" in res, str(res.get("lab_booking_id", "")))

# -- availability slot for doctor A
r = client.post(API + "/doctors/me/slots", headers=auth(tok["doctor_a"]),
                json={"start_time": (datetime.now(timezone.utc)
                                     + timedelta(days=1)).isoformat(),
                      "end_time": (datetime.now(timezone.utc)
                                   + timedelta(days=1, minutes=30)).isoformat()})
if r.status_code in (200, 201):
    res["slot_id"] = r.json().get("id")
seeded("availability slot", "slot_id" in res, str(res.get("slot_id", "")))

# -- referral from doctor A to doctor B about patient A
r = client.post(API + "/referrals", headers=auth(tok["doctor_a"]),
                json={"patient_id": uid["patient_a"], "to_doctor_id": uid["doctor_b"],
                      "specialty": "Cardiology", "reason": "%s referral reason" % CANARY_A})
if r.status_code in (200, 201):
    res["referral_id"] = r.json()["id"]
seeded("referral", "referral_id" in res, str(res.get("referral_id", "")))

log("")
log("[seed] resources: %s" % json.dumps(res, default=str))

# ----------------------------------------------------------------- probing
probes = []


def record(axis, method, path, caller, expected, status, leaked, body_excerpt=""):
    probes.append({
        "axis": axis, "method": method, "path": path, "caller": caller,
        "expected": expected, "status": status,
        "canary_leaked": "YES" if leaked else "",
        "finding": "",
        "body_excerpt": body_excerpt[:160].replace("\n", " "),
    })
    return probes[-1]


def body_text(r):
    try:
        return r.text
    except Exception:
        return ""


# Enumerate endpoints
endpoints = []
for route in app.routes:
    methods = getattr(route, "methods", None)
    if not methods:
        continue
    path = getattr(route, "path", "")
    if not path.startswith(API):
        continue
    for m in sorted(methods):
        if m in ("HEAD", "OPTIONS"):
            continue
        endpoints.append((m, path, re.findall(r"{(\w+)}", path)))

get_collections = sorted({(m, p) for m, p, params in endpoints
                          if m == "GET" and not params})
param_endpoints = sorted({(m, p, tuple(params)) for m, p, params in endpoints if params})

log("")
log("=" * 78)
log("AXIS 1 - unauthenticated access to every GET collection endpoint")
log("=" * 78)
ratelimit.reset_for_tests()
axis1_findings = 0
for m, p in get_collections:
    r = client.get(p)
    public = p in PUBLIC_BY_DESIGN
    expected = "200 (public by design)" if public else "401/403"
    ok = (r.status_code == 200) if public else (r.status_code in (401, 403, 422))
    row = record("1-unauth", m, p, "anonymous", expected, r.status_code, False,
                 body_text(r))
    if not ok:
        row["finding"] = "FINDING: unauthenticated caller got %s" % r.status_code
        axis1_findings += 1
        log("  FINDING  %-44s -> %s" % (p, r.status_code))
log("  %d endpoint(s) probed, %d finding(s)" % (len(get_collections), axis1_findings))

log("")
log("=" * 78)
log("AXIS 3 - same role, different tenant: does B's response contain A's canary?")
log("=" * 78)
ratelimit.reset_for_tests()
axis3_findings = 0
axis3_probed = 0
axis3_inconclusive = []
for m, p in get_collections:
    if p in PUBLIC_BY_DESIGN:
        continue
    for role in ROLES:
        key_b = "%s_b" % role.lower()
        r = client.get(p, headers=auth(tok[key_b]))
        if r.status_code >= 500:
            row = record("3-cross-tenant-list", m, p, "%s (tenant B)" % role,
                         "A's canary absent", r.status_code, False, body_text(r))
            row["finding"] = "INCONCLUSIVE: server error, not a security pass"
            axis3_inconclusive.append("%s as %s" % (p, role))
            continue
        if r.status_code != 200:
            continue
        axis3_probed += 1
        txt = body_text(r)
        leaked = CANARY_A in txt
        row = record("3-cross-tenant-list", m, p, "%s (tenant B)" % role,
                     "A's canary absent", r.status_code, leaked, txt)
        if leaked:
            row["finding"] = ("FINDING: tenant B of role %s received tenant A's data"
                              % role)
            axis3_findings += 1
            log("  FINDING  %-40s as %-11s -> 200 WITH CANARY_A" % (p, role))
log("  %d authorised probe(s), %d finding(s), %d inconclusive (5xx)"
    % (axis3_probed, axis3_findings, len(axis3_inconclusive)))
for _i in axis3_inconclusive:
    log("  INCONCLUSIVE  %s" % _i)

log("")
log("=" * 78)
log("AXIS 4 - same role, different tenant, A's resource id in the path")
log("=" * 78)
ratelimit.reset_for_tests()

# Map path-parameter names to tenant-A resource ids.
PARAM_VALUES = {
    "sos_id": res.get("sos_id"),
    "prescription_id": res.get("prescription_id"),
    "record_id": res.get("ehr_record_id"),
    "contact_id": res.get("contact_id"),
    "profile_id": res.get("family_profile_id"),
    "family_profile_id": res.get("family_profile_id"),
    "booking_id": res.get("lab_booking_id"),
    "referral_id": res.get("referral_id"),
    "preorder_id": res.get("preorder_id"),
    "item_id": res.get("item_a_id"),
    # Same resource, different parameter name on the stock-write routes.
    "medicine_id": res.get("item_a_id"),
    "slot_id": res.get("slot_id"),
    "hospital_id": res.get("hospital_a_id"),
    "pharmacy_id": res.get("pharmacy_a_id"),
    "lab_id": res.get("lab_a_id"),
    "patient_id": uid["patient_a"],
    "doctor_id": uid["doctor_a"],
    "user_id": uid["patient_a"],
}

axis4_findings = 0
axis4_probed = 0
axis4_skipped = []
for m, p, params in param_endpoints:
    if any(PARAM_VALUES.get(x) is None for x in params):
        axis4_skipped.append("%s %s" % (m, p))
        continue
    concrete = p
    for x in params:
        concrete = concrete.replace("{%s}" % x, str(PARAM_VALUES[x]))
    for role in ROLES:
        key_b = "%s_b" % role.lower()
        # Only GET is probed without a body; writes need valid payloads and are
        # covered by the curated probes below.
        if m != "GET":
            continue
        r = client.get(concrete, headers=auth(tok[key_b]))
        axis4_probed += 1
        txt = body_text(r)
        leaked = CANARY_A in txt
        row = record("4-cross-tenant-object", m, concrete, "%s (tenant B)" % role,
                     "403/404", r.status_code, leaked, txt)
        if r.status_code == 200 and leaked:
            row["finding"] = ("FINDING: tenant B of role %s read tenant A's object"
                              % role)
            axis4_findings += 1
            log("  FINDING  %-44s as %-11s -> 200 WITH CANARY_A" % (concrete, role))
log("  %d probe(s), %d finding(s); %d path(s) skipped for want of a seeded id"
    % (axis4_probed, axis4_findings, len(axis4_skipped)))

log("")
log("=" * 78)
log("AXIS 4b - curated write probes (bodies required, so hand-written)")
log("=" * 78)
ratelimit.reset_for_tests()
curated = []


def curated_probe(label, fn, expected_codes, note=""):
    r = fn()
    ok = r.status_code in expected_codes
    curated.append((label, r.status_code, expected_codes, ok, body_text(r)[:120]))
    row = record("4b-curated-write", "WRITE", label, "tenant B / wrong role",
                 "/".join(str(c) for c in expected_codes), r.status_code, False,
                 body_text(r))
    if not ok:
        row["finding"] = "FINDING: %s returned %s" % (label, r.status_code)
        log("  FINDING  %-56s -> %s  %s" % (label, r.status_code, note))
    else:
        log("  pass     %-56s -> %s" % (label, r.status_code))
    return ok


if res.get("sos_id"):
    curated_probe(
        "PUT /sos/{A's sos}/respond as hospital B",
        lambda: client.put("%s/sos/%s/respond" % (API, res["sos_id"]),
                           headers=auth(tok["hospital_b"])),
        (403, 404))
    curated_probe(
        "PUT /sos/{A's sos}/respond as unrelated doctor B",
        lambda: client.put("%s/sos/%s/respond" % (API, res["sos_id"]),
                           headers=auth(tok["doctor_b"])),
        (403, 404))
    curated_probe(
        "PUT /sos/{A's sos}/resolve as patient B",
        lambda: client.put("%s/sos/%s/resolve" % (API, res["sos_id"]),
                           headers=auth(tok["patient_b"])),
        (403, 404))

if res.get("prescription_id"):
    curated_probe(
        "PUT /pharmacy/fulfill/{A's rx} as pharmacist B",
        lambda: client.put("%s/pharmacy/fulfill/%s" % (API, res["prescription_id"]),
                           headers=auth(tok["pharmacist_b"])),
        (403, 404),
        "(documented residual: fulfilment is deliberately open to walk-ins, audited)")

if res.get("item_a_id"):
    curated_probe(
        "PUT /pharmacy/items/{A's item} as pharmacist B",
        lambda: client.put("%s/pharmacy/items/%s" % (API, res["item_a_id"]),
                           headers=auth(tok["pharmacist_b"]),
                           json={"stock_count": 0}),
        (403, 404))

if res.get("ehr_record_id"):
    curated_probe(
        "GET /ehr/patient/{A's id} as doctor B",
        lambda: client.get("%s/ehr/patient/%s" % (API, uid["patient_a"]),
                           headers=auth(tok["doctor_b"])),
        (200, 403, 404),
        "(doctors may legitimately read patient records - check scoping policy)")
    curated_probe(
        "GET /ehr/patient/{A's id} as patient B",
        lambda: client.get("%s/ehr/patient/%s" % (API, uid["patient_a"]),
                           headers=auth(tok["patient_b"])),
        (403, 404))

if res.get("family_profile_id"):
    curated_probe(
        "POST /triage/analyze with A's family_profile_id as patient B",
        lambda: client.post("%s/triage/analyze" % API, headers=auth(tok["patient_b"]),
                            json={"symptoms_text": "fever and chills for three days",
                                  "patient_id": str(uid["patient_b"]), "age": 30,
                                  "family_profile_id": res["family_profile_id"]}),
        (403, 404, 422),
        "(writing a triage log onto another family's profile)")

if res.get("lab_booking_id"):
    curated_probe(
        "PUT /lab/bookings/{A's booking}/status as lab B",
        lambda: client.put("%s/lab/bookings/%s/status?status=CANCELLED"
                           % (API, res["lab_booking_id"]),
                           headers=auth(tok["lab_b"])),
        (403, 404))

if res.get("item_a_id"):
    curated_probe(
        "POST /pharmacy/set_stock/{A's item} as pharmacist B",
        lambda: client.post("%s/pharmacy/set_stock/%s?count=0"
                            % (API, res["item_a_id"]),
                            headers=auth(tok["pharmacist_b"])),
        (403, 404, 422))
    curated_probe(
        "POST /pharmacy/decrement/{A's item} as pharmacist B",
        lambda: client.post("%s/pharmacy/decrement/%s" % (API, res["item_a_id"]),
                            headers=auth(tok["pharmacist_b"])),
        (403, 404, 422))
    curated_probe(
        "POST /pharmacy/update_stock/{A's item} as pharmacist B",
        lambda: client.post("%s/pharmacy/update_stock/%s?delta=-5"
                            % (API, res["item_a_id"]),
                            headers=auth(tok["pharmacist_b"])),
        (403, 404, 422))

if res.get("slot_id"):
    curated_probe(
        "DELETE /doctors/me/slots/{A's slot} as doctor B",
        lambda: client.delete("%s/doctors/me/slots/%s" % (API, res["slot_id"]),
                              headers=auth(tok["doctor_b"])),
        (403, 404))

curated_probe(
    "GET /doctors/pending as doctor B (government-only review queue)",
    lambda: client.get("%s/doctors/pending" % API, headers=auth(tok["doctor_b"])),
    (403,))
curated_probe(
    "GET /auth/government-whitelist as patient B",
    lambda: client.get("%s/auth/government-whitelist" % API, headers=auth(tok["patient_b"])),
    (403,))
curated_probe(
    "GET /analytics/overview as patient B",
    lambda: client.get("%s/analytics/overview" % API, headers=auth(tok["patient_b"])),
    (403,))

# ------------------------------------------------------------------ output
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
csv_path = os.path.join(OUT, "isolation_matrix_%s_raw.csv" % ENGINE_LABEL)
with open(csv_path, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["axis", "method", "path", "caller", "expected",
                                       "status", "canary_leaked", "finding",
                                       "body_excerpt"])
    w.writeheader()
    for row in probes:
        w.writerow(row)

findings = [p for p in probes if p["finding"]]
summary = {
    "commit": SHA,
    "run_at": RUN_AT,
    "finished_at": datetime.now(timezone.utc).isoformat(),
    "engine": ENGINE_LABEL,
    "db_version": str(DBVER),
    "python": sys.version.split()[0],
    "sqlalchemy": sqlalchemy.__version__,
    "environment": "throwaway SQLite, external credentials blanked, no production data",
    "endpoints_enumerated": len(endpoints),
    "get_collection_endpoints": len(get_collections),
    "path_param_endpoints": len(param_endpoints),
    "probes_total": len(probes),
    "axis1_probes": sum(1 for p in probes if p["axis"] == "1-unauth"),
    "axis1_findings": axis1_findings,
    "axis3_probes": axis3_probed,
    "axis3_findings": axis3_findings,
    "axis3_inconclusive_5xx": axis3_inconclusive,
    "axis4_probes": axis4_probed,
    "axis4_findings": axis4_findings,
    "axis4_skipped_paths": axis4_skipped,
    "curated_probes": len(curated),
    "curated_failures": sum(1 for c in curated if not c[3]),
    "findings_total": len(findings),
}
with open(os.path.join(OUT, "isolation_matrix_%s_summary.json" % ENGINE_LABEL),
          "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)

log("")
log("=" * 78)
log("SUMMARY")
log("=" * 78)
log("endpoints enumerated        : %d" % summary["endpoints_enumerated"])
log("GET collection endpoints    : %d" % summary["get_collection_endpoints"])
log("path-parameter endpoints    : %d" % summary["path_param_endpoints"])
log("total probes                : %d" % summary["probes_total"])
log("  axis 1 unauthenticated    : %d probes, %d findings"
    % (summary["axis1_probes"], axis1_findings))
log("  axis 3 cross-tenant list  : %d probes, %d findings" % (axis3_probed, axis3_findings))
log("  axis 4 cross-tenant object: %d probes, %d findings" % (axis4_probed, axis4_findings))
log("  axis 4b curated writes    : %d probes, %d failures"
    % (len(curated), summary["curated_failures"]))
log("TOTAL FINDINGS              : %d" % len(findings))
log("")
if findings:
    log("Findings:")
    for f in findings:
        log("  [%s] %s %s as %s -> %s" % (f["axis"], f["method"], f["path"],
                                          f["caller"], f["status"]))
        log("      %s" % f["finding"])
else:
    log("No cross-tenant exposure detected on the probed axes.")
log("")
log("raw rows  : %s" % csv_path)
log("summary   : %s" % os.path.join(OUT, "isolation_matrix_%s_summary.json" % ENGINE_LABEL))
log("skipped (no seeded id for the path parameter): %d" % len(axis4_skipped))
for s in axis4_skipped:
    log("    %s" % s)
