import asyncio
import logging
import os
from contextlib import asynccontextmanager

import time

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

from core.ratelimit import rate_limit, warn_if_counters_are_split
from core.security_middleware import SecurityHeadersMiddleware
from core.timezone_json import UtcJSONResponse

load_dotenv()

logger = logging.getLogger("gramcare.main")

# Import Routers
from modules.auth.router import router as auth_router
from modules.ai_triage.router import router as ai_triage_router
from modules.ehr_sync.router import router as ehr_sync_router
from modules.pharmacy_inventory.router import router as pharmacy_router
from modules.payments.router import router as payments_router
from modules.appointments.router import router as appointments_router
from modules.emergency.router import router as emergency_router
from modules.family.router import router as family_router
from modules.doctors.router import router as doctors_router
from modules.ai_assist.router import router as ai_assist_router
from modules.analytics.router import router as analytics_router
from modules.lab.router import router as lab_router
from modules.hospital.router import router as hospital_router
from modules.passport.router import router as passport_router
from modules.preventive.router import router as preventive_router
from modules.navigator.router import router as navigator_router
from modules.cds.router import router as cds_router
from modules.referrals.router import router as referrals_router
from modules.chw.router import router as chw_router
from modules.files.router import router as files_router
from ai.router import router as ai_health_router


def _seed_government_whitelist():
    """Idempotently seeds AuthorizedGovernmentEmail from
    GOVERNMENT_WHITELIST_EMAILS (comma-separated) — the only way to obtain
    a Government Portal (ADMIN) account is POST /auth/register/government
    with a whitelisted email, and there's no self-serve application flow to
    populate this table, so it must be seeded somewhere. Safe to run on
    every startup: only inserts emails not already present."""
    import models
    from database import SessionLocal

    raw = os.getenv("GOVERNMENT_WHITELIST_EMAILS", "")
    emails = [e.strip().lower() for e in raw.split(",") if e.strip()]
    if not emails:
        return
    db = SessionLocal()
    try:
        existing = {
            e.lower() for (e,) in db.query(models.AuthorizedGovernmentEmail.email).all()
        }
        for email in emails:
            if email not in existing:
                db.add(models.AuthorizedGovernmentEmail(email=email, note="seeded from GOVERNMENT_WHITELIST_EMAILS"))
        db.commit()
    except Exception as e:  # never block app startup over this
        logger.error("Failed to seed government email whitelist: %s", e)
        db.rollback()
    finally:
        db.close()


async def _sos_escalation_loop():
    """Background watchdog: escalate unacknowledged SOS alerts to the next
    nearest hospital (planning doc's escalation chain). Runs every 60s."""
    from database import SessionLocal
    from modules.emergency.router import escalate_stale_sos

    while True:
        try:
            db = SessionLocal()
            try:
                escalated = escalate_stale_sos(db)
                if escalated:
                    logger.warning("SOS watchdog escalated %d alert(s).", escalated)
            finally:
                db.close()
        except Exception as e:  # the watchdog must never die
            logger.error("SOS escalation loop error: %s", e)
        await asyncio.sleep(60)


async def _appointment_reminder_loop():
    """Background watchdog: SMS patients ahead of an upcoming confirmed
    appointment. Polled every 15 minutes — reminders fire hours ahead of
    time, so unlike the SOS watchdog this doesn't need 60s granularity."""
    from database import SessionLocal
    from modules.appointments.router import send_due_appointment_reminders

    while True:
        try:
            db = SessionLocal()
            try:
                sent = await send_due_appointment_reminders(db)
                if sent:
                    logger.info("Appointment reminder watchdog sent %d SMS.", sent)
            finally:
                db.close()
        except Exception as e:  # the watchdog must never die
            logger.error("Appointment reminder loop error: %s", e)
        await asyncio.sleep(900)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_government_whitelist()
    tasks = []
    # Disabled under pytest (TESTING=1) — tests call the watchdog functions directly.
    if os.getenv("TESTING") != "1":
        tasks = [
            asyncio.create_task(_sos_escalation_loop()),
            asyncio.create_task(_appointment_reminder_loop()),
        ]
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(
    title="GramCare AI Backend",
    description="Central Nervous System for the Patient, Doctor, and Pharmacy Suites.",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=UtcJSONResponse,
)

# Configure CORS
#
# These are the deployed first-party front-ends. They are unioned in
# unconditionally rather than left to CORS_ORIGINS, because that variable is
# set by hand in the Render dashboard and silently omitting one takes a whole
# role offline: the pharmacist portal was live and linked from the main
# portal's login redirect while production returned no
# Access-Control-Allow-Origin for it at all, so every API call it made was
# blocked by the browser. Nothing server-side errors in that state — the
# portal just renders and then fails on first request.
FIRST_PARTY_ORIGINS = [
    "https://gram-care-ai.vercel.app",
    "https://gramcare-pharmacy.onrender.com",
    "https://gramcare-lab.onrender.com",
]

_LOCAL_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:80",
]

_configured = os.getenv("CORS_ORIGINS")
origins = [o.strip() for o in _configured.split(",") if o.strip()] if _configured else list(_LOCAL_DEV_ORIGINS)
# Deliberately a union, not a fallback: an operator narrowing CORS_ORIGINS
# must not be able to knock a shipped front-end offline by omission.
for _origin in FIRST_PARTY_ORIGINS:
    if _origin not in origins:
        origins.append(_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Every `git push` mints a brand-new, unique Vercel preview URL
    # (gram-care-<hash>-anishas1523-1415s-projects.vercel.app) — hardcoding
    # each one into CORS_ORIGINS is a losing game and was confirmed live:
    # a preview deployment's login screen hung forever on "Please wait..."
    # because every API call was silently CORS-blocked (the browser console
    # showed the real error; the UI just looked like a slow cold start).
    # Only this account's own Vercel team can ever deploy under this
    # subdomain pattern, so trusting the whole pattern is safe and means
    # every future preview AND production deployment just works with no
    # config change needed on either side.
    allow_origin_regex=r"^https://[a-z0-9-]+-anishas1523-1415s-projects\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
# Low-bandwidth optimization: compress every response body over 500 bytes
# (gzip, applied only when the client sends Accept-Encoding: gzip) so rural
# mobile clients on slow/metered connections pay for far fewer bytes per
# sync — EHR record lists and the FHIR export bundle are the biggest wins
# here since both are JSON, which compresses very well.
app.add_middleware(GZipMiddleware, minimum_size=500)

# Include Routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(ai_triage_router, prefix="/api/v1/triage", tags=["AI Triage"])
app.include_router(ehr_sync_router, prefix="/api/v1/ehr", tags=["EHR Sync"])
app.include_router(pharmacy_router, prefix="/api/v1/pharmacy", tags=["Pharmacy Inventory"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payment Gateway"])
app.include_router(appointments_router, prefix="/api/v1/appointments", tags=["Appointments"])
app.include_router(emergency_router, prefix="/api/v1/sos", tags=["Emergency SOS"])
app.include_router(family_router, prefix="/api/v1/family", tags=["Family Profiles"])
app.include_router(doctors_router, prefix="/api/v1/doctors", tags=["Doctor Directory"])
app.include_router(ai_assist_router, prefix="/api/v1/assist", tags=["AI Doctor Assistant"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Community Health Intelligence"])
app.include_router(lab_router, prefix="/api/v1/lab", tags=["Laboratory"])
app.include_router(hospital_router, prefix="/api/v1/hospital", tags=["Hospital"])
app.include_router(passport_router, prefix="/api/v1/passport", tags=["Health Passport"])
app.include_router(preventive_router, prefix="/api/v1/preventive", tags=["Preventive AI"])
app.include_router(navigator_router, prefix="/api/v1/navigator", tags=["AI Care Navigator"])
app.include_router(cds_router, prefix="/api/v1/cds", tags=["Clinical Decision Support"])
app.include_router(referrals_router, prefix="/api/v1/referrals", tags=["Referrals"])
app.include_router(chw_router, prefix="/api/v1/chw", tags=["Community Health Worker"])
app.include_router(files_router, prefix="/api/v1/files", tags=["File Storage"])
app.include_router(ai_health_router, prefix="/api/v1/ai", tags=["AI Operations"])



warn_if_counters_are_split()


@app.get("/")
def read_root():
    return {"message": "Welcome to the GramCare AI API. System is fully operational."}


@app.get("/health", tags=["System"])
def health():
    return {
        "status": "healthy",
        "service": "GramCare AI Backend",
        "version": "1.0.0"
    }


@app.get("/health/integrations", tags=["System"])
def integrations_health():
    """Which external integrations are actually live.

    Every one of these degrades to a mock rather than failing loudly, which
    is the right behaviour at runtime and terrible for knowing what is
    switched on: "FCM will be mocked" appears once in a deploy log and is
    then invisible forever. A push that silently goes nowhere looks exactly
    like a push that was delivered.

    Booleans only — never a key, a path, or a fragment of either.
    """
    import os

    from core.cloudinary_service import cloudinary_client
    from core import notifications

    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    # "the path is set but the file is not there" is the whole failure mode
    # for a Render secret file, and the only way to see it is to compare the
    # configured path against what actually landed in the secrets directory.
    # Paths and filenames are not secret; the contents are, and are never
    # read here.
    secrets_dir = os.path.dirname(cred_path) if cred_path else "/etc/secrets"
    try:
        present = sorted(os.listdir(secrets_dir))
    except Exception:
        present = []

    if notifications._firebase_initialized:
        push_detail = "FCM delivering"
    elif not cred_path:
        push_detail = "FIREBASE_SERVICE_ACCOUNT_PATH not set — every push is silently dropped"
    elif not os.path.exists(cred_path):
        push_detail = (
            f"no file at {cred_path}. Files present in {secrets_dir}: "
            f"{present or 'none'}. The secret file's name must match the "
            f"path exactly."
        )
    else:
        push_detail = f"file exists at {cred_path} but Firebase rejected it — check it is the full service-account JSON"

    return {
        "push_notifications": {
            "live": bool(notifications._firebase_initialized),
            "configured_path": cred_path,
            "detail": push_detail,
        },
        "sms": {
            "live": bool(os.getenv("MSG91_AUTH_KEY")),
            "detail": "MSG91 configured" if os.getenv("MSG91_AUTH_KEY")
            else "MSG91_AUTH_KEY not set — SOS contact SMS is dropped",
        },
        "email": {
            # A key alone delivers nothing. Resend's shared onboarding@resend.dev
            # only accepts the address that owns the Resend account; every other
            # recipient comes back 422, so password resets and verification links
            # silently went nowhere while this reported "configured".
            "live": bool(os.getenv("RESEND_API_KEY")) and bool(os.getenv("RESEND_FROM_EMAIL")),
            "from_address": os.getenv("RESEND_FROM_EMAIL") or "onboarding@resend.dev (shared sandbox)",
            "detail": (
                "Resend configured with a sender on your own domain"
                if os.getenv("RESEND_API_KEY") and os.getenv("RESEND_FROM_EMAIL")
                else "RESEND_API_KEY not set — no email is sent at all"
                if not os.getenv("RESEND_API_KEY")
                else "No RESEND_FROM_EMAIL, so sending falls back to Resend's shared "
                     "sandbox address, which only delivers to the Resend account "
                     "owner. Password resets and verification links are rejected "
                     "(422) for everyone else."
            ),
        },
        "payments": {
            "live": bool(os.getenv("RAZORPAY_KEY_ID") and os.getenv("RAZORPAY_KEY_SECRET")),
            "detail": "Razorpay live" if os.getenv("RAZORPAY_KEY_ID") and os.getenv("RAZORPAY_KEY_SECRET")
            else "mock mode — orders are not real",
        },
        "file_storage": {
            "live": True,
            "detail": "Cloudinary" if cloudinary_client.configured
            else "database-backed (/files/{token}) — working, no Cloudinary needed",
        },
        "maps_geocoding": {
            "live": bool(os.getenv("GOOGLE_MAPS_API_KEY")),
            "detail": "Google geocoding available" if os.getenv("GOOGLE_MAPS_API_KEY")
            else "no key — map tiles are OpenStreetMap and need none; only "
                 "address lookup and road ETA degrade",
        },
    }


@app.get("/health/ai", tags=["System"])
def ai_health():
    """Why the AI is or is not answering, from the server's point of view.

    Reads the live AIManager the routers use. It used to build a fresh
    AIManager per call, which has no history, so it could never show a key
    parked for being unfunded or a provider the circuit breaker had shut
    off; it reported "ok" while two of three providers were failing.

    This still cannot tell whether a key *works*: nothing here calls a
    provider. GET /health/ai/live does that.

    Deliberately leaks nothing: counts and states only, never key material.
    """
    from ai import get_ai_manager

    providers = {}
    for name, provider in get_ai_manager().all_providers().items():
        if name == "mock":
            continue
        pool = getattr(provider, "key_pool", None)
        status = provider.health_status()
        providers[name] = {
            "configured": provider.is_configured(),
            "model": getattr(provider, "_model", None),
            "available": status.available,
            "reason": status.reason,
            "keys_configured": len(pool) if pool is not None else 0,
            "keys_usable_now": pool.available_count() if pool is not None else 0,
            "keys_unfunded": pool.dead_count() if pool is not None else 0,
            "all_keys_exhausted": provider.quota_exhausted(),
        }

    usable = sum(p["keys_usable_now"] for p in providers.values())
    configured = sum(p["keys_configured"] for p in providers.values())
    if configured == 0:
        verdict = "no_keys_configured"
    elif usable > 0:
        verdict = "ok"
    elif any(p["all_keys_exhausted"] for p in providers.values()):
        verdict = "quota_exhausted"
    else:
        verdict = "keys_rejected"

    return {
        "verdict": verdict,
        "keys_configured_total": configured,
        "keys_usable_now": usable,
        "providers": providers,
        "note": "configuration only; GET /health/ai/live calls each provider",
    }


_KEY_LIKE = __import__("re").compile(r"(sk-ant-|sk-|gsk_|AIza|AQ\.)[A-Za-z0-9_\-.*]+")


@app.get(
    "/health/ai/live",
    tags=["System"],
    # Each call spends a little real quota on every configured provider, so
    # it must not be something a stranger can loop.
    dependencies=[Depends(rate_limit("ai_health_live", 3, 600))],
)
async def ai_health_live():
    """Send one real triage request to each configured provider, separately.

    The only check that answers "does this key actually work". A retired
    model and an unfunded account both look perfectly configured until a
    request is made; this makes the request and reports the exact failure.

    Error text is passed through with anything key-shaped redacted.
    """
    import asyncio

    from ai import AITask, get_ai_manager
    from ai.base import AIRequest
    from modules.ai_triage.router import TRIAGE_PROMPT_TEMPLATE

    prompt = TRIAGE_PROMPT_TEMPLATE.format(
        age=30, symptoms="mild fever and headache since this morning", image_note="",
    )

    async def probe(name, provider):
        if not provider.is_configured():
            return name, {"ok": False, "category": "NotConfigured"}
        start = time.monotonic()
        try:
            data = await provider.generate(
                AIRequest(task=AITask.TRIAGE, prompt=prompt, timeout_seconds=30)
            )
            return name, {
                "ok": True,
                "latency_ms": round((time.monotonic() - start) * 1000),
                "answer_has_condition": bool(data.get("predicted_condition")),
            }
        except Exception as e:  # report every failure, never raise
            return name, {
                "ok": False,
                "category": getattr(e, "category", type(e).__name__),
                "detail": _KEY_LIKE.sub("[redacted]", str(e))[:200],
                "latency_ms": round((time.monotonic() - start) * 1000),
            }

    manager = get_ai_manager()
    results = await asyncio.gather(*(
        probe(name, provider)
        for name, provider in manager.all_providers().items()
        if name != "mock"
    ))
    providers = dict(results)
    working = [n for n, r in providers.items() if r.get("ok")]
    return {
        "working_providers": working,
        "verdict": "ok" if working else "no_working_provider",
        "providers": providers,
    }
