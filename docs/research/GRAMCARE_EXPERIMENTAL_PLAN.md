# Reproducible Experimental Plan

**Compiled:** 19 November 2026, against the repository at commit `bd2f48d`.

**Nothing in this document has been executed.** Every results table is a template
with empty cells. No number in this plan is a measurement, and none may be copied
into the manuscript until a real run fills it in. Where a measurement already
exists from ordinary engineering work, it is listed in Section 9 under what is
already in hand, with its provenance.

**The production-grade requirement is honoured as follows.** The plan is written
for appropriately provisioned paid infrastructure, and that configuration is
specified in Section 8. Free-tier constraints have not been used to shape the
experimental design. Where paid access is not yet authorised, the experiment is
marked **PENDING — AWAITING INFRASTRUCTURE** and its scripts are specified so it
can run the moment access exists. **Free-tier measurements will not be
substituted for production measurements, and no result from the current free-tier
deployment will be described as a production result.**

---

## 0. Classification of every experiment

| | Experiment | Can run now, free | Needs paid infra | Needs humans / ethics | Blocking on |
|---|---|---|---|---|---|
| A | Offline synchronisation | **Yes** | no | no | fault-injection harness (build it) |
| B | Network resilience | **Yes** | partly | no | network emulation (`tc`/Toxiproxy) |
| C | AI provider failover | **Partly** | **yes, for the provider comparison** | no | paid AI keys for the latency/cost arm |
| D | Tamil voice and language | **No** | no | **yes — human speakers, consent** | ethics approval; dataset licensing |
| E | API and system performance | **No** | **yes** | no | production-equivalent host |
| F | End-to-end workflow | **Yes** | partly | no | depends on A, B |
| G | Security, privacy, isolation | **Yes** | no | no | **EXECUTED + PostgreSQL-validated, 19–20 Nov 2026 — `research/experiments/exp_g/EXPERIMENT_G_RESULTS.md`. Classified B: complete with documented limitations.** |

**Run order: G → A → B → F → C → E → D.** G is free, needs nothing, and the
work is half done already. D is last because it is the only one gated on an
ethics committee.

---

## Experiment A — Offline synchronisation

**Objective.** Quantify the correctness and cost of client-UUID-keyed idempotent
synchronisation for family-scoped clinical records under controlled network
faults.

**Hypotheses.**
- H-A1: duplicate record rate is 0 across all fault conditions, including
  interrupted sync, repeated retry, and concurrent edits of the same family
  profile from two devices.
- H-A2: data-loss rate is 0 — every record created offline appears exactly once
  server-side after reconnection.
- H-A3: sync latency grows linearly, not super-linearly, in queue depth.

**Honest scope, and state it in the paper.** This covers `EHRRecord` only. It is
the only model carrying `client_uuid` (`models.py:406`). Appointments,
prescriptions, SOS triggers, lab bookings and vitals are **not** idempotent and
**not** offline-queued. Do not generalise the result.

**Setup.** `POST /ehr/sync` and `POST /ehr/record` against a PostgreSQL 15
instance. Driven by a harness that speaks the API directly rather than through
the Flutter client, so queue depth and interruption points are controllable.
Record the server commit SHA and the schema's Alembic revision with every run.

**Independent variables.**
| Variable | Levels |
|---|---|
| Queue depth | 1, 10, 50, 200, 1000 records |
| Interruption point | none; 25%; 50%; 75% of the batch transmitted |
| Retry count | 1, 2, 5 identical re-sends of the same batch |
| Concurrency | 1 device; 2 devices same family profile; 2 devices same `client_uuid` |
| Payload size | minimal; typical (prescription with 3 medicines); large (OCR scan payload) |

**Dependent variables.** sync success rate; **duplicate record rate** (primary);
data-loss rate; end-to-end sync latency (p50/p95/p99); server-reported
`duplicates[]` count; retries to convergence; HTTP error distribution.

**Procedure.**
1. Truncate `ehr_records` for the test patient. Record the row count.
2. Generate N records with client-side UUIDv4, persisted to a local fixture file
   so the same batch is replayable byte-for-byte.
3. POST the batch, aborting the connection at the configured fraction.
4. Re-send the identical batch R times.
5. Query the server for all records for that patient.
6. Assert: distinct `client_uuid` count == N; total row count == N; the union of
   `synced[]` and `duplicates[]` across all responses == N.
7. 30 repetitions per cell. Randomise cell order.

**Analysis.** Duplicate and loss rates are proportions — report exact counts, and
Wilson 95% confidence intervals rather than a bare 0%. Latency: report the full
distribution, not just the mean; Kruskal–Wallis across queue depths, since
latency will not be normal.

**Results template**

| Queue depth | Interrupt | Retries | Concurrency | n | Sync success | **Duplicates** | Loss | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | none | 1 | 1 dev | 30 | | | | | | |
| 200 | 50% | 5 | 2 dev same profile | 30 | | | | | | |
| 1000 | 75% | 5 | 2 dev same UUID | 30 | | | | | | |

*(full grid: 5 × 4 × 3 × 3 × 3 = 540 cells — pilot a reduced factorial first and
use it to drop variables that do not move the outcome)*

**Reproducibility.** Harness committed under `research/experiments/exp_a/`;
fixture batches committed; server SHA + Alembic revision recorded per run; raw
per-trial output as CSV, not just summaries.

**Interpretation guidance.** A duplicate rate of 0 is the expected result and is
**not** interesting on its own — the unique index guarantees it. What is
publishable is (a) the confidence interval, (b) the behaviour at the race
boundary that the `IntegrityError` handler covers, and (c) latency as a function
of queue depth, because that is what determines whether a health worker who was
offline for a week can actually sync in a clinic visit. **Lead with the latency
result, not the zero.**

---

## Experiment B — Network resilience

**Objective.** Measure which parts of the care pathway survive which network
conditions, and how long recovery takes.

**Hypotheses.**
- H-B1: Health Wallet read and offline record creation remain available at 100%
  packet loss.
- H-B2: triage falls back to the on-device estimator rather than failing, under
  every degraded condition.
- H-B3: time-to-consistency after restoration is bounded by the sync interval
  plus one batch latency.

**Setup.** Linux `tc`/`netem` for loss, latency and bandwidth shaping, or
Toxiproxy between client and API for connection-level faults. Conditions applied
at the client, not the server, so the server stays a fixed reference.

**Conditions.**
| Condition | Bandwidth | RTT | Loss |
|---|---|---|---|
| Stable broadband | 50 Mbps | 20 ms | 0% |
| Rural 3G | 1 Mbps | 150 ms | 1% |
| Congested 2G | 128 kbps | 400 ms | 3% |
| High latency | 10 Mbps | 1200 ms | 0% |
| Lossy | 10 Mbps | 100 ms | 15% |
| Intermittent | 1 Mbps | 200 ms | on 20 s / off 20 s |
| Disconnected | — | — | 100% |
| Restoration | 1 Mbps after 100% for 10 min | 200 ms | 0% |

**Measures.** request success rate; API latency p50/p95/p99 per condition;
**recovery time** (restoration → server consistency); which features remain
usable; data consistency after recovery.

**Results template**

| Condition | Req. success | p50 | p95 | p99 | Wallet read | Offline write | Triage | Booking | SOS | Recovery (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| Stable broadband | | | | | | | | | | — |
| Rural 3G | | | | | | | | | | — |
| Congested 2G | | | | | | | | | | — |
| Intermittent | | | | | | | | | | |
| Disconnected | | | | | | | | | | — |
| Restoration | | | | | | | | | | |

**This table is the paper's societal argument in quantitative form.** The rows
where a feature stops working are the rows that say who gets excluded.

**A finding already visible without running it.** SMS is not configured in
production (`/health/integrations`: `MSG91_AUTH_KEY not set — SOS contact SMS is
dropped`). So under *any* condition, the SOS family notification does not
deliver. That belongs in the results as a measured gap, not hidden in Limitations.

---

## Experiment C — AI provider failover

**Objective.** Measure failover reliability, recovery latency, and — the novel
part — whether triage severity banding survives a provider change.

**Hypotheses.**
- H-C1: failover success rate is ≥99% while at least one provider is reachable.
- H-C2: added latency from a failover is bounded and attributable to the failed
  provider's timeout, not to chain traversal.
- H-C3: **severity banding agreement across a failover boundary is high but not
  perfect**, and disagreement is asymmetric (over-triage more common than
  under-triage). H-C3 is the publishable claim.

**Setup.** `AIManager` with the chain Groq → Gemini → OpenAI → Anthropic → mock
(`ai/manager.py`, `ai/keypool.py`, `ai/metrics.py`). Fault injection by invalid
key, forced 429, forced timeout, and a model-retired error. **Record the exact
model version string for every provider on every run** — model updates silently
invalidate comparisons.

**Consider reusing ContinuityBench's harness** (arXiv 2607.15899), which
open-sources controlled failover injection at configurable turn indices. Using
and citing it is better than rebuilding it, and it strengthens the paper.

**Arms.**
| Arm | Needs paid keys? | Status |
|---|---|---|
| C1 failover correctness (does the chain traverse, cool down, set aside) | **No** | **Can run now** |
| C2 recovery latency | no (free-tier latency is still latency) | **Can run now, report the tier** |
| C3 severity-band agreement across failover | **Yes** — free-tier rate limits make a fair cross-provider comparison impossible | **PENDING — AWAITING INFRASTRUCTURE** |
| C4 cost per successful request / workflow | **Yes** — needs real billing data | **PENDING — AWAITING INFRASTRUCTURE** |

**Measures.** failover success rate; recovery latency per hop; per-provider
response time at matched prompt and model version; failed-request percentage;
circuit-breaker state transitions; cooldown correctness; **severity-band
agreement (Cohen's κ), under-triage rate, over-triage rate**; tokens and cost per
successful request.

**Results template**

| Fault injected | n | Failover success | Hops | Added latency p50/p95 (ms) | Final provider | Band agreement κ | Under-triage | Over-triage |
|---|---|---|---|---|---|---|---|---|
| Primary invalid key | | | | | | | | |
| Primary 429 | | | | | | | | |
| Primary timeout | | | | | | | | |
| Model retired | | | | | | | | |
| **All providers down → on-device fallback** | | | | | | | | |

**Hard constraints.**
- **Do not imply the fallback is clinically equivalent.** The claim is internal
  consistency of the system's own output across a failover, nothing more.
- The all-providers-down row is the most important one and the one the paper
  currently asserts without evidence ("degrades gracefully").
- The existing honest-failure behaviour — the API reports quota exhaustion,
  billing failure, missing model or no key rather than fabricating a result — is
  itself a measurable property. Verify it holds under every injected fault.

---

## Experiment D — Tamil voice and language

**Status: PENDING — REQUIRES HUMAN PARTICIPANTS AND ETHICS APPROVAL. Do not
start.**

**Reframe first.** GramCare contains **no ASR of its own**. Tamil recognition is
the device's, via the `speech_to_text` plugin with `localeId: 'ta-IN'`
(`triage_screen.dart:98`). A word-error-rate study would measure Google's or
Apple's recogniser and publish it as a GramCare result, which would be wrong.

**The publishable question is therefore not accuracy but access:** does
voice-first Tamil input let a low-literacy user complete a triage task they
cannot complete by typing, and what happens when the recogniser is unavailable?

**Two arms.**

*D1 — Task completion by input modality.* Within-subject, each participant
completes matched triage tasks by Tamil voice, Tamil text and English text.
Measures: task completion rate, time to completion, abandonment, assistance
events, self-reported difficulty. **Requires ethics approval and informed
consent. No patient data — scripted scenarios only.**

*D2 — Device ASR characterisation, reported as such.* Medical-vocabulary
recognition on a fixed Tamil phrase list across 3–5 Android devices and two noise
levels. Metrics: WER, CER, medical-term recall. **Must be labelled in the paper
as a characterisation of the platform recogniser, not of GramCare.**

**Dataset.** No suitable licensed Tamil medical speech corpus has been
identified. Check Mozilla Common Voice Tamil and IIT-Madras Tamil resources for
licence compatibility; if none is usable, D2 needs a small purpose-recorded set,
which puts it under the same ethics approval as D1.

**Already-known finding that needs no approval.** The app handles recogniser
absence with `'Speech recognition unavailable on this device.'` — and that string
is hardcoded English, in a Tamil-first app. The failure path for the flagship
accessibility feature is not localised. Report it.

**Prohibitions.** No clinical language-accuracy claim without a reference dataset
and qualified evaluation. No participant recruitment before written approval. No
real patient speech, ever.

---

## Experiment E — API and system performance

**Status: PENDING — AWAITING INFRASTRUCTURE.**

Free-tier Render instances that spin down after idle and cold-start in 22–63 s
cannot produce a meaningful throughput or p99 figure, and reporting their numbers
as production performance would be dishonest. The plan is specified; execution
waits on the configuration in Section 8 and on your approval to spend.

**Objective.** Establish throughput, latency distribution and saturation
behaviour on production-equivalent infrastructure.

**Tooling.** k6 or Locust, driven from a separate host so the load generator is
not competing with the service. Scenarios committed under
`research/experiments/exp_e/`.

**Scenarios.** read-heavy (wallet, prescriptions, doctor list); write-heavy
(record sync, booking); AI-heavy (triage); mixed realistic; spike (10× for 60 s);
soak (1 hour at 60% of saturation).

**Load levels.** 10, 50, 100, 250, 500, 1000 concurrent virtual users.

**Measures.** RPS at saturation; p50/p95/p99 latency per endpoint class; DB query
latency and connection-pool saturation; CPU and memory; error rate by class;
recovery time after a spike; horizontal scaling behaviour at 1, 2, 4 instances.

**Results template**

| Scenario | VUs | RPS | p50 | p95 | p99 | Error % | CPU % | Mem MB | DB p95 | Pool used |
|---|---|---|---|---|---|---|---|---|---|---|
| Read-heavy | 100 | | | | | | | | | |
| Write-heavy | 100 | | | | | | | | | |
| AI-heavy | 50 | | | | | | | | | |
| Spike 10× | → 1000 | | | | | | | | | |
| Soak 1 h | 60% sat. | | | | | | | | | |

**Every row must record the instance type, instance count, DB tier and region.**
A latency number without its hardware is not a result.

---

## Experiment F — End-to-end workflow

**Objective.** Measure stage-by-stage completion and latency for the full
pathway, under the network conditions from Experiment B.

**Pathway stages.** symptom capture → AI triage → (critical: SOS escalation) →
doctor booking → payment → video consultation → e-prescription → pharmacy
fulfilment → lab booking → referral.

**Setup.** Synthetic accounts only, clearly marked as such. The seeded demo
accounts already exist. **All patient data fictional. No real clinical record, no
real payment, no real SMS to a real number.** Razorpay in test mode with test
keys and the provider's published test card numbers only.

**Measures per stage.** completion rate; stage latency; failure mode when it
fails; whether the failure is *explained to the user* (this last one is a real
finding — before 19 Nov 2026 seven screens failed silently).

**Results template**

| Stage | Broadband | Rural 3G | Congested 2G | Intermittent | Disconnected | Median latency | Failure is explained? |
|---|---|---|---|---|---|---|---|
| Symptom capture | | | | | | | |
| AI triage | | | | | | | |
| SOS escalation | | | | | | | |
| Booking + payment | | | | | | | |
| Video consultation | | | | | | | |
| E-prescription | | | | | | | |
| Pharmacy fulfilment | | | | | | | |

**Known constraints to report rather than work around.** The signalling server is
on a free tier with a ~50 s cold start, so video consultation latency on the
current deployment is not a production figure. SMS is unconfigured, so the SOS
family notification stage will measure as failing.

**Label clearly.** This is a **simulated** workflow on synthetic accounts. It is
not a clinical deployment and must never be described as one.

---

## Experiment G — Security, privacy and multi-tenant isolation

**Status: EXECUTED AND CLOSED, 19–20 November 2026. Classified B — complete
with documented limitations.**

534 probes across five runs on two database engines (SQLite 3.50.4 and
PostgreSQL 15.18), over 135 enumerated endpoints. **Seven confirmed cross-tenant
exposures, all seven resolved and re-verified on both engines.** Three broad
accesses remain, all deliberate policy and all now audited. Authentication and
role enforcement were already flawless — 48 of 48 endpoints reject an anonymous
caller, every wrong-role probe refused — and every confirmed finding sat *behind*
a correct role check.

Five findings were new to this experiment: `GET /ehr/records` (every patient's
wallet to any doctor, unaudited), `POST /triage/analyze` (a clinical record
writable onto another household's family profile), `GET /sos/track/{token}` (the
SMSed emergency link served patient name, GPS and the audio recording
indefinitely after resolution), `GET /files/{token}` (no rate limit), and
`GET /assist/patient-summary/{id}` (AI clinical summary of any patient with no
audit row). A sixth, **G-12, was introduced by this experiment's own
remediations**: the new ownership filters select on two unindexed columns, so the
emergency-desk poll became a sequential scan. Only the PostgreSQL run could have
found that. All fixed; migration `d1f7c3b9e205` adds the indexes and **still
needs applying to production by hand.**

Also measured for the first time: the idempotent-sync race under ten concurrent
identical batches on PostgreSQL — exactly 25 rows, **duplicate rate 0.0000** —
which is the first real evidence for the project's headline offline-sync claim
(Experiment A can now build on it rather than start from nothing).

Project test suite after all remediations: **245 passed, 0 failed.** No
regressions, no pre-existing failures.

Remaining limitation: **63 of 135 endpoints — all writes — are unprobed.** Every
read path was probed. Full detail in
`research/experiments/exp_g/EXPERIMENT_G_RESULTS.md` §9.

**Objective.** Build a complete cross-role isolation matrix for a seven-role
shared-record health platform, and report what it finds.

**Hypothesis.** H-G1: role-based access control, as conventionally implemented,
is insufficient to prevent cross-tenant exposure in a multi-role health platform;
isolation requires per-resource ownership scoping that RBAC alone does not
express.

**H-G1 is already supported by evidence in hand**, which is why this experiment
is both the cheapest and the strongest.

**Method.** For every one of the 144 routed endpoints, and for each of the seven
roles (PATIENT, DOCTOR, PHARMACIST, LAB, HOSPITAL, CHW, ADMIN), plus an
unauthenticated caller, attempt access to a resource belonging to a *different*
tenant of the same role and record the outcome. Expected: 403 or 404. Any 200 is
a finding.

**Dimensions.** authentication bypass; role escalation; **cross-tenant resource
access (the main axis)**; session and refresh-token handling; JWT validation
(expiry, signature, algorithm confusion); object-level authorisation (IDOR by
sequential id); encryption at rest (DB, device Hive boxes); encryption in transit;
sensitive-field exposure in responses; audit-log completeness; device-level
protection (`allowBackup`, `dataExtractionRules`).

**Findings already established — 19 November 2026, commits `7c3f8c5`–`bd2f48d`**

| # | Endpoint | Finding | Exposed | Fix | Verified |
|---|---|---|---|---|---|
| G-1 | `GET /sos/active` | returned every active emergency system-wide to any `HOSPITAL` account and any approved doctor | patient name, live GPS, voice recording | scoped to `assigned_hospital_id`; unrouted alerts to the doctor pool | **Live: hospital sees 1 of its own; unrelated doctor sees 0** |
| G-2 | `PUT /sos/{id}/respond` | any such account could accept an alert routed elsewhere, pulling the patient's details | as G-1 | assignment gate, 403 otherwise | test asserts 403 |
| G-3 | `GET /pharmacy/queue` | returned every unfulfilled prescription in the database to any pharmacist | diagnosis, prescribing doctor, medicine list | scoped to patients with a pre-order at that pharmacy | **Live: 1 prescription, correctly scoped** |
| G-4 | `POST /triage/ocr` | unauthenticated; open to the internet | AI quota and media storage abuse | authentication required | **Live: HTTP 401** |
| G-5 | `PUT /pharmacy/fulfill/{id}` | any pharmacist could mark any prescription dispensed | service denial, record tampering | audit row naming the dispensing pharmacy | residual risk documented, not eliminated |

**Observation worth the paper's space.** All five existed in a system that
already had bcrypt hashing, JWT with server-tracked refresh sessions, role-based
dependencies on every route, and rate limiting on AI endpoints. **RBAC was
present and correct; it simply does not express "this row belongs to that
tenant."** That is the finding, and it generalises beyond GramCare.

**Results template for the full matrix**

| Endpoint | Role | Own resource | Other tenant's resource | Unauthenticated | Expected | Actual | Finding? |
|---|---|---|---|---|---|---|---|
| `GET /sos/active` | HOSPITAL | 200 | | 401 | scoped | | |
| *(× 144 endpoints × 8 callers)* | | | | | | | |

**Ethical constraints, non-negotiable.**
- Only the team's own deployment and the team's own synthetic accounts.
- **No intrusive testing against third-party production services** — not
  Razorpay, Cloudinary, Firebase, Resend, MSG91, Groq, Gemini, OpenAI or
  Anthropic. Test your boundary, not theirs.
- No real patient data at any point. All accounts synthetic and labelled.
- Findings are published with their fixes, which is what makes this responsible
  disclosure of your own system rather than a vulnerability advertisement.

---

## 8. Production infrastructure specification

This is the configuration the experiments are designed for. **It is a plan and a
cost estimate. Nothing has been purchased, subscribed to or deployed. Your
explicit authorisation is required before any spend.**

| Component | Option A | Option B | Basis for choice |
|---|---|---|---|
| Compute | AWS ECS Fargate (ap-south-1, Mumbai) | Google Cloud Run (asia-south1) | Mumbai region for data residency and latency to Indian users; both autoscale to zero-free baselines; Cloud Run is cheaper at low traffic, Fargate more predictable under sustained load |
| Managed PostgreSQL | AWS RDS PostgreSQL 15, Multi-AZ | Google Cloud SQL, HA | Multi-AZ for the availability arm; PITR backups; connection pooling via RDS Proxy or PgBouncer |
| Object storage / media | AWS S3 + CloudFront | Cloudinary paid tier | S3 is cheaper at scale; Cloudinary keeps the existing integration and does transformation |
| AI providers | paid plans on Gemini + OpenAI (two providers minimum) | add Anthropic as third | two paid providers is the floor for a failover experiment; free tiers cannot support Experiment C3/C4 |
| SMS | MSG91 with DLT registration | Twilio | **DLT registration is mandatory in India and is currently the blocker** — SOS SMS is dropped today |
| Email | Resend paid tier | AWS SES | Resend already live on `gramcare.me`; SES cheaper at volume |
| Push | Firebase FCM (free at this scale) | — | already live |
| Realtime / WebRTC | managed TURN (Twilio/Xirsys) + always-on signalling | self-hosted coturn | free-tier signalling with ~50 s cold start is unusable for emergencies |
| CDN | CloudFront | Cloudflare | — |
| Observability | Grafana Cloud or Datadog | self-hosted Prometheus + Grafana | **required for Experiment E** — you cannot report CPU/memory/DB latency without it |
| Secrets | AWS Secrets Manager | GCP Secret Manager | replaces `.env` files |
| DR | automated snapshots + tested restore | — | the backup-restoration arm of Experiment B needs a *tested* restore, not a configured one |

**Minimum paid resources to execute the pending experiments.** Deliberately not
the full production stack — only what unblocks measurement:

1. One production-tier compute instance with autoscaling (Experiment E).
2. One managed PostgreSQL instance with monitoring (Experiments A, E).
3. Paid API access to **two** AI providers (Experiment C3, C4).
4. One observability subscription or a self-hosted equivalent (Experiment E).
5. Managed TURN plus always-on signalling (Experiment F, video stage).

**No monthly figure is given here**, because quoting one without reading current
vendor pricing pages would be the kind of unverified number this whole exercise
exists to avoid. Costing this is the first task of Phase 2, and it comes to you
as a separate approval request against **Budget B**, entirely separate from the
₹10,000 publication budget.

---

## 9. Evidence status — what exists today

### Already measured, provenance recorded

| Measurement | Value | How obtained | Date |
|---|---|---|---|
| Backend test suite | **245 collected, 245 passed**, 663 s | `pytest -q` at commit `bd2f48d` | 19 Nov 2026 |
| Module count | 21 packages | `ls -d modules/*/` | 19 Nov 2026 |
| Routed endpoints | 144 | enumeration of `app.routes` | 19 Nov 2026 |
| Live demo-path checks | **33 of 33 passed** | scripted checks against production | 19 Nov 2026 |
| Cross-tenant isolation | hospital sees 1 own alert; unrelated doctor sees 0; pharmacist sees 1 scoped prescription | live API calls as three roles | 19 Nov 2026 |
| `/triage/ocr` unauthenticated | **HTTP 401** | live API call, no token | 19 Nov 2026 |
| `/assist/parse-prescription` | returns structured medicines; **was HTTP 500 on every call** before the fix | live API call | 19 Nov 2026 |
| Production integration status | push live; email live; payments live; **SMS not configured**; AI 2 usable providers | `GET /health/integrations` | 19 Nov 2026 |
| Free-tier cold start | 22–63 s observed | repeated first-request timing | 19 Nov 2026 |
| CI configuration | PostgreSQL 15 service; 3 web builds; 3 debug APKs per push/PR | `.github/workflows/main.yml` | 19 Nov 2026 |

### Verified from source, not measured

Idempotent sync mechanism (unique index + pre-check + `IntegrityError` handler);
AI key pooling, per-key cooldown, set-aside and circuit breaker; FHIR-R4-shaped
export with the code's own non-FHIR-server caveat; on-device triage fallback
present on web and mobile; device ASR via `speech_to_text` with `ta-IN`.

### Requires execution

Experiments A, B, F, G-full (free, start now); C1–C2 (free, report the tier).

### Requires paid infrastructure

C3, C4, E.

### Requires human participants and ethics approval

D1, D2, and any clinical-accuracy claim about the triage engine.

---

## 10. Integrity rules for this plan

1. **No number enters the manuscript that did not come from a recorded run.**
   Every results table above is empty and stays empty until it is filled by
   execution.
2. **Simulated, staging, production and estimated results are labelled
   differently and never merged into one table.**
3. **Free-tier measurements are never presented as production measurements.** If
   paid access does not arrive, the affected experiments stay marked pending and
   the manuscript says so.
4. **No fabricated participants, no fabricated significance, no fabricated
   clinical outcome.** Ever.
5. **No clinical validation claim** without clinician adjudication under ethics
   approval.
6. **Raw per-trial data is committed**, not only summary tables, so a reviewer
   can recompute.
7. **Every run records the commit SHA, the Alembic revision, the AI model version
   strings, and the infrastructure configuration.** A result without its
   conditions is not reproducible and should not be reported.
8. **No intrusive testing against third-party production services.**
