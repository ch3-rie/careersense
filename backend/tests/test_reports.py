from datetime import datetime, timedelta, timezone

from app.models import Account, AlumniProfile, FurtherStudy, TracerSubmission, UniversityRecord
from app.security import hash_password
from app.services.reports import build_oaaps_report, classify_further_study, latest_submissions, pct
from tests.conftest import auth_header, login

COLLEGE = "College of OAAPS Report"
PROGRAM = "Bachelor of Science in Report Testing"
YEAR = "2025"


def test_reports_count_latest_per_alumni(client, db_session):
    maria = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    existing = db_session.query(TracerSubmission).filter(TracerSubmission.account_id == maria.id).count()
    db_session.add(
        TracerSubmission(
            account_id=maria.id,
            student_id=maria.linked_student_id,
            data_json={
                "is_currently_employed": "Yes",
                "present_related_degree": "Yes",
                "pres_occ": "Software Engineer",
            },
            extra_answers={},
            alignment_status="Aligned",
            alignment_score=100,
        )
    )
    db_session.commit()
    latest = latest_submissions(db_session)
    maria_rows = [row for row in latest if row.account_id == maria.id]
    assert len(maria_rows) == 1
    assert existing >= 1

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    reports = client.get("/api/admin/reports", headers=auth_header(admin["access_token"]))
    assert reports.status_code == 200
    body = reports.json()
    assert body["alumni_with_submissions"] == len(latest)
    assert body["total_submissions"] >= body["alumni_with_submissions"]
    assert body["currently_employed_submissions"] <= body["alumni_with_submissions"]


def test_pct_guards_zero_denominator():
    assert pct(5, 0) == 0.0
    assert pct(1, 2) == 50.0
    assert pct(1, 3) == 33.33


def test_classify_further_study_labels():
    assert classify_further_study("Master in Business Administration", False) == "pursuing_masters"
    assert classify_further_study("PhD in Education", True) == "completed_doctorate"
    assert classify_further_study("Postgraduate Diploma in Data Science", False) == "postgrad_cert"
    assert classify_further_study("Bachelor of Laws", False) == "second_degree"
    assert classify_further_study("Short course", False) == "other"


def _record(db, student_id, email, first, last, year=YEAR):
    row = UniversityRecord(
        student_id=student_id,
        first_name=first,
        last_name=last,
        personal_email=email,
        degree=PROGRAM,
        year_graduated=year,
        course_code="BSRT",
        college=COLLEGE,
    )
    db.add(row)
    db.flush()
    return row


def _alumni(db, record, email, payload, extra_studies=None, submitted_at=None, alignment="Aligned"):
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
            alignment_status=alignment,
            alignment_score=100 if alignment == "Aligned" else 0,
            submitted_at=submitted_at,
        )
    )
    for item in extra_studies or []:
        db.add(FurtherStudy(account_id=account.id, **item))
    db.flush()
    return account


def _oaaps_fixture(db_session):
    employed_studies = _record(db_session, "OAAPS-0001", "oaaps.one@example.com", "One", "Productive")
    _alumni(
        db_session,
        employed_studies,
        "oaaps.one@example.com",
        {
            "first_name": "One",
            "last_name": "Productive",
            "degree": PROGRAM,
            "year_graduated": YEAR,
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_related": "Yes",
            "first_stat": "Regular/Permanent",
            "time_to_first_job": "Less than a month",
            "enroll_further_studies": "Yes",
            "further_studies": [
                {
                    "course_degree": "Master of Science in Data Analytics",
                    "school": "AUF",
                    "year_enrolled": "2026",
                    "scholarship": "CHED Scholar",
                    "is_graduated": "No",
                },
                {
                    "course_degree": "Certificate in Project Management",
                    "school": "AUF",
                    "year_enrolled": "2025",
                    "scholarship": "",
                    "is_graduated": "No",
                },
            ],
        },
        extra_studies=[
            {
                "course_degree": "Master of Science in Data Analytics",
                "school": "AUF",
                "year_enrolled": "2026",
                "scholarship": "CHED Scholar",
                "is_graduated": False,
            },
            {
                "course_degree": "Certificate in Project Management",
                "school": "AUF",
                "year_enrolled": "2025",
                "scholarship": "",
                "is_graduated": False,
            },
        ],
    )
    seeking = _record(db_session, "OAAPS-0002", "oaaps.two@example.com", "Two", "Seeking")
    _alumni(
        db_session,
        seeking,
        "oaaps.two@example.com",
        {
            "first_name": "Two",
            "last_name": "Seeking",
            "degree": PROGRAM,
            "year_graduated": YEAR,
            "is_currently_employed": "No",
            "reason_current": ["Looking for a job, but cannot find one"],
            "enroll_further_studies": "No",
        },
        alignment="Unknown",
    )
    self_employed = _record(db_session, "OAAPS-0003", "oaaps.three@example.com", "Three", "Owner")
    _alumni(
        db_session,
        self_employed,
        "oaaps.three@example.com",
        {
            "first_name": "Three",
            "last_name": "Owner",
            "degree": PROGRAM,
            "year_graduated": YEAR,
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_stat": "Self-Employed",
            "first_related": "No",
            "time_to_first_job": "7 to 11 months",
            "enroll_further_studies": "No",
        },
        alignment="Misaligned",
    )
    _record(db_session, "OAAPS-0004", "oaaps.four@example.com", "Four", "Untraced")
    db_session.commit()


def test_oaaps_report_formulas_and_no_double_count(client, db_session):
    _oaaps_fixture(db_session)
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    response = client.get(
        "/api/admin/reports/oaaps",
        params={"college": COLLEGE, "program": PROGRAM, "year": YEAR},
        headers=auth_header(admin["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "OVERALL GRADUATE PRODUCTIVITY REPORT"
    assert body["header"]["total_graduates"] == 4
    assert body["header"]["graduates_traced"] == 3
    assert body["profile"]["productive"] == 2
    assert body["profile"]["not_yet_engaged"] == 1
    assert body["overall_productivity_rate"] == 66.67
    assert body["workforce"]["key_rate"] == 66.67
    assert body["professional"]["key_rate"] == 33.33
    assert body["academic"]["key_rate"] == 33.33
    assert body["distribution"]["workforce"] == 66.67

    by_indicator = {row["indicator"]: row for row in body["executive_summary"]}
    assert by_indicator["Graduates with Multiple Productivity Indicators"]["count"] == 2
    assert by_indicator["Employed Graduates"]["count"] == 2
    assert by_indicator["Graduates Pursuing Further Studies"]["count"] == 1
    assert by_indicator["Graduates with Professional Advancement"]["count"] == 1

    status = {row["indicator"]: row for row in body["workforce"]["employment_status"]}
    assert status["Employed"]["count"] == 1
    assert status["Self-Employed / Entrepreneur"]["count"] == 1
    assert status["Freelance / Project-Based"]["available"] is False
    assert status["Unemployed – Seeking Employment"]["count"] == 1
    assert status["Total Traced"]["count"] == 3

    relevance = {row["indicator"]: row for row in body["workforce"]["employment_relevance"]}
    assert relevance["Employed in a field related to degree"]["count"] == 1
    assert relevance["Employed in a different field"]["count"] == 1
    assert relevance["Employed locally"]["available"] is False

    quality = {row["indicator"]: row for row in body["workforce"]["employment_quality"]}
    assert quality["Permanent/Regular"]["count"] == 1
    assert quality["Full-Time Employment"]["available"] is False

    time_rows = {row["indicator"]: row for row in body["workforce"]["time_to_employment"]}
    assert time_rows["Employed before graduation"]["available"] is False
    assert time_rows["Employed within 3 months"]["count"] == 1
    assert time_rows["Employed within 12 months"]["count"] == 1

    education = {row["indicator"]: row for row in body["academic"]["further_education"]}
    assert education["Pursuing Master’s Degree"]["count"] == 1
    assert education["Pursuing Postgraduate Certificate/Diploma"]["count"] == 1

    achievements = {row["indicator"]: row for row in body["academic"]["achievements"]}
    assert achievements["Received Scholarship/Fellowship"]["count"] == 1
    assert achievements["Published Research"]["available"] is False

    assert body["professional"]["achievements_available"] is False
    assert all(row["target"] is None and row["status"] is None for row in body["scorecard"])
    assert body["by_program"][-1]["college_program"] == "TOTAL"
    assert body["by_program"][-1]["graduates"] == 4
    assert body["by_program"][-1]["traced"] == 3


def test_oaaps_latest_submission_and_period_filter(client, db_session):
    college = "College of OAAPS Latest Filter"
    record = UniversityRecord(
        student_id="OAAPS-0100",
        first_name="Late",
        last_name="Update",
        personal_email="oaaps.latest@example.com",
        degree=PROGRAM,
        year_graduated="2024",
        course_code="BSRT",
        college=college,
    )
    db_session.add(record)
    db_session.flush()
    account = _alumni(
        db_session,
        record,
        "oaaps.latest@example.com",
        {
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_stat": "Regular/Permanent",
            "enroll_further_studies": "No",
        },
        submitted_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(
        TracerSubmission(
            account_id=account.id,
            student_id=record.student_id,
            data_json={
                "is_currently_employed": "No",
                "reason_current": ["Continuing Education"],
                "enroll_further_studies": "No",
            },
            extra_answers={},
            alignment_status="Unknown",
            alignment_score=50,
        )
    )
    db_session.commit()

    report = build_oaaps_report(db_session, college=college, program=PROGRAM, year="2024")
    assert report["header"]["graduates_traced"] == 1
    status = {row["indicator"]: row for row in report["workforce"]["employment_status"]}
    assert status["Employed"]["count"] == 0
    assert status["Not Seeking Employment"]["count"] == 1

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    empty_period = client.get(
        "/api/admin/reports/oaaps",
        params={
            "college": college,
            "year": "2024",
            "period_from": "2010-01-01",
            "period_to": "2010-12-31",
        },
        headers=auth_header(admin["access_token"]),
    )
    assert empty_period.status_code == 200
    empty = empty_period.json()
    assert empty["header"]["graduates_traced"] == 0
    assert empty["overall_productivity_rate"] == 0.0
    assert empty["header"]["total_graduates"] == 1


def test_oaaps_empty_cohort_and_invalid_dates(client, db_session):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    empty = client.get("/api/admin/reports/oaaps", params={"year": "1999"}, headers=headers)
    assert empty.status_code == 200
    body = empty.json()
    assert body["header"]["total_graduates"] == 0
    assert body["header"]["graduates_traced"] == 0
    assert body["overall_productivity_rate"] == 0.0
    assert body["workforce"]["employment_status"][-1]["percentage"] == 0.0

    bad = client.get("/api/admin/reports/oaaps", params={"period_from": "13-13-2024"}, headers=headers)
    assert bad.status_code == 400
    inverted = client.get(
        "/api/admin/reports/oaaps",
        params={"period_from": "2026-12-31", "period_to": "2026-01-01"},
        headers=headers,
    )
    assert inverted.status_code == 400


def test_oaaps_word_export_and_csv_still_work(client, db_session):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    word = client.get("/api/admin/reports/oaaps/export", headers=headers)
    assert word.status_code == 200
    assert "wordprocessingml" in word.headers["content-type"]
    assert word.content[:2] == b"PK"
    csv_export = client.get("/api/admin/reports/export", headers=headers)
    assert csv_export.status_code == 200
    assert csv_export.headers["content-type"].startswith("text/csv")
    assert csv_export.text.splitlines()[0].startswith("email")


def test_alumni_cannot_access_oaaps_report(client):
    alumni = login(client, "liza.torres@gmail.com", "Alumni@2026")
    response = client.get("/api/admin/reports/oaaps", headers=auth_header(alumni["access_token"]))
    assert response.status_code == 403
    assert client.get("/api/admin/reports/oaaps").status_code == 401
