from datetime import datetime, timezone

from app.models import Account, EmailOutbox, ProfileReminderSettings
from app.services.email.clock import campus_tz
from app.services.profile_reminders import reminder_is_due
from tests.conftest import auth_header, login


def _admin(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(data["access_token"])


def _alumni(client, email="maria.reyes@gmail.com"):
    data = login(client, email, "Alumni@2026")
    return auth_header(data["access_token"])


def _account_id(db_session, email):
    return db_session.query(Account).filter(Account.personal_email == email).one().id


def _ok_mail(**_kwargs):
    from app.services.email import EmailSendResult

    return EmailSendResult(ok=True, provider="resend")


def _payload(**overrides):
    body = {
        "enabled": True,
        "frequency": "weekly",
        "interval_days": 14,
        "send_hour": 9,
        "send_weekday": 0,
        "send_day_of_month": 1,
        "target_mode": "selected",
        "target_year": "",
        "target_degree": "",
        "target_completion": "",
        "alumni_ids": [],
        "requested_fields": ["employment", "contact"],
        "other_detail": "",
        "subject": "Action Required: Please Update Your CareerSense Profile",
        "message": "Please review and update your CareerSense profile this week.",
        "min_days_between": 14,
        "skip_if_complete": False,
    }
    body.update(overrides)
    return body


def test_profile_reminders_are_admin_only(client):
    url = "/api/admin/profile-reminders"
    assert client.get(url).status_code in (401, 403)
    assert client.get(url, headers=_alumni(client)).status_code == 403
    assert client.get(url, headers=_admin(client)).status_code == 200


def test_admin_saves_and_previews_reminder_settings(client, db_session):
    headers = _admin(client)
    maria_id = _account_id(db_session, "maria.reyes@gmail.com")
    saved = client.put(
        "/api/admin/profile-reminders",
        headers=headers,
        json=_payload(alumni_ids=[maria_id]),
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["enabled"] is True
    assert body["target_mode"] == "selected"
    assert maria_id in body["alumni_ids"]
    assert body["email_configured"] is False
    preview = client.get("/api/admin/profile-reminders/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "maria.reyes@gmail.com"


def test_selected_reminders_reject_inactive_alumni(client, db_session):
    headers = _admin(client)
    pending_id = _account_id(db_session, "juan.delacruz@gmail.com")
    response = client.put(
        "/api/admin/profile-reminders",
        headers=headers,
        json=_payload(alumni_ids=[pending_id]),
    )
    assert response.status_code == 400


def test_admin_can_send_reminder_now(client, db_session, monkeypatch):
    sent = []

    def fake_send(**kwargs):
        sent.append(kwargs)
        return _ok_mail()

    monkeypatch.setattr("app.services.email.service.send_email", fake_send)
    headers = _admin(client)
    maria_id = _account_id(db_session, "maria.reyes@gmail.com")
    saved = client.put(
        "/api/admin/profile-reminders",
        headers=headers,
        json=_payload(enabled=False, alumni_ids=[maria_id]),
    )
    assert saved.status_code == 200, saved.text
    ran = client.post("/api/admin/profile-reminders/run", headers=headers, json={"force": True})
    assert ran.status_code == 200, ran.text
    body = ran.json()
    assert body["ran"] is True
    assert body["run"]["sent_count"] == 1
    assert sent
    assert sent[0]["kind"] == "profile_update"
    assert "Alumni@2026" not in sent[0]["text_body"]
    assert "maria.reyes@gmail.com" == sent[0]["to_address"]
    notes = client.get("/api/alumni/notifications", headers=_alumni(client))
    assert any(row["category"] == "profile_update" for row in notes.json()["notifications"])


def test_reminder_skips_duplicate_within_window(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.email.service.send_email", lambda **kwargs: _ok_mail())
    headers = _admin(client)
    maria_id = _account_id(db_session, "maria.reyes@gmail.com")
    client.put("/api/admin/profile-reminders", headers=headers, json=_payload(alumni_ids=[maria_id]))
    first = client.post("/api/admin/profile-reminders/run", headers=headers, json={"force": True})
    assert first.status_code == 200, first.text
    assert first.json()["run"]["sent_count"] == 1
    second = client.post("/api/admin/profile-reminders/run", headers=headers, json={"force": False})
    assert second.status_code == 200, second.text
    assert second.json()["run"]["sent_count"] == 0
    assert second.json()["run"]["skipped_count"] == 1
    forced = client.post("/api/admin/profile-reminders/run", headers=headers, json={"force": True})
    assert forced.json()["run"]["sent_count"] == 1


def test_failed_reminder_is_queued_for_retry(client, db_session, monkeypatch):
    from app.services.email import EmailSendResult

    monkeypatch.setattr(
        "app.services.email.service.send_email",
        lambda **kwargs: EmailSendResult(ok=False, retryable=True, error="The email provider timed out."),
    )
    headers = _admin(client)
    maria_id = _account_id(db_session, "maria.reyes@gmail.com")
    client.put("/api/admin/profile-reminders", headers=headers, json=_payload(alumni_ids=[maria_id]))
    ran = client.post("/api/admin/profile-reminders/run", headers=headers, json={"force": True})
    assert ran.status_code == 200, ran.text
    assert ran.json()["run"]["failed_count"] == 1
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        queued = session.query(EmailOutbox).filter(EmailOutbox.kind == "profile_reminder").all()
        assert queued
        assert queued[0].status == "pending"
        assert "483921" not in queued[0].text_body
    finally:
        session.close()


def test_daily_reminder_is_due_only_after_send_hour(db_session):
    row = ProfileReminderSettings(
        id=99,
        enabled=True,
        frequency="daily",
        send_hour=9,
        send_weekday=0,
        send_day_of_month=1,
        interval_days=14,
        last_scheduled_run_at=None,
    )
    morning = datetime(2026, 9, 21, 8, 0, tzinfo=campus_tz())
    afternoon = datetime(2026, 9, 21, 10, 0, tzinfo=campus_tz())
    assert reminder_is_due(row, morning) is False
    assert reminder_is_due(row, afternoon) is False
    row.last_scheduled_run_at = datetime(2026, 9, 20, 1, 0, tzinfo=timezone.utc)
    assert reminder_is_due(row, afternoon) is True
    row.last_scheduled_run_at = datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc)
    assert reminder_is_due(row, afternoon) is False


def test_disabled_settings_are_never_due():
    row = ProfileReminderSettings(id=98, enabled=False, frequency="daily", send_hour=0)
    now = datetime(2026, 9, 21, 12, 0, tzinfo=campus_tz())
    assert reminder_is_due(row, now) is False
