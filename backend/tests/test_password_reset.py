from datetime import timedelta

import pytest

from app.models import Account, AdminLog, PasswordResetVerification
from app.rate_limit import forgot_limiter, pin_limiter, set_rate_limit_enabled
from app.security import hash_password, verify_password
from app.services.email import EmailSendResult
from app.services.password_reset import (
    GENERIC_SENT,
    INVALID_PIN,
    INVALID_RESET,
    LOCKED_PIN,
    MAX_PIN_ATTEMPTS,
    email_lookup_hash,
)
from app.services.validation import PASSWORD_HINT
from tests.conftest import auth_header, login


GENERIC = "If an account exists for this email address, a verification PIN has been sent."


@pytest.fixture(autouse=True)
def _clean_password_resets(db_session):
    db_session.query(PasswordResetVerification).delete()
    db_session.commit()
    yield


def _restore_password(db_session, email, password="Alumni@2026"):
    db_session.expire_all()
    account = db_session.query(Account).filter(Account.personal_email == email).one()
    account.password_hash = hash_password(password)
    account.password_changed_at = None
    db_session.commit()


def _ok_mail():
    return EmailSendResult(ok=True)


def _fail_mail():
    return EmailSendResult(ok=False, error="The email could not be sent.")


def _pin_sent(monkeypatch, pin="483921"):
    sent = []
    monkeypatch.setattr("app.services.password_reset.generate_pin", lambda: pin)

    def fake_send(**kwargs):
        sent.append(kwargs)
        return _ok_mail()

    monkeypatch.setattr("app.services.email.service.send_email", fake_send)
    return sent


def _open_row(db_session, email):
    db_session.expire_all()
    return (
        db_session.query(PasswordResetVerification)
        .filter(
            PasswordResetVerification.email_hash == email_lookup_hash(email),
            PasswordResetVerification.replaced_at.is_(None),
            PasswordResetVerification.used_at.is_(None),
        )
        .order_by(PasswordResetVerification.created_at.desc())
        .first()
    )


def test_forgot_password_registered_and_unregistered_are_generic(client, monkeypatch):
    sent = _pin_sent(monkeypatch)
    known = client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["message"] == GENERIC == unknown.json()["message"] == GENERIC_SENT
    assert set(known.json()) == set(unknown.json())
    assert known.json()["masked_email"] == "m***@gmail.com"
    assert unknown.json()["masked_email"] == "n***@example.com"
    assert known.json()["expires_in"] == 600
    assert len(sent) == 1
    assert sent[0]["to_address"] == "maria.reyes@gmail.com"
    assert sent[0]["subject"] == "Password reset"
    assert "483921" in sent[0]["text_body"]
    assert "Alumni@2026" not in sent[0]["text_body"]
    assert "injected@evil.com" not in str(sent[0])


def test_forgot_password_is_case_insensitive(client, monkeypatch, db_session):
    sent = _pin_sent(monkeypatch, "111111")
    response = client.post("/api/auth/forgot-password", json={"email": "Maria.Reyes@Gmail.com"})
    assert response.status_code == 200
    assert len(sent) == 1
    row = _open_row(db_session, "maria.reyes@gmail.com")
    assert row is not None
    assert row.account_id


def test_forgot_password_invalid_email(client):
    response = client.post("/api/auth/forgot-password", json={"email": "not-an-email"})
    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()


def test_forgot_password_does_not_store_plaintext_pin(client, monkeypatch, db_session):
    _pin_sent(monkeypatch, "483921")
    client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    row = _open_row(db_session, "maria.reyes@gmail.com")
    assert row is not None
    assert "483921" not in (row.pin_hash or "")
    assert "$" in row.pin_hash


def test_forgot_password_ignores_destination_override(client, monkeypatch):
    sent = _pin_sent(monkeypatch)
    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "maria.reyes@gmail.com", "to": "attacker@example.com", "destination": "attacker@example.com"},
    )
    assert response.status_code == 200
    assert sent[0]["to_address"] == "maria.reyes@gmail.com"


def test_forgot_password_email_failure_stays_generic(client, monkeypatch, db_session):
    monkeypatch.setattr("app.services.password_reset.generate_pin", lambda: "222222")
    monkeypatch.setattr("app.services.email.service.send_email", lambda **kwargs: _fail_mail())
    response = client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    assert response.status_code == 200
    assert response.json()["message"] == GENERIC
    row = _open_row(db_session, "maria.reyes@gmail.com")
    assert row is not None
    db_session.expire_all()
    assert (
        db_session.query(AdminLog)
        .filter(AdminLog.action_type == "password_reset_email_failed")
        .first()
    )


def test_registration_draft_is_not_a_login_account(client, monkeypatch):
    sent = _pin_sent(monkeypatch)
    response = client.post("/api/auth/forgot-password", json={"email": "draft-only@example.com"})
    assert response.status_code == 200
    assert response.json()["message"] == GENERIC
    assert sent == []


def test_correct_pin_issues_reset_token_not_pin(client, monkeypatch):
    _pin_sent(monkeypatch, "483921")
    client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    verified = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "maria.reyes@gmail.com", "pin": "483921"},
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert "reset_token" in body
    assert "483921" not in body["reset_token"]
    assert "verified" in body["message"].lower()


def test_incorrect_pin_and_six_digit_requirement(client, monkeypatch):
    _pin_sent(monkeypatch, "483921")
    client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    wrong = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "maria.reyes@gmail.com", "pin": "000000"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["detail"] == INVALID_PIN
    letters = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "maria.reyes@gmail.com", "pin": "abc123"},
    )
    assert letters.status_code == 400
    short = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "maria.reyes@gmail.com", "pin": "12345"},
    )
    assert short.status_code == 400


def test_pin_lockout_after_five_attempts(client, monkeypatch):
    _pin_sent(monkeypatch, "483921")
    client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    for _ in range(MAX_PIN_ATTEMPTS):
        response = client.post(
            "/api/auth/forgot-password/verify",
            json={"email": "maria.reyes@gmail.com", "pin": "000000"},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == LOCKED_PIN
    still = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "maria.reyes@gmail.com", "pin": "483921"},
    )
    assert still.status_code == 400
    assert still.json()["detail"] in {LOCKED_PIN, INVALID_PIN, INVALID_RESET}


def test_expired_pin_cannot_verify(client, monkeypatch):
    from app.services import password_reset as service

    _pin_sent(monkeypatch, "483921")
    real_now = service._now()
    monkeypatch.setattr(service, "_now", lambda: real_now)
    client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    monkeypatch.setattr(service, "_now", lambda: real_now + timedelta(minutes=11))
    expired = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "maria.reyes@gmail.com", "pin": "483921"},
    )
    assert expired.status_code == 400
    assert "expired" in expired.json()["detail"].lower()


def test_resend_cooldown_keeps_existing_pin(client, monkeypatch, db_session):
    sent = _pin_sent(monkeypatch, "483921")
    first = client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    assert first.status_code == 200
    row = _open_row(db_session, "maria.reyes@gmail.com")
    pin_hash = row.pin_hash
    again = client.post("/api/auth/forgot-password/resend", json={"email": "maria.reyes@gmail.com"})
    assert again.status_code == 200
    assert again.json()["message"] == GENERIC
    assert again.json()["resend_after"] > 0
    db_session.expire_all()
    row = _open_row(db_session, "maria.reyes@gmail.com")
    assert row.pin_hash == pin_hash
    assert len(sent) == 1


def test_new_pin_invalidates_previous_pin(client, monkeypatch, db_session):
    from app.services import password_reset as service

    pins = iter(["111111", "222222"])
    monkeypatch.setattr(service, "generate_pin", lambda: next(pins))
    monkeypatch.setattr("app.services.email.service.send_email", lambda **kwargs: _ok_mail())
    real_now = service._now()
    monkeypatch.setattr(service, "_now", lambda: real_now)
    client.post("/api/auth/forgot-password", json={"email": "liza.torres@gmail.com"})
    monkeypatch.setattr(service, "_now", lambda: real_now + timedelta(seconds=61))
    client.post("/api/auth/forgot-password/resend", json={"email": "liza.torres@gmail.com"})
    old = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "liza.torres@gmail.com", "pin": "111111"},
    )
    assert old.status_code == 400
    fresh = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "liza.torres@gmail.com", "pin": "222222"},
    )
    assert fresh.status_code == 200, fresh.text


def test_cannot_reset_without_verified_pin(client):
    response = client.post(
        "/api/auth/reset-password",
        json={"reset_token": "not-a-real-token", "new_password": "NewSecurePassword123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == INVALID_RESET


def test_reset_token_is_single_use_and_password_changes(client, monkeypatch, db_session):
    _pin_sent(monkeypatch, "483921")
    client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    verified = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "maria.reyes@gmail.com", "pin": "483921"},
    )
    token = verified.json()["reset_token"]
    previous = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    old_access = previous["access_token"]

    weak = client.post("/api/auth/reset-password", json={"reset_token": token, "new_password": "short"})
    assert weak.status_code == 400
    assert weak.json()["detail"] == PASSWORD_HINT

    changed = client.post(
        "/api/auth/reset-password",
        json={"reset_token": token, "new_password": "NewSecurePassword123"},
    )
    try:
        assert changed.status_code == 200, changed.text
        assert "updated successfully" in changed.json()["message"].lower()

        reused = client.post(
            "/api/auth/reset-password",
            json={"reset_token": token, "new_password": "AnotherValidPass1"},
        )
        assert reused.status_code == 400
        assert reused.json()["detail"] == INVALID_RESET

        assert login(client, "maria.reyes@gmail.com", "NewSecurePassword123")["user"]["status"] == "Active"
        failed = client.post("/api/auth/login", json={"email": "maria.reyes@gmail.com", "password": "Alumni@2026"})
        assert failed.status_code == 401

        me = client.get("/api/auth/me", headers=auth_header(old_access))
        assert me.status_code == 401

        db_session.expire_all()
        account = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
        assert verify_password("NewSecurePassword123", account.password_hash)
        assert not verify_password("Alumni@2026", account.password_hash)
        assert account.password_hash.startswith("$2")

        pin_again = client.post(
            "/api/auth/forgot-password/verify",
            json={"email": "maria.reyes@gmail.com", "pin": "483921"},
        )
        assert pin_again.status_code == 400
    finally:
        _restore_password(db_session, "maria.reyes@gmail.com")


def test_expired_reset_authorization_fails(client, monkeypatch):
    from app.services import password_reset as service

    _pin_sent(monkeypatch, "483921")
    real_now = service._now()
    monkeypatch.setattr(service, "_now", lambda: real_now)
    client.post("/api/auth/forgot-password", json={"email": "liza.torres@gmail.com"})
    verified = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "liza.torres@gmail.com", "pin": "483921"},
    )
    token = verified.json()["reset_token"]
    monkeypatch.setattr(service, "_now", lambda: real_now + timedelta(minutes=11))
    expired = client.post(
        "/api/auth/reset-password",
        json={"reset_token": token, "new_password": "NewSecurePassword123"},
    )
    assert expired.status_code == 400
    assert expired.json()["detail"] == INVALID_RESET


def test_admin_and_pending_can_recover_rejected_stays_rejected(client, monkeypatch, db_session):
    _pin_sent(monkeypatch, "654321")
    assert client.post("/api/auth/forgot-password", json={"email": "admin@auf.edu.ph"}).status_code == 200
    admin_ok = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "admin@auf.edu.ph", "pin": "654321"},
    )
    assert admin_ok.status_code == 200

    _pin_sent(monkeypatch, "111222")
    client.post("/api/auth/forgot-password", json={"email": "juan.delacruz@gmail.com"})
    pending = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "juan.delacruz@gmail.com", "pin": "111222"},
    )
    assert pending.status_code == 200
    reset = client.post(
        "/api/auth/reset-password",
        json={"reset_token": pending.json()["reset_token"], "new_password": "PendingPass123"},
    )
    assert reset.status_code == 200
    try:
        data = login(client, "juan.delacruz@gmail.com", "PendingPass123")
        assert data["user"]["status"] == "Pending"

        _pin_sent(monkeypatch, "333444")
        client.post("/api/auth/forgot-password", json={"email": "ana.garcia@gmail.com"})
        rejected = client.post(
            "/api/auth/forgot-password/verify",
            json={"email": "ana.garcia@gmail.com", "pin": "333444"},
        )
        assert rejected.status_code == 200
        reset_rejected = client.post(
            "/api/auth/reset-password",
            json={"reset_token": rejected.json()["reset_token"], "new_password": "RejectedPass123"},
        )
        assert reset_rejected.status_code == 200
        data = login(client, "ana.garcia@gmail.com", "RejectedPass123")
        assert data["user"]["status"] == "Rejected"
        assert client.get("/api/alumni/dashboard", headers=auth_header(data["access_token"])).status_code == 403
    finally:
        _restore_password(db_session, "juan.delacruz@gmail.com")
        _restore_password(db_session, "ana.garcia@gmail.com")


def test_forgot_password_rate_limit(client, monkeypatch):
    _pin_sent(monkeypatch, "123456")
    set_rate_limit_enabled(True)
    forgot_limiter.reset()
    original = forgot_limiter.limit
    forgot_limiter.limit = 3
    try:
        blocked = False
        for _ in range(6):
            response = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
            if response.status_code == 429:
                blocked = True
                assert "too many" in response.json()["detail"].lower()
                break
        assert blocked
    finally:
        forgot_limiter.limit = original
        forgot_limiter.reset()
        pin_limiter.reset()
        set_rate_limit_enabled(False)


def test_unregistered_pin_guess_does_not_reveal_account(client, monkeypatch):
    _pin_sent(monkeypatch)
    known = client.post("/api/auth/forgot-password", json={"email": "maria.reyes@gmail.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "missing@example.com"})
    assert known.json()["message"] == unknown.json()["message"]
    guess = client.post(
        "/api/auth/forgot-password/verify",
        json={"email": "missing@example.com", "pin": "000000"},
    )
    assert guess.status_code == 400
    assert guess.json()["detail"] == INVALID_PIN
