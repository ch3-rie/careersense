from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook

from tests.conftest import auth_header, login


def _admin(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(data["access_token"])


def test_soc_mapping_edit_rejects_duplicates(client):
    headers = _admin(client)
    created = client.post(
        "/api/admin/soc",
        headers=headers,
        json={
            "soc_code": "8801",
            "description": "Test occupation",
            "category": "Test",
            "title_patterns": "sample analyst",
            "degree_patterns": "testing",
        },
    )
    assert created.status_code == 200, created.text

    updated = client.put(
        "/api/admin/soc/8801",
        headers=headers,
        json={
            "soc_code": "8801",
            "description": "Revised test occupation",
            "category": "Revised",
            "title_patterns": "sample analyst, reviewer",
            "degree_patterns": "testing",
            "major_group": "88",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["item"]["description"] == "Revised test occupation"

    listing = client.get("/api/admin/soc?q=8801", headers=headers)
    assert listing.status_code == 200
    match = next(row for row in listing.json()["items"] if row["soc_code"] == "8801")
    assert match["description"] == "Revised test occupation"
    assert "reviewer" in match["title_patterns"]

    other = client.post(
        "/api/admin/soc",
        headers=headers,
        json={"soc_code": "8802", "description": "Second occupation"},
    )
    assert other.status_code == 200, other.text
    duplicate = client.put(
        "/api/admin/soc/8802",
        headers=headers,
        json={"soc_code": "8801", "description": "Should not replace"},
    )
    assert duplicate.status_code == 400

    mapped = client.post(
        "/api/admin/job-mappings",
        headers=headers,
        json={"raw_title": "Sample Analyst", "soc_code": "8801", "admin_notes": "Initial"},
    )
    assert mapped.status_code == 200, mapped.text
    rows = client.get("/api/admin/job-mappings?q=Sample%20Analyst", headers=headers).json()["items"]
    row = next(item for item in rows if item["raw_title"] == "Sample Analyst")
    edited = client.put(
        f"/api/admin/job-mappings/{row['id']}",
        headers=headers,
        json={"raw_title": "Sample Analyst", "soc_code": "8802", "admin_notes": "Moved"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["item"]["soc_code"] == "8802"
    assert edited.json()["item"]["admin_notes"] == "Moved"

    alumni = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    assert client.put(
        "/api/admin/soc/8801",
        headers=auth_header(alumni["access_token"]),
        json={"soc_code": "8801", "description": "Nope"},
    ).status_code == 403


def test_perk_until_further_notice_does_not_expire(client):
    headers = _admin(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    open_ended = client.post(
        "/api/admin/perks",
        headers=headers,
        json={
            "name": "Open Library Desk",
            "partner": "AUF University Library",
            "discount": "Desk access",
            "valid_until_further_notice": True,
            "valid_to": yesterday,
            "active": True,
        },
    )
    assert open_ended.status_code == 200, open_ended.text
    item = open_ended.json()["item"]
    assert item["valid_until_further_notice"] is True
    assert item["valid_to"] is None
    assert item["expired"] is False

    missing = client.post(
        "/api/admin/perks",
        headers=headers,
        json={"name": "Needs a date", "discount": "10%", "active": True},
    )
    assert missing.status_code == 400

    dated = client.post(
        "/api/admin/perks",
        headers=headers,
        json={"name": "Dated Cafe Offer", "discount": "5%", "valid_to": yesterday, "active": True},
    )
    assert dated.status_code == 200, dated.text
    assert dated.json()["item"]["expired"] is True
    assert dated.json()["item"]["valid_until_further_notice"] is False

    edited = client.put(
        f"/api/admin/perks/{item['id']}",
        headers=headers,
        json={
            "name": "Open Library Desk",
            "partner": "AUF University Library",
            "discount": "Desk access",
            "valid_until_further_notice": True,
            "active": False,
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["item"]["active"] is False
    assert edited.json()["item"]["valid_until_further_notice"] is True
    kept = client.get(f"/api/admin/perks/{item['id']}", headers=headers)
    assert kept.status_code == 200
    assert kept.json()["name"] == "Open Library Desk"


def test_employee_number_and_add_users_only(client):
    headers = _admin(client)
    rejected = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "first_name": "Number",
            "last_name": "Check",
            "email": "number.check@auf.edu.ph",
            "employee_number": "100",
            "confirm": True,
        },
    )
    assert rejected.status_code == 400

    created = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "first_name": "Number",
            "last_name": "Check",
            "email": "number.check@auf.edu.ph",
            "employee_number": "001",
            "confirm": True,
        },
    )
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["employee_number"] == "001"
    assert isinstance(item["employee_number"], str)
    assert item["admin_privileges"] == "add_users"
    assert item["privilege_label"] == "Add Users"
    assert item["full_admin"] is False

    duplicate = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "first_name": "Other",
            "last_name": "Person",
            "email": "other.person@auf.edu.ph",
            "employee_number": "001",
            "confirm": True,
        },
    )
    assert duplicate.status_code == 400
    assert "already assigned" in duplicate.json()["detail"]

    signed = login(client, "number.check@auf.edu.ph", created.json()["temporary_password"])
    assert signed["user"]["employee_number"] == "001"
    assert signed["user"]["full_admin"] is False
    limited = auth_header(signed["access_token"])
    assert client.get("/api/admin/users", headers=limited).status_code == 200
    assert client.get("/api/admin/soc", headers=limited).status_code == 403
    assert client.get("/api/admin/perks", headers=limited).status_code == 403
    assert client.get("/api/admin/partner-activity", headers=limited).status_code == 403
    assert client.post(
        "/api/admin/perks",
        headers=limited,
        json={"name": "Blocked perk", "discount": "1%", "valid_until_further_notice": True},
    ).status_code == 403
    added = client.post(
        "/api/admin/users",
        headers=limited,
        json={
            "first_name": "Second",
            "last_name": "Clerk",
            "email": "second.clerk@auf.edu.ph",
            "employee_number": "002",
            "confirm": True,
        },
    )
    assert added.status_code == 200, added.text
    assert added.json()["item"]["admin_privileges"] == "add_users"
    assert added.json()["item"]["employee_number"] == "002"
    assert client.patch(
        f"/api/admin/users/{item['id']}",
        headers=limited,
        json={"first_name": "Changed"},
    ).status_code == 403

    me = client.get("/api/auth/me", headers=headers).json()["user"]
    assert me["full_admin"] is True
    assert me["admin_privileges"] == ""


def test_soc_excel_import_adds_codes_and_skips_existing(client):
    headers = _admin(client)
    created = client.post(
        "/api/admin/soc",
        headers=headers,
        json={"soc_code": "8891", "description": "Existing import code"},
    )
    assert created.status_code == 200, created.text

    book = Workbook()
    sheet = book.active
    sheet.append(["PSOC/SOC Code", "Description", "Category", "Job-Title Patterns", "Degree Patterns", "Major Group"])
    sheet.append(["8891", "Existing import code", "Test", "analyst", "testing", "88"])
    sheet.append(["8892", "Imported occupation", "ICT", "analyst", "testing", "88"])
    sheet.append(["", "", "", "", "", ""])
    sheet.append(["8810", "", "ICT", "", "", ""])
    raw = BytesIO()
    book.save(raw)

    imported = client.post(
        "/api/admin/soc/import",
        headers=headers,
        files={"file": ("codes.xlsx", raw.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["added"] == 1
    assert body["skipped"] == 1
    assert body["invalid"] == 1
    assert any("Row 5" in issue for issue in body["issues"])

    listed = client.get("/api/admin/soc?q=8892", headers=headers)
    assert listed.status_code == 200
    match = next(row for row in listed.json()["items"] if row["soc_code"] == "8892")
    assert match["description"] == "Imported occupation"
    assert match["category"] == "ICT"
    assert match["title_patterns"] == "analyst"

    rejected = client.post(
        "/api/admin/soc/import",
        headers=headers,
        files={"file": ("codes.csv", b"code,description\n1,Test\n", "text/csv")},
    )
    assert rejected.status_code == 400
