"""Transactional email providers. Credentials never leave the server."""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional, Protocol

import httpx

logger = logging.getLogger("careersense")

RESEND_URL = "https://api.resend.com/emails"


@dataclass(frozen=True)
class OutgoingEmail:
    to_address: str
    subject: str
    text_body: str
    html_body: str
    from_address: str
    from_name: str = "CareerSense"
    reply_to: str = ""


@dataclass(frozen=True)
class EmailSendResult:
    ok: bool
    error: str = ""
    disabled: bool = False
    provider: str = ""
    retryable: bool = False
    message_id: str = ""


class EmailProvider(Protocol):
    name: str

    def send(self, message: OutgoingEmail, timeout_seconds: int) -> EmailSendResult:
        ...


def _from_header(message: OutgoingEmail) -> str:
    name = (message.from_name or "CareerSense").strip()
    address = message.from_address.strip()
    if name:
        return f"{name} <{address}>"
    return address


class DisabledProvider:
    name = "disabled"

    def send(self, message: OutgoingEmail, timeout_seconds: int) -> EmailSendResult:
        return EmailSendResult(
            ok=False,
            disabled=True,
            retryable=False,
            provider=self.name,
            error="Email sending is disabled.",
        )


class SmtpProvider:
    name = "smtp"

    def __init__(self, host: str, port: int, username: str, password: str, use_tls: bool) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, message: OutgoingEmail, timeout_seconds: int) -> EmailSendResult:
        payload = EmailMessage()
        payload["Subject"] = message.subject
        payload["From"] = _from_header(message)
        payload["To"] = message.to_address
        if message.reply_to:
            payload["Reply-To"] = message.reply_to
        payload.set_content(message.text_body or "")
        if message.html_body:
            payload.add_alternative(message.html_body, subtype="html")
        timeout = max(5, int(timeout_seconds or 15))
        try:
            if self.port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, timeout=timeout, context=context) as smtp:
                    if self.username:
                        smtp.login(self.username, self.password)
                    smtp.send_message(payload)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=timeout) as smtp:
                    smtp.ehlo()
                    if self.use_tls:
                        smtp.starttls(context=ssl.create_default_context())
                        smtp.ehlo()
                    if self.username:
                        smtp.login(self.username, self.password)
                    smtp.send_message(payload)
        except smtplib.SMTPRecipientsRefused:
            logger.warning("SMTP recipient refused provider=smtp")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=False,
                error="The mail server refused the recipient address.",
            )
        except smtplib.SMTPAuthenticationError:
            logger.warning("SMTP authentication failed provider=smtp")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=False,
                error="The mail server rejected the CareerSense email login.",
            )
        except TimeoutError:
            logger.warning("SMTP timed out provider=smtp")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=True,
                error="The mail server timed out.",
            )
        except OSError:
            logger.warning("SMTP connection failed provider=smtp")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=True,
                error="Could not connect to the mail server.",
            )
        except Exception:
            logger.exception("SMTP send failed provider=smtp")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=True,
                error="The email could not be sent.",
            )
        return EmailSendResult(ok=True, provider=self.name)


class ResendProvider:
    name = "resend"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def send(self, message: OutgoingEmail, timeout_seconds: int) -> EmailSendResult:
        payload = {
            "from": _from_header(message),
            "to": [message.to_address],
            "subject": message.subject,
            "text": message.text_body or "",
            "html": message.html_body or "",
        }
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        timeout = max(5, int(timeout_seconds or 15))
        try:
            response = httpx.post(
                RESEND_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
        except httpx.TimeoutException:
            logger.warning("Resend timed out provider=resend")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=True,
                error="The email provider timed out.",
            )
        except httpx.RequestError:
            logger.warning("Resend connection failed provider=resend")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=True,
                error="Could not reach the email provider.",
            )
        except Exception:
            logger.exception("Resend send failed provider=resend")
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=True,
                error="The email could not be sent.",
            )
        if response.status_code >= 400:
            logger.warning("Resend rejected email status=%s provider=resend", response.status_code)
            permanent = response.status_code in {400, 401, 403, 404, 422}
            return EmailSendResult(
                ok=False,
                provider=self.name,
                retryable=not permanent,
                error=(
                    "The email provider rejected the CareerSense API credentials."
                    if response.status_code in {401, 403}
                    else "The email provider rejected the message."
                ),
            )
        message_id = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message_id = str(payload.get("id") or "")[:120]
        except Exception:
            message_id = ""
        return EmailSendResult(ok=True, provider=self.name, message_id=message_id)


def build_provider(settings) -> Optional[EmailProvider]:
    name = resolved_provider_name(settings)
    if name == "resend":
        key = (getattr(settings, "email_api_key", "") or "").strip()
        if not key:
            return None
        return ResendProvider(key)
    if name == "smtp":
        host = (getattr(settings, "smtp_host", "") or "").strip()
        if not host:
            return None
        return SmtpProvider(
            host=host,
            port=int(getattr(settings, "smtp_port", 587) or 587),
            username=(getattr(settings, "smtp_username", "") or "").strip(),
            password=getattr(settings, "smtp_password", "") or "",
            use_tls=bool(getattr(settings, "smtp_use_tls", True)),
        )
    return None


def resolved_provider_name(settings) -> str:
    raw = (getattr(settings, "email_provider", "") or "").strip().lower()
    if raw in {"resend", "smtp"}:
        return raw
    if (getattr(settings, "email_api_key", "") or "").strip():
        return "resend"
    if (getattr(settings, "smtp_host", "") or "").strip():
        return "smtp"
    return ""
