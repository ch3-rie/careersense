from io import BytesIO

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Account, AlumniBadge, AlumniNotification, Resume, TracerSubmission
from app.services.achievements import (
    CATALOG_KEYS,
    PROFILE_COMPLETE_KEY,
    AchievementService,
    evaluate_alumni_card_holder,
    evaluate_career_updated,
    evaluate_profile_complete,
    evaluate_resume_ready,
    evaluate_tracer_completed,
)
from app.services.alumni_hub import set_alumni_card_status
from app.services.profile_completion import progress_from_snapshot
from tests.conftest import SAMPLE_RESUME, auth_header, login

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
)

MARIA = "maria.reyes@gmail.com"


def _account(db_session, email=MARIA):
    return db_session.query(Account).filter(Account.personal_email == email).one()


def _clear_achievements(db_session, email=MARIA, *, detach_resume=True):
    account = _account(db_session, email)
    db_session.query(AlumniBadge).filter(AlumniBadge.account_id == account.id).delete(synchronize_session=False)
    db_session.query(AlumniNotification).filter(
        AlumniNotification.account_id == account.id,
        AlumniNotification.category == "achievement",
    ).delete(synchronize_session=False)
    if detach_resume:
        latest = (
            db_session.query(TracerSubmission)
            .filter(TracerSubmission.account_id == account.id)
            .order_by(TracerSubmission.submitted_at.desc())
            .first()
        )
        if latest is not None:
            latest.resume_id = None
    db_session.commit()
    db_session.expire_all()
    return account


def _by_key(payload):
    return {row["key"]: row for row in payload["achievements"]}


def _gts(**overrides):
    payload = {
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
    payload.update(overrides)
    return payload


def _complete_progress_snapshot(**overrides):
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
        "resume_id": 1,
        "resume_usable": True,
    }
    snapshot.update(overrides)
    return snapshot


def test_catalog_has_six_core_achievements():
    assert CATALOG_KEYS == (
        "profile_complete",
        "resume_ready",
        "tracer_completed",
        "career_updated",
        "alumni_card_holder",
        "careersense_alumni",
    )


def test_profile_complete_requires_exactly_100():
    complete = progress_from_snapshot(_complete_progress_snapshot())
    almost = progress_from_snapshot(_complete_progress_snapshot(photo_path=""))
    assert complete["percent"] == 100
    assert evaluate_profile_complete(_complete_progress_snapshot(), complete) is True
    assert almost["percent"] == 99 or almost["percent"] < 100
    assert evaluate_profile_complete(_complete_progress_snapshot(photo_path=""), almost) is False


def test_resume_ready_requires_reviewed_submission_not_upload():
    assert evaluate_resume_ready({"has_tracer": False, "resume_id": 1, "resume_usable": True}) is False
    assert evaluate_resume_ready({"has_tracer": True, "tracer_required_ok": True, "resume_id": None, "resume_usable": True}) is False
    assert evaluate_resume_ready({"has_tracer": True, "tracer_required_ok": True, "resume_id": 1, "resume_usable": False}) is False
    assert evaluate_resume_ready({"has_tracer": True, "tracer_required_ok": True, "resume_id": 1, "resume_usable": True}) is True


def test_tracer_completed_requires_valid_submission():
    assert evaluate_tracer_completed({"has_tracer": False, "tracer_required_ok": False}) is False
    assert evaluate_tracer_completed({"has_tracer": True, "tracer_required_ok": False}) is False
    assert evaluate_tracer_completed({"has_tracer": True, "tracer_required_ok": True}) is True


def test_career_updated_uses_current_employment_only():
    employed = _complete_progress_snapshot()
    unemployed = _complete_progress_snapshot(
        currently_employed=False,
        current_employment_answer="No",
        occupation="",
        employer="",
        related="",
    )
    old_job_only = _complete_progress_snapshot(
        currently_employed=False,
        current_employment_answer="No",
        occupation="",
        employer="",
        related="",
        first_occ="Junior Software Developer",
        first_emp="Pampanga Digital Labs",
        jobs=[{"title": "Junior Software Developer", "employer": "Pampanga Digital Labs", "is_current": False}],
        job_count=1,
    )
    first_job = _complete_progress_snapshot(
        present_is_first=True,
        occupation="Junior Software Developer",
        employer="Pampanga Digital Labs",
        related="Yes",
    )
    present_job = _complete_progress_snapshot(
        present_is_first=False,
        occupation="Software Engineer",
        employer="North Luzon Systems Corp.",
        related="Yes",
    )
    assert evaluate_career_updated(unemployed) is False
    assert evaluate_career_updated(old_job_only) is False
    assert evaluate_career_updated(first_job) is True
    assert evaluate_career_updated(present_job) is True
    assert evaluate_career_updated(employed) is True


def test_alumni_card_holder_claimed_only():
    assert evaluate_alumni_card_holder({"card_status": "Approved"}) is False
    assert evaluate_alumni_card_holder({"card_status": "ReadyForPickup"}) is False
    assert evaluate_alumni_card_holder({"card_status": "ForVerification"}) is False
    assert evaluate_alumni_card_holder({"card_status": "Claimed"}) is True


def test_careersense_alumni_requires_five_cores():
    four = {"profile_complete", "resume_ready", "tracer_completed", "career_updated"}
    five = four | {"alumni_card_holder"}
    assert AchievementService.evaluate_careersense_alumni(four) is False
    assert AchievementService.evaluate_careersense_alumni(five) is True


def test_achievements_endpoint_returns_catalog(client, db_session):
    _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    response = client.get("/api/alumni/achievements", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_count"] == 6
    assert [row["key"] for row in payload["achievements"]] == list(CATALOG_KEYS)
    keys = _by_key(payload)
    assert "earned" in keys["profile_complete"]
    assert keys["tracer_completed"]["name"] == "Tracer Completed"
    dashboard = client.get("/api/alumni/dashboard", headers=headers).json()
    assert [row["key"] for row in dashboard["completion"]["achievements"]] == list(CATALOG_KEYS)


def test_pending_rejected_admin_cannot_read_achievements(client):
    pending = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    rejected = login(client, "ana.garcia@gmail.com", "Alumni@2026")
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    for token in (pending["access_token"], rejected["access_token"], admin["access_token"]):
        assert client.get("/api/alumni/achievements", headers=auth_header(token)).status_code == 403
    assert client.get("/api/alumni/achievements").status_code in (401, 403)
    assert client.post("/api/alumni/achievements").status_code in (401, 405, 422)


def test_resume_upload_alone_does_not_award_resume_ready(client, db_session):
    _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    uploaded = client.post(
        "/api/alumni/resumes",
        headers=headers,
        files={"resume": ("resume.txt", BytesIO(SAMPLE_RESUME), "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(payload)["resume_ready"]["earned"] is False


def test_resume_ready_after_review_and_gts_submit(client, db_session):
    account = _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    uploaded = client.post(
        "/api/alumni/resumes",
        headers=headers,
        files={"resume": ("resume.txt", BytesIO(SAMPLE_RESUME), "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    resume_id = uploaded.json()["resume_id"]
    saved = client.post("/api/alumni/gts", headers=headers, json=_gts(resume_id=resume_id))
    assert saved.status_code == 200, saved.text
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(payload)["resume_ready"]["earned"] is True
    db_session.expire_all()
    assert (
        db_session.query(AlumniBadge)
        .filter(AlumniBadge.account_id == account.id, AlumniBadge.badge_key == "resume_ready")
        .count()
        == 1
    )
    client.post("/api/alumni/gts", headers=headers, json=_gts(resume_id=resume_id))
    db_session.expire_all()
    assert (
        db_session.query(AlumniBadge)
        .filter(AlumniBadge.account_id == account.id, AlumniBadge.badge_key == "resume_ready")
        .count()
        == 1
    )


def test_failed_parse_does_not_award_resume_ready(client, db_session):
    account = _clear_achievements(db_session)
    empty = Resume(
        account_id=account.id,
        original_filename="empty.txt",
        stored_path="missing.txt",
        extracted_text="",
        parsed_json={},
        parser_source="heuristic",
    )
    db_session.add(empty)
    db_session.commit()
    db_session.refresh(empty)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    saved = client.post("/api/alumni/gts", headers=headers, json=_gts(resume_id=empty.id))
    assert saved.status_code == 200, saved.text
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(payload)["resume_ready"]["earned"] is False


def test_tracer_and_career_from_gts(client, db_session):
    _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    unemployed = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts(
            is_currently_employed="No",
            present_job_is_first="No",
            pres_occ="",
            pres_emp="",
            present_related_degree="",
        ),
    )
    assert unemployed.status_code == 200, unemployed.text
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    keys = _by_key(payload)
    assert keys["tracer_completed"]["earned"] is True
    assert keys["career_updated"]["earned"] is False

    first_job = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts(
            present_job_is_first="Yes",
            first_occ="Software Engineer",
            first_emp="AUF Systems",
            first_related="Yes",
            pres_occ="",
            pres_emp="",
        ),
    )
    assert first_job.status_code == 200, first_job.text
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(payload)["career_updated"]["earned"] is True

    present_job = client.post(
        "/api/alumni/gts",
        headers=headers,
        json=_gts(present_job_is_first="No", pres_occ="Product Engineer", pres_emp="North Luzon Systems Corp."),
    )
    assert present_job.status_code == 200, present_job.text
    db_session.expire_all()
    maria = _account(db_session)
    assert (
        db_session.query(AlumniBadge)
        .filter(AlumniBadge.account_id == maria.id, AlumniBadge.badge_key == "career_updated")
        .count()
        == 1
    )
    assert (
        db_session.query(AlumniBadge)
        .filter(AlumniBadge.account_id == maria.id, AlumniBadge.badge_key == "tracer_completed")
        .count()
        == 1
    )


def test_alumni_card_holder_status_gates(client, db_session):
    maria = _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    set_alumni_card_status(db_session, maria, "Approved", notify=False)
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(payload)["alumni_card_holder"]["earned"] is False
    set_alumni_card_status(db_session, maria, "ReadyForPickup", notify=False)
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(payload)["alumni_card_holder"]["earned"] is False
    set_alumni_card_status(db_session, maria, "Claimed", notify=True)
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(payload)["alumni_card_holder"]["earned"] is True
    db_session.expire_all()
    notes = (
        db_session.query(AlumniNotification)
        .filter(
            AlumniNotification.account_id == maria.id,
            AlumniNotification.category == "achievement",
        )
        .all()
    )
    holder_notes = [row for row in notes if "Alumni Card Holder" in (row.body or "")]
    assert len(holder_notes) == 1
    set_alumni_card_status(db_session, maria, "Claimed", notify=True)
    db_session.expire_all()
    assert (
        db_session.query(AlumniNotification)
        .filter(
            AlumniNotification.account_id == maria.id,
            AlumniNotification.category == "achievement",
            AlumniNotification.body.like("%Alumni Card Holder%"),
        )
        .count()
        == 1
    )


def test_careersense_alumni_after_five_cores(client, db_session):
    account = _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    client.delete("/api/alumni/profile/photo", headers=headers)
    uploaded = client.post(
        "/api/alumni/resumes",
        headers=headers,
        files={"resume": ("resume.txt", BytesIO(SAMPLE_RESUME), "text/plain")},
    )
    resume_id = uploaded.json()["resume_id"]
    client.post("/api/alumni/gts", headers=headers, json=_gts(resume_id=resume_id))
    set_alumni_card_status(db_session, account, "Claimed", notify=True)
    before = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(before)["careersense_alumni"]["earned"] is False
    photo = client.post(
        "/api/alumni/profile/photo",
        headers=headers,
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    assert photo.status_code == 200, photo.text
    payload = client.get("/api/alumni/achievements", headers=headers).json()
    keys = _by_key(payload)
    assert keys["profile_complete"]["earned"] is True
    assert keys["resume_ready"]["earned"] is True
    assert keys["tracer_completed"]["earned"] is True
    assert keys["career_updated"]["earned"] is True
    assert keys["alumni_card_holder"]["earned"] is True
    assert keys["careersense_alumni"]["earned"] is True
    db_session.expire_all()
    assert (
        db_session.query(AlumniBadge)
        .filter(AlumniBadge.account_id == account.id, AlumniBadge.badge_key == "careersense_alumni")
        .count()
        == 1
    )


def test_earned_badge_persists_when_profile_drops(client, db_session):
    _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    client.post(
        "/api/alumni/profile/photo",
        headers=headers,
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    client.post("/api/alumni/gts", headers=headers, json=_gts())
    earned = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(earned)["profile_complete"]["earned"] is True
    removed = client.delete("/api/alumni/profile/photo", headers=headers)
    assert removed.status_code == 200
    after = removed.json()["completion"]
    assert after["percent"] < 100
    assert after["is_complete"] is False
    assert _by_key(after)["profile_complete"]["earned"] is True
    refreshed = client.get("/api/alumni/achievements", headers=headers).json()
    assert _by_key(refreshed)["profile_complete"]["earned"] is True
    assert refreshed["percent"] < 100


def test_achievement_notifications_once(client, db_session):
    account = _clear_achievements(db_session)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    first = client.post("/api/alumni/gts", headers=headers, json=_gts())
    assert first.status_code == 200
    db_session.expire_all()
    first_count = (
        db_session.query(AlumniNotification)
        .filter(AlumniNotification.account_id == account.id, AlumniNotification.category == "achievement")
        .count()
    )
    assert first_count >= 1
    second = client.post("/api/alumni/gts", headers=headers, json=_gts())
    assert second.status_code == 200
    db_session.expire_all()
    assert (
        db_session.query(AlumniNotification)
        .filter(AlumniNotification.account_id == account.id, AlumniNotification.category == "achievement")
        .count()
        == first_count
    )


def test_unique_constraint_blocks_duplicate_badge(db_session):
    account = _clear_achievements(db_session)
    db_session.add(AlumniBadge(account_id=account.id, badge_key=PROFILE_COMPLETE_KEY))
    db_session.commit()
    db_session.add(AlumniBadge(account_id=account.id, badge_key=PROFILE_COMPLETE_KEY))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_profile_update_survives_achievement_failure(client, db_session, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("achievement failure")

    monkeypatch.setattr(AchievementService, "evaluate_all", boom)
    data = login(client, MARIA, "Alumni@2026")
    headers = auth_header(data["access_token"])
    response = client.put(
        "/api/alumni/profile",
        headers=headers,
        json={"phone": "+63 917 555 0199", "city": "Angeles City", "country_residence": "Philippines"},
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    maria = _account(db_session)
    assert maria.profile.phone == "+63 917 555 0199"
