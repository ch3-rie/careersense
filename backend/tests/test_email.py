from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.email import send_email
from app.services.email.providers import EmailSendResult, OutgoingEmail, ResendProvider, SmtpProvider
from app.services.email.render import render_account_status, render_password_reset, render_profile_update
from app.services.email.service import send_account_status_email, send_password_reset_pin


def _settings(**overrides):
    values = dict(
        email_enabled=True,
        email_provider="resend",
        email_api_key="re_test_key",
        email_from_address="oaaps@auf.edu.ph",
        email_from_name="CareerSense",
        email_reply_to="",
        email_base_url="http://localhost:5173",
        public_app_url="http://localhost:5173",
        smtp_host="",
        smtp_port=587,
        smtp_username="",
        smtp_password="",
        smtp_from="",
        smtp_use_tls=True,
        smtp_timeout_seconds=15,
        oaaps_office_name="Office of Alumni Affairs and Placement Services",
        is_production=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_health_reports_email_configuration(client):
    body = client.get("/api/health").json()
    assert body["email_configured"] is False
    assert body["email_enabled"] is False
    assert body["email_provider"] == ""
    assert body["email_scheduler"] is False


def test_disabled_email_does_not_report_success(monkeypatch):
    from app.services.email import service as email_service

    monkeypatch.setattr(email_service, "get_settings", lambda: _settings(email_enabled=False))
    result = send_email(
        to_address="maria.reyes@gmail.com",
        subject="CareerSense Password Reset Verification",
        text_body="PIN 483921",
        html_body="<p>483921</p>",
        kind="password_reset",
    )
    assert result.ok is False
    assert result.disabled is True
    assert "disabled" in result.error.lower()


def test_resend_provider_posts_to_api(monkeypatch):
    from app.services.email import service as email_service
    from app.services.email import providers as email_providers

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"id": "msg_1"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["authorization_prefix"] = (headers or {}).get("Authorization", "")[:7]
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(email_providers.httpx, "post", fake_post)
    result = send_password_reset_pin(
        to_address="maria.reyes@gmail.com",
        name="Maria",
        pin="483921",
    )
    assert result.ok is True
    assert result.provider == "resend"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["authorization_prefix"] == "Bearer "
    assert captured["json"]["to"] == ["maria.reyes@gmail.com"]
    assert captured["json"]["subject"] == "Password reset"
    assert "483921" in captured["json"]["text"]
    assert "Alumni@2026" not in captured["json"]["text"]
    assert "never ask for your password" in captured["json"]["text"].lower()


def test_resend_provider_failure_is_not_success(monkeypatch):
    class Response:
        status_code = 401

    provider = ResendProvider("re_test_key")
    monkeypatch.setattr(
        "app.services.email.providers.httpx.post",
        lambda *args, **kwargs: Response(),
    )
    result = provider.send(
        OutgoingEmail(
            to_address="maria.reyes@gmail.com",
            subject="Test",
            text_body="hello",
            html_body="<p>hello</p>",
            from_address="oaaps@auf.edu.ph",
        ),
        15,
    )
    assert result.ok is False
    assert result.provider == "resend"


def test_smtp_provider_submits_message(monkeypatch):
    sent = []

    class DummySMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None):
            return None

        def login(self, username, password):
            sent.append(("login", username))

        def send_message(self, message):
            sent.append(("send", message["To"], message["Subject"]))

    monkeypatch.setattr("app.services.email.providers.smtplib.SMTP", DummySMTP)
    provider = SmtpProvider("smtp.example.com", 587, "oaaps@auf.edu.ph", "not-a-real-password", True)
    result = provider.send(
        OutgoingEmail(
            to_address="maria.reyes@gmail.com",
            subject="CareerSense Password Reset Verification",
            text_body="PIN 483921",
            html_body="<p>483921</p>",
            from_address="oaaps@auf.edu.ph",
            from_name="CareerSense",
        ),
        15,
    )
    assert result.ok is True
    assert result.provider == "smtp"
    assert ("send", "maria.reyes@gmail.com", "CareerSense Password Reset Verification") in sent


def test_password_reset_template_escapes_html():
    text, html = render_password_reset(
        name='<script>alert(1)</script>',
        pin="483921",
        minutes=10,
        office="OAAPS",
    )
    assert "483921" in text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_profile_update_template_contains_action_link():
    text, html = render_profile_update(
        name="Maria Reyes",
        office="Office of Alumni Affairs and Placement Services",
        message="Please update your employment information.",
        fields=["Employment information", "Profile photo"],
        action_url="http://localhost:5173/alumni",
    )
    assert "Employment information" in text
    assert "Update My Profile" in html
    assert "http://localhost:5173/alumni" in html


def test_account_status_templates():
    text, html = render_account_status(
        name="Juan",
        office="OAAPS",
        headline="Your CareerSense account was approved",
        intro="You can now sign in.",
        detail="",
        action_url="http://localhost:5173/login",
        cta_label="Sign in to CareerSense",
        template="account_approved",
    )
    assert "You can now sign in." in text
    assert "Sign in to CareerSense" in html


def test_placeholder_resend_key_fails_when_email_enabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production-use-123456")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("EMAIL_API_KEY", "re_your_key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "oaaps@auf.edu.ph")
    monkeypatch.setenv("EMAIL_BASE_URL", "http://localhost:5173")
    with pytest.raises(RuntimeError, match="EMAIL_API_KEY"):
        Settings().prepare()


def test_enabled_resend_requires_from_address(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production-use-123456")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("EMAIL_API_KEY", "re_live_not_a_placeholder_key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "oaaps@your-verified-domain")
    monkeypatch.setenv("EMAIL_BASE_URL", "http://localhost:5173")
    with pytest.raises(RuntimeError, match="EMAIL_FROM_ADDRESS"):
        Settings().prepare()


def test_production_email_configuration_required(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://careersense:careersense@localhost:5432/careersense")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-not-for-tests-123456")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "")
    monkeypatch.setenv("EMAIL_API_KEY", "")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "")
    with pytest.raises(RuntimeError, match="EMAIL_PROVIDER"):
        Settings().prepare()


def test_production_rejects_disabled_email(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://careersense:careersense@localhost:5432/careersense")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-not-for-tests-123456")
    monkeypatch.setenv("EMAIL_ENABLED", "false")
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("EMAIL_API_KEY", "re_test")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "oaaps@auf.edu.ph")
    with pytest.raises(RuntimeError, match="EMAIL_ENABLED"):
        Settings().prepare()


def test_production_accepts_resend_configuration(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://careersense:careersense@localhost:5432/careersense")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-not-for-tests-123456")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("EMAIL_API_KEY", "re_test_key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "oaaps@auf.edu.ph")
    monkeypatch.setenv("EMAIL_BASE_URL", "https://careersense.auf.edu.ph")
    settings = Settings().prepare()
    assert settings.resolved_email_provider() == "resend"
    assert settings.email_provider_ready() is True


def test_notice_subjects_match_events(monkeypatch):
    from app.services.email.dispatch import send_notice

    captured = []
    monkeypatch.setattr(
        "app.services.email.dispatch.send_email",
        lambda **kwargs: captured.append(kwargs) or EmailSendResult(ok=True, provider="resend"),
    )
    monkeypatch.setattr(
        "app.services.email.service.send_email",
        lambda **kwargs: captured.append(kwargs) or EmailSendResult(ok=True, provider="resend"),
    )
    send_notice(
        None,
        kind="registration_received",
        to_address="liza.torres@gmail.com",
        account_id=1,
        name="Liza",
        subject="Registration received",
        headline="Registration received",
        intro="CareerSense received your registration.",
    )
    rejected = send_account_status_email(
        to_address="liza.torres@gmail.com",
        name="Liza",
        status="Rejected",
        reason="Record could not be verified.",
    )
    assert rejected.ok is True
    subjects = [item["subject"] for item in captured]
    assert subjects == ["Registration received", "Registration rejected"]
    assert "Record could not be verified." in captured[1]["text_body"]


def test_account_status_helper_uses_provider(monkeypatch):
    from app.services.email import service as email_service

    captured = []

    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        email_service,
        "send_email",
        lambda **kwargs: captured.append(kwargs) or EmailSendResult(ok=True, provider="resend"),
    )
    result = send_account_status_email(
        to_address="juan.delacruz@gmail.com",
        name="Juan",
        status="Active",
    )
    assert result.ok is True
    assert captured[0]["kind"] == "account_status"
    assert captured[0]["to_address"] == "juan.delacruz@gmail.com"
    assert "approved" in captured[0]["subject"].lower()


def test_send_email_retries_transient_failure(monkeypatch):
    from app.services.email import service as email_service
    from app.services.email.providers import EmailSendResult

    attempts = []

    class Provider:
        name = "resend"

        def send(self, message, timeout_seconds):
            attempts.append(timeout_seconds)
            if len(attempts) < 2:
                return EmailSendResult(ok=False, retryable=True, provider="resend", error="timeout")
            return EmailSendResult(ok=True, provider="resend", message_id="msg_retry")

    monkeypatch.setattr(email_service, "get_settings", lambda: _settings(email_retry_attempts=3, email_retry_backoff_ms=0))
    monkeypatch.setattr(email_service, "build_provider", lambda settings: Provider())
    monkeypatch.setattr(email_service.time, "sleep", lambda seconds: None)
    result = send_email(
        to_address="maria.reyes@gmail.com",
        subject="CareerSense Password Reset Verification",
        text_body="PIN 483921",
        html_body="<p>483921</p>",
        kind="password_reset",
    )
    assert result.ok is True
    assert len(attempts) == 2


def test_send_email_does_not_retry_invalid_credentials(monkeypatch):
    from app.services.email import service as email_service
    from app.services.email.providers import EmailSendResult

    attempts = []

    class Provider:
        name = "resend"

        def send(self, message, timeout_seconds):
            attempts.append(1)
            return EmailSendResult(
                ok=False,
                retryable=False,
                provider="resend",
                error="The email provider rejected the CareerSense API credentials.",
            )

    monkeypatch.setattr(email_service, "get_settings", lambda: _settings(email_retry_attempts=3, email_retry_backoff_ms=0))
    monkeypatch.setattr(email_service, "build_provider", lambda settings: Provider())
    result = send_email(
        to_address="maria.reyes@gmail.com",
        subject="CareerSense Password Reset Verification",
        text_body="PIN 483921",
        html_body="<p>483921</p>",
        kind="password_reset",
    )
    assert result.ok is False
    assert len(attempts) == 1


def test_outbox_refuses_password_reset_bodies(db_session):
    from app.services.email.outbox import enqueue

    row = enqueue(
        db_session,
        kind="password_reset",
        to_address="maria.reyes@gmail.com",
        subject="PIN",
        text_body="483921",
        html_body="<p>483921</p>",
    )
    assert row is None
    db_session.rollback()


def test_outbox_retries_profile_update(db_session, monkeypatch):
    from app.models import EmailOutbox
    from app.services.email.outbox import enqueue, process_outbox
    from app.services.email.providers import EmailSendResult

    sent = []

    monkeypatch.setattr(
        "app.services.email.outbox.send_email",
        lambda **kwargs: sent.append(kwargs) or EmailSendResult(ok=True, provider="resend", message_id="msg_2"),
    )
    db_session.query(EmailOutbox).delete()
    db_session.commit()
    row = enqueue(
        db_session,
        kind="profile_update",
        to_address="maria.reyes@gmail.com",
        subject="Please update your profile",
        text_body="Please update your employment information.",
        html_body="<p>Please update your employment information.</p>",
        account_id=None,
        meta={},
    )
    db_session.commit()
    processed = process_outbox(db_session)
    db_session.commit()
    assert processed == 1
    assert sent[0]["kind"] == "profile_update"
    stored = db_session.get(EmailOutbox, row.id)
    assert stored.status == "sent"
    assert "483921" not in stored.text_body
