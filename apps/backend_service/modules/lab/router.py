"""Laboratory module — booking, sample-status lifecycle, report upload, and
Health Wallet integration.

Planning-doc contract (standalone Laboratory web app, its own role, LAB):
- Patients search a curated test catalog (fasting/prep instructions
  included), then book a test at a nearby lab center, optionally with home
  sample collection ("ஹோம் சாம்பிள் கலெக்ஷன்").
- Lab staff move a booking through BOOKED -> SAMPLE_COLLECTED -> PROCESSING
  -> REPORT_READY, then upload the structured result.
- The moment a report is submitted it is (a) pushed to the patient via FCM
  and (b) written into the patient's Family Health Wallet as an EHRRecord —
  the same auto-save behavior the planning doc requires for doctor
  prescriptions ("இது ரெக்கார்ட்ஸ் தானாகவே பேஷன்ட்டோட ஆப்புக்குள்ள வரும்").
"""
import math
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import get_current_user, require_role
from modules.family.router import resolve_owned_profile
from core.lab_tests import search_tests, get_test, full_catalog
from core.notifications import NotificationService
from core.ratelimit import rate_limit

router = APIRouter()


def _my_lab(user: models.User, db: Session) -> models.LabCenter:
    lab = (
        db.query(models.LabCenter)
        .filter(models.LabCenter.owner_user_id == user.id)
        .first()
    )
    if not lab:
        raise HTTPException(
            status_code=409,
            detail="No lab center registered for this account yet. POST /lab/register first.",
        )
    return lab


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ==========================================================
# Lab center registration / profile
# ==========================================================

@router.post("/register", response_model=schemas.LabCenterResponse)
async def register_lab(
    body: schemas.LabCenterCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("LAB")),
):
    lab = db.query(models.LabCenter).filter(models.LabCenter.owner_user_id == current_user.id).first()
    if lab:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(lab, field, value)
    else:
        lab = models.LabCenter(owner_user_id=current_user.id, **body.model_dump())
        db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


@router.get("/me", response_model=schemas.LabCenterResponse)
async def my_lab(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("LAB")),
):
    return _my_lab(current_user, db)


# ==========================================================
# Test catalog (patient-facing search + prep instructions)
# ==========================================================

@router.get("/tests", response_model=List[schemas.LabTestInfo])
async def list_tests(
    query: Optional[str] = Query(None, min_length=1),
    current_user: models.User = Depends(get_current_user),
):
    """Full catalog, or filtered by name/category — includes fasting/prep
    instructions per test (planning doc requirement)."""
    return search_tests(query) if query else full_catalog()


@router.get("/centers", response_model=List[schemas.LabCenterResponse])
async def nearby_labs(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(50.0, gt=0, le=300),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Active lab centers, nearest-first when location is supplied."""
    labs = db.query(models.LabCenter).filter(models.LabCenter.is_active == True).all()  # noqa: E712
    if lat is not None and lng is not None:
        def dist(l):
            if l.lat is None or l.lng is None:
                return 1e9
            return _haversine_km(lat, lng, l.lat, l.lng)
        labs = [l for l in labs if dist(l) <= radius_km]
        labs.sort(key=dist)
    return labs


# ==========================================================
# Booking lifecycle
# ==========================================================

@router.post(
    "/bookings",
    response_model=schemas.LabBookingResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("lab_booking", 20, 300))],
)
async def book_test(
    body: schemas.LabBookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    lab = db.query(models.LabCenter).filter(models.LabCenter.id == body.lab_center_id).first()
    if not lab or not lab.is_active:
        raise HTTPException(status_code=404, detail="Lab center not found")
    if body.home_collection and not lab.offers_home_collection:
        raise HTTPException(status_code=400, detail="This lab does not offer home sample collection")

    resolve_owned_profile(body.family_profile_id, current_user, db)

    booking = models.LabBooking(
        patient_id=current_user.id,
        family_profile_id=body.family_profile_id,
        lab_center_id=body.lab_center_id,
        test_name=body.test_name,
        home_collection=body.home_collection,
        scheduled_at=body.scheduled_at,
        notes=body.notes,
        status="BOOKED",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/bookings/mine", response_model=List[schemas.LabBookingResponse])
async def my_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    return (
        db.query(models.LabBooking)
        .filter(models.LabBooking.patient_id == current_user.id)
        .order_by(models.LabBooking.created_at.desc())
        .all()
    )


@router.get("/bookings/queue", response_model=List[schemas.LabBookingResponse])
async def lab_queue(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("LAB")),
):
    """The caller's own lab's bookings still requiring action (collection,
    processing, or report entry) — REPORT_READY/COMPLETED/CANCELLED bookings
    have nothing left for the lab to do, so they drop off this list, oldest
    first so the front desk works through them in order."""
    lab = _my_lab(current_user, db)
    return (
        db.query(models.LabBooking)
        .filter(
            models.LabBooking.lab_center_id == lab.id,
            models.LabBooking.status.in_(["BOOKED", "SAMPLE_COLLECTED", "PROCESSING"]),
        )
        .order_by(models.LabBooking.created_at.asc())
        .all()
    )


def _owned_booking(booking_id: int, lab: models.LabCenter, db: Session) -> models.LabBooking:
    booking = (
        db.query(models.LabBooking)
        .filter(models.LabBooking.id == booking_id, models.LabBooking.lab_center_id == lab.id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.put("/bookings/{booking_id}/status", response_model=schemas.LabBookingResponse)
async def update_booking_status(
    booking_id: int,
    status: str = Query(..., pattern="^(SAMPLE_COLLECTED|PROCESSING|CANCELLED)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("LAB")),
):
    lab = _my_lab(current_user, db)
    booking = _owned_booking(booking_id, lab, db)
    if booking.status in ("REPORT_READY", "COMPLETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Booking already {booking.status.lower()}")
    booking.status = status
    db.commit()
    db.refresh(booking)
    return booking


@router.post("/bookings/{booking_id}/report", response_model=schemas.LabBookingResponse)
async def submit_report(
    booking_id: int,
    body: schemas.LabReportSubmit,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("LAB")),
):
    """Uploads the structured result and — per the planning doc's
    "records must flow into the Health Wallet automatically" rule — writes a
    matching EHRRecord into the patient's wallet in the same transaction,
    plus pushes an FCM notification."""
    lab = _my_lab(current_user, db)
    booking = _owned_booking(booking_id, lab, db)
    if booking.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="Booking already completed")

    booking.report_payload = body.model_dump()
    booking.report_ready_at = datetime.utcnow()
    booking.status = "REPORT_READY"

    values_summary = "; ".join(
        f"{v.parameter}: {v.value}{(' ' + v.unit) if v.unit else ''}"
        + (f" (ref: {v.reference_range})" if v.reference_range else "")
        for v in body.values
    ) or "See attached report"

    wallet_record = models.EHRRecord(
        patient_id=booking.patient_id,
        family_profile_id=booking.family_profile_id,
        record_type="lab_report",
        title=booking.test_name,
        content=f"{booking.test_name} — {body.summary or values_summary}",
        payload={
            "test_name": booking.test_name,
            "values": [v.model_dump() for v in body.values],
            "summary": body.summary,
            "file_url": body.file_url,
            "lab_center_id": lab.id,
            "lab_center_name": lab.name,
        },
        doctor_name=lab.name,  # attribution field doubles as "issued by"
    )
    db.add(wallet_record)
    db.commit()
    db.refresh(booking)

    try:
        NotificationService(db).notify_lab_report_ready(booking.patient_id, booking.test_name)
    except Exception:
        pass  # notification failure must never block the report being saved

    return booking


@router.put("/bookings/{booking_id}/complete", response_model=schemas.LabBookingResponse)
async def mark_completed(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Patient (or the lab) acknowledges the report has been viewed."""
    booking = db.query(models.LabBooking).filter(models.LabBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if current_user.role == "PATIENT" and booking.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    if current_user.role == "LAB":
        lab = _my_lab(current_user, db)
        if booking.lab_center_id != lab.id:
            raise HTTPException(status_code=403, detail="Not your lab's booking")
    if booking.status != "REPORT_READY":
        raise HTTPException(status_code=400, detail="Report not ready yet")
    booking.status = "COMPLETED"
    db.commit()
    db.refresh(booking)
    return booking
