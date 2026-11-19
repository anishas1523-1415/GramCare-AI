# GramCare AI: funding, grants and free services (researched 2026-11-16)

**Caveat.** These findings come from web research on 2026-11-16. Most sources are aggregators and blogs
with conflicting figures. Confirm every amount, deadline and eligibility rule on the official portal
before applying. Not legal, medical-regulatory or financial advice.

## What GramCare AI is (from this repo)
An AI-assisted rural healthcare platform: patient, doctor, pharmacist, lab, hospital, authority and
health-worker roles; AI symptom triage with an offline fallback; video consultations; e-prescriptions;
FHIR Health Passport; SOS routing; outbreak analytics; English and Tamil. FastAPI + Next.js + Flutter,
deployed on free tiers, CI passing. README status: **pre-release, not clinically or regulatorily
reviewed, not for real patient care.**

## Overall verdict
GramCare AI fits funders **much better** than a typical app: health, rural impact, AI and Tamil Nadu
are all priority themes. But two gates come before any serious money:

1. **A registered company + DPIIT recognition**, the same as for AAROVA. A sole proprietorship is not
   DPIIT-eligible. Most grants and incubators also need Indian founders holding ≥51%.
2. **Regulatory clarity.** CDSCO's final *Medical Device Software* guidance (CDSCO/MD/GD/MDSW/01/2026,
   21 July 2026) covers software with a medical purpose, and lists **AI triage/screening** tools as
   examples. GramCare's symptom triage and clinical decision support are therefore likely to be
   **medical-device software** needing classification (Class A–D) and possibly a licence. Health
   funders will ask about this. Also the **DPDP Act** (health data is sensitive) and **telemedicine
   practice guidelines** for video consultations. **Get a regulatory consultant's view before
   applying**, and position triage as "decision support for clinicians and health workers" only if
   that is how it truly works.

## A. Health-specific government programmes

| Programme | What | Fit | Status found | Notes |
|---|---|---|---|---|
| **ABDM Sandbox** (National Health Authority) | Integrate with Ayushman Bharat: ABHA IDs, FHIR records, consent (milestones M1/M2/M3) | **Very high**: GramCare already has FHIR export. ABDM integration is close to expected for Indian health apps and strengthens every application | Always open; free | Go-live needs NHA review and a security audit (WASA) |
| **Digital Health Incentive Scheme (DHIS)** | Per-record incentives for ABDM-linked records (figures conflict: e.g. ₹20 per ABHA-linked OPD registration, ₹100 per FHIR record; caps disputed) | High, once live on ABDM | A notice reportedly covered Apr–Sep 2026; check renewal | Needs WASA report; contact abdm.incentive@nha.gov.in |
| **BIRAC BIG** (DBT) | Up to **₹50 lakh**, 18 months, equity-free | **Uncertain**: the guide says biomedical devices; software-only health AI may not qualify unless paired with a device (e.g. GramCare's Bluetooth vitals) | 2026 call status conflicting | Company ≤5 years old, in-house R&D or incubation |
| **IndiaAI Mission** challenges | Sector challenges (e.g. CATCH cancer AI: up to ₹50 lakh per solution) and BuildAI grants (up to ₹20 lakh) | High when a health challenge matches | 2026 calls found are closed; watch indiaai.gov.in | Challenge-specific |
| **SISFS / MeitY TIDE 2.0** | Up to ₹20 lakh grant / ~₹7 lakh | **Good**: TIDE targets AI explicitly | See the AAROVA guide; via incubators | Company + DPIIT |

## B. Tamil Nadu
Same as AAROVA: **TANSEED** (₹10 lakh general, **₹15 lakh for rural-impact startups**, which GramCare
may qualify for). 8.0 closed in Jan 2026; watch for 9.0. StartupTN registration, and the **TN LangTech
fund** (Tamil voice triage could fit when it reopens).

## C. Impact investors, foundations, CSR

| Who | What | Fit | Status |
|---|---|---|---|
| **Villgro (MAP-Health)** | Healthcare social-enterprise acceleration + seed (grant-stage average about $74k) | **Very high** | Conflicting (rolling vs closed); check villgro.org |
| **Social Alpha** | Catalytic grants, seed, NIDHI Seed Support | High | Check socialalpha.org |
| **RAFT AI for Transformative Social Impact** (Rao Family Trust) | Up to ₹50 lakh, multi-year possible | High, **but for organisations already deploying AI** | The 2026 deadline (30 Sep) has passed; watch for 2027 |
| **Google AI for Social Good / Google.org** | Grants for AI on social problems | High | Listed as closed |
| **CSR funds** of hospitals, pharma companies and banks | Pilot funding for rural health | High *after* a pilot with a hospital or NGO | Pitch directly, with the company registered and 12A/80G partners |

## D. Health incubators (the route to grants and hospital pilots)
- **IIT Madras HTIC** (Chennai): DBT-funded healthcare technology centre.
- **Tagore Bioincubation Centre** (Chennai), **Sri Sairam Techno Incubator** (Chennai).
- **PSG-STEP** (Coimbatore): PSG also runs a medical college and hospital, a natural pilot partner.
- Outside TN: IIIT-Delhi Horizon HealthTech, IIT Bombay TIH ATMAN healthtech accelerator.

## E. Free credits and services relevant to GramCare
- **AI provider credits:** Claude for Startups was reportedly paused/full in Oct 2026. **AWS Activate**
  credits can pay for Claude on Amazon Bedrock. **Google for Startups Cloud** for Gemini. OpenAI
  startup credits come through accelerators. GramCare's multi-provider AIManager can use all of them.
- **Hosting:** the README says free tiers sleep, which is unacceptable for SOS. Use startup cloud credits
  (AWS/GCP) to pay for always-on hosting.
- **Maps:** OpenStreetMap today; Google Maps Platform credits come with Google for Startups.
- **Razorpay Rize**, GitHub (free), Sentry (free); Firebase is already set up.

## F. What to do, in order
1. Ask a CA about the structure → **Pvt Ltd** → **DPIIT** → **StartupTN**. (One company can hold both
   AAROVA and GramCare as products, but funders and incubators usually prefer one focused company per
   product. Discuss with the CA.)
2. **Regulatory scoping** with a medical-device regulatory consultant (CDSCO class, telemedicine rules, DPDP).
3. **Join the ABDM Sandbox** (free) and build M1 (ABHA). It is a strong credibility signal.
4. Apply to a **health incubator** (HTIC, PSG-STEP) and **Villgro**.
5. **Pilot with a PHC, clinic or NGO** (non-diagnostic use, clinician in the loop), with ethics and consent.
6. Then: TANSEED 9.0 (rural category), SISFS, IndiaAI health challenges, RAFT 2027, CSR.

## Repo notes (from this check)
- `.env` and the Firebase **Admin SDK JSON** are in the project folder but **not tracked by git**
  (verified: not in `git ls-files` or in history). Keep it that way, and rotate the service-account key
  if it was ever shared.
- The README already states the limits honestly (free-tier sleep, debug-signed builds, no clinical
  review). Funders will value that honesty.

## Sources
- [BIRAC BIG user guide](https://birac.nic.in/webcontent/big_user_guide.pdf) · [BIG 2026 (AndPurpose)](https://andpurpose.world/biotechnology-ignition-grant-big-scheme-2026-india/) · [BIG terms (IncubatorPro)](https://theincubatorpro.com/programs/birac-big/)
- [ABDM Sandbox (StartupGrantsIndia)](https://www.startupgrantsindia.com/providers/national-health-authority/abdm-sandbox) · [DHIS](https://www.startupgrantsindia.com/providers/national-health-authority/digital-health-incentive-scheme-dhis) · [ABDM M1–M3 guide](https://verticomply.com/blog/abdm-m1-m2-m3-integration-guide)
- [IndiaAI healthcare (PIB)](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2247769&reg=3&lang=1) · [BuildAI TechPitchSprint](https://indiaai.gov.in/article/indiaai-mission-and-itel-foundation-announce-buildai-techpitchsprint-for-early-stage-ai-startups) · [RAFT grant](https://andpurpose.world/raft-ai-transformative-social-impact-grant-2026/)
- [Villgro MAP-Health](https://www.startupgrantsindia.com/map-health) · [Social Alpha](https://theincubatorpro.com/programs/social-alpha/) · [Health incubators list](https://www.startupgrantsindia.com/incubators/sector/healthtech) · [HTIC](https://www.indiascienceandtechnology.gov.in/technologyincubators/healthcare-technology-innovation-centre-htic)
- [CDSCO medical device software guidance (Emergo)](https://www.emergobyul.com/news/india-cdsco-finalizes-guidance-medical-device-software) · [CDSCO MDSW 2026 (Corpseed)](https://www.corpseed.com/news/cdsco-medical-device-software-guidance-2026) · [Cyril Amarchand blog](https://corporate.cyrilamarchandblogs.com/2026/01/medical-device-as-software-has-cdsco-guidance-changed-the-rules/)
- General schemes (DPIIT, SISFS, TANSEED, cloud credits): see AAROVA's `docs/FUNDING_AND_FREE_SERVICES.md`.
