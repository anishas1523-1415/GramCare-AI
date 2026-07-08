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
        self.route = os.getenv("MSG91_ROUTE", "4")
        self.base_url = "https://control.msg91.com/api/v5"

    async def send_otp(self, phone_number: str, otp: str) -> dict:
        """
        Sends an OTP using MSG91.
        Prepared for integration with authentication flow.
        """
        if not self.auth_key:
            logger.warning("MSG91_AUTH_KEY not set. Skipping OTP send.")
            return {"status": "skipped", "message": "No auth key configured"}

        payload = {
            "mobile": phone_number,
            "otp": otp
        }
        
        headers = {
            "authkey": self.auth_key,
            "Content-Type": "application/json"
        }

        try:
            # Note: MSG91 OTP API typically uses GET/POST with query parameters 
            # for backward compatibility, but supports POST body as well in some iterations.
            # We will use query parameters according to their standard API.
            params = {
                "mobile": phone_number,
                "otp": otp
            }
            if self.template_id:
                params["template_id"] = self.template_id

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/otp",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to send OTP via MSG91: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP")

    async def send_sms(self, phone_number: str, message: str) -> dict:
        """
        Sends a standard SMS using MSG91.
        Prepared for integration with appointment reminders and emergency SOS.
        Note: Indian DLT requires a template_id for production use.
        """
        if not self.auth_key:
            logger.warning("MSG91_AUTH_KEY not set. Skipping SMS send.")
            return {"status": "skipped", "message": "No auth key configured"}

        # If a template ID is configured, we should use the V5 Flow API
        # which requires variables rather than raw text. Since the current signature
        # only takes `message`, if DLT templates are later used, this payload
        # will need to map `message` to the appropriate flow variable (e.g. "VAR1").
        
        # For now, to support sending raw un-templated text (e.g., international
        # or testing before DLT approval), we must use the V2 sendsms endpoint.
        # The V5 /flow/ endpoint strictly rejects raw text without a template_id.
        
        payload = {
            "sender": self.sender_id,
            "route": self.route,
            "country": "91",
            "sms": [
                {
                    "message": message,
                    "to": [phone_number]
                }
            ]
        }
        
        headers = {
            "authkey": self.auth_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                # Using the V2 API for raw text payload.
                response = await client.post(
                    "https://api.msg91.com/api/v2/sendsms",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to send SMS via MSG91: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send SMS")

# Dependency injection method
def get_sms_service() -> SMSService:
    return SMSService()
