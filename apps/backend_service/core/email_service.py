import os
import logging
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("gramcare.email_service")

class EmailService:
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")
        self.base_url = "https://api.resend.com"

    async def send_email(self, to_email: str, subject: str, html_content: str, from_email: str = "onboarding@resend.dev") -> dict:
        """
        Sends an email using the Resend REST API.
        Prepared for onboarding, auth, and notifications.
        """
        if not self.api_key:
            logger.warning("RESEND_API_KEY not set. Skipping email send.")
            return {"status": "skipped", "message": "No API key configured"}

        # Resend payload matches the standard documented structure
        payload = {
            "from": from_email,
            "to": to_email if isinstance(to_email, list) else [to_email],
            "subject": subject,
            "html": html_content
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/emails",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to send email via Resend: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send email")

# Dependency injection method
def get_email_service() -> EmailService:
    return EmailService()
