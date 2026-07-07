import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    # Disabled under pytest (TESTING=1) — tests call escalate_stale_sos directly.
    if os.getenv("TESTING") != "1":
        task = asyncio.create_task(_sos_escalation_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="GramCare AI Backend",
    description="Central Nervous System for the Patient, Doctor, and Pharmacy Suites.",
    version="1.0.0",
    lifespan=lifespan,
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
