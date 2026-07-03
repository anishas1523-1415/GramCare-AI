# GramCare AI — Comprehensive Technical Audit

**Prepared for:** Anish
**Date:** July 3, 2026
**Scope:** Full monorepo — `apps/backend_service` (FastAPI), `backend/node_api` (Node/Socket.io), `apps/web_portal` (Next.js), `apps/react_dashboard` (React/Vite), `apps/mobile_app` (Flutter), `apps/suites/*` (legacy tree), `docker-compose.yml`, CI workflows, and the Tamil planning documents.
**Status:** No code was modified. This is a read-only audit.

---

## 1. Executive Summary

GramCare AI is currently a **collection of parallel, partially-connected prototypes**, not a single production system. The root `README.md` describes a clean 5-service architecture, and that architecture does exist — but sitting alongside it is a second, undocumented `apps/suites/` tree (three more sub-apps) that is *still actively built by a second CI workflow*. Two competing pipelines build two different versions of the same product.

Within the documented 5 services, the backend (FastAPI + Node signaling) is the most mature layer but has serious authentication gaps — several routers, including pharmacy stock writes, payments, and the Socket.io signaling layer, have authentication that is either missing or explicitly bypassable. The three frontends (`web_portal`, `react_dashboard`, `mobile_app`) are best described as **high-fidelity UI scaffolding**: attractive screens exist, but core planning-document features — voice/image symptom input, the Family Health Wallet, OCR prescription scanning, GPS-based pharmacy search, Tamil/regional-language support, and most of the pharmacy intelligence features — are either mocked, hardcoded, or entirely absent.

Overall estimated alignment with the planning document's MVP scope: **roughly 20–30%** implemented end-to-end (UI-only implementations that don't reach a working backend are counted as partial, not complete).

| Area | Verdict |
|---|---|
| Backend API (FastAPI) | Functional core, critical auth gaps |
| Realtime signaling (Node) | Functional skeleton, auth intentionally bypassable |
| Web Portal (Next.js) | Visual scaffold — no working login, mocked family profiles |
| Pharmacy Dashboard (React) | Non-functional — calls API routes that don't exist |
| Mobile App (Flutter) | Early scaffold — ~15–20% of planning scope, no voice/OCR/GPS/i18n |
| `apps/suites/*` legacy tree | Duplicate/superseded prototypes, still built by a second CI file |
| Documentation vs. reality | Multiple false or misleading claims in README |

---

## 2. Architecture Reality Check

The README's "5 core microservices" claim is **true but incomplete**. `docker-compose.yml` does wire up exactly those 5 services (`web_portal`, `pharmacy_portal` → `react_dashboard`, `node_signaling` → `backend/node_api`, `fastapi_backend` → `backend_service`, `postgres_db`), and a real GitHub Actions workflow (`.github/workflows/main.yml`) does build/test all four application services on push/PR.

However, a **second, contradictory workflow** exists at `.github/workflows/ci-cd.yml`. It does not build any of the README's services — instead it builds:
- `apps/suites/patient_app/mobile_app/react_ui` (Vite/React patient SPA)
- `apps/suites/doctor_hospital_suite/web_app` (Next.js 14 doctor portal)
- `apps/suites/pharmacy_suite/web_app` (Next.js 14 pharmacy portal)

These three `apps/suites/*` sub-projects are **not mentioned anywhere in the README**, are **not referenced in `docker-compose.yml`**, yet are actively compiled by CI. This means the project currently has two live, diverging product lines: the documented one (newer stack: Next 16 / React 19 / Vite 8) and an older, undocumented one (Next 14 / React 18) that a second CI file keeps "green." A new engineer opening this repo has no way to know which is canonical without reading both workflow files — this is the single biggest structural risk in the codebase and should be resolved before any further feature work.

Version pinning is also inconsistent project-wide: README says "Python 3.11+," the FastAPI `Dockerfile` uses Python 3.10, `ci-cd.yml` sets up Python 3.10, and `main.yml` uses Python 3.11 — three different answers to the same question in three different files.

---

## 3. CRITICAL Priority Issues

Issues in this tier represent production-blocking security holes, data-integrity risks, or build-breaking defects. For a healthcare application handling patient data and emergency dispatch, these must be resolved before any pilot deployment.

### Security

1. **Live-looking Gemini API key committed to `apps/backend_service/.env`.** The value is not a placeholder pattern (unlike the blank `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` in the same file). `.env` is gitignored, but the key is loaded directly into the Docker container and should be rotated regardless, since it already exists in a live file on disk.
2. **Socket.io signaling has authentication that explicitly allows unauthenticated connections.** In `backend/node_api/server.js`, the `io.use` middleware calls `next()` (accepts the connection) both when no token is supplied and when token verification fails, with a comment describing this as intentional "for demo purposes." Any client can join any call room, inject WebRTC signaling messages, or fire triage/emergency events with zero credentials. This directly contradicts the README's claim of "strict JWT-authenticated WebRTC signaling."
3. **JWT secrets don't match between the two backend services.** FastAPI reads `JWT_SECRET_KEY` (`apps/backend_service/modules/auth/utils.py`); Node reads a different variable, `SECRET_KEY` (`backend/node_api/server.js`). `docker-compose.yml` never aligns the two. Combined with #2, a broken handshake silently degrades to "let the client in anyway" instead of rejecting the connection.
4. **Pharmacy stock endpoints have no authentication.** `apps/backend_service/modules/pharmacy_inventory/router.py` — both `GET /stock` and `POST /update_stock/{medicine_id}` have no auth dependency, and `quantity_added` is unvalidated (can go negative). Anyone who can reach the API can corrupt medicine inventory for the entire pharmacy network.
5. **Payments endpoints are unauthenticated with a trivially forgeable mock-verification path.** `apps/backend_service/modules/payments/router.py` — `/create-order`, `/verify`, `/checkout` have no auth; `patient_id` is client-supplied and never cross-checked against the caller; the mock-mode signature check accepts any string starting with `mock_sig_`.
6. **Vitals and SOS ingestion are unauthenticated with no rate limiting.** `POST /vitals` (`ehr_sync/router.py`) accepts fabricated clinical data from anyone. `POST /api/sos/trigger` (`backend/node_api/server.js`) broadcasts to **every connected socket** with no payload validation and no throttling — a trivial spam vector that could drown out genuine emergencies in a system whose entire premise is emergency response.
7. **Hardcoded weak database password, committed in plaintext.** `docker-compose.yml` sets `POSTGRES_PASSWORD: securepassword123` in two places, and this same value is echoed into GitHub Actions (`main.yml` and `ci-cd.yml`). The `environment:` block in `docker-compose.yml` also silently overrides the Supabase `DATABASE_URL` loaded from `.env` via Compose precedence rules — meaning the `.env` database URL is dead in the containerized path, a confusing trap for developers.

### Data / Database

8. **The application silently falls back from PostgreSQL to SQLite on any connection error**, logging only a warning (`apps/backend_service/database.py`). Because the committed `.env`'s `DATABASE_URL` contains a literal unfilled placeholder (`[YOUR-PASSWORD]`), this fallback is what actually runs outside Docker — explaining the stray `gramcare.db` / `gramcare_local.db` files found in the repo despite the README's PostgreSQL claim. This is a silent data-durability risk: nobody would notice the app is running on a throwaway local SQLite file instead of the real database.
9. **`gramcare_local.db` is not covered by `.gitignore`** (only `gramcare.db` and `*.sqlite3` are excluded) — real patient data risks being committed to source control.
10. **Two divergent, incompatible "Prescription" concepts exist in the same system.** `schemas.py` defines a proper `Prescription` schema backing `models.Prescription`; `modules/ehr_sync/router.py` independently redefines an incompatible inline version backing `models.EHRRecord`, where `medicines` is a plain string instead of structured data.

### Build / Runtime

11. **`apps/react_dashboard` cannot function against the real backend.** It calls `GET /pharmacy/inventory`, `GET /pharmacy/queue`, and `PUT /pharmacy/fulfill/{id}` — none of these routes exist. The real backend only exposes `GET /pharmacy/stock` and `POST /pharmacy/update_stock/{id}`. Every request from this dashboard 404s; the prescription-fulfillment feature is completely non-functional. Even the field names don't match (`item.medicine_name` on the frontend vs. `name` in the backend response), so fixing the routes alone would still render blank medicine names.
12. **`apps/mobile_app`'s test suite does not compile.** `test/widget_test.dart` still references `MyApp` and the default Flutter counter demo (`Icons.add`, text `'0'`/`'1'`); the real app class is `GramCareApp`. `flutter test` and `flutter analyze` (run in CI) will fail on this file.
13. **`apps/web_portal` has no login or registration page anywhere.** Grepping the entire `src/app` tree for auth pages returns nothing — only an `AuthContext` that exposes a `login()` function nothing in the UI ever calls. Every "protected" page (booking, family profiles, doctor dashboard, consultation) is unreachable through a real session; the planning document's very first step, "Secure login or registration," does not exist in this app.
14. **`apps/mobile_app`'s offline sync has a likely crash bug.** `lib/services/sync_service.dart` calls `healthWallet.add(record)` to re-insert an already-boxed Hive object into a second box. Hive throws `HiveError: The same instance of a HiveObject cannot be added to two different boxes` — this is a foreseeable runtime crash in the app's core offline-sync path, not a hypothetical edge case.

---

## 4. HIGH Priority Issues

### Backend / Infra

15. Firebase service-account private key (`backend/node_api/firebase-service-account.json`) is gitignored but has no `.dockerignore` guarding the Docker build context, risking leakage into a shared build context or pushed image.
16. Socket.io CORS is set to `origin: "*"`, and the Express layer uses bare `cors()` (reflects any origin) — combined with the auth bypass above, any origin can open a socket or hit the SOS endpoint.
17. No rate limiting anywhere in either backend service — login, registration, and SOS trigger are all open to brute force or spam.
18. WebRTC signaling relay (`offer`/`answer`/`ice_candidate` handlers) never verifies the socket actually joined the target room before relaying — signaling can be injected into arbitrary call sessions if room IDs are guessable.
19. No global error handling in the Node service — a malformed payload before the FCM push call can crash the emergency-alert path silently, with no `uncaughtException` guard.
20. Only STUN is configured for WebRTC, no TURN server — calls will fail for any client behind a symmetric NAT or strict firewall, a real-world reliability risk for the rural connectivity this platform explicitly targets.
21. `/register` in `modules/auth/router.py` defines a local, unvalidated `UserCreate` model that shadows the properly-constrained one in `schemas.py` — password length and role-pattern checks are effectively dead code on the registration path.
22. Role-authorization logic is duplicated ad hoc per router (`appointments`, `emergency`) while an unused `require_role()` factory sits in `auth/router.py`, never applied anywhere.
23. Two divergent, both-runnable seed scripts (`seed.py`, `seed_data.py`) with different demo users and coverage — unclear which is canonical, risking confusing demo/test state.

### Web Portal

24. Family Profiles are 100% mocked — `family/page.tsx` explicitly comments out the real API call ("Temporarily using mock data to keep UI stable during backend transition") and only writes to local React state. Nothing survives a page refresh. This is the planning document's "Family profile selection" step, and it does not talk to the backend at all.
25. No voice or image input for symptoms — only a plain `<textarea>` exists, despite the planning doc requiring voice/text/image triage input as a headline feature.
26. No Family Health Wallet feature of any kind — no per-member record view, no color-coded record types, no voice playback.
27. No pharmacy/medicine-availability search anywhere in the patient-facing web app.
28. No patient-facing view of issued prescriptions or AI consultation summaries — doctors can write prescriptions, but patients have no page to see them; the "auto-shared to pharmacy" loop is one-directional.
29. Hardcoded patient/doctor IDs used for real transactions (`DOCTOR_ID = 2`, `patientId={1}`, `patient_id: 1` scattered across booking and prescription pages) — once wired to a real multi-user backend, this lets any logged-in user act as patient #1.
30. `RazorpayCheckout.tsx` prefills payment data with static placeholders (`"Patient Name"`, `"patient@example.com"`) instead of the authenticated user's real details.
31. Several pages destructure Next.js dynamic route `params` synchronously; on the installed Next.js version (16.2.9) `params` is a Promise and must be awaited — this will throw or warn at runtime as written.
32. `src/utils/supabase/{server,client,middleware}.ts` import `@supabase/ssr`, which is not in `package.json` or installed — dead/broken code representing an abandoned second auth system that was never wired up (no root `middleware.ts` exists to invoke it).

### Pharmacy Dashboard

33. Every pharmacy planning-doc feature is missing: no stock-entry UI matching the "manual count / tap-to-decrement" model described for rural pharmacies, no GPS-based nearby search, no generic substitutes, no medicine interaction alerts, no expiry alerts, no prescription OCR scanner, no medicine information assistant.
34. The backend has no `expiry_date` column on `PharmacyItem` at all — so the Expiry Alerts feature is structurally unsupported end-to-end, not just unbuilt in the UI.
35. Stock-status logic is duplicated and diverges between frontend and backend: the backend computes "Low Stock" at `< 50`, the frontend independently recomputes "Healthy" at `> 50` and ignores the backend's own computed `status` field.
36. No pharmacist authentication anywhere in this app or its backend routes — same gap as Critical #4, listed here from the frontend's perspective since there's no login screen to even attempt auth.

### Mobile App

37. No Tamil or regional-language support anywhere — no localization files, no `intl`/`flutter_localizations` packages, no locale configuration. This is a core requirement for the target rural/low-literacy audience and is entirely absent.
38. No voice playback of records ("tap to hear it read aloud") — a headline accessibility feature for illiterate users, not implemented.
39. Emergency SOS sends a hardcoded location string (`'Rural Clinic Alpha'`) instead of real GPS coordinates; no location package is installed; the network call is fire-and-forget with no error handling or confirmation — dangerous for a life-safety feature.
40. Pharmacy search is completely absent from the mobile app — no screen, no route.
41. No distinctive per-module theming or animation despite the planning discussion's explicit, repeated emphasis on this (medicine-themed pharmacy visuals, disease-themed triage loading, hospital-themed consultation) — every screen reuses an identical copy-pasted neumorphic container.
42. Neither of the two mandated Health Wallet record-entry paths exists: no in-app doctor consultation/prescription screen, and no OCR camera-scan flow. The only way a record is created is a hardcoded demo button (`_addMockRecord()`).
43. Sensitive health data is stored in a plain, unencrypted Hive box, and the auth token is stored in plain `shared_preferences` rather than secure storage — a real compliance gap for clinical data.

### Suites / Architecture

44. `apps/suites/patient_app/mobile_app/react_ui/src/components/` contains nine fully-written components (auth, EHR dashboard, payments, chat, triage result, Tamil-localized neumorphic UI) that `App.tsx` never imports — entirely dead code sitting in a directory a new developer would reasonably assume is live.

---

## 5. MEDIUM Priority Issues

### Backend / Infra
45. String-typed foreign keys (`EHRRecord.patient_id`, `PharmacyItem.pharmacy_id`) with no DB-level `ForeignKey` constraint — no referential integrity enforced, per an explicit "legacy compatibility" code comment.
46. `pharmacy_inventory/router.py` returns `{"error": "Medicine not found"}` with HTTP 200 instead of a 404 — clients checking status codes will treat this as success.
47. Redundant PostgreSQL drivers installed (`psycopg2-binary` and `psycopg[binary]`) — unnecessary image bloat.
48. Docker-compose service names diverge from folder/README names (`fastapi_backend` vs. `backend_service`, `node_signaling` vs. `node_api`, `pharmacy_portal` vs. `react_dashboard`) — cosmetic, but confusing during onboarding and debugging.
49. `tests/test_triage.py` accepts both HTTP 200 and HTTP 500 as "passing," meaning it never actually confirms the AI triage engine works. No test coverage exists for appointments, emergency SOS, EHR sync, payments, or pharmacy mutation endpoints; the Node service has no test framework configured at all, and its `package.json` `main` field points at a file (`index.js`) that doesn't exist (real entry point is `server.js`).

### Web Portal
50. `any` typing is pervasive across state hooks (`page.tsx`, `family/page.tsx`, `doctor/dashboard/page.tsx`, `RazorpayCheckout.tsx`) despite `tsconfig.json` having `strict: true` — no shared type definitions exist for `TriageResult`, `Appointment`, `FamilyProfile`, or `Prescription`.
51. API/WebSocket base URLs are hardcoded and redefined independently in at least four separate files rather than centralized in one config module — easy to drift.
52. `consultation/[id]/page.tsx`'s mute/video toggle logic reads track-`enabled` state before flipping it, works only by a double-negative coincidence, and will throw if `getAudioTracks()`/`getVideoTracks()` return an empty array (e.g. permission denied).
53. Socket.io connection setup is duplicated independently in three separate files with no shared hook/provider; one page even opens a second, throwaway socket connection just to emit one event.
54. No multilingual support and no accessibility affordances (missing `aria-label`s on icon-only buttons, no alt-text strategy) despite the target audience being explicitly low-literacy rural patients.
55. Errors are surfaced via blocking `alert()` calls rather than in-UI messaging — poor UX, inaccessible for screen readers.

### Pharmacy Dashboard
56. `any[]` typing throughout with no interfaces defined anywhere in `src/` — the exact field-mismatch bug in Critical #11 would not have been caught by the type system even if types existed, because none do.
57. A hardcoded, non-functional analytics figure ("Total Fulfilled: 1,284, +12% from last week") is displayed as if real.
58. Single global `loading` boolean blocks the entire page rather than allowing partial rendering; no retry/error banner UI.
59. No routing library, no component decomposition — the entire dashboard is one 133-line file with inline styles mixed with utility classes.

### Mobile App
60. Unsafe dynamic access into API response maps with no null/type checks in the triage screen — a `null` or differently-typed field from a degraded AI response will throw at runtime.
61. Identical neumorphic `BoxDecoration`/shadow code is copy-pasted at least eight times across six screen files instead of being a shared widget.
62. The "IoT Vitals" screen is fully mocked (`Random()`-generated numbers presented as a real smartwatch connection) and doesn't persist submitted data anywhere, despite a code comment claiming otherwise.
63. Reminders screen is 100% hardcoded static data with no relation to actual prescriptions and no notification-scheduling package installed, despite showing a bell icon that implies real reminders.
64. No state-management framework (Provider/Riverpod/Bloc) — everything is local `setState`, which will not scale once family-profile switching and shared auth/sync state are needed.

### Architecture
65. Internal Python version disagreement across README (3.11+), `Dockerfile` (3.10), and the two CI workflows (3.10 and 3.11 respectively) — the codebase doesn't agree with itself on target runtime.

---

## 6. LOW Priority Issues

66. Backend Dockerfile runs as root, has no `HEALTHCHECK`, and installs test dependencies (`pytest`, `httpx`) into the production image.
67. `.gitignore` gaps: no `.env.*` wildcard (only bare `.env`), no `*.db` wildcard, nothing for `.pytest_cache/`, `.next/`, or IDE folders.
68. PostgreSQL port 5432 is exposed to the host in `docker-compose.yml` — unnecessary attack surface if not needed for local debugging.
69. No audit trail/persistence for SOS/emergency events on the Node service — `console.log` only, no delivery confirmation or retry if a responder's client is offline.
70. `apps/web_portal` still has default `create-next-app` boilerplate assets (favicon, placeholder SVGs) never replaced with GramCare branding.
71. `apps/react_dashboard`'s own `README.md` is still the untouched default Vite template text.
72. Suspicious/unusual package version pins across multiple frontends (e.g. `lucide-react ^1.22.0`, `vite ^8.1.0`, `typescript ~6.0.2`) that should be verified to actually resolve on `npm install` rather than assumed.
73. `apps/mobile_app`'s `analysis_options.yaml` uses only stock `flutter_lints` with no stricter rules, despite `print()` statements present in shipped code (`sync_service.dart`).

---

## 7. Missing Features vs. the Planning Document

The Tamil brainstorming transcript and the English "Volume 5" roadmap document together describe a specific MVP scope. Status against each item:

| Planning-doc feature | Status |
|---|---|
| Secure login/registration | **Missing** in web_portal; present but token stored insecurely in mobile_app |
| Family profile selection ("boxes per member") | **Not implemented** anywhere — mocked in web, absent in mobile |
| Voice symptom input | **Missing** in both web_portal and mobile_app |
| Text symptom input | Present (web_portal, mobile_app) |
| Image symptom input | **Missing** everywhere |
| AI severity %, cause, home remedies, first aid, recovery time, specialist referral | Partially present in mobile_app (severity score, condition, doctor recommendation only) — home remedies/first aid/recovery time/untreated-outcome all **missing** |
| Triage risk tiers (Low/Moderate/High/Critical) with auto-SOS on Critical | **Not implemented** as a client-side flow in either app |
| Doctor consultation with AI-prepared summary | Doctor dashboard/consult UI exists in web_portal; no AI-summary hand-off implemented |
| Digital prescription generation | Present (doctor can write one in web_portal) |
| Prescription auto-shared to pharmacy | **Broken** — react_dashboard calls nonexistent API routes |
| Nearby medicine availability (GPS) | **Missing** in all three frontends |
| Family Health Wallet (multi-profile, color-coded, voice playback) | **Missing** — mobile_app has a flat single-list record view only |
| OCR prescription/report scanning | **Missing** entirely — no camera, no OCR package anywhere |
| Medicine reminders | Present only as static, non-persisted mock UI in mobile_app |
| Emergency SOS with GPS + hospital routing | Present in signaling server, but **client sends fake location data** and has no auth |
| Pharmacy: manual/tap stock entry model | **Missing** — react_dashboard has no stock-entry UI at all |
| Pharmacy: Generic Substitutes | **Missing** |
| Pharmacy: Medicine Interaction Alerts | **Missing** |
| Pharmacy: Expiry Alerts | **Missing**, and unsupported by the DB schema (no `expiry_date` column) |
| Tamil / regional-language voice & text UI | **Missing** everywhere (some Tamil UI exists only in orphaned, unimported dead code in `apps/suites`) |
| Offline-first with sync | Partial in mobile_app (Hive local storage exists) but sync path has a likely crash bug and no conflict resolution |
| Distinctive per-module "stunning" UI/theming | **Not implemented** — all modules reuse identical generic styling |

Roughly **4 of 20** planning-doc MVP items are genuinely complete end-to-end; most others are either partially built on one platform only, mocked, or entirely absent.

---

## 8. Folder Structure & Duplication — `apps/suites/`

A full second application tree exists at `apps/suites/`, containing three sub-projects not mentioned in the README:

- **`doctor_hospital_suite/`** — the Flutter `mobile_app/` is an untouched `flutter create` counter template (no real code). The `web_app/` (Next.js 14) is real, working code (a 305-line doctor dashboard plus a 215-line WebRTC consultation room) that **duplicates** functionality already built, on a newer stack, in `apps/web_portal`.
- **`pharmacy_suite/`** — same pattern: dead Flutter template plus a real 185-line Next.js 14 "GramPharma" dashboard that duplicates `apps/react_dashboard`.
- **`patient_app/`** — the most active of the three: a Flutter WebView shell loading a separate React dev server, containing a genuinely substantial 724-line patient SPA (login, triage, SOS, WebRTC, IoT vitals, offline EHR caching) built on the *same* bleeding-edge stack (React 19 / Vite 8) as the current `apps/mobile_app` and `apps/web_portal` — suggesting this one may be more recent than the other two, not simply abandoned.

As shown in Section 2, this tree is not dead weight sitting idle — it is **actively rebuilt by `.github/workflows/ci-cd.yml`** on every push to `main`, in parallel with the documented services being built by `main.yml`. This is the audit's top structural finding: two CI pipelines are keeping two different products "green" simultaneously, and nothing in the repository states which one is authoritative.

**Recommendation:** get an explicit decision on `patient_app`'s WebView+React approach vs. the native Flutter `apps/mobile_app` approach; if Flutter is the chosen direction (which the README and the more complete `apps/mobile_app` implementation suggest), delete all of `apps/suites/`, delete `ci-cd.yml`, and remove the now-orphaned `react_ui/src/components/` dead code regardless of the final decision on `patient_app` itself.

---

## 9. Recommended Remediation Order

1. **Resolve the architecture split first.** Decide canonical apps, delete the losing tree and its CI workflow. Every other fix is wasted effort if it lands in a directory that gets deleted next sprint.
2. **Close the authentication gaps** (Critical #2–#6): Socket.io auth, pharmacy write endpoints, payments, vitals/SOS ingestion. These are exploitable today by anyone who can reach the deployed services.
3. **Fix the database configuration** (Critical #8): make the Postgres-vs-SQLite fallback fail loudly instead of silently, fill in the real `DATABASE_URL`, and align `.gitignore`.
4. **Fix the broken pharmacy API contract** (Critical #11) — this single fix unblocks the entire pharmacy dashboard.
5. **Build the missing web_portal login/registration flow** (Critical #13) — nothing else in that app is reachable without it.
6. **Fix the mobile app's sync crash** (Critical #14) and **broken test suite** (Critical #12).
7. Then work High-priority items module by module, prioritizing Family Health Wallet, voice/image input, and Tamil localization — these are the features that most define GramCare AI's stated purpose of serving low-literacy rural users, and none of them currently exist.

---

*This audit is based on static code review of the repository as of July 3, 2026. No runtime testing, penetration testing, or dependency-resolution verification (e.g. confirming `npm install`/`pip install` succeed with the pinned versions) was performed — several Low-priority items flag version pins that should be verified before relying on this report's build-success assumptions.*
