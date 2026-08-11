import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import timedelta

import models
import schemas
from core.ratelimit import rate_limit
from database import get_db
from core.email_service import get_email_service, EmailService
from core.sms_service import get_sms_service, SMSService
from .utils import (
    verify_password, get_password_hash, create_access_token, decode_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES, create_refresh_token, REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter()
logger = logging.getLogger("gramcare.auth")

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


def require_approved_doctor(extra_roles: Union[List[str], str, None] = None):
    """Like require_role("DOCTOR" [, *extra_roles]), but additionally blocks
    a DOCTOR caller whose DoctorProfile.verification_status isn't APPROVED —
    a doctor account can log in and manage its own application the moment
    it's registered, but must not reach patient-facing actions (appointment
    queues, prescriptions, SOS response, publishing availability) until a
    government reviewer approves it. Non-DOCTOR roles in extra_roles
    (e.g. HOSPITAL, ADMIN) are never subject to this check — the gate is
    specifically about unverified doctors, not those roles.
    """
    if extra_roles is None:
        extra_roles = []
    elif isinstance(extra_roles, str):
        extra_roles = [extra_roles]
    allowed = set(extra_roles) | {"DOCTOR"}

    def dependency(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if current_user.role not in allowed and current_user.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Not enough permissions")
        if current_user.role == "DOCTOR":
            profile = (
                db.query(models.DoctorProfile)
                .filter(models.DoctorProfile.user_id == current_user.id)
                .first()
            )
            if not profile or profile.verification_status != "APPROVED":
                raise HTTPException(
                    status_code=403,
                    detail="Your doctor account is pending government verification and cannot perform this action yet.",
                )
        return current_user
    return dependency


def _issue_verification_token(db: Session, user: models.User) -> str:
    import secrets
    from datetime import datetime, timezone, timedelta
    token = secrets.token_urlsafe(32)
    db.add(models.EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    db.commit()
    return token


async def _send_verification_email(db: Session, email_service: EmailService, user: models.User):
    """Best-effort — must never block registration itself. Every role gets
    a verification link (so PATIENT accounts can self-verify too if they
    want to), but only non-PATIENT roles are actually blocked from logging
    in until they use it — see the is_verified check in login()."""
    try:
        token = _issue_verification_token(db, user)
        # Same default fix as forgot_password below — this used to point at
        # the pharmacy dashboard's dev port (5173), not the patient portal
        # where /verify-email actually lives.
        frontend_url = os.getenv("FRONTEND_URL", "https://gram-care-ai.vercel.app")
        verify_link = f"{frontend_url}/verify-email?token={token}"
        html_content = (
            f"<p>Hello {user.full_name},</p>"
            f"<p>Welcome to GramCare AI. Please verify your email to activate your account:</p>"
            f"<p><a href='{verify_link}'>Verify my email</a></p>"
            f"<p>This link expires in 24 hours.</p>"
        )
        result = await email_service.send_email(
            to_email=user.email,
            subject="Verify your GramCare AI account",
            html_content=html_content,
        )
        if isinstance(result, dict) and result.get("status") == "skipped":
            # EmailService.send_email doesn't raise when RESEND_API_KEY is
            # unset — it returns a normal-looking {"status": "skipped"} dict
            # instead, so the try/except below never fires and nothing is
            # ever logged. That silence is exactly what left non-PATIENT
            # registrations (DOCTOR/HOSPITAL/ADMIN all require a verified
            # email to log in) stuck forever with no error anywhere: the
            # registration API call reports success, the account is created,
            # and the user just... never gets an email, with no trace in the
            # logs pointing at why. Surfacing it here at least makes the
            # cause visible to whoever's reading Render logs.
            logger.error(
                "Verification email to %s was SKIPPED (RESEND_API_KEY not configured) — "
                "this account cannot log in until it's verified some other way.",
                user.email,
            )
    except Exception as e:
        logger.warning("Failed to send verification email to %s: %s", user.email, e)


@router.post("/register", dependencies=[Depends(rate_limit("register", 10, 3600))])
async def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
):
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

    # DOCTOR/HOSPITAL must prove phone ownership before the account is
    # created — the same phone must have completed /auth/phone/verify-otp
    # within the last 15 minutes. PATIENT/PHARMACIST/LAB don't require this
    # (keeps rural patient self-service low-friction).
    phone_verified = False
    if user.role in ("DOCTOR", "HOSPITAL"):
        if not user.phone:
            raise HTTPException(status_code=400, detail="A verified phone number is required for this role.")
        from datetime import datetime, timezone, timedelta
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        verified_otp = (
            db.query(models.PhoneOTP)
            .filter(
                models.PhoneOTP.phone == user.phone,
                models.PhoneOTP.is_used == True,  # noqa: E712
                models.PhoneOTP.created_at >= recent_cutoff.replace(tzinfo=None),
            )
            .order_by(models.PhoneOTP.created_at.desc())
            .first()
        )
        if not verified_otp:
            raise HTTPException(
                status_code=400,
                detail="Please verify this phone number with an OTP before registering.",
            )
        phone_verified = True

    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        role=user.role,
        phone=user.phone,
        phone_verified=phone_verified,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    await _send_verification_email(db, email_service, new_user)

    return {"message": "User registered successfully", "username": new_user.username}


@router.post("/register/government", dependencies=[Depends(rate_limit("register", 10, 3600))])
async def register_government_user(
    user: schemas.GovernmentRegisterCreate,
    request: Request,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
):
    """The ONLY way to obtain an ADMIN (Government Portal) account. The
    caller's email must already exist in AuthorizedGovernmentEmail — there
    is deliberately no self-serve "apply to be a government official" flow,
    unlike doctors. Exact case-insensitive match via LOWER() on both sides
    — NOT .ilike(user.email), which would treat attacker-controlled '%'/'_'
    characters (both legal in email local-parts) as SQL LIKE wildcards and
    could match a whitelist entry it shouldn't."""
    whitelisted = (
        db.query(models.AuthorizedGovernmentEmail)
        .filter(func.lower(models.AuthorizedGovernmentEmail.email) == user.email.lower())
        .first()
    )
    if not whitelisted:
        raise HTTPException(
            status_code=403,
            detail="This email is not authorized for Government Portal access.",
        )

    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name,
        role="ADMIN",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    db.add(models.AuditLog(
        user_id=new_user.id,
        action="CREATE",
        resource="GovernmentAccount",
        resource_id=str(new_user.id),
        details={"email": new_user.email, "whitelist_entry_id": whitelisted.id},
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    await _send_verification_email(db, email_service, new_user)

    return {"message": "Government account registered successfully", "username": new_user.username}


# ==========================================
# Government whitelist management (ADMIN-only admin-UI equivalent of the
# GOVERNMENT_WHITELIST_EMAILS env var / _seed_government_whitelist in
# main.py — that mechanism only ever ADDS entries once, at process startup;
# these let an existing ADMIN manage the table directly, without a redeploy.
# ==========================================

@router.get("/government-whitelist", response_model=list[schemas.GovernmentWhitelistEntryResponse])
def list_government_whitelist(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin accounts only.")
    return (
        db.query(models.AuthorizedGovernmentEmail)
        .order_by(models.AuthorizedGovernmentEmail.created_at.desc())
        .all()
    )


@router.post("/government-whitelist", response_model=schemas.GovernmentWhitelistEntryResponse, status_code=201)
def add_government_whitelist_entry(
    body: schemas.GovernmentWhitelistEntryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin accounts only.")
    email = body.email.lower()
    existing = (
        db.query(models.AuthorizedGovernmentEmail)
        .filter(func.lower(models.AuthorizedGovernmentEmail.email) == email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="This email is already whitelisted.")

    entry = models.AuthorizedGovernmentEmail(email=email, note=body.note)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="CREATE",
        resource="AuthorizedGovernmentEmail",
        resource_id=str(entry.id),
        details={"email": entry.email},
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()
    return entry


@router.delete("/government-whitelist/{entry_id}")
def remove_government_whitelist_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin accounts only.")
    entry = db.query(models.AuthorizedGovernmentEmail).filter(models.AuthorizedGovernmentEmail.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Whitelist entry not found.")

    db.add(models.AuditLog(
        user_id=current_user.id,
        action="DELETE",
        resource="AuthorizedGovernmentEmail",
        resource_id=str(entry.id),
        details={"email": entry.email},
        ip_address=request.client.host if request.client else None,
    ))
    db.delete(entry)
    db.commit()
    return {"message": "Whitelist entry removed."}


@router.post("/login", dependencies=[Depends(rate_limit("login", 15, 300))])
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # PATIENT stays ungated (low-friction rural self-service); every other
    # role can approve doctors, dispense medicine, issue lab reports, or
    # run emergency response, so email ownership must be proven first.
    if user.role != "PATIENT" and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before signing in. Check your inbox for a verification link, or request a new one.",
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
    # UserSession.expires_at is a naive DateTime column (no timezone=True),
    # so SQLAlchemy reads it back naive. Comparing that directly against an
    # aware `now` below raised "can't compare offset-naive and
    # offset-aware datetimes" — an unhandled 500 on every single refresh
    # attempt, since nothing ever called this endpoint before the frontend
    # started actually using the refresh token it had been discarding.
    now = datetime.now(timezone.utc).replace(tzinfo=None)

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


@router.get("/sessions", response_model=list[schemas.UserSessionResponse])
def list_my_sessions(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Every active (not revoked, not expired) device/session for the
    caller — previously the only way to end a session was /auth/logout with
    that exact device's own refresh token, so a lost or stolen device could
    never be revoked remotely."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return (
        db.query(models.UserSession)
        .filter(
            models.UserSession.user_id == current_user.id,
            models.UserSession.is_revoked == False,  # noqa: E712
            models.UserSession.expires_at > now,
        )
        .order_by(models.UserSession.created_at.desc())
        .all()
    )


@router.delete("/sessions/{session_id}")
def revoke_my_session(session_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Remotely sign out one device — e.g. a lost phone — without needing
    that device's refresh token."""
    session = (
        db.query(models.UserSession)
        .filter(models.UserSession.id == session_id, models.UserSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.is_revoked = True
    db.commit()
    return {"message": "Session revoked"}

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
    
    # Default matches the patient web portal (where /reset-password actually
    # lives), not the pharmacy dashboard's dev port — a real production
    # email with no FRONTEND_URL override was previously linking to
    # localhost:5173, which no recipient's browser could ever reach.
    frontend_url = os.getenv("FRONTEND_URL", "https://gram-care-ai.vercel.app")
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


@router.post("/verify-email")
def verify_email(payload: schemas.VerifyEmailRequest, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    token_entry = db.query(models.EmailVerificationToken).filter(
        models.EmailVerificationToken.token == payload.token,
        models.EmailVerificationToken.is_used == False,  # noqa: E712
        models.EmailVerificationToken.expires_at > now,
    ).first()
    if not token_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")

    user = token_entry.user
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    user.is_verified = True
    token_entry.is_used = True
    db.commit()

    return {"message": "Email verified. You can now log in."}


@router.post("/resend-verification", dependencies=[Depends(rate_limit("resend_verification", 3, 3600))])
async def resend_verification(
    payload: schemas.ResendVerificationRequest,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    # Same email-enumeration-safe generic response as forgot-password.
    if user and not user.is_verified:
        await _send_verification_email(db, email_service, user)
    return {"message": "If that email is registered and unverified, a new verification link has been sent."}


@router.post("/phone/send-otp", dependencies=[Depends(rate_limit("phone_otp", 5, 3600))])
async def send_phone_otp(
    payload: schemas.PhoneSendOTPRequest,
    db: Session = Depends(get_db),
    sms_service: SMSService = Depends(get_sms_service),
):
    """First half of phone verification for DOCTOR/HOSPITAL registration.
    Generates and stores our own OTP (rather than relying on MSG91's OTP API
    to track it) so /auth/register can later check "was this phone verified
    recently" without a second round-trip to MSG91."""
    import secrets
    from datetime import datetime, timezone, timedelta

    otp_code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.now(timezone.utc)
    db.add(models.PhoneOTP(
        phone=payload.phone,
        otp_code=otp_code,
        expires_at=now + timedelta(minutes=10),
    ))
    db.commit()

    await sms_service.send_otp(payload.phone, otp_code)
    return {"message": "OTP sent."}


@router.post("/phone/verify-otp", dependencies=[Depends(rate_limit("phone_otp_verify", 10, 3600))])
def verify_phone_otp(payload: schemas.PhoneVerifyOTPRequest, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    otp_entry = (
        db.query(models.PhoneOTP)
        .filter(
            models.PhoneOTP.phone == payload.phone,
            models.PhoneOTP.is_used == False,  # noqa: E712
            models.PhoneOTP.expires_at > now,
        )
        .order_by(models.PhoneOTP.created_at.desc())
        .first()
    )
    if not otp_entry:
        raise HTTPException(status_code=400, detail="No pending OTP for this number — request a new one.")

    otp_entry.attempt_count += 1
    if otp_entry.attempt_count > 5:
        db.commit()
        raise HTTPException(status_code=429, detail="Too many attempts — request a new OTP.")

    if otp_entry.otp_code != payload.otp:
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect OTP.")

    otp_entry.is_used = True
    db.commit()
    return {"message": "Phone verified."}


@router.get("/me")
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_verified": current_user.is_verified,
        "phone": current_user.phone,
        "phone_verified": current_user.phone_verified,
    }

@router.put("/me/phone", dependencies=[Depends(rate_limit("update_phone", 5, 300))])
def update_my_phone(
    payload: schemas.PhoneUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("PATIENT")),
):
    """PATIENT-only: add or change the phone number SMS appointment
    reminders go to. Unlike DOCTOR/HOSPITAL registration, this doesn't
    require an OTP — phone here is only used for optional reminders, not
    account trust, so a wrong number just means a missed SMS rather than a
    security issue. Registration never collects a phone for PATIENT
    (deliberately low-friction), so this is the only way an existing
    patient account can start receiving reminders."""
    current_user.phone = payload.phone
    db.commit()
    return {"message": "Phone number updated", "phone": current_user.phone}


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
