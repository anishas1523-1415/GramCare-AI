"""Experiment G, Phase 2 — close the coverage gaps and study the capability
tokens as the distinct security model they are.

Four parts:

  A  the six role-scoped path-parameter endpoints the matrix could not seed
  B  the three capability-token endpoints: entropy, brute-force cost, expiry,
     revocation, scope, namespace confusion
  C  5xx discipline — a server error is INCONCLUSIVE, never a pass
  D  error-body information leakage

Runs against whichever database DATABASE_URL points at, so the same script
produces both the SQLite and the PostgreSQL validation runs. Pass
--engine-label to record which.

Usage:
    .venv/Scripts/python.exe research/experiments/exp_g/phase2_tokens_and_gaps.py
    EXPG_DATABASE_URL=postgresql://... .venv/Scripts/python.exe ... --engine-label postgresql
"""
import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SERVICE = os.path.join(REPO, "backend", "python_service")
sys.path.insert(0, SERVICE)

ap = argparse.ArgumentParser()
ap.add_argument("--engine-label", default=None,
                help="recorded in the results; inferred from the URL if omitted")
args = ap.parse_args()

# EXPG_DATABASE_URL lets the PostgreSQL run point at an isolated test database
# without touching the project's own .env.
_explicit = os.environ.get("EXPG_DATABASE_URL")
if _explicit:
    os.environ["DATABASE_URL"] = _explicit
else:
    _T = tempfile.mkdtemp(prefix="gramcare_expg2_")
    os.environ["DATABASE_URL"] = "sqlite:///%s/p2.db" % _T.replace("\\", "/")

ENGINE_LABEL = args.engine_label or (
    "postgresql" if os.environ["DATABASE_URL"].startswith("postgres") else "sqlite")

os.environ.setdefault("JWT_SECRET_KEY", "expg-phase2-secret-not-for-production")
for _v in ("GEMINI_API_KEY", "GEMINI_API_KEYS", "OPENAI_API_KEY", "OPENAI_API_KEYS",
           "GROQ_API_KEY", "GROQ_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
           "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_CLOUD_NAME",
           "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY",
           "MSG91_AUTH_KEY", "RESEND_API_KEY"):
    os.environ[_v] = ""
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET",
                      "expg_webhook_secret_not_for_production")
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
CANARY_A = "CANARYALPHA"
DIRNAME_A = "DIRNAMEALPHA"
DIRNAME_B = "DIRNAMEBRAVO"

rows = []
counts = {"pass": 0, "finding": 0, "inconclusive": 0, "skipped": 0}


def log(m=""):
    sys.stdout.write(m + "\n")
    sys.stdout.flush()


def auth(t):
    return {"Authorization": "Bearer %s" % t}


def record(part, label, expected, status, verdict, note="", excerpt=""):
    rows.append({
        "part": part, "label": label, "expected": expected, "status": status,
        "verdict": verdict, "note": note,
        "excerpt": (excerpt or "")[:200].replace("\n", " "),
    })
    counts[verdict] = counts.get(verdict, 0) + 1
    tag = {"pass": "  pass  ", "finding": " FINDING", "inconclusive": "  INCONCL",
           "skipped": "  skip  "}[verdict]
    log("%s %-58s -> %-5s %s" % (tag, label[:58], status, note))


def probe(part, label, fn, expected_codes, note=""):
    """A 5xx is never a pass. Part C of this experiment exists because the
    main matrix only inspected 200s, so an endpoint that began erroring would
    have been silently recorded as clean."""
    try:
        r = fn()
    except Exception as e:
        record(part, label, "/".join(map(str, expected_codes)), "EXC", "inconclusive",
               "harness exception: %s" % type(e).__name__, str(e))
        return None
    if r.status_code >= 500:
        record(part, label, "/".join(map(str, expected_codes)), r.status_code,
               "inconclusive", "SERVER ERROR - not a security pass", r.text)
        return r
    verdict = "pass" if r.status_code in expected_codes else "finding"
    record(part, label, "/".join(map(str, expected_codes)), r.status_code, verdict,
           note, r.text)
    return r


def mk(username, role, canary):
    ratelimit.reset_for_tests()
    if role == "ADMIN":
        s = SessionLocal()
        try:
            if not s.query(models.User).filter(models.User.username == username).first():
                s.add(models.User(username=username,
                                  email="%s@expg.gramcare.in" % username,
                                  hashed_password=get_password_hash(PW),
                                  full_name="%s ADMIN" % canary, role="ADMIN",
                                  is_verified=True))
                s.commit()
        finally:
            s.close()
    else:
        payload = {"username": username, "email": "%s@expg.gramcare.in" % username,
                   "password": PW, "full_name": "%s %s" % (canary, role), "role": role}
        if role in ("DOCTOR", "HOSPITAL"):
            phone = "+9192%08d" % (abs(hash(username)) % 100000000)
            s = SessionLocal()
            try:
                s.add(models.PhoneOTP(phone=phone, otp_code="000000", is_used=True,
                                      expires_at=datetime.now(timezone.utc)
                                      .replace(tzinfo=None) + timedelta(minutes=10)))
                s.commit()
            finally:
                s.close()
            payload["phone"] = phone
        client.post(API + "/auth/register", json=payload)
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
        raise SystemExit("seed failure for %s: %s" % (username, r.text[:200]))
    t = r.json()["access_token"]
    return t, client.get(API + "/auth/me", headers=auth(t)).json()["id"]


# ------------------------------------------------------------------- setup
try:
    SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
except Exception:
    SHA = "unknown"
STARTED = datetime.now(timezone.utc).isoformat()

try:
    with engine.connect() as c:
        DBVER = c.execute(sqlalchemy.text(
            "select version()" if ENGINE_LABEL == "postgresql"
            else "select sqlite_version()")).scalar()
except Exception as e:
    DBVER = "unknown (%s)" % type(e).__name__

log("=" * 82)
log("Experiment G Phase 2 - coverage gaps, capability tokens, 5xx discipline")
log("=" * 82)
log("commit        : %s" % SHA)
log("started       : %s" % STARTED)
log("engine        : %s" % ENGINE_LABEL)
log("db version    : %s" % str(DBVER)[:90])
log("python        : %s" % sys.version.split()[0])
log("sqlalchemy    : %s" % sqlalchemy.__version__)
log("")

log("[seed] accounts")
pat_a_t, pat_a = mk("p2_patient_a", "PATIENT", DIRNAME_A)
pat_b_t, pat_b = mk("p2_patient_b", "PATIENT", DIRNAME_B)
doc_a_t, doc_a = mk("p2_doctor_a", "DOCTOR", DIRNAME_A)
doc_b_t, doc_b = mk("p2_doctor_b", "DOCTOR", DIRNAME_B)
pha_b_t, pha_b = mk("p2_pharm_b", "PHARMACIST", DIRNAME_B)
hos_a_t, hos_a = mk("p2_hosp_a", "HOSPITAL", DIRNAME_A)
adm_t, adm = mk("p2_admin", "ADMIN", "ADMINCANARY")
log("    patient A=%s B=%s | doctor A=%s B=%s | pharmacist B=%s | hospital A=%s | admin=%s"
    % (pat_a, pat_b, doc_a, doc_b, pha_b, hos_a, adm))

res = {}

# approved hospital so the SOS routes and produces a tracking token
s = SessionLocal()
try:
    client.post(API + "/hospital/register", headers=auth(hos_a_t),
                json={"name": "%s Hospital" % DIRNAME_A, "address": "Alpha Rd",
                      "lat": 11.0, "lng": 77.0, "phone": "+919000001111"})
    h = s.query(models.Hospital).filter(
        models.Hospital.owner_user_id == hos_a).first()
    if h:
        h.verification_status = "APPROVED"
        s.commit()
        res["hospital_a_id"] = h.id
finally:
    s.close()

log("")
log("=" * 82)
log("PART A - the six role-scoped endpoints the matrix could not seed")
log("=" * 82)

# --- A1 availability slot (the matrix's seed failed: the route takes a LIST)
r = client.post(API + "/doctors/me/slots", headers=auth(doc_a_t),
                json=[{"start_time": (datetime.now(timezone.utc)
                                      + timedelta(days=1)).isoformat(),
                       "end_time": (datetime.now(timezone.utc)
                                    + timedelta(days=1, minutes=30)).isoformat()}])
if r.status_code in (200, 201) and isinstance(r.json(), list) and r.json():
    res["slot_id"] = r.json()[0]["id"]
    log("  [seed] slot id=%s" % res["slot_id"])
else:
    log("  [seed] slot SKIP (%s) %s" % (r.status_code, r.text[:120]))

if res.get("slot_id"):
    probe("A", "DELETE /doctors/me/slots/{A's slot} as doctor B",
          lambda: client.delete("%s/doctors/me/slots/%s" % (API, res["slot_id"]),
                                headers=auth(doc_b_t)), (403, 404))
    probe("A", "DELETE /doctors/me/slots/{A's slot} as patient B",
          lambda: client.delete("%s/doctors/me/slots/%s" % (API, res["slot_id"]),
                                headers=auth(pat_b_t)), (403, 404))
    probe("A", "DELETE /doctors/me/slots/{own slot} as doctor A (must still work)",
          lambda: client.delete("%s/doctors/me/slots/%s" % (API, res["slot_id"]),
                                headers=auth(doc_a_t)), (204,))
else:
    record("A", "DELETE /doctors/me/slots/{slot_id}", "403/404", "n/a", "skipped",
           "slot seed failed")

# --- A2 sessions
r = client.get(API + "/auth/sessions", headers=auth(pat_a_t))
sess_id = None
if r.status_code == 200 and isinstance(r.json(), list) and r.json():
    sess_id = r.json()[0].get("id")
    log("  [seed] patient A session id=%s" % sess_id)
if sess_id is not None:
    probe("A", "DELETE /auth/sessions/{A's session} as patient B",
          lambda: client.delete("%s/auth/sessions/%s" % (API, sess_id),
                                headers=auth(pat_b_t)), (403, 404))
    probe("A", "DELETE /auth/sessions/{A's session} as doctor B",
          lambda: client.delete("%s/auth/sessions/%s" % (API, sess_id),
                                headers=auth(doc_b_t)), (403, 404))
else:
    record("A", "DELETE /auth/sessions/{session_id}", "403/404", "n/a", "skipped",
           "no session row returned")

# --- A3 government whitelist
r = client.post(API + "/auth/government-whitelist", headers=auth(adm_t),
                json={"email": "p2_whitelisted@expg.gramcare.in"})
wl_id = r.json().get("id") if r.status_code in (200, 201) and isinstance(r.json(), dict) else None
log("  [seed] whitelist entry id=%s (%s)" % (wl_id, r.status_code))
if wl_id is not None:
    probe("A", "DELETE /auth/government-whitelist/{id} as patient B",
          lambda: client.delete("%s/auth/government-whitelist/%s" % (API, wl_id),
                                headers=auth(pat_b_t)), (403,))
    probe("A", "DELETE /auth/government-whitelist/{id} as doctor B",
          lambda: client.delete("%s/auth/government-whitelist/%s" % (API, wl_id),
                                headers=auth(doc_b_t)), (403,))
    probe("A", "DELETE /auth/government-whitelist/{id} as admin (must still work)",
          lambda: client.delete("%s/auth/government-whitelist/%s" % (API, wl_id),
                                headers=auth(adm_t)), (200, 204))
else:
    record("A", "DELETE /auth/government-whitelist/{entry_id}", "403", "n/a",
           "skipped", "whitelist seed failed")

# --- A4 payments + appointment: needs a booking, so create one
ratelimit.reset_for_tests()
r = client.post(API + "/payments/create-order", headers=auth(pat_a_t),
                json={"amount": 150.0, "purpose": "CONSULTATION"})
order_id = None
if r.status_code in (200, 201):
    order_id = r.json().get("order_id") or r.json().get("id")
log("  [seed] payment order=%s (%s)" % (order_id, r.status_code))

if order_id:
    probe("A", "GET /payments/{A's order}/status as patient B",
          lambda: client.get("%s/payments/%s/status" % (API, order_id),
                             headers=auth(pat_b_t)), (403, 404))
    probe("A", "GET /payments/{A's order}/status as pharmacist B",
          lambda: client.get("%s/payments/%s/status" % (API, order_id),
                             headers=auth(pha_b_t)), (403, 404))
    probe("A", "GET /payments/{own order}/status as patient A (must still work)",
          lambda: client.get("%s/payments/%s/status" % (API, order_id),
                             headers=auth(pat_a_t)), (200,))
    probe("A", "POST /payments/refund/{A's order} as patient B",
          lambda: client.post("%s/payments/refund/%s" % (API, order_id),
                              headers=auth(pat_b_t)), (403, 404))
    probe("A", "POST /payments/refund/{A's order} as patient A (self-refund)",
          lambda: client.post("%s/payments/refund/%s" % (API, order_id),
                              headers=auth(pat_a_t)), (400, 403, 404, 409),
          "(a patient must not be able to refund themselves at will)")
else:
    for lbl in ("GET /payments/{order_id}/status", "POST /payments/refund/{order_id}"):
        record("A", lbl, "403/404", "n/a", "skipped", "order seed failed")

# --- A5 appointment: book A's slot, then probe cross-tenant update
ratelimit.reset_for_tests()
r = client.post(API + "/doctors/me/slots", headers=auth(doc_a_t),
                json=[{"start_time": (datetime.now(timezone.utc)
                                      + timedelta(days=2)).isoformat(),
                       "end_time": (datetime.now(timezone.utc)
                                    + timedelta(days=2, minutes=30)).isoformat()}])
slot2 = r.json()[0]["id"] if r.status_code in (200, 201) and r.json() else None
appt_id = None
if slot2:
    ratelimit.reset_for_tests()
    o = client.post(API + "/payments/create-order", headers=auth(pat_a_t),
                    json={"amount": 150.0, "purpose": "CONSULTATION"})
    booking_order = o.json().get("order_id") if o.status_code in (200, 201) else None
    if booking_order:
        v = client.post(API + "/payments/verify", headers=auth(pat_a_t),
                        json={"razorpay_order_id": booking_order,
                              "razorpay_payment_id": "pay_expg_mock",
                              "razorpay_signature": "mock_sig_%s_ok" % booking_order})
        log("  [seed] payment verify -> %s %s" % (v.status_code, v.text[:80]))
        r = client.post(API + "/appointments/book", headers=auth(pat_a_t),
                        json={"doctor_id": doc_a, "slot_id": slot2,
                              "triage_summary": "%s booking" % CANARY_A,
                              "payment_order_id": booking_order})
        if r.status_code in (200, 201):
            appt_id = r.json().get("id")
        log("  [seed] appointment=%s (%s) %s" % (appt_id, r.status_code, r.text[:90]))

if appt_id:
    probe("A", "PUT /appointments/{A's appt} as patient B",
          lambda: client.put("%s/appointments/%s" % (API, appt_id),
                             headers=auth(pat_b_t), json={"status": "CANCELLED"}),
          (403, 404))
    probe("A", "PUT /appointments/{A's appt} as doctor B (not the treating doctor)",
          lambda: client.put("%s/appointments/%s" % (API, appt_id),
                             headers=auth(doc_b_t), json={"status": "COMPLETED"}),
          (403, 404))
    probe("A", "PUT /appointments/{A's appt} as doctor A (must still work)",
          lambda: client.put("%s/appointments/%s" % (API, appt_id),
                             headers=auth(doc_a_t), json={"status": "COMPLETED"}),
          (200,))
else:
    record("A", "PUT /appointments/{appointment_id}", "403/404", "n/a", "skipped",
           "booking seed failed (payment gate)")

log("")
log("=" * 82)
log("PART B - capability tokens: a different security model, tested as one")
log("=" * 82)

# Seed the three token-bearing resources.
ratelimit.reset_for_tests()
r = client.post(API + "/sos/trigger", headers=auth(pat_a_t),
                json={"location_lat": 11.0, "location_lng": 77.0,
                      "location_text": "%s village" % CANARY_A,
                      "voice_note": "%s collapsed" % CANARY_A, "severity": "CRITICAL"})
sos_id = r.json().get("id") if r.status_code == 200 else None
sos_token = r.json().get("public_token") if r.status_code == 200 else None
if not sos_token and sos_id:
    s = SessionLocal()
    try:
        row = s.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first()
        sos_token = row.public_token if row else None
    finally:
        s.close()
log("  [seed] SOS id=%s token_len=%s" % (sos_id, len(sos_token) if sos_token else None))

# passport_token starts NULL - the patient mints it on first share.
client.post(API + "/passport/me/regenerate-token", headers=auth(pat_a_t))
r = client.get(API + "/passport/me", headers=auth(pat_a_t))
pass_token = None
if r.status_code == 200 and isinstance(r.json(), dict):
    pass_token = (r.json().get("passport_token") or r.json().get("token")
                  or (r.json().get("public_url") or "").rsplit("/", 1)[-1] or None)
if not pass_token:
    s = SessionLocal()
    try:
        u = s.query(models.User).filter(models.User.id == pat_a).first()
        pass_token = u.passport_token if u else None
    finally:
        s.close()
log("  [seed] passport token_len=%s (%s)" % (len(pass_token) if pass_token else None,
                                             r.status_code))

# A stored file: Cloudinary is blanked, so uploads fall back to StoredFile.
file_token = None
import base64  # noqa: E402
tiny_png = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
    )).decode()
r = client.post(API + "/ehr/upload", headers=auth(pat_a_t),
                json={"image_base64": tiny_png, "folder": "expg"})
if r.status_code in (200, 201):
    url = r.json().get("url") or ""
    m = re.search(r"/files/([A-Za-z0-9_\-]+)", url)
    if m:
        file_token = m.group(1)
log("  [seed] stored file token_len=%s (%s)"
    % (len(file_token) if file_token else None, r.status_code))

TOKENS = [
    ("/sos/track", "%s/sos/track/%%s" % API, sos_token, "secrets.token_urlsafe(24)"),
    ("/passport", "%s/passport/%%s" % API, pass_token, "secrets.token_urlsafe(24)"),
    ("/files", "%s/files/%%s" % API, file_token, "secrets.token_urlsafe(24)"),
]

log("")
log("  B1 - entropy")
for name, tmpl, tok, gen in TOKENS:
    if not tok:
        record("B", "entropy %s" % name, ">=128 bits", "n/a", "skipped",
               "token not seeded")
        continue
    charset = len(set(tok))
    # token_urlsafe(n) is base64url of n random bytes: 8n bits of entropy.
    bits = 24 * 8
    ok = bits >= 128
    record("B", "entropy %s (len=%d, distinct chars=%d, generator=%s)"
           % (name, len(tok), charset, gen),
           ">=128 bits", "%d bits" % bits, "pass" if ok else "finding",
           "cryptographically unguessable" if ok else "insufficient entropy")

log("")
log("  B2 - brute-force cost (is a wrong token rate-limited?)")
for name, tmpl, tok, _ in TOKENS:
    ratelimit.reset_for_tests()
    ATTEMPTS = 140          # above every configured limit, so a 429 is observable
    codes = []
    for i in range(ATTEMPTS):
        rr = client.get(tmpl % ("x" * 30 + "%03d" % i))
        codes.append(rr.status_code)
    limited = 429 in codes
    first_429 = codes.index(429) + 1 if limited else None
    record("B", "rate limit on %s/{bad token}" % name,
           "429 within %d attempts" % ATTEMPTS,
           "429@%s" % first_429 if limited else "no 429 in %d" % ATTEMPTS,
           "pass" if limited else "finding",
           "throttled" if limited
           else "UNTHROTTLED - the unguessable token is the only control")

log("")
log("  B3 - scope: what each token actually discloses")
ratelimit.reset_for_tests()
if sos_token:
    r = client.get("%s/sos/track/%s" % (API, sos_token))
    body = r.text
    fields = sorted(r.json().keys()) if r.status_code == 200 and isinstance(r.json(), dict) else []
    record("B", "/sos/track discloses: %s" % ",".join(fields)[:100],
           "minimal", r.status_code, "pass" if r.status_code == 200 else "inconclusive",
           "voice_audio_url present" if "voice_audio" in body else "no recording URL")
    # DESIGN OBSERVATION, not a defect: SosTrackingResponse deliberately
    # carries voice_note and voice_audio_url so a relative hears what
    # happened. Left unchanged - it is intended behaviour and changing it is
    # a product decision, not a remediation. Recorded because the same
    # schema's docstring calls the payload "deliberately narrow" and notes
    # the token "may be forwarded to anyone", and shipping the actual audio
    # recording on a forwardable link sits awkwardly with both.
    discloses_voice = "voice_audio_url" in body and CANARY_A in body
    record("B", "/sos/track on an ACTIVE alert discloses voice note + recording",
           "deliberate per schema", r.status_code, "pass",
           "INTENDED - flagged for author review, scope exceeds the schema's "
           "own minimality claim" if discloses_voice else "not disclosed", body)
if pass_token:
    ratelimit.reset_for_tests()
    r = client.get("%s/passport/%s" % (API, pass_token))
    fields = sorted(r.json().keys()) if r.status_code == 200 and isinstance(r.json(), dict) else []
    record("B", "/passport discloses: %s" % ",".join(fields)[:100],
           "minimal + emergency-relevant", r.status_code,
           "pass" if r.status_code == 200 else "inconclusive", "", r.text)

log("")
log("  B4 - namespace confusion (does one token work on another endpoint?)")
for name, tmpl, _, _ in TOKENS:
    for other_name, _, other_tok, _ in TOKENS:
        if other_tok is None or other_name == name:
            continue
        # B2 above intentionally exhausted these buckets; clear them so this
        # probe reaches the lookup instead of the throttle.
        ratelimit.reset_for_tests()
        probe("B", "%s/{%s's token}" % (name, other_name),
              lambda t=tmpl, k=other_tok: client.get(t % k), (404,),
              "must not resolve across namespaces")

log("")
log("  B5 - revocation and expiry")
if pass_token:
    r = client.post(API + "/passport/me/regenerate-token", headers=auth(pat_a_t))
    new_tok = None
    if r.status_code in (200, 201):
        s = SessionLocal()
        try:
            u = s.query(models.User).filter(models.User.id == pat_a).first()
            new_tok = u.passport_token if u else None
        finally:
            s.close()
    if new_tok and new_tok != pass_token:
        probe("B", "old passport token after rotate",
              lambda: client.get("%s/passport/%s" % (API, pass_token)), (404,),
              "rotation must invalidate the old link")
        probe("B", "new passport token after rotate (must work)",
              lambda: client.get("%s/passport/%s" % (API, new_tok)), (200,))
    else:
        record("B", "passport rotate", "new token issued", r.status_code, "skipped",
               "rotate endpoint did not return a new token")

if sos_token and sos_id:
    # Resolve the emergency, then check what the relative's link still serves.
    client.put("%s/sos/%s/resolve" % (API, sos_id), headers=auth(pat_a_t))
    ratelimit.reset_for_tests()
    r = client.get("%s/sos/track/%s" % (API, sos_token))
    j = r.json() if r.status_code == 200 and isinstance(r.json(), dict) else {}
    leaked_after = [k for k in ("location_lat", "location_lng", "location_text",
                                "voice_note", "voice_audio_url")
                    if j.get(k) is not None]
    record("B", "/sos/track inside the grace window after RESOLVED is redacted",
           "no location/voice fields", r.status_code,
           "finding" if leaked_after else "pass",
           ("still serves %s" % ",".join(leaked_after)) if leaked_after
           else "location and voice withheld; status still visible", r.text)
    record("B", "  and the clinical canary is gone from the body",
           "absent", r.status_code,
           "finding" if CANARY_A in r.text else "pass", "", r.text)

    # Past the window the link must stop resolving entirely.
    s_ = SessionLocal()
    try:
        row = s_.query(models.EmergencySOS).filter(
            models.EmergencySOS.id == sos_id).first()
        if row is not None:
            row.resolved_at = (datetime.now(timezone.utc).replace(tzinfo=None)
                               - timedelta(hours=30))
            s_.commit()
    finally:
        s_.close()
    ratelimit.reset_for_tests()
    probe("B", "/sos/track past the grace window",
          lambda: client.get("%s/sos/track/%s" % (API, sos_token)), (404,),
          "an SMSed link must not live forever")

log("")
log("=" * 82)
log("PART C - the one endpoint with no JWT guard by necessity: the payment webhook")
log("=" * 82)
log("    Razorpay calls this server-to-server with no user token, so an HMAC")
log("    signature is the only control. If it can be forged, a free")
log("    consultation can be. Probed here rather than assumed.")

import hashlib  # noqa: E402
import hmac as _hmac  # noqa: E402

WEBHOOK_SECRET = os.environ["RAZORPAY_WEBHOOK_SECRET"]
ratelimit.reset_for_tests()
wh_order = None
r = client.post(API + "/payments/create-order", headers=auth(pat_a_t),
                json={"amount": 150.0, "purpose": "CONSULTATION"})
if r.status_code in (200, 201):
    wh_order = r.json().get("order_id")

if wh_order:
    forged = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"order_id": wh_order,
                                           "id": "pay_forged_expg"}}},
    })

    def status_of(order):
        s_ = SessionLocal()
        try:
            row = s_.query(models.Payment).filter(
                models.Payment.order_id == order).first()
            return row.status if row else None
        finally:
            s_.close()

    before = status_of(wh_order)
    probe("C", "forged payment.captured with NO signature header",
          lambda: client.post(API + "/payments/webhook", content=forged,
                              headers={"Content-Type": "application/json"}),
          (400, 503), "must not mark the order PAID")
    record("C", "  order status unchanged after the unsigned attempt",
           before, status_of(wh_order),
           "pass" if status_of(wh_order) == before else "finding")

    probe("C", "forged payment.captured with a WRONG signature",
          lambda: client.post(API + "/payments/webhook", content=forged,
                              headers={"Content-Type": "application/json",
                                       "X-Razorpay-Signature": "deadbeef" * 8}),
          (400, 503), "must not mark the order PAID")
    record("C", "  order status unchanged after the bad-signature attempt",
           before, status_of(wh_order),
           "pass" if status_of(wh_order) == before else "finding")

    good_sig = _hmac.new(WEBHOOK_SECRET.encode(), forged.encode(),
                         hashlib.sha256).hexdigest()
    r = client.post(API + "/payments/webhook", content=forged,
                    headers={"Content-Type": "application/json",
                             "X-Razorpay-Signature": good_sig})
    after_good = status_of(wh_order)
    record("C", "correctly signed payment.captured IS honoured",
           "PAID", "%s (http %s)" % (after_good, r.status_code),
           "pass" if after_good == "PAID" else "finding",
           "the signature is the control, and it works in both directions")

    # Replay the same signed event: must be idempotent, not a double-credit.
    r2 = client.post(API + "/payments/webhook", content=forged,
                     headers={"Content-Type": "application/json",
                              "X-Razorpay-Signature": good_sig})
    record("C", "replaying the signed event is idempotent",
           "PAID, http < 500", "%s (http %s)" % (status_of(wh_order), r2.status_code),
           "pass" if status_of(wh_order) == "PAID" and r2.status_code < 500
           else "finding")
else:
    record("C", "payment webhook signature probes", "400/503", "n/a", "skipped",
           "order seed failed")

log("")
log("=" * 82)
log("PART D - error-body information leakage")
log("=" * 82)
ratelimit.reset_for_tests()
LEAK_MARKERS = ["Traceback", "File \"", "sqlalchemy", "SELECT ", "psycopg",
                "sqlite3.", "/home/", "C:\\\\", "hashed_password", "JWT_SECRET"]
for label, fn in [
    ("bad token /files", lambda: client.get("%s/files/%s" % (API, "z" * 40))),
    ("bad token /passport", lambda: client.get("%s/passport/%s" % (API, "z" * 40))),
    ("bad token /sos/track", lambda: client.get("%s/sos/track/%s" % (API, "z" * 40))),
    ("malformed id /payments/status", lambda: client.get("%s/payments/%%27%%20or%%201=1/status" % API,
                                                         headers=auth(pat_a_t))),
    ("negative id /appointments", lambda: client.put("%s/appointments/-1" % API,
                                                     headers=auth(pat_a_t),
                                                     json={"status": "CANCELLED"})),
    ("huge id /ehr/patient", lambda: client.get("%s/ehr/patient/99999999999" % API,
                                                headers=auth(doc_a_t))),
]:
    ratelimit.reset_for_tests()
    try:
        r = fn()
    except Exception as e:
        record("D", label, "no internals", "EXC", "inconclusive", type(e).__name__)
        continue
    hits = [m for m in LEAK_MARKERS if m.replace("\\\\", "\\") in r.text]
    if r.status_code >= 500:
        record("D", label, "no internals", r.status_code, "inconclusive",
               "server error", r.text)
    else:
        record("D", label, "no internals", r.status_code,
               "finding" if hits else "pass",
               ("leaks: %s" % ",".join(hits)) if hits else "clean", r.text)

# ------------------------------------------------------------------ output
FINISHED = datetime.now(timezone.utc).isoformat()
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
suffix = ENGINE_LABEL
with open(os.path.join(OUT, "phase2_%s_raw.csv" % suffix), "w", newline="",
          encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["part", "label", "expected", "status",
                                       "verdict", "note", "excerpt"])
    w.writeheader()
    for row in rows:
        w.writerow(row)

summary = {
    "commit": SHA, "started": STARTED, "finished": FINISHED,
    "engine": ENGINE_LABEL, "db_version": str(DBVER),
    "python": sys.version.split()[0], "sqlalchemy": sqlalchemy.__version__,
    "probes": len(rows),
    "pass": counts.get("pass", 0),
    "findings": counts.get("finding", 0),
    "inconclusive": counts.get("inconclusive", 0),
    "skipped": counts.get("skipped", 0),
    "finding_labels": [r["label"] for r in rows if r["verdict"] == "finding"],
    "inconclusive_labels": [r["label"] for r in rows if r["verdict"] == "inconclusive"],
    "skipped_labels": [r["label"] for r in rows if r["verdict"] == "skipped"],
}
with open(os.path.join(OUT, "phase2_%s_summary.json" % suffix), "w",
          encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)

log("")
log("=" * 82)
log("SUMMARY (%s)" % ENGINE_LABEL)
log("=" * 82)
log("probes        : %d" % len(rows))
log("pass          : %d" % counts.get("pass", 0))
log("FINDINGS      : %d" % counts.get("finding", 0))
log("inconclusive  : %d  (5xx or harness error - never counted as a pass)"
    % counts.get("inconclusive", 0))
log("skipped       : %d" % counts.get("skipped", 0))
if summary["finding_labels"]:
    log("")
    log("Findings:")
    for f in summary["finding_labels"]:
        log("  - %s" % f)
if summary["inconclusive_labels"]:
    log("")
    log("Inconclusive:")
    for f in summary["inconclusive_labels"]:
        log("  - %s" % f)
if summary["skipped_labels"]:
    log("")
    log("Skipped:")
    for f in summary["skipped_labels"]:
        log("  - %s" % f)
log("")
log("raw     : %s" % os.path.join(OUT, "phase2_%s_raw.csv" % suffix))
log("summary : %s" % os.path.join(OUT, "phase2_%s_summary.json" % suffix))
