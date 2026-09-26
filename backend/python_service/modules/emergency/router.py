"""Emergency SOS — trigger, respond, resolve, contacts, hospital escalation.

Planning-doc rules implemented here:
- SOS carries GPS/location, an optional transcribed voice note, and the
  family member concerned.
- Emergency contacts are stored per account and returned to clients so the
  mobile app can run its offline SMS fallback.
- Unacknowledged SOS alerts escalate: after ESCALATION_AFTER_SECONDS the
  alert is (re)assigned to the next-nearest hospital and its escalation
  level increments ("ரெஸ்பான்ஸ் வரலைன்னா அலர்ட் அடுத்த ஹாஸ்பிடலுக்கு
  தானாகவே மாற்றப்படும்").
- Acceptance flips status to RESPONDED — the "Help En Route" state that
  stops double dispatch.
"""
import logging
import math
import os
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from database import get_db
import models
import schemas
from modules.auth.router import get_current_user, require_role, require_approved_doctor
from modules.family.router import resolve_owned_profile
from core.maps import maps_client
from core.cloudinary_service import cloudinary_client
from core.ratelimit import rate_limit

router = APIRouter()
logger = logging.getLogger("gramcare.emergency")

ESCALATION_AFTER_SECONDS = int(os.getenv("SOS_ESCALATION_AFTER_SECONDS", "180"))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance. _nearest_hospital ranks with math.hypot on raw
    degrees, which is fine for ordering but is not a distance — a degree of
    longitude is ~30% shorter than a degree of latitude at this latitude, and
    neither is a kilometre. Anything shown to a family member has to be real.
    """
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return radius_km * 2 * math.asin(math.sqrt(a))


# Straight-line distance understates a real journey; rural roads wind. 1.3 is
# the usual planning multiplier, and 40 km/h is a realistic average for an
# ambulance on district roads rather than a highway figure that would promise
# a family someone will arrive sooner than they can.
_ROAD_WINDING_FACTOR = 1.3
_AMBULANCE_KMH = 40.0


def _tracking_url(sos: models.EmergencySOS) -> Optional[str]:
    """Public tracking link for the patient's contacts. Defined once, on the
    model, so the server's SMS and the phone's message cannot drift apart."""
    return sos.tracking_url


def _distance_and_eta(lat1, lng1, lat2, lng2) -> tuple[Optional[float], Optional[int]]:
    """Road-distance estimate in km and ETA in minutes, or (None, None).

    Tries the Maps Distance Matrix first for a real road route, and falls
    back to the estimate when that is unavailable — which it currently
    always is, because the deployed key has no billing account.
    """
    if None in (lat1, lng1, lat2, lng2):
        return None, None
    try:
        real = maps_client.get_distance_and_eta(lat1, lng1, lat2, lng2)
        if real:
            return (
                round(real["distance_meters"] / 1000.0, 1),
                max(1, round(real["duration_seconds"] / 60)),
            )
    except Exception:
        logger.debug("Distance Matrix unavailable; using the offline estimate.", exc_info=True)

    straight = _haversine_km(lat1, lng1, lat2, lng2)
    road = straight * _ROAD_WINDING_FACTOR
    return round(road, 1), max(1, round(road / _AMBULANCE_KMH * 60))


def _nearest_hospital(
    db: Session,
    lat: Optional[float],
    lng: Optional[float],
    exclude_ids: List[int],
) -> Optional[models.Hospital]:
    # Only approved hospitals. Without this filter, anyone who registered an
    # account with role=HOSPITAL was immediately eligible to be sent a
    # patient's location, name and voice recording.
    q = db.query(models.Hospital).filter(models.Hospital.verification_status == "APPROVED")
    if exclude_ids:
        q = q.filter(~models.Hospital.id.in_(exclude_ids))
    hospitals = q.all()
    if not hospitals:
        return None
    if lat is None or lng is None:
        return hospitals[0]

    # Coarse filter (math) to get top 5 before hitting the API
    def dist(h: models.Hospital) -> float:
        if h.lat is None or h.lng is None:
            return 1e9
        return math.hypot(h.lat - lat, h.lng - lng)

    top_hospitals = sorted(hospitals, key=dist)[:5]

    # Distance Matrix API for exact driving time
    dest_list = [{"id": h.id, "lat": h.lat, "lng": h.lng} for h in top_hospitals if h.lat and h.lng]
    best = maps_client.get_nearest_destination(lat, lng, dest_list)

    if best:
        # Return the actual Hospital object corresponding to best['id']
        return next((h for h in top_hospitals if h.id == best['id']), top_hospitals[0])

    # Fallback to straight line math if API fails
    return top_hospitals[0]


def escalate_stale_sos(db: Session) -> int:
    """Escalate every ACTIVE SOS that has waited too long without a
    response. Called by the startup background loop and directly testable.
    Returns the number of alerts escalated."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(seconds=ESCALATION_AFTER_SECONDS)
    # The escalation clock is last_escalated_at once escalated, else created_at.
    # created_at is never mutated, preserving the true creation time for audit.
    stale = (
        db.query(models.EmergencySOS)
        .filter(
            models.EmergencySOS.status == "ACTIVE",
            func.coalesce(
                models.EmergencySOS.last_escalated_at,
                models.EmergencySOS.created_at,
            )
            <= cutoff,
        )
        .all()
    )
    count = 0
    for sos in stale:
        exclude = [sos.assigned_hospital_id] if sos.assigned_hospital_id else []
        next_hospital = _nearest_hospital(db, sos.location_lat, sos.location_lng, exclude)
        if next_hospital and next_hospital.id != sos.assigned_hospital_id:
            sos.assigned_hospital_id = next_hospital.id
            sos.escalation_level = (sos.escalation_level or 0) + 1
            # Reset the escalation clock only — the new hospital gets a full
            # window — without destroying created_at.
            sos.last_escalated_at = now
            count += 1
            logger.warning(
                "SOS %d escalated to level %d -> hospital %s",
                sos.id, sos.escalation_level, next_hospital.name,
            )
    if count:
        db.commit()
    return count


# ==========================================================
# SOS lifecycle
# ==========================================================

# Exactly the audio types the `filetype` sniffer in CloudinaryClient can
# actually name — it reports "audio/x-wav", not "audio/wav", and an
# allow-list written from intuition silently rejects every upload. Android's
# recorder produces AAC in an MP4 container, which lands as audio/mp4.
SOS_AUDIO_MIMES = [
    "audio/mp4", "audio/aac", "audio/mpeg", "audio/ogg",
    "audio/x-wav", "audio/x-flac", "audio/amr", "audio/x-aiff",
    # An audio-only recording from Android arrives as video/mp4. The phone's
    # MediaMuxer stamps the MPEG-4 container with brand "isom" or "mp42",
    # and a sniffer reading that box reports video/mp4 — only the "M4A "
    # brand reads as audio/mp4, and Android does not write it. Leaving these
    # out rejected every voice note the app recorded.
    #
    # Two of these entries have now been wrong in the same way: the sniffer
    # also says audio/x-wav where "audio/wav" looks obvious. Do not write
    # this list from what the format is called; write it from what the
    # sniffer actually returns, and test it.
    "video/mp4", "video/3gpp",
]

async def _dispatch_sos(db: Session, sos: models.EmergencySOS, patient: models.User,
                        hospital: Optional[models.Hospital]) -> None:
    """Fan a new SOS out to the people who can actually act on it.

    Until this existed, POST /sos/trigger wrote a row and returned. Nobody
    was told: not the hospital it had just been assigned to, not the
    patient's emergency contacts. The patient's screen said "waiting for a
    hospital to respond" while the alert sat in a table waiting for someone
    to happen to refresh a dashboard.

    Every channel here is best-effort and individually guarded: an SOS must
    never fail because a push token expired or an SMS gateway is down, and
    one dead channel must not stop the next one being tried.
    """
    from core.notifications import NotificationService
    from core.sms_service import SMSService

    where = sos.location_text or (
        f"{sos.location_lat:.5f}, {sos.location_lng:.5f}"
        if sos.location_lat is not None and sos.location_lng is not None
        else "location unknown"
    )
    maps_link = (
        f"https://maps.google.com/?q={sos.location_lat},{sos.location_lng}"
        if sos.location_lat is not None and sos.location_lng is not None
        else None
    )
    who = patient.full_name or patient.username

    # 1. The hospital's emergency desk, then its owner as a backstop — a
    #    self-registered hospital may have set neither, which is worth a
    #    warning rather than silence.
    notified_staff = 0
    if hospital:
        staff_ids = {hospital.emergency_desk_user_id, hospital.owner_user_id} - {None}
        if not staff_ids:
            logger.warning(
                "SOS %d assigned to hospital %d (%s) which has no emergency-desk "
                "or owner account — nobody there can be paged.",
                sos.id, hospital.id, hospital.name,
            )
        for staff_id in staff_ids:
            try:
                notified_staff += NotificationService(db).send_notification(
                    user_id=staff_id,
                    title=f"EMERGENCY SOS — {who}",
                    body=f"{where}. Severity {sos.severity or 'unknown'}. Open to respond.",
                    data={"type": "sos_alert", "sos_id": str(sos.id), "status": "ACTIVE"},
                )
            except Exception:
                logger.exception("SOS %d: push to hospital staff %d failed.", sos.id, staff_id)

    # 2. The patient's own emergency contacts, by SMS. This is the channel
    #    that matters most in a village: family reach the patient long
    #    before an ambulance does.
    contacts = (
        db.query(models.EmergencyContact)
        .filter(models.EmergencyContact.user_id == patient.id)
        .all()
    )
    text = f"EMERGENCY: {who} triggered an SOS on GramCare AI. Location: {where}."
    # The tracking page carries the live map, the responding hospital, the
    # distance and ETA, and the voice recording once it exists — far more
    # than a map pin, and it keeps updating after this SMS is sent.
    track = _tracking_url(sos)
    if track:
        text += f" Live updates: {track}"
    elif maps_link:
        text += f" Map: {maps_link}"
    notified_contacts = 0
    for contact in contacts:
        if not contact.phone:
            continue
        try:
            await SMSService().send_sms(contact.phone, text)
            notified_contacts += 1
        except Exception as exc:
            # HTTPException included: an unconfigured or rejecting gateway
            # must not abort the remaining contacts.
            logger.warning("SOS %d: SMS to contact %d failed: %s", sos.id, contact.id, exc)

    logger.info(
        "SOS %d dispatch: hospital=%s staff_pushes=%d contacts_total=%d contacts_sms=%d",
        sos.id, hospital.name if hospital else "none",
        notified_staff, len(contacts), notified_contacts,
    )
    if notified_staff == 0 and notified_contacts == 0:
        logger.error(
            "SOS %d reached NOBODY — no push tokens and no SMS delivery. "
            "Check FIREBASE_SERVICE_ACCOUNT_PATH and MSG91_AUTH_KEY.",
            sos.id,
        )


@router.post("/trigger", response_model=schemas.EmergencySOSResponse, dependencies=[Depends(rate_limit("sos_trigger", 3, 60))])
async def trigger_sos(
    sos_data: schemas.EmergencySOSTrigger,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT"))
):
    """Trigger an Emergency SOS alert (Patient only). Immediately assigned
    to the nearest hospital's emergency desk."""

    resolve_owned_profile(sos_data.family_profile_id, current_user, db)
    hospital = _nearest_hospital(db, sos_data.location_lat, sos_data.location_lng, [])

    loc_text = sos_data.location_text
    if (not loc_text or loc_text == "GPS unavailable" or loc_text == "location unknown") and sos_data.location_lat and sos_data.location_lng:
        geo = maps_client.reverse_geocode(sos_data.location_lat, sos_data.location_lng)
        if geo:
            loc_text = geo

    # Store the recording before the row is written so the URL lands with
    # it. A failed upload must not cost the patient their alert — the
    # transcript and location still get through.
    voice_audio_url = None
    if sos_data.voice_audio_base64:
        try:
            uploaded = cloudinary_client.upload_base64(
                sos_data.voice_audio_base64,
                folder="sos_voice",
                db=db,
                # Cloudinary files audio under its video resource type.
                resource_type="video",
                max_size_bytes=2 * 1024 * 1024,
                allowed_mimes=SOS_AUDIO_MIMES,
            )
            voice_audio_url = (uploaded or {}).get("url")
        except Exception:
            logger.exception("SOS voice recording upload failed for patient %d.", current_user.id)

    db_sos = models.EmergencySOS(
        patient_id=current_user.id,
        family_profile_id=sos_data.family_profile_id,
        location_lat=sos_data.location_lat,
        location_lng=sos_data.location_lng,
        location_text=loc_text,
        voice_note=sos_data.voice_note,
        voice_audio_url=voice_audio_url,
        severity=sos_data.severity,
        status="ACTIVE",
        escalation_level=0,
        assigned_hospital_id=hospital.id if hospital else None,
        public_token=secrets.token_urlsafe(24),
    )
    db.add(db_sos)
    db.commit()
    db.refresh(db_sos)
    logger.info("SOS %d triggered by patient %d (hospital=%s).",
                db_sos.id, current_user.id, hospital.name if hospital else "none")
    if hospital is None:
        # Every SOS ever raised in production was assigned to nobody, because
        # no hospital was registered — while the patient's screen said
        # "waiting for a hospital to respond". An alert with no recipient has
        # to say so, not imply someone is coming.
        logger.error(
            "SOS %d has NO hospital to route to: no APPROVED hospital exists%s. "
            "The patient must be told to call 108 directly.",
            db_sos.id,
            " within range" if db.query(models.Hospital).filter(
                models.Hospital.verification_status == "APPROVED").first() else "",
        )

    # Page the hospital and the patient's emergency contacts. Guarded as a
    # whole as well as per channel: a patient in an emergency must still get
    # their alert id back even if every notification route is broken.
    try:
        await _dispatch_sos(db, db_sos, current_user, hospital)
    except Exception:
        logger.exception("SOS %d: dispatch failed entirely.", db_sos.id)

    if hospital is None:
        # Tell the caller, not just the log. The client shows this instead of
        # a waiting state, because nobody is coming.
        response = schemas.EmergencySOSResponse.model_validate(db_sos)
        response.unrouted_reason = (
            "No approved hospital could receive this alert. Call 108 now. "
            "Your emergency contacts have been notified."
        )
        return response

    return db_sos


@router.get("/active", response_model=List[schemas.EmergencySOSResponse])
async def get_active_emergencies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor("HOSPITAL"))
):
    """All active SOS emergencies (Doctor/Hospital desk/Admin)."""

    return (
        db.query(models.EmergencySOS)
        .filter(models.EmergencySOS.status == "ACTIVE")
        .order_by(models.EmergencySOS.created_at.desc())
        .all()
    )


@router.post("/{sos_id}/voice", response_model=schemas.EmergencySOSResponse)
async def attach_voice_recording(
    sos_id: int,
    payload: schemas.SosVoiceUpload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """Attach the patient's actual recording to an SOS already in flight.

    Recording does not happen during the press: speech_to_text holds the
    microphone through the hold, and an SOS "must happen in a fraction of a
    second" — so the alert fires first and the patient can speak afterwards,
    while help is on its way. That also gives them far longer than the
    three-second hold to say what is wrong.
    """
    sos = (
        db.query(models.EmergencySOS)
        .filter(models.EmergencySOS.id == sos_id,
                models.EmergencySOS.patient_id == current_user.id)
        .first()
    )
    if not sos:
        raise HTTPException(status_code=404, detail="SOS alert not found.")
    if sos.status == "RESOLVED":
        raise HTTPException(status_code=409, detail="This emergency is already resolved.")

    uploaded = cloudinary_client.upload_base64(
        payload.voice_audio_base64,
        folder="sos_voice",
        db=db,
        # Cloudinary files audio under its video resource type.
        resource_type="video",
        max_size_bytes=2 * 1024 * 1024,
        allowed_mimes=SOS_AUDIO_MIMES,
    )
    if not uploaded or not uploaded.get("url"):
        raise HTTPException(status_code=502, detail="Could not store the recording.")

    sos.voice_audio_url = uploaded["url"]
    db.commit()
    db.refresh(sos)
    logger.info("SOS %d: voice recording attached by patient %d.", sos.id, current_user.id)

    # The contacts were SMSed at trigger time, before this recording
    # existed, so they got a location and nothing else. Send the link on
    # once it is there — hearing a relative's own voice is the difference
    # between "something has happened" and knowing what.
    from core.sms_service import SMSService

    who = current_user.full_name or current_user.username
    contacts = (
        db.query(models.EmergencyContact)
        .filter(models.EmergencyContact.user_id == current_user.id)
        .all()
    )
    for contact in contacts:
        if not contact.phone:
            continue
        try:
            await SMSService().send_sms(
                contact.phone,
                f"{who} recorded a voice message with their GramCare AI "
                f"emergency: {sos.voice_audio_url}",
            )
        except Exception as exc:
            logger.warning("SOS %d: voice-link SMS to contact %d failed: %s",
                           sos.id, contact.id, exc)

    return sos


@router.get("/track/{token}", response_model=schemas.SosTrackingResponse)
async def track_sos(token: str, db: Session = Depends(get_db)):
    """Public tracking view for the patient's emergency contacts.

    Unauthenticated by necessity: contacts are phone numbers, not accounts.
    Keyed by a high-entropy capability token that is not derivable from any
    visible identifier, the same model the health passport public view uses.
    The payload is deliberately minimal — see SosTrackingResponse.
    """
    sos = (
        db.query(models.EmergencySOS)
        .filter(models.EmergencySOS.public_token == token)
        .first()
    )
    if not sos:
        raise HTTPException(status_code=404, detail="This tracking link is not valid.")

    patient = db.query(models.User).filter(models.User.id == sos.patient_id).first()
    hospital = (
        db.query(models.Hospital).filter(models.Hospital.id == sos.assigned_hospital_id).first()
        if sos.assigned_hospital_id else None
    )

    distance_km = eta_minutes = None
    if hospital:
        distance_km, eta_minutes = _distance_and_eta(
            hospital.lat, hospital.lng, sos.location_lat, sos.location_lng,
        )

    return schemas.SosTrackingResponse(
        patient_name=(patient.full_name or patient.username) if patient else "Patient",
        status=sos.status,
        severity=sos.severity,
        location_lat=sos.location_lat,
        location_lng=sos.location_lng,
        location_text=sos.location_text,
        voice_note=sos.voice_note,
        voice_audio_url=sos.voice_audio_url,
        hospital_name=hospital.name if hospital else None,
        hospital_phone=hospital.phone if hospital else None,
        hospital_lat=hospital.lat if hospital else None,
        hospital_lng=hospital.lng if hospital else None,
        distance_km=distance_km,
        eta_minutes=eta_minutes,
        # True until the Distance Matrix API is reachable; the page says so
        # rather than presenting a guess as a road ETA.
        eta_is_estimate=not maps_client.configured if hasattr(maps_client, "configured") else True,
        escalation_level=sos.escalation_level or 0,
        created_at=sos.created_at,
        resolved_at=sos.resolved_at,
    )


@router.get("/mine", response_model=List[schemas.EmergencySOSResponse])
async def my_sos_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The caller's own SOS alerts — lets the patient app show delivery/
    "Help En Route" status."""
    return (
        db.query(models.EmergencySOS)
        .filter(models.EmergencySOS.patient_id == current_user.id)
        .order_by(models.EmergencySOS.created_at.desc())
        .limit(20)
        .all()
    )


@router.put("/{sos_id}/respond", response_model=schemas.EmergencySOSResponse)
async def respond_to_sos(
    sos_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_approved_doctor("HOSPITAL"))
):
    """A doctor or hospital desk accepts an SOS ("Help En Route")."""

    sos = db.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS not found.")

    if sos.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="SOS is already being handled or resolved.")

    sos.status = "RESPONDED"
    sos.responded_by = current_user.id
    db.commit()
    db.refresh(sos)
    
    from core.notifications import NotificationService
    NotificationService(db).notify_sos_alert(
        user_id=sos.patient_id,
        hospital_name=current_user.full_name or "Emergency Desk",
        status="RESPONDED"
    )
    
    return sos


@router.put("/{sos_id}/resolve", response_model=schemas.EmergencySOSResponse)
async def resolve_sos(
    sos_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark an SOS as resolved."""
    sos = db.query(models.EmergencySOS).filter(models.EmergencySOS.id == sos_id).first()
    if not sos:
        raise HTTPException(status_code=404, detail="SOS not found.")

    if current_user.role not in ["ADMIN"] and sos.responded_by != current_user.id and sos.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to resolve this SOS.")

    sos.status = "RESOLVED"
    sos.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sos)
    
    from core.notifications import NotificationService
    NotificationService(db).notify_sos_alert(
        user_id=sos.patient_id,
        hospital_name=current_user.full_name or "Emergency Desk",
        status="RESOLVED"
    )
    
    return sos


# ==========================================================
# Emergency contacts
# ==========================================================

@router.get("/contacts", response_model=List[schemas.EmergencyContactResponse])
async def list_contacts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.EmergencyContact)
        .filter(models.EmergencyContact.user_id == current_user.id)
        .order_by(models.EmergencyContact.created_at)
        .all()
    )


@router.post("/contacts", response_model=schemas.EmergencyContactResponse, status_code=201)
async def add_contact(
    contact: schemas.EmergencyContactCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = (
        db.query(models.EmergencyContact)
        .filter(models.EmergencyContact.user_id == current_user.id)
        .count()
    )
    if count >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 emergency contacts.")
    db_contact = models.EmergencyContact(user_id=current_user.id, **contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    contact = (
        db.query(models.EmergencyContact)
        .filter(
            models.EmergencyContact.id == contact_id,
            models.EmergencyContact.user_id == current_user.id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return None
