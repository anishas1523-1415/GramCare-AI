"""Cloudinary-backed file storage for the images/documents the platform
already has fields or transient payloads for but nowhere durable to put:
family profile photos (models.FamilyProfile.photo_url), symptom/prescription/
invoice photos submitted to the AI Symptom Checker and OCR endpoints
(previously analyzed once and discarded), and lab report scans
(schemas.LabReportSubmit.file_url).

Mirrors core/maps.py's client pattern exactly: a single client instance,
initialized from env vars, that degrades to returning None (never raises)
when unconfigured, so the rest of the app works identically with or without
Cloudinary credentials present — matching MapsClient/AIManager's established
"missing external credential is not a startup failure" convention.
"""
import base64
import io
import logging
import os
import filetype
from typing import Any, Dict, Optional

import cloudinary
import cloudinary.uploader

logger = logging.getLogger("gramcare.cloudinary")


class CloudinaryClient:
    def __init__(self):
        self.cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        self.api_key = os.getenv("CLOUDINARY_API_KEY")
        self.api_secret = os.getenv("CLOUDINARY_API_SECRET")
        self.configured = False

        if self.cloud_name and self.api_key and self.api_secret:
            try:
                cloudinary.config(
                    cloud_name=self.cloud_name,
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    secure=True,
                )
                self.configured = True
                logger.info("Cloudinary client initialized (cloud=%s).", self.cloud_name)
            except Exception as e:
                logger.error("Failed to initialize Cloudinary client: %s", e)
        else:
            logger.warning("CLOUDINARY_* env vars missing. File uploads will be skipped/mocked.")

    @staticmethod
    def _decode(data: str) -> bytes:
        # Accept both a raw base64 string and a data URI
        # ("data:image/jpeg;base64,...") — mobile/web clients send either.
        if "," in data and data.strip().lower().startswith("data:"):
            data = data.split(",", 1)[1]
        return base64.b64decode(data)

    def upload_base64(
        self,
        data: str,
        folder: str,
        resource_type: str = "auto",
        public_id: Optional[str] = None,
        max_size_bytes: int = 10 * 1024 * 1024,
        allowed_mimes: Optional[list[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Uploads a base64-encoded file and returns `{"url", "public_id",
        "resource_type", "bytes"}`, or None if Cloudinary isn't configured or
        the upload fails — callers must treat storage as best-effort and
        never let it block the primary action (AI analysis, record
        creation, etc.), same convention as NotificationService."""
        if allowed_mimes is None:
            allowed_mimes = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
            
        if not self.configured:
            return None
        try:
            file_bytes = self._decode(data)
            
            # Size validation
            if len(file_bytes) > max_size_bytes:
                logger.error("Upload rejected: File size %d exceeds limit of %d bytes", len(file_bytes), max_size_bytes)
                return None
                
            # MIME type validation
            kind = filetype.guess(file_bytes)
            mime_type = kind.mime if kind else None
            
            if not mime_type or mime_type not in allowed_mimes:
                logger.error("Upload rejected: Invalid MIME type %s", mime_type)
                return None

            result = cloudinary.uploader.upload(
                io.BytesIO(file_bytes),
                folder=folder,
                resource_type=resource_type,
                public_id=public_id,
                overwrite=bool(public_id),
            )
            return {
                "url": result.get("secure_url"),
                "public_id": result.get("public_id"),
                "resource_type": result.get("resource_type"),
                "bytes": result.get("bytes"),
            }
        except Exception as e:
            logger.error("Cloudinary upload failed (folder=%s): %s", folder, e)
            return None

    def delete(self, public_id: str, resource_type: str = "image") -> bool:
        if not self.configured:
            return False
        try:
            res = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return res.get("result") == "ok"
        except Exception as e:
            logger.error("Cloudinary delete failed (public_id=%s): %s", public_id, e)
            return False


cloudinary_client = CloudinaryClient()
