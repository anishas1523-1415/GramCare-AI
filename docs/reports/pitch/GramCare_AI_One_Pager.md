# GramCare AI: one-page summary (DRAFT)

> For health incubators (Villgro, HTIC, PSG-STEP), StartupTN/TANSEED and SISFS. **[Brackets]** = fill in
> or verify. **No invented numbers.** Health funders check claims closely, so cite every statistic and
> never imply clinical validation that hasn't happened.

**GramCare AI: one shared health record for rural care, with AI help that works on weak connections.**
[Tamil Nadu] · [Company, Pvt Ltd, date] · [DPIIT no.] · [StartupTN ID] · Founder: [Name], [background] · [contact]

### Problem
In rural India, a patient's care is split across a clinic, a pharmacy, a lab and a distant hospital that
don't share information. Mobile data is patchy, doctors are few, and emergencies depend on someone
making phone calls. [Add 1–2 sourced facts, e.g. doctor and specialist shortfalls at rural health
facilities from the Ministry of Health's *Health Dynamics of India / Rural Health Statistics*, latest
edition, with the page cited.]

### Solution
GramCare AI connects **patients, doctors, pharmacists, labs, hospitals, health workers and health
authorities on one record**:
- **AI symptom triage** (text or voice, English and Tamil) that **falls back to an on-device engine**
  when the network or AI service is down. It is decision support only; a clinician decides.
- **Teleconsultation** (video), **e-prescriptions** a pharmacy fulfils directly, lab bookings and reports.
- **SOS** with location and a voice note, routed to the nearest hospital and escalated if unanswered.
- **Health Passport** with **FHIR export** (ready for ABDM integration).
- **Outbreak analytics** for health authorities, from triage patterns.

### Stage (be exact)
- Working platform: FastAPI API, web portals (patient/doctor, pharmacist, lab), three Android apps;
  deployed on free hosting; automated test suite and CI passing.
- **Not yet clinically validated or regulatorily reviewed; not used for real patient care.**
  Next: regulatory scoping (CDSCO medical-device software guidance, July 2026; telemedicine guidelines;
  DPDP Act), ABDM Sandbox integration, and a supervised pilot.
- Pilot: [planned partner: PHC / NGO / hospital, month] → replace with real results once done.

### Who pays (to validate)
[Choose and test with partners] e.g. hospitals and clinic networks (SaaS per facility), pharmacies and
labs (subscription), CSR and government programmes (deployment per block or district), and the
ABDM Digital Health Incentive Scheme for linked records (check current terms).

### Why us / why now
- India is building national digital health infrastructure (ABDM, ABHA, FHIR); GramCare already speaks FHIR.
- Designed for weak connectivity and Tamil from day one.
- [Founder's connection to rural health: a story, a partner doctor or PHC.]

### The ask
[₹ amount] for: regulatory scoping and compliance, ABDM integration and security audit, always-on hosting
for emergencies, a supervised pilot with [partner] (devices, health-worker training), [clinical advisor].
