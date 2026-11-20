"""Experiment A · Phase 4 — metrics.

Ten metrics, each with its calculation stated, measured over repeated runs
against an isolated PostgreSQL database. Rates are reported as
numerator/denominator with a Wilson 95% confidence interval. Latencies are
reported as median, p95 and p99, and only when the sample size supports them.

Every quantity is derived from PERSISTED DATABASE STATE, never from an HTTP
status code.

Usage:
    EXPA_DATABASE_URL=postgresql://expa:...@localhost:5434/expa_metrics \
      .venv/Scripts/python.exe research/experiments/exp_a/sync_metrics.py
"""
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SERVICE = os.path.join(REPO, "backend", "python_service")
sys.path.insert(0, SERVICE)

URL = os.environ.get("EXPA_DATABASE_URL", "")
if not URL.startswith("postgres"):
    raise SystemExit("EXPA_DATABASE_URL must be a PostgreSQL URL.")
for banned in ("supabase.co", "neon.tech", "render.com", "amazonaws.com"):
    if banned in URL:
        raise SystemExit("Refusing to run against %s." % banned)

os.environ["DATABASE_URL"] = URL
os.environ.setdefault("JWT_SECRET_KEY", "expa-metrics-not-for-production")
for _v in ("GEMINI_API_KEY", "GEMINI_API_KEYS", "OPENAI_API_KEY", "OPENAI_API_KEYS",
           "GROQ_API_KEY", "GROQ_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
           "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_CLOUD_NAME",
           "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY",
           "MSG91_AUTH_KEY", "RESEND_API_KEY"):
    os.environ[_v] = ""
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
import sqlalchemy  # noqa: E402
import sqlalchemy.orm as _orm  # noqa: E402
import models  # noqa: E402
from database import engine, SessionLocal  # noqa: E402
from core import ratelimit  # noqa: E402
from main import app  # noqa: E402

API = "/api/v1"
PW = "strongpass123"
SERVER_CAP = 100
client = TestClient(app, raise_server_exceptions=False)

UUID_PREFIX = "expam"
metrics = []


def log(m=""):
    sys.stdout.write(m + "\n")
    sys.stdout.flush()


def auth(t):
    return {"Authorization": "Bearer %s" % t}


def wilson(k, n, z=1.96):
    """Wilson score interval for a binomial proportion. Returned as
    (low, high) in [0, 1]. Defined here because scipy is not a dependency."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(vals, q):
    """Nearest-rank percentile. Reported only where n supports it."""
    if not vals:
        return None
    sv = sorted(vals)
    idx = min(len(sv) - 1, max(0, int(math.ceil(q / 100.0 * len(sv))) - 1))
    return sv[idx]


def emit(mid, name, definition, numerator=None, denominator=None,
         value=None, unit="", n=None, note=""):
    rate = None
    lo = hi = None
    if numerator is not None and denominator:
        rate = numerator / denominator
        lo, hi = wilson(numerator, denominator)
    metrics.append({
        "id": mid, "metric": name, "definition": definition,
        "numerator": numerator, "denominator": denominator,
        "rate": ("%.6f" % rate) if rate is not None else "",
        "ci95_low": ("%.6f" % lo) if lo is not None and not math.isnan(lo) else "",
        "ci95_high": ("%.6f" % hi) if hi is not None and not math.isnan(hi) else "",
        "value": value if value is not None else "",
        "unit": unit, "sample_size": n if n is not None else (denominator or ""),
        "note": note,
    })
    if rate is not None:
        log("  %-4s %-44s %s/%s = %.4f  (95%% CI %.4f-%.4f)  n=%s%s"
            % (mid, name[:44], numerator, denominator, rate, lo, hi,
               n if n is not None else denominator,
               ("  | " + note) if note else ""))
    else:
        log("  %-4s %-44s %s %s  n=%s%s"
            % (mid, name[:44], value, unit, n if n is not None else "-",
               ("  | " + note) if note else ""))


def make_records(n, prefix, when=None, profile_id=None):
    out = []
    for i in range(n):
        cu = "%s-%s-%04d" % (UUID_PREFIX, prefix, i)
        out.append({
            "client_uuid": cu, "record_type": "note",
            "title": "%s t%d" % (prefix, i), "content": "%s c%d" % (prefix, i),
            "doctor_name": None, "family_profile_id": profile_id,
            "record_date": (when or datetime.now(timezone.utc)).isoformat(),
        })
    return out


def post_sync(token, records):
    ratelimit.reset_for_tests()
    t0 = time.perf_counter()
    r = client.post(API + "/ehr/sync", headers=auth(token),
                    json={"records": records})
    dt = (time.perf_counter() - t0) * 1000.0
    try:
        return r.status_code, r.json(), dt
    except Exception:
        return r.status_code, r.text[:200], dt


def persisted_state(records, patient_id):
    uuids = [r["client_uuid"] for r in records]
    content_by = {r["client_uuid"]: r["content"] for r in records}
    s = SessionLocal()
    try:
        got = s.query(models.EHRRecord).filter(
            models.EHRRecord.client_uuid.in_(uuids)).all() if uuids else []
        unique = len({r.client_uuid for r in got})
        return {
            "persisted": len(got),
            "unique": unique,
            "duplicates": len(got) - unique,
            "missing": len(set(uuids)) - unique,
            "cross": sum(1 for r in got if r.patient_id != patient_id),
            "overwritten": sum(1 for r in got if r.client_uuid in content_by
                               and r.content != content_by[r.client_uuid]),
        }
    finally:
        s.close()


def mk(username):
    ratelimit.reset_for_tests()
    client.post(API + "/auth/register", json={
        "username": username, "email": "%s@expam.gramcare.in" % username,
        "password": PW, "full_name": "Metrics %s" % username, "role": "PATIENT"})
    s = SessionLocal()
    u = s.query(models.User).filter(models.User.username == username).first()
    u.is_verified = True
    s.commit(); uid = u.id; s.close()
    ratelimit.reset_for_tests()
    r = client.post(API + "/auth/login", data={"username": username, "password": PW})
    return r.json()["access_token"], uid


class ClientSim:
    """Same reimplementation of sync_service.dart used by the scenario
    harness: unchunked whole-queue push, ack on synced OR duplicates, no
    retry accounting."""

    def __init__(self, token):
        self.token = token
        self.queue = []
        self.attempts = 0

    def create_many(self, recs):
        for r in recs:
            self.queue.append(dict(r, synced=False))

    def unsynced(self):
        return [r for r in self.queue if not r["synced"]]

    def push(self):
        pending = self.unsynced()
        if not pending:
            return None, 0.0
        self.attempts += 1
        payload = [{k: v for k, v in r.items() if k != "synced"} for r in pending]
        st, body, dt = post_sync(self.token, payload)
        if st == 200 and isinstance(body, dict):
            ack = set(body.get("synced") or []) | set(body.get("duplicates") or [])
            for r in pending:
                if r["client_uuid"] in ack:
                    r["synced"] = True
        return st, dt

    def drain(self, max_attempts=6):
        total_ms = 0.0
        for _ in range(max_attempts):
            if not self.unsynced():
                break
            _, dt = self.push()
            total_ms += dt
        return len(self.unsynced()), total_ms


# ---------------------------------------------------------------------- run
try:
    SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
except Exception:
    SHA = "unknown"
STARTED = datetime.now(timezone.utc).isoformat()

models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)
with engine.connect() as c:
    DBVER = c.execute(sqlalchemy.text("select version()")).scalar()
    ISO = c.execute(sqlalchemy.text("show transaction_isolation")).scalar()

log("=" * 104)
log("Experiment A - Phase 4 metrics")
log("=" * 104)
log("commit   : %s" % SHA)
log("started  : %s" % STARTED)
log("postgres : %s" % DBVER[:76])
log("isolation: %s" % ISO)
log("")

A_tok, A_id = mk("expam_a")
B_tok, B_id = mk("expam_b")

REPS = 30            # repeats for the rate metrics
BATCH = 20           # records per batch for the latency metrics

# ---------------------------------------------------------------- M1, M9
log("M1 / M9 - clean-path success and batch completion time (n=%d batches of %d)"
    % (REPS, BATCH))
m1_success = 0
m9_latency = []
for rep in range(REPS):
    recs = make_records(BATCH, "m1r%03d" % rep)
    st, body, dt = post_sync(A_tok, recs)
    state = persisted_state(recs, A_id)
    ok = (state["unique"] == BATCH and state["duplicates"] == 0
          and state["missing"] == 0 and state["cross"] == 0)
    if ok:
        m1_success += 1
    if st == 200:
        m9_latency.append(dt)
emit("M1", "synchronisation success rate",
     "batches where unique_persisted == submitted AND duplicates == 0 AND "
     "missing == 0 AND cross_tenant == 0, over batches submitted on a clean "
     "connection",
     m1_success, REPS, n=REPS)
emit("M9", "batch completion time (median)",
     "wall-clock ms from request start to response, %d-record batch, "
     "in-process ASGI (no network)" % BATCH,
     value="%.1f" % statistics.median(m9_latency), unit="ms", n=len(m9_latency))
emit("M9b", "batch completion time (p95)", "nearest-rank p95 of the same sample",
     value="%.1f" % pct(m9_latency, 95), unit="ms", n=len(m9_latency))
emit("M9c", "batch completion time (p99)",
     "nearest-rank p99; n=%d is too small for a stable p99 and it is reported "
     "only for completeness" % len(m9_latency),
     value="%.1f" % pct(m9_latency, 99), unit="ms", n=len(m9_latency),
     note="UNDERPOWERED at n=%d" % len(m9_latency))

# ---------------------------------------------------------------- M2, M3, M4
log("")
log("M2 / M3 / M4 - duplicate, loss and integrity-violation rates")
log("         (every batch submitted 3x: fresh, immediate resend, resend after "
    "a lost ack)")
m2_dup_records = 0
m3_lost_records = 0
m4_violating_batches = 0
m_total_records = 0
for rep in range(REPS):
    recs = make_records(BATCH, "m2r%03d" % rep)
    post_sync(A_tok, recs)
    post_sync(A_tok, recs)
    post_sync(A_tok, recs)
    state = persisted_state(recs, A_id)
    m_total_records += BATCH
    m2_dup_records += state["duplicates"]
    m3_lost_records += state["missing"]
    if (state["duplicates"] or state["missing"] or state["cross"]
            or state["overwritten"]):
        m4_violating_batches += 1
emit("M2", "duplicate insertion rate",
     "extra rows beyond one per submitted client_uuid, divided by records "
     "submitted, after each batch is delivered three times",
     m2_dup_records, m_total_records, n=REPS)
emit("M3", "record-loss rate",
     "submitted client_uuids with no persisted row, divided by records "
     "submitted (clean connection)",
     m3_lost_records, m_total_records, n=REPS)
emit("M4", "data-integrity violation rate",
     "batches with any duplicate, missing, cross-tenant or overwritten row, "
     "divided by batches",
     m4_violating_batches, REPS, n=REPS)

# ---------------------------------------------------------------- M5, M7, M8
log("")
log("M5 / M7 / M8 - recovery after an injected commit failure (n=%d)" % REPS)
_real_commit = _orm.Session.commit
_arm = {"on": False}


def _flaky(self, *a, **k):
    if _arm["on"]:
        _arm["on"] = False
        self.rollback()
        raise sqlalchemy.exc.OperationalError("injected transport loss", None,
                                              Exception())
    return _real_commit(self, *a, **k)


m5_recovered = 0
m7_convergence_ms = []
m8_retries = []
for rep in range(REPS):
    recs = make_records(BATCH, "m5r%03d" % rep)
    sim = ClientSim(A_tok)
    sim.create_many(recs)
    t0 = time.perf_counter()
    _arm["on"] = True
    _orm.Session.commit = _flaky
    try:
        sim.push()                      # fails at commit
    finally:
        _orm.Session.commit = _real_commit
        _arm["on"] = False
    left, _ = sim.drain(max_attempts=5)  # recovery attempts
    conv_ms = (time.perf_counter() - t0) * 1000.0
    state = persisted_state(recs, A_id)
    if (left == 0 and state["unique"] == BATCH and state["duplicates"] == 0
            and state["missing"] == 0):
        m5_recovered += 1
        m7_convergence_ms.append(conv_ms)
    m8_retries.append(sim.attempts)
emit("M5", "recovery success rate",
     "runs where, after one injected commit failure, the queue drained and "
     "unique_persisted == submitted with no duplicate or loss",
     m5_recovered, REPS, n=REPS)
emit("M7", "eventual-consistency convergence time (median)",
     "wall-clock ms from first push attempt to a fully drained queue, "
     "measured only on runs that converged. EXCLUDES the client's own "
     "scheduler: the shipped app's reliable retry is a 1-hour Workmanager "
     "task, so real-world convergence is bounded by that, not by this figure",
     value="%.1f" % (statistics.median(m7_convergence_ms)
                     if m7_convergence_ms else float("nan")),
     unit="ms", n=len(m7_convergence_ms))
emit("M7b", "eventual-consistency convergence time (p95)",
     "nearest-rank p95 of the same sample",
     value="%.1f" % (pct(m7_convergence_ms, 95) or float("nan")), unit="ms",
     n=len(m7_convergence_ms))
emit("M8", "retry count to convergence (mean)",
     "push attempts per run until the queue drained, including the failed "
     "first attempt",
     value="%.2f" % statistics.mean(m8_retries), unit="attempts", n=len(m8_retries))
emit("M8b", "retry count to convergence (max)", "maximum of the same sample",
     value="%d" % max(m8_retries), unit="attempts", n=len(m8_retries))

# ---------------------------------------------------------------- M6
log("")
log("M6 - conflict-resolution correctness")
emit("M6", "conflict-resolution correctness",
     "undefined for this system: EHRRecord has no update path, no version "
     "column and no updated_at, so there is no conflict to resolve. Records "
     "are append-only and the observed policy is first-write-wins",
     value="NOT_APPLICABLE", n=0,
     note="measured instead by M6b")
# M6b - first-write-wins is at least deterministic
m6_stable = 0
for rep in range(REPS):
    recs = make_records(1, "m6r%03d" % rep)
    post_sync(A_tok, recs)
    mutated = [dict(recs[0], content="MUTATED_%d" % rep)]
    post_sync(A_tok, mutated)
    state = persisted_state(recs, A_id)     # compared against ORIGINAL content
    if state["overwritten"] == 0 and state["unique"] == 1:
        m6_stable += 1
emit("M6b", "first-write-wins stability",
     "resubmissions of an existing client_uuid carrying different content "
     "that leave the stored content unchanged, over trials",
     m6_stable, REPS, n=REPS)

# ---------------------------------------------------------------- M10
log("")
log("M10 - concurrent synchronisation correctness")
CONC = 10
CONC_BATCH = 25
m10_correct = 0
m10_5xx = 0


def _one(args):
    tok, recs = args
    try:
        st, _, _ = post_sync(tok, recs)
        return st
    except Exception:
        return "EXC"


for rep in range(REPS):
    recs = make_records(CONC_BATCH, "m10r%03d" % rep)
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        res = list(ex.map(_one, [(A_tok, recs)] * CONC))
    m10_5xx += sum(1 for x in res
                   if x == "EXC" or (isinstance(x, int) and x >= 500))
    state = persisted_state(recs, A_id)
    if (state["unique"] == CONC_BATCH and state["duplicates"] == 0
            and state["missing"] == 0 and state["cross"] == 0):
        m10_correct += 1
emit("M10", "concurrent synchronisation correctness",
     "runs where %d concurrent deliveries of the same %d-record batch yielded "
     "exactly %d rows with no duplicate, loss or cross-tenant row"
     % (CONC, CONC_BATCH, CONC_BATCH),
     m10_correct, REPS, n=REPS)
emit("M10b", "server errors under concurrency",
     "5xx or transport exceptions across %d requests (%d runs x %d concurrent)"
     % (REPS * CONC, REPS, CONC),
     m10_5xx, REPS * CONC, n=REPS * CONC)

# ------------------------------------------- M11: the deadlock, quantified
log("")
log("M11 - queue-depth ceiling (the deadlock found in Phase 3)")
depths = [50, 90, 100, 101, 120, 150, 300]
ceiling_rows = []
for d in depths:
    recs = make_records(d, "m11d%04d" % d)
    sim = ClientSim(A_tok)
    sim.create_many(recs)
    left, _ = sim.drain(max_attempts=4)
    state = persisted_state(recs, A_id)
    drained = left == 0 and state["unique"] == d
    ceiling_rows.append((d, drained, state["unique"], left))
    log("      depth %-4d -> drained=%-5s persisted=%-4d still_queued=%d"
        % (d, drained, state["unique"], left))
max_ok = max([d for d, ok, _, _ in ceiling_rows if ok], default=0)
min_bad = min([d for d, ok, _, _ in ceiling_rows if not ok], default=None)
emit("M11", "maximum drainable queue depth",
     "largest tested queue depth the shipped client algorithm can fully "
     "synchronise; above it every attempt is rejected 422 and the queue "
     "cannot drain",
     value=str(max_ok), unit="records", n=len(depths),
     note="first failing depth tested: %s" % min_bad)
emit("M11b", "queue depths that deadlock",
     "tested depths where the queue never drained, over depths tested",
     sum(1 for _, ok, _, _ in ceiling_rows if not ok), len(depths),
     n=len(depths))

# ------------------------------------------- M12: cross-tenant UUID collision
log("")
log("M12 - cross-tenant client_uuid collision (the Phase 3 G5 finding)")
m12_loss = 0
for rep in range(REPS):
    shared = "%s-m12r%03d-0000" % (UUID_PREFIX, rep)
    a_rec = [{"client_uuid": shared, "record_type": "note", "title": "A",
              "content": "A_CONTENT_%d" % rep, "doctor_name": None,
              "family_profile_id": None,
              "record_date": datetime.now(timezone.utc).isoformat()}]
    post_sync(A_tok, a_rec)
    b_rec = [dict(a_rec[0], title="B", content="B_CONTENT_%d" % rep)]
    st_b, body_b, _ = post_sync(B_tok, b_rec)
    told_ok = (isinstance(body_b, dict)
               and shared in (set(body_b.get("synced") or [])
                              | set(body_b.get("duplicates") or [])))
    s = SessionLocal()
    try:
        rows_ = s.query(models.EHRRecord).filter(
            models.EHRRecord.client_uuid == shared).all()
        b_has = any(r.patient_id == B_id for r in rows_)
    finally:
        s.close()
    if told_ok and not b_has:
        m12_loss += 1
emit("M12", "silent cross-tenant record-loss rate",
     "trials where patient B submitted a client_uuid already used by patient "
     "A, B was told the record synced, and no row exists for B, over trials",
     m12_loss, REPS, n=REPS,
     note="client_uuid is UNIQUE across the whole table rather than per "
          "patient, and the pre-check filters on client_uuid with no "
          "patient_id predicate")

# ------------------------------------------------------------------- output
FINISHED = datetime.now(timezone.utc).isoformat()
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "exp_a_metrics.csv"), "w", newline="",
          encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=[
        "id", "metric", "definition", "numerator", "denominator", "rate",
        "ci95_low", "ci95_high", "value", "unit", "sample_size", "note"])
    w.writeheader()
    for m in metrics:
        w.writerow(m)

summary = {
    "commit": SHA, "started": STARTED, "finished": FINISHED,
    "engine": "postgresql", "db_version": DBVER,
    "default_transaction_isolation": ISO,
    "python": sys.version.split()[0], "sqlalchemy": sqlalchemy.__version__,
    "repeats_per_rate_metric": REPS,
    "batch_size": BATCH,
    "concurrency": CONC,
    "concurrent_batch_size": CONC_BATCH,
    "queue_depths_tested": depths,
    "metrics": metrics,
}
with open(os.path.join(OUT, "exp_a_metrics_summary.json"), "w",
          encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)

log("")
log("=" * 104)
log("metrics written: %s" % os.path.join(OUT, "exp_a_metrics.csv"))
log("summary written: %s" % os.path.join(OUT, "exp_a_metrics_summary.json"))
