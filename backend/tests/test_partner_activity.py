from datetime import datetime, timedelta, timezone

from app.models import AlumniPerk, PartnerActivity
from app.services.alumni_qr import alumni_qr_token
from tests.conftest import auth_header, login


def _admin(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(admin["access_token"])


def test_partner_scans_visits_and_redemptions_stay_separate(client, db_session):
    headers = _admin(client)
    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    alumni_headers = auth_header(maria["access_token"])
    denied = client.get("/api/admin/partner-activity", headers=alumni_headers)
    assert denied.status_code == 403
    assert client.get("/api/admin/partner-activity").status_code == 401
    assert client.post("/api/admin/partner-activity/scans", headers=alumni_headers, json={"partner": "X", "payload": "v1", "idempotency_key": "alumni-scan-1"}).status_code == 403

    before = db_session.query(PartnerActivity).count()
    token = alumni_qr_token(maria["user"]["id"])
    opened = client.get(f"/api/public/alumni-qr/{token}")
    image = client.get("/api/alumni/qr/image", headers=alumni_headers)
    assert opened.status_code == 200
    assert image.status_code == 200
    db_session.expire_all()
    assert db_session.query(PartnerActivity).count() == before

    catalog = client.get("/api/admin/partner-activity/partners", headers=headers)
    assert catalog.status_code == 200
    partner = next(item for item in catalog.json()["items"] if item["active"] and any(perk["usable"] for perk in item["perks"]))
    perk = next(item for item in partner["perks"] if item["usable"])

    forged = client.post(
        "/api/admin/partner-activity/scans",
        headers=headers,
        json={"partner": "Not A Real Partner", "payload": token, "idempotency_key": "scan-forged-01"},
    )
    assert forged.status_code == 400

    scan = client.post(
        "/api/admin/partner-activity/scans",
        headers=headers,
        json={"partner": partner["name"], "payload": f"https://careersense.example/verify/qr/{token}", "idempotency_key": "scan-maria-01"},
    )
    assert scan.status_code == 200, scan.text
    body = scan.json()
    assert body["status"] == "success"
    assert body["activity_type"] == "qr_scan"
    assert body["recording_method"] == "qr_scan"
    assert body["email"] == "maria.reyes@gmail.com"
    assert "token" not in body
    replay = client.post(
        "/api/admin/partner-activity/scans",
        headers=headers,
        json={"partner": partner["name"], "payload": token, "idempotency_key": "scan-maria-01"},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == body["id"]
    assert replay.json()["replayed"] is True

    rejected = client.post(
        "/api/admin/partner-activity/scans",
        headers=headers,
        json={"partner": partner["name"], "payload": "not-a-real-qr", "idempotency_key": "scan-rejected-01"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["alumni_account_id"] is None

    after_scans = client.get("/api/admin/partner-activity/summary", headers=headers)
    assert after_scans.status_code == 200
    totals = after_scans.json()
    assert totals["qr_scans"] == 2
    assert totals["qr_scans_successful"] == 1
    assert totals["qr_scans_unsuccessful"] == 1
    assert totals["partner_visits"] == 0
    assert totals["confirmed_redemptions"] == 0

    found = client.get("/api/admin/partner-activity/alumni", headers=headers, params={"q": "Maria Reyes"})
    assert found.status_code == 200
    assert any(item["email"] == "maria.reyes@gmail.com" for item in found.json()["items"])
    alumni_id = next(item["id"] for item in found.json()["items"] if item["email"] == "maria.reyes@gmail.com")

    visit_at = datetime(2024, 6, 1, 2, 30, tzinfo=timezone.utc)
    visit = client.post(
        "/api/admin/partner-activity",
        headers=headers,
        json={
            "alumni_account_id": alumni_id,
            "partner": partner["name"],
            "activity_type": "partner_visit",
            "activity_at": visit_at.isoformat(),
            "status": "pending",
            "notes": "Front desk sign-in",
            "idempotency_key": "visit-maria-01",
            "related_activity_id": body["id"],
        },
    )
    assert visit.status_code == 200, visit.text
    assert visit.json()["recording_method"] == "manual"
    assert visit.json()["activity_type"] == "partner_visit"
    assert visit.json()["status"] == "pending"
    assert visit.json()["related_activity"]["id"] == body["id"]

    redemption = client.post(
        "/api/admin/partner-activity",
        headers=headers,
        json={
            "alumni_account_id": alumni_id,
            "partner": partner["name"],
            "activity_type": "benefit_redemption",
            "activity_at": (visit_at + timedelta(hours=1)).isoformat(),
            "status": "pending",
            "perk_id": perk["id"],
            "reference_code": "REF-100",
            "idempotency_key": "redeem-maria-01",
        },
    )
    assert redemption.status_code == 200, redemption.text
    redemption_id = redemption.json()["id"]
    confirmed = client.patch(f"/api/admin/partner-activity/{redemption_id}", headers=headers, json={"status": "confirmed"})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert any(entry["action"] == "partner_activity.update" for entry in confirmed.json()["audit"])
    assert confirmed.json()["benefit_label"]

    locked = client.patch(f"/api/admin/partner-activity/{body['id']}", headers=headers, json={"status": "confirmed"})
    assert locked.status_code == 400

    totals = client.get("/api/admin/partner-activity/summary", headers=headers).json()
    assert totals["qr_scans"] == 2
    assert totals["partner_visits"] == 1
    assert totals["confirmed_redemptions"] == 1
    assert totals["unique_alumni"] == 1

    drill = client.get("/api/admin/partner-activity", headers=headers, params={"match": "redemptions"})
    assert drill.status_code == 200
    assert drill.json()["total"] == totals["confirmed_redemptions"]
    assert all(item["activity_type"] == "benefit_redemption" and item["status"] == "confirmed" for item in drill.json()["items"])

    named = client.get("/api/admin/partner-activity", headers=headers, params={"q": "Maria Reyes", "activity_type": "partner_visit", "method": "manual", "status": "pending"})
    assert named.json()["total"] == 1
    dated = client.get("/api/admin/partner-activity", headers=headers, params={"date_from": "2024-06-01", "date_to": "2024-06-01", "partner": partner["name"]})
    assert dated.json()["total"] == 2

    future = client.post(
        "/api/admin/partner-activity",
        headers=headers,
        json={
            "alumni_account_id": alumni_id,
            "partner": partner["name"],
            "activity_type": "partner_visit",
            "activity_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "status": "pending",
            "idempotency_key": "visit-future-01",
        },
    )
    assert future.status_code == 400

    perk_row = db_session.get(AlumniPerk, perk["id"])
    perk_row.active = False
    db_session.commit()
    try:
        still = client.get(f"/api/admin/partner-activity/{redemption_id}", headers=headers)
        assert still.status_code == 200
        assert still.json()["benefit_label"]
        assert still.json()["partner"] == partner["name"]
        blocked = client.post(
            "/api/admin/partner-activity",
            headers=headers,
            json={
                "alumni_account_id": alumni_id,
                "partner": partner["name"],
                "activity_type": "benefit_redemption",
                "activity_at": visit_at.isoformat(),
                "status": "confirmed",
                "perk_id": perk["id"],
                "idempotency_key": "redeem-inactive-1",
            },
        )
        assert blocked.status_code == 400
    finally:
        perk_row = db_session.get(AlumniPerk, perk["id"])
        perk_row.active = True
        db_session.commit()
