# GramCare AI pitch deck: slide-by-slide draft (12 slides)

> **[Brackets]** = fill in or verify. Health panels include doctors: be precise, show the safety
> thinking, and never claim diagnosis or clinical accuracy without evidence.

## 1. Title
**GramCare AI: one record for rural care.** AI help that works on weak connections. [Founder] · [date]

## 2. Problem
- Rural care is fragmented: clinic, pharmacy, lab and hospital don't share records.
- Weak mobile data breaks most health apps exactly where they're needed.
- Emergencies rely on phone calls; minutes are lost. [one sourced statistic on the rural doctor shortfall]
*Notes:* a real story from a village or PHC you've visited. [Visit one before presenting.]

## 3. Solution
One platform, seven roles: patient · doctor · pharmacist · lab · hospital · health worker · authority.
Diagram: the prescription moves from doctor → pharmacy → patient record; the lab report attaches to the same record.

## 4. Demo (video, 90 seconds)
Health worker registers a patient → AI triage (Tamil voice) → doctor reviews and prescribes by video →
pharmacy receives the prescription → SOS routes to the nearest hospital.
*Notes:* wake the free-tier servers first, or record the video in advance.

## 5. Built for the village
- Triage keeps working **offline** (on-device fallback).
- English and **Tamil**; voice input.
- Bluetooth vitals (pulse oximeter, thermometer, heart rate).

## 6. Safety and compliance (health panels will ask)
- AI is **decision support**; a clinician decides. Failures say so honestly (no fake answers).
- Regulatory path: CDSCO medical-device software guidance (July 2026) → classification [in progress];
  telemedicine practice guidelines; DPDP Act for health data.
- ABDM / FHIR interoperability: [Sandbox status].
- Clinical validation plan: [partner, protocol, ethics approval].

## 7. Market
Who pays, bottom-up: [N PHCs / clinics / pharmacies in the pilot district] × [price] → Tamil Nadu → India.
Plus programme funding (CSR, government digital health). [sources]

## 8. Business model
| Customer | What they pay for | Price |
|---|---|---|
| Clinics / hospitals | Records, teleconsult, SOS routing | [₹/month per facility] |
| Pharmacies / labs | Orders, inventory, reports | [₹/month] |
| CSR / government | Deployment across a block or district | [per deployment] |
| ABDM DHIS | Incentives per linked record | [verify current terms] |

## 9. Traction
**True today:** working platform (web + 3 Android apps), CI and tests passing, deployed.
**Pilot:** [partner, patients served, consultations, SOS response times]. Empty until real.

## 10. Competition
Telemedicine apps (urban, single-role), hospital management systems (one facility), government apps
(eSanjeevani and others; **position GramCare as complementary**, e.g. integrating via ABDM).
GramCare: **multi-role shared record + offline triage + emergency routing, for rural settings.**

## 11. Team and advisors
[Founder]: built the full platform. **Needed: a clinical advisor (a doctor in rural practice)**: most
health panels expect one. [Regulatory advisor], [public-health mentor].

## 12. The ask
[₹ amount] for: regulatory work, ABDM integration and audit, always-on hosting, a supervised pilot,
a clinical advisor. **Milestones:** [regulatory class confirmed, ABDM M1 live, pilot with N patients].

### Before presenting
- [ ] Get a clinical advisor and a pilot partner (PHC, NGO or hospital).
- [ ] Regulatory scoping note (CDSCO class) from a consultant.
- [ ] Source every statistic (Ministry of Health rural health statistics, NHA ABDM figures).
- [ ] Record the 90-second demo.
- [ ] Move emergency features off free hosting before any real pilot.
