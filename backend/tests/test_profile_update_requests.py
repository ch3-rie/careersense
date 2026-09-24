from tests.conftest import auth_header, login


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
)


def _admin(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(data["access_token"])


def _alumni(client, email="maria.reyes@gmail.com"):
    data = login(client, email, "Alumni@2026")
    return auth_header(data["access_token"]), data


def _account_id(db_session, email):
    from app.models import Account

    return db_session.query(Account).filter(Account.personal_email == email).one().id


def _ok_mail(**_kwargs):
    from app.services.email import EmailSendResult

    return EmailSendResult(ok=True)


def test_profile_update_authorization(client):
    url = "/api/admin/profile-update-requests"
    assert client.get(url).status_code in (401, 403)
    maria = _alumni(client)[0]
    assert client.get(url, headers=maria).status_code == 403
    pending = _alumni(client, "juan.delacruz@gmail.com")[0]
    assert client.get(url, headers=pending).status_code == 403
    rejected = _alumni(client, "ana.garcia@gmail.com")[0]
    assert client.get(url, headers=rejected).status_code == 403
    assert client.get(url, headers=_admin(client)).status_code == 200


def test_profile_update_alumni_search_is_active_only(client, db_session):
    headers = _admin(client)
    listing = client.get("/api/admin/profile-update-requests/alumni?page_size=50", headers=headers)
    assert listing.status_code == 200, listing.text
    emails = {row["email"] for row in listing.json()["items"]}
    assert "maria.reyes@gmail.com" in emails
    assert "liza.torres@gmail.com" in emails
    assert "juan.delacruz@gmail.com" not in emails
    assert "ana.garcia@gmail.com" not in emails
    search = client.get("/api/admin/profile-update-requests/alumni?q=2020-0001", headers=headers)
    assert search.status_code == 200
    assert any(row["student_id"] == "2020-0001" for row in search.json()["items"])


def test_admin_sends_profile_update_notification_and_email(client, db_session, monkeypatch):
    sent = []

    def fake_send(**kwargs):
        sent.append(kwargs)
        return _ok_mail()

    monkeypatch.setattr("app.services.email.service.send_email", fake_send)
    headers = _admin(client)
    maria_id = _account_id(db_session, "maria.reyes@gmail.com")
    liza_id = _account_id(db_session, "liza.torres@gmail.com")
    created = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={
            "alumni_ids": [maria_id, liza_id, maria_id],
            "requested_fields": ["employment", "work_history", "profile_photo"],
            "subject": "Action Required: Please Update Your CareerSense Profile",
            "message": "Please review and update your employment information and profile photo.",
            "email": "injected@example.com",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["recipient_count"] == 2
    assert body["email_sent_count"] == 2
    assert body["email_failed_count"] == 0
    assert body["status"] == "Sent"
    assert "injected@example.com" not in str(body)
    assert {row["email"] for row in body["recipients"]} == {"maria.reyes@gmail.com", "liza.torres@gmail.com"}
    assert len(sent) == 2
    assert {item["to_address"] for item in sent} == {"maria.reyes@gmail.com", "liza.torres@gmail.com"}
    assert "employment information" in sent[0]["text_body"].lower() or "Employment information" in sent[0]["html_body"]
    assert "Update My Profile" in sent[0]["html_body"]
    assert "/alumni" in sent[0]["html_body"]
    assert sent[0]["subject"].startswith("Action Required")

    notes = client.get("/api/alumni/notifications", headers=_alumni(client)[0])
    assert notes.status_code == 200
    items = notes.json()["notifications"]
    update = next(row for row in items if row["category"] == "profile_update")
    assert update["read"] is False
    assert notes.json()["unread_count"] >= 1
    assert update["link"] in {
        "/alumni",
        "/alumni#profile",
        "/alumni#contact",
        "/alumni#work-history",
        "/alumni/resume",
    }
    assert "Employment information" in update["body"]
    assert "Profile photo" in update["body"]

    other = client.post(f"/api/alumni/notifications/{update['id']}/read", headers=_alumni(client, "liza.torres@gmail.com")[0])
    assert other.status_code == 404

    marked = client.post(f"/api/alumni/notifications/{update['id']}/read", headers=_alumni(client)[0])
    assert marked.status_code == 200
    saved = next(row for row in marked.json()["notifications"] if row["id"] == update["id"])
    assert saved["read"] is True
    detail = client.get(f"/api/admin/profile-update-requests/{body['id']}", headers=headers)
    maria_row = next(row for row in detail.json()["recipients"] if row["email"] == "maria.reyes@gmail.com")
    assert maria_row["viewed_at"]
    assert maria_row["completed_at"] is None
    assert detail.json()["status"] != "Completed"

    from app.models import AdminLog

    db_session.expire_all()
    log = (
        db_session.query(AdminLog)
        .filter(AdminLog.action_type == "profile_update_request", AdminLog.target_id == str(body["id"]))
        .one()
    )
    assert log.new_value["email_sent"] == 2
    assert "smtp" not in str(log.new_value).lower()


def test_profile_update_rejects_ineligible_recipients(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.email.service.send_email", lambda **kwargs: _ok_mail())
    headers = _admin(client)
    rejected_id = _account_id(db_session, "ana.garcia@gmail.com")
    pending_id = _account_id(db_session, "juan.delacruz@gmail.com")
    maria_id = _account_id(db_session, "maria.reyes@gmail.com")
    payload = {
        "requested_fields": ["phone"],
        "subject": "Action Required: Please Update Your CareerSense Profile",
        "message": "Please update your phone number on file.",
    }
    bad = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={**payload, "alumni_ids": [999999]},
    )
    assert bad.status_code == 400
    rejected = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={**payload, "alumni_ids": [rejected_id]},
    )
    assert rejected.status_code == 400
    pending = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={**payload, "alumni_ids": [pending_id]},
    )
    assert pending.status_code == 400
    mixed = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={**payload, "alumni_ids": [maria_id, rejected_id]},
    )
    assert mixed.status_code == 400


def test_profile_update_partial_email_failure(client, db_session, monkeypatch):
    def fake_send(**kwargs):
        from app.services.email import EmailSendResult

        if kwargs["to_address"] == "liza.torres@gmail.com":
            return EmailSendResult(ok=False, error="The mail server timed out.")
        return EmailSendResult(ok=True)

    monkeypatch.setattr("app.services.email.service.send_email", fake_send)
    headers = _admin(client)
    created = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={
            "alumni_ids": [
                _account_id(db_session, "maria.reyes@gmail.com"),
                _account_id(db_session, "liza.torres@gmail.com"),
            ],
            "requested_fields": ["city"],
            "subject": "Action Required: Please Update Your CareerSense Profile",
            "message": "Please confirm the city on your alumni profile.",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "Partially Sent"
    assert body["email_sent_count"] == 1
    assert body["email_failed_count"] == 1
    assert "1 email failed" in body["message_summary"]
    liza = next(row for row in body["recipients"] if row["email"] == "liza.torres@gmail.com")
    assert liza["email_status"] == "failed"
    notes = client.get("/api/alumni/notifications", headers=_alumni(client, "liza.torres@gmail.com")[0])
    assert any(row["category"] == "profile_update" for row in notes.json()["notifications"])


def test_profile_update_duplicate_requires_explicit_resend(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.email.service.send_email", lambda **kwargs: _ok_mail())
    headers = _admin(client)
    payload = {
        "alumni_ids": [_account_id(db_session, "maria.reyes@gmail.com")],
        "requested_fields": ["country"],
        "subject": "Action Required: Please Update Your CareerSense Profile",
        "message": "Please confirm your country of residence.",
    }
    first = client.post("/api/admin/profile-update-requests", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    second = client.post("/api/admin/profile-update-requests", headers=headers, json=payload)
    assert second.status_code == 409
    assert second.json()["detail"]["duplicates"]
    retry = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={**payload, "force_resend": True},
    )
    assert retry.status_code == 200, retry.text


def test_profile_update_completes_only_after_requested_fields_change(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.email.service.send_email", lambda **kwargs: _ok_mail())
    headers = _admin(client)
    liza_id = _account_id(db_session, "liza.torres@gmail.com")
    created = client.post(
        "/api/admin/profile-update-requests",
        headers=headers,
        json={
            "alumni_ids": [liza_id],
            "requested_fields": ["profile_photo"],
            "subject": "Action Required: Please Update Your CareerSense Profile",
            "message": "Please add a profile photo to your alumni profile.",
        },
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["id"]
    liza = _alumni(client, "liza.torres@gmail.com")[0]
    contact = client.put(
        "/api/alumni/profile",
        headers=liza,
        json={"phone": "+63 900 000 1111", "city": "Mabalacat", "country_residence": "Philippines"},
    )
    assert contact.status_code == 200, contact.text
    still_open = client.get(f"/api/admin/profile-update-requests/{request_id}", headers=headers)
    assert still_open.json()["status"] != "Completed"
    assert still_open.json()["recipients"][0]["completed_at"] is None

    uploaded = client.post(
        "/api/alumni/profile/photo",
        headers=liza,
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    done = client.get(f"/api/admin/profile-update-requests/{request_id}", headers=headers)
    assert done.json()["status"] == "Completed"
    assert done.json()["recipients"][0]["completed_at"]
    notes = client.get("/api/alumni/notifications", headers=liza)
    update = next(row for row in notes.json()["notifications"] if row["category"] == "profile_update")
    assert update["read"] is True
