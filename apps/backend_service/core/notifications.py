import logging
import os
from typing import Optional, Dict

from sqlalchemy.orm import Session
import firebase_admin
from firebase_admin import credentials, messaging
from firebase_admin.exceptions import FirebaseError

import models

logger = logging.getLogger("gramcare.notifications")

# Android notification channel per message type — must match the channel ids
# created client-side in apps/mobile_app/lib/services/firebase_notification_
# service.dart. This is what actually determines which channel a background/
# terminated-state notification lands in: Android reads channel_id straight
# off the FCM payload's AndroidConfig, it does NOT ask the (possibly not
# running) app to decide. Only foreground messages are channel-routed by the
# app itself, since those are rendered locally rather than auto-displayed.
_CHANNEL_BY_TYPE: Dict[str, str] = {
    "sos_alert": "gramcare_emergency_channel",
    "appointment_reminder": "gramcare_appointments_channel",
    "pharmacy_ready": "gramcare_pharmacy_channel",
    "pharmacy_update": "gramcare_pharmacy_channel",
}
_DEFAULT_CHANNEL = "gramcare_general_channel"

# Initialize Firebase Admin if credentials are provided
_firebase_initialized = False
try:
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin initialized successfully.")
    else:
        logger.warning("FIREBASE_SERVICE_ACCOUNT_PATH not set or file missing. FCM will be mocked.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase Admin: {e}")

class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def send_notification(self, user_id: int, title: str, body: str, data: Optional[Dict[str, str]] = None) -> int:
        """
        Sends a notification to all active devices for a user.
        Returns the number of successfully delivered messages.
        """
        tokens = self.db.query(models.UserPushToken).filter(
            models.UserPushToken.user_id == user_id,
            models.UserPushToken.is_active == True
        ).all()

        if not tokens:
            logger.info(f"No active push tokens found for user {user_id}")
            return 0

        success_count = 0
        for token_record in tokens:
            if not _firebase_initialized:
                logger.info(f"[MOCK FCM] Sending to {token_record.fcm_token}: {title} - {body}")
                success_count += 1
                continue

            try:
                channel_id = _CHANNEL_BY_TYPE.get((data or {}).get("type"), _DEFAULT_CHANNEL)
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=data or {},
                    token=token_record.fcm_token,
                    android=messaging.AndroidConfig(
                        notification=messaging.AndroidNotification(channel_id=channel_id)
                    ),
                )
                response = messaging.send(message)
                logger.debug(f"Successfully sent message: {response}")
                success_count += 1
            except messaging.UnregisteredError:
                logger.warning(f"FCM token unregistered for user {user_id}, deactivating token ID {token_record.id}")
                token_record.is_active = False
            except messaging.SenderIdMismatchError:
                logger.warning(f"Sender ID mismatch for user {user_id}, deactivating token ID {token_record.id}")
                token_record.is_active = False
            except FirebaseError as e:
                logger.error(f"Firebase error sending to user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending FCM to user {user_id}: {e}")

        # Commit any deactivations
        self.db.commit()
        return success_count

    # Higher-level notification workflows
    def notify_sos_alert(self, user_id: int, hospital_name: str, status: str):
        self.send_notification(
            user_id=user_id,
            title="Emergency SOS Update",
            body=f"{hospital_name} has marked your SOS as {status}.",
            data={"type": "sos_alert", "status": status}
        )

    def notify_appointment_reminder(self, user_id: int, doctor_name: str, time_str: str):
        self.send_notification(
            user_id=user_id,
            title="Appointment Reminder",
            body=f"You have an upcoming appointment with {doctor_name} at {time_str}.",
            data={"type": "appointment_reminder"}
        )

    def notify_lab_report_ready(self, user_id: int, test_name: str):
        self.send_notification(
            user_id=user_id,
            title="Lab Report Ready",
            body=f"Your {test_name} report is ready to view.",
            data={"type": "lab_report_ready"}
        )

    def notify_batch_recall(self, user_id: int, medicine_name: str, is_pharmacist: bool):
        self.send_notification(
            user_id=user_id,
            title="Medicine Recall Alert",
            body=(
                f"{medicine_name} has been recalled — check your stock and stop dispensing this batch."
                if is_pharmacist else
                f"{medicine_name}, which you were prescribed, has been recalled. Please check with your pharmacist."
            ),
            data={"type": "batch_recall", "medicine_name": medicine_name}
        )
