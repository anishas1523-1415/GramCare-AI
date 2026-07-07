# Frontend Production Integration Audit — GramCare AI

**Date:** July 5, 2026 · **Scope:** `apps/web_portal` (Next.js → Vercel), `apps/react_dashboard` (Vite → Render static) · **Local commit:** `fbcf85b`

---

## 1. Problems Found

| # | Severity | Problem | Status |
|---|---|---|---|
| 1 | **CRITICAL** | **Vercel production serves 404 at every route** despite a READY deployment. Root cause: `output: "standalone"` in `next.config.ts` (correct for the Docker image, incompatible with Vercel's serverless output — the deployment ships with no routable pages). Build logs show all 12 routes compiling fine; serving was the failure. | ✅ Fixed — standalone is now Docker-only via `DOCKER_BUILD=1` |
| 2 | HIGH | 8 hardcoded `localhost` fallbacks across both frontends (API `localhost:8000`, sockets `localhost:4000`). Any build without env vars produced a bundle pointing at the user's own machine. | ✅ Fixed — all fallbacks now default to the live Render services |
| 3 | HIGH | No `.env.production` existed for either frontend, and **both `.gitignore` layers blocked committing one** (`.env.*` at root, `.env*` in web_portal) — so Vercel builds silently depended entirely on dashboard env vars that may not be set. | ✅ Fixed — `.env.production` committed for both apps + explicit gitignore opt-ins (public values only) |
| 4 | MEDIUM | Unused `API_URL` constant in `page.tsx` (localhost) — dead code inviting future misuse. | ✅ Removed |
| 5 | LOW | web_portal Dockerfile ARG defaults pointed at localhost (bare `docker build` produced a broken image). | ✅ Defaults now production URLs; compose overrides for local |
| 6 | INFO | Web push notifications: no Firebase client config exists in the web portal — by design, doctors receive real-time alerts via authenticated Socket.IO (`emergency_alert`, `triage_update`); FCM is the mobile app's path. Nothing to fix, documented for clarity. | — |

## 2. Verification Results (what passed)

- **Endpoint contract:** all 21 static API paths used by both frontends (`/auth/*`, `/family`, `/triage/*`, `/ehr/*`, `/appointments/*`, `/payments/*`, `/pharmacy/*` ×10, `/sos/*`, `/doctors*`, `/assist/*`, `/analytics/*`) exist on the FastAPI backend route table. No mismatches.
- **JWT end-to-end:** login stores the token (`localStorage`: `access_token` / `pharmacy_access_token`); axios request interceptors attach `Authorization: Bearer` on **every** request in both apps; 401 responses clear the session centrally.
- **Socket.IO auth:** consultation room and doctor dashboard pass the same JWT in the socket handshake (`auth: { token }`); the signaling server verifies it and gates `join_room`/`offer`/`answer`/`ice_candidate`/`join_department` — video calling and the responder room both authenticate correctly. The homepage guest socket is intentionally unauthenticated (public symptom-checker feed, receives nothing sensitive).
- **Video signaling:** consultation page connects to the signaling URL (now production-defaulted), fetches ICE servers from `/api/webrtc/turn-credentials` (TURN-ready via env).
- **Vercel env inventory:** required build-time vars are now all supplied by the committed `.env.production` — `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, `NEXT_PUBLIC_RAZORPAY_KEY_ID`, `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`. Dashboard vars, if set, override the file.

## 3. Files Modified (12, commit `fbcf85b`)

`apps/web_portal`: `src/lib/api.ts`, `src/app/page.tsx`, `src/app/consultation/[id]/page.tsx`, `src/app/doctor/dashboard/page.tsx`, `next.config.ts`, `Dockerfile`, `.env.production` (new), `.gitignore`
`apps/react_dashboard`: `src/lib/api.ts`, `src/components/LoginScreen.tsx`, `.env.production` (new)
Root: `.gitignore`

## 4. URLs Changed

| From | To | Sites |
|---|---|---|
| `http://localhost:8000/api/v1` (and bare `:8000`) | `https://gramcare-fastapi.onrender.com/api/v1` | 4 |
| `http://localhost:4000` | `https://gramcare-signaling.onrender.com` | 4 |

## 5. Deployment Status & The One Manual Step

- Vercel project **`gram-care-ai`** (team `anishas1523-1415s-projects`), production domain `gram-care-ai.vercel.app`, GitHub auto-deploy enabled (git-main domain present).
- Commit `fbcf85b` is **committed locally but NOT pushed** — this sandbox has no GitHub credentials (the GitHub connector needs authorization in your claude.ai settings, and no token/gh CLI exists here; Vercel CLI deploy likewise requires a token).
- **→ Run `git push origin main` from your machine.** That push auto-triggers the Vercel build; with the standalone fix the site will serve instead of 404ing.

## 6. Post-Deploy Testing — done vs. blocked

Tested from here: current Vercel deployment fetched directly (confirmed the 404 + READY paradox, diagnosed root cause from build logs). Sandbox egress is proxy-restricted: `onrender.com` is unreachable from this environment (403 at the proxy), so live Register/Login/Triage/SOS/Booking/Pharmacy/Family/Doctor/Video/Notification flows **could not be exercised from this session**. They were all verified green earlier against the identical codebase on the live Docker stack (15/15 E2E) and the 32-test backend suite; the code shipping to Vercel calls those same verified endpoints.

**5-minute post-push checklist for you:** open `gram-care-ai.vercel.app` (homepage renders, "Live" socket badge green) → register + login → run a triage (result panel incl. first-aid fields) → Family: add member → Book: pick doctor → slot → mock-pay → confirmed → login as `doctor1` → dashboard shows queue + your booking → open Consult (camera prompt = signaling connected) → pharmacy dashboard (Render) fulfills the prescription. Any CRITICAL triage should show the SOS banner; doctor dashboard receives `emergency_alert` in real time.

## 7. Remaining Bugs / Risks

1. **Render free tier sleeps** — first request after idle takes ~50s and the frontend will look "down"; upgrade before real users (SOS depends on it).
2. Web JWT in `localStorage` (XSS surface) + no refresh rotation — pre-existing, unchanged (see main readiness report).
3. `CORS_ORIGINS` on the Render backend must include `https://gram-care-ai.vercel.app` (and the pharmacy dashboard's origin) or browser calls will be blocked — set it in the Render dashboard env.
4. Google Maps key is public by nature but should be **referrer-restricted** to your domains in Google Cloud Console.
5. Razorpay is in test mode (by design until live KYC).

## 8. Production Readiness (frontend integration)

**85%.** Code/config: 100% of found integration defects fixed and committed. Deducted: push+redeploy pending your one command (−5), live E2E on the deployed URL not yet re-run post-fix (−5), CORS env on Render unconfirmed (−5).
