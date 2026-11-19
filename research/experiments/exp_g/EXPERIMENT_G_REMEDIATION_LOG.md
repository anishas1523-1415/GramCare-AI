# Experiment G — Remediation Log

Every code change Experiment G caused, in order, with the file touched, the
reason, the expected outcome, the test that proves it, and the risk of breaking
something else. No change outside the scope of a recorded finding was made.

**Scope discipline:** nothing in this log alters application functionality
unrelated to an isolation finding. One disclosure that *is* intended behaviour —
the voice recording on an active SOS tracking link — was deliberately **left
unchanged** and reported for author review instead.

---

## Round 1 — the leaks the preceding audit found

Committed as `7c3f8c5` (plus follow-ups through `bd2f48d`).

### R1.1 · `GET /sos/active` scoped to the assigned hospital

**File:** `backend/python_service/modules/emergency/router.py`
**Finding:** G-1
**Change:** added `_my_hospital_id()`, which resolves the caller's hospital from
`owner_user_id` or `emergency_desk_user_id` (both unique columns), and filtered
the query by `assigned_hospital_id` plus alerts the caller accepted. ADMIN
unscoped. Doctors see only unrouted alerts.
**Expected outcome:** a hospital sees its own alerts; an unrelated hospital or
doctor sees none.
**Test:** `isolation_matrix` axis 3 (both engines); `tests/test_phase6_emergency.py`
**Risk:** **real and accepted** — the doctor dashboard's emergency panel is now
empty unless an alert is unrouted. That is correct behaviour (a doctor has no
hospital link in the schema), but it changes what the doctor portal shows.
Mitigated by the fact that the emergency desk is the intended responder surface.
**Collateral:** required `or_` to be imported from `sqlalchemy`.

### R1.2 · `PUT /sos/{id}/respond` assignment gate

**File:** `modules/emergency/router.py`
**Finding:** G-2
**Change:** the caller must be the assigned hospital, an admin, or — for an
unrouted alert — any approved clinician. 403 otherwise. The gate runs **before**
the status check, so "not entitled" (403) is distinguishable from "already
handled" (400).
**Test:** `phase2` Part A; `tests/test_phase6_emergency.py`, updated to assert
both codes.
**Risk:** low. One existing test asserted 400 where 403 is now correct; the test
was corrected rather than the code loosened.

### R1.3 · `GET /pharmacy/queue` scoped to the pharmacy's own patients

**File:** `modules/pharmacy_inventory/router.py`
**Finding:** G-3
**Change:** filtered to patients with a `MedicinePreorder` at the caller's
pharmacy, via `.distinct().scalar_subquery()`.
**Test:** `isolation_matrix` axis 3; `tests/test_phase5_pharmacy.py`, rewritten
to assert the prescription is **absent** before a pre-order exists and present
after.
**Risk:** moderate and considered. A walk-in patient with no pre-order does not
appear in the queue. Dispensing was deliberately left open for exactly that
reason — see R1.4.

### R1.4 · `PUT /pharmacy/fulfill/{id}` — audit instead of a hard block

**File:** `modules/pharmacy_inventory/router.py`
**Finding:** G-5
**Change:** an earlier draft of this remediation returned 403 unless a pre-order
linked the patient to the pharmacy. **That was reverted**, because it breaks the
ordinary walk-in — a patient holding a prescription at whichever pharmacy is
open — which is the common case in a village. Replaced with an `AuditLog` row
recording the dispensing pharmacy, the patient and whether a pre-order link
existed.
**Expected outcome:** browsing is closed (R1.3); dispensing stays possible and
becomes attributable.
**Test:** `isolation_matrix` axis 4b records this as a known residual, by design.
**Residual risk:** documented and not eliminated. See the register's G-5 entry.

### R1.5 · `POST /triage/ocr` requires authentication

**File:** `modules/ai_triage/router.py`
**Finding:** G-4
**Change:** added `Depends(get_current_user)`; imported it alongside the
existing `get_current_user_optional`.
**Test:** `isolation_matrix` axis 1; confirmed 401 in production.
**Risk:** low. `/triage/analyze` stays open, so the guest symptom checker is
unaffected.

---

## Round 2 — what this experiment found

### R2.1 · `GET /ehr/records` scoped to the doctor's own patients

**File:** `modules/ehr_sync/router.py`
**Finding:** G-6 — **found by this experiment**
**Change:** filtered to patients with whom the calling doctor has an appointment
or a prescription, built as a `union` subquery. ADMIN unscoped.
**Expected outcome:** the doctor portal's patient directory shows the doctor's
own patients and nobody else's.
**Tests:** `isolation_matrix` axis 3 (0 findings, both engines);
`verify_ehr_records_scoping.py` for the positive case;
`phase2_postgres_validation` P5 for pagination and out-of-range rejection.
**Risk:** **real and accepted** — a doctor with no appointments or prescriptions
now sees an empty directory. The portal already renders a correct empty state
for this screen.
**Collateral:** required `select` to be imported from `sqlalchemy`.
**Follow-on defect it introduced:** the new filter selects on
`prescriptions.doctor_id`, which was unindexed. See R2.4.

### R2.2 · `POST /triage/analyze` family-profile ownership check

**File:** `modules/ai_triage/router.py`
**Finding:** G-9 — **found by this experiment**
**Change:** when `family_profile_id` is supplied by an authenticated caller,
verify `FamilyProfile.user_id == current_user.id`; 403 otherwise.
**Expected outcome:** a patient cannot attach a clinical assessment to another
household's family member.
**Tests:** `isolation_matrix` axis 4b (403, both engines);
`phase2_postgres_validation` P4 additionally confirms **no orphan `TriageLog`
row** is left behind.
**Risk:** low. The guest path is unaffected: the check only applies when a
profile id is supplied by an authenticated caller.

### R2.3 · `GET /assist/patient-summary/{id}` writes an audit row

**File:** `modules/ai_assist/router.py`
**Finding:** G-8 — **found by this experiment**
**Change:** added the same `AuditLog` row that `GET /ehr/patient/{id}` writes —
reader, patient, resource `PatientSummary`.
**Expected outcome:** the break-glass policy's mitigation now exists on the
derived-data path, not only on the raw path.
**Test:** `phase2_postgres_validation` P4.
**Risk:** minimal — one extra insert per summary read. Access breadth was
deliberately **not** narrowed; that is a policy decision for the authors.

### R2.4 · Indexes on the two columns the scoping filters select on

**Files:** `backend/python_service/models.py`,
`backend/python_service/alembic/versions/d1f7c3b9e205_index_isolation_scoping_columns.py`
**Finding:** G-12 — **found by this experiment's PostgreSQL run, and caused by
R1.1 and R2.1**
**Change:** `index=True` on `EmergencySOS.assigned_hospital_id` and
`Prescription.doctor_id`, plus migration `d1f7c3b9e205`. The migration is
index-only — no column added, nothing dropped, no data changed — and guards
against pre-existing index names, so it is safe to apply to a live database.
**Expected outcome:** the emergency-desk poll and the doctor directory use an
index instead of a sequential scan.
**Tests:** `phase2_postgres_validation` P6 (8 of 8 scoping columns indexed); the
full 26-migration chain run against a fresh PostgreSQL 15 database, after which
both indexes exist and `alembic_version` reads `d1f7c3b9e205`.
**Risk:** low. Two added indexes cost a little write throughput and disk.
**⚠ Deployment:** Alembic does **not** run automatically on deploy in this
project. This migration must be applied by hand to production. Until it is, both
queries remain sequential scans — correct, but progressively slower.

### R2.5 · `GET /sos/track/{token}` — post-resolution redaction, expiry, rate limit

**File:** `modules/emergency/router.py`
**Finding:** G-10 — **found by this experiment**
**Change:** three parts.
1. `SOS_TRACK_GRACE_AFTER_RESOLVE = 24 hours`. A resolved alert still resolves
   inside that window but with `location_lat`, `location_lng`, `location_text`,
   `voice_note` and `voice_audio_url` withheld, so a relative can see that it
   closed without the link remaining a permanent disclosure.
2. Past the window, 404.
3. Rate limit `sos_track`, 120 requests per 300 s.
**Expected outcome:** the link is fully informative while it matters, minimal
afterwards, and dead eventually.
**Tests:** `phase2` Part B5 (both engines) and
`verify_sos_track_remediation.py`, which asserts all three states plus that a
legitimate 15-second poll is never throttled.
**Risk:** considered. The tracking page polls every 15 s — 20 requests per 5
minutes — so the limit leaves roughly six times the needed headroom. The
redaction changes what a relative sees after resolution, which is the intended
effect.

### R2.6 · `GET /files/{token}` rate limit

**File:** `modules/files/router.py`
**Finding:** G-11 — **found by this experiment**
**Change:** rate limit `file_fetch`, 120 per 60 s; imported `rate_limit`.
**Expected outcome:** parity with `/passport/{token}`, which already had one.
**Test:** `phase2` Part B2 — first 429 at attempt 121, both engines.
**Risk:** low but worth noting — a single page may embed several of these (a
profile photo, a licence scan, an OCR source), hence 120 rather than something
tighter.

---

## Harness corrections — no application code involved

Recorded because several of them changed what the experiment *reported*, and a
reader is entitled to know the reported numbers moved for harness reasons rather
than code reasons.

| # | Problem | Effect on reported results | Fix |
|---|---|---|---|
| H1 | one undifferentiated canary could not tell a public directory listing from a leak | **18 false positives** across `/doctors` and `/lab/centers` | split into a clinical canary and a directory-name canary |
| H2 | six endpoints assumed public actually require authentication | 6 false "findings" in axis 1 | allowlist corrected; the real observation — that `/triage/analyze` is open to a guest while the lab catalogue is not — kept as a design note |
| H3 | the rate-limit probe sent 40 requests against limits of 120 | the new limits looked absent | probe raised to 140 attempts |
| H4 | the B2 probe exhausts each bucket, and later probes reused it | 2 false namespace-confusion findings on `/files` | `ratelimit.reset_for_tests()` before each probe group |
| H5 | the post-resolution probe asserted 404 | the redacted-200 remediation reported as a finding | assert redaction field-by-field, and 404 only past the grace window |
| H6 | axis 3 inspected only HTTP 200 responses | **a 5xx would have been recorded as clean** | 5xx counted as `inconclusive`, listed by label, never as a pass |
| H7 | the family-profile seed omitted the required `gender` | every family-scoped path unprobed | field added |
| H8 | the slot seed posted an object; the route takes a list | `DELETE /doctors/me/slots/{id}` unprobed | list payload |
| H9 | the lab status probe sent a JSON body; the route takes a query parameter | 422 recorded instead of reaching the authorisation check | query parameter |
| H10 | mock payment verify needs a signature derived from the order id | the booking seed failed, so `PUT /appointments/{id}` was unprobed | derive `mock_sig_{order_id}_ok`. The rejection of a bare constant is correct behaviour and is now itself a recorded pass |
| H11 | `passport_token` starts NULL | passport entropy and rotation unprobed | mint it via `POST /passport/me/regenerate-token` first |
| H12 | the three stock-write routes name the parameter `medicine_id`, not `item_id` | 3 paths unprobed | mapping added |
| H13 | the payment webhook showed as `UNGUARDED` because it has no JWT dependency | a cryptographically guarded endpoint looked unprotected | labelled `hmac_signature_verified`, and Part C now proves it by forging |
| H14 | coverage attribution by string matching under- and over-credited probes | the "probed" count moved between 61, 82 and 72 across rebuilds | replaced with an explicit, auditable coverage map naming the probe for each endpoint |

---

## Verification after all remediations

| Check | Result |
|---|---|
| Project test suite (SQLite) | **245 passed, 0 failed** (634 s) |
| Isolation matrix — SQLite | 201 probes, 3 findings (all deliberate), 0 inconclusive |
| Isolation matrix — PostgreSQL 15.18 | 201 probes, 3 findings (identical), 0 inconclusive |
| Phase 2 — SQLite | 48 probes, **0 findings**, 0 inconclusive, 0 skipped |
| Phase 2 — PostgreSQL 15.18 | 48 probes, **0 findings**, 0 inconclusive, 0 skipped |
| PostgreSQL-specific validation | 36 checks, **36 pass**, 0 findings |
| Alembic chain on a fresh PostgreSQL 15 database | 26 migrations applied, head `d1f7c3b9e205`, both indexes present |
| `verify_ehr_records_scoping.py` | 11 checks, all pass |
| `verify_sos_track_remediation.py` | 17 checks, all pass |

No regression was introduced by any remediation, and no pre-existing test
failure was found.
