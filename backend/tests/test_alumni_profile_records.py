from app.models import Account
from app.services.reports import classify_graduate, employment_analytics, latest_submissions
from tests.conftest import auth_header, login

TINY_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def _headers(client, email="liza.torres@gmail.com"):
    data = login(client, email, "Alumni@2026")
    return auth_header(data["access_token"])


def test_pending_alumni_cannot_add_profile_records(client):
    headers = _headers(client, "juan.delacruz@gmail.com")
    assert client.post("/api/alumni/seminars", headers=headers, json={"title": "Career talk", "location": "AUF"}).status_code == 403
    assert client.post("/api/alumni/awards", headers=headers, json={"title": "Dean’s List"}).status_code == 403
    assert client.put(
        "/api/alumni/employment-status",
        headers=headers,
        json={"currently_unemployed": True, "unemployment_reason": "seeking"},
    ).status_code == 403


def test_employment_note_and_study_address(client):
    headers = _headers(client)

    created = client.post(
        "/api/alumni/studies",
        headers=headers,
        json={
            "course_degree": "Master of Science in Accountancy",
            "school": "Angeles University Foundation",
            "institution_address": "Angeles City, Pampanga",
            "year_enrolled": "2024",
            "is_graduated": False,
        },
    )
    assert created.status_code == 200, created.text
    study = next(row for row in created.json()["studies"] if row["course_degree"] == "Master of Science in Accountancy")
    assert study["institution_address"] == "Angeles City, Pampanga"

    dashboard = client.get("/api/alumni/dashboard", headers=headers)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert any(row["institution_address"] == "Angeles City, Pampanga" for row in body["further_studies"])

    client.delete(f"/api/alumni/studies/{study['id']}", headers=headers)


def test_currently_unemployed_preserves_jobs_and_tracer_counts(client, db_session):
    headers = _headers(client)
    before_jobs = client.get("/api/alumni/dashboard", headers=headers).json()["jobs"]
    job_ids = [row["id"] for row in before_jobs]
    current_ids = [row["id"] for row in before_jobs if row["is_current"]]
    assert job_ids and current_ids

    db_session.expire_all()
    before_stats = employment_analytics(db_session)

    missing = client.put("/api/alumni/employment-status", headers=headers, json={"currently_unemployed": True})
    assert missing.status_code == 400

    unspecified = client.put(
        "/api/alumni/employment-status",
        headers=headers,
        json={"currently_unemployed": True, "unemployment_reason": "other"},
    )
    assert unspecified.status_code == 400

    try:
        saved = client.put(
            "/api/alumni/employment-status",
            headers=headers,
            json={
                "currently_unemployed": True,
                "unemployment_reason": "seeking",
                "unemployment_details": "Applying to audit firms.",
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["currently_unemployed"] is True
        assert saved.json()["unemployment_reason"] == "seeking"
        assert saved.json()["unemployment_reason_label"] == "Currently Seeking Employment"

        blocked = client.post(
            "/api/alumni/jobs",
            headers=headers,
            json={"job_title": "Consultant", "company": "Independent", "is_current": True},
        )
        assert blocked.status_code == 400

        dashboard = client.get("/api/alumni/dashboard", headers=headers).json()
        assert [row["id"] for row in dashboard["jobs"]] == job_ids
        assert [row["id"] for row in dashboard["jobs"] if row["is_current"]] == current_ids
        assert dashboard["profile"]["currently_unemployed"] is True
        assert dashboard["career"]["employment_status"] == "No"
        survey = dashboard["latest_submission"]["data"]
        assert survey["is_currently_employed"] == "No"
        assert survey["reason_current"] == ["Looking for a job, but cannot find one"]
        assert survey["first_occ"] == "Associate Auditor"
        assert survey["pres_occ"] == "Restaurant Manager"
        assert dashboard["latest_submission"]["job_title"] in ("", None)

        db_session.expire_all()
        after_stats = employment_analytics(db_session)
        assert after_stats["employed"] == before_stats["employed"] - 1
        assert after_stats["unemployed"] == before_stats["unemployed"] + 1
        seeking = next(row for row in after_stats["reasons"] if row["label"] == "Looking for a job, but cannot find one")
        seeking_before = next((row["count"] for row in before_stats["reasons"] if row["label"] == seeking["label"]), 0)
        assert seeking["count"] == seeking_before + 1

        liza = db_session.query(Account).filter(Account.personal_email == "liza.torres@gmail.com").one()
        classified = classify_graduate(next(row for row in latest_submissions(db_session) if row.account_id == liza.id))
        assert classified["currently_employed"] is False
        assert classified["unemployed_seeking"] is True
        assert classified["workforce"] is False

        studies = client.put(
            "/api/alumni/employment-status",
            headers=headers,
            json={"currently_unemployed": True, "unemployment_reason": "further_studies", "unemployment_details": "MBA at AUF."},
        )
        assert studies.status_code == 200, studies.text
        db_session.expire_all()
        classified = classify_graduate(next(row for row in latest_submissions(db_session) if row.account_id == liza.id))
        assert classified["currently_employed"] is False
        assert classified["unemployed_seeking"] is False
        assert classified["unemployed_not_seeking"] is True

        not_seeking = client.put(
            "/api/alumni/employment-status",
            headers=headers,
            json={"currently_unemployed": True, "unemployment_reason": "not_seeking"},
        )
        assert not_seeking.status_code == 200, not_seeking.text
        assert not_seeking.json()["unemployment_reason_label"] == "Not Currently Seeking Employment"
        db_session.expire_all()
        classified = classify_graduate(next(row for row in latest_submissions(db_session) if row.account_id == liza.id))
        assert classified["unemployed_seeking"] is False
        assert classified["unemployed_not_seeking"] is True
        refreshed = client.get("/api/alumni/dashboard", headers=headers).json()
        assert refreshed["latest_submission"]["data"]["reason_current"] == ["Not Currently Seeking Employment"]
        assert [row["id"] for row in refreshed["jobs"]] == job_ids
    finally:
        restored = client.put("/api/alumni/employment-status", headers=headers, json={"currently_unemployed": False})
        assert restored.status_code == 200, restored.text

    again = client.get("/api/alumni/dashboard", headers=headers).json()
    assert again["profile"]["currently_unemployed"] is False
    assert [row["id"] for row in again["jobs"]] == job_ids
    assert [row["id"] for row in again["jobs"] if row["is_current"]] == current_ids
    assert again["latest_submission"]["data"]["is_currently_employed"] == "Yes"
    assert again["latest_submission"]["job_title"] == "Restaurant Manager"
    assert again["career"]["employment_status"] == "Yes"


def test_seminars_certifications_and_awards_round_trip(client):
    headers = _headers(client, "maria.reyes@gmail.com")
    seminar = client.post(
        "/api/alumni/seminars",
        headers=headers,
        json={"title": "Alumni Career Forum", "location": "AUF Main Campus", "held_on": "2024", "organizer": "OAAPS"},
    )
    assert seminar.status_code == 200, seminar.text
    saved = seminar.json()["seminars"][0]
    assert saved["location"] == "AUF Main Campus"

    missing = client.post(
        "/api/alumni/seminars",
        headers=headers,
        json={"title": "No location"},
    )
    assert missing.status_code == 400

    award = client.post(
        "/api/alumni/awards",
        headers=headers,
        json={"title": "College Leadership Award", "issuer": "College of Computing", "awarded_on": "2023", "description": "Student organization lead."},
    )
    assert award.status_code == 200, award.text
    award_row = next(row for row in award.json()["awards"] if row["title"] == "College Leadership Award")

    blank_url = client.post(
        "/api/alumni/certifications",
        headers=headers,
        data={"name": "AWS Cloud Practitioner", "awarded_on": "2024-05-01", "awarding_body": "Amazon Web Services", "verification_url": "not a link"},
        files={"certificate": ("badge.png", TINY_PNG, "image/png")},
    )
    assert blank_url.status_code == 400

    created = client.post(
        "/api/alumni/certifications",
        headers=headers,
        data={"name": "AWS Cloud Practitioner", "awarded_on": "2024-05-01", "awarding_body": "Amazon Web Services", "verification_url": "aws.amazon.com/verification/example"},
        files={"certificate": ("badge.png", TINY_PNG, "image/png")},
    )
    assert created.status_code == 200, created.text
    cert = next(row for row in created.json()["certifications"] if row["name"] == "AWS Cloud Practitioner")
    assert cert["has_certificate"] is True
    assert cert["verification_url"].startswith("https://aws.amazon.com/")

    opened = client.get(f"/api/alumni/certifications/{cert['id']}/file", headers=headers)
    assert opened.status_code == 200
    assert opened.content.startswith(b"\x89PNG")

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    admin_headers = auth_header(admin["access_token"])
    records = client.get("/api/admin/tracer", headers=admin_headers, params={"email": "maria.reyes@gmail.com"})
    assert records.status_code == 200
    detail = client.get(f"/api/admin/tracer/{records.json()['items'][0]['id']}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    activity = detail.json()["profile_activity"]
    assert any(row["title"] == "College Leadership Award" for row in activity["awards"])
    assert any(row["location"] == "AUF Main Campus" for row in activity["seminars"])
    assert any(row["name"] == "AWS Cloud Practitioner" for row in activity["certifications"])
    admin_file = client.get(f"/api/admin/certifications/{cert['id']}/file", headers=admin_headers)
    assert admin_file.status_code == 200

    client.delete(f"/api/alumni/seminars/{saved['id']}", headers=headers)
    client.delete(f"/api/alumni/awards/{award_row['id']}", headers=headers)
    client.delete(f"/api/alumni/certifications/{cert['id']}", headers=headers)
