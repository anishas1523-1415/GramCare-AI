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

from database import get_db
import models

router = APIRouter()


@router.get("/{token}")
def get_file(token: str, db: Session = Depends(get_db)):
    stored = db.query(models.StoredFile).filter(models.StoredFile.token == token).first()
    if not stored:
        raise HTTPException(status_code=404, detail="File not found.")
    return Response(
        content=stored.data,
        media_type=stored.content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
