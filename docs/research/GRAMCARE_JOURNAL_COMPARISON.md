# Journal Comparison — IEEE TTS vs IEEE JBHI vs alternatives

**Compiled:** 19 November 2026. All indexing and fee facts carry their source;
see `GRAMCARE_SCOPUS_AND_FEE_VERIFICATION.md` for the verification ledger.

**Recommendation: IEEE Transactions on Technology and Society, at 10 pages, as a
Traditional (subscription) submission. Mandatory cost ₹0.**

The budget makes this decision, and the scope argument happens to agree with it.

---

## 1. Side-by-side

| | **IEEE TTS** | **IEEE JBHI** |
|---|---|---|
| Full title | IEEE Transactions on Technology and Society | IEEE Journal of Biomedical and Health Informatics |
| eISSN / ISSN | 2637-6415 (online only) | 2168-2208 / 2168-2194 |
| Publisher | IEEE | IEEE |
| **Scopus status** | **Active**, 2020–2026 | **Active**, 2013–2026 |
| Scopus ASJC | **2201 Engineering (misc.) — and nothing else** | 3605 Health Information Mgmt; 2718 Health Informatics; 2208 EEE; 1706 CS Applications |
| Medline / PubMed | No | **Yes, Medline-sourced** |
| Page limit | **10** (hard cap 20) | 14 regular / 16 review, **incl. supplementary** |
| **Free pages** | **10** | **8** |
| Overlength | $200/page, pages 11–20 | **$250/page for 9–10; $350/page for 11+** |
| Charges negotiable? | overlength applies only if you exceed 10 | **"not negotiable or voluntary"** |
| **Mandatory cost, 10-page paper** | **$0 → ₹0** | **$500 → ₹47,500** |
| OA APC (avoidable) | $2,800 | $2,800 |
| Traditional option | Yes (hybrid) | Yes (hybrid), APC explicitly waived |
| Reviewers | not stated | min. 3 regular, 5 review |
| Review model | anonymous; detail not stated | anonymous both ways |
| ORCID | not stated | **required for all authors** |
| IRB statement | not stated | **required with approval reference number** where human subjects involved |
| Preprint policy | **not stated — UNVERIFIED** | **"NOT ... any form of online publication" — your Zenodo DOI is at risk** |
| Manuscript format | **`.DOC` template required; LaTeX NOT accepted** | not stated |
| Portal | `ieee.atyponrex.com/journal/TTS` (site also mentions Manuscript Central) | `ieee.atyponrex.com/journal/jbhi-embs` (policy/FAQ say ScholarOne only) |
| Frequency | quarterly, online only | monthly |

---

## 2. Scope fit — IEEE TTS

**Verdict: good fit, but only if the paper is reframed. As currently written, it
is a poor fit.**

TTS "publishes research papers on the interactions among technology, science, and
society," and names among its topics **health and safety**, **social effects of
emerging technologies and innovations**, **regulation and public policy**, and
**technology and the future of work**. Its sole Scopus category is general
engineering — Scopus does not classify it as a health venue, and its readership
is not biomedical informaticians.

**Why GramCare fits, when framed correctly.** The strongest thing about this work
is not the FastAPI service. It is the argument embedded in Section I-B: mainstream
telemedicine assumes constant connectivity, English literacy and one phone per
patient, and therefore treats a village clinic as a degraded version of an urban
user rather than a different context. That is a technology-and-society thesis.
The system is the instrument that tests it. Three results are directly on TTS's
topic list:

1. **Offline-first design as an equity intervention.** Measured degradation under
   intermittent connectivity, with an explicit argument about who is excluded when
   software assumes a network.
2. **The multi-tenant isolation failures.** A health platform that had RBAC,
   bcrypt, JWT sessions and rate limiting, and still leaked every active
   emergency — patient name, live GPS, voice recording — to any registered
   hospital account, and every unfulfilled prescription to any pharmacist. That is
   a finding about how health software fails people, which is TTS's subject
   matter exactly. Including the before/after and how the tests that caught it
   were constructed makes it a contribution other builders can reuse.
3. **Honest failure as a design stance.** The AI layer refuses to fabricate a
   result when no provider can answer, and reports why. In a clinical-adjacent
   context that is an ethics-of-AI position with measurable consequences, and
   "Ethics of AI" sits on the topic list.

**Why it does not fit as written.** The current manuscript is an architecture
paper. TTS reviewers will not reward a four-layer diagram or a module inventory.
Everything in Sections IV and VI has to compress to make room for the societal
argument and the measurements that support it.

**Risks**
- Only one Scopus category, general engineering — a paper that reads as health
  informatics may be desk-rejected as out of scope.
- The 10-page cap is tight. It is also the thing keeping the cost at zero.
- `.DOC` only. Plan the figures and tables around Word from the start.
- Quarterly publication, so the review cycle is likely slower than JBHI's.

---

## 3. Scope fit — IEEE JBHI

**Verdict: better subject fit, and financially impossible inside ₹10,000.**

JBHI "publishes original papers describing recent advances in the field of
biomedical and health informatics where information and communication
technologies intersect with health, healthcare, life sciences and biomedicine."
Its listed sections include Clinical Informatics, Public Health Informatics,
Artificial Intelligence, Sensor Informatics, Patient Safety, Learning Health
Systems and Ethics of AI and Informatics. GramCare touches most of those.

**Four reasons it is the wrong target now:**

1. **Money.** Mandatory charges begin at page 9. One page past the free allowance
   costs ₹23,750 — more than twice the entire publication budget. A realistic
   12-page paper costs ₹114,000. There is no configuration above 8 pages that
   fits ₹10,000, and 8 pages including supplementary material cannot carry seven
   experiments.
2. **The preprint.** JBHI's editorial policy disqualifies work that has appeared
   in "any form of online publication." A Zenodo deposit with its own DOI is
   exposed to that wording, there is no stated carve-out, and your brief
   correctly forbids concealing it. This needs a written answer from the
   editorial office before JBHI is even a candidate.
3. **Evidence expectations.** JBHI expects clinical or algorithmic contribution
   with quantitative evaluation. It discontinued Communications articles, its
   Human Factors section requires "formal usability testing" for interventions,
   and it needs IRB approval numbers for human-subject work. GramCare has no
   clinical validation and no ethics approval — both correctly disclosed. A
   system paper without either will struggle against reviewers who see three to
   five referees per submission.
4. **No validated AI.** The triage engine's clinical accuracy is unmeasured. At a
   biomedical-informatics journal that is the first question asked.

**When JBHI becomes right.** After a supervised pilot with ethics approval and a
clinician-adjudicated triage validation — the Future Work the paper already
names. That is the next paper, not this one, and by then the page charges will be
worth paying from a funded budget.

---

## 4. Alternatives considered

Indexing and fees below are **UNVERIFIED** — they were not checked against the
official Scopus list or the journals' own fee pages in this pass. Verify before
acting on any of them. They are listed so the decision is informed, not to
recommend a switch.

| Venue | Why it might fit | Why it is not recommended now |
|---|---|---|
| **IEEE Access** | Broad scope, fast, accepts system papers, IEEE-branded, Scopus-indexed | **Fully gold open access — APC ~$1,995+.** Exceeds the budget by an order of magnitude. Ruled out by your "no compulsory gold OA" condition. |
| **IEEE Open Journal of Engineering in Medicine and Biology** | Health-adjacent, IEEE | Fully open access, APC-funded. Same problem. |
| **IEEE Transactions on Computational Social Systems** | Society-facing, hybrid | Scope leans social-network/computational-social-science, not health delivery. Weaker fit than TTS. |
| **ACM Journal on Computing and Sustainable Societies / ICTD venues** | Excellent fit for the rural-ICT argument | Not IEEE, which is your stated requirement. Worth knowing as a fallback. |
| *Journal of Medical Internet Research* | Strong digital-health fit | Not IEEE; gold OA with substantial APC. |

**Conclusion: the primary target you chose is the right one, for a reason you may
not have had in mind — it is the only IEEE option that costs ₹0 and accepts the
kind of contribution this work can honestly claim.** Treat JBHI as the venue for
the post-pilot paper.

---

## 5. Decision gates before submission

Do not open the submission portal until all of these are true.

| Gate | Status today |
|---|---|
| Experiments A–G executed, with results tables populated from real runs | **Not met** |
| Reference [3] resolved or removed; all references rebuilt with verified DOIs | **Not met** |
| 1:11,082 attribution corrected | **Not met** |
| Idempotency claim narrowed to `EHRRecord` | **Not met** |
| Verification numbers re-run at one named commit | **Not met** — 245/245 available, needs stating with its SHA |
| Literature review of 25–40 works with a documented protocol | **Not met** |
| Manuscript reframed around the societal thesis and fitted to 10 pages | **Not met** |
| TTS preprint policy confirmed in writing by the editorial office | **Not met** — ask now, it is a one-email dependency |
| Which portal is live for TTS confirmed | **Not met** |
| Supervisor (Mr. G. S. Pugalendhi) and all three co-authors have read and approved the revised manuscript | **Not met — and this is non-negotiable** |
| Similarity check run through SKCET's institutional licence | **Not met** |
| ORCIDs obtained for all four authors | **Not met** |
| Author block fixed: affiliations and emails, corresponding author designated | **Not met** |
