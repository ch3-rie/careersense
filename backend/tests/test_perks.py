from datetime import date, timedelta

from app.routers.admin_perks import perk_is_expired
from tests.conftest import auth_header, login


def test_perk_expiry_rules():
    today = date(2026, 9, 13)
    assert perk_is_expired(today - timedelta(days=1), today) is True
    assert perk_is_expired(today, today) is False
    assert perk_is_expired(today + timedelta(days=1), today) is False
    assert perk_is_expired(None, today) is False


def _frontend_expired(row, today=date(2026, 9, 13)):
    if row.get("expired") is True:
        return True
    valid_to = row.get("valid_to")
    if not valid_to:
        return False
    parsed = date.fromisoformat(str(valid_to)[:10])
    return parsed < today


def _filter_admin_perks(items, query="", category="", status="", expiry=""):
    needle = query.strip().lower()
    out = []
    for row in items:
        hay = f"{row.get('name', '')} {row.get('partner', '')} {row.get('discount', '')} {row.get('category', '')}".lower()
        if needle and needle not in hay:
            continue
        if category and row.get("category") != category:
            continue
        if status == "active" and not row.get("active"):
            continue
        if status == "inactive" and row.get("active"):
            continue
        if expiry == "expired" and not _frontend_expired(row):
            continue
        out.append(row)
    return out


def test_expired_filter_includes_expired_and_keeps_other_filters():
    rows = [
        {"name": "Yesterday Dining", "category": "Dining", "valid_to": "2026-09-12", "active": True, "expired": True},
        {"name": "Today Dining", "category": "Dining", "valid_to": "2026-09-13", "active": True, "expired": False},
        {"name": "Tomorrow Fitness", "category": "Fitness", "valid_to": "2026-09-14", "active": True, "expired": False},
        {"name": "No Expiry", "category": "Dining", "valid_to": None, "active": True, "expired": False},
        {"name": "Inactive Expired", "category": "Dining", "valid_to": "2026-09-12", "active": False, "expired": True},
    ]
    expired = {row["name"] for row in _filter_admin_perks(rows, expiry="expired")}
    assert expired == {"Yesterday Dining", "Inactive Expired"}
    active_expired = {row["name"] for row in _filter_admin_perks(rows, expiry="expired", status="active")}
    assert active_expired == {"Yesterday Dining"}
    searched = {row["name"] for row in _filter_admin_perks(rows, expiry="expired", query="dining")}
    assert searched == {"Yesterday Dining", "Inactive Expired"}
    dining = {row["name"] for row in _filter_admin_perks(rows, category="Dining")}
    assert "Tomorrow Fitness" not in dining
    assert "Yesterday Dining" in dining


def test_admin_perks_mark_expired_rows(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    created = client.post(
        "/api/admin/perks",
        headers=headers,
        json={
            "name": "QA Expired Perk",
            "discount": "10%",
            "valid_to": yesterday,
            "active": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["item"]["expired"] is True

    current = client.post(
        "/api/admin/perks",
        headers=headers,
        json={
            "name": "QA Current Perk",
            "discount": "15%",
            "valid_to": tomorrow,
            "active": True,
        },
    )
    assert current.status_code == 200, current.text
    assert current.json()["item"]["expired"] is False

    listing = client.get("/api/admin/perks", headers=headers).json()
    by_name = {row["name"]: row for row in listing["items"]}
    assert by_name["QA Expired Perk"]["expired"] is True
    assert by_name["QA Current Perk"]["expired"] is False
