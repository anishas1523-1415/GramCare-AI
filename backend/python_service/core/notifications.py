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
    # A Render secret file keeps whatever name it was uploaded under, which
    # is rarely the name the path was written for — the downloaded Firebase
    # key is called gramcare-ai-firebase-adminsdk-fbsvc-<hash>.json. Rather
    # than make an emergency notification chain depend on two strings being
    # typed to match, fall back to the single service-account JSON sitting
    # in the secrets directory when the exact path is not there.
    if cred_path and not os.path.exists(cred_path):
        secrets_dir = os.path.dirname(cred_path) or "/etc/secrets"
        try:
            candidates = [
                os.path.join(secrets_dir, f)
                for f in sorted(os.listdir(secrets_dir))
                if f.endswith(".json") and not f.startswith(".")
            ]
        except OSError:
            candidates = []
        if len(candidates) == 1:
            logger.warning(
                "FIREBASE_SERVICE_ACCOUNT_PATH points at %s which does not exist; "
                "using the only JSON in %s instead (%s). Set the variable to that "
                "path to silence this.",
                cred_path, secrets_dir, os.path.basename(candidates[0]),
            )
            cred_path = candidates[0]
        elif len(candidates) > 1:
            logger.error(
                "FIREBASE_SERVICE_ACCOUNT_PATH points at %s which does not exist, and "
                "%s holds %d JSON files — refusing to guess which is the credential.",
                cred_path, secrets_dir, len(candidates),
            )

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
                notif_type = (data or {}).get("type")
                channel_id = _CHANNEL_BY_TYPE.get(notif_type, _DEFAULT_CHANNEL)
                is_emergency = notif_type == "sos_alert"
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=data or {},
                    token=token_record.fcm_token,
                    android=messaging.AndroidConfig(
                        # An SOS has to break through Doze and a silenced
                        # phone. Normal priority lets Android hold the
                        # message until the next maintenance window, which
                        # for an emergency is useless — a responder can be
                        # told about it twenty minutes late.
                        priority="high" if is_emergency else "normal",
                        notification=messaging.AndroidNotification(
                            channel_id=channel_id,
                            priority="max" if is_emergency else "default",
                            default_sound=True,
                            default_vibrate_timings=is_emergency,
                            # Keeps the alert on screen until acted on
                            # rather than sliding away unseen.
                            sticky=is_emergency,
                        ),
                    ),
                    apns=messaging.APNSConfig(
                        headers={"apns-priority": "10" if is_emergency else "5"},
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound="default",
                                # iOS only surfaces a notification through
                                # Focus/Do Not Disturb at this level.
                                content_available=True,
                            )
                        ),
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

    # Notification text lands on a lock screen, where anyone holding or
    # glancing at the phone can read it without unlocking. A doctor's name or
    # a test name is enough to disclose a diagnosis, a pregnancy, an HIV
    # test or a psychiatric referral to a family member, partner or employer.
    # Titles and bodies below stay deliberately non-specific; the details
    # ride in `data`, which only the app can read once it is open.
    def notify_appointment_reminder(self, user_id: int, doctor_name: str, time_str: str):
        self.send_notification(
            user_id=user_id,
            title="Appointment reminder",
            body=f"You have an appointment at {time_str}. Open GramCare AI for details.",
            data={"type": "appointment_reminder"}
        )

    def notify_lab_report_ready(self, user_id: int, test_name: str):
        self.send_notification(
            user_id=user_id,
            title="Lab report ready",
            body="A lab report is ready. Open GramCare AI to view it.",
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

    def notify_low_stock(self, pharmacist_user_id: int, medicine_name: str, stock_count: int):
        """Pushed to the pharmacy's own owner the moment a decrement/set
        crosses below the low-stock threshold (modules/pharmacy_inventory's
        _status_for) — previously stock status was only a passive label a
        pharmacist saw if they happened to look at their own inventory list,
        unlike expiry and batch-recall alerts, which both proactively push."""
        self.send_notification(
            user_id=pharmacist_user_id,
            title="Low Stock Alert",
            body=(
                f"{medicine_name} is out of stock."
                if stock_count <= 0 else
                f"{medicine_name} is running low — {stock_count} unit{'s' if stock_count != 1 else ''} left."
            ),
            data={"type": "pharmacy_update", "medicine_name": medicine_name, "stock_count": str(stock_count)}
        )
