from io import BytesIO

from tests.conftest import auth_header, login, unique_resume

GTS = {
    "first_name": "Card",
    "last_name": "Applicant",
    "degree": "Bachelor of Science in Information Technology",
    "year_graduated": "2024",
    "ever_employed": "No",
    "is_currently_employed": "No",
}

APPLY = {
    "birthday": "1999-01-15",
    "phone": "+63 918 555 0199",
    "city": "Angeles",
    "country_residence": "Philippines",
    "mailing_address": "100 Freedom Park, Angeles City",
    "company_affiliation": "",
    "position": "",
    "membership_type": "New",
    "pickup_acknowledged": True,
}


def _apply_body(client, token):
    card = client.get("/api/alumni/card", headers=auth_header(token))
    assert card.status_code == 200, card.text
    day = card.json()["appointments"][0]
    return {**APPLY, "appointment_date": day["date"], "appointment_time": day["times"][0]["time"]}


def _register_active(client, email, first="Card", last="Applicant"):
    start = client.post(
        "/api/auth/register",
        data={
            "email": email,
            "password": "Alumni@2026",
            "confirm_password": "Alumni@2026",
            "privacy_consent": "true",
        },
        files={"resume": ("resume.txt", BytesIO(unique_resume(first, last)), "text/plain")},
    )
    assert start.status_code == 200, start.text
    complete = client.post(
        "/api/auth/register/complete",
        json={"registration_token": start.json()["registration_token"], **GTS, "first_name": first, "last_name": last},
    )
    assert complete.status_code == 200, complete.text
    account_id = complete.json()["user"]["id"]
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    approved = client.post(
        f"/api/admin/approvals/{account_id}/approve",
        headers=auth_header(admin["access_token"]),
    )
    assert approved.status_code == 200, approved.text
    alumni = login(client, email, "Alumni@2026")
    return alumni, account_id, admin


def test_alumni_cannot_self_approve_card(client):
    alumni, account_id, _admin = _register_active(client, "aac.self@gmail.com", "Self", "Card")
    headers = auth_header(alumni["access_token"])
    applied = client.post("/api/alumni/card/apply", headers=headers, json=_apply_body(client, alumni["access_token"]))
    assert applied.status_code == 200
    assert applied.json()["card"]["status"] == "ForVerification"
    blocked = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=headers,
        json={"status": "Approved"},
    )
    assert blocked.status_code == 403
    still = client.get("/api/alumni/card", headers=headers).json()
    assert still["card"]["status"] == "ForVerification"


def test_admin_card_status_linear_flow(client):
    alumni, account_id, admin = _register_active(client, "aac.flow@gmail.com", "Flow", "Card")
    alumni_headers = auth_header(alumni["access_token"])
    admin_headers = auth_header(admin["access_token"])
    assert client.post("/api/alumni/card/apply", headers=alumni_headers, json=_apply_body(client, alumni["access_token"])).status_code == 200

    dash = client.get("/api/admin/dashboard", headers=admin_headers).json()
    assert dash["pending_card_applications"] >= 1

    listing = client.get("/api/admin/cards?status=ForVerification&page_size=20", headers=admin_headers)
    assert listing.status_code == 200
    assert account_id in {row["id"] for row in listing.json()["items"]}

    skipped = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "Claimed"},
    )
    assert skipped.status_code == 400
    printed_early = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "ReadyForPickup"},
    )
    assert printed_early.status_code == 400
    still_requested = client.get("/api/alumni/card", headers=alumni_headers).json()
    assert still_requested["card"]["status"] == "ForVerification"
    assert still_requested["card"]["issued_at"] is None

    approved = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "Approved"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["card"]["status"] == "Approved"

    ready = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "ReadyForPickup"},
    )
    assert ready.status_code == 200
    assert ready.json()["card"]["status"] == "ReadyForPickup"

    claimed = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "Claimed"},
    )
    assert claimed.status_code == 200
    assert claimed.json()["card"]["status"] == "Claimed"
    assert claimed.json()["card"]["card_number"]

    alumni_view = client.get("/api/alumni/card", headers=alumni_headers).json()
    assert alumni_view["card"]["status"] == "Claimed"
    assert alumni_view["card"]["can_view"] is True

    notes = client.get("/api/alumni/notifications", headers=alumni_headers).json()["notifications"]
    titles = " ".join(item["title"] for item in notes)
    assert "approved" in titles.lower() or "claimed" in titles.lower() or "ready" in titles.lower()


def test_unauthenticated_cannot_list_cards(client):
    assert client.get("/api/admin/cards").status_code == 401


def test_renewal_scope_excludes_new_applications(client):
    new_alumni, new_id, admin = _register_active(client, "aac.new@gmail.com", "New", "Card")
    renewal_alumni, renewal_id, _same = _register_active(client, "aac.renew@gmail.com", "Renew", "Card")
    admin_headers = auth_header(admin["access_token"])
    new_body = {**_apply_body(client, new_alumni["access_token"]), "membership_type": "New"}
    renewal_body = {**_apply_body(client, renewal_alumni["access_token"]), "membership_type": "Renewal"}
    assert client.post("/api/alumni/card/apply", headers=auth_header(new_alumni["access_token"]), json=new_body).status_code == 200
    assert client.post("/api/alumni/card/apply", headers=auth_header(renewal_alumni["access_token"]), json=renewal_body).status_code == 200

    scoped = client.get("/api/admin/cards?scope=renewal&page_size=20", headers=admin_headers)
    assert scoped.status_code == 200, scoped.text
    payload = scoped.json()
    ids = {row["id"] for row in payload["items"]}
    assert renewal_id in ids
    assert new_id not in ids
    assert payload["status"] == ""
    assert payload["summary"]["all"] >= 1
    assert payload["summary"]["printing"] >= 0
    assert payload["summary"]["undefined"] >= 1
    renewal_row = next(row for row in payload["items"] if row["id"] == renewal_id)
    assert renewal_row["status"] == "ForVerification"
    assert renewal_row["display_status"] == "Undefined"
    assert renewal_row["actions"] == ["Claimed", "ForVerification", "Approved", "ReadyForPickup"]
    assert renewal_row["year_graduated"] == "2024"
    assert renewal_row["claimed_at"] is None
    assert renewal_row["id_status"] == "Undefined"
    assert renewal_row["eligibility"] == "not_determined"
    assert renewal_row["next_renewal_on"] is None
    assert renewal_row["id_note"]
    undefined = client.get("/api/admin/cards?scope=renewal&id_status=undefined&page_size=20", headers=admin_headers)
    assert renewal_id in {row["id"] for row in undefined.json()["items"]}
    undefined_queue = client.get("/api/admin/cards?scope=renewal&queue=undefined&page_size=20", headers=admin_headers)
    assert renewal_id in {row["id"] for row in undefined_queue.json()["items"]}
    before_printing = client.get("/api/admin/cards?scope=renewal&queue=printing&page_size=20", headers=admin_headers)
    assert before_printing.status_code == 200
    assert renewal_id not in {row["id"] for row in before_printing.json()["items"]}
    before_requesting = client.get("/api/admin/cards?scope=renewal&queue=requesting&page_size=20", headers=admin_headers)
    assert renewal_id not in {row["id"] for row in before_requesting.json()["items"]}
    approved = client.post(
        f"/api/admin/cards/{renewal_id}/status",
        headers=admin_headers,
        json={"status": "Approved"},
    )
    assert approved.status_code == 200
    printing = client.get("/api/admin/cards?scope=renewal&queue=printing&page_size=20", headers=admin_headers)
    assert renewal_id in {row["id"] for row in printing.json()["items"]}
    assert printing.json()["summary"]["printing"] >= 1
    still_requesting = client.get("/api/admin/cards?scope=renewal&queue=requesting&page_size=20", headers=admin_headers)
    assert renewal_id not in {row["id"] for row in still_requesting.json()["items"]}
    settled = client.get("/api/admin/cards?scope=renewal&id_status=undefined&page_size=20", headers=admin_headers)
    assert renewal_id not in {row["id"] for row in settled.json()["items"]}

    by_year = client.get("/api/admin/cards?scope=renewal&year=2024&page_size=20", headers=admin_headers)
    assert renewal_id in {row["id"] for row in by_year.json()["items"]}
    other_year = client.get("/api/admin/cards?scope=renewal&year=2027&page_size=20", headers=admin_headers)
    assert renewal_id not in {row["id"] for row in other_year.json()["items"]}

    open_list = client.get("/api/admin/cards?status=ForVerification&page_size=20", headers=admin_headers)
    assert new_id in {row["id"] for row in open_list.json()["items"]}


def test_account_link_does_not_create_a_renewal_or_start_the_cycle(client, db_session):
    from app.models import AdminLog, AlumniCard, UniversityRecord

    email = "early.batch.9001@gmail.com"
    db_session.add(
        UniversityRecord(
            student_id="2015-9001",
            first_name="Early",
            last_name="Batch",
            personal_email=email,
            degree="Bachelor of Science in Accountancy",
            year_graduated="2016",
            course_code="BSA",
            college="College of Business and Accountancy",
        )
    )
    db_session.commit()

    alumni, account_id, admin = _register_active(client, email, "Early", "Batch")
    admin_headers = auth_header(admin["access_token"])
    alumni_headers = auth_header(alumni["access_token"])
    db_session.expire_all()
    stored = db_session.query(AlumniCard).filter(AlumniCard.account_id == account_id).one_or_none()
    assert stored is None

    detail = client.get(f"/api/admin/cards/{account_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["account"]["student_id"] == "2015-9001"
    assert body["account"]["year_graduated"] == "2016"
    assert body["card"]["status"] == "NotYetApplied"
    assert body["card"]["issued_at"] is None
    assert body["renewal"]["id_status"] == "Undefined"
    assert body["renewal"]["eligibility"] == "not_determined"
    assert body["renewal"]["next_renewal_on"] is None
    assert body["actions"] == []
    assert body["renewal"]["display_status"] == "Undefined"
    scoped = client.get("/api/admin/cards?scope=renewal&q=2015-9001&page_size=20", headers=admin_headers)
    assert account_id not in {row["id"] for row in scoped.json()["items"]}

    applied = client.post(
        "/api/alumni/card/apply",
        headers=alumni_headers,
        json={**_apply_body(client, alumni["access_token"]), "membership_type": "Renewal"},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["card"]["status"] == "ForVerification"
    assert applied.json()["card"]["issued_at"] is None
    duplicate = client.post(
        "/api/alumni/card/apply",
        headers=alumni_headers,
        json={**_apply_body(client, alumni["access_token"]), "membership_type": "Renewal"},
    )
    assert duplicate.status_code == 400

    requested = client.get(f"/api/admin/cards/{account_id}", headers=admin_headers).json()
    assert requested["card"]["status"] == "ForVerification"
    assert requested["renewal"]["display_status"] == "Undefined"
    assert requested["actions"] == ["Claimed", "ForVerification", "Approved", "ReadyForPickup"]

    approved = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "Approved"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["card"]["status"] == "Approved"
    assert approved.json()["card"]["issued_at"] is None
    assert client.get(f"/api/admin/cards/{account_id}", headers=admin_headers).json()["actions"] == ["ReadyForPickup"]

    printed = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "ReadyForPickup"},
    )
    assert printed.status_code == 200, printed.text
    assert printed.json()["card"]["status"] == "ReadyForPickup"
    assert printed.json()["card"]["issued_at"] is None
    assert printed.json()["card"]["pickup_ready_at"]
    after_print = client.get(f"/api/admin/cards/{account_id}", headers=admin_headers).json()
    assert after_print["card"]["status"] == "ReadyForPickup"
    assert after_print["renewal"]["claimed_at"] is None
    assert after_print["renewal"]["next_renewal_on"] is None
    assert after_print["actions"] == ["Claimed"]

    future = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "Claimed", "claimed_on": "2099-01-01"},
    )
    assert future.status_code == 400
    assert client.get("/api/alumni/card", headers=alumni_headers).json()["card"]["status"] == "ReadyForPickup"

    claimed = client.post(
        f"/api/admin/cards/{account_id}/status",
        headers=admin_headers,
        json={"status": "Claimed", "claimed_on": "2022-02-08"},
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["card"]["status"] == "Claimed"
    finished = client.get(f"/api/admin/cards/{account_id}", headers=admin_headers).json()
    assert finished["card"]["status"] == "Claimed"
    assert finished["renewal"]["display_status"] == "ForRenewal"
    assert finished["renewal"]["id_status"] == "Undefined"
    assert finished["renewal"]["claiming_date"] == "2022-02-08"
    assert finished["renewal"]["next_renewal_on"] == "2026-02-08"
    assert finished["renewal"]["eligibility"] == "due"
    assert finished["actions"] == ["ForVerification"]
    due_list = client.get("/api/admin/cards?scope=renewal&queue=renewal&page_size=20", headers=admin_headers)
    assert account_id in {row["id"] for row in due_list.json()["items"]}
    assert due_list.json()["summary"]["renewal"] >= 1
    still_claimed = client.get("/api/admin/cards?scope=renewal&queue=claimed&page_size=20", headers=admin_headers)
    assert account_id not in {row["id"] for row in still_claimed.json()["items"]}

    edited = client.put(
        "/api/alumni/profile",
        headers=alumni_headers,
        json={"phone": "09170001111", "city": "Angeles", "address": "100 Freedom Park, Angeles City"},
    )
    assert edited.status_code == 200, edited.text
    untouched = client.get(f"/api/admin/cards/{account_id}", headers=admin_headers).json()
    assert untouched["card"]["status"] == "Claimed"
    assert untouched["renewal"]["claiming_date"] == "2022-02-08"
    assert untouched["renewal"]["next_renewal_on"] == "2026-02-08"
    assert untouched["renewal"]["printed_at"] == finished["renewal"]["printed_at"]

    db_session.expire_all()
    logs = (
        db_session.query(AdminLog)
        .filter(AdminLog.action_type == "AAC_STATUS", AdminLog.target_id == str(account_id))
        .order_by(AdminLog.id.asc())
        .all()
    )
    assert [row.old_value["status"] for row in logs] == ["ForVerification", "Approved", "ReadyForPickup"]
    assert [row.new_value["status"] for row in logs] == ["Approved", "ReadyForPickup", "Claimed"]
    assert logs[-1].new_value["claimed_on"] == "2022-02-08"
    assert logs[-1].admin_id == admin["user"]["id"]
    found = client.get("/api/admin/cards?scope=renewal&q=2015-9001&year=2016&page_size=20", headers=admin_headers)
    assert account_id in {row["id"] for row in found.json()["items"]}
    hidden = client.get("/api/admin/cards?scope=renewal&q=2015-9001&year=2027&page_size=20", headers=admin_headers)
    assert account_id not in {row["id"] for row in hidden.json()["items"]}
