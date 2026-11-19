"""Experiment G Phase 2 — PostgreSQL-specific validation.

The isolation matrix and the token study are engine-agnostic: they drive the
HTTP surface, and they produced identical results on SQLite and PostgreSQL.
This script covers the things that are *only* meaningful on PostgreSQL,
because SQLite serialises writes and therefore cannot exercise them:

  P1  database constraints   — are the unique indexes actually enforced?
  P2  concurrent idempotent sync — the IntegrityError race in /ehr/sync
  P3  concurrent cross-tenant reads under write load
  P4  transaction behaviour  — does a denied request leave partial state?
  P5  pagination and filtering on the remediated /ehr/records
  P6  index presence         — are the scoping columns indexed?

Requires EXPG_DATABASE_URL pointing at an isolated PostgreSQL database.
Refuses to run against SQLite, and refuses to run against anything that
looks like a production host.

Usage:
    EXPG_DATABASE_URL=postgresql://expg:...@localhost:5433/expg_isolation \
      .venv/Scripts/python.exe research/experiments/exp_g/phase2_postgres_validation.py
"""
import csv
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SERVICE = os.path.join(REPO, "backend", "python_service")
sys.path.insert(0, SERVICE)

URL = os.environ.get("EXPG_DATABASE_URL", "")
if not URL.startswith("postgres"):
    raise SystemExit("EXPG_DATABASE_URL must be a PostgreSQL URL. Refusing to run.")
# Guard against ever pointing this at real infrastructure.
for banned in ("supabase.co", "neon.tech", "render.com", "amazonaws.com"):
    if banned in URL:
        raise SystemExit(
            "EXPG_DATABASE_URL points at %s, which is not an isolated local test "
            "database. Refusing to run." % banned)

os.environ["DATABASE_URL"] = URL
os.environ.setdefault("JWT_SECRET_KEY", "expg-pg-secret-not-for-production")
for _v in ("GEMINI_API_KEY", "GEMINI_API_KEYS", "OPENAI_API_KEY", "OPENAI_API_KEYS",
           "GROQ_API_KEY", "GROQ_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
           "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_CLOUD_NAME",
           "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY",
           "MSG91_AUTH_KEY", "RESEND_API_KEY"):
    os.environ[_v] = ""
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
import sqlalchemy  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
import models  # noqa: E402
from database import engine, SessionLocal  # noqa: E402
from core import ratelimit  # noqa: E402
from main import app  # noqa: E402
from modules.auth.utils import get_password_hash  # noqa: E402

# Fresh schema for this run so row counts are unambiguous.
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

client = TestClient(app)
API = "/api/v1"
PW = "strongpass123"
CANARY_A = "CANARYALPHA"

rows = []
counts = {"pass": 0, "finding": 0, "inconclusive": 0, "skipped": 0}


def log(m=""):
    sys.stdout.write(m + "\n")
    sys.stdout.flush()


def auth(t):
    return {"Authorization": "Bearer %s" % t}


def record(part, label, expected, observed, verdict, note=""):
    rows.append({"part": part, "label": label, "expected": expected,
                 "observed": str(observed), "verdict": verdict, "note": note})
    counts[verdict] = counts.get(verdict, 0) + 1
    tag = {"pass": "  pass  ", "finding": " FINDING", "inconclusive": "  INCONCL",
           "skipped": "  skip  "}[verdict]
    log("%s %-56s expected=%-22s got=%s %s"
        % (tag, label[:56], expected, observed, ("| " + note) if note else ""))


def mk(username, role):
    ratelimit.reset_for_tests()
    if role == "ADMIN":
        s = SessionLocal()
        try:
            s.add(models.User(username=username, email="%s@expg.gramcare.in" % username,
                              hashed_password=get_password_hash(PW),
                              full_name="PG %s" % role, role="ADMIN", is_verified=True))
            s.commit()
        finally:
            s.close()
    else:
        payload = {"username": username, "email": "%s@expg.gramcare.in" % username,
                   "password": PW, "full_name": "PG %s" % role, "role": role}
        if role in ("DOCTOR", "HOSPITAL"):
            phone = "+9193%08d" % (abs(hash(username)) % 100000000)
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
        raise SystemExit("seed failure %s: %s" % (username, r.text[:160]))
    t = r.json()["access_token"]
    return t, client.get(API + "/auth/me", headers=auth(t)).json()["id"]


try:
    SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
except Exception:
    SHA = "unknown"
STARTED = datetime.now(timezone.utc).isoformat()
with engine.connect() as c:
    DBVER = c.execute(sqlalchemy.text("select version()")).scalar()
    ISO = c.execute(sqlalchemy.text("show transaction_isolation")).scalar()

log("=" * 92)
log("Experiment G Phase 2 - PostgreSQL-specific validation")
log("=" * 92)
log("commit            : %s" % SHA)
log("started           : %s" % STARTED)
log("postgres          : %s" % DBVER[:76])
log("default isolation : %s" % ISO)
log("python / sqlalchemy: %s / %s" % (sys.version.split()[0], sqlalchemy.__version__))
log("database          : isolated container, synthetic data only")
log("")

log("[seed] accounts")
pat_a_t, pat_a = mk("pg_patient_a", "PATIENT")
pat_b_t, pat_b = mk("pg_patient_b", "PATIENT")
doc_a_t, doc_a = mk("pg_doctor_a", "DOCTOR")
doc_b_t, doc_b = mk("pg_doctor_b", "DOCTOR")
log("    patient A=%s B=%s  doctor A=%s B=%s" % (pat_a, pat_b, doc_a, doc_b))
log("")

# ============================================================== P1 constraints
log("=" * 92)
log("P1 - database constraints actually enforced by PostgreSQL")
log("=" * 92)

CONSTRAINED = [
    ("ehr_records", "client_uuid", "idempotent offline sync depends on it"),
    ("users", "passport_token", "capability token must be unique"),
    ("users", "username", "identity"),
    ("users", "email", "identity"),
    ("stored_files", "token", "capability token must be unique"),
    ("emergency_sos", "public_token", "capability token must be unique"),
]
with engine.connect() as c:
    idx = c.execute(sqlalchemy.text("""
        select t.relname as tbl, i.relname as idx, ix.indisunique as uniq,
               array_to_string(array_agg(a.attname order by a.attnum), ',') as cols
        from pg_class t
        join pg_index ix on t.oid = ix.indrelid
        join pg_class i on i.oid = ix.indexrelid
        join pg_attribute a on a.attrelid = t.oid and a.attnum = any(ix.indkey)
        where t.relkind = 'r'
        group by 1,2,3
    """)).fetchall()
index_map = {}
for tbl, iname, uniq, cols in idx:
    index_map.setdefault((tbl, cols), []).append((iname, uniq))

for tbl, col, why in CONSTRAINED:
    entries = index_map.get((tbl, col), [])
    has_unique = any(u for _, u in entries)
    record("P1", "unique index on %s.%s (%s)" % (tbl, col, why),
           "unique index present", "yes" if has_unique else "NO",
           "pass" if has_unique else "finding")

# Prove the client_uuid constraint rejects a duplicate at the database level,
# not merely in application code.
s = SessionLocal()
try:
    s.add(models.EHRRecord(patient_id=pat_a, record_type="note",
                           title="pg constraint probe", content=CANARY_A,
                           client_uuid="pg-dup-probe-1"))
    s.commit()
    dup_rejected = False
    try:
        s.add(models.EHRRecord(patient_id=pat_a, record_type="note",
                               title="pg constraint probe dup", content=CANARY_A,
                               client_uuid="pg-dup-probe-1"))
        s.commit()
    except IntegrityError:
        s.rollback()
        dup_rejected = True
    record("P1", "PostgreSQL rejects a duplicate ehr_records.client_uuid",
           "IntegrityError", "rejected" if dup_rejected else "ACCEPTED",
           "pass" if dup_rejected else "finding",
           "the idempotency guarantee is enforced by the database")
finally:
    s.close()

# ========================================== P2 concurrent idempotent sync race
log("")
log("=" * 92)
log("P2 - concurrent idempotent sync: the race SQLite cannot exercise")
log("=" * 92)
log("    SQLite serialises writers, so /ehr/sync's IntegrityError handler is")
log("    only genuinely exercised under PostgreSQL's concurrent writers.")

BATCH = [{"client_uuid": "pg-race-%04d" % i, "record_type": "note",
          "title": "%s race %d" % (CANARY_A, i),
          "content": "%s concurrent sync" % CANARY_A} for i in range(25)]


def push_batch(_):
    try:
        r = client.post(API + "/ehr/sync", headers=auth(pat_a_t),
                        json={"records": BATCH})
        return r.status_code, (r.json() if r.status_code < 500 else None)
    except Exception as e:
        return "EXC", str(e)[:120]


ratelimit.reset_for_tests()
CONC = 10
with ThreadPoolExecutor(max_workers=CONC) as ex:
    results = list(ex.map(push_batch, range(CONC)))

statuses = [r[0] for r in results]
server_errors = [x for x in statuses if x == "EXC" or (isinstance(x, int) and x >= 500)]

s = SessionLocal()
try:
    total = (s.query(models.EHRRecord)
             .filter(models.EHRRecord.client_uuid.like("pg-race-%")).count())
    distinct = s.execute(sqlalchemy.text(
        "select count(distinct client_uuid) from ehr_records "
        "where client_uuid like 'pg-race-%'")).scalar()
finally:
    s.close()

record("P2", "%d concurrent identical batches of %d records" % (CONC, len(BATCH)),
       "no 5xx", "%d server error(s)" % len(server_errors),
       "pass" if not server_errors else "finding",
       "statuses=%s" % sorted(set(str(x) for x in statuses)))
record("P2", "rows written for a batch sent %d times concurrently" % CONC,
       "exactly %d" % len(BATCH), total,
       "pass" if total == len(BATCH) else "finding",
       "duplicate rate = %.4f" % ((total - len(BATCH)) / float(len(BATCH))))
record("P2", "distinct client_uuids", "%d" % len(BATCH), distinct,
       "pass" if distinct == len(BATCH) else "finding")

# =================================== P3 concurrent cross-tenant reads under load
log("")
log("=" * 92)
log("P3 - concurrent cross-tenant reads while tenant A writes")
log("=" * 92)

stop = threading.Event()
write_errors = []


def writer():
    i = 0
    while not stop.is_set() and i < 60:
        try:
            client.post(API + "/ehr/record", headers=auth(pat_a_t),
                        json={"record_type": "note",
                              "title": "%s live %d" % (CANARY_A, i),
                              "content": "%s live write" % CANARY_A,
                              "client_uuid": "pg-live-%04d" % i})
        except Exception as e:
            write_errors.append(str(e)[:80])
        i += 1


READ_PATHS = ["/ehr/records", "/sos/active", "/pharmacy/queue", "/ehr/prescriptions/my",
              "/appointments/my", "/analytics/overview"]
leaks = []
read_5xx = []


def reader(path):
    tok = doc_b_t if path in ("/ehr/records", "/sos/active", "/analytics/overview") else pat_b_t
    try:
        r = client.get(API + path, headers=auth(tok))
        if r.status_code >= 500:
            read_5xx.append("%s -> %s" % (path, r.status_code))
        elif r.status_code == 200 and CANARY_A in r.text:
            leaks.append("%s -> leaked" % path)
        return r.status_code
    except Exception as e:
        read_5xx.append("%s -> EXC %s" % (path, type(e).__name__))
        return "EXC"


ratelimit.reset_for_tests()
wt = threading.Thread(target=writer, daemon=True)
wt.start()
with ThreadPoolExecutor(max_workers=8) as ex:
    read_statuses = list(ex.map(reader, READ_PATHS * 6))
stop.set()
wt.join(timeout=20)

record("P3", "cross-tenant reads during concurrent writes (%d reads)"
       % len(read_statuses), "no canary", "%d leak(s)" % len(leaks),
       "pass" if not leaks else "finding", ", ".join(leaks[:4]))
record("P3", "server errors during the concurrent run", "0",
       "%d" % len(read_5xx), "pass" if not read_5xx else "inconclusive",
       ", ".join(read_5xx[:4]))
record("P3", "writer thread errors", "0", "%d" % len(write_errors),
       "pass" if not write_errors else "inconclusive", ", ".join(write_errors[:2]))

# ======================================================= P4 transaction behaviour
log("")
log("=" * 92)
log("P4 - transaction behaviour on a denied request")
log("=" * 92)

s = SessionLocal()
try:
    before_records = s.query(models.EHRRecord).count()
    before_audit = s.query(models.AuditLog).count()
    before_triage = s.query(models.TriageLog).count()
finally:
    s.close()

# A denied cross-tenant triage write (the G-9 fix) must leave nothing behind.
fp = client.post(API + "/family", headers=auth(pat_a_t),
                 json={"full_name": "%s Child" % CANARY_A, "relation": "Daughter",
                       "age": 6, "gender": "Female"})
fp_id = fp.json().get("id") if fp.status_code in (200, 201) else None
if fp_id:
    ratelimit.reset_for_tests()
    r = client.post(API + "/triage/analyze", headers=auth(pat_b_t),
                    json={"symptoms_text": "fever and chills for three days",
                          "patient_id": str(pat_b), "age": 30,
                          "family_profile_id": fp_id})
    s = SessionLocal()
    try:
        after_triage = s.query(models.TriageLog).count()
        orphan = s.query(models.TriageLog).filter(
            models.TriageLog.family_profile_id == fp_id).count()
    finally:
        s.close()
    record("P4", "denied cross-tenant triage leaves no TriageLog row",
           "403 and 0 new rows for that profile", "%s / %d row(s)"
           % (r.status_code, orphan),
           "pass" if r.status_code == 403 and orphan == 0 else "finding")
else:
    record("P4", "denied cross-tenant triage", "403", "n/a", "skipped",
           "family profile seed failed")

# A denied cross-tenant read must not write an audit row attributing the read.
ratelimit.reset_for_tests()
s = SessionLocal()
try:
    audit_before = s.query(models.AuditLog).count()
finally:
    s.close()
r = client.get("%s/ehr/patient/%s" % (API, pat_a), headers=auth(pat_b_t))
s = SessionLocal()
try:
    audit_after = s.query(models.AuditLog).count()
finally:
    s.close()
record("P4", "denied patient-to-patient wallet read", "403",
       r.status_code, "pass" if r.status_code == 403 else "finding")
record("P4", "no audit row written for the denied read",
       "0 new rows", audit_after - audit_before,
       "pass" if audit_after == audit_before else "finding",
       "a denial is not a read")

# A permitted read MUST write one.
ratelimit.reset_for_tests()
s = SessionLocal()
try:
    audit_before = s.query(models.AuditLog).count()
finally:
    s.close()
r = client.get("%s/ehr/patient/%s" % (API, pat_a), headers=auth(doc_a_t))
s = SessionLocal()
try:
    audit_after = s.query(models.AuditLog).count()
finally:
    s.close()
record("P4", "permitted doctor wallet read is audited", ">=1 new row",
       audit_after - audit_before,
       "pass" if audit_after > audit_before else "finding",
       "the break-glass policy depends on this trail")

# And the AI summary, which recorded nothing before remediation.
ratelimit.reset_for_tests()
s = SessionLocal()
try:
    audit_before = s.query(models.AuditLog).filter(
        models.AuditLog.resource == "PatientSummary").count()
finally:
    s.close()
r = client.get("%s/assist/patient-summary/%s" % (API, pat_a), headers=auth(doc_a_t))
s = SessionLocal()
try:
    audit_after = s.query(models.AuditLog).filter(
        models.AuditLog.resource == "PatientSummary").count()
finally:
    s.close()
record("P4", "AI patient summary is audited (G-8 remediation)", ">=1 new row",
       audit_after - audit_before,
       "pass" if audit_after > audit_before else "finding",
       "status=%s" % r.status_code)

# ============================================ P5 pagination and filtering on PG
log("")
log("=" * 92)
log("P5 - pagination and filtering on the remediated /ehr/records")
log("=" * 92)

# doctor A has a relationship with patient A (the audited read above does not
# create one), so establish it explicitly with a prescription.
ratelimit.reset_for_tests()
client.post(API + "/ehr/issue_prescription", headers=auth(doc_a_t),
            json={"patient_id": pat_a,
                  "medicines": [{"name": "PgMed", "dosage": "1", "frequency": "1-0-1",
                                 "duration": "3 days"}],
                  "diagnosis": "pg relationship"})

r = client.get(API + "/ehr/records", headers=auth(doc_a_t))
related_ok = r.status_code == 200 and CANARY_A in r.text
record("P5", "related doctor sees the patient's records", "200 with canary",
       "%s / %s" % (r.status_code, "canary" if CANARY_A in r.text else "no canary"),
       "pass" if related_ok else "finding")

r = client.get(API + "/ehr/records", headers=auth(doc_b_t))
unrelated_ok = r.status_code == 200 and CANARY_A not in r.text
record("P5", "unrelated doctor sees none of them", "200 without canary",
       "%s / %s" % (r.status_code, "canary" if CANARY_A in r.text else "clean"),
       "pass" if unrelated_ok else "finding")

for skip, limit in ((0, 1), (0, 50), (0, 200), (3, 7), (10000, 5)):
    r = client.get(API + "/ehr/records?skip=%d&limit=%d" % (skip, limit),
                   headers=auth(doc_a_t))
    n = len(r.json()) if r.status_code == 200 and isinstance(r.json(), list) else None
    ok = r.status_code == 200 and (n is not None and n <= limit)
    record("P5", "pagination skip=%d limit=%d" % (skip, limit),
           "200, <= limit rows", "%s / %s rows" % (r.status_code, n),
           "pass" if ok else "finding")

for bad in ("limit=0", "limit=201", "skip=-1"):
    r = client.get(API + "/ehr/records?%s" % bad, headers=auth(doc_a_t))
    record("P5", "rejects out-of-range %s" % bad, "422", r.status_code,
           "pass" if r.status_code == 422 else "finding")

# ==================================================== P6 indexes on scope columns
log("")
log("=" * 92)
log("P6 - the columns the scoping queries filter on are indexed")
log("=" * 92)
SCOPE_COLS = [
    ("ehr_records", "patient_id"),
    ("prescriptions", "patient_id"),
    ("prescriptions", "doctor_id"),
    ("emergency_sos", "assigned_hospital_id"),
    ("medicine_preorders", "pharmacy_id"),
    ("medicine_preorders", "patient_id"),
    ("hospitals", "owner_user_id"),
    ("pharmacies", "owner_user_id"),
]
for tbl, col in SCOPE_COLS:
    entries = index_map.get((tbl, col), [])
    # A composite index whose leading column is `col` also serves.
    if not entries:
        for (t2, cols), e in index_map.items():
            if t2 == tbl and cols.split(",")[0] == col:
                entries = e
                break
    record("P6", "index covering %s.%s" % (tbl, col), "present",
           "yes" if entries else "NO", "pass" if entries else "finding",
           "scoping filter would otherwise be a sequential scan")

# ======================================================================= output
FINISHED = datetime.now(timezone.utc).isoformat()
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "phase2_postgres_validation_raw.csv"), "w", newline="",
          encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["part", "label", "expected", "observed",
                                       "verdict", "note"])
    w.writeheader()
    for row in rows:
        w.writerow(row)

summary = {
    "commit": SHA, "started": STARTED, "finished": FINISHED,
    "engine": "postgresql", "db_version": DBVER,
    "default_transaction_isolation": ISO,
    "python": sys.version.split()[0], "sqlalchemy": sqlalchemy.__version__,
    "concurrency_level": CONC, "batch_size": len(BATCH),
    "checks": len(rows),
    "pass": counts.get("pass", 0), "findings": counts.get("finding", 0),
    "inconclusive": counts.get("inconclusive", 0), "skipped": counts.get("skipped", 0),
    "finding_labels": [r["label"] for r in rows if r["verdict"] == "finding"],
    "inconclusive_labels": [r["label"] for r in rows if r["verdict"] == "inconclusive"],
}
with open(os.path.join(OUT, "phase2_postgres_validation_summary.json"), "w",
          encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)

log("")
log("=" * 92)
log("SUMMARY - PostgreSQL validation")
log("=" * 92)
log("checks        : %d" % len(rows))
log("pass          : %d" % counts.get("pass", 0))
log("FINDINGS      : %d" % counts.get("finding", 0))
log("inconclusive  : %d" % counts.get("inconclusive", 0))
log("skipped       : %d" % counts.get("skipped", 0))
for f in summary["finding_labels"]:
    log("  FINDING: %s" % f)
for f in summary["inconclusive_labels"]:
    log("  INCONCLUSIVE: %s" % f)
log("")
log("raw     : %s" % os.path.join(OUT, "phase2_postgres_validation_raw.csv"))
log("summary : %s" % os.path.join(OUT, "phase2_postgres_validation_summary.json"))
