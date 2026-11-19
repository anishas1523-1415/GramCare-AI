# GramCare AI — Research Manuscript Audit

**Manuscript audited:** *GramCare AI: An Offline-First, Multilingual AI-Assisted
Telemedicine Ecosystem for Rural Healthcare* — 7 pages, Zenodo DOI
10.5281/zenodo.22879440. Preserved unmodified at
`docs/research/ORIGINAL_PAPER_as_submitted_to_Zenodo.pdf`.

**Audited:** 19 November 2026, against the manuscript text and against the live
repository at commit `bd2f48d`.

**Overall quality score: 4.5 / 10** as a journal manuscript.

That number needs explaining, because it is not a judgement on the engineering.
The system described here is real, substantial and better built than the paper
claims. The paper is a competent, honest **technical report**. It is not yet a
research paper, and the gap between those two things is the whole of the work
ahead. Specifically: the manuscript contains **no experiment**. It reports a test
count and a deployment status, and a test count is not a measurement of anything
a reader cares about. Every quantitative claim in it is either a passing-test
tally, a citation to a secondary statistic, or an architectural description.

**Classification: 2 — Needs major research work.**

---

## 1. The five biggest scientific weaknesses

### S1 — There is no evaluation. CRITICAL.

Section VII is titled "Testing and Evaluation" and contains testing only. "96 of
96 automated backend tests and 37 of 37 cross-module integration checks pass" is
a statement about the test suite, not about the system's behaviour under the
conditions the paper claims to have designed for. The paper's central claim is
that GramCare AI works when connectivity does not. **Nothing in the paper
measures what happens when connectivity does not.** No sync success rate, no
duplicate rate, no latency distribution, no recovery time, no failover timing, no
word error rate, no throughput figure.

An IEEE reviewer will reach Section VII, find no measured result, and stop. This
single weakness is sufficient for desk or first-round rejection at either target
journal, independently of everything else in this document.

### S2 — The headline statistic is misattributed. CRITICAL.

The abstract's first sentence and the Introduction's first sentence both state
that "the **rural** doctor-to-patient ratio stands near 1:11,082."

1:11,082 is the national ratio of population per **government allopathic
doctor**, from the Health Ministry's National Health Profile. It is not a rural
ratio. It excludes the private sector, which holds the large majority of India's
allopathic doctors, and it is not disaggregated by rural/urban at all. Ministry
estimates for *all* registered allopathic doctors give ratios around 1:811 to
1:834.

The real rural access gap is severe and well documented — the ~70% CHC specialist
vacancy figure in the same sentence is the stronger and better-sourced claim. But
the paper opens by attaching a precise number to the wrong denominator, and
attributes it to an IJMR article without a DOI. At a journal whose entire remit
is technology *and society*, misreading a health-workforce statistic in the first
sentence is close to disqualifying on credibility grounds.

**Fix:** cite the National Health Profile directly for 1:11,082 and describe it
correctly as government-sector doctors nationally; or replace it with a figure
that genuinely measures rural access and cite the primary source.

### S3 — Reference [3] cannot be found, and two more are miscited. CRITICAL.

Checked against Crossref and the arXiv API on 19 Nov 2026:

| Ref | As cited | What verification found |
|---|---|---|
| [1] | Ashista et al., PLOS Digital Health, "vol. 5, no. 2", 2026 | **Real.** DOI `10.1371/journal.pdig.0001204`. Volume/issue as given do not match PLOS's article-number scheme. No DOI in the reference. |
| [2] | "field study, West Garo Hills, Meghalaya, **ScienceDirect**, 2025" | **Real but badly miscited.** Actual venue: *SSM – Health Systems*, 2025, DOI `10.1016/j.ssmhs.2025.100124`. **ScienceDirect is a platform, not a journal.** No authors, no journal, no volume, no DOI. |
| [3] | "Artificial Intelligence in Rural Healthcare Delivery: Bridging Gaps and Enhancing Equity through Innovation," **arXiv preprint, 2025** | **NOT FOUND.** No arXiv record for that title. No Crossref record for that title. Crossref returned only different papers on adjacent topics. **Treat this reference as unverifiable until someone produces the actual item.** |
| [4] | "SymptomAI...", **arXiv preprint, 2026** | **Real but wrong repository.** It is a Research Square preprint, DOI `10.21203/rs.3.rs-9684240/v1`, not arXiv. |
| [5]–[9] | Reports and standards | No DOIs, no URLs, no access dates, no publisher locations. [7] is a **commercial market-research report** used to support factual rural-internet claims — not acceptable evidence at an IEEE journal. |
| [10]–[12] | FastAPI / Flutter / WebRTC docs | Framework documentation cited as research references. Harmless but it pads the list and signals a thin literature base. |

Reference [3] is the serious one. Whatever its origin, a citation to a
non-existent preprint in a submitted manuscript is a research-integrity problem,
not a formatting slip. **Find the actual source or delete the claim it
supports.** It currently carries the paper's entire argument that AI can bridge
rural workforce gaps.

### S4 — Only four research references, and no systematic review behind the gap claim. HIGH.

Of thirteen references, four are research works ([1]–[4]); one of those four
cannot be found. The paper then asserts in Section II-D that "**No work reviewed
here** unifies an offline-first, family-scoped health record, voice-first
regional-language AI triage, and a closed consultation-to-pharmacy-to-emergency
loop."

That sentence is literally true and rhetorically worthless: three papers is not a
review, and "no work reviewed here" with three works reviewed establishes
nothing. A reviewer reads this as an unsupported novelty claim. The Conclusion
escalates it to "a gap that runs through the existing literature," which the
evidence does not support.

**Fix:** a real review of 25–40 works across the ten topic areas, with a
documented search protocol (databases, query strings, date range, inclusion
criteria, counts at each stage). Then the gap statement becomes a finding instead
of an assertion.

### S5 — The paper disclaims the thing it needs most, and the disclaimer is correct. HIGH.

Section XI says the AI triage engine is not clinically validated, and that is
honest and right. But the paper's contribution #2 is an "AI symptom-triage engine
… that degrades gracefully to an on-device fallback rather than failing outright."
With no validation of either the primary or the fallback path, the reader has no
way to know whether graceful degradation degrades to something *useful* or to
something *wrong but confident*. The paper does not claim clinical equivalence —
good — but it also never says what the fallback's output is worth, which leaves
the contribution unmeasured.

This is addressable without clinical approval: agreement between the AI path and
the rule-based fallback on a fixed vignette set, scored against a clinician's
severity banding, is a legitimate engineering result and needs no patients. It is
Experiment C/D territory, not an ethics-board problem.

---

## 2. The five biggest technical weaknesses

### T1 — The headline contribution is overstated by scope. CRITICAL.

Section IV-D: "**Every write** made while offline on a mobile client is assigned a
client-generated UUID before it reaches the server, and the entire queue for an
encounter is sent as one idempotent batch."

What the repository actually contains, verified by reading it:

- `client_uuid` is a column on **exactly one** model: `EHRRecord`
  (`backend/python_service/models.py:406`), unique-indexed.
- `POST /ehr/sync` and `POST /ehr/record` dedupe on it properly — a pre-check,
  plus an `IntegrityError` handler for the race, plus a `duplicates[]` field in
  the response (`modules/ehr_sync/router.py:320–393`). **This part is genuinely
  well engineered** and better than the paper conveys.
- The Flutter client queues **only** Health Wallet records
  (`mobile/patient_app/lib/services/sync_service.dart`: "batches them to POST
  /ehr/sync").
- `Payment` has a separate `idempotency_key` with a partial unique index — a
  different and also sound mechanism, but not the same one and not described.
- **No other write path is idempotent.** Appointments, prescriptions, SOS
  triggers, lab bookings, preorders, vitals: none carry a client UUID and none
  are queued offline.

So the true claim is: *Health Wallet records created offline sync idempotently.*
That is a real, defensible, narrower contribution. The paper's version — "every
write" — is false as written, and a reviewer who opens the public repository will
find that out. Narrow the claim and it becomes a strength; leave it and it
becomes the reason for rejection.

### T2 — The two verification numbers are from different points in time. CRITICAL.

The paper presents "96/96 automated backend tests and 37/37 cross-module
integration checks pass on a live Docker stack" as one checkpoint, in the
abstract, in Section VII, in Table II, in Section X and again in the Conclusion.

- The 37/37 figure traces to `docs/audits/INTEGRATION_VERIFICATION_REPORT.md`.
  **That same report states the suite was 73 tests at the time.**
- The 96 figure is from a later checkpoint.
- **The suite today is 245 tests, all passing** (`pytest --collect-only`: "245
  tests collected"; full run 19 Nov 2026: "245 passed").

Two numbers from different dates, presented as a single verification event, with
both now stale by a factor of 2.5. The paper understates its own work and is
internally inconsistent at the same time. Either re-run both checks at one commit
and report that commit, or drop the integration figure and report the test count
with its SHA.

### T3 — Tamil speech recognition is the operating system's, not GramCare's. HIGH.

The abstract and contribution #2 lead with "voice and Tamil-language input," and
the Related Work section positions this against SymptomAI as a differentiator.

In the code, this is the `speech_to_text` Flutter plugin called with
`localeId: 'ta-IN'` (`mobile/patient_app/lib/screens/triage_screen.dart:98`) and
`flutter_tts` with the same locale. The recognition is performed by the device —
Google's or Apple's on-device/cloud ASR. GramCare contributes **locale selection
and a voice-first interaction design**, which is a legitimate HCI contribution,
and **no ASR of its own**.

This matters in two ways. It is an overclaim if presented as a language-technology
contribution. And it reshapes the experiment: a word-error-rate study would be
measuring **Google's Tamil recogniser**, not GramCare, and the publishable
question is not "how good is our ASR" but "does voice-first Tamil input let a
low-literacy user complete a triage task they could not complete by typing, and
what happens when the recogniser is absent?" (The patient app already handles the
absent case — `'Speech recognition unavailable on this device.'` — and the paper
never mentions that failure mode.)

### T4 — The architecture section describes the intended system, not the deployed one. HIGH.

Verified discrepancies between Section IV/VIII and the running system:

| Paper says | Repository / production says |
|---|---|
| "more than twenty domain modules" | **21 module packages**, **144 routed endpoints**. Accurate, and understated. |
| Email and SMS "not fully completed" (Section XI) | **Email is live** on a verified domain (`/health/integrations`: Resend configured, sender `no-reply@gramcare.me`). **SMS is still not configured** — `MSG91_AUTH_KEY not set — SOS contact SMS is dropped`. Half the limitation is stale; the other half is worse than it sounds, because the dropped message is the SOS family notification. |
| "Android builds are debug-signed only" | True for the doctor and pharmacy apps (`signingConfig = signingConfigs.getByName("debug")`). **The patient app has a real release signing config** reading `key.properties`. |
| Health-wallet records in "an AES-encrypted local database"; reminder and profile caches "not yet encrypted" | Both were true at the time of writing. The caches **now** route through `HiveAesCipher` via `services/encrypted_boxes.dart`. The limitation is resolved and the paper should say so with a commit reference. |
| Free-tier hosting cold start "up to a minute" | Confirmed, 22–63 s observed. Honestly reported, and the paper is right that it is unacceptable for SOS. |

None of these are dishonest — the paper was accurate when written. But a
manuscript whose stated limitations have moved on is a manuscript that will be
read as careless. Every claim needs re-verification against one named commit
before submission.

### T5 — Security claims are made without a threat model, and the system had real holes. HIGH.

Section IX lists controls: bcrypt, JWT plus server-side refresh sessions,
role-based access, rate limits on AI endpoints, no committed secrets. All verified
present. But the section asserts controls rather than demonstrating isolation,
and a full audit of the same codebase on 19 Nov 2026 found **three cross-tenant
data leaks** behind exactly those controls:

- `GET /sos/active` returned **every** active emergency in the system — patient
  name, live GPS, voice recording — to any account with role `HOSPITAL` and to
  any approved doctor, with no scoping to the hospital an alert was routed to.
- `PUT /sos/{id}/respond` let any of them accept an alert routed elsewhere.
- `GET /pharmacy/queue` returned **every** unfulfilled prescription in the
  database — diagnosis, prescribing doctor, medicine list — to any pharmacist.
- `POST /triage/ocr` was unauthenticated and open to the internet.

All four are fixed and verified in production as of commits `7c3f8c5`–`bd2f48d`
(hospital sees 1 of its own alerts; an unrelated doctor sees 0; `/triage/ocr`
returns 401). **This is the single best thing that has happened to this paper.**
"Role-based access control is implemented" is an assertion. "We built a
multi-tenant isolation test suite, it found three cross-role leaks in a system
that already had RBAC, and here is the before/after" is a *result* — and it is
precisely the kind of result IEEE TTS cares about, because it is a finding about
how health systems fail people, not a feature list.

---

## 3. Section-by-section assessment

Scores are as a journal manuscript, not as documentation.

### Title — 7/10 · Priority: Medium
Accurate and descriptive, but it is a system announcement, not a claim. It
promises an ecosystem; a reviewer wants to know what was *found*.
**Recommended:** lead with the contribution and the evidence. For TTS, something
on the order of *"Offline-First, Family-Scoped Health Records for Rural Primary
Care: Design, Multi-Tenant Isolation Failures, and Measured Degradation Under
Intermittent Connectivity."* Long, but every clause is a thing you can show.

### Abstract — 5/10 · Priority: Critical
Well written as prose. Structurally wrong for a research abstract: ~60% of it is
architecture and technology names (FastAPI, Next.js, Flutter, Socket.io, Groq,
Gemini, OpenAI, Anthropic all appear). It contains no result. Its one number is
the test count. Its first statistic is misattributed (S2).
**Required:** rebuild as problem → gap → approach → **measured results with
numbers** → limitation. Cut every framework name; they belong in Section VI. Keep
it under 250 words (JBHI's stated cap, and good practice for TTS).

### Keywords — 7/10 · Priority: Low
Ten terms, reasonable. Includes "FastAPI" and "Flutter" — implementation tools
are poor index terms. Replace with IEEE-thesaurus-aligned terms: *health
information management*, *mobile computing*, *data synchronization*,
*fault tolerance*, *medical information systems*.

### Introduction — 6/10 · Priority: High
I-A and I-B are the strongest writing in the paper, and I-B's framing — platforms
"treat a village clinic as a degraded version of that user rather than a
different context altogether" — is a genuinely good sentence that belongs in the
abstract. Weaknesses: the misattributed statistic (S2); I-B characterises
e-Sanjeevani and private apps with no citation of either; I-D lists contributions
that are capabilities rather than findings.
**Required:** fix the statistic, cite the platforms being criticised, and rewrite
I-D so each bullet names what was measured.

### Problem statement — 6/10 · Priority: Medium
Present and clear, but distributed across I-A to I-C rather than stated. The
three operating conditions it identifies — shared device, Tamil-only speaker,
mid-session signal loss — are the paper's sharpest idea and deserve to be
numbered as explicit design constraints that the evaluation then tests one by one.

### Research gap — 3/10 · Priority: Critical
See S4. Asserted from three papers, escalated in the Conclusion to a claim about
the literature as a whole. Must be rebuilt on a documented review.

### Related work — 4/10 · Priority: Critical
Four works, one unverifiable. Each subsection follows the pattern "paper X found
Y; GramCare addresses this by design" — which positions GramCare as a *solution*
to each cited paper rather than situating it in a research conversation. No
comparison of approaches to the same problem, no discussion of what the cited
work measured, no critique. Section II-A in particular cites Ashista et al.'s
finding about multi-sync-per-encounter and then says GramCare "addresses this
directly by design" — but offers no evidence that it does, which is exactly what
Experiment A must supply.
**Required:** 25–40 works, organised by research question rather than by paper,
with a comparison matrix on dimensions you can actually place yourself on.

### Research contributions — 4/10 · Priority: Critical
Four bullets, all phrased as features. One is factually over-scoped (T1). None is
accompanied by a measurement. See the companion novelty document for the
rewritten set.

### System architecture — 8/10 · Priority: Low
The best section in the paper. The four-layer split is clean, the shared-JWT
decision between FastAPI and the Socket.io service is a real design choice
explained well, and the AI provider-chain description (priority order, key
pooling, cooldown on rate limit, set-aside on billing failure, honest failure
reporting instead of a fabricated result) is specific and verified present in
`backend/python_service/ai/` — `keypool.py`, `metrics.py`, `manager.py`.
**Only required change:** correct IV-D's scope per T1.

### Methodology — 2/10 · Priority: Critical
**There is no methodology section.** Section VI describes what was built, module
by module, in the order it was built. A research paper needs a section stating
what questions were asked, what was manipulated, what was measured, under what
conditions, and how the results were analysed. Its absence is the structural
reason the paper reads as a report.

### Implementation — 7/10 · Priority: Medium
Accurate and verified (21 modules, 144 endpoints). But it is organised by
development module ("Module 1… Module 6"), which is a project-management
narrative, not a technical one. Reorganise by subsystem, and compress hard — at
10 pages, implementation detail is competing with results, and results win.

### Experimental evaluation — 1/10 · Priority: Critical
Does not exist. See S1. This is the work of the next phase.

### Results and discussion — 2/10 · Priority: Critical
Section X is a feature checklist with a test count. There is no discussion: no
interpretation, no comparison to prior work, no analysis of why anything behaves
as it does, no threats to validity.

### Security and privacy — 5/10 · Priority: High
Controls are real and correctly described. No threat model, no attacker
capabilities, no isolation testing — and the system contained three cross-tenant
leaks while this section was true as written (T5). Rebuild around a threat model
and report the isolation findings as a result. It will be one of the paper's
strongest sections.

### Limitations — 8/10 · Priority: Medium
Genuinely good, and rare. Eight specific, unflattering, unresolved items stated
plainly. This section is why the paper deserves a serious revision rather than
abandonment: the authors are honest. Two items are now stale (T4) — update them
with commit references rather than deleting them, because showing what you fixed
and when is more credible than a shorter list.

### Future work — 7/10 · Priority: Low
Appropriate and concrete. Trim: at 10 pages, future work earns one paragraph, not
five subsections.

### Conclusion — 4/10 · Priority: High
Repeats the stale test counts a third time and escalates the gap claim beyond the
evidence ("addresses a gap that runs through the existing literature"). Must
restate measured results instead.

### References — 2/10 · Priority: Critical
See S3. One unverifiable entry, two with wrong venues, a platform cited as a
journal, no DOIs anywhere, a market-research report supporting factual claims,
and framework documentation padding the count. Every entry needs rebuilding in
full IEEE style with verified DOIs.

### IEEE formatting — 5/10 · Priority: High
Two-column IEEE layout, correct heading hierarchy, numbered tables with captions,
figure captions present. Problems: author block lists a roll number
("727823TUAD010") where an IEEE affiliation belongs, and no email or ORCID; no
corresponding author designated; tables are "presented as full-width figures
following this section," which is a workaround that will not survive IEEE
production; **TTS requires a `.DOC` template and does not accept LaTeX**, so
check what the current file was produced in; references are not in IEEE style.

### Originality and novelty — 5/10 · Priority: Critical
The *system* is substantial, integrated and real. The *research* novelty is
currently unestablished, because novelty is a claim about the literature and the
literature has not been reviewed. There is a defensible contribution here — see
the novelty document — but it is narrower and more interesting than the one the
paper currently claims.

---

## 4. Specific unsupported or contradictory statements

| Location | Statement | Problem |
|---|---|---|
| Abstract, I-A | "rural doctor-to-patient ratio … 1:11,082" | Misattributed; it is a national government-sector figure |
| IV-D | "Every write made while offline … assigned a client-generated UUID" | False as written; applies to `EHRRecord` only |
| Abstract, VII, Table II, X, XIII | "96/96 tests and 37/37 integration checks" | Two different checkpoints presented as one; both stale (now 245 tests) |
| II-D | "No work reviewed here unifies…" | True but vacuous — three works reviewed |
| XIII | "a gap that runs through the existing literature" | Exceeds the evidence of II-D |
| I-B | e-Sanjeevani and private apps "built for an urban, high-literacy, always-connected user" | No citation for either platform |
| XI | "Email and SMS delivery depend on external setup … not been fully completed" | Email is now live; SMS is not — needs splitting |
| XI | "Android builds are debug-signed only" | Patient app has release signing |
| IX, XI | "reminder and profile caches … not yet encrypted" | Now encrypted via `HiveAesCipher` |
| Abstract, I-D | "Gemini-backed" triage | Contradicts IV-C's four-provider chain; Gemini is one provider in a configurable order |
| VII | "Forty-five or more commits … since the previous review" | Commit count is not a research result; delete |
| Table II | "Deployment evidence: 96/96 backend tests … live deployment" vs "Existing Platforms: rarely demonstrated end to end" | Compares your test suite against other platforms' *published* evaluation — not a like-for-like dimension |

---

## 5. What is already strong, and should be protected in revision

Listed because a 4.5/10 score invites the wrong conclusion.

1. **The limitations section.** Honest, specific, unflattering. Keep its spirit
   completely.
2. **The architecture.** Four layers, one identity, one API contract, shared JWT
   across two services. Clean and well explained.
3. **The AI provider chain.** Key pooling, per-key cooldown, set-aside on billing
   failure, circuit breaker, and — importantly — refusing to return a fabricated
   result when no provider can answer. `ai/keypool.py`, `ai/metrics.py`,
   `ai/manager.py`. This is a genuinely good piece of reliability engineering and
   the paper undersells it.
4. **The idempotent sync, as actually built.** Unique-indexed client UUID,
   pre-check plus `IntegrityError` race handler, explicit `duplicates[]` in the
   response. Correct, and correct for the right reasons.
5. **Honest AI failure reporting.** `/health/ai` and `/health/integrations` tell
   you *why* something is mocked rather than silently degrading. Few student
   systems do this; it is a paper-worthy design stance.
6. **FHIR scoping discipline.** The code's own docstring says "FHIR-R4-*shaped*
   … it is NOT a FHIR server, does not do SMART-on-FHIR auth." Carry that
   caveat into the manuscript verbatim.
7. **The CI pipeline.** Verified: PostgreSQL 15 service container, three web
   builds, three Flutter APK builds, on every push and PR. Real reproducibility
   infrastructure that the paper mentions in one sentence and should exploit.
8. **The writing.** Clear, well-paced English with no filler. **Do not spend any
   of the ₹10,000 on language editing.** This manuscript needs evidence, not
   prose.

---

## 6. Repository verification record

All figures below were obtained by running or reading the repository at commit
`bd2f48d` on 19 November 2026, not from the manuscript.

| Claim in paper | Verification method | Result |
|---|---|---|
| "96/96 automated backend tests" | `pytest --collect-only -q`; full run | **245 collected, 245 passed** (663 s) |
| "37/37 cross-module integration checks" | located in `docs/audits/INTEGRATION_VERIFICATION_REPORT.md` | Exists; that report states 73 tests at the time — **different checkpoint** |
| "more than twenty domain modules" | `ls -d modules/*/` | **21** — accurate |
| (unstated) endpoint count | enumerated `app.routes` | **144 routed endpoints** |
| "client-generated UUID … idempotent" | read `models.py`, `modules/ehr_sync/router.py`, `sync_service.dart` | **Exists, correct, scoped to `EHRRecord` only** |
| "key pooling and circuit breaking" | read `ai/keypool.py`, `ai/metrics.py`, `ai/manager.py` | **Verified present** |
| "FHIR-exportable Health Passport" | read `modules/ehr_sync/router.py`, `core/fhir_export.py` | **Verified** — FHIR-R4-shaped bundle; not a FHIR server, and the code says so |
| "degrades to an on-device fallback" | `lib/offlineTriage.ts` (199 lines), `offline_triage_service.dart` | **Verified present on web and mobile** |
| "Tamil … voice input" | `triage_screen.dart:98` | **Device ASR** via `speech_to_text`, `localeId: 'ta-IN'` — not a GramCare model |
| "CI … against PostgreSQL 15, builds three portals and three APKs" | `.github/workflows/main.yml` | **Verified** — `postgres:15`, 3 × `npm run build`, 3 × `flutter build apk --debug` |
| "Email and SMS … not fully completed" | `GET /health/integrations` on production | **Email live** (Resend, own domain); **SMS not configured** |
| "debug-signed only" | three `app/build.gradle.kts` | True for doctor and pharmacy; **patient app has release signing** |

---

## 7. Required modifications, in priority order

**Critical — the paper cannot be submitted anywhere without these**

1. Run the experiments. No evaluation, no paper. (See the experimental plan.)
2. Fix or remove reference [3]; rebuild all references in IEEE style with DOIs.
3. Correct the 1:11,082 attribution.
4. Narrow the idempotency claim to `EHRRecord`.
5. Re-run and re-report the verification numbers at one named commit.
6. Add a Methodology section.
7. Rebuild Related Work and the gap on a documented review of 25–40 works.
8. Rewrite the abstract around measured results.

**High**

9. Rebuild Security and Privacy around a threat model, and report the
   multi-tenant isolation findings as a result.
10. Scope the Tamil/voice claim to interaction design, not language technology.
11. Re-verify every limitation; update the stale ones with commit references.
12. Fix the author block: affiliations and emails, not roll numbers; designate a
    corresponding author; add ORCIDs.
13. Rewrite the Conclusion around results.

**Medium**

14. Retitle around the contribution.
15. Compress Implementation and Future Work to make room for results.
16. Replace tool names in the keywords with IEEE thesaurus terms.
17. Move the tables inline properly rather than as full-width figures.

**Low**

18. Decide Word vs LaTeX based on the target journal — TTS requires `.DOC`.
