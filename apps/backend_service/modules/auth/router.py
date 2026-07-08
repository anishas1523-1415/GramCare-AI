from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

import models
import schemas
from core.ratelimit import rate_limit
from database import get_db
from core.email_service import get_email_service, EmailService
from .utils import (
    verify_password, get_password_hash, create_access_token, decode_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES, create_refresh_token, REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
# Variant that does NOT 401 when the header is absent — used by endpoints
# that serve both guests and logged-in users (e.g. the public symptom
# checker, which attributes results to the caller only when known).
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """Return the authenticated user if a valid token was supplied, None for
    guests. An *invalid* (as opposed to missing) token is still rejected —
    silently ignoring bad credentials would mask client bugs."""
    if token is None:
        return None
    return get_current_user(token=token, db=db)


from typing import Union, List

def require_role(required_roles: Union[List[str], str]):
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    def role_dependency(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in required_roles and current_user.role != 'ADMIN':
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_dependency

@router.post("/register", dependencies=[Depends(rate_limit("register", 10, 3600))])
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Uses the validated schemas.UserCreate (min password length 8, username
    # length bounds, role restricted to a known set), so weak passwords,
    # malformed emails, and arbitrary role strings are rejected with a 422
    # before ever reaching the database.
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    existing_email = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully", "username": new_user.username}

@router.post("/login", dependencies=[Depends(rate_limit("login", 15, 300))])
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    refresh_token = create_refresh_token()
    
    session = models.UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        device_info=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(session)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role
    }

@router.post("/refresh", response_model=schemas.Token)
def refresh_token(request: Request, payload: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    session = db.query(models.UserSession).filter(
        models.UserSession.refresh_token == payload.refresh_token,
        models.UserSession.is_revoked == False
    ).first()

    if not session or session.expires_at < now:
        if session:
            session.is_revoked = True
            db.commit()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = session.user
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or deleted")

    # Rotate refresh token
    new_refresh_token = create_refresh_token()
    session.is_revoked = True  # Revoke the old one
    
    new_session = models.UserSession(
        user_id=user.id,
        refresh_token=new_refresh_token,
        device_info=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_session)
    db.commit()

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "role": user.role
    }

@router.post("/logout")
def logout(payload: schemas.LogoutRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    session = db.query(models.UserSession).filter(
        models.UserSession.refresh_token == payload.refresh_token,
        models.UserSession.user_id == current_user.id
    ).first()
    
    if session:
        session.is_revoked = True
        db.commit()
    
    return {"message": "Successfully logged out"}

@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot_password", 3, 3600))])
async def forgot_password(
    payload: schemas.ForgotPasswordRequest, 
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service)
):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        # Prevent email enumeration by returning a generic success message
        return {"message": "If that email is registered, a reset link has been sent."}
        
    import secrets
    from datetime import datetime, timezone, timedelta
    
    reset_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    
    # Invalidate older active tokens for this user
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id,
        models.PasswordResetToken.is_used == False,
        models.PasswordResetToken.expires_at > now
    ).update({"is_used": True})
    
    token_entry = models.PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=now + timedelta(hours=1)
    )
    db.add(token_entry)
    db.commit()
    
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"
    html_content = f"<p>Hello {user.full_name},</p><p>You requested a password reset. Click the link below to reset your password:</p><p><a href='{reset_link}'>Reset Password</a></p><p>If you did not request this, please ignore this email. This link expires in 1 hour.</p>"
    
    await email_service.send_email(
        to_email=user.email,
        subject="Reset your GramCare AI Password",
        html_content=html_content
    )
    
    return {"message": "If that email is registered, a reset link has been sent."}

@router.post("/reset-password", dependencies=[Depends(rate_limit("reset_password", 5, 3600))])
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    token_entry = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == payload.token,
        models.PasswordResetToken.is_used == False,
        models.PasswordResetToken.expires_at > now
    ).first()
    
    if not token_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
        
    user = token_entry.user
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")
        
    user.hashed_password = get_password_hash(payload.new_password)
    token_entry.is_used = True
    
    # Invalidate all active sessions for security
    db.query(models.UserSession).filter(
        models.UserSession.user_id == user.id,
        models.UserSession.is_revoked == False
    ).update({"is_revoked": True})
    
    db.commit()
    
    return {"message": "Password has been successfully reset. You can now log in."}



@router.get("/me")
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role
    }

@router.post("/fcm-token", dependencies=[Depends(rate_limit("fcm_token", 10, 60))])
def register_fcm_token(
    payload: schemas.FCMTokenRegistration,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # 1. Deactivate any token matching this fcm_token globally (prevents token stealing/duplicates)
    db.query(models.UserPushToken).filter(
        models.UserPushToken.fcm_token == payload.fcm_token,
        models.UserPushToken.user_id != current_user.id
    ).update({"is_active": False})

    # 2. Check if this device for this user already exists
    existing = db.query(models.UserPushToken).filter(
        models.UserPushToken.user_id == current_user.id,
        models.UserPushToken.device_id == payload.device_id,
        models.UserPushToken.platform == payload.platform
    ).first()

    if existing:
        existing.fcm_token = payload.fcm_token
        existing.is_active = True
        existing.last_seen_at = now
    else:
        new_token = models.UserPushToken(
            user_id=current_user.id,
            device_id=payload.device_id,
            platform=payload.platform,
            fcm_token=payload.fcm_token,
            is_active=True,
            last_seen_at=now
        )
        db.add(new_token)

    db.commit()
    return {"message": "FCM token registered successfully"}
