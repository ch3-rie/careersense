from tests.conftest import auth_header, login

CCS = "College of Computer Studies"
BSIT = "Bachelor of Science in Information Technology"
NURSING = "College of Nursing"
BSN = "Bachelor of Science in Nursing"


def _admin(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(admin["access_token"])


def test_academic_catalog_comes_from_registry(client):
    headers = _admin(client)
    catalog = client.get("/api/admin/academic-filters", headers=headers)
    assert catalog.status_code == 200
    body = catalog.json()
    assert CCS in body["colleges"]
    assert BSIT in body["courses"]
    assert {"college": CCS, "course": BSIT} in body["pairs"]
    assert {"college": NURSING, "course": BSN} in body["pairs"]
    assert {"college": NURSING, "course": BSIT} not in body["pairs"]


def test_registry_college_and_course_filters(client):
    headers = _admin(client)
    college = client.get("/api/admin/university-records", headers=headers, params={"college": CCS, "page_size": 25})
    assert college.status_code == 200
    rows = college.json()["items"]
    assert rows
    assert all(row["college"] == CCS for row in rows)
    assert college.json()["page"] == 1

    course = client.get("/api/admin/university-records", headers=headers, params={"course": BSIT, "page_size": 25})
    assert all(row["degree"] == BSIT for row in course.json()["items"])

    both = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"college": CCS, "course": BSIT, "page_size": 25},
    )
    assert both.json()["items"]
    assert all(row["college"] == CCS and row["degree"] == BSIT for row in both.json()["items"])

    named = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"q": "Reyes", "college": CCS, "course": BSIT},
    )
    assert any(row["personal_email"] == "maria.reyes@gmail.com" for row in named.json()["items"])

    mismatch = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"q": "Reyes", "college": NURSING},
    )
    assert mismatch.json()["total"] == 0

    cleared = client.get("/api/admin/university-records", headers=headers, params={"page_size": 25})
    assert cleared.json()["total"] >= both.json()["total"]


def test_registry_filter_trims_course_and_resets_page_count(client, db_session):
    from app.models import UniversityRecord

    headers = _admin(client)
    created = client.post(
        "/api/admin/university-records",
        headers=headers,
        json={
            "student_id": "2099-0101",
            "first_name": "Filter",
            "middle_name": "",
            "last_name": "Probe",
            "personal_email": "filter.probe@example.com",
            "degree": f" {BSN} ",
            "year_graduated": "2021",
            "course_code": "BSN",
            "college": f" {NURSING} ",
        },
    )
    assert created.status_code == 200
    try:
        matched = client.get(
            "/api/admin/university-records",
            headers=headers,
            params={"college": NURSING, "course": BSN, "page_size": 25, "page": 1},
        )
        assert any(row["student_id"] == "2099-0101" for row in matched.json()["items"])
        narrow = client.get(
            "/api/admin/university-records",
            headers=headers,
            params={"college": "No Such College", "page": 5, "page_size": 25},
        )
        assert narrow.json()["total"] == 0
        assert narrow.json()["items"] == []
        assert narrow.json()["page"] == 5
    finally:
        row = db_session.get(UniversityRecord, "2099-0101")
        if row:
            db_session.delete(row)
            db_session.commit()
    headers = _admin(client)
    created = client.post(
        "/api/admin/university-records",
        headers=headers,
        json={
            "student_id": "2099-0101",
            "first_name": "Filter",
            "middle_name": "",
            "last_name": "Probe",
            "personal_email": "filter.probe@example.com",
            "degree": f" {BSN} ",
            "year_graduated": "2021",
            "course_code": "BSN",
            "college": f" {NURSING} ",
        },
    )
    assert created.status_code == 200
    matched = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"college": NURSING, "course": BSN, "page_size": 5, "page": 1},
    )
    assert any(row["student_id"] == "2099-0101" for row in matched.json()["items"])
    narrow = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"college": "No Such College", "page": 5, "page_size": 25},
    )
    assert narrow.json()["total"] == 0
    assert narrow.json()["items"] == []
    assert narrow.json()["page"] == 5


def test_tracer_college_course_and_alignment_filters(client):
    headers = _admin(client)
    college = client.get("/api/admin/tracer", headers=headers, params={"college": CCS, "page_size": 20})
    assert college.status_code == 200
    emails = {row["email"] for row in college.json()["items"]}
    assert "maria.reyes@gmail.com" in emails

    both = client.get(
        "/api/admin/tracer",
        headers=headers,
        params={"college": CCS, "course": BSIT, "email": "reyes", "page_size": 20},
    )
    assert any(row["email"] == "maria.reyes@gmail.com" for row in both.json()["items"])

    other_course = client.get(
        "/api/admin/tracer",
        headers=headers,
        params={"college": CCS, "course": "Bachelor of Science in Computer Science", "email": "reyes"},
    )
    assert other_course.json()["total"] == 0

    nursing = client.get("/api/admin/tracer", headers=headers, params={"college": NURSING, "page_size": 20})
    assert "maria.reyes@gmail.com" not in {row["email"] for row in nursing.json()["items"]}

    maria = next(row for row in college.json()["items"] if row["email"] == "maria.reyes@gmail.com")
    kept = client.get(
        "/api/admin/tracer",
        headers=headers,
        params={"college": CCS, "alignment": maria["alignment"], "email": "reyes"},
    )
    assert any(row["email"] == "maria.reyes@gmail.com" for row in kept.json()["items"])
    blocked = client.get(
        "/api/admin/tracer",
        headers=headers,
        params={"college": CCS, "alignment": "Not A Status", "email": "reyes"},
    )
    assert blocked.json()["total"] == 0
