"""Forgot-password email PIN verification and one-time reset authorization."""

from __future__ import annotations

import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import Account, AdminLog, PasswordResetVerification
from app.security import hash_password
from app.services.email import send_password_reset_pin
from app.services.validation import normalize_email, validate_password_strength

logger = logging.getLogger("careersense")

GENERIC_SENT = "If an account exists for this email address, a verification PIN has been sent."
INVALID_PIN = "The PIN is incorrect. Please try again."
EXPIRED_PIN = "This PIN has expired. Please request a new PIN."
LOCKED_PIN = "Too many incorrect attempts. Please request a new PIN."
INVALID_RESET = "Your password reset session is no longer valid. Please start again."
PIN_TTL_SECONDS = 10 * 60
RESET_TTL_SECONDS = 10 * 60
RESEND_SECONDS = 60
MAX_PIN_ATTEMPTS = 5
MAX_REQUESTS_PER_HOUR = 8
AUDIT_RETENTION = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def generate_pin() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def _secret_bytes() -> bytes:
    return get_settings().secret_key.encode("utf-8")


def email_lookup_hash(email: str) -> str:
    return hmac.new(_secret_bytes(), f"reset-email:{email}".encode("utf-8"), sha256).hexdigest()


def hash_pin(pin: str) -> str:
    salt = secrets.token_hex(16)
    digest = hmac.new(_secret_bytes(), f"{salt}:{pin}".encode("utf-8"), sha256).hexdigest()
    return f"{salt}${digest}"


def verify_hashed_pin(pin: str, stored: str) -> bool:
    try:
        salt, digest = str(stored or "").split("$", 1)
    except ValueError:
        return False
    expected = hmac.new(_secret_bytes(), f"{salt}:{pin}".encode("utf-8"), sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def hash_reset_token(token: str) -> str:
    return hmac.new(_secret_bytes(), f"reset-token:{token}".encode("utf-8"), sha256).hexdigest()


def verify_reset_token(token: str, stored: str) -> bool:
    expected = hash_reset_token(token)
    return hmac.compare_digest(expected, str(stored or ""))


def mask_email(email: str) -> str:
    local, _, domain = str(email or "").partition("@")
    if not domain:
        return "***"
    visible = local[:1] if local else "*"
    return f"{visible}***@{domain}"


def generic_sent_payload(email: str, *, expires_in: int = PIN_TTL_SECONDS, resend_after: int = RESEND_SECONDS) -> dict:
    return {
        "ok": True,
        "message": GENERIC_SENT,
        "masked_email": mask_email(email),
        "expires_in": max(0, int(expires_in)),
        "resend_after": max(0, int(resend_after)),
    }


def account_is_eligible(account: Optional[Account]) -> bool:
    if account is None:
        return False
    if account.role == "Admin":
        return account.status == "Active"
    if account.role == "Alumni":
        return account.status in {"Active", "Pending", "Rejected"}
    return False


def greeting_name(account: Account) -> str:
    profile = account.profile
    if profile and (profile.first_name or "").strip():
        return profile.first_name.strip()
    if (account.first_name or "").strip():
        return account.first_name.strip()
    return "Alumni"


def _audit(db: Session, action: str, account_id: Optional[int] = None, extra: Optional[dict] = None) -> None:
    db.add(
        AdminLog(
            admin_id=None,
            action_type=action,
            target_id=str(account_id or ""),
            new_value=extra or {},
        )
    )


def purge_stale_resets(db: Session) -> None:
    cutoff = _now() - AUDIT_RETENTION
    stale = (
        db.query(PasswordResetVerification)
        .filter(PasswordResetVerification.created_at <= cutoff)
        .all()
    )
    for row in stale:
        db.delete(row)
    if stale:
        db.flush()


def _open_rows(db: Session, email_hash: str) -> list[PasswordResetVerification]:
    return (
        db.query(PasswordResetVerification)
        .filter(
            PasswordResetVerification.email_hash == email_hash,
            PasswordResetVerification.replaced_at.is_(None),
            PasswordResetVerification.used_at.is_(None),
        )
        .order_by(PasswordResetVerification.created_at.desc())
        .all()
    )


def _latest_open(db: Session, email_hash: str) -> Optional[PasswordResetVerification]:
    rows = _open_rows(db, email_hash)
    return rows[0] if rows else None


def _invalidate_open(db: Session, email_hash: str) -> None:
    now = _now()
    for row in _open_rows(db, email_hash):
        row.replaced_at = now


def _hourly_count(db: Session, email_hash: str) -> int:
    since = _now() - timedelta(hours=1)
    return (
        db.query(PasswordResetVerification)
        .filter(
            PasswordResetVerification.email_hash == email_hash,
            PasswordResetVerification.created_at >= since,
        )
        .count()
    )


def _find_account(db: Session, email: str) -> Optional[Account]:
    return (
        db.query(Account)
        .options(joinedload(Account.profile))
        .filter(Account.personal_email == email)
        .first()
    )


def _send_pin(account: Account, pin: str) -> bool:
    result = send_password_reset_pin(
        to_address=account.personal_email,
        name=greeting_name(account),
        pin=pin,
        minutes=PIN_TTL_SECONDS // 60,
    )
    if result.ok:
        logger.info("Password reset PIN emailed for account %s", account.id)
        return True
    logger.warning("Password reset email failed for account %s", account.id)
    return False


def _create_challenge(db: Session, email: str, email_hash: str, account: Optional[Account]) -> PasswordResetVerification:
    pin = generate_pin()
    now = _now()
    eligible = account_is_eligible(account)
    row = PasswordResetVerification(
        email_hash=email_hash,
        account_id=account.id if eligible and account else None,
        pin_hash=hash_pin(pin),
        expires_at=now + timedelta(seconds=PIN_TTL_SECONDS),
        attempts=0,
        last_sent_at=now,
    )
    db.add(row)
    db.flush()
    if eligible and account:
        sent = _send_pin(account, pin)
        _audit(db, "password_reset_requested", account.id, {"eligible": True})
        if sent:
            _audit(db, "password_reset_pin_sent", account.id)
        else:
            _audit(db, "password_reset_email_failed", account.id)
    else:
        _audit(db, "password_reset_requested", extra={"eligible": False})
    return row


def request_pin(db: Session, raw_email: str) -> dict:
    email = normalize_email(raw_email)
    purge_stale_resets(db)
    email_hash = email_lookup_hash(email)
    latest = _latest_open(db, email_hash)
    now = _now()
    if latest and latest.last_sent_at:
        sent_at = _aware(latest.last_sent_at)
        wait = RESEND_SECONDS - int((now - sent_at).total_seconds())
        if wait > 0:
            remaining = int((_aware(latest.expires_at) - now).total_seconds())
            db.commit()
            return generic_sent_payload(email, expires_in=max(0, remaining), resend_after=wait)
    if _hourly_count(db, email_hash) >= MAX_REQUESTS_PER_HOUR:
        remaining = 0
        resend_after = RESEND_SECONDS
        if latest:
            remaining = int((_aware(latest.expires_at) - now).total_seconds())
            if latest.last_sent_at:
                resend_after = max(0, RESEND_SECONDS - int((now - _aware(latest.last_sent_at)).total_seconds()))
        db.commit()
        return generic_sent_payload(email, expires_in=max(0, remaining), resend_after=resend_after)

    _invalidate_open(db, email_hash)
    account = _find_account(db, email)
    _create_challenge(db, email, email_hash, account)
    db.commit()
    return generic_sent_payload(email)


def resend_pin(db: Session, raw_email: str) -> dict:
    return request_pin(db, raw_email)


def verify_pin(db: Session, raw_email: str, pin: str) -> dict:
    email = normalize_email(raw_email)
    code = str(pin or "").strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=400, detail="Enter the 6-digit PIN.")
    purge_stale_resets(db)
    email_hash = email_lookup_hash(email)
    row = _latest_open(db, email_hash)
    now = _now()
    if row is None:
        raise HTTPException(status_code=400, detail=INVALID_PIN)
    if row.used_at is not None or row.replaced_at is not None:
        raise HTTPException(status_code=400, detail=INVALID_RESET)
    if row.verified_at is not None:
        raise HTTPException(status_code=400, detail=INVALID_RESET)
    if _aware(row.expires_at) <= now:
        row.replaced_at = now
        _audit(db, "password_reset_pin_expired", row.account_id)
        db.commit()
        raise HTTPException(status_code=400, detail=EXPIRED_PIN)
    if (row.attempts or 0) >= MAX_PIN_ATTEMPTS:
        row.replaced_at = now
        _audit(db, "password_reset_pin_locked", row.account_id)
        db.commit()
        raise HTTPException(status_code=400, detail=LOCKED_PIN)
    if not verify_hashed_pin(code, row.pin_hash):
        row.attempts = (row.attempts or 0) + 1
        if row.attempts >= MAX_PIN_ATTEMPTS:
            row.replaced_at = now
            _audit(db, "password_reset_pin_locked", row.account_id)
            db.commit()
            raise HTTPException(status_code=400, detail=LOCKED_PIN)
        _audit(db, "password_reset_pin_failed", row.account_id, {"attempts": row.attempts})
        db.commit()
        raise HTTPException(status_code=400, detail=INVALID_PIN)

    token = generate_reset_token()
    row.verified_at = now
    row.reset_token_hash = hash_reset_token(token)
    row.reset_expires_at = now + timedelta(seconds=RESET_TTL_SECONDS)
    _audit(db, "password_reset_pin_verified", row.account_id)
    db.commit()
    return {
        "ok": True,
        "message": "Email verified successfully. You can now create a new password.",
        "reset_token": token,
        "expires_in": RESET_TTL_SECONDS,
    }


def _row_for_reset_token(db: Session, token: str) -> Optional[PasswordResetVerification]:
    digest = hash_reset_token(token)
    return (
        db.query(PasswordResetVerification)
        .filter(
            PasswordResetVerification.reset_token_hash == digest,
            PasswordResetVerification.used_at.is_(None),
            PasswordResetVerification.replaced_at.is_(None),
            PasswordResetVerification.verified_at.isnot(None),
        )
        .first()
    )


def reset_password(db: Session, token: str, new_password: str) -> dict:
    raw_token = str(token or "").strip()
    if not raw_token:
        raise HTTPException(status_code=400, detail=INVALID_RESET)
    validate_password_strength(new_password)
    purge_stale_resets(db)
    row = _row_for_reset_token(db, raw_token)
    now = _now()
    if row is None:
        raise HTTPException(status_code=400, detail=INVALID_RESET)
    if _aware(row.reset_expires_at) is None or _aware(row.reset_expires_at) <= now:
        row.replaced_at = now
        db.commit()
        raise HTTPException(status_code=400, detail=INVALID_RESET)
    account = db.get(Account, row.account_id) if row.account_id else None
    if not account or not account_is_eligible(account):
        row.replaced_at = now
        db.commit()
        raise HTTPException(status_code=400, detail=INVALID_RESET)

    account.password_hash = hash_password(new_password)
    account.password_changed_at = now
    account.must_change_password = False
    account.token_version = int(account.token_version or 0) + 1
    row.used_at = now
    row.replaced_at = now
    email_hash = row.email_hash
    for other in _open_rows(db, email_hash):
        if other.id != row.id:
            other.replaced_at = now
            other.used_at = other.used_at or now
    _audit(db, "password_reset_completed", account.id)
    db.commit()
    return {"ok": True, "message": "Password updated successfully"}
