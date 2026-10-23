from io import BytesIO

from openpyxl import Workbook

from app.models import AcademicProgram, College, UniversityRecord
from tests.conftest import auth_header, login

CCS = "College of Computer Studies"
BSIT = "Bachelor of Science in Information Technology"
NURSING = "College of Nursing"
BSN = "Bachelor of Science in Nursing"
PROBE = "College of Catalog Studies"
PROBE_CODE = "CCTS"
COURSE = "Bachelor of Catalog Studies"
COURSE_CODE = "BCAT"


def _admin(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(admin["access_token"])


def _workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.append(["Student Number", "First Name", "Middle Name", "Last Name", "College", "Course", "Course Code"])
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _cleanup(db_session, college_names, student_ids):
    db_session.rollback()
    if student_ids:
        db_session.query(UniversityRecord).filter(UniversityRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
    if college_names:
        colleges = db_session.query(College).filter(College.name.in_(college_names)).all()
        ids = [row.id for row in colleges]
        if ids:
            db_session.query(AcademicProgram).filter(AcademicProgram.college_id.in_(ids)).delete(synchronize_session=False)
            db_session.query(College).filter(College.id.in_(ids)).delete(synchronize_session=False)
    db_session.commit()


def test_academics_requires_admin(client):
    assert client.get("/api/admin/academics").status_code == 401


def test_seeded_catalog_is_the_shared_source(client):
    headers = _admin(client)
    catalog = client.get("/api/admin/academic-filters", headers=headers)
    assert catalog.status_code == 200
    body = catalog.json()
    assert CCS in body["colleges"]
    assert any(item["college"] == CCS and item["course"] == BSIT and item["course_code"] == "BSIT" for item in body["programs"])
    listed = client.get("/api/admin/academics", headers=headers)
    assert listed.status_code == 200
    colleges = {row["name"]: row for row in listed.json()["colleges"]}
    assert CCS in colleges
    courses = listed.json()["courses"]
    assert any(row["name"] == BSIT and row["course_code"] == "BSIT" and row["college"] == CCS for row in courses)


def test_catalog_validation_confirmation_and_protected_delete(client, db_session):
    headers = _admin(client)
    college_names = [PROBE, "College of Catalog Studies Renamed"]
    try:
        created = client.post(
            "/api/admin/academics/colleges",
            headers=headers,
            json={"name": f"  {PROBE}  ", "code": PROBE_CODE},
        )
        assert created.status_code == 200, created.text
        college_id = created.json()["id"]
        assert created.json()["name"] == PROBE
        assert created.json()["graduate_count"] == 0

        duplicate = client.post(
            "/api/admin/academics/colleges",
            headers=headers,
            json={"name": PROBE.lower(), "code": "OTHER"},
        )
        assert duplicate.status_code == 400
        assert "already exists" in duplicate.json()["detail"]

        empty = client.post("/api/admin/academics/colleges", headers=headers, json={"name": " ", "code": ""})
        assert empty.status_code == 400
        assert empty.json()["detail"] == "Enter a college name."

        course = client.post(
            "/api/admin/academics/courses",
            headers=headers,
            json={"college_id": college_id, "name": COURSE, "course_code": COURSE_CODE},
        )
        assert course.status_code == 200, course.text
        course_id = course.json()["id"]

        taken_code = client.post(
            "/api/admin/academics/courses",
            headers=headers,
            json={"college_id": college_id, "name": "Another Catalog Course", "course_code": "bsit"},
        )
        assert taken_code.status_code == 400
        assert "BSIT" in taken_code.json()["detail"] or "bsit" in taken_code.json()["detail"].lower()

        duplicate_course = client.post(
            "/api/admin/academics/courses",
            headers=headers,
            json={"college_id": college_id, "name": COURSE.lower(), "course_code": "BCAT2"},
        )
        assert duplicate_course.status_code == 400
        assert "already exists" in duplicate_course.json()["detail"]

        filters = client.get("/api/admin/academic-filters", headers=headers)
        assert PROBE in filters.json()["colleges"]
        assert any(item["college"] == PROBE and item["course"] == COURSE and item["course_code"] == COURSE_CODE for item in filters.json()["programs"])
        nursing = [item["course"] for item in filters.json()["programs"] if item["college"] == NURSING]
        assert COURSE not in nursing

        report = client.get("/api/admin/reports", headers=headers)
        assert report.status_code == 200
        assert PROBE in report.json()["options"]["colleges"]
        assert any(item["college"] == PROBE and item["program"] == COURSE for item in report.json()["options"]["pairs"])

        graduate = client.post(
            "/api/admin/university-records",
            headers=headers,
            json={
                "student_id": "cat-9001",
                "first_name": "Catalog",
                "middle_name": "Probe",
                "last_name": "Graduate",
                "personal_email": "catalog.probe@example.com",
                "degree": COURSE,
                "year_graduated": "2024",
                "course_code": "WRONG",
                "college": PROBE,
            },
        )
        assert graduate.status_code == 200, graduate.text
        assert graduate.json()["course_code"] == COURSE_CODE
        assert graduate.json()["degree"] == COURSE

        code_only = client.patch(
            f"/api/admin/academics/colleges/{college_id}",
            headers=headers,
            json={"name": PROBE, "code": "CCTS-2"},
        )
        assert code_only.status_code == 200, code_only.text
        db_session.expire_all()
        record = db_session.get(UniversityRecord, "cat-9001")
        assert record.college == PROBE
        assert record.first_name == "Catalog"

        blocked = client.patch(
            f"/api/admin/academics/colleges/{college_id}",
            headers=headers,
            json={"name": "College of Catalog Studies Renamed", "code": "CCTS-2"},
        )
        assert blocked.status_code == 409
        detail = blocked.json()["detail"]
        assert detail["requires_confirmation"] is True
        assert detail["graduate_count"] == 1
        db_session.expire_all()
        record = db_session.get(UniversityRecord, "cat-9001")
        assert record.college == PROBE
        assert record.personal_email == "catalog.probe@example.com"

        renamed = client.patch(
            f"/api/admin/academics/colleges/{college_id}",
            headers=headers,
            json={"name": "College of Catalog Studies Renamed", "code": "CCTS-2", "confirm": True},
        )
        assert renamed.status_code == 200, renamed.text
        db_session.expire_all()
        record = db_session.get(UniversityRecord, "cat-9001")
        assert record.college == "College of Catalog Studies Renamed"
        assert record.first_name == "Catalog"
        assert record.year_graduated == "2024"
        assert db_session.get(UniversityRecord, "2020-0001").college == CCS

        course_blocked = client.patch(
            f"/api/admin/academics/courses/{course_id}",
            headers=headers,
            json={"college_id": college_id, "name": COURSE, "course_code": "BCATX"},
        )
        assert course_blocked.status_code == 409
        db_session.expire_all()
        assert db_session.get(UniversityRecord, "cat-9001").course_code == COURSE_CODE

        course_saved = client.patch(
            f"/api/admin/academics/courses/{course_id}",
            headers=headers,
            json={"college_id": college_id, "name": COURSE, "course_code": "BCATX", "confirm": True},
        )
        assert course_saved.status_code == 200, course_saved.text
        db_session.expire_all()
        record = db_session.get(UniversityRecord, "cat-9001")
        assert record.course_code == "BCATX"
        assert record.degree == COURSE
        assert record.last_name == "Graduate"
        refreshed = client.get("/api/admin/academic-filters", headers=headers)
        assert any(
            item["college"] == "College of Catalog Studies Renamed" and item["course"] == COURSE and item["course_code"] == "BCATX"
            for item in refreshed.json()["programs"]
        )

        protected = client.delete(f"/api/admin/academics/courses/{course_id}", headers=headers)
        assert protected.status_code == 409
        assert "not deleted" in protected.json()["detail"]["message"]
        db_session.expire_all()
        assert db_session.get(UniversityRecord, "cat-9001") is not None

        college_protected = client.delete(f"/api/admin/academics/colleges/{college_id}", headers=headers)
        assert college_protected.status_code == 409
        assert "courses" in college_protected.json()["detail"]["message"]
    finally:
        _cleanup(db_session, college_names, ["cat-9001"])


def test_import_uses_catalog_and_adds_new_programs(client, db_session):
    headers = _admin(client)
    imported_college = "College of Imported Studies"
    imported_course = "Bachelor of Imported Studies"
    try:
        preview = client.post(
            "/api/admin/university-records/import/preview",
            headers=headers,
            files={
                "file": (
                    "catalog-preview.xlsx",
                    _workbook([("cat-9101", "Inez", "", "Santos", NURSING, BSN, "WRONG")]),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert preview.status_code == 200, preview.text
        row = preview.json()["rows"][0]
        assert row["status"] == "ready"
        assert row["college"] == NURSING
        assert row["course"] == BSN
        assert row["course_code"] == "BSN"

        mismatch = client.post(
            "/api/admin/university-records/import/preview",
            headers=headers,
            files={
                "file": (
                    "catalog-mismatch.xlsx",
                    _workbook([("cat-9102", "Inez", "", "Santos", CCS, BSN, "BSN")]),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert mismatch.status_code == 200, mismatch.text
        assert mismatch.json()["rows"][0]["status"] == "invalid"
        assert "does not belong" in mismatch.json()["rows"][0]["message"]

        imported = client.post(
            "/api/admin/university-records/import",
            headers=headers,
            files={
                "file": (
                    "catalog-import.xlsx",
                    _workbook([
                        ("cat-9103", "Omar", "Dela", "Cruz", imported_college, imported_course, "BIMP"),
                    ]),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert imported.status_code == 200, imported.text
        listed = client.get("/api/admin/academics", headers=headers)
        assert any(
            row["name"] == imported_course and row["course_code"] == "BIMP" and row["college"] == imported_college
            for row in listed.json()["courses"]
        )
        filters = client.get("/api/admin/academic-filters", headers=headers)
        assert imported_college in filters.json()["colleges"]
        assert any(
            item["college"] == imported_college and item["course"] == imported_course and item["course_code"] == "BIMP"
            for item in filters.json()["programs"]
        )
    finally:
        _cleanup(db_session, [imported_college], ["cat-9103"])
        db_session.rollback()
        from app.models import RegistryImport

        db_session.query(RegistryImport).filter(RegistryImport.filename == "catalog-import.xlsx").delete(synchronize_session=False)
        db_session.commit()
