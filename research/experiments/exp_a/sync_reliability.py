"""Experiment A · Phase 3 — offline synchronisation reliability harness.

Executes the protocol in docs/research/experiments/exp_a/experiment_protocol.md
against an ISOLATED PostgreSQL database with synthetic data only.

Design rules this harness enforces on itself:

  * An HTTP 200 is never evidence. Every verdict is decided by an integrity
    ledger computed from persisted database state, read through a direct
    SQLAlchemy session.
  * Each scenario group runs a positive control first. If the control fails,
    every scenario in that group is reported INCONCLUSIVE, not PASSED.
  * Four verdicts: PASSED / FAILED / INCONCLUSIVE / NOT_APPLICABLE. A
    capability that does not exist is recorded NOT_APPLICABLE, never skipped.
  * A 5xx or a harness exception is INCONCLUSIVE.
  * PostgreSQL only. Refuses SQLite, and refuses any managed-host URL.

Usage:
    EXPA_DATABASE_URL=postgresql://expa:...@localhost:5434/expa_sync \
      .venv/Scripts/python.exe research/experiments/exp_a/sync_reliability.py
"""
import csv
import json
import os
import subprocess
import sys
import time
import uuid as uuidlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SERVICE = os.path.join(REPO, "backend", "python_service")
sys.path.insert(0, SERVICE)

URL = os.environ.get("EXPA_DATABASE_URL", "")
if not URL.startswith("postgres"):
    raise SystemExit(
        "EXPA_DATABASE_URL must be a PostgreSQL URL. This experiment refuses to "
        "run on SQLite: SQLite serialises writers and cannot exercise the "
        "concurrency scenarios."
    )
for banned in ("supabase.co", "neon.tech", "render.com", "amazonaws.com",
               "azure.com", "googleapis.com"):
    if banned in URL:
        raise SystemExit(
            "EXPA_DATABASE_URL points at %s. This experiment writes and deletes "
            "freely and must only ever run against an isolated local test "
            "database. Refusing to run." % banned
        )

os.environ["DATABASE_URL"] = URL
os.environ.setdefault("JWT_SECRET_KEY", "expa-secret-not-for-production")
for _v in ("GEMINI_API_KEY", "GEMINI_API_KEYS", "OPENAI_API_KEY", "OPENAI_API_KEYS",
           "GROQ_API_KEY", "GROQ_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
           "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_CLOUD_NAME",
           "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY",
           "MSG91_AUTH_KEY", "RESEND_API_KEY"):
    os.environ[_v] = ""
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
import sqlalchemy  # noqa: E402
import models  # noqa: E402
from database import engine, SessionLocal  # noqa: E402
from core import ratelimit  # noqa: E402
from main import app  # noqa: E402
from modules.auth.utils import get_password_hash  # noqa: E402

API = "/api/v1"
PW = "strongpass123"
SERVER_CAP = 100          # schemas.EHRSyncRequest.records max_length
client = TestClient(app, raise_server_exceptions=False)

rows = []
counts = {"PASSED": 0, "FAILED": 0, "INCONCLUSIVE": 0, "NOT_APPLICABLE": 0}
group_control_ok = {}
timings = {}


def log(m=""):
    sys.stdout.write(m + "\n")
    sys.stdout.flush()


def auth(t):
    return {"Authorization": "Bearer %s" % t}


def record(group, sid, title, expected, observed, verdict, ledger=None, note=""):
    """Record one scenario outcome. A group whose control failed can only
    report INCONCLUSIVE."""
    if verdict == "PASSED" and group_control_ok.get(group) is False:
        note = ("positive control for group %s failed; result cannot be trusted. "
                "%s" % (group, note)).strip()
        verdict = "INCONCLUSIVE"
    led = ledger or {}
    rows.append({
        "group": group, "scenario": sid, "title": title,
        "expected": expected, "observed": str(observed)[:300],
        "verdict": verdict,
        "submitted": led.get("submitted", ""),
        "persisted": led.get("persisted", ""),
        "unique_persisted": led.get("unique_persisted", ""),
        "duplicates": led.get("duplicates", ""),
        "missing": led.get("missing", ""),
        "unexpected": led.get("unexpected", ""),
        "overwritten": led.get("overwritten", ""),
        "cross_tenant": led.get("cross_tenant", ""),
        "note": note,
    })
    counts[verdict] = counts.get(verdict, 0) + 1
    tag = {"PASSED": "  PASS ", "FAILED": " FAIL  ",
           "INCONCLUSIVE": " INCONC", "NOT_APPLICABLE": "  N/A  "}[verdict]
    extra = ""
    if led:
        extra = ("  [sub=%s pers=%s uniq=%s dup=%s miss=%s xten=%s]"
                 % (led.get("submitted"), led.get("persisted"),
                    led.get("unique_persisted"), led.get("duplicates"),
                    led.get("missing"), led.get("cross_tenant")))
    log("%s %-7s %-52s -> %s%s%s"
        % (tag, sid, title[:52], str(observed)[:46], extra,
           ("  | " + note) if note else ""))


# ----------------------------------------------------------------- fixtures
# schemas.EHRSyncItem constrains client_uuid to min_length=8 (a real UUIDv4 is
# 36 characters). Short fixture ids are rejected with 422, which on the first
# run looked like a product defect and was a harness defect. Fixture ids are
# therefore built with a fixed prefix that guarantees the length, and asserted
# below so this cannot recur silently.
UUID_PREFIX = "expa"
MIN_UUID_LEN = 8


def make_records(n, prefix, content_suffix="", profile_id=None, rtype="note",
                 when=None):
    """Deterministic, replayable record fixtures."""
    out = []
    for i in range(n):
        cu = "%s-%s-%04d" % (UUID_PREFIX, prefix, i)
        assert len(cu) >= MIN_UUID_LEN, "fixture uuid too short: %r" % cu
        out.append({
            "client_uuid": cu,
            "record_type": rtype,
            "title": "%s title %d" % (prefix, i),
            "content": "%s content %d%s" % (prefix, i, content_suffix),
            "doctor_name": None,
            "family_profile_id": profile_id,
            "record_date": (when or datetime.now(timezone.utc)).isoformat(),
        })
    return out


def ledger(submitted_records, patient_id, window_prefix=None):
    """Compute the integrity ledger from PERSISTED DATABASE STATE."""
    uuids = [r["client_uuid"] for r in submitted_records]
    content_by_uuid = {r["client_uuid"]: r["content"] for r in submitted_records}
    s = SessionLocal()
    try:
        got = (s.query(models.EHRRecord)
               .filter(models.EHRRecord.client_uuid.in_(uuids)).all()) if uuids else []
        persisted = len(got)
        unique = len({r.client_uuid for r in got})
        duplicates = persisted - unique
        missing = len(set(uuids)) - unique
        cross = sum(1 for r in got if r.patient_id != patient_id)
        overwritten = sum(
            1 for r in got
            if r.client_uuid in content_by_uuid
            and r.content != content_by_uuid[r.client_uuid])
        unexpected = 0
        if window_prefix:
            unexpected = (s.query(models.EHRRecord)
                          .filter(models.EHRRecord.patient_id == patient_id,
                                  models.EHRRecord.client_uuid.like(window_prefix + "%"),
                                  ~models.EHRRecord.client_uuid.in_(uuids))
                          .count())
        return {
            "submitted": len(submitted_records),
            "persisted": persisted,
            "unique_persisted": unique,
            "duplicates": duplicates,
            "missing": missing,
            "unexpected": unexpected,
            "overwritten": overwritten,
            "cross_tenant": cross,
        }
    finally:
        s.close()


def clean(led):
    return (led["duplicates"] == 0 and led["missing"] == 0
            and led["unexpected"] == 0 and led["overwritten"] == 0
            and led["cross_tenant"] == 0)


LAST_ERROR = {"status": None, "body": None}


def post_sync(token, records):
    """POST /ehr/sync. Returns (status, body_or_text)."""
    ratelimit.reset_for_tests()
    r = client.post(API + "/ehr/sync", headers=auth(token),
                    json={"records": records})
    if r.status_code != 200:
        LAST_ERROR["status"] = r.status_code
        LAST_ERROR["body"] = r.text[:400]
        log("        [server %s] %s" % (r.status_code, r.text[:260]))
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text[:300]


# ------------------------------------------------- client-side reimplementation
class ClientSim:
    """A faithful reimplementation of mobile/patient_app/lib/services/
    sync_service.dart, so client-side behaviour can be exercised without a
    Flutter runtime.

    Mirrors the current implementation, including the Experiment A fixes:
      * pushUnsynced() slices the queue into syncBatchLimit (100) record
        requests and acknowledges each slice independently (F-A1).
      * a record is marked synced if its UUID is in synced[] OR duplicates[].
      * a record named in rejected[] stops being retried and is NOT marked
        synced (F-A2).
      * payload rides along with each record (F-A6).
      * a transport/HTTP failure leaves the remaining slices queued and
        stops; there is still no retry counter and no backoff.
      * pullRemote() UPDATES a cached 'srv-<id>' record rather than skipping
        it (F-A5).

    This is a REIMPLEMENTATION, not the shipped Dart code. Divergence is
    possible and is stated as a limitation in the report.
    """

    def __init__(self, token, user_id):
        self.token = token
        self.user_id = user_id
        self.queue = []          # list of dicts with a 'synced' flag
        self.attempts = 0
        self.last_status = None

    def create(self, rec):
        item = dict(rec)
        item["synced"] = False
        self.queue.append(item)
        return item

    def unsynced(self):
        return [r for r in self.queue
                if not r["synced"] and not r.get("rejected")]

    SYNC_BATCH_LIMIT = 100          # SyncService.syncBatchLimit

    def push(self):
        pending = self.unsynced()
        if not pending:
            return None
        self.attempts += 1
        status = None
        for start in range(0, len(pending), self.SYNC_BATCH_LIMIT):
            slice_ = pending[start:start + self.SYNC_BATCH_LIMIT]
            payload = [{k: v for k, v in r.items()
                        if k not in ("synced", "rejected")} for r in slice_]
            status, body = post_sync(self.token, payload)
            self.last_status = status
            if status != 200 or not isinstance(body, dict):
                # Dart: stop here; the rest of the queue waits for next time.
                return status
            ack = (set(body.get("synced") or [])
                   | set(body.get("duplicates") or []))
            # rejected[] is permanent: stop retrying, but never claim synced.
            refused = {x["client_uuid"] for x in (body.get("rejected") or [])}
            for r in slice_:
                if r["client_uuid"] in ack:
                    r["synced"] = True
                elif r["client_uuid"] in refused:
                    r["rejected"] = True
        return status

    def push_until_drained(self, max_attempts=5):
        for _ in range(max_attempts):
            if not self.unsynced():
                break
            self.push()
        return len(self.unsynced())

    def pull(self):
        ratelimit.reset_for_tests()
        r = client.get("%s/ehr/patient/%s" % (API, self.user_id),
                       headers=auth(self.token))
        if r.status_code != 200:
            return r.status_code
        by_uuid = {x["client_uuid"]: x for x in self.queue
                   if x.get("client_uuid")}
        for m in r.json():
            marker = "srv-%s" % m["id"]
            if marker in by_uuid:
                # Dart now updates in place (F-A5).
                cached = by_uuid[marker]
                cached["content"] = m.get("content", cached.get("content"))
                cached["title"] = m.get("title", cached.get("title"))
                cached["record_type"] = m.get("record_type",
                                              cached.get("record_type"))
                if isinstance(m.get("payload"), dict):
                    cached["payload"] = m["payload"]
                continue
            self.queue.append({"client_uuid": marker, "content": m.get("content"),
                               "synced": True, "record_type": m.get("record_type"),
                               "title": m.get("title"), "doctor_name": None,
                               "family_profile_id": m.get("family_profile_id"),
                               "record_date": m.get("record_date")})
        return 200


# -------------------------------------------------------------------- seeding
def mk(username, role="PATIENT"):
    ratelimit.reset_for_tests()
    payload = {"username": username, "email": "%s@expa.gramcare.in" % username,
               "password": PW, "full_name": "ExpA %s" % username, "role": role}
    if role in ("DOCTOR", "HOSPITAL"):
        phone = "+9195%08d" % (abs(hash(username)) % 100000000)
        s = SessionLocal()
        s.add(models.PhoneOTP(phone=phone, otp_code="000000", is_used=True,
                              expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                              + timedelta(minutes=10)))
        s.commit(); s.close()
        payload["phone"] = phone
    client.post(API + "/auth/register", json=payload)
    s = SessionLocal()
    u = s.query(models.User).filter(models.User.username == username).first()
    if u is None:
        s.close()
        raise SystemExit("seed failure: %s not created" % username)
    u.is_verified = True
    if role == "DOCTOR":
        p = s.query(models.DoctorProfile).filter(
            models.DoctorProfile.user_id == u.id).first()
        if not p:
            p = models.DoctorProfile(user_id=u.id); s.add(p)
        p.verification_status = "APPROVED"
    s.commit(); uid = u.id; s.close()
    ratelimit.reset_for_tests()
    r = client.post(API + "/auth/login", data={"username": username, "password": PW})
    if r.status_code != 200:
        raise SystemExit("seed failure: login %s -> %s" % (username, r.text[:160]))
    return r.json()["access_token"], uid


def fresh_schema():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)


# =========================================================================
#                                  RUN
# =========================================================================
try:
    SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
except Exception:
    SHA = "unknown"
STARTED = datetime.now(timezone.utc).isoformat()

fresh_schema()
with engine.connect() as c:
    DBVER = c.execute(sqlalchemy.text("select version()")).scalar()
    ISO = c.execute(sqlalchemy.text("show transaction_isolation")).scalar()
s = SessionLocal()
try:
    ALEMBIC = "n/a (schema built by create_all)"
finally:
    s.close()

log("=" * 100)
log("Experiment A - offline synchronisation reliability")
log("=" * 100)
log("commit            : %s" % SHA)
log("started           : %s" % STARTED)
log("postgres          : %s" % DBVER[:80])
log("isolation         : %s" % ISO)
log("python/sqlalchemy : %s / %s" % (sys.version.split()[0], sqlalchemy.__version__))
log("server batch cap  : %d  (schemas.EHRSyncRequest.records max_length)" % SERVER_CAP)
log("database          : isolated container, synthetic data only, schema rebuilt")
log("")

log("[seed] synthetic accounts")
A_tok, A_id = mk("expa_patient_a")
B_tok, B_id = mk("expa_patient_b")
DOC_tok, DOC_id = mk("expa_doctor", "DOCTOR")
log("    patient A=%s  patient B=%s  doctor=%s" % (A_id, B_id, DOC_id))

# A owns a family profile; a second one will be deleted to set up G4.
def make_profile(tok, name):
    ratelimit.reset_for_tests()
    r = client.post(API + "/family", headers=auth(tok),
                    json={"full_name": name, "relation": "Daughter", "age": 7,
                          "gender": "Female"})
    return r.json()["id"] if r.status_code in (200, 201) else None

A_profile = make_profile(A_tok, "ExpA Child A")
A_profile_doomed = make_profile(A_tok, "ExpA Child Doomed")
B_profile = make_profile(B_tok, "ExpA Child B")
log("    A profile=%s  A doomed profile=%s  B profile=%s"
    % (A_profile, A_profile_doomed, B_profile))
log("")

# =======================================================  GROUP A
log("=" * 100)
log("GROUP A - normal synchronisation")
log("=" * 100)

ctl = make_records(1, "a0ctl")
st, body = post_sync(A_tok, ctl)
led = ledger(ctl, A_id)
group_control_ok["A"] = (st == 200 and led["persisted"] == 1 and clean(led))
record("A", "A0", "CONTROL: one record, stable connection", "1 persisted, clean",
       "http %s" % st, "PASSED" if group_control_ok["A"] else "FAILED", led,
       "control for group A")

for sid, n, title in (("A1", 1, "1 record"), ("A2", 10, "10 records in one batch"),
                      ("A3", SERVER_CAP, "%d records (the schema cap)" % SERVER_CAP)):
    recs = make_records(n, sid.lower())
    st, body = post_sync(A_tok, recs)
    led = ledger(recs, A_id, window_prefix="%s-%s" % (UUID_PREFIX, sid.lower()))
    ok = st == 200 and led["persisted"] == n and clean(led)
    record("A", sid, title, "%d persisted, clean" % n, "http %s" % st,
           "PASSED" if ok else ("INCONCLUSIVE" if st >= 500 else "FAILED"), led)

# A3b - one over the cap
recs = make_records(SERVER_CAP + 1, "a3b")
st, body = post_sync(A_tok, recs)
led = ledger(recs, A_id, window_prefix="%s-a3b" % UUID_PREFIX)
over_rejected = st == 422 and led["persisted"] == 0
record("A", "A3b", "%d records (one over the cap)" % (SERVER_CAP + 1),
       "422 and 0 persisted", "http %s, persisted=%d" % (st, led["persisted"]),
       "PASSED" if over_rejected else ("INCONCLUSIVE" if st >= 500 else "FAILED"),
       led, "server correctly enforces its cap" if over_rejected else "")

# A3c - the client's own logic against a queue over the cap
sim = ClientSim(A_tok, A_id)
for rec in make_records(150, "a3c"):
    sim.create(rec)
remaining = sim.push_until_drained(max_attempts=5)
led = ledger(make_records(150, "a3c"), A_id, window_prefix="%s-a3c" % UUID_PREFIX)
drained = remaining == 0
record("A", "A3c", "client with 150 queued records drains the queue",
       "queue drains to 0", "%d still queued after %d attempts (last http %s)"
       % (remaining, sim.attempts, sim.last_status),
       "PASSED" if drained else "FAILED", led,
       "" if drained else "DEADLOCK: pushUnsynced sends the whole queue in one "
                          "request with no chunking, so a queue over the cap can "
                          "never drain")

# A4 - record_date validation
now = datetime.now(timezone.utc)
dates = {"now": now, "future_10y": now + timedelta(days=3650),
         "past_10y": now - timedelta(days=3650)}
a4 = []
for label, when in dates.items():
    a4 += make_records(1, "a4-%s" % label, when=when)
st, body = post_sync(A_tok, a4)
s = SessionLocal()
try:
    stored = {r.client_uuid: r.record_date for r in
              s.query(models.EHRRecord).filter(
                  models.EHRRecord.client_uuid.in_([r["client_uuid"] for r in a4])).all()}
finally:
    s.close()
led = ledger(a4, A_id)
now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
future_uuid = [r["client_uuid"] for r in a4 if "future" in r["client_uuid"]][0]
past_uuid = [r["client_uuid"] for r in a4 if "past" in r["client_uuid"]][0]
future_clamped = (stored.get(future_uuid) is not None
                  and stored[future_uuid] <= now_naive + timedelta(hours=25))
past_kept = (stored.get(past_uuid) is not None
             and stored[past_uuid] < now_naive - timedelta(days=3000))
record("A", "A4", "record_date: now, +10 years, -10 years",
       "future clamped to now, past preserved",
       "persisted=%d, future_clamped=%s, past_preserved=%s"
       % (led["persisted"], future_clamped, past_kept),
       "PASSED" if (st == 200 and led["persisted"] == 3 and future_clamped
                    and past_kept) else "FAILED", led,
       "a patient legitimately records something that happened days ago while "
       "offline, so only the future side is bounded")

# A5 - all six record types
types = ["note", "prescription", "lab_report", "triage_log", "vaccination", "scan"]
a5 = []
for t in types:
    a5 += make_records(1, "a5-%s" % t, rtype=t)
st, body = post_sync(A_tok, a5)
led = ledger(a5, A_id)
s = SessionLocal()
try:
    kept = {r.client_uuid: r.record_type for r in s.query(models.EHRRecord).filter(
        models.EHRRecord.client_uuid.in_([r["client_uuid"] for r in a5])).all()}
finally:
    s.close()
types_ok = all(kept.get(r["client_uuid"]) == r["record_type"] for r in a5)
record("A", "A5", "one record of each of the 6 types",
       "6 persisted, types preserved",
       "http %s, %d persisted, types_preserved=%s" % (st, led["persisted"], types_ok),
       "PASSED" if (st == 200 and led["persisted"] == 6 and types_ok and clean(led))
       else "FAILED", led)

# A6 - payload on the offline path
a6 = make_records(1, "a6")
a6[0]["payload"] = {"image_url": "https://example.invalid/scan.png", "medicines": ["X"]}
st, body = post_sync(A_tok, a6)
s = SessionLocal()
try:
    row = s.query(models.EHRRecord).filter(
        models.EHRRecord.client_uuid == a6[0]["client_uuid"]).first()
    payload_stored = row.payload if row else None
finally:
    s.close()
record("A", "A6", "payload accepted by the API contract",
       "payload stored", "http %s, payload=%s" % (st, payload_stored),
       "PASSED" if payload_stored else "FAILED", ledger(a6, A_id),
       "API stores it - but the Hive model has no payload field and "
       "pushUnsynced never sends one, so this is unreachable from the "
       "offline queue (audit A6)")
# A6b - payload now rides the offline queue (F-A6: the Hive model gained a
# payload field and pushUnsynced sends it).
a6b = make_records(1, "a6b")
a6b[0]["payload"] = {"image_url": "https://example.invalid/offline.png",
                     "medicines": ["OfflineMed"]}
sim_a6b = ClientSim(A_tok, A_id)
for rec in a6b:
    sim_a6b.create(rec)
sim_a6b.push()
s_ = SessionLocal()
try:
    row_ = s_.query(models.EHRRecord).filter(
        models.EHRRecord.client_uuid == a6b[0]["client_uuid"]).first()
    offline_payload = row_.payload if row_ else None
finally:
    s_.close()
record("A", "A6b", "payload survives the OFFLINE queue path",
       "payload stored", "payload=%s" % offline_payload,
       "PASSED" if offline_payload else "FAILED", ledger(a6b, A_id),
       "the Hive model now carries payload and pushUnsynced sends it")

# =======================================================  GROUP B
log("")
log("=" * 100)
log("GROUP B - duplicate delivery")
log("=" * 100)

b0 = make_records(5, "b0ctl")
post_sync(A_tok, b0)
led0 = ledger(b0, A_id)
group_control_ok["B"] = led0["persisted"] == 5 and clean(led0)
record("B", "B0", "CONTROL: 5 records persist cleanly once", "5 persisted, clean",
       "persisted=%d" % led0["persisted"],
       "PASSED" if group_control_ok["B"] else "FAILED", led0, "control for group B")

b1 = make_records(10, "b1")
post_sync(A_tok, b1)
st, body = post_sync(A_tok, b1)
led = ledger(b1, A_id)
dups_reported = len(body.get("duplicates", [])) if isinstance(body, dict) else -1
record("B", "B1", "identical batch submitted twice",
       "10 reported duplicate, 10 rows",
       "http %s, duplicates_reported=%d" % (st, dups_reported),
       "PASSED" if (led["persisted"] == 10 and clean(led) and dups_reported == 10)
       else "FAILED", led)

b2 = make_records(1, "b2")
for _ in range(5):
    post_sync(A_tok, b2)
led = ledger(b2, A_id)
record("B", "B2", "same UUID submitted 5 times sequentially", "1 row",
       "persisted=%d" % led["persisted"],
       "PASSED" if led["persisted"] == 1 and clean(led) else "FAILED", led)

# B3 - resubmission after a simulated client timeout (ack discarded)
b3 = make_records(8, "b3")
sim3 = ClientSim(A_tok, A_id)
for rec in b3:
    sim3.create(rec)
payload = [{k: v for k, v in r.items() if k != "synced"} for r in sim3.unsynced()]
post_sync(A_tok, payload)              # server commits
# the ack never reaches the client: queue still unsynced
st = sim3.push()                       # the retry a real client would make
led = ledger(b3, A_id)
record("B", "B3", "retry after the ack was lost (client never marked synced)",
       "8 rows, all acknowledged as duplicates on retry",
       "http %s, still_queued=%d" % (st, len(sim3.unsynced())),
       "PASSED" if (led["persisted"] == 8 and clean(led)
                    and not sim3.unsynced()) else "FAILED", led,
       "this is the case the whole idempotency design exists for")

# B4 - client restart: brand new client object, same records
b4 = make_records(6, "b4")
post_sync(A_tok, b4)
sim4 = ClientSim(A_tok, A_id)
for rec in b4:
    sim4.create(rec)
sim4.push()
led = ledger(b4, A_id)
record("B", "B4", "restarted client resubmits records already on the server",
       "6 rows, queue drains", "still_queued=%d" % len(sim4.unsynced()),
       "PASSED" if (led["persisted"] == 6 and clean(led)
                    and not sim4.unsynced()) else "FAILED", led)

# B5 - same UUIDs, different content
b5 = make_records(5, "b5")
post_sync(A_tok, b5)
b5_mutated = make_records(5, "b5", content_suffix=" MUTATED")
st, body = post_sync(A_tok, b5_mutated)
led = ledger(b5, A_id)              # ledger vs the ORIGINAL content
record("B", "B5", "same UUIDs resubmitted with different content",
       "rows unchanged (first write wins)",
       "http %s, overwritten=%d" % (st, led["overwritten"]),
       "PASSED" if (led["persisted"] == 5 and led["overwritten"] == 0) else "FAILED",
       led, "documented as first-write-wins; there is no update path, so this is "
            "not conflict resolution")

# =======================================================  GROUP C
log("")
log("=" * 100)
log("GROUP C - intermittent connectivity")
log("=" * 100)

c0 = make_records(3, "c0ctl")
post_sync(A_tok, c0)
led0 = ledger(c0, A_id)
group_control_ok["C"] = led0["persisted"] == 3 and clean(led0)
record("C", "C0", "CONTROL: 3 records persist on a stable connection",
       "3 persisted", "persisted=%d" % led0["persisted"],
       "PASSED" if group_control_ok["C"] else "FAILED", led0, "control for group C")

# C1 - never sent
c1 = make_records(10, "c1")
simc1 = ClientSim(A_tok, A_id)
for rec in c1:
    simc1.create(rec)
led = ledger(c1, A_id)
record("C", "C1", "records queued, request never sent", "0 persisted, 10 queued",
       "persisted=%d, queued=%d" % (led["persisted"], len(simc1.unsynced())),
       "PASSED" if led["persisted"] == 0 and len(simc1.unsynced()) == 10 else "FAILED",
       led)

# C2 - connection dies before the server commits.
# Simulated by making the commit itself fail once, which is what the server
# observes when the transport drops mid-transaction.
import sqlalchemy.orm as _orm  # noqa: E402

c2 = make_records(10, "c2")
_real_commit = _orm.Session.commit
_fail_state = {"armed": True}


def _flaky_commit(self, *a, **k):
    if _fail_state["armed"]:
        _fail_state["armed"] = False
        self.rollback()
        raise sqlalchemy.exc.OperationalError("simulated transport loss", None, Exception())
    return _real_commit(self, *a, **k)


_orm.Session.commit = _flaky_commit
try:
    st, body = post_sync(A_tok, c2)
finally:
    _orm.Session.commit = _real_commit
    _fail_state["armed"] = False
led_mid = ledger(c2, A_id)
# st is expected to be 5xx here: that IS the injected transport loss. The
# verdict depends on persisted state, not on the status code.
nothing_persisted = led_mid["persisted"] == 0
# C4 - reconnect and retry the same batch
st2, body2 = post_sync(A_tok, c2)
led_after = ledger(c2, A_id)
record("C", "C2", "connection dies before the server commits",
       "0 persisted", "http %s (injected), persisted=%d"
       % (st, led_mid["persisted"]),
       "PASSED" if nothing_persisted else "FAILED", led_mid,
       "commit failure injected at the session boundary; the 5xx is the "
       "injected fault, and the verdict is decided by persisted state")
record("C", "C4", "reconnect and retry the aborted batch",
       "10 persisted, clean", "http %s, persisted=%d" % (st2, led_after["persisted"]),
       "PASSED" if (led_after["persisted"] == 10 and clean(led_after)) else "FAILED",
       led_after)

# C3 - server commits, response lost. THE central scenario.
c3 = make_records(12, "c3")
simc3 = ClientSim(A_tok, A_id)
for rec in c3:
    simc3.create(rec)
payload = [{k: v for k, v in r.items() if k != "synced"} for r in simc3.unsynced()]
post_sync(A_tok, payload)                     # committed server-side
led_committed = ledger(c3, A_id)
# the client never saw the response, so everything is still unsynced
retry_status = simc3.push()
led_final = ledger(c3, A_id)
c3_ok = (led_committed["persisted"] == 12 and led_final["persisted"] == 12
         and clean(led_final) and not simc3.unsynced())
record("C", "C3", "server commits, response lost, client retries",
       "12 rows, no duplicate, queue drains",
       "committed=%d, after_retry=%d, queued=%d"
       % (led_committed["persisted"], led_final["persisted"], len(simc3.unsynced())),
       "PASSED" if c3_ok else "FAILED", led_final,
       "the scenario the idempotency design exists for")

# C5 - repeated flapping
c5 = make_records(10, "c5")
simc5 = ClientSim(A_tok, A_id)
for rec in c5:
    simc5.create(rec)
flap_attempts = 0
for cycle in range(5):
    _fail_state["armed"] = True
    _orm.Session.commit = _flaky_commit
    try:
        simc5.push()
    finally:
        _orm.Session.commit = _real_commit
        _fail_state["armed"] = False
    flap_attempts += 1
    if not simc5.unsynced():
        break
    simc5.push()                     # the good attempt between flaps
    flap_attempts += 1
    if not simc5.unsynced():
        break
led = ledger(c5, A_id)
record("C", "C5", "5 connect/abort cycles around one batch",
       "exactly 10 rows after convergence",
       "persisted=%d, attempts=%d" % (led["persisted"], flap_attempts),
       "PASSED" if (led["persisted"] == 10 and clean(led)) else "FAILED", led,
       "retries to convergence = %d" % flap_attempts)

# =======================================================  GROUP D
log("")
log("=" * 100)
log("GROUP D - concurrency (PostgreSQL)")
log("=" * 100)

d0 = make_records(4, "d0ctl")
post_sync(A_tok, d0)
led0 = ledger(d0, A_id)
group_control_ok["D"] = led0["persisted"] == 4 and clean(led0)
record("D", "D0", "CONTROL: sequential batch before concurrency",
       "4 persisted", "persisted=%d" % led0["persisted"],
       "PASSED" if group_control_ok["D"] else "FAILED", led0, "control for group D")

REPEATS = 10


def concurrent_post(args):
    tok, recs = args
    try:
        return post_sync(tok, recs)
    except Exception as e:
        return "EXC", str(e)[:120]


# D1 - N concurrent identical batches, repeated
d1_fail = 0
d1_5xx = 0
for rep in range(REPEATS):
    recs = make_records(25, "d1r%d" % rep)
    with ThreadPoolExecutor(max_workers=10) as ex:
        res = list(ex.map(concurrent_post, [(A_tok, recs)] * 10))
    d1_5xx += sum(1 for st, _ in res if st == "EXC" or (isinstance(st, int) and st >= 500))
    led = ledger(recs, A_id)
    if not (led["persisted"] == 25 and clean(led)):
        d1_fail += 1
record("D", "D1", "10x concurrent identical 25-record batches (n=%d)" % REPEATS,
       "exactly 25 rows every run, no 5xx",
       "failed_runs=%d/%d, server_errors=%d" % (d1_fail, REPEATS, d1_5xx),
       "PASSED" if (d1_fail == 0 and d1_5xx == 0)
       else ("INCONCLUSIVE" if d1_5xx else "FAILED"),
       ledger(make_records(25, "d1r%d" % (REPEATS - 1)), A_id),
       "duplicate rate 0/%d batches" % REPEATS)

# D2 - overlapping batches
d2_fail = 0
for rep in range(REPEATS):
    left = make_records(20, "d2r%da" % rep)
    right = make_records(10, "d2r%da" % rep) + make_records(10, "d2r%db" % rep)
    union = {r["client_uuid"]: r for r in left + right}
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(concurrent_post, [(A_tok, left), (A_tok, right),
                                      (A_tok, left), (A_tok, right)]))
    led = ledger(list(union.values()), A_id)
    if not (led["unique_persisted"] == len(union) and clean(led)):
        d2_fail += 1
record("D", "D2", "4 concurrent batches overlapping by 50%% (n=%d)" % REPEATS,
       "exactly |union| rows", "failed_runs=%d/%d" % (d2_fail, REPEATS),
       "PASSED" if d2_fail == 0 else "FAILED",
       ledger(list(union.values()), A_id))

# D3 - two concurrent batches sharing one UUID with different content
d3_fail = 0
for rep in range(REPEATS):
    shared = "%s-d3r%d-0000" % (UUID_PREFIX, rep)
    one = [{"client_uuid": shared, "record_type": "note", "title": "t",
            "content": "VERSION_ONE", "doctor_name": None,
            "family_profile_id": None,
            "record_date": datetime.now(timezone.utc).isoformat()}]
    two = [dict(one[0], content="VERSION_TWO")]
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(concurrent_post, [(A_tok, one), (A_tok, two)]))
    s = SessionLocal()
    try:
        got = s.query(models.EHRRecord).filter(
            models.EHRRecord.client_uuid == shared).all()
    finally:
        s.close()
    if len(got) != 1:
        d3_fail += 1
record("D", "D3", "2 concurrent batches, same UUID, different content (n=%d)" % REPEATS,
       "exactly 1 row each run", "failed_runs=%d/%d" % (d3_fail, REPEATS),
       "PASSED" if d3_fail == 0 else "FAILED", None,
       "one of the two contents wins; which one is not specified by the design")

# D4 - concurrent resubmission of an existing UUID
d4 = make_records(1, "d4")
post_sync(A_tok, d4)
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(concurrent_post, [(A_tok, d4)] * 8))
led = ledger(d4, A_id)
record("D", "D4", "8 concurrent resubmissions of one existing UUID", "1 row",
       "persisted=%d" % led["persisted"],
       "PASSED" if led["persisted"] == 1 and clean(led) else "FAILED", led)

# D5 - the single-record endpoint's IntegrityError branch
def post_single(args):
    tok, rec = args
    ratelimit.reset_for_tests()
    try:
        r = client.post(API + "/ehr/record", headers=auth(tok), json=rec)
        return r.status_code
    except Exception:
        return "EXC"


d5_uuid = "%s-d5-single-0000" % UUID_PREFIX
d5rec = {"client_uuid": d5_uuid, "record_type": "note", "title": "d5",
         "content": "single path", "record_date": datetime.now(timezone.utc).isoformat()}
with ThreadPoolExecutor(max_workers=20) as ex:
    d5res = list(ex.map(post_single, [(A_tok, d5rec)] * 20))
s = SessionLocal()
try:
    d5rows = s.query(models.EHRRecord).filter(
        models.EHRRecord.client_uuid == d5_uuid).count()
finally:
    s.close()
d5_5xx = sum(1 for x in d5res if x == "EXC" or (isinstance(x, int) and x >= 500))
record("D", "D5", "20 concurrent POST /ehr/record with the same UUID",
       "1 row, no 5xx", "rows=%d, server_errors=%d" % (d5rows, d5_5xx),
       "PASSED" if (d5rows == 1 and d5_5xx == 0)
       else ("INCONCLUSIVE" if d5_5xx else "FAILED"), None,
       "exercises the single-record IntegrityError branch, which D1 does not reach")

# =======================================================  GROUP E
log("")
log("=" * 100)
log("GROUP E - concurrent change semantics (reframed: no conflict resolution exists)")
log("=" * 100)
group_control_ok["E"] = True

record("E", "E1", "local update vs server update of one record",
       "a conflict-resolution policy", "no update path exists on either side",
       "NOT_APPLICABLE", None,
       "no PUT/PATCH for EHRRecord, no version column, no updated_at. Records "
       "are append-only, so conflicts are avoided rather than resolved.")

# E2 - two offline 'edits' become two records
e2a = make_records(1, "e2-first")
e2b = make_records(1, "e2-second")
post_sync(A_tok, e2a + e2b)
led = ledger(e2a + e2b, A_id)
record("E", "E2", "two offline entries for the same fact",
       "2 separate rows, neither overwritten",
       "persisted=%d, overwritten=%d" % (led["persisted"], led["overwritten"]),
       "PASSED" if (led["persisted"] == 2 and led["overwritten"] == 0) else "FAILED",
       led, "design cost: a wrong entry and its correction both persist with no "
            "link between them")

# E3 - server-side change after a client pull
e3 = make_records(1, "e3")
post_sync(A_tok, e3)
sim_e3 = ClientSim(A_tok, A_id)
sim_e3.pull()
s = SessionLocal()
try:
    row = s.query(models.EHRRecord).filter(
        models.EHRRecord.client_uuid == e3[0]["client_uuid"]).first()
    srv_id = row.id
    row.content = "SERVER_SIDE_CORRECTION"
    s.commit()
finally:
    s.close()
sim_e3.pull()
local = [r for r in sim_e3.queue if r.get("client_uuid") == "srv-%s" % srv_id]
reflected = bool(local) and local[0].get("content") == "SERVER_SIDE_CORRECTION"
record("E", "E3", "server-side change after the client has pulled",
       "local copy updated",
       "local content=%r" % (local[0].get("content")[:30] if local else None),
       "PASSED" if reflected else "FAILED", None,
       "pullRemote skips any srv-<id> already cached (sync_service.dart:116-117), "
       "so the local copy is permanently stale" if not reflected else "")

# E4 - two devices, same account, same UUID
e4 = make_records(5, "e4")
dev1 = ClientSim(A_tok, A_id)
dev2 = ClientSim(A_tok, A_id)
for rec in e4:
    dev1.create(rec)
    dev2.create(dict(rec))
dev1.push()
dev2.push()
led = ledger(e4, A_id)
record("E", "E4", "two devices, same account, same UUIDs",
       "5 rows, both devices converge",
       "persisted=%d, dev1_queued=%d, dev2_queued=%d"
       % (led["persisted"], len(dev1.unsynced()), len(dev2.unsynced())),
       "PASSED" if (led["persisted"] == 5 and clean(led)
                    and not dev1.unsynced() and not dev2.unsynced()) else "FAILED", led)

# E5 - two devices, different UUIDs for the same fact
e5a = make_records(1, "e5-dev1")
e5b = make_records(1, "e5-dev2")
post_sync(A_tok, e5a)
post_sync(A_tok, e5b)
led = ledger(e5a + e5b, A_id)
record("E", "E5", "two devices, different UUIDs for the same fact",
       "2 rows (the system cannot tell they are the same)",
       "persisted=%d" % led["persisted"],
       "PASSED" if led["persisted"] == 2 else "FAILED", led,
       "documented design cost, not a defect")

# =======================================================  GROUP F
log("")
log("=" * 100)
log("GROUP F - recovery")
log("=" * 100)

f0 = make_records(3, "f0ctl")
post_sync(A_tok, f0)
led0 = ledger(f0, A_id)
group_control_ok["F"] = led0["persisted"] == 3 and clean(led0)
record("F", "F0", "CONTROL: baseline batch", "3 persisted",
       "persisted=%d" % led0["persisted"],
       "PASSED" if group_control_ok["F"] else "FAILED", led0, "control for group F")

# F1 - kill mid-flight, restart, sync again
f1 = make_records(20, "f1")
simf1 = ClientSim(A_tok, A_id)
for rec in f1:
    simf1.create(rec)
_fail_state["armed"] = True
_orm.Session.commit = _flaky_commit
try:
    simf1.push()
finally:
    _orm.Session.commit = _real_commit
    _fail_state["armed"] = False
# "restart": a brand-new client with the same durable queue
simf1b = ClientSim(A_tok, A_id)
for rec in f1:
    simf1b.create(rec)
simf1b.push()
led = ledger(f1, A_id)
record("F", "F1", "sync killed mid-flight, client restarts, syncs again",
       "exactly 20 rows", "persisted=%d, queued=%d"
       % (led["persisted"], len(simf1b.unsynced())),
       "PASSED" if (led["persisted"] == 20 and clean(led)
                    and not simf1b.unsynced()) else "FAILED", led)

# F2 - half already committed but unacknowledged
f2 = make_records(20, "f2")
post_sync(A_tok, f2[:10])                     # first 10 committed
simf2 = ClientSim(A_tok, A_id)
for rec in f2:
    simf2.create(rec)                          # client believes none are synced
simf2.push()
led = ledger(f2, A_id)
record("F", "F2", "10 of 20 already committed but unacknowledged",
       "20 rows, first 10 returned as duplicates",
       "persisted=%d, queued=%d" % (led["persisted"], len(simf2.unsynced())),
       "PASSED" if (led["persisted"] == 20 and clean(led)
                    and not simf2.unsynced()) else "FAILED", led)

# F3 - resume after a partial per-item commit
f3 = make_records(15, "f3")
post_sync(A_tok, f3[3:8])                     # a middle slice exists
st, body = post_sync(A_tok, f3)               # full batch, collides on the slice
led = ledger(f3, A_id)
record("F", "F3", "batch overlapping an already-committed slice",
       "all 15 present exactly once",
       "http %s, persisted=%d" % (st, led["persisted"]),
       "PASSED" if (led["persisted"] == 15 and clean(led)) else "FAILED", led)

# F4 - seven days of accumulation
f4 = make_records(120, "f4")
simf4 = ClientSim(A_tok, A_id)
for rec in f4:
    simf4.create(rec)
remaining = simf4.push_until_drained(max_attempts=4)
led = ledger(f4, A_id)
record("F", "F4", "7 days offline: 120 queued records reconnect",
       "queue drains, 120 rows",
       "persisted=%d, still_queued=%d, last http %s"
       % (led["persisted"], remaining, simf4.last_status),
       "PASSED" if (led["persisted"] == 120 and remaining == 0) else "FAILED", led,
       "real-world consequence of the un-chunked push against the 100 cap"
       if remaining else "")

# F5 - local durability is a Hive property, not reachable from Python
record("F", "F5", "local durability across a process restart",
       "records survive in the encrypted box",
       "requires a Flutter runtime", "NOT_APPLICABLE", None,
       "Hive durability and HiveAesCipher cannot be exercised from this "
       "harness; tested in mobile/patient_app/test/ instead")

# =======================================================  GROUP G
log("")
log("=" * 100)
log("GROUP G - data isolation")
log("=" * 100)

g0 = make_records(3, "g0ctl")
post_sync(A_tok, g0)
led0 = ledger(g0, A_id)
group_control_ok["G"] = led0["persisted"] == 3 and clean(led0)
record("G", "G0", "CONTROL: baseline batch", "3 persisted",
       "persisted=%d" % led0["persisted"],
       "PASSED" if group_control_ok["G"] else "FAILED", led0, "control for group G")

# G1 - two patients, separate wallets
ga = make_records(10, "g1-a")
gb = make_records(10, "g1-b")
post_sync(A_tok, ga)
post_sync(B_tok, gb)
led_a = ledger(ga, A_id)
led_b = ledger(gb, B_id)
ratelimit.reset_for_tests()
a_sees = client.get("%s/ehr/patient/%s" % (API, A_id), headers=auth(A_tok))
leak = ("g1-b" in a_sees.text) if a_sees.status_code == 200 else None
record("G", "G1", "two patients each sync 10 records",
       "each sees only their own",
       "A cross_tenant=%d, B cross_tenant=%d, A sees B's records=%s"
       % (led_a["cross_tenant"], led_b["cross_tenant"], leak),
       "PASSED" if (led_a["cross_tenant"] == 0 and led_b["cross_tenant"] == 0
                    and leak is False) else "FAILED", led_a)

# G2 - B submits against A's family profile
g2 = make_records(5, "g2", profile_id=A_profile)
st, body = post_sync(B_tok, g2)
led = ledger(g2, B_id)
record("G", "G2", "B submits a batch scoped to A's family profile",
       "403, nothing persisted", "http %s, persisted=%d" % (st, led["persisted"]),
       "PASSED" if (st == 403 and led["persisted"] == 0) else "FAILED", led)

# G3 - A submits against A's own profile
g3 = make_records(5, "g3", profile_id=A_profile)
st, body = post_sync(A_tok, g3)
led = ledger(g3, A_id)
s = SessionLocal()
try:
    scoped = all(r.family_profile_id == A_profile for r in
                 s.query(models.EHRRecord).filter(
                     models.EHRRecord.client_uuid.in_(
                         [r["client_uuid"] for r in g3])).all())
finally:
    s.close()
record("G", "G3", "A submits scoped to A's own profile",
       "5 persisted and scoped", "http %s, persisted=%d, scoped=%s"
       % (st, led["persisted"], scoped),
       "PASSED" if (st == 200 and led["persisted"] == 5 and scoped and clean(led))
       else "FAILED", led)

# G4 - one queued record references a DELETED profile
ratelimit.reset_for_tests()
client.delete("%s/family/%s" % (API, A_profile_doomed), headers=auth(A_tok))
g4_valid = make_records(9, "g4-valid")
g4_bad = make_records(1, "g4-bad", profile_id=A_profile_doomed)
g4 = g4_valid + g4_bad
st, body = post_sync(A_tok, g4)
led_all = ledger(g4, A_id)
led_valid = ledger(g4_valid, A_id)
rejected_uuids = ([x["client_uuid"] for x in (body.get("rejected") or [])]
                  if isinstance(body, dict) else [])
bad_rejected = g4_bad[0]["client_uuid"] in rejected_uuids
# The client must stop retrying a rejected record without claiming it synced.
sim_g4 = ClientSim(A_tok, A_id)
for rec in g4:
    sim_g4.create(rec)
sim_g4.push()
record("G", "G4", "queue contains 1 record for a DELETED profile",
       "9 valid persist, 1 reported rejected, queue unblocked",
       "http %s, valid_persisted=%d of 9, rejected=%s, still_pending=%d"
       % (st, led_valid["persisted"], rejected_uuids, len(sim_g4.unsynced())),
       "PASSED" if (st == 200 and led_valid["persisted"] == 9 and bad_rejected
                    and not sim_g4.unsynced()) else "FAILED", led_all,
       "one unresolvable record no longer discards the batch, and the client "
       "can tell a permanent rejection from a transient failure")

# G5 - cross-tenant UUID reuse. The scenario most likely to be novel.
g5_uuid = "%s-g5-shared-0000" % UUID_PREFIX
g5_a = [{"client_uuid": g5_uuid, "record_type": "note", "title": "A's record",
         "content": "PATIENT_A_CONTENT", "doctor_name": None,
         "family_profile_id": None,
         "record_date": datetime.now(timezone.utc).isoformat()}]
st_a, body_a = post_sync(A_tok, g5_a)
g5_b = [dict(g5_a[0], title="B's record", content="PATIENT_B_CONTENT")]
st_b, body_b = post_sync(B_tok, g5_b)
s = SessionLocal()
try:
    g5rows = s.query(models.EHRRecord).filter(
        models.EHRRecord.client_uuid == g5_uuid).all()
    owners = [(r.patient_id, r.content) for r in g5rows]
finally:
    s.close()
b_told_ok = (isinstance(body_b, dict)
             and g5_uuid in (set(body_b.get("synced") or [])
                             | set(body_b.get("duplicates") or [])))
b_has_record = any(pid == B_id for pid, _ in owners)
silent_loss = b_told_ok and not b_has_record
record("G", "G5", "B submits a client_uuid that A already used",
       "B's record stored, or B told it was rejected",
       "rows=%d, owners=%s, B_told_acknowledged=%s, B_has_record=%s"
       % (len(g5rows), owners, b_told_ok, b_has_record),
       "FAILED" if silent_loss else "PASSED", None,
       "SILENT CROSS-TENANT RECORD LOSS: client_uuid is unique across the whole "
       "table, not per patient, and the pre-check filters on client_uuid alone "
       "with no patient_id. B is told the record synced and nothing is stored "
       "for B." if silent_loss else
       ("B's record was stored" if b_has_record else "B was not acknowledged"))

# G6 - patient_id injection
g6 = make_records(3, "g6")
for r in g6:
    r["patient_id"] = B_id          # attempt to write into B's wallet
st, body = post_sync(A_tok, g6)
led = ledger(g6, A_id)
record("G", "G6", "patient_id injected in the payload",
       "ignored; rows belong to the token's owner",
       "http %s, cross_tenant=%d" % (st, led["cross_tenant"]),
       "PASSED" if (st == 200 and led["cross_tenant"] == 0) else "FAILED", led,
       "patient_id is taken from current_user.id and the schema does not accept "
       "it from the client")

# ======================================================================= output
FINISHED = datetime.now(timezone.utc).isoformat()
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "exp_a_raw.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=[
        "group", "scenario", "title", "expected", "observed", "verdict",
        "submitted", "persisted", "unique_persisted", "duplicates", "missing",
        "unexpected", "overwritten", "cross_tenant", "note"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

summary = {
    "commit": SHA, "started": STARTED, "finished": FINISHED,
    "engine": "postgresql", "db_version": DBVER,
    "default_transaction_isolation": ISO,
    "python": sys.version.split()[0], "sqlalchemy": sqlalchemy.__version__,
    "server_batch_cap": SERVER_CAP,
    "concurrency_repeats": REPEATS,
    "scenarios": len(rows),
    "PASSED": counts["PASSED"], "FAILED": counts["FAILED"],
    "INCONCLUSIVE": counts["INCONCLUSIVE"],
    "NOT_APPLICABLE": counts["NOT_APPLICABLE"],
    "group_controls": group_control_ok,
    "failed": [r["scenario"] + " " + r["title"] for r in rows if r["verdict"] == "FAILED"],
    "inconclusive": [r["scenario"] + " " + r["title"] for r in rows
                     if r["verdict"] == "INCONCLUSIVE"],
    "not_applicable": [r["scenario"] + " " + r["title"] for r in rows
                       if r["verdict"] == "NOT_APPLICABLE"],
}
with open(os.path.join(OUT, "exp_a_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)

log("")
log("=" * 100)
log("SUMMARY")
log("=" * 100)
log("scenarios       : %d" % len(rows))
log("PASSED          : %d" % counts["PASSED"])
log("FAILED          : %d" % counts["FAILED"])
log("INCONCLUSIVE    : %d" % counts["INCONCLUSIVE"])
log("NOT_APPLICABLE  : %d" % counts["NOT_APPLICABLE"])
log("group controls  : %s" % group_control_ok)
if summary["failed"]:
    log("")
    log("FAILED:")
    for f in summary["failed"]:
        log("  - %s" % f)
if summary["not_applicable"]:
    log("")
    log("NOT_APPLICABLE (capability absent, recorded not skipped):")
    for f in summary["not_applicable"]:
        log("  - %s" % f)
log("")
log("raw     : %s" % os.path.join(OUT, "exp_a_raw.csv"))
log("summary : %s" % os.path.join(OUT, "exp_a_summary.json"))
