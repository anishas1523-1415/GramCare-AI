# GramCare AI — Master Implementation Roadmap

**Prepared:** July 3, 2026 · **Scope:** Full monorepo + Tamil planning discussion (source of truth) + Volume 5 blueprint + previous technical audit + all fixes applied since.
**Rule observed (initial version):** No code was modified. This document is analysis and planning only.

---

## PROGRESS UPDATE — July 3, 2026 (implementation session)

| Phase | Status | Evidence |
|---|---|---|
| P0 Repo unification | ✅ **DONE** | `apps/suites/`, `AI/`, `ci-cd.yml`, Supabase remnants, `.env.local`, dual seeds, stray `.db` files all removed; Python 3.11 aligned; README corrected |
| P1 Contract & data model | ✅ **DONE** | 5 new entities + EHR/vitals redesign + family-scoping columns; migration `7a1c4e9f2b30` runs from scratch; `/ehr/sync`, `/ehr/records`, `/doctors` live; TriageLog persisted; rate limiting on auth/triage/OCR; migrations run on container/render start |
| P2 Family profiles | ✅ **DONE** | Family CRUD API (owner-scoped) + web page wired + web profile switcher + mobile profile-selection screen (avatar buttons) with offline cache + profile scoping through triage/EHR/booking/vitals/SOS |
| P3 Wallet + OCR + sync | ✅ **DONE** | Idempotent batched `/ehr/sync` (client UUIDs); encrypted Hive + keystore token; camera→OCR→confirm→save flow; per-member color-coded wallet; web prescriptions page |
| P4 Doctors + payments | ✅ **DONE** | Doctor directory/profiles/slots; Payment state machine (CREATED→PAID→CONSUMED→REFUNDED); server-enforced pay-before-book; auto-refund + slot release on cancel; web booking rewritten (no more DOCTOR_ID=2) |
| P5 Pharmacy intelligence | ✅ **DONE** | Pharmacy entity + geo registration; nearby search w/ green-red + per-shop generic substitutes; set/decrement/delta stock modes; fulfill decrements stock; expiry alerts; invoice-OCR entry; patient search UI (web + mobile) |
| Verification | ✅ 27/27 backend tests pass (auth, family, doctors, sync idempotency, triage persistence, payment/booking invariants, pharmacy lifecycle, migration-from-scratch); react_dashboard `tsc` clean; Node `--check` clean; seed idempotent | |
| P6 Emergency SOS | ✅ **DONE** | EmergencyContact model+API, migration `9b2d5f7c1a44`; GPS capture + hold-3s guard + SMS fallback (mobile); voice note on SOS; nearest-hospital assignment + escalation watchdog; responder-room-scoped broadcasts; HOSPITAL desk role can respond |
| P7 Tamil + voice | ✅ **DONE** | Tamil-first LocaleService (en/ta, persisted, toggle); mic-first voice symptom input (ta-IN/en-IN); TTS playback on wallet records + triage results; per-module color themes |
| P8 AI depth | ✅ **DONE** | Triage enriched with causes/first-aid/side-effects/treatments/untreated-outcome/specialist/language; auto-SOS prompt on CRITICAL (mobile) + emergency banner (web); AI Doctor Assistant pre-consult summary (rules + optional Gemini); Community Health Intelligence clusters + overview + web page |
| P9 Hardening | ✅ **DONE** | Non-root backend image + HEALTHCHECK; runtime/dev dependency split; .dockerignore everywhere; Postgres port unexposed; TURN config via env; new P6/P8 test suite added |
| P10 Deployment | ✅ Config complete | render.yaml covers all 4 services with production env vars; deployment checklist + owner-required items in final report |
| ⚠ Outstanding | See "Remaining issues" in the final report: P6/P8 tests written but not yet executed (sandbox VM failed mid-session — run `pytest` once locally), JWT-in-localStorage (web), no refresh tokens, web portal untranslated | |

---

## 1. Executive Summary

Since the July 3 technical audit, a substantial hardening pass has landed (currently **uncommitted** in the working tree). Verified against the current code, the following previously-critical items are now **fixed**: Socket.io auth gating with room-membership checks, JWT secret alignment between FastAPI and Node, pharmacy endpoint auth + the missing `/queue` and `/fulfill` routes, payment endpoint auth + ownership checks + hardened mock signature, vitals/SOS auth + validation + rate limiting, loud/fail-fast SQLite fallback, the web portal login/registration page, the react_dashboard login + corrected API contract + real types, the prescription dual-write fix (doctor prescriptions now reach the pharmacy queue), the mobile Hive sync crash, the mobile login endpoint, the broken widget test, docker-compose secrets/healthchecks, and Node process-level error handlers.

**What remains** is the gap between a *secured demo skeleton* and the product the Tamil planning document actually describes. The three defining pillars of GramCare AI — **(a)** family-centric offline-first Health Wallet, **(b)** voice/image/regional-language accessibility for rural low-literacy users, and **(c)** the pharmacy/emergency/consultation intelligence loop — are still 0–30% implemented. Alignment with the planning MVP is now roughly **35–40%** (up from 20–30%), almost entirely from infrastructure fixes rather than feature completion.

Estimated remaining effort to a production-grade pilot: **10 phases, ~14–18 working weeks** for a small team (see §7).

---

## 2. Feature Matrix vs. the Tamil Planning Document

Legend: ✅ Fully implemented · 🟡 Partial · ❌ Missing · ⚠️ Incorrect/broken implementation

### 2.1 Foundation (Planning Phase 1)

| Feature (planning source) | Status | Reality in code |
|---|---|---|
| Secure login/registration (all apps) | 🟡 | Backend solid (validated schemas, JWT). Web portal ✅. Pharmacy dashboard ✅. Mobile 🟡 — token in plain `shared_preferences`, no registration screen. |
| Role-based access (PATIENT/DOCTOR/PHARMACIST/ADMIN) | 🟡 | `require_role()` now used in pharmacy/EHR routers; appointments/emergency still use ad-hoc inline role checks. No HOSPITAL/LAB/HEALTH_DEPT roles exist (planning requires them). |
| Family profile selection — "one box per member", photo-as-button, applies to ALL features | ❌/⚠️ | `FamilyProfile` model + schemas exist, but **no backend router exposes any family CRUD endpoint**. Web `family/page.tsx` is 100% mocked (in-memory, lost on refresh). Mobile has no concept of profiles. Nothing else (triage, records, booking) is profile-scoped. |
| Offline storage + sync queue + conflict resolution | ⚠️ | Mobile Hive queue exists and the crash is fixed, but it posts to **`POST /ehr/sync`, which does not exist on the backend** — every sync attempt 404s and records stay queued forever. No conflict resolution, no timestamps/versioning strategy. |

### 2.2 AI Health Assistant / Symptom Checker (patient mobile+web)

| Feature | Status | Reality |
|---|---|---|
| Text symptom input | ✅ | Web + mobile, hits Gemini-backed `/triage/analyze`. |
| Regional-language response (auto-detect, reply in user's language) | 🟡 | Prompt instructs Gemini to do this; **UI itself has zero localization** (no Tamil strings, no `flutter_localizations`, no next-intl). |
| Voice symptom input (mic-first UI, planning's headline feature) | ❌ | No speech package, no mic UI anywhere. |
| Image symptom input (optional photo → analysis) | ❌ | No upload UI. (Gemini Vision OCR endpoint exists server-side but nothing calls it.) |
| Seriousness %, problem, causes, home remedies, first aid, duration, untreated outcome, side effects, treatments, specialist suggestion | 🟡 | Severity %, condition, remedies, recommendation, recovery time, explanation ✅. **Causes, first aid, untreated-outcome, side effects, treatment options, specialist-type referral missing** from the prompt/response schema. |
| Risk tiers Low/Moderate/High/Critical with auto-SOS on Critical | 🟡/⚠️ | Web maps score→tier client-side for display only; no auto-SOS trigger on Critical anywhere. |
| Explainable AI + confidence | ✅ | Present in schema and prompt. |
| Empathetic tone / mindset-aware chat | ❌ | Single-shot request/response; no conversational chat flow. |
| Triage results persisted (needed by AI Doctor Assistant + Community Health Intelligence) | ⚠️ | `TriageLog` model exists but **`/triage/analyze` never writes to it** — every analysis is discarded. |
| `/triage/analyze` + `/ocr` abuse protection | ⚠️ | Both intentionally unauthenticated (guest checker) but have **no rate limiting** — an open Gemini-cost/spam vector. |

### 2.3 Family Health Wallet / EHR

| Feature | Status | Reality |
|---|---|---|
| Per-member records, color-coded types, voice playback | ❌ | Mobile shows a flat single list; no member scoping, no colors by type, no TTS. |
| Doctor-typed prescription auto-saved to patient wallet | 🟡 | `issue_prescription` now writes structured `Prescription` + readable `EHRRecord`; mobile wallet read path works. **No patient-facing web view of prescriptions.** |
| OCR scan of outside prescriptions/lab reports (camera → AI → structured record) | ⚠️ | Backend `/triage/ocr` exists (Gemini Vision); **no camera flow or upload UI in any client**; OCR output is never persisted as an EHR record. |
| Offline SQLite + cloud sync | ⚠️ | See §2.1 — sync endpoint missing server-side. |
| Encrypted local storage | ❌ | Hive box unencrypted; auth token in `shared_preferences` instead of `flutter_secure_storage`. |

### 2.4 Doctor / Hospital Suite

| Feature | Status | Reality |
|---|---|---|
| Doctor dashboard (queue, SOS feed) | ✅ | Real API-backed queue + active SOS + respond/complete actions, uses real logged-in doctor id. |
| Digital prescription writing | ✅ | Works end-to-end into the pharmacy queue. |
| AI Doctor Assistant (pre-consult summary from timestamped records, active-medicines detection, risk stratification) | ❌ | Nothing exists. Only the raw client-supplied `triage_summary` string rides on the appointment. |
| Doctor discovery (specialty, experience, fee, schedule) | ⚠️ | No `GET /doctors` endpoint; booking page hardcodes `DOCTOR_ID = 2`. `doctor/directory/page.tsx` calls **`/ehr/records`, an endpoint that does not exist** → the page always fails. |
| Doctor availability calendar / slot booking | ❌ | Booking accepts any datetime; no schedule model. |
| Hospital web portal + central emergency desk (SOS routing, escalation to next hospital, "Help En Route" status, accidental-press guard) | ❌ | No hospital entity, portal, or escalation logic. SOS goes to all doctors globally. |
| WebRTC consultation | 🟡 | Signaling now authenticated and room-scoped; consultation page passes JWT ✅. **No TURN server** (stub returns STUN only) — calls will fail on rural symmetric-NAT networks, precisely the target environment. No adaptive bandwidth switching (video→audio→text). |
| Real-time multilingual translation in consults | ❌ | Not present (planning marked it an enhancement; acceptable to defer). |

### 2.5 Pharmacy Suite

| Feature | Status | Reality |
|---|---|---|
| Prescription fulfillment queue | ✅ | Now functional end-to-end with auth. |
| Stock view + shipment update | 🟡 | Works, but no rural-friendly entry (manual count set / tap-to-decrement / invoice scan / voice entry — all planning-mandated). `update_stock` only supports delta adds. |
| Stock auto-decrement on fulfillment | ❌ | Fulfilling a prescription does not touch inventory counts. |
| GPS nearby-pharmacy search (green/red availability) for patients | ❌ | No pharmacy lat/lng columns, no search endpoint, no patient-facing UI in any app. |
| Generic substitutes, interaction alerts, expiry alerts, pre-order, Jan Aushadhi, batch recall | ❌ | None. Schema lacks `expiry_date`, generic-group, and composition fields, so these are structurally unsupported. |
| Prescription scanner + medicine info assistant | ❌ | See OCR above — backend capability orphaned. |

### 2.6 Emergency SOS

| Feature | Status | Reality |
|---|---|---|
| SOS persistence + doctor respond/resolve lifecycle | ✅ | FastAPI `/sos/*` with role checks. |
| Real-time broadcast + FCM push | 🟡 | Node path authenticated, validated, rate-limited ✅. But **no client ever subscribes to the `doctors_global` FCM topic**, and broadcast is global rather than responder-scoped. |
| GPS location, hold-to-activate guard, voice description → AI summary, family-contact SMS, hospital escalation chain | ❌/⚠️ | Mobile SOS sends hardcoded `'Rural Clinic Alpha'`, hardcoded `patient_id: '1'`, fire-and-forget. Its payload (`location`) **doesn't match FastAPI's schema** (`location_text/lat/lng`) so location is silently dropped; it also requires PATIENT auth the hardcoded flow doesn't guarantee. No geolocator package, no press guard, no SMS fallback, no escalation. |

### 2.7 Remaining patient modules

| Feature | Status |
|---|---|
| Payment before call, UPI-primary (Razorpay) | 🟡 Auth + ownership + verify ✅, but **booking is not server-side linked to a verified payment** (client calls book after verify; server never checks), and no refund/escrow-style hold ("money returns if doctor doesn't attend" was explicitly required). |
| Medication reminders (from prescriptions, notifications, refill reorder) | ⚠️ 100% static mock UI in mobile; no notification scheduling package. |
| Health Vitals Tracker (sensors/smartwatch, graphs, goals, doctor visibility) | ⚠️ Mobile screen generates `Random()` numbers; posts to authenticated `/ehr/vitals` ✅ but nothing reads/graphs them; no sensor integration. |
| Lab test booking & reports; separate Lab web portal | ❌ Nothing exists. |
| Community Health Intelligence + health-dept dashboard | ❌ Nothing exists (blocked on TriageLog persistence, §2.2). |
| Per-module themed animations/transitions, "stunning" distinct UI per feature | ❌ All screens share one generic glass/neumorphic style. |
| PWA/web app for patients assisted by government officers | 🟡 web_portal is responsive Next.js but has no patient records/pharmacy views and no assisted-access mode. |
| On hold per planning (correctly not built): Wellness/Diet, Mental Health, Insurance, IoT wearables | ✅ deferred |

**Score: of the 9 planning MVP pillars (auth, family profiles, symptom checker, consultation, wallet, digital prescriptions, pharmacy search, SOS, offline), 3 are genuinely end-to-end (auth, consultation-with-prescription, prescription→pharmacy queue); 4 are partial; 2 (family profiles, pharmacy search) are absent.**

---

## 3. Architecture Consistency Review

1. **The dual-product-line split is still unresolved — the #1 structural issue.** `.github/workflows/ci-cd.yml` still builds the three `apps/suites/*` projects (Next 14/React 18) in parallel with `main.yml` building the documented five services. `AI/apps/patient_app/...` is a third, empty ghost tree. Nothing declares which tree is canonical.
2. **Env-var plumbing for frontends is broken in Docker.** `VITE_*` and `NEXT_PUBLIC_*` variables are **build-time**, but docker-compose passes them as runtime `environment:` — they have no effect on the already-built bundles. Worse, the values themselves omit the `/api/v1` suffix (`VITE_API_URL=http://localhost:8000`), so if they *were* honored, every request would 404. Works today only by accident of the in-code fallbacks.
3. **Dead Supabase auth remnants likely break the web_portal build.** `src/utils/supabase/{client,server,middleware}.ts` import `@supabase/ssr`, which is not in `package.json`. `next build` type-checks all files in the tsconfig include set, so this should fail CI — must be verified and the files removed (plus the stray `.env.local` Supabase keys).
4. **Python version disagreement persists:** Dockerfile 3.10, main.yml 3.11, render.yaml 3.11.0, ci-cd.yml 3.10.
5. **Migration strategy is mixed:** Alembic migrations exist, but `seed.py` calls `Base.metadata.create_all()`, and nothing in the Docker/render startup runs `alembic upgrade head`. Two seed scripts (`seed.py`, `seed_data.py`) still coexist.
6. **Contract drift remains the dominant defect class.** Confirmed live mismatches: mobile `POST /ehr/sync` (no such route), web `GET /ehr/records` (no such route), mobile SOS payload shape, hardcoded `DOCTOR_ID=2`. There is no shared API contract (OpenAPI-generated clients or even a shared types package).
7. **Data-model debt:** `EHRRecord.patient_id` and `PharmacyItem.pharmacy_id` are strings with no FK; `EHRRecord.content` is an unstructured blob; no `Pharmacy` entity (only items with a string tag); no doctor-profile entity (specialty/fee/schedule); no hospital/lab entities; `TriageLog` unused.
8. **Security posture (improved, remaining):** JWT in `localStorage` (XSS exposure) on both web apps; no FastAPI-side rate limiting (login/register brute-forceable; Gemini endpoints open); Dockerfile runs as root, no HEALTHCHECK directive, test deps in prod image; committed live-looking Gemini key in local `.env` should be rotated; Postgres port still host-exposed; refresh-token/rotation absent (7-day static access token).
9. **Testing:** the triage test still accepts HTTP 500 as passing; zero tests for auth, appointments, SOS, payments, pharmacy queue; Node service has no test framework; no frontend tests.

---

## 4. Consolidated Defect Register (current tree)

### Critical (breaks a planning-mandated flow or safety)
| # | Defect | Location |
|---|---|---|
| C1 | Mobile offline sync targets nonexistent `POST /ehr/sync` — offline-first pillar silently dead | `mobile_app/lib/services/sync_service.dart` ↔ `modules/ehr_sync/router.py` |
| C2 | Mobile SOS: payload shape mismatch, hardcoded patient/location, no GPS, no error handling — life-safety feature non-functional in real use | `mobile_app/lib/screens/dashboard_screen.dart` |
| C3 | No family-profile API despite model/schema existing; web page mocked — Phase-1 planning dependency for everything | backend (missing router), `web_portal/src/app/family/page.tsx` |
| C4 | `doctor/directory` calls nonexistent `/ehr/records` — page always errors | `web_portal/src/app/doctor/directory/page.tsx` |
| C5 | Booking hardcodes `DOCTOR_ID=2`; no doctors listing/schedule API — multi-doctor reality broken | `web_portal/src/app/book/page.tsx`, backend |
| C6 | Payment verification not linked server-side to appointment creation — bookable without paying by calling the API directly | `payments/router.py` + `appointments/router.py` |
| C7 | Dual CI / `apps/suites` split still live | `.github/workflows/ci-cd.yml` |
| C8 | Probable web_portal build failure from orphaned Supabase imports (verify, then delete) | `web_portal/src/utils/supabase/*` |

### High
H1 Triage results never persisted (`TriageLog` unused) — blocks AI Doctor Assistant + Community Health Intelligence. · H2 No rate limiting on `/triage/*` (Gemini cost abuse) or `/auth/*` (brute force). · H3 No TURN server for WebRTC — rural NAT failure. · H4 Docker/env plumbing for frontend base URLs (build-args needed). · H5 Unencrypted Hive + token in shared_preferences. · H6 FCM `doctors_global` topic has no subscriber. · H7 Fulfillment doesn't decrement stock. · H8 No pharmacy entity/geo columns/expiry — pharmacy intelligence structurally unsupported. · H9 Alembic not run on startup; `create_all` bypass; dual seed scripts. · H10 Global SOS broadcast unscoped (no responder room).

### Medium
M1 JWT in localStorage (both web apps). · M2 Python version drift (3.10 vs 3.11). · M3 Test suite accepts 500; no coverage of new endpoints; Node untested. · M4 `EHRRecord` string-typed pseudo-FKs, blob content. · M5 Wallet read path returns `doctor_name` under key `doctor_id` (`ehr_sync` read model). · M6 No pagination on list endpoints. · M7 Static reminders/vitals mocks presented as real. · M8 Dockerfile root user/no healthcheck/test deps in image; Postgres port exposed. · M9 Rotate the committed Gemini key. · M10 `.env.local` Supabase creds should be removed with C8.

### Low
Default Next/Vite boilerplate assets and READMEs; `alert()`-based errors and missing aria-labels in web portal; copy-pasted neumorphic decorations in Flutter (needs a shared widget); stock `flutter_lints`; `print`/`debugPrint` in production paths.

---

## 5. Optimal Implementation Order (dependency-derived)

The planning document's own dependency graph (Volume 5 §21.3) still holds. Adjusted for what's already built, the critical path is:

```
P0 Repo unification & build truth  ──►  P1 Contract & data-model foundation
        │                                        │
        ▼                                        ▼
P2 Family profiles (backend→web→mobile)  ──►  P3 Health Wallet + OCR + offline sync
        │                                        │
        ▼                                        ▼
P4 Doctor discovery/schedule + payment-linked booking
        │
        ▼
P5 Pharmacy intelligence (entity, geo search, stock lifecycle)
        │
        ▼
P6 Emergency SOS end-to-end (GPS, guard, FCM, escalation)
        │
        ▼
P7 Accessibility: Tamil i18n + voice in/out + themed UI
        │
        ▼
P8 AI depth: enriched triage, AI Doctor Assistant, TriageLog analytics
        │
        ▼
P9 Hardening, testing, observability  ──►  P10 Pilot deployment
```

Rationale: P0/P1 first because every later fix risks landing in a deleted tree or against a drifting contract. Family profiles (P2) precede the Wallet because the planning doc makes *every* feature member-scoped. Pharmacy (P5) needs prescriptions (done) + geo model (P1). SOS (P6) needs hospital/responder modeling from P1 and FCM wiring. Accessibility (P7) is deliberately before AI depth (P8): the planning discussion treats voice + Tamil as the product's identity, and UI text churn in P2–P6 would otherwise force re-translation.

---

## 6. Implementation Phases — Detail

### Phase 0 — Repository Unification & Build Truth (complexity: LOW, ~2–3 days)
**Goal:** one canonical product line, green builds, committed baseline.
**Work:** commit the current uncommitted hardening pass first (it is the new baseline); decide Flutter `apps/mobile_app` as canonical patient client (README + maturity support this); delete `apps/suites/` and `AI/`, delete `ci-cd.yml`; verify/remove Supabase dead files (C8) + `.env.local`; align Python to 3.11 in Dockerfile; consolidate seed scripts into one; rotate Gemini key.
**Modules:** repo root, `.github/workflows`, `web_portal`, `backend_service`.
**Expected files:** ~10 deletions/edits + one large tree removal.
**Risks:** losing useful reference code from `suites` (mitigate: git history retains it); web_portal build breakage discovery.
**Dependencies:** none. **Blocks everything.**

### Phase 1 — API Contract & Data-Model Foundation (complexity: MEDIUM-HIGH, ~1.5 weeks)
**Goal:** the schema the rest of the roadmap stands on; kill contract drift.
**Work:**
- New/changed models: `DoctorProfile` (specialty, fee, experience, schedule slots), `Pharmacy` (name, lat/lng, contact), `PharmacyItem` + `expiry_date`/`batch`/`generic_group` + FK to Pharmacy, `Hospital` (+ emergency-desk users, HOSPITAL role), `Payment` (order id, status, appointment link), fix `EHRRecord` (int FK patient_id, structured `record_type`/`payload` JSON, `family_profile_id`), wire `TriageLog` persistence.
- Alembic migration(s) + run `alembic upgrade head` on container/render start.
- Missing endpoints that already have callers: `POST /ehr/sync` (C1), `GET /ehr/records` or fix the directory page's target (C4), `GET /doctors` (C5).
- FastAPI rate limiting (slowapi) on `/auth/*` and `/triage/*` (H2); pagination conventions.
- Publish the OpenAPI schema as the contract; add a typed client generation step (or a shared TS types package) for web_portal/react_dashboard.
**Modules:** backend_service (models, schemas, alembic, all routers), both web frontends' `lib/api`.
**Expected files:** `models.py`, `schemas.py`, new `modules/doctors/`, `modules/family/` (stub for P2), alembic version files, `main.py`, Dockerfile/render.yaml (migration step), ~15–20 files.
**Risks:** migration against existing demo DBs (accept destructive reset pre-pilot); scope creep — keep endpoints minimal, models complete.
**Dependencies:** P0.

### Phase 2 — Family Profiles End-to-End (complexity: MEDIUM, ~1 week)
**Goal:** planning's Phase-1 mandate: member selection gates every feature.
**Work:** family CRUD router (owner-scoped); web `family/page.tsx` wired to real API with edit/delete; mobile profile-selection screen (photo-as-button per planning), persisted active-profile context; propagate `family_profile_id` through triage, EHR reads/writes, booking, vitals; introduce mobile state management (Riverpod/Provider) since profile context is app-global.
**Modules:** backend `modules/family/`, web_portal (family, header/profile switcher), mobile_app (new screens, router, services).
**Expected files:** ~12–15.
**Risks:** retrofitting profile-scoping into existing endpoints (make `family_profile_id` optional-null = account owner, to stay backward compatible).
**Dependencies:** P1.

### Phase 3 — Family Health Wallet + OCR + Real Offline Sync (complexity: HIGH, ~2 weeks)
**Goal:** the Wallet as designed: per-member, color-coded, camera/OCR ingestion, offline-first that actually syncs.
**Work:** server `POST /ehr/sync` accepting batched client records with client-generated UUIDs + timestamps (idempotent upsert; last-write-wins + server audit trail as the planning's conflict answer); mobile: encrypted Hive (`HiveAesCipher` via `flutter_secure_storage`-held key), token to secure storage, camera flow (`image_picker`) → `/triage/ocr` → confirm-and-save structured record; wallet UI per member with color-coded record types; patient-facing prescriptions view in web_portal; fix M5 read-model naming.
**Modules:** mobile_app (wallet, camera, sync, storage), backend ehr_sync, web_portal.
**Expected files:** ~15–18.
**Risks:** OCR accuracy on handwritten rural prescriptions (mitigate: always human-confirm before save); sync edge cases (duplicate submission — solved by UUID idempotency).
**Dependencies:** P2 (member scoping), P1 (EHR model).

### Phase 4 — Doctor Discovery, Schedules & Payment-Linked Booking (complexity: MEDIUM-HIGH, ~1.5 weeks)
**Goal:** real multi-doctor booking with the planning's "pay before call, refund if unattended" rule.
**Work:** `GET /doctors` + doctor profile management; slot model + availability endpoint; booking flow: create order → verify payment server-side → **server** creates appointment only against a verified `Payment` row (closes C6); refund path (`razorpay` refund API / mock) when doctor marks unavailable or no-show — the practical stand-in for the discussed escrow; remove `DOCTOR_ID=2`; doctor-side schedule editor in web_portal.
**Modules:** backend (doctors, appointments, payments), web_portal (book, directory, doctor dashboard).
**Expected files:** ~12.
**Risks:** payment-state machine correctness (define statuses CREATED→PAID→CONSUMED/REFUNDED and test them); double-booking races (unique slot constraint).
**Dependencies:** P1.

### Phase 5 — Pharmacy Intelligence (complexity: HIGH, ~2 weeks)
**Goal:** pharmacy as an ecosystem node, not a stock table.
**Work:** pharmacy registration/profile (geo); patient-facing nearby-medicine search (Haversine query; green/red availability) in mobile + web; fulfillment decrements stock atomically (H7); rural stock entry modes: set-absolute-count and tap-to-decrement (planning-mandated), invoice photo → OCR-assisted entry; expiry alerts (now schema-supported) with orange-coded list; generic substitutes via `generic_group`; deferred to V2: interaction alerts, pre-order, Jan Aushadhi, batch recall (planning allows).
**Modules:** backend pharmacy module, react_dashboard, mobile_app (new pharmacy screens), web_portal.
**Expected files:** ~18–20.
**Risks:** substitute/interaction data sourcing (start with a small curated CSV, not a live drug DB); geo accuracy with self-reported locations.
**Dependencies:** P1 (Pharmacy entity), P3 (OCR flow reuse).

### Phase 6 — Emergency SOS, Production-Grade (complexity: MEDIUM-HIGH, ~1.5 weeks)
**Goal:** the life-safety loop as discussed: GPS, guard, escalation, confirmation.
**Work:** mobile: `geolocator` GPS capture, hold-3-seconds/slide activation guard, correct payload (`location_lat/lng/text`), await + retry + visible delivery confirmation, SMS-intent fallback to emergency contacts when offline (`url_launcher` sms:); emergency-contacts model + settings UI; Node: responder room (`emergency_responders`) instead of global broadcast (H10); doctor/hospital web subscribes to FCM topic (H6) and the room; escalation timer — unaccepted SOS re-alerts next-nearest hospital (needs Hospital geo from P1) with "Help En Route" status broadcast on acceptance; persist SOS acceptance in FastAPI (already modeled) and reflect status to the patient app.
**Modules:** mobile_app, backend emergency, node_api, web_portal doctor dashboard.
**Expected files:** ~12–15.
**Risks:** the SMS fallback is best-effort on Android only — document the limitation; escalation logic needs a scheduler (a simple asyncio task/celery-lite is enough at pilot scale).
**Dependencies:** P1 (Hospital), P2 (contacts per profile).

### Phase 7 — Accessibility & Identity: Tamil + Voice + Themed UI (complexity: HIGH, ~2 weeks)
**Goal:** the features that make GramCare "GramCare".
**Work:** Flutter `flutter_localizations` + full Tamil/English ARB catalogs; web next-intl for the assisted-access portal; voice input: `speech_to_text` (Tamil locale) feeding the symptom checker's big-mic-first screen per the planning's screen spec; voice output: `flutter_tts` "tap to hear" on wallet records and triage results; per-module theming: color identity (pharmacy green, consultation blue, SOS red per planning), module-specific loading/transition animations, extract the copy-pasted neumorphic decoration into shared themed widgets.
**Modules:** mobile_app (broad), web_portal (i18n), design tokens.
**Expected files:** ~25+ (touches every screen).
**Risks:** Tamil ASR quality on-device varies by phone (fallback: server-side transcription via Gemini audio later); translation review needs a native speaker; do this *after* feature UIs stabilize (hence its position).
**Dependencies:** P2–P6 UI surfaces exist.

### Phase 8 — AI Depth (complexity: MEDIUM-HIGH, ~1.5 weeks)
**Goal:** close the AI gaps against §2.2/§2.4.
**Work:** enrich the triage schema/prompt with causes, first aid, side effects, treatment options, untreated-outcome, specialist-type; persist every analysis to `TriageLog` (H1) with anonymizable region tag; auto-SOS prompt on Critical tier in clients; AI Doctor Assistant: pre-consult summary endpoint aggregating timestamped EHR + active medicines (start/end-date logic) + latest triage, rendered in the doctor dashboard before a call; Community Health Intelligence v1: clustering query over TriageLog (same region + similar condition within window) surfaced on a minimal health-authority page (defer a full separate portal to V2 per planning's hold list); conversational follow-up questions in the symptom checker (multi-turn with Gemini chat sessions).
**Modules:** backend ai_triage + new ai_assist module, web_portal doctor views, mobile triage.
**Expected files:** ~12.
**Risks:** medical-safety review of expanded advice fields (keep the enforced disclaimer, avoid dosage instructions in home remedies); prompt-injection via symptom text (sanitize + system-prompt hardening).
**Dependencies:** P1 (TriageLog wiring), P3 (EHR data to summarize).

### Phase 9 — Hardening, Testing & Observability (complexity: MEDIUM, ~1.5 weeks)
**Goal:** production-grade quality gates.
**Work:** backend test suite that asserts real outcomes (kill the 200-or-500 test): auth flows, role denials, payment-booking linkage, pharmacy lifecycle, SOS lifecycle, sync idempotency; Node tests (vitest + socket.io-client) for auth gating and room scoping; Flutter widget tests for profile switching and offline queue; Playwright smoke for the patient journey; security: httpOnly-cookie or in-memory token strategy for web, refresh tokens, non-root Docker user + HEALTHCHECK, drop test deps from prod image, unexpose Postgres port, `.dockerignore` everywhere, dependency audit; TURN server (coturn container or Twilio NTS) behind the existing `/api/webrtc/turn-credentials` endpoint (H3); structured logging + Sentry (or equivalent) + uptime checks; load test triage and SOS paths.
**Modules:** all.
**Expected files:** ~20–25 (mostly tests/config).
**Risks:** none novel — this phase *reduces* risk. **Dependencies:** P1–P8 feature-complete.

### Phase 10 — Pilot Deployment (complexity: MEDIUM, ~1 week + ongoing)
**Goal:** planning's Stage-3 pilot (selected rural health centers).
**Work:** production env promotion on Render (or move to a single VM/K8s if Render free-tier limits bite — free tier sleeps, unacceptable for SOS; budget for paid tier); managed Postgres with automated backups + restore drill; domain + TLS + CORS/ALLOWED_ORIGINS lockdown; secrets in platform vault (rotate everything once more); signed Android APK/AAB + Play internal testing track; seed real pilot data (doctors, pharmacies, hospitals); operations runbook + on-call expectations for SOS; UAT with patients/doctors/pharmacists per Volume 5 §21.8; success-metric dashboards (API latency, sync success rate, AI latency, SOS acknowledgment time — §21.12).
**Risks:** free-tier sleeping vs. emergency availability (must upgrade); Gemini quota under real load (billing + caching plan); medico-legal review of AI advice before real patients.
**Dependencies:** P9.

---

## 7. Master Timeline & Resourcing

| Phase | Duration | Cumulative |
|---|---|---|
| P0 Repo unification | 0.5 wk | 0.5 |
| P1 Contract & data model | 1.5 wk | 2 |
| P2 Family profiles | 1 wk | 3 |
| P3 Wallet + OCR + sync | 2 wk | 5 |
| P4 Doctors + payments | 1.5 wk | 6.5 |
| P5 Pharmacy intelligence | 2 wk | 8.5 |
| P6 Emergency SOS | 1.5 wk | 10 |
| P7 Tamil + voice + theming | 2 wk | 12 |
| P8 AI depth | 1.5 wk | 13.5 |
| P9 Hardening & tests | 1.5 wk | 15 |
| P10 Pilot deployment | 1 wk | **16 wk** |

Parallelization: with 2+ developers, P4∥P3 (after P1) and P5∥P6 compress the plan to ~11–12 weeks. P7 must not start before its dependent UIs settle. For the research-publication goal, P8's TriageLog dataset + explainability outputs and §21.12 metrics are the evaluation backbone — instrument them from P1, not at the end.

**Definition of done per phase:** all CI green (single workflow), `docker compose up` end-to-end demo of the phase's journey, no new items in the defect register, and the feature-matrix row(s) it targets flipped to ✅.

---

## 8. Immediate Next Actions (this week)

1. Commit the current uncommitted hardening baseline (it's the foundation everything above builds on).
2. Execute Phase 0 (delete `suites`/`ci-cd.yml`, verify web_portal build, rotate the Gemini key).
3. Approve the Phase 1 data-model list (§6-P1) — it is the single highest-leverage decision remaining.
