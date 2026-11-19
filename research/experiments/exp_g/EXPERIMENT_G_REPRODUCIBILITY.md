# Experiment G — Reproducibility Record

Everything needed to re-run Experiment G from a clean environment and obtain the
numbers in `EXPERIMENT_G_RESULTS.md`. Nothing here depends on state left behind
by a previous run: each script builds its own database and seeds its own
accounts.

---

## 1. Environment as executed

| | |
|---|---|
| Date executed | 19–20 November 2026 |
| Git commit (code under test) | `7c0117611174353a4b713dac934fb07854f475e2` plus the remediations in `EXPERIMENT_G_REMEDIATION_LOG.md`, which were committed after the runs — each run's `summary.json` records the SHA it actually saw |
| Host OS | Windows 11 (26200) |
| Python | 3.14.2 |
| FastAPI | 0.115.12 |
| SQLAlchemy | 2.0.41 |
| Alembic | 1.16.2 |
| Pydantic | 2.13.4 |
| psycopg2-binary | 2.9.12 |
| httpx (TestClient transport) | 0.28.1 |
| pytest | 9.1.1 |
| razorpay | 1.4.2 |
| **Engine A** | SQLite 3.50.4, throwaway file under the OS temp directory |
| **Engine B** | PostgreSQL 15.18 (`postgres:15-alpine`), isolated Docker container |
| PostgreSQL default isolation | `read committed` |
| Alembic head | `d1f7c3b9e205` |
| Migration files | 26 |
| Project test suite | 245 tests collected |

**Why PostgreSQL 15.** It matches what the project actually runs: the CI
workflow uses a `postgres:15` service container and the Docker Compose stack
uses `postgres:15-alpine`. The validation is therefore against the same major
version as production, not an arbitrary one.

---

## 2. Isolated PostgreSQL container

```powershell
docker run -d --name expg_postgres_isolated -e POSTGRES_PASSWORD=expg_synthetic_only -e POSTGRES_USER=expg -e POSTGRES_DB=expg_isolation -p 5433:5432 postgres:15-alpine
```

Notes from the actual run:

- Port **5433**. Ports 55432 and some others fall inside a Windows reserved
  range and fail with `bind: An attempt was made to access a socket in a way
  forbidden by its access permissions`. If 5433 is taken, any free port works —
  change it in the URL below.
- The credential is deliberately named `expg_synthetic_only`. It guards nothing
  real: the container holds only synthetic data and is destroyed afterwards.
- This container is **separate** from the project's own `gramcare_postgres`
  compose service, which was left running and untouched.

`phase2_postgres_validation.py` refuses to run against SQLite, and refuses
outright if the URL contains `supabase.co`, `neon.tech`, `render.com` or
`amazonaws.com`, so it cannot be pointed at real infrastructure by mistake.

---

## 3. Exact commands

Run from `backend/python_service`. Set `PG` once:

```powershell
$PG = "postgresql://expg:expg_synthetic_only@localhost:5433/expg_isolation"
```

### 3.1 Isolation matrix — both engines

```powershell
.venv\Scripts\python.exe ..\..\research\experiments\exp_g\isolation_matrix.py
```

```powershell
$env:EXPG_DATABASE_URL = $PG; .venv\Scripts\python.exe ..\..\research\experiments\exp_g\isolation_matrix.py; Remove-Item Env:\EXPG_DATABASE_URL
```

### 3.2 Coverage gaps and capability tokens — both engines

```powershell
.venv\Scripts\python.exe ..\..\research\experiments\exp_g\phase2_tokens_and_gaps.py
```

```powershell
$env:EXPG_DATABASE_URL = $PG; .venv\Scripts\python.exe ..\..\research\experiments\exp_g\phase2_tokens_and_gaps.py --engine-label postgresql; Remove-Item Env:\EXPG_DATABASE_URL
```

### 3.3 PostgreSQL-specific validation

```powershell
$env:EXPG_DATABASE_URL = $PG; .venv\Scripts\python.exe ..\..\research\experiments\exp_g\phase2_postgres_validation.py; Remove-Item Env:\EXPG_DATABASE_URL
```

### 3.4 Targeted regression checks

```powershell
.venv\Scripts\python.exe ..\..\research\experiments\exp_g\verify_ehr_records_scoping.py
```

```powershell
.venv\Scripts\python.exe ..\..\research\experiments\exp_g\verify_sos_track_remediation.py
```

### 3.5 Migration chain on a fresh PostgreSQL database

```powershell
docker exec expg_postgres_isolated psql -U expg -d postgres -c "DROP DATABASE IF EXISTS expg_migrations;" -c "CREATE DATABASE expg_migrations;"
```

```powershell
$env:DATABASE_URL = "postgresql://expg:expg_synthetic_only@localhost:5433/expg_migrations"; .venv\Scripts\python.exe -m alembic upgrade head; Remove-Item Env:\DATABASE_URL
```

### 3.6 Project test suite

```powershell
.venv\Scripts\python.exe -m pytest -q
```

### 3.7 Regenerate the CSV deliverables

```powershell
.venv\Scripts\python.exe ..\..\research\experiments\exp_g\build_deliverables.py
```

### 3.8 Tear down

```powershell
docker rm -f expg_postgres_isolated
```

---

## 4. Clean-environment guarantees

| Concern | How it is handled |
|---|---|
| Leftover rows skewing canary detection | the PostgreSQL database is dropped and recreated before each run; the SQLite runs use a fresh temp file per invocation; `phase2_postgres_validation.py` additionally does `drop_all` then `create_all` so row counts are unambiguous |
| Rate-limit counters bleeding between probes | `ratelimit.reset_for_tests()` is called before each seeding step and before each probe group. The B2 probe deliberately exhausts buckets, so every probe after it resets first — without this, later probes were answered 429 and misreported as findings |
| Calls reaching real third-party services | every external credential is set to the empty string before the app is imported: Gemini, OpenAI, Groq, Anthropic, Razorpay, Cloudinary, Google Maps, MSG91, Resend. The AI layer falls back to its mock provider, uploads fall back to the database-backed file store, and geocoding falls back to the offline haversine path |
| Accidental production access | the PostgreSQL script hard-refuses URLs containing known managed-host domains; no script reads the project's `.env` |
| Emailing or texting real people | Resend and MSG91 keys blank; the run logs show the sends being skipped |
| Background escalation loop interfering | `TESTING=1` disables the SOS escalation loop |

---

## 5. Synthetic account definitions

No real person's data is used anywhere. All accounts are created by the scripts
at run time and live only in the throwaway database.

### Isolation matrix — 13 accounts, two independent tenants per role

| Username | Role | Purpose |
|---|---|---|
| `expg_patient_a` / `expg_patient_b` | PATIENT | tenant A owns the clinical resources; B is the probing stranger |
| `expg_doctor_a` / `expg_doctor_b` | DOCTOR (auto-approved) | |
| `expg_pharmacist_a` / `expg_pharmacist_b` | PHARMACIST | each registers its own pharmacy and stock |
| `expg_lab_a` / `expg_lab_b` | LAB | each registers its own lab centre |
| `expg_hospital_a` / `expg_hospital_b` | HOSPITAL | both approved, so SOS routing can choose |
| `expg_chw_a` / `expg_chw_b` | CHW | |
| `expg_admin` | ADMIN | oversight baseline |

Password for every account: `strongpass123`. Emails are
`<username>@expg.gramcare.in`. (`.test` cannot be used — the email validator
rejects reserved TLDs.)

### Phase 2 — 7 accounts

`p2_patient_a`, `p2_patient_b`, `p2_doctor_a`, `p2_doctor_b`, `p2_pharm_b`,
`p2_hosp_a`, `p2_admin`, same password and email convention.

### PostgreSQL validation — 4 accounts

`pg_patient_a`, `pg_patient_b`, `pg_doctor_a`, `pg_doctor_b`.

### Canary strings

Two classes, and keeping them separate is what makes the results valid:

| Canary | Marks | Appearance in another tenant's response means |
|---|---|---|
| `CANARYALPHA` | **private clinical data** — wallet note content and allergies, prescription diagnosis and medicine name, SOS voice note and location text, lab test name, referral reason, family-member name | **a confirmed leak**, no interpretation needed |
| `DIRNAMEALPHA` / `DIRNAMEBRAVO` | **display names** of accounts and facilities — doctor, lab and pharmacy names | nothing; public directories are supposed to list these |

The first run used a single undifferentiated canary and produced **18 false
positives** from the doctor and lab directories. Splitting the classes removed
that error class at the root rather than allowlisting around it.

### Test-only bypasses, stated plainly

The scripts flip two things directly in the database, exactly as the project's
own `tests/conftest.py` does, because neither can be driven from a script:

- `User.is_verified = True` — real registration sends an email nobody can click
  in a test run.
- `DoctorProfile.verification_status = "APPROVED"` — a doctor otherwise sits
  PENDING behind a government reviewer.

Both are bypasses **in the harness**, not in the application. The gates
themselves are exercised by the project test suite.

---

## 6. Raw output

Committed under `results/`, one row per probe, so every number in the reports
can be recomputed:

| File | Rows | Contents |
|---|---|---|
| `isolation_matrix_sqlite_raw.csv` | 201 | axis, method, path, caller, expectation, observed status, canary flag, finding, response excerpt |
| `isolation_matrix_postgresql_raw.csv` | 201 | same |
| `isolation_matrix_sqlite_summary.json` | — | SHA, engine, db version, Python and SQLAlchemy versions, timestamps, per-axis counts, skipped paths |
| `isolation_matrix_postgresql_summary.json` | — | same |
| `phase2_sqlite_raw.csv` | 48 | part, label, expectation, status, verdict, note, excerpt |
| `phase2_postgresql_raw.csv` | 48 | same |
| `phase2_sqlite_summary.json`, `phase2_postgresql_summary.json` | — | counts plus the labels of every finding, inconclusive and skipped probe |
| `phase2_postgres_validation_raw.csv` | 36 | part, label, expectation, observation, verdict, note |
| `phase2_postgres_validation_summary.json` | — | PostgreSQL version, isolation level, concurrency level, batch size, counts |
| `../EXPERIMENT_G_ACCESS_MATRIX.csv` | 534 | every probe from every run and both engines, consolidated |
| `../EXPERIMENT_G_ENDPOINT_INVENTORY.csv` | 135 | every endpoint, its declared guard, role requirements, rate limit, whether probed, by which script, and outcome |

Each summary JSON records `started` and `finished` in UTC ISO-8601, so run
durations are recoverable from the artefacts rather than from this document.

---

## 7. Verdict discipline

Four verdicts, and the distinction between the last two is the point.

| Verdict | Meaning |
|---|---|
| `pass` | the endpoint behaved as the security model requires |
| `finding` | it did not |
| `inconclusive` | **a 5xx or a harness exception — explicitly NOT a pass.** The first version of the matrix only inspected HTTP 200 responses for a canary, so an endpoint that began returning 500 after a fix would have been silently recorded as clean. Both harnesses now count 5xx separately and the summaries list every instance by label. |
| `skipped` | the probe could not be seeded (no resource id available); listed by name, never folded into the pass count |

Observed across the final runs: **0 inconclusive, 0 skipped** on both engines.

Because a scoping change can also mask itself behind a correct-looking empty
result, two targeted scripts assert the **positive** case independently —
`verify_ehr_records_scoping.py` (the related doctor must still see the record,
the unrelated one must get `[]` and not an error, ADMIN must still see
everything, pagination must still work) and
`verify_sos_track_remediation.py` (full disclosure while active, redacted
inside the grace window, 404 past it, throttle fires above the threshold,
legitimate polling unaffected).

---

## 8. Known deviations from a production-parity run

Stated so the results are not read as more than they are.

1. **The project test suite runs on SQLite only.** `tests/conftest.py` sets
   `DATABASE_URL` to a temp SQLite file unconditionally, so `pytest` cannot be
   pointed at PostgreSQL without editing it. The 245-test result is therefore a
   SQLite result. PostgreSQL coverage comes from the three experiment scripts
   and from `tests/test_migrations.py`, which runs the real Alembic chain.
2. **`TestClient`, not a network server.** Probes go through ASGI in-process, so
   nothing here exercises TLS, the reverse proxy, CORS or any
   infrastructure-layer control.
3. **The rate limiter is in-process and per-worker.** Measured limits hold for a
   single worker. A multi-worker or multi-instance deployment will admit
   proportionally more requests per window unless the limiter is moved to shared
   storage. Recorded as future work.
4. **Synthetic data volumes are small.** The index findings (P6) are structural —
   whether an index exists — not performance measurements. No query timing is
   claimed anywhere in these reports.
5. **One run per probe.** These are deterministic authorisation outcomes, not
   measurements with variance, so repetition adds nothing. The concurrency
   checks (P2, P3) are the exception and do run repeated concurrent operations.
