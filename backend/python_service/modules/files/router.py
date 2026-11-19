"""Serves files held in the application database.

CloudinaryClient falls back to storing uploads as models.StoredFile rows
when CLOUDINARY_* credentials are absent, and hands back a URL pointing
here. Reads are unauthenticated and keyed by a high-entropy capability
token — the same model the Health Passport public view uses, and for the
same reason: these URLs are embedded in records (a doctor's license scan
reviewed by a government official, a profile photo rendered in the patient
directory) that are read by clients which may not carry the uploader's
session. The token is not derivable from any user-visible identifier, so
the store cannot be enumerated.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.ratelimit import rate_limit
from database import get_db
import models

router = APIRouter()


@router.get(
    "/{token}",
    # Experiment G found this endpoint unthrottled, unlike the health-passport
    # view it is modelled on. The 192-bit token is what makes the store
    # unenumerable; this caps how fast it can be hammered, and how fast a
    # leaked token can be scraped. Generous, because a single page may embed
    # several of these (a profile photo, a licence scan, an OCR source).
    dependencies=[Depends(rate_limit("file_fetch", 120, 60))],
)
def get_file(token: str, db: Session = Depends(get_db)):
    stored = db.query(models.StoredFile).filter(models.StoredFile.token == token).first()
    if not stored:
        raise HTTPException(status_code=404, detail="File not found.")
    return Response(
        content=stored.data,
        media_type=stored.content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
