import pytest
from core.notifications import NotificationService
import models

def test_fcm_token_registration(client, patient_token, db):
    res = client.post("/api/v1/auth/fcm-token", headers={"Authorization": f"Bearer {patient_token}"}, json={
        "fcm_token": "token_a_123",
        "device_id": "device_1",
        "platform": "android"
    })
    assert res.status_code == 200

    token = db.query(models.UserPushToken).filter_by(fcm_token="token_a_123").first()
    assert token is not None
    assert token.is_active is True
    assert token.platform == "android"
    assert token.device_id == "device_1"

def test_fcm_token_refresh(client, patient_token, db):
    # Register first
    client.post("/api/v1/auth/fcm-token", headers={"Authorization": f"Bearer {patient_token}"}, json={
        "fcm_token": "old_token",
        "device_id": "device_1",
        "platform": "android"
    })
    
    # Refresh token for the same device
    res = client.post("/api/v1/auth/fcm-token", headers={"Authorization": f"Bearer {patient_token}"}, json={
        "fcm_token": "new_token",
        "device_id": "device_1",
        "platform": "android"
    })
    assert res.status_code == 200

    tokens = db.query(models.UserPushToken).filter_by(device_id="device_1").all()
    assert len(tokens) == 1
    assert tokens[0].fcm_token == "new_token"

def test_fcm_token_duplicate_cleanup(client, patient_token, doctor_token, db):
    # Patient registers token_x
    client.post("/api/v1/auth/fcm-token", headers={"Authorization": f"Bearer {patient_token}"}, json={
        "fcm_token": "token_shared",
        "device_id": "device_patient",
        "platform": "android"
    })
    
    # Doctor logs into the same physical device, token_x is now associated with doctor
    client.post("/api/v1/auth/fcm-token", headers={"Authorization": f"Bearer {doctor_token}"}, json={
        "fcm_token": "token_shared",
        "device_id": "device_doctor",
        "platform": "android"
    })

    # The patient's token record should now be inactive to prevent cross-account push notifications
    patient_user = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {patient_token}"}).json()
    doctor_user = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {doctor_token}"}).json()
    
    patient_record = db.query(models.UserPushToken).filter_by(user_id=patient_user["id"], fcm_token="token_shared").first()
    doctor_record = db.query(models.UserPushToken).filter_by(user_id=doctor_user["id"], fcm_token="token_shared").first()
    
    assert doctor_record.is_active is True
    assert patient_record.is_active is False

def test_notification_service_mock(client, patient_token, db):
    client.post("/api/v1/auth/fcm-token", headers={"Authorization": f"Bearer {patient_token}"}, json={
        "fcm_token": "token_test_send",
        "device_id": "device_1",
        "platform": "android"
    })
    patient_user = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {patient_token}"}).json()

    svc = NotificationService(db)
    # This will use the mock path since we didn't set FIREBASE_SERVICE_ACCOUNT_PATH
    success_count = svc.send_notification(patient_user["id"], "Test Title", "Test Body")
    assert success_count == 1
