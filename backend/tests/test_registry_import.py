from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import create_engine, text

from app.db import _relax_university_email
from app.models import RegistryImport, UniversityRecord
from tests.conftest import auth_header, login

HEADERS = ["Student Number", "First Name", "Middle Name", "Last Name", "College", "Course", "Course Code"]
CCS = "College of Computer Studies"
BSIT = "Bachelor of Science in Information Technology"
NURSING = "College of Nursing"
BSN = "Bachelor of Science in Nursing"


def _admin(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(admin["access_token"])


def _workbook(rows, headers=HEADERS, title=None):
    book = Workbook()
    sheet = book.active
    if title:
        sheet.append([title])
        sheet.append([])
    sheet.append(headers)
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _files(data, name="graduates.xlsx"):
    return {"file": (name, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


def _cleanup(db_session, student_ids):
    db_session.rollback()
    db_session.query(RegistryImport).delete()
    if student_ids:
        db_session.query(UniversityRecord).filter(UniversityRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
    db_session.commit()


def test_preview_does_not_insert_and_commit_imports_new_graduates(client, db_session):
    headers = _admin(client)
    data = _workbook(
        [
            ("imp-1001", "Elena", "Cruz", "Ramos", NURSING, BSN, "BSN"),
            ("imp-1002", "Mark", "", "Castro", CCS, BSIT, "BSIT"),
        ],
        title="Angeles University Foundation",
    )
    before = db_session.query(UniversityRecord).count()
    preview = client.post("/api/admin/university-records/import/preview", headers=headers, files=_files(data))
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["summary"] == {"ready": 2, "imported": 0, "skipped": 0, "invalid": 0, "total": 2}
    assert body["rows"][0]["student_number"] == "imp-1001"
    assert [column for column in body["rows"][0]][:7] == [
        "row_number",
        "student_number",
        "first_name",
        "middle_name",
        "last_name",
        "college",
        "course",
    ]
    db_session.expire_all()
    assert db_session.query(UniversityRecord).count() == before

    imported = client.post("/api/admin/university-records/import", headers=headers, files=_files(data, "batch-a.xlsx"))
    assert imported.status_code == 200, imported.text
    summary = imported.json()["summary"]
    assert summary["imported"] == 2
    assert imported.json()["last_import"]["imported_at"]
    db_session.expire_all()
    first = db_session.get(UniversityRecord, "imp-1001")
    second = db_session.get(UniversityRecord, "imp-1002")
    assert first.personal_email is None
    assert first.degree == BSN
    assert first.course_code == "BSN"
    assert first.college == NURSING
    assert second.middle_name == ""
    listed = client.get("/api/admin/university-records", headers=headers, params={"q": "imp-1001"})
    assert listed.json()["last_import"]["filename"] == "batch-a.xlsx"
    assert listed.json()["items"][0]["student_id"] == "imp-1001"
    _cleanup(db_session, ["imp-1001", "imp-1002"])


def test_same_file_and_same_content_are_rejected(client, db_session):
    headers = _admin(client)
    rows = [("imp-2001", "Hannah", "Reyes", "Villanueva", CCS, BSIT, "BSIT")]
    data = _workbook(rows)
    first = client.post("/api/admin/university-records/import", headers=headers, files=_files(data))
    assert first.status_code == 200, first.text
    again = client.post("/api/admin/university-records/import/preview", headers=headers, files=_files(data))
    assert again.status_code == 409
    assert "already been imported" in again.json()["detail"]
    same_content = _workbook(rows)
    duplicate = client.post(
        "/api/admin/university-records/import",
        headers=headers,
        files=_files(same_content, "copy.xlsx"),
    )
    assert duplicate.status_code == 409
    assert "already been imported" in duplicate.json()["detail"]
    db_session.expire_all()
    assert db_session.query(UniversityRecord).filter(UniversityRecord.student_id == "imp-2001").count() == 1
    _cleanup(db_session, ["imp-2001"])


def test_duplicate_student_numbers_and_existing_records_are_not_overwritten(client, db_session):
    headers = _admin(client)
    data = _workbook(
        [
            ("imp-3001", "Paolo", "Diaz", "Navarro", CCS, BSIT, "BSIT"),
            ("imp-3001", "Other", "Name", "Person", NURSING, BSN, "BSN"),
            ("2020-0001", "Not", "Maria", "Reyes", NURSING, BSN, "BSN"),
            ("imp-3002", "", "Cruz", "Sy", NURSING, BSN, "BSN"),
        ]
    )
    result = client.post("/api/admin/university-records/import", headers=headers, files=_files(data))
    assert result.status_code == 200, result.text
    summary = result.json()["summary"]
    assert summary["imported"] == 1
    assert summary["skipped"] == 2
    assert summary["invalid"] == 1
    messages = {row["student_number"]: row["message"] for row in result.json()["issues"]}
    assert "already in the import list" in messages["2020-0001"]
    assert "Duplicate student number" in messages["imp-3001"]
    assert "First name is required" in messages["imp-3002"]
    db_session.expire_all()
    maria = db_session.get(UniversityRecord, "2020-0001")
    assert maria.first_name == "Maria"
    assert maria.college == CCS
    created = db_session.get(UniversityRecord, "imp-3001")
    assert created.first_name == "Paolo"
    assert created.college == CCS
    assert db_session.get(UniversityRecord, "imp-3002") is None
    _cleanup(db_session, ["imp-3001", "imp-3002"])


def test_invalid_workbook_reports_a_clear_error(client):
    headers = _admin(client)
    missing = _workbook(
        [("imp-4001", "Ana", "Lopez", "Garcia", NURSING, BSN)],
        headers=["Student Number", "First Name", "Middle Name", "Last Name", "College", "Course"],
    )
    response = client.post("/api/admin/university-records/import/preview", headers=headers, files=_files(missing))
    assert response.status_code == 400
    assert "Course Code" in response.json()["detail"]
    text = client.post(
        "/api/admin/university-records/import/preview",
        headers=headers,
        files={"file": ("graduates.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert text.status_code == 400
    assert "Excel workbook" in text.json()["detail"]


def test_partial_file_can_be_corrected_in_a_new_workbook(client, db_session):
    headers = _admin(client)
    original = _workbook(
        [
            ("imp-5001", "Sofia", "Ramos", "Lim", CCS, BSIT, "BSIT"),
            ("imp-5002", "Miguel", "", "", NURSING, BSN, "BSN"),
        ]
    )
    first = client.post("/api/admin/university-records/import", headers=headers, files=_files(original))
    assert first.status_code == 200, first.text
    assert first.json()["summary"]["imported"] == 1
    blocked = client.post("/api/admin/university-records/import", headers=headers, files=_files(original))
    assert blocked.status_code == 409
    corrected = _workbook([("imp-5002", "Miguel", "Bautista", "Santos", NURSING, BSN, "BSN")])
    second = client.post("/api/admin/university-records/import", headers=headers, files=_files(corrected, "fixed.xlsx"))
    assert second.status_code == 200, second.text
    assert second.json()["summary"]["imported"] == 1
    db_session.expire_all()
    assert db_session.get(UniversityRecord, "imp-5002").last_name == "Santos"
    _cleanup(db_session, ["imp-5001", "imp-5002"])


def test_manual_course_must_belong_to_college_and_code_is_filled(client, db_session):
    headers = _admin(client)
    mismatched = client.post(
        "/api/admin/university-records",
        headers=headers,
        json={
            "student_id": "imp-6001",
            "first_name": "Liza",
            "middle_name": "Pineda",
            "last_name": "Torres",
            "personal_email": "imp.liza@example.com",
            "degree": BSN,
            "year_graduated": "2020",
            "course_code": "WRONG",
            "college": CCS,
        },
    )
    assert mismatched.status_code == 400
    assert "does not belong" in mismatched.json()["detail"]
    created = client.post(
        "/api/admin/university-records",
        headers=headers,
        json={
            "student_id": "imp-6001",
            "first_name": "Liza",
            "middle_name": "Pineda",
            "last_name": "Torres",
            "personal_email": "imp.liza@example.com",
            "degree": f" {BSN} ",
            "year_graduated": "2020",
            "course_code": "WRONG",
            "college": f" {NURSING} ",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["course_code"] == "BSN"
    assert created.json()["degree"] == BSN
    db_session.expire_all()
    row = db_session.get(UniversityRecord, "imp-6001")
    assert row.course_code == "BSN"
    assert row.college == NURSING
    _cleanup(db_session, ["imp-6001"])


def test_academic_catalog_includes_course_codes(client):
    headers = _admin(client)
    catalog = client.get("/api/admin/academic-filters", headers=headers)
    assert catalog.status_code == 200
    assert any(item["college"] == CCS and item["course"] == BSIT and item["course_code"] == "BSIT" for item in catalog.json()["programs"])


def test_sqlite_registry_email_can_be_empty(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE university_records (
                    student_id VARCHAR(40) NOT NULL PRIMARY KEY,
                    first_name VARCHAR(80) NOT NULL,
                    middle_name VARCHAR(80) NOT NULL,
                    last_name VARCHAR(80) NOT NULL,
                    personal_email VARCHAR(255) NOT NULL,
                    degree VARCHAR(200) NOT NULL,
                    year_graduated VARCHAR(8) NOT NULL,
                    course_code VARCHAR(40) NOT NULL,
                    college VARCHAR(160) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY,
                    linked_student_id VARCHAR(40),
                    FOREIGN KEY(linked_student_id) REFERENCES university_records(student_id)
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO university_records VALUES "
                "('2020-0001', 'Maria', 'Cruz', 'Reyes', 'maria@example.com', :degree, '2022', 'BSIT', :college)"
            ),
            {"degree": BSIT, "college": CCS},
        )
        conn.execute(text("INSERT INTO accounts (id, linked_student_id) VALUES (1, '2020-0001')"))
    _relax_university_email(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO university_records (
                    student_id, first_name, middle_name, last_name, personal_email,
                    degree, year_graduated, course_code, college
                ) VALUES ('imp-1', 'Ana', '', 'Cruz', NULL, :degree, '', 'BSN', :college)
                """
            ),
            {"degree": BSN, "college": NURSING},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM university_records")).scalar()
        linked = conn.execute(text("SELECT linked_student_id FROM accounts WHERE id = 1")).scalar()
    assert count == 2
    assert linked == "2020-0001"
    engine.dispose()


def test_import_requires_an_admin(client):
    data = _workbook([("imp-7001", "Ana", "Lopez", "Garcia", NURSING, BSN, "BSN")])
    response = client.post("/api/admin/university-records/import/preview", files=_files(data))
    assert response.status_code == 401
