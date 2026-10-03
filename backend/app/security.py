from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .models import AppUser

COOKIE_NAME = "event_attendance_session"
JWT_ISSUER = "event-attendance-app"
JWT_AUDIENCE = "event-attendance-operators"
password_hasher = PasswordHasher(type=Type.ID)


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    # A missing username still incurs Argon2 verification work.
    return password_hasher.hash("invalid-login-timing-check")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if not password_hash.startswith("$argon2id$"):
            return False
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
         "iss": JWT_ISSUER, "aud": JWT_AUDIENCE},
        settings.JWT_SECRET.get_secret_value(), algorithm="HS256",
    )


def get_current_user(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> AppUser:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    try:
        claims = jwt.decode(
            token, settings.JWT_SECRET.get_secret_value(), algorithms=["HS256"],
            issuer=JWT_ISSUER, audience=JWT_AUDIENCE,
            options={"require": ["sub", "iat", "exp", "iss", "aud"]},
        )
        raw_subject = claims["sub"]
        if not isinstance(raw_subject, str) or not raw_subject.isdigit():
            raise ValueError("Invalid subject")
        user_id = int(raw_subject)
        if user_id <= 0:
            raise ValueError("Invalid subject")
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="La sesión expiró. Ingresa nuevamente.") from None
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    if not user.is_active or user.role not in {"ADMIN", "LOGISTICS"}:
        raise HTTPException(status_code=403, detail="Tu usuario no tiene acceso a esta aplicación.")
    return user
