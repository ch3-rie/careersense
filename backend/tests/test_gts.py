from tests.conftest import auth_header, login


def _gts_payload(**overrides):
    payload = {
        "first_name": "Maria",
        "last_name": "Reyes",
        "degree": "Bachelor of Science in Information Technology",
        "year_graduated": "2022",
        "ever_employed": "Yes",
        "is_currently_employed": "Yes",
        "present_job_is_first": "No",
        "pres_occ": "Software Engineer",
        "first_occ": "Junior Software Developer",
        "first_emp": "Pampanga Digital Labs",
        "first_related": "Yes",
        "first_stat": "Regular/Permanent",
        "skills": ["Python", "SQL"],
    }
    payload.update(overrides)
    return payload


def test_valid_gts_update(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.post("/api/alumni/gts", headers=auth_header(data["access_token"]), json=_gts_payload())
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True


def test_missing_job_title_when_employed(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.post(
        "/api/alumni/gts",
        headers=auth_header(data["access_token"]),
        json=_gts_payload(pres_occ="", first_occ="", present_job_is_first="No"),
    )
    assert response.status_code == 400
    assert "occupation" in response.json()["detail"].lower() or "job title" in response.json()["detail"].lower()


def test_duplicate_skills_do_not_500(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.post(
        "/api/alumni/gts",
        headers=auth_header(data["access_token"]),
        json=_gts_payload(skills=["Python", "Python", "python", " SQL ", "SQL"]),
    )
    assert response.status_code == 200, response.text


def test_rejected_cannot_submit_gts(client):
    data = login(client, "ana.garcia@gmail.com", "Alumni@2026")
    response = client.post("/api/alumni/gts", headers=auth_header(data["access_token"]), json=_gts_payload())
    assert response.status_code == 403


def test_cannot_attach_another_accounts_resume(client):
    data = login(client, "liza.torres@gmail.com", "Alumni@2026")
    response = client.post(
        "/api/alumni/gts",
        headers=auth_header(data["access_token"]),
        json=_gts_payload(
            first_name="Liza",
            last_name="Torres",
            degree="Bachelor of Science in Accountancy",
            resume_id=999999,
        ),
    )
    assert response.status_code == 400
    assert "resume" in response.json()["detail"].lower()


def test_present_is_first_persists_first_occupation(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    response = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts_payload(
            present_job_is_first="Yes",
            first_occ="Software Engineer",
            first_emp="AUF Systems",
            pres_occ="",
            pres_emp="",
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["alignment_status"] != "Unknown"
    profile = client.get("/api/alumni/profile", headers=headers).json()
    gts = profile["latest_gts"]
    assert gts["current_occupation"] == "Software Engineer"
    assert gts["current_employer"] == "AUF Systems"
    assert gts["first_occ"] == "Software Engineer"


def test_later_gts_update_changes_official_occupation(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    first = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts_payload(
            present_job_is_first="Yes",
            first_occ="Software Engineer",
            first_emp="AUF Systems",
            pres_occ="",
        ),
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts_payload(
            present_job_is_first="No",
            first_occ="Junior Software Developer",
            first_emp="Pampanga Digital Labs",
            pres_occ="Software Engineer",
            pres_emp="North Luzon Systems Corp.",
        ),
    )
    assert second.status_code == 200, second.text
    profile = client.get("/api/alumni/profile", headers=headers).json()
    assert profile["latest_gts"]["current_occupation"] == "Software Engineer"
    assert profile["latest_gts"]["current_employer"] == "North Luzon Systems Corp."


def test_same_employer_different_roles_stay_separate(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    response = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts_payload(
            present_job_is_first="No",
            first_occ="Software Developer",
            first_emp="ABC Corporation",
            pres_occ="Systems Analyst",
            pres_emp="ABC Corporation",
        ),
    )
    assert response.status_code == 200, response.text
    profile = client.get("/api/alumni/profile", headers=headers).json()
    gts = profile["latest_gts"]
    assert gts["first_occ"] == "Software Developer"
    assert gts["pres_occ"] == "Systems Analyst"
    assert gts["first_emp"] == gts["pres_emp"] == "ABC Corporation"
    assert gts["current_occupation"] == "Systems Analyst"
    assert gts["present_job_is_first"] == "No"


def test_hidden_pres_occ_does_not_replace_missing_first_occ(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.post(
        "/api/alumni/gts",
        headers=auth_header(data["access_token"]),
        json=_gts_payload(
            present_job_is_first="Yes",
            first_occ="",
            pres_occ="Software Engineer",
        ),
    )
    assert response.status_code == 400


def test_closed_survey_blocks_pending_gts(client):
    from tests.test_registration import _register

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    admin_headers = auth_header(admin["access_token"])
    start = _register(client, "qa.pending.closed@gmail.com", first_name="Pending", last_name="Closed")
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": start.json()["registration_token"],
            "first_name": "Pending",
            "last_name": "Closed",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
        },
    )
    assert complete.status_code == 200, complete.text
    token = complete.json()["access_token"]
    client.put(
        "/api/admin/survey/settings",
        headers=admin_headers,
        json={"accepting_responses": False, "allow_alumni_edit": True},
    )
    try:
        blocked = client.post(
            "/api/alumni/gts",
            headers=auth_header(token),
            json={
                "first_name": "Pending",
                "last_name": "Closed",
                "degree": "Bachelor of Science in Information Technology",
                "year_graduated": "2024",
                "ever_employed": "No",
                "is_currently_employed": "No",
            },
        )
        assert blocked.status_code == 400
        assert "not currently accepting" in blocked.json()["detail"].lower()
    finally:
        client.put(
            "/api/admin/survey/settings",
            headers=admin_headers,
            json={"accepting_responses": True, "allow_alumni_edit": True},
        )


def test_open_survey_allows_pending_gts(client):
    from tests.test_registration import _register

    start = _register(client, "qa.pending.open@gmail.com", first_name="Pending", last_name="Open")
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": start.json()["registration_token"],
            "first_name": "Pending",
            "last_name": "Open",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
        },
    )
    assert complete.status_code == 200, complete.text
    updated = client.post(
        "/api/alumni/gts",
        headers=auth_header(complete.json()["access_token"]),
        json={
            "first_name": "Pending",
            "last_name": "Open",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "Yes",
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_occ": "Software Engineer",
            "first_emp": "AUF Systems",
            "first_related": "Yes",
            "first_stat": "Regular/Permanent",
            "skills": ["Python"],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["alignment_status"] != "Unknown"


def test_resume_upload_does_not_overwrite_official_gts(client):
    from io import BytesIO

    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    saved = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts_payload(
            present_job_is_first="Yes",
            first_occ="Software Engineer",
            first_emp="AUF Systems",
            pres_occ="",
            pres_emp="",
        ),
    )
    assert saved.status_code == 200, saved.text
    upload = client.post(
        "/api/alumni/resumes",
        headers=headers,
        files={
            "resume": (
                "other.txt",
                BytesIO(b"Maria Cruz Reyes\nBSIT 2022\nCashier\nQuick Mart\nSkills: POS\n"),
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200, upload.text
    profile = client.get("/api/alumni/profile", headers=headers).json()
    assert profile["latest_gts"]["current_occupation"] == "Software Engineer"
    assert profile["latest_gts"]["current_employer"] == "AUF Systems"
