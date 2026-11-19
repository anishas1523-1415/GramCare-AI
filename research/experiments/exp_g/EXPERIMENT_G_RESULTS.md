# Experiment G — Cross-Role, Cross-Tenant Isolation Matrix

**Phase 1 executed:** 19 November 2026 · **Phase 2 executed:** 19–20 November 2026
**Engines:** SQLite 3.50.4 and PostgreSQL 15.18 · **Probes:** 534 across five runs
**Classification: B — complete with documented limitations** (§9)

| Deliverable | File |
|---|---|
| This report | `EXPERIMENT_G_RESULTS.md` |
| Every finding, its state, its proof | `EXPERIMENT_G_VULNERABILITY_REGISTER.md` |
| Every code change and its risk | `EXPERIMENT_G_REMEDIATION_LOG.md` |
| How to re-run it from clean | `EXPERIMENT_G_REPRODUCIBILITY.md` |
| PostgreSQL-specific findings | `EXPERIMENT_G_POSTGRES_VALIDATION.md` |
| 534 consolidated probe rows | `EXPERIMENT_G_ACCESS_MATRIX.csv` |
| 135 endpoints, guards, coverage | `EXPERIMENT_G_ENDPOINT_INVENTORY.csv` |
| Raw per-run output | `results/*.csv`, `results/*.json` |

---

## 1. Research question and result

**Is role-based access control, as conventionally implemented, sufficient to
prevent cross-tenant exposure in a multi-role shared-record health platform?**

**H-G1: it is not. Isolation additionally requires per-resource ownership
scoping, which RBAC does not express.**

**H-G1 is supported, and the shape of the evidence is the finding.**

A platform with bcrypt password hashing, JWT access tokens paired with
server-tracked refresh sessions, role dependencies on every route, and rate
limiting on its AI endpoints was probed on five axes across 135 endpoints.

- **Authentication was flawless.** 48 of 48 GET collection endpoints rejected an
  unauthenticated caller. Zero exceptions, both engines.
- **Role enforcement was flawless.** Every wrong-role probe was refused.
- **Tenant isolation was not.** Seven endpoints exposed one tenant's data or
  accepted one tenant's writes against another's resources — **and every one of
  them sat behind a correct role check.**

The endpoints that leaked were the ones whose job is to answer *"show me the
active work"*: active emergencies, the prescription queue, recent records.
Written naturally, that question returns **all** the active work, and the role
check passes because the caller genuinely does hold the role.

> **RBAC answers "may this role do this?" It cannot answer "does this row belong
> to this caller?" Those are different questions, and a shared-record design
> makes the second one load-bearing.**

GramCare's premise is one record across seven roles — which is its real benefit
to a patient who would otherwise repeat their story at every step, and
simultaneously the structural reason a single unscoped query exposes everyone.

---

## 2. Method

Two independent tenants for each of six roles, plus an admin: 13 synthetic
accounts. Tenant A creates clinical resources carrying a canary. Every endpoint
is then probed from tenant B's side.

| Axis | Probe | Expectation |
|---|---|---|
| 1 | every GET collection endpoint, no token | 401/403 unless public by design |
| 2 | wrong role | 403 |
| **3** | **same role, other tenant — is A's clinical canary in B's response?** | **absent** |
| 4 | same role, other tenant, A's resource id in the path | 403/404, never 200 |
| 4b | curated write probes (bodies required, hand-written) | 403/404 |
| B | capability tokens: entropy, brute-force cost, scope, namespace, revocation, expiry | per §5 |
| C | the payment webhook's HMAC guard | forgery rejected |
| D | error-body information leakage | no internals |
| P1–P6 | PostgreSQL: constraints, concurrency, transactions, pagination, indexes | per the PostgreSQL report |

**Axis 3 is the axis that matters.** Axes 1 and 2 are what conventional testing
already covers, and they were already clean. Axis 3 is where an endpoint passes
every authentication and role check and still hands tenant B tenant A's rows.

### Two canary classes, and why that is a methodological point

- `CANARYALPHA` marks **private clinical data** — wallet content and allergies,
  prescription diagnosis, SOS voice note and location, lab test name, referral
  reason. Any appearance in another tenant's response is a leak, with no
  interpretation needed.
- `DIRNAMEALPHA` marks **display names** of accounts and facilities, which
  public doctor, lab and pharmacy directories are supposed to expose.

The first run used a single undifferentiated canary and produced **18 false
positives** from directory listings. Splitting the classes removed that error
class at the root rather than allowlisting around it.

### Environment

Throwaway SQLite, and an isolated PostgreSQL 15 container. Every external
credential blanked before the app is imported, so no call reached Gemini,
OpenAI, Groq, Anthropic, Razorpay, Cloudinary, Google Maps, MSG91 or Resend. No
production data at any point. Full specification in the reproducibility record.

---

## 3. Coverage

| | Count |
|---|---|
| Endpoints enumerated (`/api/v1`, method × path) | **135** |
| Probed by Experiment G | **72** |
| Not probed | **63** — 47 POST, 14 PUT, 2 DELETE |
| **GET endpoints not probed** | **0** |
| Endpoints with no authorisation control of any kind | **0** |
| Total probes across five runs | **534** |

**Every read path was probed. The gap is writes**, which need valid request
bodies and are therefore hand-written; 15 of the most security-relevant are
covered by the curated probes and Part A. This is the main limitation behind the
classification in §9.

Three endpoints carry no JWT dependency, all legitimately — they carry their own
credential in the request itself:

| Endpoint | Control | Proven by |
|---|---|---|
| `POST /payments/webhook` | HMAC-SHA256 signature | Part C — forgery rejected both unsigned and wrongly-signed; correct signature honoured; replay idempotent; fails closed (503) when the secret is unconfigured |
| `POST /auth/refresh` | the refresh token itself | project test suite |
| `POST /auth/verify-email` | single-use token in the body | project test suite |

---

## 4. Findings: 7 confirmed, 7 resolved, 3 open by design

Full detail, including why each passed review, in the vulnerability register.

| | Endpoint | Caller | Exposed | State |
|---|---|---|---|---|
| **G-1** | `GET /sos/active` | any `HOSPITAL` account; any approved doctor | **every active emergency in the system** — patient name, live GPS, voice note, recording URL | **FIXED** |
| **G-2** | `PUT /sos/{id}/respond` | same | could accept another hospital's alert and receive the patient's details | **FIXED** |
| **G-3** | `GET /pharmacy/queue` | any pharmacist | **every unfulfilled prescription in the database** — diagnosis, doctor, medicines | **FIXED** |
| **G-4** | `POST /triage/ocr` | **unauthenticated** | open to the internet; AI quota and media-storage abuse | **FIXED** |
| **G-6** | `GET /ehr/records` | any approved doctor | **recent wallet records across every patient**, ≤200/request, no relationship, **no audit row** | **FIXED** ← found here |
| **G-9** | `POST /triage/analyze` | any authenticated patient | could **write** a clinical record onto another household's family profile | **FIXED** ← found here |
| **G-10** | `GET /sos/track/{token}` | anyone holding the SMSed link | patient name, GPS, voice note and recording, **indefinitely after resolution** | **FIXED** ← found here |
| **G-11** | `GET /files/{token}` | — | no rate limit (192-bit token, so no practical disclosure) | **FIXED** ← found here |
| **G-8** | `GET /assist/patient-summary/{id}` | any approved doctor | AI clinical summary of any patient **with no audit row** | **AUDITED** ← found here |
| **G-12** | two scoping columns | — | sequential scan on the emergency desk and the doctor directory | **FIXED** ← found here, **caused by G-1/G-6 remediation** |

### Open by design — deliberate, audited, documented

| | Behaviour | Why accepted |
|---|---|---|
| G-7 | `GET /ehr/patient/{id}` — any approved doctor reads any patient | break-glass. A rural patient may present at any facility; requiring a prior relationship blocks care. Every read writes an audit row with reader, patient and IP. |
| G-8 | `GET /assist/patient-summary/{id}` | same policy, now carrying the same trail |
| G-5 | `PUT /pharmacy/fulfill/{id}` — any pharmacist dispenses any prescription | the walk-in is the common case. Browsing was the exposure and is closed. Every dispense is audited. **Residual: id enumeration to flip the fulfilled flag — documented, not eliminated.** |

### Design observation — reported, deliberately unchanged

`GET /sos/track/{token}` discloses the voice note **and the audio recording** on
an active alert. That is intended — the schema lists the fields so a relative
hears what happened — and was **left alone**, because changing it is a product
decision, not a remediation. It is recorded because the same schema's docstring
calls the payload "deliberately narrow" and notes the token "may be forwarded to
anyone", and shipping the actual recording of a medical emergency on an
unauthenticated forwardable link sits awkwardly with both. **Flagged for author
review.**

---

## 5. Capability tokens: a different model, tested as one

Three endpoints are unauthenticated by necessity — the recipients have no
accounts. A relative gets an SOS tracking link by SMS; a government reviewer
opens a licence scan; a clinician scans a Health Passport QR.

| Property | `/sos/track` | `/passport` | `/files` |
|---|---|---|---|
| Generator | `token_urlsafe(24)` | `token_urlsafe(24)` | `token_urlsafe(24)` |
| Entropy | **192 bits** | **192 bits** | **192 bits** |
| Rate limited | **added** (120/300 s) | yes (20/60 s) | **added** (120/60 s) |
| Cross-namespace resolution | none (6/6 probes 404) | none | none |
| Rotatable | no | **yes — and rotation invalidates the old token** | no |
| Expiry | **added** — redacted after resolution, 404 past 24 h | none | none |

**Assessment.** 192 bits is unguessable; brute force is not the threat, and the
missing rate limits were never a practical confidentiality break. The real defect
was **lifetime**: a link SMSed during an emergency kept serving the patient's
name, exact GPS and the recording forever. That is now redacted after resolution
and dead after 24 hours, with the status still visible in between so a relative
can see it closed.

`/passport` is the exemplar of the three — rate-limited, rotatable, and rotation
genuinely kills the old link. `/files` and `/sos/track` still lack a rotation
path; recorded as future work.

---

## 6. Error handling and information leakage

Six probes — bad tokens, a SQL-ish path segment, a negative id, an oversized id —
produced **no** stack trace, no SQL, no driver name, no file path and no
credential field name. All clean, both engines.

One positive worth naming: an oversized patient id returns `200 []` rather than
404, so the endpoint does not disclose whether a patient id exists.

---

## 7. PostgreSQL validation

Full report in `EXPERIMENT_G_POSTGRES_VALIDATION.md`. In brief:

- **Both HTTP harnesses produced identical results on both engines** — 201 and
  48 probes, same findings, 0 inconclusive. No isolation claim now rests on
  SQLite alone.
- **36 PostgreSQL-specific checks, 2 findings, both performance and both caused
  by this experiment's own remediations.** `emergency_sos.assigned_hospital_id`
  and `prescriptions.doctor_id` were unindexed, so the new ownership filters were
  sequential scans — one of them on the emergency desk. Fixed by migration
  `d1f7c3b9e205`; re-run gives **36/36**.
- **The idempotency race was exercised for the first time.** SQLite serialises
  writers; under ten concurrent identical 25-record batches on PostgreSQL the
  result was exactly 25 rows, 25 distinct UUIDs, **duplicate rate 0.0000**, zero
  server errors. This is the first measured support for the project's headline
  offline-sync claim, which previously rested on code reading.
- **The audit trail behaves in both directions:** a permitted read writes exactly
  one row; a **denied** read writes none.
- **26 migrations apply cleanly** to a fresh PostgreSQL 15 database, head
  `d1f7c3b9e205`, both indexes present.

---

## 8. Regression verification

| Check | Result |
|---|---|
| **Project test suite** | **245 passed, 0 failed** (634 s, SQLite) |
| Pre-existing failures | **none** |
| Regressions introduced by remediation | **none** |
| Isolation matrix — SQLite | 201 probes, 3 findings (all deliberate), 0 inconclusive, 0 skipped |
| Isolation matrix — PostgreSQL | 201 probes, 3 findings (identical), 0 inconclusive, 0 skipped |
| Phase 2 — SQLite | 48 probes, **0 findings**, 0 inconclusive, 0 skipped |
| Phase 2 — PostgreSQL | 48 probes, **0 findings**, 0 inconclusive, 0 skipped |
| PostgreSQL validation | 36 checks, **36 pass** |
| `verify_ehr_records_scoping.py` | 11 checks, all pass |
| `verify_sos_track_remediation.py` | 17 checks, all pass |

Three existing tests were **corrected, not loosened**, because they asserted the
pre-remediation behaviour: `test_phase6_emergency.py` now distinguishes 403 (not
entitled) from 400 (already handled), and `test_phase5_pharmacy.py` now asserts
the queue scope rather than working around it.

### A 5xx is never a pass

The first version of the matrix inspected only HTTP 200 responses for a canary,
so **an endpoint that began returning 500 after a fix would have been recorded as
clean.** Both harnesses now classify 5xx and harness exceptions as
`inconclusive`, count them separately, and list every instance by label. Final
runs: **0 inconclusive on both engines.**

Because a scoping change can equally mask itself behind a correct-looking empty
result, two scripts assert the **positive** case independently — the related
doctor must still see the record and the unrelated one must get `[]` rather than
an error; the tracking link must disclose fully while active, redact after
resolution, 404 past the window, throttle above the threshold, and never
throttle a legitimate 15-second poll.

---

## 9. Classification

### **B — Complete with documented limitations.**

**Why not C (incomplete).** Every objective in the Phase 2 brief was met. All
nine previously unprobed path-parameter endpoints are now either probed or
explained as a distinct security model and probed as such. PostgreSQL validation
is done and found a real defect. The regression run completed: 245/245, no
pre-existing failures. All seven confirmed findings are resolved and re-verified
on both engines. The three remaining broad accesses are shown to be deliberate
and are now consistently audited. Legitimate access is independently confirmed
intact. 5xx responses are no longer counted as passes. Error bodies leak nothing.

**Why not A (complete and independently reproducible).** Two honest reasons:

1. **63 of 135 endpoints — all of them writes — were not probed.** Every read
   path was, and 15 of the most security-relevant writes are covered by curated
   probes, but a complete write matrix needs valid payloads for every POST and
   PUT. Until that exists, the experiment cannot claim to have probed the whole
   surface.
2. **Nothing has been reproduced by an independent party.** The harness,
   remediations and verification were all produced in the same effort. The
   artefacts make independent reproduction possible — committed scripts, 534 raw
   probe rows, per-run SHA, engine, version and timestamp records, explicit
   coverage declarations — but "independently reproducible" and "independently
   reproduced" are different claims, and only the first is supported.

### Limitations, stated once and plainly

| | Limitation |
|---|---|
| 1 | 63 write endpoints unprobed (47 POST, 14 PUT, 2 DELETE) |
| 2 | the project test suite is SQLite-only — `conftest.py` sets `DATABASE_URL` unconditionally. PostgreSQL coverage comes from the experiment scripts and `test_migrations.py` |
| 3 | in-process `TestClient` — nothing exercises TLS, the reverse proxy, CORS, or connection pooling under saturation |
| 4 | the rate limiter is in-process and per-worker; measured limits hold for one worker, and a multi-instance deployment admits proportionally more per window |
| 5 | **no query timing or throughput is claimed anywhere.** P6 checks index existence, not cost |
| 6 | one run per probe — correct for deterministic authorisation outcomes, and the concurrency checks are the exception and do repeat |
| 7 | the harness flips `is_verified` and doctor approval directly, exactly as the project's own conftest does; those gates are covered by the test suite, not by this experiment |
| 8 | G-5's residual (prescription-id enumeration to flip the fulfilled flag) is **documented, not eliminated** |
| 9 | migration `d1f7c3b9e205` is **not yet applied to production** — Alembic does not run on deploy here |

### To reach A

1. Automate the write matrix: generate a valid minimal payload per POST/PUT from
   the Pydantic request models, then probe all 63.
2. Parameterise the project test suite over both engines.
3. Add a rotation and revocation path for the `/files` and `/sos/track` tokens.
4. Move the rate limiter to shared storage and re-measure.
5. Apply `d1f7c3b9e205` to production and confirm both indexes.
6. Have someone outside this effort re-run the scripts and compare.

---

## 10. What this gives the paper

This is the first experiment in the plan to produce a result, and it is the
strongest material the project has, for three reasons.

1. **It is a finding, not a feature.** Not *"we implemented role-based access
   control"* — an assertion — but *"we built a cross-tenant isolation matrix, it
   found seven exposures in a system that already had RBAC, bcrypt, tracked JWT
   sessions and rate limiting, four of them handing one tenant another tenant's
   clinical data, and one of the fixes introduced a sequential scan on the
   emergency desk."*
2. **It generalises.** The conclusion — that RBAC cannot express row ownership,
   and that shared-record designs make that distinction load-bearing — applies to
   any multi-role health platform. The method is reproducible by other builders
   against their own systems, which is the part a reader can use.
3. **It is IEEE TTS's subject exactly.** A finding about how health software
   exposes patients, with a method, a fix, a measured before-and-after on two
   database engines, and an honest account of the three accesses that remain
   deliberately broad and what audits them.

**One more thing the paper should say, because it is the most interesting
sentence in this report:** the two most severe findings were in the endpoints
that answer *"show me the active work."* Emergency queues and prescription
queues are, by their nature, written as "everything currently open" — and that
is precisely the query shape that a role check cannot constrain. That is a
reusable warning, not an anecdote about one codebase.
