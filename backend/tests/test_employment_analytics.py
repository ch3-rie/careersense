from datetime import datetime, timedelta, timezone

from app.models import Account, AlumniProfile, TracerSubmission, UniversityRecord
from app.security import hash_password
from app.services.reports import employment_analytics
from tests.conftest import auth_header, login

COLLEGE = "College of Employment Analytics"
OTHER_COLLEGE = "College of Employment Analytics Other"
COURSE = "Bachelor of Science in Employment Analytics"
OTHER_COURSE = "Bachelor of Science in Employment Analytics Other"
YEAR = "2031"
OTHER_YEAR = "2032"
SECRET = "Confidential family detail that must not appear"


def _record(db, student_id, email, degree=COURSE, year=YEAR, college=COLLEGE):
    row = UniversityRecord(
        student_id=student_id,
        first_name="Emp",
        last_name=student_id,
        personal_email=email,
        degree=degree,
        year_graduated=year,
        course_code="BSEA",
        college=college,
    )
    db.add(row)
    db.flush()
    return row


def _submit(db, record, email, payload, submitted_at=None):
    account = Account(
        personal_email=email,
        password_hash=hash_password("Alumni@2026"),
        linked_student_id=record.student_id,
        role="Alumni",
        status="Active",
        is_verified=True,
        privacy_consent=True,
    )
    db.add(account)
    db.flush()
    db.add(
        AlumniProfile(
            account_id=account.id,
            first_name=record.first_name,
            last_name=record.last_name,
            degree=record.degree,
            year_graduated=record.year_graduated,
        )
    )
    db.add(
        TracerSubmission(
            account_id=account.id,
            student_id=record.student_id,
            data_json=payload,
            extra_answers={},
            alignment_status="Aligned",
            alignment_score=100,
            submitted_at=submitted_at or datetime.now(timezone.utc),
        )
    )
    db.flush()
    return account


def _seed(db):
    employed = _record(db, "EMP-0001", "emp.one@example.com")
    _submit(db, employed, "emp.one@example.com", {"is_currently_employed": "Yes", "first_occ": "Analyst"})

    unemployed = _record(db, "EMP-0002", "emp.two@example.com")
    _submit(
        db,
        unemployed,
        "emp.two@example.com",
        {
            "is_currently_employed": "No",
            "first_occ": "Chief Executive Officer",
            "reason_current": ["Looking for a job, but cannot find one", "Other", "Other"],
            "reason_current_other": SECRET,
        },
    )

    missing_reason = _record(db, "EMP-0003", "emp.three@example.com")
    _submit(db, missing_reason, "emp.three@example.com", {"is_currently_employed": "No", "reason_current": []})

    unknown = _record(db, "EMP-0004", "emp.four@example.com")
    _submit(
        db,
        unknown,
        "emp.four@example.com",
        {"is_currently_employed": "", "reason_current": ["Health-related reason/s"]},
    )

    other_course = _record(db, "EMP-0005", "emp.five@example.com", degree=OTHER_COURSE)
    _submit(db, other_course, "emp.five@example.com", {"is_currently_employed": "Yes"})

    other_college = _record(
        db,
        "EMP-0006",
        "emp.six@example.com",
        college=OTHER_COLLEGE,
        year=OTHER_YEAR,
    )
    _submit(
        db,
        other_college,
        "emp.six@example.com",
        {"is_currently_employed": "No", "reason_current": ["Health-related reason/s"]},
    )

    replaced = _record(db, "EMP-0007", "emp.seven@example.com")
    account = _submit(
        db,
        replaced,
        "emp.seven@example.com",
        {"is_currently_employed": "No", "reason_current": ["Continuing Education"]},
        submitted_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db.add(
        TracerSubmission(
            account_id=account.id,
            student_id=replaced.student_id,
            data_json={"is_currently_employed": "Yes"},
            extra_answers={},
            alignment_status="Aligned",
            alignment_score=100,
            submitted_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def test_employment_analytics_counts_official_gts_only(client, db_session):
    _seed(db_session)
    before = db_session.query(TracerSubmission).count()
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    response = client.get(
        "/api/admin/reports/employment",
        headers=headers,
        params={"college": COLLEGE, "course": COURSE, "year": YEAR},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["employed"] == 2
    assert body["unemployed"] == 2
    assert body["unknown"] == 1
    assert body["total"] == 5
    assert body["employment_rate"] == 50.0
    assert SECRET not in response.text
    reasons = {item["label"]: item["count"] for item in body["reasons"]}
    assert reasons["Looking for a job, but cannot find one"] == 1
    assert reasons["Other"] == 1
    assert reasons["Not reported"] == 1
    assert "Health-related reason/s" not in reasons
    assert "Continuing Education" not in reasons
    assert "Chief Executive Officer" not in response.text
    assert db_session.query(TracerSubmission).count() == before

    both = client.get(
        "/api/admin/reports/employment",
        headers=headers,
        params={"college": COLLEGE, "course": COURSE},
    )
    assert both.json()["total"] == body["total"]

    course_only = client.get(
        "/api/admin/reports/employment",
        headers=headers,
        params={"course": OTHER_COURSE},
    )
    assert course_only.json()["employed"] == 1
    assert course_only.json()["unemployed"] == 0
    assert course_only.json()["reasons"] == []

    year_only = client.get(
        "/api/admin/reports/employment",
        headers=headers,
        params={"year": OTHER_YEAR, "college": OTHER_COLLEGE},
    )
    year_body = year_only.json()
    assert year_body["unemployed"] == 1
    assert year_body["reasons"] == [{"label": "Health-related reason/s", "count": 1}]

    empty = client.get(
        "/api/admin/reports/employment",
        headers=headers,
        params={"college": "No Such Employment College"},
    )
    assert empty.json()["total"] == 0
    assert empty.json()["status"] == []
    assert empty.json()["reasons"] == []
    assert empty.json()["employment_rate"] == 0.0

    overall = employment_analytics(db_session)
    filtered = employment_analytics(db_session, college=COLLEGE, program=COURSE, year=YEAR)
    assert overall["total"] > filtered["total"]
    assert filtered["employed"] == 2


def test_alumni_cannot_read_employment_analytics(client):
    alumni = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.get("/api/admin/reports/employment", headers=auth_header(alumni["access_token"]))
    assert response.status_code == 403
