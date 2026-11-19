# Research Gap, Novelty and Contribution Analysis

**Compiled:** 19 November 2026.
**Status of the literature work below: PARTIAL.** This is a targeted probe of the
two most dangerous overlaps, not the 25–40-work systematic review the manuscript
needs. Works named here were **identified via database search; their full texts
have not been read.** Nothing in this document should enter the manuscript until
the full review is done and the primary sources are read. That is Phase 2 work.

---

## 1. The headline finding, stated plainly

**Two of the paper's four claimed contributions are not novel as mechanisms, and
one of those two is a solved problem in industry practice.**

This is not a reason to abandon the paper. It is a reason to move the novelty
claim from the *mechanism* to the *measurement*, which is where it actually
belongs and where the literature is genuinely empty.

| Paper's claimed contribution | Mechanism novel? | Where the real gap is |
|---|---|---|
| C1 — offline-first idempotent UUID-keyed sync | **No.** Client-generated UUIDs, idempotency keys and upsert-on-key are established offline-first practice (UUIDv7/ULID, per-write idempotency keys, deduped-response patterns are all documented industry guidance). | **Nobody has published a quantitative evaluation of these approaches on clinical records.** The search returned no controlled study measuring duplicate rate, data-loss rate or sync latency for an offline-first health record. |
| C2 — AI triage with Tamil voice and on-device fallback | **Partly.** Conversational symptom assessment is active research (SymptomAI, TriageAgent, MECR-RAG). Tamil ASR here is the **device's**, not GramCare's (see audit T3). | **Whether a degraded fallback preserves triage severity banding is unmeasured anywhere.** |
| C3 — closed consultation→pharmacy→emergency loop | **Arguably yes, as an integration.** No reviewed work unifies these on one record. | Integration is weak novelty on its own. It becomes strong when paired with a **measured** claim about what integration buys — e.g. multi-tenant isolation across seven roles on one record. |
| C4 — multi-provider AI failover with key pooling and circuit breaking | **No.** `ContinuityBench` (arXiv 2607.15899) is a published benchmark and systems study of **stateful failover in multi-provider LLM routing**; commercial gateways (e.g. Portkey) already retry across providers. | **No paper evaluates whether triage output survives a provider failover.** The search found nothing measuring triage-level consistency, under-triage or over-triage across a failover event. |

**The pattern is consistent: the engineering is standard, the measurement is
missing.** That is a publishable position, and an honest one. It is also a much
better fit for IEEE TTS than a novelty claim would be, because TTS cares about
consequences, not mechanisms.

---

## 2. Works that must be read before any novelty claim is made

### Directly threatening — read these first

| Work | Venue / ID | Why it matters |
|---|---|---|
| **ContinuityBench: A Benchmark and Systems Study of Stateful Failover in Multi-Provider LLM Routing** | arXiv 2607.15899 | **This is the paper that could sink C4.** It defines failover continuity, proposes a History-Forwarding proxy, and **open-sources an evaluation harness that injects controlled failovers at configurable turn indices.** Read it, cite it, and position against it: it evaluates general multi-turn conversation, not clinical triage. Its harness may be directly reusable for Experiment C — which would make that experiment both cheaper and more credible. |
| **Ashista et al., "An offline-first electronic health record for vulnerable populations: A mixed-methods feasibility study"** | PLOS Digital Health, 2026, DOI `10.1371/journal.pdig.0001204` | Already cited as [1], and the citation is substantively right. **The closest prior work to C1.** Its multi-sync-per-encounter finding is the specific failure your design claims to prevent. You must show you prevent it, not assert it. |
| **"Disconnected data: mHealth data systems and challenges for primary health care workers…"** | *SSM – Health Systems*, 2025, DOI `10.1016/j.ssmhs.2025.100124` | Cited as [2] with the wrong venue. Field evidence of duplication and unreliable offline behaviour in rural Indian mHealth — the motivating evidence for C1. |
| **SymptomAI: Toward a Conversational AI Agent for Everyday Symptom Assessment** | Research Square preprint, DOI `10.21203/rs.3.rs-9684240/v1` | Cited as [4] as an arXiv preprint. It is Research Square. Closest prior work to C2. |
| **TriageAgent: Towards Better Multi-Agents Collaborations for LLM-Based Clinical Triage** | Findings of EMNLP 2024 | Compares multi-LLM collaboration (majority voting, debate, adjudication) against single-model baselines. **Relevant to C4**: it is multi-model for *accuracy*; yours is multi-provider for *availability*. Name that distinction explicitly — it is a real one and it protects your contribution. |
| **MECR-RAG — Multi-Evidence Clinical Reasoning With RAG for Emergency Triage** | retrospective evaluation study, PMC12887567 | 236 triage encounters, 5-level categories, labels from blinded senior triage nurses. **This is the methodological template for your triage evaluation** — including how to get defensible labels without running a clinical trial. |
| **"Evaluation format, not model capability, drives measured triage failure in the assessment of consumer health AI"** | arXiv 2603.11413 | Potentially important and uncomfortable: if evaluation format dominates measured triage failure, your Experiment D design has to account for it or the result is an artefact. Read before designing the vignettes. |
| **LLM-Based Multi-Agent Systems for Clinical Workflows: A Survey of AI Hospitals** | ACL 2026 (`2026.acl-long.2123`) | Introduces a four-layer evaluation stack — safety, process, outcome, operations. Useful as the framing for your whole evaluation section. |

### Reference [3] — unresolved

"Artificial Intelligence in Rural Healthcare Delivery: Bridging Gaps and
Enhancing Equity through Innovation," cited as an arXiv preprint, 2025.
**Not found on arXiv. Not found on Crossref.** Either produce the item or remove
it and the claim it supports. Candidate replacements surfaced by search, both
needing verification: *Artificial Intelligence for Health Equity: Bridging Gaps
with Multimodal Intelligence* (DOI `10.1007/978-981-95-9027-8_4`, 2026) — note
this is a book chapter, not a journal article.

### Still to search — the review is not done

Nine of the ten topic areas your brief lists have not been searched yet:
offline-first EHR beyond [1]; rural telemedicine outcomes; Tamil speech
recognition in healthcare; mHealth in low-connectivity settings; data
synchronisation and conflict resolution (CRDT literature in particular);
healthcare cybersecurity and multi-tenant isolation; rural digital-health
adoption; ABDM/national digital health infrastructure; WHO workforce evidence.

**A CRDT search is mandatory.** Conflict-free replicated data types are the
academically respectable answer to offline sync, and a reviewer will ask why you
used a unique-key dedupe instead. You have a good answer — append-only clinical
records with client UUIDs avoid most apparent conflicts without CRDT machinery,
and immutable timestamped clinical events are a recognised pattern — but you must
make it explicitly and cite the alternative you rejected.

---

## 3. The contribution set, rewritten

Each is phrased as something that can be true or false, and measured.

> **N1 — Offline-first clinical record synchronisation, measured.**
> We implement client-UUID-keyed idempotent synchronisation for family-scoped
> health records and report the first quantitative evaluation of such a scheme on
> clinical records under controlled network fault injection: duplicate rate,
> data-loss rate, sync latency distribution and behaviour under concurrent
> multi-device edits of the same family profile.
> *Novelty:* the measurement, not the mechanism.
> *Prior art to position against:* Ashista et al. 2026; industry offline-first
> practice; the CRDT literature.
> *Measured by:* Experiment A.
> *Honest scope:* applies to `EHRRecord` only. State that.

> **N2 — Triage-severity stability across AI provider failover.**
> We measure whether an AI triage assessment preserves its severity banding when
> the serving provider changes mid-chain, and when the chain is exhausted and the
> system falls back to on-device rules — reporting severity-band agreement,
> under-triage and over-triage rates across the failover boundary.
> *Novelty:* **this appears genuinely unoccupied.** The search found failover
> benchmarks without clinical outcome measures, and triage benchmarks without
> failover. This is the strongest novelty claim available.
> *Prior art:* ContinuityBench (failover, no clinical measure); TriageAgent
> (multi-model for accuracy, not availability); MECR-RAG (triage labels method).
> *Measured by:* Experiments C and D.
> *Hard constraint:* **do not claim clinical equivalence.** The claim is about
> *consistency of the system's own output*, not correctness against a diagnosis.

> **N3 — Multi-tenant isolation failures in a role-complete rural health platform.**
> A single shared record across seven roles is the design's main benefit and its
> main hazard. We report that a platform with role-based access control, bcrypt
> password hashing, server-tracked JWT refresh sessions and endpoint rate
> limiting nonetheless exposed every active emergency alert — patient name, live
> GPS coordinates and voice recording — to any account holding the `HOSPITAL`
> role, and every unfulfilled prescription to any pharmacist; we give the
> isolation test construction that found these, and the scoping that fixes them.
> *Novelty:* an empirical security finding from a real multi-role health system,
> with reproducible tests. Rare in the literature because few authors publish
> their own failures.
> *Measured by:* Experiment G.
> *Why it is the best thing in the paper for TTS:* it is a finding about how
> health software harms people, with a fix — which is TTS's subject exactly.
> *Evidence already in hand:* fixed and verified in production at commits
> `7c3f8c5`–`bd2f48d`; hospital account sees 1 of its own alerts, unrelated
> doctor sees 0, `/triage/ocr` returns 401 unauthenticated.

> **N4 — Graceful degradation as an equity property, measured end to end.**
> We measure completion of the full care pathway — symptom capture → triage →
> consultation → prescription → fulfilment → emergency escalation — under seven
> network conditions from stable broadband to total disconnection, and report
> which pathway stages survive each.
> *Novelty:* moderate. The framing — that assuming a network is an exclusion
> decision, and here is the measured cost of that assumption — is the paper's
> societal thesis made quantitative.
> *Measured by:* Experiments B and F.

### Contributions to retire

- **"First to…" anything.** Nothing in the paper supports a first-ness claim and
  the current evidence base cannot support one. Delete the construction entirely.
- **Integration-as-contribution.** "Twenty-plus modules behind one API" is
  engineering scale, not research novelty. Keep it in Implementation.
- **Tamil as language-technology novelty.** It is the device's ASR. Reframe as
  interaction design and, if you want a measured claim, measure *task completion*
  by input modality — not word error rate.
- **The test count.** 245/245 passing is good engineering hygiene and belongs in
  a reproducibility statement, not in the abstract and not as a result.

---

## 4. Contribution-to-evidence matrix

| | Contribution | Evidence needed | Have it? | Source of evidence | Blocking issue |
|---|---|---|---|---|---|
| N1 | Offline sync, measured | duplicate rate, loss rate, latency distribution, concurrent-edit outcome | **No** | Experiment A | needs fault-injection harness; none exists yet |
| N1 | mechanism is correct | code-level proof of idempotency | **Yes** | `models.py:406`, `ehr_sync/router.py:320–393`, unique index + `IntegrityError` handler | — |
| N2 | severity stability across failover | banded agreement, under/over-triage across failover | **No** | Experiments C, D | needs a vignette set and a clinician to band it; **paid AI keys for a fair provider comparison** |
| N2 | failover works at all | failover success rate, recovery latency | **Partial** | `ai/keypool.py`, `ai/metrics.py` + existing tests | tests prove the path exists; no timing measured |
| N3 | isolation failures + fix | the three leaks, the tests, before/after | **Yes — strongest evidence in the project** | commits `7c3f8c5`–`bd2f48d`; live verification 19 Nov 2026 | needs writing up as a systematic study, not an anecdote |
| N3 | no further leaks remain | a complete cross-role isolation matrix | **No** | Experiment G | needs the full 7-role × endpoint matrix built |
| N4 | pathway survival by network condition | per-stage completion under 7 conditions | **No** | Experiments B, F | needs network emulation |
| — | 245/245 tests at one commit | CI run with SHA | **Yes** | full run 19 Nov 2026, 663 s | report the SHA |
| — | 21 modules, 144 endpoints | enumeration | **Yes** | route enumeration | — |
| — | clinical accuracy of triage | clinician-adjudicated validation | **No, and out of scope** | — | **requires ethics approval; explicitly deferred** |
| — | real-world rural usage | field deployment with users | **No, and out of scope** | — | requires ethics approval and a pilot site |

---

## 5. The research gap statement, as it should read

Current (Section II-D) — unsupported:

> "No work reviewed here unifies an offline-first, family-scoped health record,
> voice-first regional-language AI triage, and a closed
> consultation-to-pharmacy-to-emergency loop inside one connected ecosystem."

Proposed — defensible once the review is complete:

> Offline-first health-record synchronisation is well established as engineering
> practice, and client-generated identifiers with idempotent upserts are the
> standard answer to duplicate writes. What the literature does not provide is
> measurement: feasibility studies report that offline-first design helps
> low-resource clinics and that repeated synchronisation per encounter erodes
> record integrity in the field, but we found no quantitative evaluation of an
> idempotent clinical-record sync under controlled network faults. Separately,
> multi-provider LLM failover has been benchmarked for conversational continuity,
> and clinical triage has been benchmarked for accuracy, but no work connects the
> two — whether a triage assessment's severity banding survives a provider
> failover, or an exhausted provider chain, is unreported. Finally, systems that
> place several care roles on one shared record are described architecturally far
> more often than their isolation properties are tested. This paper addresses
> these three measurement gaps in a single deployed system.

Note what changed: it no longer claims to be first at anything. It claims the
*measurements* are missing, which is checkable, and it is a stronger position
precisely because it concedes the mechanisms are known.

---

## 6. Risks to the novelty claim

| Risk | Severity | Mitigation |
|---|---|---|
| ContinuityBench already covers failover measurement adequately | **High** | Read it. If its harness fits, use it and cite it — "we apply X's harness to a clinical setting it did not evaluate" is a perfectly good contribution. Do not pretend it does not exist. |
| A CRDT paper has already measured clinical offline sync | **High** | Search before writing. If one exists, N1 becomes a comparison rather than a first measurement — still publishable, differently framed. |
| Reviewers read N3 as "the authors shipped insecure software" | **Medium** | Frame as a systematic isolation study of a system built to current practice. The point is that RBAC was present and insufficient — that is the finding. Report the fix and the tests. |
| Evaluation-format artefacts dominate the triage result | **Medium** | arXiv 2603.11413 warns about exactly this. Design the vignette protocol with it in hand. |
| N2 needs paid AI keys for a fair cross-provider comparison | **Medium** | Separate infrastructure budget; **your explicit approval required before any spend.** Free-tier rate limits cannot support a provider-latency comparison, and reporting free-tier numbers as production numbers is not acceptable. |
| 10-page TTS limit cannot hold four contributions plus a literature review | **High** | **Cut to two or three.** N3 and N2 are the strongest and most TTS-appropriate. N1 is strong but may belong in a second paper. Decide before writing, not during. |
