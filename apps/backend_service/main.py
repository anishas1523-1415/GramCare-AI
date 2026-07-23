import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:3001,http://localhost:80,https://gram-care-mru8ufysx-anishas1523-1415s-projects.vercel.app,https://gram-care-ai.vercel.app").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

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
