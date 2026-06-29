from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.ai_triage.router import router as ai_triage_router
from modules.ehr_sync.router import router as ehr_sync_router
from modules.pharmacy_inventory.router import router as pharmacy_router
import models
from database import engine

# Create the database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GramCare AI Backend",
    description="Central Nervous System for the Patient, Doctor, and Pharmacy Suites.",
    version="1.0.0"
)

# Configure CORS for our local React/Next.js apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev purposes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(ai_triage_router, prefix="/api/v1/triage", tags=["AI Triage"])
app.include_router(ehr_sync_router, prefix="/api/v1/ehr", tags=["EHR Sync"])
app.include_router(pharmacy_router, prefix="/api/v1/pharmacy", tags=["Pharmacy Inventory"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the GramCare AI API. System is fully operational."}
