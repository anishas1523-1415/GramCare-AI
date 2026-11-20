# Experiment A — Results

**Executed:** 20 November 2026 · **re-measured after remediation the same day**
**Code under test (before):** `505799a1ff53aff30f680d1d64eb7120921b499d`
**Code under test (after):** the six fixes in §7, same harnesses, same engine
**Engine:** PostgreSQL 15.18 (`postgres:15-alpine`), isolated container, `read committed`
**Python / SQLAlchemy:** 3.14.2 / 2.0.41
**Data:** synthetic only. No real patient data. No production database touched.

| Artefact | Path |
|---|---|
| Phase 1 audit | `implementation_audit.md` |
| Phase 2 protocol | `experiment_protocol.md` |
| Phase 3 harness | `research/experiments/exp_a/sync_reliability.py` |
| Phase 4 metrics harness | `research/experiments/exp_a/sync_metrics.py` |
| 46 scenario rows | `research/experiments/exp_a/results/exp_a_raw.csv` |
| 19 metric rows | `research/experiments/exp_a/results/exp_a_metrics.csv` |
| Run provenance | `results/exp_a_summary.json`, `results/exp_a_metrics_summary.json` |

---

## 1. Answer to the research question

> *How reliably can an offline-first, multi-tenant healthcare application
> preserve data integrity and achieve eventual consistency under intermittent
> connectivity, retries, concurrent submissions and application interruptions?*

**On the path it was designed for: perfectly, within the precision the sample
size supports.** Duplicate insertion rate **0/600**. Record loss on a clean
connection **0/600**. Recovery from an interrupted sync **30/30**. Ten-way
concurrent delivery of the same batch **30/30 correct**, with **0/300** server
errors. The central scenario — the server commits, the response is lost, the
client retries — behaves exactly as designed.

**Off that path it fails in three specific ways, two of which lose or strand
clinical data permanently.** The offline queue has a hard ceiling of **100
records**; above it, synchronisation can never complete. A single unresolvable
record blocks every record behind it. And a `client_uuid` collision across two
patients **destroys the second patient's record silently, at a measured rate of
30/30**.

The honest one-line answer: *the idempotency mechanism is sound; the queue
management around it was not, and the uniqueness scope was wrong.*

**All six findings have since been fixed and re-measured with the same
harnesses on the same engine.** The scenario suite goes from 37 passed / 6
failed to **44 passed / 0 failed**, the queue ceiling from 100 records to no
ceiling within the tested range (300), and the silent cross-tenant record-loss
rate from **30/30** to **0/30**. The before-and-after numbers are kept side by
side below rather than overwritten, because the before state is the result.

---

## 2. Scenario results — 46 scenarios

| Verdict | Before fixes | **After fixes** |
|---|---|---|
| PASSED | 37 | **44** |
| **FAILED** | **6** | **0** |
| INCONCLUSIVE | 0 | **0** |
| NOT_APPLICABLE | 3 | 2 |
| Positive controls passed | 7 of 7 | **7 of 7** |

The two remaining `NOT_APPLICABLE` are genuine capability absences, not gaps in
the experiment: **E1** (no update path exists, so there is no conflict to
resolve — by design) and **F5** (Hive durability needs a Flutter runtime). The
third, **A6b**, became testable once the Hive model gained a `payload` field and
now passes.

Every group's control passed, so no result in this report is suppressed as
untrustworthy. No scenario produced an unexplained 5xx.

### The six failures

| # | Scenario | Measured outcome, before | **After the fix** |
|---|---|---|---|
| **A3c** | client with 150 queued records drains the queue | 150 still queued after 5 attempts, **0 persisted**, HTTP 422 every time | **PASS** — drains in **1 attempt**, 150 persisted |
| **F4** | 7 days offline (120 records) reconnects | 120 still queued, **0 persisted** | **PASS** — 120 persisted, queue empty |
| **G4** | queue contains 1 record for a **deleted** family profile | HTTP 404, **0 of 9 valid records persisted** | **PASS** — HTTP 200, **9 of 9** valid persisted, the stale one reported in `rejected[]`, queue unblocked |
| **G5** | patient B submits a `client_uuid` patient A already used | 1 row, owned by **A**; B told the record synced; **nothing stored for B** | **PASS** — **2 rows**, one per patient, both contents intact |
| **A4** | `record_date` of now, +10 years, −10 years | all three accepted exactly as sent | **PASS** — future clamped to now, past preserved |
| **E3** | server-side change after the client pulled | local copy still `'e3 content 0'` | **PASS** — local copy reads `SERVER_SIDE_CORRECTION` |

A seventh scenario, **G2** (patient B submits a batch scoped to patient A's
family profile), **regressed during remediation and was caught by the same
harness.** The first version of the F-A2 fix turned every ownership failure into
a per-item rejection, which downgraded that authorization refusal from 403 to a
200 with a reason string — and would have let a client enumerate other
households' profile ids in bulk. The fix was narrowed so that a **404** (the
profile is gone) rejects one item while a **403** (it belongs to someone else)
still refuses the whole request. G2 is back to 403 with nothing persisted.

### The three NOT_APPLICABLE

Recorded rather than skipped, because each marks a capability that does not
exist:

- **E1 — conflict resolution.** `EHRRecord` has no update endpoint, no version
  column and no `updated_at`. Records are append-only, so there is no conflict
  to resolve. This is a defensible design, and the manuscript must describe it as
  append-only immutability, **not** as conflict resolution.
- **A6b — `payload` on the offline path.** The server accepts and stores
  `payload`; the Hive model has no such field and the client never sends one.
  Structured data created offline is silently lost at field level.
- **F5 — local durability.** Hive persistence and `HiveAesCipher` need a Flutter
  runtime and cannot be exercised from this harness.

---

## 3. Metrics — Phase 4

Every rate is numerator/denominator with a Wilson 95% interval. Every metric's
calculation is stated in `exp_a_metrics.csv`.

### What works

| | Metric | Result | 95% CI | n |
|---|---|---|---|---|
| M1 | synchronisation success rate | **30/30 = 1.0000** | 0.8865–1.0000 | 30 batches × 20 records |
| M2 | **duplicate insertion rate** | **0/600 = 0.0000** | 0.0000–0.0064 | each batch delivered 3× |
| M3 | record-loss rate (clean connection) | **0/600 = 0.0000** | 0.0000–0.0064 | 30 batches |
| M4 | data-integrity violation rate | **0/30 = 0.0000** | 0.0000–0.1135 | 30 batches |
| M5 | recovery success rate | **30/30 = 1.0000** | 0.8865–1.0000 | 30 injected commit failures |
| M6b | first-write-wins stability | **30/30 = 1.0000** | 0.8865–1.0000 | 30 |
| M10 | concurrent synchronisation correctness | **30/30 = 1.0000** | 0.8865–1.0000 | 30 runs × 10 concurrent |
| M10b | server errors under concurrency | **0/300 = 0.0000** | 0.0000–0.0126 | 300 requests |

The confidence intervals matter here. A duplicate rate of 0/600 bounds the true
rate below **0.64%**, not at zero. Thirty runs cannot demonstrate a rate lower
than that, and the report does not claim it.

### Timing

| | Metric | Median | p95 | p99 | n |
|---|---|---|---|---|---|
| M9 | batch completion time, 20 records | **80.3 ms** | 89.0 ms | 94.3 ms | 30 |
| M7 | convergence after one failure | **149.6 ms** | 177.9 ms | — | 30 |
| M8 | retries to convergence | mean **2.00**, max **2** | | | 30 |

**Three qualifications, all material:**

1. **In-process ASGI, no network.** These are server-side processing times. They
   are not field latencies and must never be presented as such.
2. **p99 at n=30 is underpowered** and is flagged as such in the CSV. It is
   reported for completeness only.
3. **M7 excludes the client's own scheduler, and that dominates reality.** The
   shipped app has no connectivity listener; its reliable retry is a
   **1-hour** Workmanager task. Real-world convergence after a failed sync is
   therefore bounded by up to an hour, or by the patient next opening the app —
   not by 150 ms. The research paper must state the scheduler, not this number.

### What breaks

| | Metric | Before | 95% CI | **After** | 95% CI |
|---|---|---|---|---|---|
| **M11** | maximum drainable queue depth | **100 records** | — | **300+ (no ceiling in range)** | — |
| M11b | tested depths that deadlock | 4/7 = 0.5714 | 0.2505–0.8418 | **0/7 = 0.0000** | 0.0000–0.3543 |
| **M12** | **silent cross-tenant record-loss rate** | **30/30 = 1.0000** | 0.8865–1.0000 | **0/30 = 0.0000** | 0.0000–0.1135 |

M12's after-interval is the honest limit of 30 trials: it bounds the true rate
below **11.4%**, not at zero. What makes the fix credible is not the interval but
the mechanism — uniqueness is now `(patient_id, client_uuid)` enforced by the
database, and both dedupe predicates filter on the caller — together with the
30/30 before-measurement of the behaviour it replaced.

**M11, measured depth by depth:**

| Queue depth | Drained, before? | Persisted | **Drained, after?** | **Persisted** |
|---|---|---|---|---|
| 50 | yes | 50 | yes | 50 |
| 90 | yes | 90 | yes | 90 |
| **100** | **yes** | **100** | yes | 100 |
| **101** | **no** | **0** | **yes** | **101** |
| 120 | no | 0 | **yes** | **120** |
| 150 | no | 0 | **yes** | **150** |
| 300 | no | 0 | **yes** | **300** |

The cliff is exactly at the server's `max_length=100`. At 101 records **nothing
persists at all** — it is not a partial sync, it is a total one, and it repeats
identically on every retry.

---

## 4. The three findings in detail

### F-A1 · The offline queue has a hard ceiling of 100 records — CRITICAL

**Measured:** depth 100 drains fully; depth 101 persists **0** records and stays
queued through 4 further attempts. Depths 120, 150 and 300 behave identically.

**Mechanism.** `schemas.EHRSyncRequest.records` is `Field(..., max_length=100)`.
`SyncService.pushUnsynced()` collects *every* unsynced record and posts them in
**one** request, with no chunking (`sync_service.dart:66-84`). Over 100 records
the request fails validation with 422, the client's `catch` treats it as a
deferral, and the next attempt sends the same oversized batch.

**Why it is critical rather than cosmetic.** The queue only grows that large
during exactly the conditions the product exists for: a long offline stretch in
a village. A patient who records daily vitals and notes for a week crosses 100
and the wallet then **never syncs again** — with no error surfaced to the user,
because the client logs one debug line. There is no recovery path short of
reinstalling the app, which discards the queue.

**Fix:** chunk the push into slices of ≤100 and treat each chunk's
acknowledgement independently. Three lines in `pushUnsynced`. The server cap is
correct and should stay.

### F-A2 · One unresolvable record blocks the entire queue — HIGH

**Measured:** a 10-record batch where one record references a deleted family
profile returned **404** and persisted **0 of the 9 valid records**.

**Mechanism.** `resolve_owned_profile()` raises from inside the per-item loop
(`ehr_sync/router.py:361`), before the single `commit()` at line 375, so the
whole transaction is discarded. The client cannot distinguish this from a
transient failure and retries the same batch forever.

**Why it matters.** The triggering condition is ordinary: a family member deleted
on a second device while this one was offline. The wallet then stops syncing
entirely, for the same reason as F-A1 and with the same invisibility.

**Fix:** collect per-item failures into a `rejected[]` list in the response
instead of raising, commit the valid items, and have the client stop retrying
records the server has explicitly rejected.

### F-A3 · Cross-tenant `client_uuid` collision silently destroys the second patient's record — CRITICAL

**Measured:** **30/30 trials, rate 1.0000, 95% CI 0.8865–1.0000.** In every
trial: one row exists, owned by patient A, containing A's content. Patient B's
submission is reported in the acknowledgement set, and **no row exists for B**.

**Mechanism.** `EHRRecord.client_uuid` is `unique=True` **across the whole
table**, not per patient (`models.py:406`). The dedupe pre-check filters on
`client_uuid` alone with **no `patient_id` predicate**
(`ehr_sync/router.py:362-369`). B's record matches A's row, is classified a
duplicate, and is skipped. B's client then marks it `synced = true`, because the
acknowledgement protocol treats `duplicates[]` as success — which is correct
behaviour for B's own duplicates and exactly wrong here.

**Why this is the most serious finding.** It is **silent clinical data loss with
no error path**: the patient's phone shows the record as synced, the server has
nothing, and nobody is told. UUIDv4 collision by chance is not the concern — 122
bits makes that negligible. The concern is that nothing *prevents* a buggy or
hostile client from submitting a UUID it did not generate, and the resulting
behaviour is destructive rather than refused. It is also a small information
oracle: a 200 with the UUID in `duplicates[]` reveals that some other patient has
used that identifier.

**Fix:** scope uniqueness to the patient. Replace the global unique index with a
composite unique on `(patient_id, client_uuid)` and add `patient_id` to the
pre-check predicate. Then A's and B's records coexist, and each patient's own
retries still deduplicate correctly.

**This fix requires a production migration that alters a unique constraint**, so
it is recorded here and not applied as part of this experiment.

### Lesser findings

| | Finding | Measured |
|---|---|---|
| F-A4 | `record_date` accepted unvalidated | +10 years and −10 years both stored verbatim. The wallet orders by `record_date desc`, so a skewed device clock reorders a patient's clinical history |
| F-A5 | server-side changes never reach a client that already pulled | local copy unchanged after a server-side edit; `pullRemote` skips any cached `srv-<id>` |
| F-A6 | `payload` silently dropped on the offline path | the Hive model has no payload field; the API accepts one |

---

## 5. What the manuscript may now claim

With measurements, not assertions.

| Claim | Status |
|---|---|
| "Health Wallet records created offline synchronise idempotently; duplicate insertion rate 0/600 (95% CI 0–0.0064) with each batch delivered three times" | **supported, measured** |
| "Retries after a lost acknowledgement cannot duplicate data; recovery succeeded in 30/30 injected-failure runs" | **supported, measured** |
| "Ten concurrent deliveries of the same batch yield exactly the submitted record count in 30/30 runs with 0/300 server errors" | **supported, measured** |
| "Every write made while offline is assigned a client-generated UUID" (§IV-D) | **false** — `EHRRecord` only |
| "Conflict-free / conflict-resolving sync" | **must not be claimed** — append-only, no update path; first-write-wins measured stable at 30/30 |
| "Syncs when connectivity returns" | **must be qualified** — no connectivity listener; retry is a 1-hour Workmanager task or a user action |
| Any latency figure as a field measurement | **must not** — these are in-process ASGI times |
| "Reliable under extended offline operation" | **contradicted** — hard ceiling at 100 queued records |
| Multi-tenant data integrity | **contradicted for UUID collisions** — 30/30 silent loss |

The paper is now in a position to report a genuine, quantified reliability
result **and** the boundary at which it stops holding, which is a stronger
contribution than the unqualified claim it currently makes.

---

## 6. Limitations

1. **The client is a reimplementation — except for F-A1, which was confirmed on
   real hardware.** `ClientSim` mirrors `sync_service.dart` closely but is
   Python, so divergence is possible in principle. The server-side findings
   (F-A2, F-A3, F-A4) do not depend on it. **F-A1 was the one that did, and it
   has since been verified on a device** — see §8. F-A5 and F-A6 are still
   reimplementation-only and are the remaining exposure.
2. **In-process ASGI.** No TLS, no proxy, no real network. Latency figures are
   server-side processing only.
3. **Fault injection is at the session boundary.** "Connection dies before
   commit" is simulated by making `Session.commit` raise once, which reproduces
   what the server observes but not the socket behaviour.
4. **n = 30 per rate metric.** Enough to bound a zero rate below ~0.6%; not
   enough for a stable p99, which is flagged in the CSV.
5. **Hive durability and encryption untested here** (F5), and the 1-hour
   Workmanager cadence was read from the code, not observed over an hour.
6. **Small data volumes.** No statement is made about behaviour at production
   table sizes.
7. **One engine, one isolation level** — PostgreSQL 15.18 at `read committed`.

---

## 7. Remediation — all six applied

Applied after the measurements above, then re-measured with the same harnesses
on the same engine.

| Finding | Fix | Where | Verified by |
|---|---|---|---|
| **F-A3** | uniqueness scoped to the patient: `UNIQUE (patient_id, client_uuid)` replaces the table-wide unique index, and **all four** dedupe predicates gained a `patient_id` filter | `models.py`, `modules/ehr_sync/router.py`, migration `e4a9d2c7b118` | G5 (2 rows, one per patient); M12 **30/30 → 0/30**; B1–B5 confirm each patient's own dedupe still works |
| **F-A1** | `pushUnsynced` slices the queue into `syncBatchLimit` (100) requests, acknowledging each slice independently | `mobile/patient_app/lib/services/sync_service.dart` | A3c (150 drains in 1 attempt), F4 (120 drains); M11 **100 → 300+** |
| **F-A2** | `POST /ehr/sync` returns `rejected[]` for records it will never accept; a **404** rejects that item, a **403** still refuses the request | `schemas.py`, `modules/ehr_sync/router.py`, client honours `rejected[]` without claiming synced | G4 (9 of 9 valid persist, stale one rejected); **G2 still 403** |
| **F-A4** | `record_date` clamped to now when it is more than 24 h ahead of the server clock; past dates preserved | `modules/ehr_sync/router.py` | A4 (future clamped, past preserved) |
| **F-A5** | `pullRemote` updates a cached `srv-<id>` record instead of skipping it | `sync_service.dart` | E3 (local copy reads the correction) |
| **F-A6** | `payload` added to the Hive model and the push body | `health_record.dart`, `health_record.g.dart`, `sync_service.dart` | A6b (payload stored via the offline queue) |

### Design decisions taken along the way

**F-A4 bounds only the future.** A patient legitimately records something that
happened days ago while offline, so there is no defensible lower bound on a
clinical history. A 24-hour forward tolerance covers ordinary clock drift
without letting a record claim to be from the future.

**F-A2 distinguishes 404 from 403**, and that distinction was not in the first
attempt. See the G2 regression note in §2: collapsing both into a per-item
rejection downgraded an authorization refusal to a 200 and would have handed a
client a bulk oracle for other households' profile ids.

**F-A2's `rejected[]` is not an acknowledgement.** A rejected record stops being
retried but is never marked `synced`, because it never reached the server.
Claiming otherwise would be the same class of lie as the F-A3 bug.

### Migration safety

`e4a9d2c7b118` alters a unique constraint on a live table, so it is written to
refuse rather than corrupt:

- It **counts cross-patient `client_uuid` duplicates first** and raises with the
  diagnostic query if any exist, instead of failing on a cryptic index error.
  Production was checked: **21 `ehr_records`, 19 with a UUID, 19 distinct, 0
  shared across patients.**
- It **adds the per-patient constraint before dropping the global index**, so
  the table is never without an idempotency guarantee.
- Every step inspects before acting, so a partial state is recoverable by
  re-running.
- `NULL` client_uuid rows — server-created records such as doctor-issued
  prescriptions — are unaffected: PostgreSQL treats NULLs as distinct in a
  unique constraint.
- `downgrade()` **refuses** if any `client_uuid` has since been used by more than
  one patient, because restoring the global index would mean deleting a
  patient's record and there is no safe automatic way to choose which.

Tested on two paths against PostgreSQL 15.18:

| Path | Result |
|---|---|
| fresh database, full chain | 27 migrations clean, head `e4a9d2c7b118`, `ix_ehr_records_client_uuid` non-unique + `uq_ehr_records_patient_client_uuid` unique |
| **upgrade from `d1f7c3b9e205`** (the production revision) with seeded data including NULL-uuid rows | clean; **all 4 rows preserved**; indexes correct |

`render.yaml` runs `alembic upgrade head` in the service start command, before
uvicorn, so the deploy applies it. That is also why it fails loudly on a real
data problem rather than half-applying.

### Regression

Full backend suite after all six fixes, and the scenario and metrics harnesses
re-run from clean databases. Results in §2 and §3.

---

## 8. On-device verification of F-A1

The queue-ceiling finding was the one result that depended on the Python
reimplementation of the client, so it was re-tested against the **real Dart
code on real hardware**: the real encrypted Hive box, the real `SyncService`,
the real Dio client and its interceptors.

| | |
|---|---|
| Device | Motorola Edge 70 (`ZD222W9GN6`), Android 17 (API 37), arm64 |
| Build | debug APK via `flutter test integration_test/` |
| Test | `mobile/patient_app/integration_test/offline_queue_test.dart` |
| Backend | local FastAPI on the development machine, reached from the handset through `adb reverse tcp:8010` |
| Database | isolated PostgreSQL 15 container, table truncated for a clean baseline |
| Data | 150 synthetic records, all synthetic accounts. **No production write.** |

### Result — all three tests passed

```
[exp-a] backlog=150  still_queued=0  marked_synced=150  elapsed_ms=1087
[exp-a] server-side rows for this run: 150
[exp-a] 101-record single request -> HTTP 422
All tests passed!
```

Independently confirmed by querying the database directly rather than trusting
the test's own assertion:

| Check | Value |
|---|---|
| rows persisted | **150** |
| distinct `client_uuid` | **150** |
| **duplicates** | **0** |
| distinct patients | 1 |
| records from this run | 150 of 150 |
| `record_date` span | 07:40:42 → 10:09:43 — the backdating survived, confirming F-A4 bounds only the future |

### What this establishes

- **A 150-record backlog drains completely on a real handset, in 1087 ms.**
  Before the fix the same queue produced HTTP 422 on every attempt with nothing
  persisted, forever.
- **The fix is the client's chunking, not a relaxed server cap.** The third test
  sends 101 records in a *single* request from the same device and still gets
  **422**. Since 150 records nonetheless persisted, the client must have issued
  more than one request — which is the chunking doing its job.
- **An HTTP 200 was not accepted as proof.** The count came back from the
  database.
- Re-pushing a drained queue is a no-op, so the acknowledgement bookkeeping
  holds on the device too.

### Two changes this required, both debug-only

Recorded because they touch shipped files:

- `ApiService.baseUrl` now reads `String.fromEnvironment('GRAMCARE_API_BASE')`
  with the production URL as its default, so a normal build is byte-identical in
  behaviour and only a `--dart-define` at compile time can point it elsewhere.
  This is what let the test drive a local backend instead of writing 150
  synthetic clinical records into production.
- `android/app/src/debug/AndroidManifest.xml` permits cleartext HTTP. It lives
  in `src/debug/`, so it is merged into debug APKs and **never** into a release
  one; a release build still refuses cleartext. Needed because Android blocks
  cleartext from API 28 onwards, loopback included.

### Honest notes from the run

- The first two attempts failed on my own test code, not the product: the
  verification step called `GET /ehr/records`, which is scoped to approved
  doctors and admins (Experiment G, finding G-6), so a patient token correctly
  got a 403; and the server-side count read a single 200-row page while an
  earlier run's records were still in the table. Both fixed — the count now
  pages through, and the table is truncated for a clean baseline.
- Two further attempts failed on transport, not on the code: an `adb reverse`
  tunnel goes stale across the install/uninstall cycle, and the host's LAN route
  timed out on sustained POSTs while small GETs succeeded. Re-establishing the
  tunnel immediately before the run gives a reproducible result; a 100-record
  POST issued from the handset over a fresh tunnel completes in **0.245 s**.
- **F-A5 and F-A6 have not been device-verified.** They are Dart changes still
  resting on the Python reimplementation, and the same integration-test harness
  is now in place to cover them.
