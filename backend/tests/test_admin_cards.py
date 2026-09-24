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
