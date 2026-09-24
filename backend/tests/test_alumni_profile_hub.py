from tests.conftest import auth_header, login


def test_profile_hub_payload(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    body = client.get("/api/alumni/dashboard", headers=auth_header(data["access_token"])).json()
    assert body["profile"]["college"] == "College of Computer Studies"
    assert body["profile"]["phone"]
    assert body["card"]["status"] == "Claimed"
    assert body["card"]["can_view"] is True
    assert body["card"]["label"] == "Claimed"
    assert body["career"]["alignment_status"] == "Aligned"
    industries = {row["industry"] for row in body["jobs"]}
    assert "Information and communications technology" in industries
    statuses = {row["status"] for row in body["perks"]}
    assert "Available" in statuses
    assert "Used" in statuses
    assert "Expired" in statuses
    cafe = next(row for row in body["perks"] if row["name"] == "Partner cafe discount")
    assert cafe["partner"]
    assert body["notifications"]
    assert "unread_count" in body
    assert "completion" in body
    assert 0 <= body["completion"]["percent"] <= 100
    assert sum(body["completion"]["weights"].values()) == 100
    assert body["completion"]["categories"]


def test_edit_profile_and_notifications(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    updated = client.put(
        "/api/alumni/profile",
        headers=headers,
        json={"phone": "+63 900 111 2222", "city": "San Fernando", "country_residence": "Philippines"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["profile"]["phone"] == "+63 900 111 2222"
    assert updated.json()["profile"]["city"] == "San Fernando"

    notes = updated.json()["notifications"]
    unread = next(row for row in notes if not row["read"])
    marked = client.post(f"/api/alumni/notifications/{unread['id']}/read", headers=headers)
    assert marked.status_code == 200
    saved = next(row for row in marked.json()["notifications"] if row["id"] == unread["id"])
    assert saved["read"] is True


def test_perk_claim_and_locked_benefit(client):
    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(maria["access_token"])
    perks = client.get("/api/alumni/dashboard", headers=headers).json()["perks"]
    cafe = next(row for row in perks if row["name"] == "Partner cafe discount")
    assert cafe["status"] == "Available"
    claimed = client.post(f"/api/alumni/perks/{cafe['id']}/claim", headers=headers)
    assert claimed.status_code == 200
    used = next(row for row in claimed.json()["perks"] if row["id"] == cafe["id"])
    assert used["status"] == "Used"
    assert used["code"]

    liza = login(client, "liza.torres@gmail.com", "Alumni@2026")
    liza_headers = auth_header(liza["access_token"])
    liza_perks = client.get("/api/alumni/dashboard", headers=liza_headers).json()["perks"]
    library = next(row for row in liza_perks if row["name"] == "AUF Library alumni access")
    assert library["status"] == "Locked"
    blocked = client.post(f"/api/alumni/perks/{library['id']}/claim", headers=liza_headers)
    assert blocked.status_code == 400
    assert client.get("/api/alumni/dashboard", headers=liza_headers).json()["card"]["status"] == "NotYetApplied"


def test_card_application_and_perks_endpoint(client):
    liza = login(client, "liza.torres@gmail.com", "Alumni@2026")
    headers = auth_header(liza["access_token"])
    card = client.get("/api/alumni/card", headers=headers)
    assert card.status_code == 200, card.text
    body = card.json()
    assert body["card"]["status"] == "NotYetApplied"
    assert body["card"]["gts_completed"] is True
    assert body["card"]["can_apply"] is True
    assert body["office"]["name"]
    assert "AAPS" in body["office"]["name"]
    assert "New" in body["membership_types"]
    assert body["identity"]["email"]
    assert body["identity"]["student_number"] or body["identity"]["student_id"]
    prefill = {field["key"]: field for field in body["prefill"]}
    assert prefill["email"]["value"] == "liza.torres@gmail.com"
    assert prefill["email"]["locked"] is True
    assert prefill["first_name"]["value"] == "Liza"
    assert prefill["last_name"]["value"] == "Torres"
    assert prefill["student_id"]["value"] == "2018-0330"
    assert prefill["college"]["value"] == "College of Business and Accountancy"
    assert "Accountancy" in prefill["course"]["value"]
    assert prefill["year_graduated"]["value"] == "2020"
    assert prefill["birthday"]["value"] == "1998-08-20"
    assert prefill["phone"]["value"]
    assert prefill["home_address"]["status"] == "needed"
    assert body["appointments"]
    slot_day = body["appointments"][0]
    slot_time = slot_day["times"][0]["time"]

    refused = client.post(
        "/api/alumni/card/apply",
        headers=headers,
        json={
            "birthday": "1998-08-20",
            "phone": "+63 918 555 0144",
            "city": "Mabalacat",
            "country_residence": "Philippines",
            "mailing_address": "12 Rizal St, Mabalacat",
            "company_affiliation": "Kapampangan Kitchen Group",
            "position": "Restaurant Manager",
            "membership_type": "New",
            "pickup_acknowledged": False,
            "appointment_date": slot_day["date"],
            "appointment_time": slot_time,
        },
    )
    assert refused.status_code == 400

    submitted = client.post(
        "/api/alumni/card/apply",
        headers=headers,
        json={
            "birthday": "1998-08-20",
            "phone": "+63 918 555 0144",
            "city": "Mabalacat",
            "country_residence": "Philippines",
            "mailing_address": "12 Rizal St, Mabalacat",
            "company_affiliation": "Kapampangan Kitchen Group",
            "position": "Restaurant Manager",
            "membership_type": "New",
            "pickup_acknowledged": True,
            "appointment_date": slot_day["date"],
            "appointment_time": slot_time,
        },
    )
    assert submitted.status_code == 200, submitted.text
    saved = submitted.json()["card"]
    assert saved["status"] == "ForVerification"
    assert saved["can_apply"] is False
    assert saved["application"]["mailing_address"]
    assert saved["application"]["membership_type"] == "New"
    assert saved["application"]["appointment_date"] == slot_day["date"]
    assert saved["application"]["appointment_time"] == slot_time
    assert saved["card_number"] == ""
    assert saved["show_pickup"] is False

    again = client.post(
        "/api/alumni/card/apply",
        headers=headers,
        json={
            "birthday": "1998-08-20",
            "phone": "+63 918 555 0144",
            "city": "Mabalacat",
            "country_residence": "Philippines",
            "mailing_address": "12 Rizal St, Mabalacat",
            "company_affiliation": "Kapampangan Kitchen Group",
            "position": "Restaurant Manager",
            "membership_type": "New",
            "pickup_acknowledged": True,
            "appointment_date": slot_day["date"],
            "appointment_time": slot_time,
        },
    )
    assert again.status_code == 400

    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    perks = client.get("/api/alumni/perks", headers=auth_header(maria["access_token"]))
    assert perks.status_code == 200
    assert perks.json()["perks"]


def test_photo_rejected_for_non_image(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.post(
        "/api/alumni/profile/photo",
        headers=auth_header(data["access_token"]),
        files={"photo": ("note.txt", b"not-an-image", "text/plain")},
    )
    assert response.status_code == 400


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
)


def test_photo_png_upload_and_size_limit(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    uploaded = client.post(
        "/api/alumni/profile/photo",
        headers=headers,
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["profile"]["has_photo"] is True
    photo = client.get("/api/alumni/profile/photo", headers=headers)
    assert photo.status_code == 200
    too_big = client.post(
        "/api/alumni/profile/photo",
        headers=headers,
        files={"photo": ("huge.jpg", b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024), "image/jpeg")},
    )
    assert too_big.status_code == 400
    unauth = client.post(
        "/api/alumni/profile/photo",
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    assert unauth.status_code in (401, 403)


def test_photo_can_be_removed_by_owner(client, db_session):
    from pathlib import Path

    from app.models import Account, AlumniProfile

    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    uploaded = client.post(
        "/api/alumni/profile/photo",
        headers=headers,
        files={"photo": ("avatar.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    phone = uploaded.json()["profile"]["phone"]
    city = uploaded.json()["profile"]["city"]

    db_session.expire_all()
    profile = (
        db_session.query(AlumniProfile)
        .join(Account)
        .filter(Account.personal_email == "maria.reyes@gmail.com")
        .one()
    )
    stored = profile.photo_path
    assert stored
    assert Path(stored).exists()

    removed = client.delete("/api/alumni/profile/photo", headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["profile"]["has_photo"] is False
    assert removed.json()["profile"]["phone"] == phone
    assert removed.json()["profile"]["city"] == city
    assert client.get("/api/alumni/profile/photo", headers=headers).status_code == 404
    assert not Path(stored).exists()

    db_session.expire_all()
    db_session.refresh(profile)
    assert profile.photo_path == ""
    assert profile.photo_mime == ""

    again = client.delete("/api/alumni/profile/photo", headers=headers)
    assert again.status_code == 404

    unauth = client.delete("/api/alumni/profile/photo")
    assert unauth.status_code in (401, 403)

    pending = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    assert client.delete("/api/alumni/profile/photo", headers=auth_header(pending["access_token"])).status_code == 403

    rejected = login(client, "ana.garcia@gmail.com", "Alumni@2026")
    assert client.delete("/api/alumni/profile/photo", headers=auth_header(rejected["access_token"])).status_code == 403

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    assert client.delete("/api/alumni/profile/photo", headers=auth_header(admin["access_token"])).status_code == 403


def test_edit_profile_bio_and_address(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    updated = client.put(
        "/api/alumni/profile",
        headers=headers,
        json={
            "phone": "+63 900 111 2222",
            "city": "San Fernando",
            "country_residence": "Philippines",
            "address": "123 Santo Rosario Street",
            "bio": "Information Technology graduate building web applications for local organizations.",
        },
    )
    assert updated.status_code == 200, updated.text
    profile = updated.json()["profile"]
    assert profile["bio"].startswith("Information Technology graduate")
    assert profile["address"] == "123 Santo Rosario Street"
    assert profile["has_cover"] is False
    too_long = client.put(
        "/api/alumni/profile",
        headers=headers,
        json={"bio": "x" * 801},
    )
    assert too_long.status_code == 422


def test_cover_png_upload_and_remove(client, db_session):
    from pathlib import Path

    from app.models import Account, AlumniProfile

    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    uploaded = client.post(
        "/api/alumni/profile/cover",
        headers=headers,
        files={"cover": ("cover.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["profile"]["has_cover"] is True
    cover = client.get("/api/alumni/profile/cover", headers=headers)
    assert cover.status_code == 200

    db_session.expire_all()
    profile = (
        db_session.query(AlumniProfile)
        .join(Account)
        .filter(Account.personal_email == "maria.reyes@gmail.com")
        .one()
    )
    stored = profile.cover_path
    assert stored
    assert Path(stored).exists()

    removed = client.delete("/api/alumni/profile/cover", headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["profile"]["has_cover"] is False
    assert client.get("/api/alumni/profile/cover", headers=headers).status_code == 404
    assert not Path(stored).exists()

    pending = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    assert client.post(
        "/api/alumni/profile/cover",
        headers=auth_header(pending["access_token"]),
        files={"cover": ("cover.png", PNG_1X1, "image/png")},
    ).status_code == 403


def test_studies_crud(client):
    data = login(client, "liza.torres@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    created = client.post(
        "/api/alumni/studies",
        headers=headers,
        json={
            "course_degree": "Master of Information Technology",
            "school": "Angeles University Foundation",
            "year_enrolled": "2024",
            "is_graduated": False,
        },
    )
    assert created.status_code == 200, created.text
    studies = created.json()["studies"]
    added = next(row for row in studies if row["course_degree"].startswith("Master"))
    assert added["school"] == "Angeles University Foundation"
    assert added["is_graduated"] is False
    dashboard = client.get("/api/alumni/dashboard", headers=headers).json()
    assert any(row["id"] == added["id"] for row in dashboard["further_studies"])

    updated = client.put(
        f"/api/alumni/studies/{added['id']}",
        headers=headers,
        json={
            "course_degree": "Master of Science in Information Technology",
            "school": "Angeles University Foundation",
            "year_enrolled": "2024",
            "is_graduated": True,
        },
    )
    assert updated.status_code == 200
    edited = next(row for row in updated.json()["studies"] if row["id"] == added["id"])
    assert edited["is_graduated"] is True
    assert edited["course_degree"].startswith("Master of Science")

    deleted = client.delete(f"/api/alumni/studies/{added['id']}", headers=headers)
    assert deleted.status_code == 200
    remaining_ids = [row["id"] for row in deleted.json()["studies"]]
    assert added["id"] not in remaining_ids

    pending = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    assert client.post(
        "/api/alumni/studies",
        headers=auth_header(pending["access_token"]),
        json={"course_degree": "MBA", "school": "AUF"},
    ).status_code == 403
