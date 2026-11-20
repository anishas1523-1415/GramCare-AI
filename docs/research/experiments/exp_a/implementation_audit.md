# Experiment A · Phase 1 — Implementation Audit

**Audited:** 20 November 2026
**Code state:** repository at `505799a` (`git rev-parse HEAD`)
**Method:** read the implementation. Nothing in this document is inferred from
documentation, comments or the research paper — every claim cites a file and a
line range, and anything I could not find in the code is recorded as absent.

**Headline:** the idempotency mechanism is real, correctly built and enforced by
a database constraint. Around it sit **six gaps**, two of which can deadlock a
patient's offline queue permanently. One is a hard bound that the client does not
respect.

---

## 1. Architecture as actually implemented

```
Flutter patient app                          FastAPI service
───────────────────────                      ────────────────────────────────
HealthRecord (Hive, typeId 0)
  clientUuid  = Uuid().v4()      ──┐
  synced      = false             │
  ↓                               │
'health_wallet' box               │
  AES-encrypted via               │
  HiveAesCipher(SecureStore key)  │
  ↓                               │
SyncService.pushUnsynced()        │
  collects ALL unsynced  ─────────┴──POST /ehr/sync──▶ per item:
                                                        resolve_owned_profile()
                                                        SELECT by client_uuid
                                                        ├─ exists → duplicates[]
                                                        └─ else   → db.add()
                                                      one db.commit()
                                                        └─ IntegrityError →
                                                           rollback, re-apply
                                                           one at a time
  ◀──{synced[], duplicates[]}──────────────────────────  EHRRecord
  mark synced = true for                                   client_uuid UNIQUE
  (synced ∪ duplicates)

SyncService.pullRemote()  ────────GET /ehr/patient/{id}──▶ scoped read
  skip if 'srv-<id>' present
```

### Files and functions

| Concern | Location |
|---|---|
| Local model | `mobile/patient_app/lib/models/health_record.dart:12-60` — `HiveType(typeId: 0)`, 10 fields |
| Encrypted box access | `mobile/patient_app/lib/services/encrypted_boxes.dart:13-25` — `EncryptedBoxes.open` / `openDynamic` |
| Hive encryption key | `mobile/patient_app/lib/services/secure_store.dart` — `getOrCreateHiveKey()`, platform secure store |
| Local write | `sync_service.dart:35-61` — `createRecord()` |
| Queue push | `sync_service.dart:64-103` — `pushUnsynced()` |
| Server pull | `sync_service.dart:108-136` — `pullRemote()` |
| Full cycle | `sync_service.dart:139-142` — `fullSync()` |
| Batch endpoint | `backend/python_service/modules/ehr_sync/router.py:343-412` — `sync_offline_records()` |
| Single endpoint | `modules/ehr_sync/router.py:280-341` — `create_record()` |
| Server model | `backend/python_service/models.py:384-409` — `EHRRecord`, `client_uuid` unique + indexed |
| Ownership guard | `backend/python_service/modules/family/router.py:23-45` — `resolve_owned_profile()` |
| Batch schema | `backend/python_service/schemas.py:375-380` — `EHRSyncRequest`, `EHRSyncResult` |
| Background trigger | `mobile/patient_app/lib/main.dart:19-40` (`callbackDispatcher`), `:82-91` (registration) |

### Sync triggers — the complete list

| Trigger | Location | Calls |
|---|---|---|
| App start | `main.dart:32` | `pushUnsynced()` |
| Dashboard load / pull-to-refresh | `dashboard_screen.dart:59,62` | `fullSync()` / `pushUnsynced()` |
| Health Wallet screen | `health_wallet_screen.dart:62,65` | `fullSync()` / `pushUnsynced()` |
| Record creation | `sync_service.dart:59` | `pushUnsynced()`, fire-and-forget |
| Workmanager periodic | `main.dart:85-91` | `pushUnsynced()`, **every 1 hour**, `NetworkType.connected` |

---

## 2. Guarantees that genuinely exist

### G1 · Client-generated identity, 122 bits

`Uuid().v4()` (`sync_service.dart:54`) assigns the identifier **on the device,
before the record ever reaches the server**. This is what makes a retry safe: the
identity does not depend on a server round-trip completing.

### G2 · Server-side deduplication, enforced by the database

Two layers:

1. **Pre-check** — `SELECT` by `client_uuid`; a hit is appended to
   `duplicates[]` and skipped (`router.py:362-369`).
2. **Constraint** — `EHRRecord.client_uuid` is `unique=True, index=True`
   (`models.py:406`). The pre-check is an optimisation; **the constraint is the
   guarantee.** Confirmed enforced on PostgreSQL in Experiment G (P1): the
   database itself rejects a duplicate with `IntegrityError`.

### G3 · Race handling that does not destroy the queue

The batch `commit()` is wrapped: on `IntegrityError` it rolls back and re-applies
every item individually, counting collisions as duplicates
(`router.py:376-399`). This matters because a patient's queue can hold days of
records — aborting the batch on one collision would strand all of them.

Experiment G measured this under genuine concurrency on PostgreSQL: ten
concurrent identical 25-record batches produced exactly 25 rows, duplicate rate
**0.0000**.

### G4 · Acknowledgement treats duplicates as success

`pushUnsynced` marks a record `synced = true` if its UUID appears in
**either** `synced[]` **or** `duplicates[]` (`sync_service.dart:86-95`). Without
this, an acknowledged-as-duplicate record would be retried forever. This is
correct and easy to get wrong.

### G5 · Per-item tenant ownership

`resolve_owned_profile()` runs for **every** item in the batch
(`router.py:361`), raising 403 if the `family_profile_id` belongs to another
account. `patient_id` is always taken from `current_user.id` and never from the
payload (`router.py:371`), so a client cannot write a record onto another
patient. Confirmed by Experiment G axis 4b.

### G6 · Encryption at rest, including the background path

Every box opens through `EncryptedBoxes`, and the background isolate opens the
wallet with the same cipher before syncing (`main.dart:25-29`). The comment in
`encrypted_boxes.dart:9-11` records why this wrapper exists: `Hive.openBox`
returns an already-open box regardless of cipher, so a background sync that
opened it first previously left the wallet unencrypted.

### G7 · Local read idempotency on the pull path

`pullRemote` marks server-origin records `srv-<id>` and skips any already
present (`sync_service.dart:116-117`), so repeated pulls do not duplicate
locally.

---

## 3. Gaps — what does not exist

Stated as absences, not as criticisms of the comments. Several of these are
things the research paper's §IV-D claims or implies.

### ✕ A1 · No batch chunking, against a hard server cap of 100 — **can deadlock the queue permanently**

`EHRSyncRequest.records` is `Field(..., max_length=100)` (`schemas.py:376`).

`pushUnsynced()` collects **every** unsynced record and posts them in **one**
request (`sync_service.dart:66-84`). There is no chunking, no slicing, no
pagination.

**Therefore: once a patient accumulates more than 100 unsynced records, every
sync attempt is rejected with 422 and the queue can never drain.** The client's
`catch` treats it as a deferral (`sync_service.dart:97-102`), so the records stay
queued and the next attempt fails identically. There is no path out of this state
short of reinstalling the app.

This is the single most consequential gap, and it is squarely in scope for a
system whose premise is extended offline operation in a village. **Predicted
failure — scenario A3.**

### ✕ A2 · One poisoned record blocks the whole batch — **second deadlock path**

`resolve_owned_profile()` raises `HTTPException` from inside the per-item loop
(`router.py:361`), **after** earlier items have been `db.add()`ed but before the
single `commit()` at line 375. An exception therefore aborts the request and
discards the entire batch.

If one queued record carries a `family_profile_id` that is no longer valid — a
family member deleted on another device while this one was offline — **every
record behind it in the queue is blocked indefinitely**, for the same reason as
A1: the client cannot distinguish this from a transient failure. **Predicted
failure — scenario G4.**

### ✕ A3 · No conflict resolution — by design, and the paper should say so

There is **no** update path for a wallet record. No `PUT /ehr/record/{id}`, no
version column, no vector clock, no last-writer-wins, no merge. `EHRRecord` has
no `updated_at`. The local model has no dirty flag beyond `synced`.

**Records are append-only, so conflicts are avoided rather than resolved.** That
is a legitimate and defensible design — immutable timestamped clinical events are
a recognised pattern, and it is why a plain unique key suffices where the
literature reaches for CRDTs — but it must be described accurately. The
manuscript must not claim conflict resolution, and the experiment cannot measure
"conflict-resolution correctness" on a system that has no conflicts to resolve.
Scenario group E is therefore reframed in Phase 2: it tests that concurrent
writes **cannot** conflict, and documents what the design gives up.

**What it gives up:** a correction to a record is a new record, so the wallet
accumulates both the wrong and the right entry with no link between them.

### ✕ A4 · Server-side changes never reach a client that already pulled

`pullRemote` does `if (existingUuids.contains(marker)) continue;`
(`sync_service.dart:117`). Once `srv-42` is cached locally, **no later change to
server record 42 is ever reflected** — not an edit, not a deletion. The local
copy is permanently stale.

In practice wallet records are not edited server-side, so the exposure today is
limited. It is recorded because the design has no mechanism to recover if that
changes. **Predicted failure — scenario E3.**

### ✕ A5 · No retry accounting and no reconnect trigger

- No retry counter, no backoff, no jitter, no dead-letter queue. A failure logs
  one line and leaves the records queued (`sync_service.dart:97-102`).
- **No connectivity listener.** `connectivity_plus` is not a dependency of the
  patient app, and there is no `onConnectivityChanged` subscription anywhere in
  `lib/`. Regaining signal does **not** trigger a sync.
- The reliable backstop is the Workmanager task at **1-hour** frequency with
  `NetworkType.connected` (`main.dart:85-91`). Everything else is a user action.

So "reconnect and retry" in the research plan is really "retry within the hour,
or when the patient next opens the app". That is a meaningful finding for a
system whose value proposition is connectivity tolerance, and the metric
"eventual consistency convergence time" must be interpreted against a 1-hour
scheduler rather than a reconnect event.

### ✕ A6 · `payload` is never sent from the offline queue

The server accepts `payload: Optional[Dict]` on both sync paths
(`schemas.py:349`, `router.py:357`). The Hive `HealthRecord` model **has no
payload field at all** (`health_record.dart:12-60`), and `pushUnsynced` does not
send one (`sync_service.dart:74-82`).

Structured data therefore cannot survive the offline path. A record created
offline carries only its human-readable `content`. The OCR flow's `image_url` and
parsed medicine list are reachable only through the online `POST /ehr/record`.
**This is a silent field-level data loss on the offline path**, and the client
cannot detect it because the server accepts the record happily without it.

### ✕ A7 · `record_date` is the unvalidated device clock

`record_date` is `r.timestamp.toIso8601String()` where `timestamp` is
`DateTime.now()` at creation (`sync_service.dart:49,81`). The server stores it
unexamined — no bound, no sanity check against `created_at`, no clock-skew
correction. A device with a wrong clock produces wrong clinical dates, and
`GET /ehr/patient/{id}` orders by `record_date desc`, so the wallet displays in
the wrong order. **Predicted failure — scenario A4.**

---

## 4. Record types: supported offline vs online-only

| Type | In `EHRRecordCreate` pattern | Reachable via offline queue? |
|---|---|---|
| `note` | yes | **yes** |
| `prescription` | yes | **yes** (patient-captured; doctor-issued ones come from `/ehr/issue_prescription` and arrive via pull) |
| `lab_report` | yes | **yes** |
| `triage_log` | yes | **yes** |
| `vaccination` | yes | **yes** |
| `scan` | yes | **yes, but without `payload`** — see A6 |

**Only `EHRRecord` is offline-capable at all.** Every other write in the system
is online-only and carries no client UUID: appointments, doctor-issued
prescriptions, SOS triggers, lab bookings, medicine pre-orders, IoT vitals,
referrals. `Payment` has a separate `idempotency_key` with a partial unique index
— a different mechanism, not part of this subsystem.

This bounds the experiment, and it bounds what the paper may claim. The correct
claim is *"Health Wallet records created offline synchronise idempotently"*, not
*"every write made while offline"*.

---

## 5. Transaction boundaries

| Path | Boundary |
|---|---|
| `POST /ehr/sync` happy path | **one** `commit()` for the whole batch (`router.py:375`) — all-or-nothing |
| `POST /ehr/sync` after `IntegrityError` | `rollback()`, then per-item `add` + commit (`router.py:376-399`) — partial success becomes possible |
| `POST /ehr/sync` on a 403 from the ownership guard | request aborts, **nothing commits** — see A2 |
| `POST /ehr/record` | `commit()`, `IntegrityError` → rollback → return existing; then a **second** `commit()` for the audit row (`router.py:320-341`) |
| Local write | `box.add()` — Hive is its own transaction; the record is durable before any network call |

Two things worth noting. First, the batch is atomic on the happy path but becomes
**per-item** after a collision, so the same endpoint has two different atomicity
semantics depending on whether a race occurred. The client handles both correctly
because it keys off the returned UUID lists rather than the HTTP status. Second,
`/ehr/record` commits the record and the audit row separately, so a crash between
them leaves a record with no audit entry — the record is not lost, which is the
right trade.

---

## 6. Interrupted upload recovery

What happens at each interruption point, read off the code:

| Interruption | Server | Client | Net effect |
|---|---|---|---|
| Before the request leaves | nothing | records stay `synced=false` | retried on next trigger ✔ |
| Mid-request, before commit | transaction aborts | `DioException` → stays queued | retried, no duplicate ✔ |
| **After commit, before the response is received** | **records persisted** | `DioException` → stays queued | **retried; the pre-check finds them and returns them in `duplicates[]`; client marks them synced.** This is the case the whole design exists for, and it is handled ✔ |
| Process killed after commit, before the client writes `synced=true` | records persisted | still `synced=false` | same as above ✔ |
| Device restart | — | Hive is durable; `main.dart:32` pushes on start | ✔ |

The acknowledgement design (G4) is what makes the third row work. There is no
server-side request log or idempotency-key table, and none is needed: the record
itself is the idempotency record.

---

## 7. Predicted failure scenarios for Phase 2

Each must be tested, not assumed. The first two are the ones I expect to fail.

| # | Scenario | Prediction | Basis |
|---|---|---|---|
| **P1** | queue exceeds 100 records | **FAIL — 422, permanent deadlock** | A1 |
| **P2** | one queued record references a deleted family profile | **FAIL — whole batch blocked indefinitely** | A2 |
| P3 | same batch sent twice | pass | G2, G3 |
| P4 | same UUID in two concurrent batches | pass | G2, G3 + Experiment G P2 |
| P5 | interruption after commit, before ack | pass | §6 |
| P6 | cross-tenant `family_profile_id` in a batch | 403, nothing written | G5 |
| P7 | **cross-tenant UUID reuse** — tenant B submits a UUID tenant A already used | **uncertain — the unique index is global, not per-patient.** Expect tenant B's record to be silently swallowed as a "duplicate" and reported as synced, losing B's record | `models.py:406`, `router.py:362-369` |
| P8 | `payload` on an offline record | **FAIL — field silently dropped** | A6 |
| P9 | future-dated / skewed `record_date` | **FAIL — accepted unvalidated** | A7 |
| P10 | server-side change after a local pull | **FAIL — never reflected** | A4 |

**P7 deserves emphasis.** `client_uuid` is unique across the whole table, not
per patient. UUIDv4 collisions are not a practical concern, but a *malicious or
buggy* client can submit a UUID it knows another patient used. The pre-check
matches on `client_uuid` alone, with no `patient_id` filter — so the submitting
patient would be told their record synced while nothing was stored for them. That
is a record-loss and a cross-tenant information-leak primitive (it reveals that a
given UUID exists), and it has not been tested. Phase 3 must test it.

---

## 8. What the manuscript may and may not claim

| Claim | Verdict |
|---|---|
| "Health Wallet records created offline synchronise idempotently, deduplicated by a unique client-generated UUID enforced by a database constraint" | **supported** |
| "Retries and double-sends cannot duplicate data" | **supported** — measured at duplicate rate 0.0000 under ten-way concurrency (Experiment G P2) |
| "Records survive interruption after a server commit but before acknowledgement" | **supported** by code reading; to be measured in Phase 3 |
| "Every write made while offline is assigned a client-generated UUID" (§IV-D) | **false** — `EHRRecord` only |
| "Conflict resolution" / "conflict-free sync" | **must not be claimed** — there is no update path and therefore no conflict resolution. Claim append-only immutability instead |
| "Two family members editing the same profile from different devices cannot create a duplicate" (§IV-D) | **supported but trivial** — profiles are not edited through this path at all |
| "Syncs when connectivity returns" | **must be qualified** — no reconnect listener; within one hour via Workmanager, or on user action |
| Anything about queue depth, latency or convergence time | **no basis yet** — Phase 3 must measure it |

---

## 9. Audit summary

| | Count |
|---|---|
| Guarantees verified present in code | **7** (G1–G7) |
| Gaps found | **7** (A1–A7) |
| Gaps that can permanently deadlock a patient's queue | **2** (A1, A2) |
| Silent data-loss paths | **2** (A6 field-level, P7 potential record-level) |
| Capabilities the paper claims that do not exist | **2** (universal offline UUIDs; conflict resolution) |
| Offline-capable models out of 27 | **1** |

The mechanism at the centre is sound. What surrounds it is incomplete in ways
that only show up in the conditions the system is explicitly designed for —
long offline periods and large queues — which is exactly what Phase 3 must
measure rather than assume.

**No code was changed during this audit.** Remediation decisions wait on Phase 3
evidence.
