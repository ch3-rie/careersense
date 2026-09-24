"""Persisted retry queue for non-secret transactional mail."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmailOutbox, ProfileReminderSend, ProfileUpdateRequestRecipient
from app.services.email.service import send_email

logger = logging.getLogger("careersense")

SECRET_KINDS = frozenset({"password_reset", "verification", "pin"})
RETRYABLE_KINDS = frozenset({
    "profile_update",
    "profile_reminder",
    "account_status",
    "registration_received",
    "gts_reminder",
    "aac_status",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(
    db: Session,
    *,
    kind: str,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str,
    account_id: Optional[int] = None,
    meta: Optional[dict] = None,
) -> Optional[EmailOutbox]:
    if kind in SECRET_KINDS:
        logger.warning("Refused to persist secret email kind=%s", kind)
        return None
    if kind not in RETRYABLE_KINDS:
        return None
    settings = get_settings()
    max_attempts = max(1, int(getattr(settings, "email_outbox_max_attempts", 5) or 5))
    row = EmailOutbox(
        kind=kind,
        account_id=account_id,
        to_address=(to_address or "").strip(),
        subject=(subject or "")[:200],
        text_body=text_body or "",
        html_body=html_body or "",
        status="pending",
        attempts=0,
        max_attempts=max_attempts,
        next_retry_at=_now(),
        meta_json=dict(meta or {}),
    )
    db.add(row)
    db.flush()
    logger.info("Queued transactional email retry kind=%s", kind)
    return row


def enqueue_if_retryable(
    db: Session,
    result,
    *,
    kind: str,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str,
    account_id: Optional[int] = None,
    meta: Optional[dict] = None,
) -> Optional[EmailOutbox]:
    if result.ok or result.disabled or not getattr(result, "retryable", True):
        return None
    try:
        return enqueue(
            db,
            kind=kind,
            to_address=to_address,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            account_id=account_id,
            meta=meta,
        )
    except Exception:
        logger.exception("Could not queue email retry kind=%s", kind)
        return None


def _apply_success(db: Session, row: EmailOutbox) -> None:
    meta = row.meta_json or {}
    recipient_id = meta.get("recipient_id")
    send_id = meta.get("reminder_send_id")
    now = _now()
    if recipient_id:
        recipient = db.get(ProfileUpdateRequestRecipient, int(recipient_id))
        if recipient:
            recipient.email_status = "sent"
            recipient.email_sent_at = now
            recipient.email_error = ""
    if send_id:
        send = db.get(ProfileReminderSend, int(send_id))
        if send:
            send.email_status = "sent"
            send.sent_at = now
            send.email_error = ""
            send.skipped_reason = ""


def _apply_failure(db: Session, row: EmailOutbox, error: str) -> None:
    meta = row.meta_json or {}
    recipient_id = meta.get("recipient_id")
    send_id = meta.get("reminder_send_id")
    message = (error or "The email could not be sent.")[:400]
    if recipient_id:
        recipient = db.get(ProfileUpdateRequestRecipient, int(recipient_id))
        if recipient and recipient.email_status != "sent":
            recipient.email_status = "failed"
            recipient.email_error = message
    if send_id:
        send = db.get(ProfileReminderSend, int(send_id))
        if send and send.email_status != "sent":
            send.email_status = "failed"
            send.email_error = message


def process_outbox(db: Session, limit: int = 25) -> int:
    now = _now()
    rows = (
        db.query(EmailOutbox)
        .filter(
            EmailOutbox.status == "pending",
            EmailOutbox.next_retry_at.isnot(None),
            EmailOutbox.next_retry_at <= now,
        )
        .order_by(EmailOutbox.next_retry_at.asc(), EmailOutbox.id.asc())
        .limit(max(1, limit))
        .all()
    )
    processed = 0
    for row in rows:
        if row.kind in SECRET_KINDS:
            row.status = "skipped"
            row.last_error = "Secret messages cannot be retried from the outbox."
            processed += 1
            continue
        row.attempts = int(row.attempts or 0) + 1
        result = send_email(
            to_address=row.to_address,
            subject=row.subject,
            text_body=row.text_body,
            html_body=row.html_body,
            kind=row.kind,
        )
        row.provider = result.provider or row.provider
        if result.ok:
            row.status = "sent"
            row.sent_at = now
            row.last_error = ""
            row.provider_message_id = result.message_id or ""
            _apply_success(db, row)
        elif result.disabled:
            row.status = "skipped"
            row.last_error = (result.error or "Email sending is disabled.")[:400]
        elif row.attempts >= int(row.max_attempts or 1) or not result.retryable:
            row.status = "failed"
            row.last_error = (result.error or "The email could not be sent.")[:400]
            _apply_failure(db, row, row.last_error)
        else:
            delay = min(60, 2 ** min(row.attempts, 6))
            row.next_retry_at = now + timedelta(minutes=delay)
            row.last_error = (result.error or "The email could not be sent.")[:400]
            logger.info("Outbox retry scheduled kind=%s attempt=%s", row.kind, row.attempts)
        processed += 1
    return processed
