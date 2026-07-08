from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from jwt import PyJWTError as JWTError, ExpiredSignatureError
import bcrypt
import secrets
import os

# Secret key for JWT.
#
# Security: the previous code unconditionally fell back to a hardcoded default
# that is committed to source control. Anyone with repo access could therefore
# forge valid tokens for ANY user against a deployment that forgot to set
# JWT_SECRET_KEY. For a healthcare application that is a critical hole.
#
# We now refuse to boot on the public default when ENVIRONMENT=production, while
# preserving the zero-config dev/test experience (the default is still used when
# ENVIRONMENT is unset or "development"/"test"). Set ENVIRONMENT=production and a
# strong JWT_SECRET_KEY (shared with the Node signaling service) in real
# deployments.
_DEV_DEFAULT_SECRET = "gramcare_jwt_secret_change_this_in_production_2026"
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    if _ENVIRONMENT == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY is not set but ENVIRONMENT=production. Refusing to "
            "start on the publicly-known default secret. Set a strong, secret "
            "JWT_SECRET_KEY (shared with the Node signaling service)."
        )
    SECRET_KEY = _DEV_DEFAULT_SECRET
elif SECRET_KEY == _DEV_DEFAULT_SECRET and _ENVIRONMENT == "production":
    raise RuntimeError(
        "JWT_SECRET_KEY is set to the publicly-known development default in a "
        "production environment. Generate a unique secret (e.g. "
        "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`)."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))  # 15 minutes default
REFRESH_TOKEN_EXPIRE_DAYS = 7



def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    """Create a cryptographically secure random string for use as a refresh token."""
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

