"""The AUF reference updates the existing catalog without inventing course codes."""

from app.models import AcademicProgram, College, UniversityRecord
from app.services.academic_reference import apply_auf_reference
from tests.conftest import auth_header, login

CAMP = "College of Allied Medical Professions"
CBA = "College of Business and Accountancy"
CCS = "College of Computer Studies"
CEA = "College of Engineering and Architecture"
BSIT = "Bachelor of Science in Information Technology"
BSBA = "Bachelor of Science in Business Administration"
BSCE = "Bachelor of Science in Civil Engineering"
HISTORICAL = "Bachelor of Historical Studies"


def _admin(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(admin["access_token"])


def _courses(client, headers):
    listed = client.get("/api/admin/academics", headers=headers)
    assert listed.status_code == 200, listed.text
    return listed.json()


def test_reference_keeps_verified_codes_and_adds_unverified_programs(client, db_session):
    headers = _admin(client)
    body = _courses(client, headers)
    colleges = {row["name"]: row for row in body["colleges"]}
    courses = body["courses"]

    assert colleges[CAMP]["code"] == "CAMP"
    assert colleges[CCS]["code"] == "CCS"
    assert colleges["College of Business and Accountancy"]["code"] == "CBA"
    assert colleges["College of Education"]["code"] == "CED"
    assert colleges["College of Nursing"]["code"] == "CON"
    assert colleges[CEA]["code"] == "CEA"
    assert colleges["School of Law"]["code"] == ""
    assert "College of Engineering" not in colleges

    pharmacy = next(row for row in courses if row["name"] == "BS Pharmacy" and row["college"] == CAMP)
    assert pharmacy["course_code"] == ""
    assert pharmacy["review_status"] == "needs_review"
    assert pharmacy["kind"] == "undergraduate"
    assert pharmacy["parent_id"] is None

    information_technology = [
        row for row in courses
        if row["college"] == CCS and "Information Technology" in row["name"] and row["kind"] == "undergraduate"
    ]
    assert len(information_technology) == 1
    assert information_technology[0]["name"] == BSIT
    assert information_technology[0]["course_code"] == "BSIT"
    assert information_technology[0]["review_status"] == "on_record"

    assert not any(row["name"] in {"BS Marketing", "Marketing Management"} for row in courses)
    marketing = next(row for row in courses if row["college"] == CBA and row["name"].endswith("Marketing Management"))
    assert marketing["kind"] == "specialization"
    assert marketing["parent_name"] == BSBA
    assert marketing["course_code"] == ""
    assert "—" in marketing["name"]

    clinical = next(row for row in courses if row["name"] == "BS Clinical Pharmacy")
    assert clinical["kind"] == "undergraduate"
    assert clinical["parent_id"] is None

    law = next(row for row in courses if row["name"] == "Juris Doctor")
    assert law["college"] == "School of Law"
    assert law["kind"] == "professional"
    assert law["course_code"] == ""

    public_health = next(row for row in courses if row["name"] == "Doctor of Public Health")
    assert public_health["college"] == "Graduate School"
    assert public_health["review_status"] == "needs_review"

    lab = next(row for row in courses if row["name"] == "Master of Science in Medical Laboratory Science")
    assert lab["college"] == CAMP

    clinical_psych = next(
        row for row in courses
        if row["college"] == "College of Arts and Sciences" and row["name"].endswith("Clinical Psychology")
    )
    assert clinical_psych["kind"] == "major"
    assert clinical_psych["parent_name"] == "Master of Arts in Psychology"

    db_session.expire_all()
    paolo = db_session.get(UniversityRecord, "2022-0112")
    assert paolo.college == CEA
    assert paolo.degree == BSCE
    assert paolo.course_code == "BSCE"

    pharmacy_row = db_session.get(AcademicProgram, pharmacy["id"])
    pharmacy_row.course_code = "KEPT-CODE"
    pharmacy_row.review_status = "on_record"
    db_session.commit()
    assert apply_auf_reference(db_session) in {True, False}
    db_session.commit()
    db_session.refresh(pharmacy_row)
    assert pharmacy_row.course_code == "KEPT-CODE"
    assert pharmacy_row.review_status == "on_record"
    assert pharmacy_row.name == "BS Pharmacy"
    pharmacy_row.course_code = ""
    pharmacy_row.review_status = "needs_review"
    db_session.commit()


def test_reference_does_not_remove_unlisted_programs_or_reject_blank_codes(client, db_session):
    headers = _admin(client)
    body = _courses(client, headers)
    cba = next(row for row in body["colleges"] if row["name"] == CBA)
    created = client.post(
        "/api/admin/academics/courses",
        headers=headers,
        json={"college_id": cba["id"], "name": HISTORICAL, "course_code": "", "kind": "undergraduate"},
    )
    assert created.status_code == 200, created.text
    historical_id = created.json()["id"]
    probe = client.post(
        "/api/admin/academics/colleges",
        headers=headers,
        json={"name": "College of Blank Course Codes", "code": ""},
    )
    assert probe.status_code == 200, probe.text
    probe_id = probe.json()["id"]
    try:
        first = client.post(
            "/api/admin/academics/courses",
            headers=headers,
            json={"college_id": probe_id, "name": "Blank Code One", "course_code": "", "kind": "undergraduate"},
        )
        second = client.post(
            "/api/admin/academics/courses",
            headers=headers,
            json={"college_id": probe_id, "name": "Blank Code Two", "course_code": "", "kind": "certificate"},
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["course_code"] == ""
        assert second.json()["course_code"] == ""
        assert second.json()["review_status"] == "needs_review"

        again = _courses(client, headers)
        names = {row["name"] for row in again["courses"]}
        assert HISTORICAL in names
        assert "Blank Code One" in names
        assert "BS Pharmacy" in names
        db_session.expire_all()
        paolo = db_session.get(UniversityRecord, "2022-0112")
        assert paolo.degree == BSCE
        assert paolo.course_code == "BSCE"
    finally:
        client.delete(f"/api/admin/academics/courses/{historical_id}", headers=headers)
        for row in _courses(client, headers)["courses"]:
            if row["college_id"] == probe_id:
                client.delete(f"/api/admin/academics/courses/{row['id']}", headers=headers)
        removed = client.delete(f"/api/admin/academics/colleges/{probe_id}", headers=headers)
        assert removed.status_code == 200, removed.text
        db_session.rollback()
