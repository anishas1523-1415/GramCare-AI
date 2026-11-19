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
