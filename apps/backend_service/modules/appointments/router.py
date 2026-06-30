import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
from modules.auth.router import get_current_user

router = APIRouter()
logger = logging.getLogger("gramcare.appointments")

@router.post("/book", response_model=schemas.AppointmentResponse)
async def book_appointment(
    appointment: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Book a new appointment as a patient."""
    if current_user.role != "PATIENT":
        raise HTTPException(status_code=403, detail="Only patients can book appointments.")
        
    doctor = db.query(models.User).filter(models.User.id == appointment.doctor_id, models.User.role == "DOCTOR").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")
        
    db_appointment = models.Appointment(
        patient_id=current_user.id,
        doctor_id=appointment.doctor_id,
        scheduled_at=appointment.scheduled_at,
        triage_summary=appointment.triage_summary,
        status="CONFIRMED" # Auto-confirm for demo purposes
    )
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    logger.info("Appointment %d booked successfully for patient %d.", db_appointment.id, current_user.id)
    return db_appointment

@router.get("/doctor/{doctor_id}/queue", response_model=List[schemas.AppointmentResponse])
async def get_doctor_queue(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get the queue of upcoming appointments for a doctor."""
    if current_user.role not in ["DOCTOR", "ADMIN"] or (current_user.role == "DOCTOR" and current_user.id != doctor_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this doctor's queue.")
        
    appointments = db.query(models.Appointment).filter(
        models.Appointment.doctor_id == doctor_id,
        models.Appointment.status.in_(["PENDING", "CONFIRMED"])
    ).order_by(models.Appointment.scheduled_at).all()
    return appointments

@router.put("/{appointment_id}", response_model=schemas.AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    update_data: schemas.AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update appointment status or add consultation notes (Doctor only)."""
    appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found.")
        
    if current_user.role == "DOCTOR" and appointment.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this appointment.")
        
    if update_data.status:
        appointment.status = update_data.status
    if update_data.consultation_notes:
        appointment.consultation_notes = update_data.consultation_notes
        
    db.commit()
    db.refresh(appointment)
    return appointment
