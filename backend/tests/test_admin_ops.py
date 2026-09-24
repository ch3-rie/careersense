from tests.conftest import auth_header, login


def test_admin_dashboard_and_approval_search(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])

    dash = client.get("/api/admin/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert "pending_approvals" in body
    assert "percent_aligned" in body
    assert set(body["alignment_distribution"]) == {"Aligned", "Unknown", "Misaligned"}

    queue = client.get("/api/admin/approvals?page=1&page_size=8&sort_by=name&sort_dir=asc", headers=headers)
    assert queue.status_code == 200
    payload = queue.json()
    assert payload["page_size"] == 8
    assert "items" in payload

    search = client.get("/api/admin/approvals?q=juan&page_size=8", headers=headers)
    assert search.status_code == 200
    names = " ".join(row["name"].lower() + row["email"].lower() for row in search.json()["items"])
    assert "juan" in names

    reports = client.get("/api/admin/reports", headers=headers)
    assert reports.status_code == 200
    assert "options" in reports.json()
    assert "colleges" in reports.json()["options"]


def test_verify_returns_match_type(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    queue = client.get("/api/admin/approvals?page_size=8", headers=headers)
    items = queue.json()["items"]
    assert items
    account_id = items[0]["id"]
    verify = client.post(f"/api/admin/approvals/{account_id}/verify", headers=headers)
    assert verify.status_code == 200
    data = verify.json()
    assert "match_type" in data


def test_tracer_record_detail(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    listing = client.get("/api/admin/tracer?page_size=12", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert items
    record_id = items[0]["id"]
    detail = client.get(f"/api/admin/tracer/{record_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == record_id
    assert "email" in body
    assert "data" in body
    missing = client.get("/api/admin/tracer/999999", headers=headers)
    assert missing.status_code == 404


def test_approve_and_reject_update_queue_and_dashboard(client, monkeypatch):
    from io import BytesIO

    from app.services.email import EmailSendResult
    from tests.conftest import unique_resume

    mailed = []
    monkeypatch.setattr(
        "app.routers.admin.send_account_status_email",
        lambda **kwargs: mailed.append(kwargs) or EmailSendResult(ok=True, provider="resend"),
    )

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])

    start = client.post(
        "/api/auth/register",
        data={
            "email": "review.test@gmail.com",
            "password": "Alumni@2026",
            "confirm_password": "Alumni@2026",
            "privacy_consent": "true",
        },
        files={"resume": ("resume.txt", BytesIO(unique_resume("Review", "Tester")), "text/plain")},
    )
    assert start.status_code == 200, start.text
    complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": start.json()["registration_token"],
            "first_name": "Review",
            "last_name": "Tester",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
        },
    )
    assert complete.status_code == 200, complete.text
    reject_id = complete.json()["user"]["id"]

    approve_start = client.post(
        "/api/auth/register",
        data={
            "email": "review.approve@gmail.com",
            "password": "Alumni@2026",
            "confirm_password": "Alumni@2026",
            "privacy_consent": "true",
        },
        files={"resume": ("resume.txt", BytesIO(unique_resume("Approve", "Tester")), "text/plain")},
    )
    assert approve_start.status_code == 200, approve_start.text
    approve_complete = client.post(
        "/api/auth/register/complete",
        json={
            "registration_token": approve_start.json()["registration_token"],
            "first_name": "Approve",
            "last_name": "Tester",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2024",
            "ever_employed": "No",
            "is_currently_employed": "No",
        },
    )
    assert approve_complete.status_code == 200, approve_complete.text
    approve_id = approve_complete.json()["user"]["id"]

    before = client.get("/api/admin/dashboard", headers=headers).json()

    too_short = client.post(
        f"/api/admin/approvals/{reject_id}/reject",
        headers=headers,
        json={"reason": "no"},
    )
    assert too_short.status_code == 422

    still_pending = client.get("/api/admin/approvals?page_size=50", headers=headers).json()
    assert reject_id in {row["id"] for row in still_pending["items"]}

    approved = client.post(f"/api/admin/approvals/{approve_id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "Active"

    again = client.post(f"/api/admin/approvals/{approve_id}/approve", headers=headers)
    assert again.status_code == 200
    assert again.json().get("already_processed") is True

    rejected = client.post(
        f"/api/admin/approvals/{reject_id}/reject",
        headers=headers,
        json={"reason": "Documents did not match the graduate registry."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"

    cannot_reject_active = client.post(
        f"/api/admin/approvals/{approve_id}/reject",
        headers=headers,
        json={"reason": "Too late to reject this account."},
    )
    assert cannot_reject_active.status_code == 409

    remaining = {row["id"] for row in client.get("/api/admin/approvals?page_size=50", headers=headers).json()["items"]}
    assert approve_id not in remaining
    assert reject_id not in remaining

    after = client.get("/api/admin/dashboard", headers=headers).json()
    assert after["pending_approvals"] == before["pending_approvals"] - 2
    assert after["approved_alumni"] == before["approved_alumni"] + 1
    assert after["rejected_alumni"] == before["rejected_alumni"] + 1

    detail = client.get(f"/api/admin/approvals/{approve_id}", headers=headers).json()
    assert detail["account"]["status"] == "Active"
    assert detail["account"]["is_verified"] is True
    assert [item["status"] for item in mailed] == ["Active", "Rejected"]
    assert mailed[0]["to_address"] == "review.approve@gmail.com"
    assert mailed[1]["to_address"] == "review.test@gmail.com"
    assert "Documents did not match" in mailed[1]["reason"]

    juan = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    assert client.get("/api/alumni/dashboard", headers=auth_header(juan["access_token"])).status_code == 403

