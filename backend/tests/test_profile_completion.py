from app.models import AlumniBadge, AlumniNotification
from app.services.profile_completion import CATEGORY_WEIGHTS, PROFILE_COMPLETE_KEY, progress_from_snapshot
from tests.conftest import auth_header, login

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
)


def _category(progress, category_id):
    return next(row for row in progress["categories"] if row["id"] == category_id)


def _complete_snapshot(**overrides):
    snapshot = {
        "first_name": "Maria",
        "last_name": "Reyes",
        "degree": "Bachelor of Science in Information Technology",
        "year_graduated": "2022",
        "phone": "+63 917 555 0101",
        "city": "Angeles City",
        "country": "Philippines",
        "photo_path": "/photos/maria.jpg",
        "has_tracer": True,
        "tracer_required_ok": True,
        "ever_employed": "Yes",
        "currently_employed": True,
        "current_employment_answer": "Yes",
        "occupation": "Software Engineer",
        "employer": "North Luzon Systems Corp.",
        "first_occ": "Junior Software Developer",
        "first_emp": "Pampanga Digital Labs",
        "related": "Yes",
        "enroll_further_studies": "No",
        "studies": [],
        "jobs": [],
        "job_count": 0,
        "card_status": "Claimed",
    }
    snapshot.update(overrides)
    return snapshot


def test_weights_sum_to_100():
    assert sum(CATEGORY_WEIGHTS.values()) == 100


def test_empty_profile_is_incomplete():
    progress = progress_from_snapshot({})
    assert progress["is_complete"] is False
    assert progress["percent"] < 100
    assert progress["missing_sections"]


def test_complete_snapshot_is_100():
    progress = progress_from_snapshot(_complete_snapshot())
    assert progress["percent"] == 100
    assert progress["percentage"] == 100
    assert progress["is_complete"] is True
    assert progress["status"] == "Complete"
    assert progress["missing_sections"] == []


def test_missing_photo_is_not_complete_and_not_100():
    progress = progress_from_snapshot(_complete_snapshot(photo_path=""))
    assert progress["percent"] == 90
    assert progress["is_complete"] is False
    assert progress["percent"] < 100
    assert _category(progress, "photo")["complete"] is False


def test_incomplete_never_reports_100_percent():
    progress = progress_from_snapshot(_complete_snapshot(phone="", city=""))
    assert progress["is_complete"] is False
    assert progress["percent"] < 100


def test_unemployed_alumni_are_not_penalized_for_employer_fields():
    progress = progress_from_snapshot(
        _complete_snapshot(
            ever_employed="No",
            currently_employed=False,
            current_employment_answer="No",
            occupation="",
            employer="",
            first_occ="",
            first_emp="",
            related="",
            job_count=0,
            jobs=[],
        )
    )
    employment = _category(progress, "employment")
    assert employment["complete"] is True
    assert progress["is_complete"] is True


def test_employed_alumni_need_current_occupation_and_employer():
    progress = progress_from_snapshot(_complete_snapshot(occupation="", employer="", related=""))
    employment = _category(progress, "employment")
    assert employment["complete"] is False
    assert progress["is_complete"] is False
    joined = " ".join(employment["missing"]).lower()
    assert "occupation" in joined
    assert "employer" in joined


def test_not_currently_employed_does_not_require_current_employer():
    progress = progress_from_snapshot(
        _complete_snapshot(
            currently_employed=False,
            current_employment_answer="No",
            occupation="",
            employer="",
            related="",
            ever_employed="Yes",
            first_occ="IT Support Specialist",
            first_emp="Angeles Medical Center",
        )
    )
    employment = _category(progress, "employment")
    assert employment["complete"] is True
    assert not any("current employer" in item.lower() for item in employment["missing"])


def test_further_studies_no_is_complete():
    assert _category(progress_from_snapshot(_complete_snapshot(enroll_further_studies="No", studies=[])), "further_studies")["complete"] is True


def test_further_studies_yes_requires_program_details():
    studies = _category(progress_from_snapshot(_complete_snapshot(enroll_further_studies="Yes", studies=[])), "further_studies")
    assert studies["complete"] is False


def test_further_studies_yes_with_program_is_complete():
    progress = progress_from_snapshot(
        _complete_snapshot(
            enroll_further_studies="Yes",
            studies=[{"course_degree": "MBA", "school": "Angeles University Foundation"}],
        )
    )
    assert _category(progress, "further_studies")["complete"] is True


def test_no_tracer_zeroes_conditional_sections():
    progress = progress_from_snapshot(
        _complete_snapshot(
            has_tracer=False,
            tracer_required_ok=False,
            ever_employed="",
            currently_employed=False,
            current_employment_answer="",
            occupation="",
            employer="",
            enroll_further_studies="",
        )
    )
    assert _category(progress, "tracer")["complete"] is False
    assert _category(progress, "employment")["complete"] is False
    assert progress["is_complete"] is False


def test_dashboard_and_profile_completion_endpoint_match(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    dashboard = client.get("/api/alumni/dashboard", headers=headers)
    completion = client.get("/api/alumni/profile-completion", headers=headers)
    alias = client.get("/api/alumni/completion", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    assert completion.status_code == 200, completion.text
    assert alias.status_code == 200
    left = dashboard.json()["completion"]
    right = completion.json()
    assert left["percent"] == right["percent"] == alias.json()["percent"]
    assert right["percentage"] == right["percent"]
    assert "is_complete" in right
    assert right["badge"]["key"] == PROFILE_COMPLETE_KEY
    assert len(right["achievements"]) == 6
    assert {row["id"] for row in left["categories"]} == set(CATEGORY_WEIGHTS)


def test_badge_not_awarded_below_100(client, db_session):
    from app.models import Account

    maria = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    db_session.query(AlumniBadge).filter(
        AlumniBadge.account_id == maria.id,
        AlumniBadge.badge_key.in_([PROFILE_COMPLETE_KEY, "record_complete"]),
    ).delete(synchronize_session=False)
    db_session.commit()

    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    client.delete("/api/alumni/profile/photo", headers=headers)
    body = client.get("/api/alumni/profile-completion", headers=headers)
    assert body.status_code == 200
    payload = body.json()
    assert payload["percent"] < 100
    assert payload["is_complete"] is False
    assert payload["badge"]["earned"] is False
    maria = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    db_session.expire_all()
    assert (
        db_session.query(AlumniBadge)
        .filter(AlumniBadge.account_id == maria.id, AlumniBadge.badge_key == PROFILE_COMPLETE_KEY)
        .count()
        == 0
    )


def _official_gts():
    return {
        "first_name": "Maria",
        "last_name": "Reyes",
        "country": "Philippines",
        "degree": "Bachelor of Science in Information Technology",
        "year_graduated": "2022",
        "ever_employed": "Yes",
        "is_currently_employed": "Yes",
        "present_job_is_first": "No",
        "pres_occ": "Software Engineer",
        "pres_emp": "North Luzon Systems Corp.",
        "first_occ": "Junior Software Developer",
        "first_emp": "Pampanga Digital Labs",
        "first_related": "Yes",
        "first_stat": "Regular/Permanent",
        "present_related_degree": "Yes",
        "enroll_further_studies": "No",
        "skills": ["Python", "SQL"],
    }


def test_badge_awarded_once_at_100_and_persists_after_drop(client, db_session):
    from app.models import Account

    maria = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    db_session.query(AlumniBadge).filter(
        AlumniBadge.account_id == maria.id,
        AlumniBadge.badge_key.in_([PROFILE_COMPLETE_KEY, "record_complete"]),
    ).delete(synchronize_session=False)
    db_session.query(AlumniNotification).filter(
        AlumniNotification.account_id == maria.id,
        AlumniNotification.category == "achievement",
    ).delete(synchronize_session=False)
    db_session.commit()

    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    client.delete("/api/alumni/profile/photo", headers=headers)
    client.put(
        "/api/alumni/profile",
        headers=headers,
        json={"phone": "+63 917 555 0101", "city": "Angeles City", "country_residence": "Philippines"},
    )
    saved_gts = client.post("/api/alumni/gts", headers=headers, json=_official_gts())
    assert saved_gts.status_code == 200, saved_gts.text
    before = client.get("/api/alumni/profile-completion", headers=headers).json()
    assert before["badge"]["earned"] is False

    uploaded = client.post(
        "/api/alumni/profile/photo",
        headers=headers,
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    completion = uploaded.json()["completion"]
    assert completion["percent"] == 100
    assert completion["is_complete"] is True
    assert completion["badge"]["earned"] is True
    assert completion["badge"]["awarded_at"]
    notes = uploaded.json()["notifications"]
    profile_notes = [
        row
        for row in notes
        if row["category"] == "achievement" and "Profile Complete" in (row.get("body") or row.get("title") or "")
    ]
    assert len(profile_notes) == 1

    again = client.post(
        "/api/alumni/profile/photo",
        headers=headers,
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    assert again.status_code == 200
    maria = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    db_session.expire_all()
    assert (
        db_session.query(AlumniBadge)
        .filter(AlumniBadge.account_id == maria.id, AlumniBadge.badge_key == PROFILE_COMPLETE_KEY)
        .count()
        == 1
    )
    assert (
        db_session.query(AlumniNotification)
        .filter(
            AlumniNotification.account_id == maria.id,
            AlumniNotification.category == "achievement",
            AlumniNotification.body.like("%Profile Complete%"),
        )
        .count()
        == 1
    )

    removed = client.delete("/api/alumni/profile/photo", headers=headers)
    assert removed.status_code == 200
    after = removed.json()["completion"]
    assert after["percent"] < 100
    assert after["is_complete"] is False
    assert after["badge"]["earned"] is True

    refreshed = client.get("/api/alumni/profile-completion", headers=headers).json()
    assert refreshed["badge"]["earned"] is True
    assert refreshed["percent"] < 100


def test_get_home_does_not_notify_for_incomplete_profile(client, db_session):
    from app.models import Account

    liza = db_session.query(Account).filter(Account.personal_email == "liza.torres@gmail.com").one()
    db_session.query(AlumniNotification).filter(
        AlumniNotification.account_id == liza.id,
        AlumniNotification.category == "achievement",
    ).delete(synchronize_session=False)
    db_session.commit()

    data = login(client, "liza.torres@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    first = client.get("/api/alumni/dashboard", headers=headers)
    assert first.status_code == 200
    db_session.expire_all()
    assert (
        db_session.query(AlumniNotification)
        .filter(AlumniNotification.account_id == liza.id, AlumniNotification.category == "achievement")
        .count()
        == 0
    )
    second = client.get("/api/alumni/dashboard", headers=headers)
    assert second.status_code == 200
    db_session.expire_all()
    assert (
        db_session.query(AlumniNotification)
        .filter(AlumniNotification.account_id == liza.id, AlumniNotification.category == "achievement")
        .count()
        == 0
    )


def test_pending_rejected_admin_and_anonymous_cannot_read_completion(client):
    pending = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    rejected = login(client, "ana.garcia@gmail.com", "Alumni@2026")
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    for token in (pending["access_token"], rejected["access_token"], admin["access_token"]):
        assert client.get("/api/alumni/profile-completion", headers=auth_header(token)).status_code == 403
        assert client.get("/api/alumni/completion", headers=auth_header(token)).status_code == 403
        assert client.get("/api/alumni/achievements", headers=auth_header(token)).status_code == 403
    assert client.get("/api/alumni/profile-completion").status_code in (401, 403)
