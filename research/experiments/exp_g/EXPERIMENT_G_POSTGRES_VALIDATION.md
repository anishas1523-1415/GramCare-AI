# Experiment G — PostgreSQL Validation Report

A separate report, because PostgreSQL did two different jobs here: it confirmed
that the engine-agnostic results hold on the real database, and it found one
defect that SQLite structurally cannot surface.

**Executed:** 19–20 November 2026
**Engine:** PostgreSQL 15.18 (`postgres:15-alpine`), isolated Docker container,
synthetic data only
**Default transaction isolation:** `read committed`
**Scripts:** `isolation_matrix.py`, `phase2_tokens_and_gaps.py` (both
engine-agnostic, run with `EXPG_DATABASE_URL`) and
`phase2_postgres_validation.py` (PostgreSQL-only)
**Raw data:** `results/isolation_matrix_postgresql_raw.csv`,
`results/phase2_postgresql_raw.csv`,
`results/phase2_postgres_validation_raw.csv`

**Why version 15.** It matches what the project runs: the CI workflow uses a
`postgres:15` service container and the Compose stack uses `postgres:15-alpine`.
This is same-major-version validation, not an arbitrary choice.

---

## 1. The engine-agnostic results hold

Both HTTP-level harnesses were run against PostgreSQL from a freshly created
database, and both produced results **identical** to the SQLite runs.

| Harness | SQLite | PostgreSQL 15.18 | Identical? |
|---|---|---|---|
| Isolation matrix — total probes | 201 | 201 | yes |
| axis 1 unauthenticated | 48 probes, 0 findings | 48 probes, 0 findings | yes |
| axis 3 cross-tenant collection | 114 probes, 0 findings | 114 probes, 0 findings | yes |
| axis 4 cross-tenant object | 24 probes, 2 findings | 24 probes, 2 findings | yes |
| axis 4b curated writes | 15 probes, 1 finding | 15 probes, 1 finding | yes |
| Inconclusive (5xx) | 0 | 0 | yes |
| Phase 2 — total probes | 48 | 48 | yes |
| Phase 2 findings | 0 | 0 | yes |

The three findings that persist on both engines are the deliberate broad-access
policies (`/ehr/patient/{id}`, `/assist/patient-summary/{id}`,
`/pharmacy/fulfill/{id}`), each documented and audited in the vulnerability
register.

**Interpretation.** This is the expected outcome and it is worth stating plainly
rather than glossing: the isolation logic under test is application-level SQL
filtering built through SQLAlchemy, so it should not vary by backend. The value
of the run is that this is now **measured** rather than assumed — and SQLite
results are consequently no longer the only evidence behind any isolation claim.

---

## 2. What PostgreSQL found that SQLite could not: 36 checks, 2 findings

`phase2_postgres_validation.py` ran 36 checks. On the first run **34 passed and
2 failed.** Both failures were performance defects introduced by Experiment G's
own earlier remediations, and neither was detectable on SQLite.

### P1 — Database constraints: 7 of 7 pass

Every unique index the security model depends on exists in PostgreSQL:

| Table.column | Why it matters |
|---|---|
| `ehr_records.client_uuid` | the idempotent-sync guarantee |
| `users.passport_token` | capability token uniqueness |
| `users.username`, `users.email` | identity |
| `stored_files.token` | capability token uniqueness |
| `emergency_sos.public_token` | capability token uniqueness |

And beyond index presence, PostgreSQL was shown to **actually reject** a
duplicate `ehr_records.client_uuid` with an `IntegrityError`. The idempotency
guarantee is enforced by the database, not merely by application code — which is
what makes the race handling in §P2 meaningful.

### P2 — Concurrent idempotent sync: 3 of 3 pass

**This is the check SQLite cannot perform.** SQLite serialises writers, so
`/ehr/sync`'s `IntegrityError` race handler is never genuinely exercised there.

Ten threads posted the **same** 25-record batch, with the same client UUIDs,
concurrently:

| Measure | Expected | Observed |
|---|---|---|
| Server errors | 0 | **0** (all ten responses HTTP 200) |
| Rows written | exactly 25 | **25** |
| Distinct `client_uuid` values | 25 | **25** |
| **Duplicate rate** | 0 | **0.0000** |

The pre-check plus `IntegrityError` handler plus unique index behave correctly
under genuine write concurrency. This is also the first real measurement
supporting the project's idempotent-sync claim — previously that claim rested on
code reading alone.

### P3 — Concurrent cross-tenant reads under write load: 3 of 3 pass

While tenant A wrote continuously, eight workers issued 36 cross-tenant reads
across six endpoints (`/ehr/records`, `/sos/active`, `/pharmacy/queue`,
`/ehr/prescriptions/my`, `/appointments/my`, `/analytics/overview`) as tenant B.

| Measure | Observed |
|---|---|
| Canary leaks | **0** |
| Server errors | **0** |
| Writer-thread errors | **0** |

Scoping does not degrade under concurrency, and no partially committed row
became visible across a tenant boundary.

### P4 — Transaction behaviour on a denied request: 5 of 5 pass

| Check | Expected | Observed |
|---|---|---|
| Denied cross-tenant triage write | 403, no `TriageLog` row for that profile | 403, **0 rows** |
| Denied patient-to-patient wallet read | 403 | 403 |
| Audit rows written for the **denied** read | 0 | **0** — a denial is not a read |
| Audit rows for a **permitted** doctor read | ≥1 | **1** |
| Audit rows for the AI patient summary (G-8 fix) | ≥1 | **1** |

The last two matter because the break-glass policy on `/ehr/patient/{id}` and
`/assist/patient-summary/{id}` is only defensible if the trail exists. It now
does, on both paths, and a rejection leaves nothing behind.

### P5 — Pagination and filtering after remediation: 10 of 10 pass

| Check | Observed |
|---|---|
| Related doctor sees the patient's records | 200, canary present |
| Unrelated doctor sees none | 200, canary absent — **an empty list, not an error** |
| `skip=0 limit=1` | 200, 1 row |
| `skip=0 limit=50` | 200, 31 rows |
| `skip=0 limit=200` | 200, 31 rows |
| `skip=3 limit=7` | 200, 7 rows |
| `skip=10000 limit=5` | 200, 0 rows |
| `limit=0` | **422** |
| `limit=201` | **422** |
| `skip=-1` | **422** |

The "empty list, not an error" row is the important one: a scoping change can
mask itself behind a 500, and this confirms the remediated query returns a
correct empty result instead.

### P6 — Indexes on the scoping columns: 6 of 8 pass, then 8 of 8

**The two findings.** Experiment G's remediations added ownership filters to two
hot paths, and neither target column was indexed:

| Column | Filtered by | First run | Consequence |
|---|---|---|---|
| `emergency_sos.assigned_hospital_id` | `GET /sos/active`, on every emergency-desk poll (R1.1) | **no index** | sequential scan on the one endpoint that must never be slow |
| `prescriptions.doctor_id` | `GET /ehr/records`, the doctor directory (R2.1) | **no index** | sequential scan, growing with every prescription ever issued |

Six other scoping columns were already indexed: `ehr_records.patient_id`,
`prescriptions.patient_id`, `medicine_preorders.pharmacy_id`,
`medicine_preorders.patient_id`, `hospitals.owner_user_id`,
`pharmacies.owner_user_id`.

**Remediation:** `index=True` on both model columns plus Alembic migration
`d1f7c3b9e205`. Re-run: **36 of 36 pass, 0 findings.**

---

## 3. Migration chain on a fresh PostgreSQL database

The full chain was applied to a newly created database — not to one built with
`create_all` — so the migrations themselves were under test.

| | |
|---|---|
| Migrations applied | **26**, clean |
| Final `alembic_version` | `d1f7c3b9e205` |
| `ix_emergency_sos_assigned_hospital_id` | present |
| `ix_prescriptions_doctor_id` | present |

The new migration is index-only: it adds no column, drops nothing, changes no
data, and skips an index whose name already exists. It is therefore safe to
apply to a live database.

> **⚠ Production action required.** Alembic does **not** run automatically on
> deploy in this project. Migration `d1f7c3b9e205` must be applied by hand to
> the production database. Until it is, `GET /sos/active` and `GET /ehr/records`
> remain sequential scans in production — functionally correct, progressively
> slower with volume.

---

## 4. Why this run was worth doing

The honest summary is that PostgreSQL validated the isolation results — which
was the expected and somewhat unexciting outcome — and then found something the
SQLite runs could not have found:

1. **It made the engine-agnostic claim measured rather than assumed.** No
   isolation claim in this experiment now rests on SQLite alone.
2. **It exercised the idempotency race for the first time.** The project's
   headline offline-sync claim had been supported by code reading only; under
   ten concurrent writers of the same batch, the duplicate rate is a measured
   0.0000.
3. **It caught a defect the remediations introduced.** Two security fixes added
   unindexed filters to hot paths, one of them the emergency desk. That is a
   realistic failure mode for security work — correctness improved, performance
   quietly regressed — and only a real database surfaces it.
4. **It proved the audit trail behaves in both directions**, including that a
   denied read writes no audit row, which a weaker check would have missed.

---

## 5. Limitations of this run

1. **The project test suite still runs on SQLite only.** `tests/conftest.py`
   sets `DATABASE_URL` to a temp SQLite file unconditionally, so the 245-test
   result is a SQLite result. PostgreSQL coverage comes from the three
   experiment scripts and from `tests/test_migrations.py`, which runs the real
   Alembic chain. Making the suite engine-parameterised is recorded as future
   work.
2. **Small data volumes.** P6 checks whether an index *exists*; it does not
   measure query time. **No query timing or throughput figure is claimed
   anywhere in this report.** Measuring the actual cost of these scans belongs
   to Experiment E, which needs production-grade infrastructure.
3. **`read committed`, the default.** No test was run under `repeatable read`
   or `serializable`, so nothing is claimed about behaviour at higher isolation
   levels.
4. **Concurrency level 10, batch size 25.** Enough to exercise the race
   reliably, not a load test.
5. **In-process `TestClient`.** Nothing here exercises TLS, the reverse proxy,
   connection pooling under saturation, or any infrastructure-layer control.
6. **The rate limiter is in-process and per-worker.** The measured limits hold
   for one worker; a multi-instance deployment admits proportionally more per
   window until the limiter moves to shared storage.
