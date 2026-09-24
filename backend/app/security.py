import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import HTTPException, status

from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REGISTRATION = "registration"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        chars = [secrets.choice(string.ascii_letters), secrets.choice(string.digits)]
        chars.extend(secrets.choice(alphabet) for _ in range(max(6, length - 2)))
        secrets.SystemRandom().shuffle(chars)
        password = "".join(chars)
        if any(c.isalpha() for c in password) and any(c.isdigit() for c in password):
            return password


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=get_settings().access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "typ": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": expire,
        "ver": 0,
    }
    if extra:
        payload.update(extra)
        payload["typ"] = TOKEN_TYPE_ACCESS
        payload["sub"] = str(subject)
        payload["ver"] = int(payload.get("ver") or 0)
    return _encode(payload)


def access_token_claims(user: Any) -> dict[str, Any]:
    return {
        "role": getattr(user, "role", ""),
        "status": getattr(user, "status", ""),
        "ver": int(getattr(user, "token_version", 0) or 0),
    }


def create_registration_token(draft_id: int) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=24)
    return _encode(
        {
            "did": str(draft_id),
            "typ": TOKEN_TYPE_REGISTRATION,
            "iat": int(now.timestamp()),
            "exp": expire,
        }
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc


def require_access_payload(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("typ") != TOKEN_TYPE_ACCESS or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to continue.",
        )
    return payload


def require_registration_payload(token: str) -> dict[str, Any]:
    try:
        payload = decode_token(token)
    except HTTPException as exc:
        if "expired" in str(exc.detail).lower():
            raise HTTPException(
                status_code=400,
                detail="Your resume review session expired. Please upload your resume again.",
            ) from exc
        raise HTTPException(
            status_code=400,
            detail="Your resume review session is invalid. Please start registration again.",
        ) from exc
    if payload.get("typ") != TOKEN_TYPE_REGISTRATION:
        raise HTTPException(
            status_code=400,
            detail="Please complete registration from the survey step.",
        )
    if not payload.get("did"):
        raise HTTPException(
            status_code=400,
            detail="Your resume review session is invalid. Please start registration again.",
        )
    return payload
