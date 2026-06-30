import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Import Routers
from modules.auth.router import router as auth_router
from modules.ai_triage.router import router as ai_triage_router
from modules.ehr_sync.router import router as ehr_sync_router
from modules.pharmacy_inventory.router import router as pharmacy_router
from modules.payments.router import router as payments_router
from modules.appointments.router import router as appointments_router
from modules.emergency.router import router as emergency_router

app = FastAPI(
    title="GramCare AI Backend",
    description="Central Nervous System for the Patient, Doctor, and Pharmacy Suites.",
    version="1.0.0"
)

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:3001,http://localhost:80").split(",")

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

@app.get("/")
def read_root():
    return {"message": "Welcome to the GramCare AI API. System is fully operational."}
