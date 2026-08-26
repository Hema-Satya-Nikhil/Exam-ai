from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def _decode(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def create_access_token(
    user_id: str,
    roles: list[str],
    *,
    email: str | None = None,
    full_name: str | None = None,
) -> str:
    """Issue a short-lived access JWT (type=access)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if email is not None:
        payload["email"] = email
    if full_name is not None:
        payload["full_name"] = full_name
    return _encode(payload)


def create_refresh_token(user_id: str, jti: str) -> str:
    """Issue a long-lived refresh JWT (type=refresh).

    ``jti`` must be stored in ``refresh_sessions`` *before* this token is
    handed to the client so that revocation can be checked on use.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_expire_days),
    }
    return _encode(payload)


def decode_access_token(token: str) -> dict | None:
    """Decode and type-check an access token. Returns payload or None."""
    payload = _decode(token)
    if payload is None or payload.get("type") != "access":
        return None
    return payload


def decode_refresh_token(token: str) -> dict | None:
    """Decode and type-check a refresh token. Returns payload or None."""
    payload = _decode(token)
    if payload is None or payload.get("type") != "refresh":
        return None
    return payload


# ---------------------------------------------------------------------------
# Backward-compat shim so existing AuthService still works during transition
# ---------------------------------------------------------------------------

class SecurityService:
    """Legacy wrapper kept for backward compatibility."""

    def hash_value(self, value: str) -> str:
        return hash_password(value)

    def verify_value(self, plain: str, hashed: str) -> bool:
        return verify_password(plain, hashed)

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None) -> str:
        user_id = data.get("sub", "")
        roles = data.get("roles", [])
        email = data.get("email")
        full_name = data.get("full_name")
        return create_access_token(user_id, roles, email=email, full_name=full_name)

    def decode_token(self, token: str) -> dict | None:
        return _decode(token)
