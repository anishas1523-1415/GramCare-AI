# Research Project Changelog

All modifications to the manuscript and to research artefacts, in order.

## 2026-11-19 — Phase 1: audit and research

**Manuscript: NOT MODIFIED.** The original is preserved byte-for-byte at
`docs/research/ORIGINAL_PAPER_as_submitted_to_Zenodo.pdf`. Phase 1 is audit only;
rewriting begins in Phase 3, after the evidence exists.

**Zenodo preprint: NOT MODIFIED.** DOI 10.5281/zenodo.22879440 untouched.

Added:
- `GRAMCARE_RESEARCH_AUDIT.md` — section-by-section audit, 20 sections scored,
  repository verification record.
- `GRAMCARE_RESEARCH_GAP_AND_NOVELTY.md` — contribution analysis, rewritten
  contribution set, contribution-to-evidence matrix. Partial literature probe.
- `GRAMCARE_EXPERIMENTAL_PLAN.md` — Experiments A–G, all templates empty.
- `GRAMCARE_JOURNAL_COMPARISON.md` — TTS vs JBHI vs alternatives.
- `GRAMCARE_SCOPUS_AND_FEE_VERIFICATION.md` — Scopus coverage verified against
  the official Elsevier source list; fees verified against journal author pages.
- `GRAMCARE_EVIDENCE_REGISTER.md` — every claim, its source, its status.

Primary sources consulted: official Elsevier Scopus source title list (Oct 2026);
technologyandsociety.org TTS author information; embs.org JBHI prepare-and-submit,
open-access, editorial-policy and FAQ pages; Crossref API; arXiv API.

Repository verified at commit `bd2f48d`: 245 tests collected and passed; 21
module packages; 144 routed endpoints; 33/33 live demo-path checks.

Still to do in Phase 1: full systematic literature review (25-40 works across
the ten topic areas; a CRDT search is mandatory). Read ContinuityBench
(arXiv 2607.15899) before any novelty claim about AI failover.

## 2026-11-20 — Experiment G Phase 2: coverage, PostgreSQL, closure

**Manuscript: still NOT MODIFIED.** Rewriting begins in Phase 3.

Closed the nine unprobed path-parameter endpoints, validated on PostgreSQL 15,
completed the regression run, and classified the experiment **B — complete with
documented limitations**.

Five findings new to this experiment, all fixed:
- `GET /ehr/records` — every patient's wallet to any approved doctor, unaudited
- `POST /triage/analyze` — a clinical record writable onto another household's
  family profile
- `GET /sos/track/{token}` — the SMSed emergency link served patient name, GPS
  and the audio recording indefinitely after resolution
- `GET /files/{token}` — no rate limit
- `GET /assist/patient-summary/{id}` — AI clinical summary of any patient with
  no audit row

A sixth, G-12, was **introduced by this experiment's own remediations**: the new
ownership filters select on two unindexed columns, so the emergency-desk poll
became a sequential scan. Found only by the PostgreSQL run. Fixed by migration
`d1f7c3b9e205`, which **still needs applying to production by hand** — Alembic
does not run on deploy here.

Also measured for the first time: the idempotent-sync race under ten concurrent
identical batches on PostgreSQL — exactly 25 rows, duplicate rate 0.0000. That
is the first real evidence behind the project's headline offline-sync claim, and
Experiment A can build on it.

Added `research/experiments/exp_g/`: six reports, two consolidated CSVs
(534 probe rows, 135-endpoint inventory), per-run raw output with SHA, engine
and version records, and six scripts.

Project test suite after all remediations: 245 passed, 0 failed. No regressions.

Remaining limitation: 63 of 135 endpoints — all writes — are unprobed. Every
read path was probed. Nothing has been reproduced by an independent party, which
is why the classification is B and not A.
