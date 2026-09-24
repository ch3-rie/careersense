"""CareerSense transactional email service. Routes never talk to a provider directly."""

from __future__ import annotations

import logging
import re
import time

from app.config import (
    get_settings,
    looks_like_placeholder_email_key,
    looks_like_placeholder_from_address,
)
from app.services.email.providers import (
    EmailSendResult,
    OutgoingEmail,
    build_provider,
    resolved_provider_name,
)
from app.services.email.render import (
    render_account_status,
    render_password_reset,
    render_profile_update,
)

logger = logging.getLogger("careersense")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def office_name() -> str:
    return get_settings().oaaps_office_name or "Office of Alumni Affairs and Placement Services"


def from_address() -> str:
    settings = get_settings()
    return (settings.email_from_address or settings.smtp_from or settings.smtp_username or "").strip()


def from_name() -> str:
    return (get_settings().email_from_name or "CareerSense").strip() or "CareerSense"


def reply_to_address() -> str:
    return (get_settings().email_reply_to or "").strip()


def public_base_url() -> str:
    settings = get_settings()
    return (settings.email_base_url or settings.frontend_url or settings.public_app_url or "").strip().rstrip("/")


def app_url(path: str = "") -> str:
    base = public_base_url()
    fragment = (path or "").strip()
    if not fragment:
        return base or "/"
    if fragment.startswith("http://") or fragment.startswith("https://"):
        return fragment
    if not fragment.startswith("/"):
        fragment = f"/{fragment}"
    return f"{base}{fragment}" if base else fragment


def provider_is_configured(settings=None) -> bool:
    settings = settings or get_settings()
    ready = getattr(settings, "email_provider_ready", None)
    if callable(ready):
        return bool(ready())
    if looks_like_placeholder_from_address(from_address_for(settings)):
        return False
    name = resolved_provider_name(settings)
    if name == "resend":
        key = (getattr(settings, "email_api_key", "") or "").strip()
        return bool(key) and not looks_like_placeholder_email_key(key)
    if name == "smtp":
        return bool((getattr(settings, "smtp_host", "") or "").strip())
    return False


def from_address_for(settings) -> str:
    return (settings.email_from_address or settings.smtp_from or settings.smtp_username or "").strip()


def sending_enabled(settings=None) -> bool:
    settings = settings or get_settings()
    flag = settings.email_enabled
    if flag is False:
        return False
    if flag is True:
        return True
    return provider_is_configured(settings)


def email_is_configured() -> bool:
    return sending_enabled() and provider_is_configured()


def email_health() -> dict:
    settings = get_settings()
    provider = resolved_provider_name(settings) if sending_enabled(settings) else ""
    return {
        "email_enabled": sending_enabled(settings),
        "email_configured": email_is_configured(),
        "email_provider": provider,
    }


def scheduler_is_enabled(settings=None) -> bool:
    settings = settings or get_settings()
    flag = getattr(settings, "email_scheduler_enabled", None)
    if flag is False:
        return False
    if flag is True:
        return True
    return sending_enabled(settings)


def send_email(
    *,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str,
    kind: str = "transactional",
) -> EmailSendResult:
    settings = get_settings()
    recipient = (to_address or "").strip()
    if not recipient or not _EMAIL_RE.match(recipient):
        return EmailSendResult(
            ok=False,
            retryable=False,
            error="The registered account email is missing or invalid.",
        )

    if not sending_enabled(settings):
        logger.info("Transactional email skipped kind=%s reason=disabled", kind)
        return EmailSendResult(
            ok=False,
            disabled=True,
            retryable=False,
            provider="disabled",
            error="Email sending is disabled.",
        )

    sender = from_address()
    if not sender or "@" not in sender:
        logger.warning("Transactional email failed kind=%s reason=missing_from", kind)
        return EmailSendResult(
            ok=False,
            retryable=False,
            error="The email sender address is not configured.",
        )

    provider = build_provider(settings)
    if provider is None:
        logger.warning("Transactional email failed kind=%s reason=unconfigured_provider", kind)
        return EmailSendResult(ok=False, retryable=False, error="Email service is not configured.")

    message = OutgoingEmail(
        to_address=recipient,
        subject=subject,
        text_body=text_body or "",
        html_body=html_body or "",
        from_address=sender,
        from_name=from_name(),
        reply_to=reply_to_address(),
    )
    timeout = int(getattr(settings, "smtp_timeout_seconds", 15) or 15)
    attempts = max(1, int(getattr(settings, "email_retry_attempts", 3) or 1))
    backoff_ms = max(0, int(getattr(settings, "email_retry_backoff_ms", 400) or 0))
    result = EmailSendResult(ok=False, error="The email could not be sent.", provider=provider.name)
    for attempt in range(1, attempts + 1):
        result = provider.send(message, timeout)
        if result.ok or result.disabled or not result.retryable:
            break
        if attempt < attempts:
            logger.warning(
                "Transactional email retry kind=%s attempt=%s provider=%s",
                kind,
                attempt,
                result.provider or provider.name,
            )
            if backoff_ms:
                time.sleep((backoff_ms / 1000.0) * attempt)
    if result.ok:
        logger.info("Transactional email accepted kind=%s provider=%s", kind, result.provider)
    else:
        logger.warning("Transactional email failed kind=%s provider=%s", kind, result.provider or provider.name)
    return result


def send_password_reset_pin(*, to_address: str, name: str, pin: str, minutes: int = 10) -> EmailSendResult:
    text_body, html_body = render_password_reset(
        name=name,
        pin=pin,
        minutes=minutes,
        office=office_name(),
    )
    return send_email(
        to_address=to_address,
        subject="Password reset",
        text_body=text_body,
        html_body=html_body,
        kind="password_reset",
    )


def send_profile_update_email(
    *,
    to_address: str,
    name: str,
    subject: str,
    message: str,
    fields: list[str],
    action_url: str,
) -> EmailSendResult:
    text_body, html_body = render_profile_update(
        name=name,
        office=office_name(),
        message=message,
        fields=fields,
        action_url=action_url,
    )
    return send_email(
        to_address=to_address,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        kind="profile_update",
    )


def send_account_status_email(
    *,
    to_address: str,
    name: str,
    status: str,
    reason: str = "",
) -> EmailSendResult:
    normalized = (status or "").strip().lower()
    if normalized == "active":
        headline = "Your CareerSense account was approved"
        intro = (
            "The Angeles University Foundation Office of Alumni Affairs and Placement Services "
            "has approved your CareerSense registration. You can now sign in to the alumni portal."
        )
        detail = ""
        path = "/login"
        cta = "Sign in to CareerSense"
        subject = "Account approved"
        template = "account_approved"
    elif normalized == "rejected":
        headline = "Registration rejected"
        intro = (
            "The Angeles University Foundation Office of Alumni Affairs and Placement Services "
            "was unable to approve your CareerSense registration."
        )
        detail = f"Reason: {reason.strip()}" if reason.strip() else "Please contact OAAPS for assistance."
        path = "/login"
        cta = "Review your account status"
        subject = "Registration rejected"
        template = "account_rejected"
    else:
        headline = "CareerSense account update"
        intro = "There is an update to your CareerSense account."
        detail = reason.strip()
        path = "/login"
        cta = "Open CareerSense"
        subject = "CareerSense account update"
        template = "account_rejected"
    text_body, html_body = render_account_status(
        name=name,
        office=office_name(),
        headline=headline,
        intro=intro,
        detail=detail,
        action_url=app_url(path),
        cta_label=cta,
        template=template,
    )
    return send_email(
        to_address=to_address,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        kind="account_status",
    )
