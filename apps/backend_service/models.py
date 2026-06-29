from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime
from database import Base

class EHRRecord(Base):
    __tablename__ = "ehr_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    record_type = Column(String) # e.g., 'prescription', 'lab_report'
    content = Column(String)
    doctor_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class PharmacyItem(Base):
    __tablename__ = "pharmacy_inventory"

    id = Column(Integer, primary_key=True, index=True)
    pharmacy_id = Column(String, index=True)
    medicine_name = Column(String, index=True)
    stock_count = Column(Integer, default=0)
    price = Column(Float, default=0.0)
    requires_prescription = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
