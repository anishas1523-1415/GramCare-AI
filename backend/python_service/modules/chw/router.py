"""Community Health Worker (CHW) tooling.

CHW is a new user role, same tier as PATIENT/DOCTOR/HOSPITAL/LAB. A field
health worker registers a walk-in villager who may have no phone, email, or
literacy to self-register, and can then act on that patient's behalf for
triage and booking.

Design contract (deliberate, see the roadmap task this was built from):
- A CHW-registered patient IS a real PATIENT account. Registration here
  auto-generates a username + temporary password and creates an ordinary
  `models.User(role="PATIENT")` row — every existing patient feature
  (triage, booking, prescriptions, EHR, family profiles, ...) works for them
  completely unmodified. The only CHW-specific things are (a) the
  simplified registration flow itself and (b) the two "act on behalf of"
  proxy endpoints below.
- `models.User.registered_by_chw_id` is both the audit trail ("who
  registered this patient") and the authorization boundary: a CHW may only
  triage/book for patients where that column points at their own id — a
  403 otherwise, even for a patient who exists and is a real PATIENT.
- Triage and booking are NOT reimplemented here. This module calls straight
  into the same core logic the patient-facing endpoints use
  (ai_triage.router.run_triage_analysis, appointments.router.
  _book_appointment_core), attributing the result to the PATIENT's id, not
  the CHW's — so a walk-in patient's triage log / appointment looks exactly
  like one they created themselves.
- Paid bookings: the payment requirement is intentionally NOT bypassed. A
  doctor with consultation_fee > 0 still requires a payment_order_id whose
  Payment.patient_id matches the target patient's id — i.e. the patient (or
  someone signed in as the patient with the credentials issued at
  registration) must complete POST /payments/create-order +
  POST /payments/verify under the patient's own account first. There is no
  "CHW collects cash" concept implemented — see the accompanying report for
  why that was deliberately left out rather than invented ad hoc.
"""
import logging
import random
import re
import secrets
import string
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from modules.auth.router import require_role
from modules.auth.utils import get_password_hash
from modules.appointments.router import _book_appointment_core
from modules.ai_triage.router import run_triage_analysis, TriageResponse
from core.ratelimit import rate_limit

router = APIRouter()
logger = logging.getLogger("gramcare.chw")

_USERNAME_ALPHABET = string.digits
# Excludes visually-ambiguous characters (0/O, 1/I/l) — this password gets
# hand-copied onto paper by a CHW in the field and read back by, or to, the
# patient later.
_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


def _slugify_name(full_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", full_name.lower())
    return slug[:20] or "patient"


def _generate_username(db: Session, full_name: str) -> str:
    """Slugified name + a short random numeric suffix, retried on collision.
    E.g. "Muthu Selvam" -> "muthuselvam4821"."""
    base = _slugify_name(full_name)
    for _ in range(25):
        suffix = "".join(random.choices(_USERNAME_ALPHABET, k=4))
        candidate = f"{base}{suffix}"
        if not db.query(models.User).filter(models.User.username == candidate).first():
            return candidate
    # Astronomically unlikely (25 collisions in a row), but never loop
    # forever — fall back to a wider random suffix.
    return f"{base}{secrets.token_hex(4)}"


def _generate_temp_password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(10))


def _owned_patient(patient_id: int, chw: models.User, db: Session) -> models.User:
    """The target of a CHW proxy action: must be a real PATIENT that THIS
    CHW registered (or the caller is ADMIN, mirroring the same admin-bypass
    convention used by modules/family/router.py's resolve_owned_profile)."""
    patient = (
        db.query(models.User)
        .filter(models.User.id == patient_id, models.User.role == "PATIENT")
        .first()
    )
    if not patient or (patient.registered_by_chw_id != chw.id and chw.role != "ADMIN"):
        raise HTTPException(status_code=403, detail="You did not register this patient.")
    return patient


@router.post(
    "/register-patient",
    response_model=schemas.CHWPatientRegisterResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("chw_register_patient", 30, 3600))],
)
async def register_patient(
    body: schemas.CHWPatientRegister,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("CHW")),
):
    """Registers a walk-in villager as a real PATIENT account. Auto-generates
    a username + temporary password (returned once, in plaintext, in this
    response only) instead of asking for one, since the patient may be
    unable to read/choose either. `registered_by_chw_id` is set to the
    CHW's own id — the flag "later look-up" (GET /chw/my-patients) and every
    ownership check below key off.
    """
    username = _generate_username(db, body.full_name)
    temp_password = _generate_temp_password()

    # Villagers frequently have no email at all — the `email` column is
    # unique/used for login lookups elsewhere in the app, so a stable,
    # clearly-fake placeholder (never a real mailbox) is synthesized from
    # the just-generated, guaranteed-unique username rather than leaving the
    # column null (which would collide across every emailless registration
    # once more than one exists, since a unique index treats NULLs as
    # distinct only for a subset of databases and this repo doesn't rely on
    # that inconsistency).
    placeholder_email = f"chw.{username}@no-email.gramcare.local"

    new_user = models.User(
        username=username,
        email=placeholder_email,
        hashed_password=get_password_hash(temp_password),
        full_name=body.full_name,
        role="PATIENT",
        phone=body.phone,
        # PATIENT login is never gated on is_verified (see modules/auth/
        # router.py's login()), but there is no real inbox behind
        # placeholder_email for a verification link to reach anyway, so this
        # is set True for clarity rather than left to default to False.
        is_verified=True,
        registered_by_chw_id=current_user.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Full registration context (age/gender/address — not stored as
    # queryable columns on User, see schemas.CHWPatientRegister) lives here,
    # attributed to the acting CHW — the audit trail the roadmap task asked
    # for, mirroring the AuditLog pattern already used for government
    # account creation and lab report submission.
    db.add(models.AuditLog(
        user_id=current_user.id,
        action="CREATE",
        resource="CHWPatientRegistration",
        resource_id=str(new_user.id),
        details={
            "full_name": body.full_name,
            "age": body.age,
            "gender": body.gender,
            "phone": body.phone,
            "address_note": body.address_note,
            "generated_username": username,
        },
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    logger.info(
        "CHW %d (%s) registered patient %d (%s) on behalf of a walk-in villager.",
        current_user.id, current_user.username, new_user.id, username,
    )

    return schemas.CHWPatientRegisterResponse(
        id=new_user.id,
        username=username,
        temporary_password=temp_password,
        full_name=new_user.full_name,
    )


@router.get("/my-patients", response_model=List[schemas.CHWPatientSummary])
async def my_patients(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("CHW")),
):
    """Patients this CHW registered, most recently registered first."""
    return (
        db.query(models.User)
        .filter(models.User.registered_by_chw_id == current_user.id)
        .order_by(models.User.created_at.desc())
        .all()
    )


@router.post(
    "/patients/{patient_id}/triage",
    response_model=TriageResponse,
    dependencies=[Depends(rate_limit("chw_triage", 20, 300))],
)
async def triage_for_patient(
    patient_id: int,
    body: schemas.CHWTriageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("CHW")),
):
    """Runs the same AI triage engine patients use themselves
    (ai_triage.router.run_triage_analysis), attributed to the PATIENT's own
    id — the resulting TriageLog row is indistinguishable from one the
    patient ran on their own phone."""
    patient = _owned_patient(patient_id, current_user, db)
    return await run_triage_analysis(
        db,
        patient,
        body.symptoms_text,
        body.age,
        family_profile_id=body.family_profile_id,
        image_base64=body.image_base64,
    )


@router.post(
    "/patients/{patient_id}/book",
    response_model=schemas.AppointmentResponse,
    dependencies=[Depends(rate_limit("chw_book_appointment", 10, 300))],
)
async def book_for_patient(
    patient_id: int,
    body: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("CHW")),
):
    """Books a consultation for the patient using the exact same booking
    logic and payment enforcement as POST /appointments/book
    (appointments.router._book_appointment_core) — see the module
    docstring's note on why paid bookings still require the patient's own
    verified Payment row rather than a CHW-side bypass."""
    patient = _owned_patient(patient_id, current_user, db)
    return await _book_appointment_core(body, db, patient)
