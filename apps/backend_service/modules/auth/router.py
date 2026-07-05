from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

import models
import schemas
from core.ratelimit import rate_limit
from database import get_db
from .utils import verify_password, get_password_hash, create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

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


def require_role(required_role: str):
    def role_dependency(current_user: models.User = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != 'ADMIN':
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
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

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
