from tests.conftest import auth_header, login


def test_alumni_cannot_download_unknown_resume(client):
    liza = login(client, "liza.torres@gmail.com", "Alumni@2026")
    response = client.get("/api/alumni/resumes/999999/file", headers=auth_header(liza["access_token"]))
    assert response.status_code == 404


def test_unauthenticated_admin_rejected(client):
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/admin/approvals").status_code == 401


def test_pending_alumni_blocked_from_dashboard(client):
    data = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/alumni/dashboard", headers=headers).status_code == 403
    assert client.get("/api/alumni/profile", headers=headers).status_code == 403
    assert client.get("/api/alumni/completion", headers=headers).status_code == 403
    assert client.get("/api/alumni/profile-completion", headers=headers).status_code == 403
    assert client.get("/api/alumni/achievements", headers=headers).status_code == 403
    assert client.get("/api/alumni/jobs", headers=headers).status_code == 403
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["user"]["status"] == "Pending"


def test_rejected_alumni_cannot_access_alumni_records(client):
    data = login(client, "ana.garcia@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/alumni/profile", headers=headers).status_code == 403
    assert client.get("/api/alumni/resumes", headers=headers).status_code == 403
    assert client.post(
        "/api/alumni/alignment/preview",
        headers=headers,
        json={"job_title": "Nurse", "degree": "Bachelor of Science in Nursing"},
    ).status_code == 403
    assert client.get("/api/alumni/dashboard", headers=headers).status_code == 403
    assert client.get("/api/alumni/completion", headers=headers).status_code == 403
    assert client.get("/api/alumni/profile-completion", headers=headers).status_code == 403
    assert client.get("/api/alumni/achievements", headers=headers).status_code == 403
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["user"]["status"] == "Rejected"


def test_active_alumni_can_access_portal(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/alumni/dashboard", headers=headers).status_code == 200
    assert client.get("/api/alumni/profile", headers=headers).status_code == 200
    assert client.get("/api/alumni/completion", headers=headers).status_code == 200
    assert client.get("/api/alumni/profile-completion", headers=headers).status_code == 200
    assert client.get("/api/alumni/achievements", headers=headers).status_code == 200
    assert client.get("/api/alumni/jobs", headers=headers).status_code == 200


def test_alumni_cannot_access_admin(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 403


def test_admin_can_access_admin_dashboard(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 200
    assert client.get("/api/alumni/dashboard", headers=headers).status_code == 403
    assert client.get("/api/alumni/completion", headers=headers).status_code == 403
    assert client.get("/api/alumni/profile-completion", headers=headers).status_code == 403
    assert client.get("/api/alumni/achievements", headers=headers).status_code == 403


def test_csv_formula_values_are_sanitized(client, db_session):
    from app.models import Account, TracerSubmission
    from app.services.validation import csv_safe

    assert csv_safe("=CMD()") == "'=CMD()"
    assert csv_safe("+1+1") == "'+1+1"
    assert csv_safe("Software Engineer") == "Software Engineer"

    maria = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    latest = (
        db_session.query(TracerSubmission)
        .filter(TracerSubmission.account_id == maria.id)
        .order_by(TracerSubmission.id.desc())
        .first()
    )
    data = dict(latest.data_json or {})
    data["first_name"] = "=1+1"
    latest.data_json = data
    db_session.commit()

    from tests.conftest import auth_header, login as do_login

    admin = do_login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    export = client.get("/api/admin/reports/export", headers=auth_header(admin["access_token"]))
    assert export.status_code == 200
    text = export.content.decode("utf-8")
    assert "'=1+1" in text
    assert text.splitlines()[0].startswith("email")
