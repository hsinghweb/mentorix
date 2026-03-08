"""JWT creation and verification for student/admin auth."""
from datetime import datetime, timezone, timedelta
from uuid import UUID

import jwt

from app.core.settings import settings


def create_token(learner_id: UUID | str, username: str, *, role: str = "student") -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(learner_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None


def create_admin_token(username: str) -> str:
    return create_token(f"admin:{username}", username, role="admin")


def token_role(payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    role = payload.get("role")
    return str(role) if role else None
