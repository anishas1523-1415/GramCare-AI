import asyncio
from dotenv import load_dotenv
from core.email_service import get_email_service

async def main():
    # Load environment variables from .env
    load_dotenv()
    
    # Initialize our backend's email service
    email_service = get_email_service()
    
    print("Sending test email via Resend...")
    try:
        response = await email_service.send_email(
            from_email="onboarding@resend.dev",
            to_email="anish.as.1523@gmail.com",
            subject="Hello World",
            html_content="<p>Congrats on sending your <strong>first email</strong> via GramCare AI!</p>"
        )
        print("Success! Response from Resend API:")
        print(response)
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    asyncio.run(main())
