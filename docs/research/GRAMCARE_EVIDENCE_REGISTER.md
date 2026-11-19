# Evidence Register

Every quantitative or factual claim in the manuscript, what supports it, and
whether it survives checking. One row per claim. **This file is the gate: no
claim may appear in the revised manuscript unless its row here says VERIFIED, or
says PENDING against a named experiment that has since been run.**

**Compiled:** 19 November 2026 · repository at commit `bd2f48d`.

Status values: **VERIFIED** (checked against a primary source) · **STALE**
(was true, no longer is) · **OVERSTATED** (true in part, claimed too broadly) ·
**MISATTRIBUTED** (number real, source or meaning wrong) · **UNVERIFIED** (could
not confirm) · **NOT FOUND** (claimed source does not appear to exist) ·
**PENDING** (needs an experiment).

---

## A. Claims about the external world

| # | Claim | Where in paper | Cited as | Verification | Status |
|---|---|---|---|---|---|
| A1 | "rural doctor-to-patient ratio stands near 1:11,082" | Abstract; §I-A | [6] IJMR, no DOI | 1:11,082 is the **national** ratio of population per **government allopathic doctor** (National Health Profile). Not rural. Not all doctors. Ministry figures for all registered allopathic doctors: ~1:811–1:834. | **MISATTRIBUTED — CRITICAL.** Re-source to NHP and describe correctly, or replace with a genuine rural measure. |
| A2 | "close to 70% of specialist posts at rural CHCs remain vacant" | Abstract; §I-A | [5] NHSRC *Health Dynamics of India 2022–23* | Plausible and consistent with NHSRC reporting. Primary document not opened in this pass. | **UNVERIFIED** — open the NHSRC report, quote the table, cite page. This is the **stronger** of the two statistics; lead with it. |
| A3 | WHO benchmark of 1:1,000 | Abstract; §I-A | [9] WHO Global Health Workforce Statistics | Widely used; WHO's own current threshold framing has shifted over time. | **UNVERIFIED** — cite the specific WHO publication and year. |
| A4 | e-Sanjeevani and private apps are "built for an urban, high-literacy, always-connected user" | §I-B | *no citation* | Characterisation of named real platforms with nothing behind it. | **UNVERIFIED — must cite or soften.** |
| A5 | rural internet-penetration claims | §I context | [7] "India Telemedicine Market Size & Growth Report … industry market research" | A commercial market report supporting a factual claim. | **UNVERIFIED — not acceptable at IEEE.** Replace with TRAI or a peer-reviewed source. |

## B. Claims about the literature

| # | Claim | Where | Verification | Status |
|---|---|---|---|---|
| B1 | Ref [1] Ashista et al., offline-first EHR, PLOS Digital Health, "vol. 5, no. 2", 2026 | §II-A, refs | **Real.** Crossref: DOI `10.1371/journal.pdig.0001204`, PLOS Digital Health, 2026, first author Ashista. Volume/issue as printed do not match PLOS's article-number scheme; no DOI given. | **VERIFIED (work) / malformed (citation)** |
| B2 | Ref [2] mHealth field study, "ScienceDirect, 2025" | §II-B, refs | **Real but miscited.** Actual: *SSM – Health Systems*, 2025, DOI `10.1016/j.ssmhs.2025.100124`. **ScienceDirect is a platform, not a journal.** No authors, no volume, no DOI. | **MISATTRIBUTED — CRITICAL** |
| B3 | Ref [3] "Artificial Intelligence in Rural Healthcare Delivery: Bridging Gaps and Enhancing Equity through Innovation," arXiv preprint, 2025 | §II-C, refs | **No arXiv record. No Crossref record for that title.** Crossref returned only different papers on adjacent topics. | **NOT FOUND — CRITICAL. Produce the item or delete it and the claim it supports.** |
| B4 | Ref [4] SymptomAI, "arXiv preprint, 2026" | §II-C, refs | **Real, wrong repository.** Research Square preprint, DOI `10.21203/rs.3.rs-9684240/v1`. | **MISATTRIBUTED** |
| B5 | "No work reviewed here unifies [the three capabilities]" | §II-D | Literally true of three reviewed works; establishes nothing. | **UNVERIFIED as a gap claim** |
| B6 | "a gap that runs through the existing literature" | §XIII | Escalates B5 beyond its own evidence. | **OVERSTATED — CRITICAL** |
| B7 | *(absent)* multi-provider LLM failover is unaddressed | implied by contribution 4 | **Contradicted.** ContinuityBench (arXiv 2607.15899) is a published benchmark and systems study of stateful failover in multi-provider LLM routing. Commercial gateways already do cross-provider retry. | **Must be cited and positioned against.** |
| B8 | *(absent)* client-UUID idempotent sync is novel | implied by contribution 1 | **Contradicted.** Client-generated UUIDs (UUIDv7/ULID), per-write idempotency keys and upsert-on-key are established offline-first practice. | **Narrow the claim to the measurement.** |

## C. Claims about the system — verification counts

| # | Claim | Where | Verification | Status |
|---|---|---|---|---|
| C1 | "96 of 96 automated backend tests … pass" | Abstract; §VII; Table II; §X; §XIII | **Suite is now 245 tests.** `pytest --collect-only -q` → "245 tests collected"; full run → "245 passed, 663 s", 19 Nov 2026, commit `bd2f48d`. | **STALE — CRITICAL.** Understates by 2.5×. Re-report with the SHA. |
| C2 | "37 of 37 cross-module integration checks pass" | same five places | Traces to `docs/audits/INTEGRATION_VERIFICATION_REPORT.md`. **That report states the suite was 73 tests at the time** — a different checkpoint from the 96. | **STALE + internally inconsistent — CRITICAL.** The two numbers are from different dates and are presented as one event. |
| C3 | "on a live Docker stack" | §VII; §X | Not re-verified in this pass. | **UNVERIFIED** |
| C4 | "more than twenty domain modules" | Abstract; §IV-B; §X | `ls -d modules/*/` → **21**. | **VERIFIED** (and understated) |
| C5 | *(absent)* endpoint count | — | **144 routed endpoints.** | **VERIFIED — worth stating** |
| C6 | "Forty-five or more commits … since the previous review" | §VII | Not a research result. | **Delete** |

## D. Claims about the system — architecture and features

| # | Claim | Where | Verification | Status |
|---|---|---|---|---|
| D1 | "**Every write** made while offline … assigned a client-generated UUID … one idempotent batch" | §IV-D; contribution 1 | `client_uuid` exists on **`EHRRecord` only** (`models.py:406`). Flutter client queues **only** Health Wallet records to `/ehr/sync`. `Payment` has a separate `idempotency_key`. **No other write path is offline-queued or idempotent** — not appointments, prescriptions, SOS, lab bookings, preorders or vitals. | **OVERSTATED — CRITICAL.** Narrow to `EHRRecord`. |
| D2 | the dedupe is correct | §IV-D | `modules/ehr_sync/router.py:320–393`: unique index, pre-check, `IntegrityError` race handler, explicit `duplicates[]` in the response. | **VERIFIED — and better than the paper conveys** |
| D3 | provider chain Groq → Gemini → OpenAI → Anthropic, configurable priority, key pooling, cooldown on rate limit, set-aside on billing failure, circuit breaking | §IV-C; contribution 4 | `ai/manager.py`, `ai/keypool.py`, `ai/metrics.py` — all present. | **VERIFIED** |
| D4 | "If no provider can answer, the API reports why … rather than returning a fabricated result" | §IV-C | Present; `/health/ai` and `/health/integrations` report the reason. | **VERIFIED — a paper-worthy design stance, undersold** |
| D5 | user-supplied API key routed only to the provider matching its prefix | §IV-C | Present in the AI layer. | **VERIFIED** |
| D6 | "voice and Tamil-language input" as a contribution | Abstract; contribution 2 | `speech_to_text` plugin, `localeId: 'ta-IN'` (`triage_screen.dart:98`); `flutter_tts` same locale. **Recognition is performed by the device OS. GramCare contributes locale selection and interaction design, not ASR.** | **OVERSTATED as language technology.** Reframe as interaction design. |
| D7 | triage "degrades gracefully to an on-device fallback" | Abstract; contribution 2 | `frontend/.../lib/offlineTriage.ts` (199 lines) and `mobile/patient_app/lib/services/offline_triage_service.dart` both present. | **VERIFIED present / PENDING measured** (Experiment C, all-providers-down row) |
| D8 | "Gemini-backed" AI triage | Abstract; contribution 2 | Contradicts D3 — Gemini is one provider in a configurable chain. | **Internally inconsistent** |
| D9 | "FHIR-exportable Health Passport" | contribution 4; §VI-B | `core/fhir_export.py` + `/fhir-export`. The code's own docstring: "FHIR-R4-*shaped* … it is NOT a FHIR server, does not do SMART-on-FHIR auth, and does not push/sync to any external system." | **VERIFIED with caveat — carry the code's caveat into the paper verbatim** |
| D10 | SOS "escalates to the next hospital automatically if the first does not respond" | contribution 3 | Escalation logic present (`COALESCE(last_escalated_at, created_at) <= now − 180 s`). | **VERIFIED present / PENDING measured** |
| D11 | "SMS fallback to the family if no hospital responds in time" | §VI-A | **`MSG91_AUTH_KEY not set — SOS contact SMS is dropped`** (`/health/integrations`, production, 19 Nov 2026). **The fallback does not deliver.** | **STALE/BROKEN — must be reported as a measured gap, not buried in Limitations** |
| D12 | pay-before-book enforced by server-verified Razorpay | §V; §VI-A | Present; signature verified server-side; payments live. | **VERIFIED** |
| D13 | CI runs the suite against PostgreSQL 15, builds three portals and three APKs on every push/PR | §VII | `.github/workflows/main.yml`: `postgres:15`, 3 × `npm run build`, 3 × `flutter build apk --debug`. | **VERIFIED** |

## E. Claims about security and privacy

| # | Claim | Where | Verification | Status |
|---|---|---|---|---|
| E1 | role-based access control; bcrypt; JWT + server-tracked refresh sessions; AI endpoints rate-limited; no committed secrets | §IX | All present. | **VERIFIED as controls** |
| E2 | *(implied)* those controls achieve isolation | §IX | **Contradicted by a full audit of the same codebase, 19 Nov 2026**: `GET /sos/active` returned every active emergency system-wide (patient name, live GPS, voice recording) to any `HOSPITAL` account and any approved doctor; `PUT /sos/{id}/respond` let them accept alerts routed elsewhere; `GET /pharmacy/queue` returned every unfulfilled prescription to any pharmacist; `POST /triage/ocr` was unauthenticated. | **FALSIFIED as written — and this is the paper's best available result.** Fixed in `7c3f8c5`–`bd2f48d`. |
| E3 | the fixes hold | — | Live, 19 Nov 2026: hospital account sees **1** of its own alerts; unrelated doctor sees **0**; pharmacist sees **1** correctly scoped prescription; `/triage/ocr` → **401** without a token. Re-confirmed by the isolation matrix: axis 3 went from 7 findings to **0**. | **VERIFIED** |
| E8 | `GET /ehr/records` returned recent wallet records across **every** patient to any approved doctor, up to 200 per request, with no care relationship and no audit row | Experiment G, axis 3 | Confirmed by reading `modules/ehr_sync/router.py` — the docstring said "across all patients" and meant it. | **FALSIFIED as safe → FIXED**, scoped to the doctor's own patients |
| E9 | `POST /triage/analyze` accepted and persisted any `family_profile_id` without checking ownership | Experiment G, axis 4b | Confirmed: patient B got HTTP 200 writing a triage assessment onto patient A's family member. | **FIXED** — ownership check, now returns 403 |
| E10 | `GET /assist/patient-summary/{id}` returned a derived clinical summary of any patient to any approved doctor with **no audit row**, while `/ehr/patient/{id}` audited every read of the same underlying data | Experiment G, axis 4 | Confirmed by reading `modules/ai_assist/router.py`. | **FIXED** — same audit row added |
| E11 | authentication and role enforcement are correct | Experiment G, axes 1–2 | **48 of 48** endpoints rejected an unauthenticated caller; every wrong-role probe refused. | **VERIFIED** |
| E4 | "health-wallet records are held in an AES-encrypted local database" | §IX | `HiveAesCipher` via `services/encrypted_boxes.dart`. | **VERIFIED** |
| E5 | "reminder and profile caches on the device are not yet encrypted" | §IX; §XI | **Now encrypted** — same `encrypted_boxes.dart` path. | **STALE — resolved. Update with the commit, don't just delete the line.** |
| E6 | email verification required before login for all roles except patients | §IX | Present. | **VERIFIED** |
| E7 | authority accounts registerable only from an allow-listed address | §IX | `AuthorizedGovernmentEmail` model present. | **VERIFIED** |

## F. Claims about deployment and limitations

| # | Claim | Where | Verification | Status |
|---|---|---|---|---|
| F1 | free-tier hosting sleeps; first request "up to a minute" | §VIII; §XI | **22–63 s observed**, 19 Nov 2026. | **VERIFIED** |
| F2 | "unacceptable for an emergency-facing service" | §VIII; §XI | Correct, and well put. | **VERIFIED as judgement** |
| F3 | "Android builds are debug-signed only; no release keystore" | §XI | True for doctor and pharmacy (`signingConfig = signingConfigs.getByName("debug")`). **Patient app has a real release config** reading `key.properties`. | **PARTLY STALE** |
| F4 | "Email and SMS delivery … not been fully completed" | §XI | **Email is live** — Resend on verified domain `gramcare.me`, sender `no-reply@gramcare.me`. **SMS is not** — `MSG91_AUTH_KEY not set`. | **PARTLY STALE — split into two items** |
| F5 | drug-interaction screening checks "only a small curated list of pairs" | §XI | Present in `modules/cds`. Not quantified. | **VERIFIED as scoped / state the pair count** |
| F6 | mapping relies on public OSM tiles and Nominatim | §XI | Confirmed; also a dead Google `MAPS_API_KEY` placeholder remains in the patient app build, producing a misleading build warning. | **VERIFIED** |
| F7 | localisation covers English and Tamil only | §XI | True. Also: **the Health Wallet screen was entirely English in Tamil mode**, the whole triage result card was hardcoded English, and the speech-unavailable message is still English — all now fixed except where noted. | **VERIFIED, and the paper understates the gap it had** |
| F8 | not clinically validated; no regulatory or data-protection review; not for real patient care | §XI | Correct and essential. | **VERIFIED — keep verbatim** |

## G. Claims pending experiments

Everything in this block is currently unsupported by any measurement.

| # | Claim the paper needs | Experiment | Status |
|---|---|---|---|
| G1 | duplicate rate, data-loss rate, sync latency for offline records | A | **PENDING** — can start now, free |
| G2 | which pathway stages survive which network conditions | B, F | **PENDING** — can start now, free |
| G3 | failover success rate and recovery latency | C1–C2 | **PENDING** — can start now, free; report the tier |
| G4 | severity-band agreement across a failover; under/over-triage | C3 | **PENDING — AWAITING PAID AI ACCESS** |
| G5 | cost per successful request / workflow | C4 | **PENDING — AWAITING PAID AI ACCESS** |
| G6 | throughput, p99 latency, saturation, scaling | E | **PENDING — AWAITING PRODUCTION INFRASTRUCTURE** |
| G7 | complete 7-role isolation matrix | G | **DONE and PostgreSQL-validated, 19–20 Nov 2026. Classified B.** 534 probes, five runs, two engines (SQLite 3.50.4 / PostgreSQL 15.18), 135 endpoints enumerated. **7 confirmed cross-tenant exposures, all 7 resolved and re-verified on both engines.** 3 broad accesses remain, all deliberate and audited. Authentication and role enforcement already clean (48/48 reject anonymous; every wrong-role probe refused). **0 GET endpoints unprobed; 63 write endpoints unprobed — the stated coverage gap.** | **VERIFIED** |
| G7a | idempotent sync holds under genuine write concurrency | G, PostgreSQL P2 | 10 concurrent identical 25-record batches → exactly 25 rows, 25 distinct UUIDs, **duplicate rate 0.0000**, 0 server errors. SQLite serialises writers and could not have tested this. | **VERIFIED — first measured evidence for the project's headline sync claim** |
| G7b | database enforces the idempotency constraint, not just app code | G, PostgreSQL P1 | PostgreSQL rejects a duplicate `ehr_records.client_uuid` with `IntegrityError`; all 6 unique indexes present | **VERIFIED** |
| G7c | the break-glass audit trail works in both directions | G, PostgreSQL P4 | a permitted doctor read writes exactly 1 audit row; a **denied** read writes 0 | **VERIFIED** |
| G7d | capability tokens are unguessable | G, Part B1 | all three are `secrets.token_urlsafe(24)` = **192 bits**; 6/6 cross-namespace probes return 404; passport rotation invalidates the old token | **VERIFIED** |
| G7e | error bodies leak no internals | G, Part D | 6 probes (bad tokens, SQL-ish ids, negative and oversized ids) → no stack trace, no SQL, no driver name, no file path, no credential field name | **VERIFIED** |
| G7f | the payment webhook's HMAC guard holds | G, Part C | unsigned forgery 400, wrongly-signed forgery 400, order status unchanged in both, correct signature honoured, replay idempotent, fails closed when unconfigured | **VERIFIED** |
| G7g | the isolation remediations introduced a performance defect | G, PostgreSQL P6 | `emergency_sos.assigned_hospital_id` and `prescriptions.doctor_id` were unindexed, so the new ownership filters were sequential scans — one on the emergency desk. Fixed by migration `d1f7c3b9e205`, **applied and verified in production 20 Nov 2026** (`alembic_version = d1f7c3b9e205`, both indexes `indisvalid`). | **VERIFIED — found, fixed, deployed** |
| G8 | task completion by input modality (voice vs text, Tamil vs English) | D1 | **PENDING — REQUIRES ETHICS APPROVAL** |
| G9 | device ASR word error rate on Tamil medical vocabulary | D2 | **PENDING — REQUIRES ETHICS APPROVAL AND A LICENSED OR RECORDED DATASET** |
| G10 | clinical accuracy of the triage engine | — | **OUT OF SCOPE — requires clinician adjudication under ethics approval. Explicitly deferred; do not claim it.** |

---

## Summary

| Status | Count |
|---|---|
| VERIFIED | 21 |
| STALE (was true, now wrong) | 6 |
| OVERSTATED / internally inconsistent | 6 |
| MISATTRIBUTED | 3 |
| UNVERIFIED | 7 |
| **NOT FOUND** | **1** (reference [3]) |
| FALSIFIED as written | 1 (E2 — and it is the paper's best opportunity) |
| PENDING an experiment | 10 |

**The single most important line in this file is G10's neighbour — the empty
column.** Of the paper's claims, 21 survive checking, and essentially all of
those 21 are *descriptions of what was built*. Not one is a measurement of how
well it works. That is the whole gap between this manuscript and a publishable
paper.
