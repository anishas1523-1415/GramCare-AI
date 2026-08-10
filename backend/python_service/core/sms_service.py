import os
import logging
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("gramcare.sms_service")


class SMSService:
    def __init__(self):
        self.auth_key = os.getenv("MSG91_AUTH_KEY")
        self.sender_id = os.getenv("MSG91_SENDER_ID", "")
        self.template_id = os.getenv("MSG91_TEMPLATE_ID", "")
        # A separate DLT template is required for free-text transactional SMS
        # (appointment reminders etc.) — MSG91's OTP product and its Flow/SMS
        # product each need their OWN DLT-approved template, they are not
        # interchangeable. Falls back to MSG91_TEMPLATE_ID only so a
        # single-template setup still works during initial rollout.
        self.sms_template_id = os.getenv("MSG91_SMS_TEMPLATE_ID", self.template_id)
        self.base_url = "https://control.msg91.com/api/v5"

    def _require_configured(self, template_id: str, purpose: str):
        """Fail fast and loud rather than let MSG91 reject the call with a
        cryptic error: India's DLT regulations mean MSG91 will refuse any
        OTP/SMS sent without an approved template_id regardless of whether
        auth_key is valid, so a missing template_id is never "send this
        without a template" — it's a guaranteed rejection. Surfacing that
        here, in our own logs, is more useful than making an API call we
        already know will fail."""
        if not self.auth_key:
            logger.error("MSG91_AUTH_KEY is not set — cannot send %s.", purpose)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"SMS delivery is not configured on the server (missing MSG91_AUTH_KEY) — cannot send {purpose}.",
            )
        if not template_id:
            logger.error("No MSG91 template_id configured for %s — MSG91 will reject un-templated sends under India's DLT rules.", purpose)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"SMS delivery is not configured on the server (missing a DLT-approved MSG91 template_id) — cannot send {purpose}.",
            )

    async def send_otp(self, phone_number: str, otp: str) -> dict:
        """Sends an OTP via MSG91's OTP product (POST /api/v5/otp), passing
        our own pre-generated `otp` so MSG91 delivers exactly the code
        /auth/phone/send-otp already stored in PhoneOTP — verification stays
        self-hosted (see modules/auth/router.py's send_phone_otp), MSG91 is
        used purely as the SMS carrier here."""
        self._require_configured(self.template_id, "an OTP")

        headers = {"authkey": self.auth_key, "Content-Type": "application/json"}
        params = {
            "mobile": phone_number,
            "otp": otp,
            "template_id": self.template_id,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(f"{self.base_url}/otp", headers=headers, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            # MSG91's error body (invalid template, DLT rejection, exhausted
            # balance, bad auth key, etc.) is exactly what's needed to
            # diagnose a delivery failure — log it in full instead of
            # discarding it behind a generic message.
            logger.error("MSG91 OTP send failed (%s): %s", e.response.status_code, e.response.text)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send OTP — SMS provider rejected the request.")
        except Exception as e:
            logger.error("MSG91 OTP send failed: %s", e)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send OTP — SMS provider is unreachable.")

    async def send_sms(self, phone_number: str, message: str) -> dict:
        """Sends a transactional SMS (appointment reminders, SOS) via MSG91's
        current Flow API (POST /api/v5/flow) — the v2 sendsms endpoint this
        used to call is deprecated and many MSG91 accounts created after the
        DLT rollout don't have v2 API access enabled at all, which fails
        every single call regardless of auth_key/credit validity. The Flow
        API requires a DLT-approved template with a single free-text
        variable (commonly named VAR1) that the template's approved wording
        must actually contain, e.g. "Your GramCare update: {{VAR1}}"."""
        self._require_configured(self.sms_template_id, "an SMS")

        headers = {"authkey": self.auth_key, "Content-Type": "application/json"}
        payload = {
            "template_id": self.sms_template_id,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": f"91{phone_number.lstrip('+').removeprefix('91')}",
                    "VAR1": message,
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(f"{self.base_url}/flow", headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("MSG91 SMS send failed (%s): %s", e.response.status_code, e.response.text)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send SMS — SMS provider rejected the request.")
        except Exception as e:
            logger.error("MSG91 SMS send failed: %s", e)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send SMS — SMS provider is unreachable.")


# Dependency injection method
def get_sms_service() -> SMSService:
    return SMSService()
