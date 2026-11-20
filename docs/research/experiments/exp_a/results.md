# Experiment A — Results

**Executed:** 20 November 2026
**Code under test:** `505799a1ff53aff30f680d1d64eb7120921b499d`
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
management around it is not, and the uniqueness scope is wrong.*

---

## 2. Scenario results — 46 scenarios

| Verdict | Count |
|---|---|
| **PASSED** | **37** |
| **FAILED** | **6** |
| INCONCLUSIVE | **0** |
| NOT_APPLICABLE | 3 |
| Positive controls passed | **7 of 7** (A, B, C, D, E, F, G) |

Every group's control passed, so no result in this report is suppressed as
untrustworthy. No scenario produced an unexplained 5xx.

### The six failures

| # | Scenario | Measured outcome | Root cause (predicted in Phase 1) |
|---|---|---|---|
| **A3c** | client with 150 queued records drains the queue | 150 still queued after 5 attempts, **0 persisted**, HTTP 422 every time | A1 — `pushUnsynced` posts the whole queue in one request; the server caps the list at 100 |
| **F4** | 7 days offline (120 records) reconnects | 120 still queued, **0 persisted** | same as A3c; this is its real-world shape |
| **G4** | queue contains 1 record for a **deleted** family profile | HTTP 404, **0 of 9 valid records persisted** | A2 — the ownership guard raises inside the per-item loop before the single commit, discarding the batch |
| **G5** | patient B submits a `client_uuid` patient A already used | 1 row, owned by **A**; B told the record synced; **nothing stored for B** | P7 — `client_uuid` is unique table-wide, not per patient |
| **A4** | `record_date` of now, +10 years, −10 years | all three accepted exactly as sent | A7 — no bound, no sanity check |
| **E3** | server-side change after the client pulled | local copy still `'e3 content 0'` | A4 — `pullRemote` skips any `srv-<id>` already cached |

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

| | Metric | Result | 95% CI | Meaning |
|---|---|---|---|---|
| **M11** | **maximum drainable queue depth** | **100 records** | — | a sharp cliff, not a degradation |
| M11b | tested depths that deadlock | 4/7 = 0.5714 | 0.2505–0.8418 | depths 101, 120, 150, 300 |
| **M12** | **silent cross-tenant record-loss rate** | **30/30 = 1.0000** | **0.8865–1.0000** | deterministic, every attempt |

**M11, measured depth by depth:**

| Queue depth | Drained? | Persisted | Still queued |
|---|---|---|---|
| 50 | yes | 50 | 0 |
| 90 | yes | 90 | 0 |
| **100** | **yes** | **100** | **0** |
| **101** | **no** | **0** | **101** |
| 120 | no | 0 | 120 |
| 150 | no | 0 | 150 |
| 300 | no | 0 | 300 |

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

1. **The client is a reimplementation.** `ClientSim` mirrors
   `sync_service.dart` line by line — unchunked whole-queue push, acknowledgement
   on `synced ∪ duplicates`, no retry accounting, `pullRemote` skip-if-cached —
   but it is Python, not the shipped Dart. Divergence is possible. The server-side
   findings (F-A2, F-A3, F-A4) do not depend on it; **F-A1 does**, and should be
   confirmed on a device before publication.
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

## 7. Remediation status

**No application code was changed by this experiment.** The findings and their
fixes are recorded; applying them is a separate decision, because two of the
three touch things this brief told me to protect:

| Finding | Fix | Why it needs a decision |
|---|---|---|
| F-A1 | chunk `pushUnsynced` into ≤100-record slices | changes the Flutter client |
| F-A2 | return `rejected[]` and commit the valid items | changes the server's response contract, which the client reads |
| **F-A3** | composite unique on `(patient_id, client_uuid)` + `patient_id` in the pre-check | **a production migration that alters a unique constraint** |
| F-A4 | bound `record_date` against `created_at` | server-side only, low risk |
| F-A5 | update cached `srv-<id>` records on pull instead of skipping | changes the Flutter client |
| F-A6 | add `payload` to the Hive model and the push body | changes the Flutter client and the local schema |

F-A3 is the one I would do first: it is silent clinical data loss, measured at
100%, and the fix is well understood. It needs a migration plan because the
existing global unique index has to be dropped and replaced, and the production
table must be checked for cross-patient duplicates before the composite
constraint can be created.
