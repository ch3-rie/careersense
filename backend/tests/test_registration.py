from io import BytesIO

from tests.conftest import auth_header, login, unique_resume


def _register(client, email, password="Alumni@2026", first_name="Unique", last_name="Graduate"):
    return client.post(
        "/api/auth/register",
        data={
            "email": email,
            "password": password,
            "confirm_password": password,
            "privacy_consent": "true",
        },
        files={"resume": ("resume.txt", BytesIO(unique_resume(first_name, last_name)), "text/plain")},
    )


def test_invalid_email_rejected(client):
    response = _register(client, "not-an-email")
    assert response.status_code == 400
    assert "valid email" in response.json()["detail"].lower()


def test_duplicate_email_pending_message(client):
    response = _register(client, "juan.delacruz@gmail.com")
    assert response.status_code == 400
    assert "awaiting review" in response.json()["detail"].lower()


def test_duplicate_active_email(client):
    response = _register(client, "maria.reyes@gmail.com")
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_registration_token_completes_and_creates_pending_account(client):
    start = _register(client, "carlos.mendoza@gmail.com")
    assert start.status_code == 200, start.text
    body = start.json()
    token = body["registration_token"]
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": token,
            "first_name": "Carlos",
            "last_name": "Mendoza",
            "degree": "Bachelor of Science in Computer Science",
            "year_graduated": "2024",
            "ever_employed": "Yes",
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_occ": "Software Developer",
            "first_emp": "AUF Systems",
            "first_related": "Yes",
            "first_stat": "Regular/Permanent",
            "pres_occ": "Software Developer",
            "skills": ["Python", "Python", "python", "SQL"],
        },
    )
    assert complete.status_code == 200, complete.text
    data = complete.json()
    assert data["user"]["status"] == "Pending"
    assert data["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(data["access_token"]))
    assert me.status_code == 200
    assert me.json()["user"]["personal_email"] == "carlos.mendoza@gmail.com"


def test_access_token_cannot_complete_registration(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    response = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": admin["access_token"],
            "first_name": "X",
            "last_name": "Y",
            "degree": "BSIT",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
        },
    )
    assert response.status_code == 400


def test_present_first_job_without_pres_occ_is_official(client, db_session):
    from app.models import Account, TracerSubmission

    start = _register(client, "qa.firstocc.only@gmail.com", first_name="First", last_name="Only")
    assert start.status_code == 200, start.text
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": start.json()["registration_token"],
            "first_name": "First",
            "last_name": "Only",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "Yes",
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_occ": "Software Engineer",
            "first_emp": "AUF Systems",
            "first_related": "Yes",
            "first_stat": "Regular/Permanent",
            "pres_occ": "",
            "pres_emp": "",
            "skills": ["Python"],
        },
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["alignment_status"] != "Unknown"
    headers = auth_header(body["access_token"])
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["user"]["status"] == "Pending"
    user = db_session.query(Account).filter(Account.personal_email == "qa.firstocc.only@gmail.com").one()
    latest = (
        db_session.query(TracerSubmission)
        .filter(TracerSubmission.account_id == user.id)
        .order_by(TracerSubmission.id.desc())
        .first()
    )
    assert latest.data_json["current_occupation"] == "Software Engineer"
    assert latest.data_json["current_employer"] == "AUF Systems"
    assert latest.data_json["first_occ"] == "Software Engineer"


def test_unemployed_complete_has_no_current_occupation(client, db_session):
    from app.models import Account, TracerSubmission

    start = _register(client, "qa.unemployed@gmail.com", first_name="Unemployed", last_name="Graduate")
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": start.json()["registration_token"],
            "first_name": "Unemployed",
            "last_name": "Graduate",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
            "first_occ": "Software Engineer",
        },
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["alignment_status"] == "Unknown"
    user = db_session.query(Account).filter(Account.personal_email == "qa.unemployed@gmail.com").one()
    latest = (
        db_session.query(TracerSubmission)
        .filter(TracerSubmission.account_id == user.id)
        .order_by(TracerSubmission.id.desc())
        .first()
    )
    assert latest.data_json["current_occupation"] == ""
    assert latest.data_json["current_employer"] == ""


def test_closed_survey_blocks_registration_complete(client, db_session):
    from app.models import Account

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    client.put(
        "/api/admin/survey/settings",
        headers=headers,
        json={"accepting_responses": False, "allow_alumni_edit": True},
    )
    try:
        start = _register(client, "qa.closed.survey@gmail.com", first_name="Closed", last_name="Survey")
        assert start.status_code == 200, start.text
        complete = client.post(
            "/api/auth/register/complete",
            json={
                "registration_token": start.json()["registration_token"],
                "first_name": "Closed",
                "last_name": "Survey",
                "degree": "Bachelor of Science in Information Technology",
                "year_graduated": "2024",
                "ever_employed": "No",
                "is_currently_employed": "No",
            },
        )
        assert complete.status_code == 400
        assert "not currently accepting" in complete.json()["detail"].lower()
        assert db_session.query(Account).filter(Account.personal_email == "qa.closed.survey@gmail.com").first() is None
        from app.models import RegistrationDraft

        db_session.expire_all()
        draft = db_session.query(RegistrationDraft).filter(RegistrationDraft.personal_email == "qa.closed.survey@gmail.com").first()
        assert draft is not None
    finally:
        client.put(
            "/api/admin/survey/settings",
            headers=headers,
            json={"accepting_responses": True, "allow_alumni_edit": True},
        )


def test_reopened_survey_allows_registration_complete(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    client.put(
        "/api/admin/survey/settings",
        headers=headers,
        json={"accepting_responses": False, "allow_alumni_edit": True},
    )
    client.put(
        "/api/admin/survey/settings",
        headers=headers,
        json={"accepting_responses": True, "allow_alumni_edit": True},
    )
    start = _register(client, "qa.reopened.survey@gmail.com", first_name="Reopened", last_name="Survey")
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": start.json()["registration_token"],
            "first_name": "Reopened",
            "last_name": "Survey",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
        },
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["user"]["status"] == "Pending"


def test_complete_rejects_student_id_already_linked(client, db_session):
    from app.models import Account, RegistrationDraft

    start = _register(client, "qa.linked.id@gmail.com", first_name="Link", last_name="Conflict")
    assert start.status_code == 200, start.text
    maria = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    draft = db_session.query(RegistrationDraft).filter(RegistrationDraft.personal_email == "qa.linked.id@gmail.com").one()
    draft.linked_student_id = maria.linked_student_id
    db_session.commit()
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": start.json()["registration_token"],
            "first_name": "Link",
            "last_name": "Conflict",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
        },
    )
    assert complete.status_code == 409
    assert db_session.query(Account).filter(Account.personal_email == "qa.linked.id@gmail.com").first() is None


def test_compound_given_name_matches_registry_first_token():
    from app.routers.auth import _names_match

    assert _names_match("Sean", "Sean Gabriel") is True
    assert _names_match("Sean Gabriel", "Sean") is True
    assert _names_match("Maria", "Ana") is False
