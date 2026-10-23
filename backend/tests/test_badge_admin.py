from app.models import AlumniBadge, BadgeDefinition
from app.services.achievements import CATALOG_KEYS
from tests.conftest import auth_header, login

MARIA = "maria.reyes@gmail.com"


def _admin(client):
    return auth_header(login(client, "admin@auf.edu.ph", "Admin@AUF2026")["access_token"])


def _cleanup(db_session, key: str) -> None:
    db_session.query(AlumniBadge).filter(AlumniBadge.badge_key == key).delete(synchronize_session=False)
    db_session.query(BadgeDefinition).filter(BadgeDefinition.key == key).delete(synchronize_session=False)
    db_session.commit()


def test_badge_management_is_admin_only(client):
    assert client.get("/api/admin/badges").status_code in (401, 403)
    alumni = auth_header(login(client, MARIA, "Alumni@2026")["access_token"])
    assert client.get("/api/admin/badges", headers=alumni).status_code == 403
    assert client.post("/api/admin/badges", headers=alumni, json={"name": "Nope"}).status_code == 403
    listed = client.get("/api/admin/badges", headers=_admin(client))
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert [row["key"] for row in payload["items"] if row["is_system"]] == list(CATALOG_KEYS)


def test_add_edit_and_award_custom_badge(client, db_session):
    headers = _admin(client)
    created = client.post("/api/admin/badges", headers=headers, json={
        "name": "Survey Star",
        "description": "Submitted the Graduate Tracer Survey.",
        "locked_description": "Submit the Graduate Tracer Survey to earn this badge.",
        "icon": "star",
        "category": "recognition",
        "criteria_type": "tracer_completed",
        "active": True,
    })
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    key = item["key"]
    try:
        duplicate = client.post("/api/admin/badges", headers=headers, json={
            "name": "survey star",
            "description": "Another one.",
            "locked_description": "Not allowed.",
            "icon": "check",
            "category": "recognition",
            "criteria_type": "profile_complete",
            "active": True,
        })
        assert duplicate.status_code == 400
        blank = client.post("/api/admin/badges", headers=headers, json={
            "name": "",
            "description": "",
            "locked_description": "",
            "criteria_type": "not-a-rule",
        })
        assert blank.status_code == 400

        edited = client.put(f"/api/admin/badges/{item['id']}", headers=headers, json={
            "name": "Survey Star",
            "description": "The tracer survey is on file.",
            "locked_description": "Submit the Graduate Tracer Survey to earn this badge.",
            "icon": "clipboard",
            "category": "recognition",
            "criteria_type": "tracer_completed",
            "active": True,
        })
        assert edited.status_code == 200, edited.text
        assert edited.json()["item"]["description"] == "The tracer survey is on file."

        alumni = auth_header(login(client, MARIA, "Alumni@2026")["access_token"])
        achievements = client.get("/api/alumni/achievements", headers=alumni)
        assert achievements.status_code == 200, achievements.text
        match = next(row for row in achievements.json()["achievements"] if row["key"] == key)
        assert match["earned"] is True
        assert match["name"] == "Survey Star"
        assert match["description"] == "The tracer survey is on file."
        assert match["icon"] == "clipboard"
    finally:
        _cleanup(db_session, key)


def test_inactive_badge_is_not_newly_awarded_and_earned_badges_stay(client, db_session):
    headers = _admin(client)
    created = client.post("/api/admin/badges", headers=headers, json={
        "name": "Quiet Honor",
        "description": "A paused badge.",
        "locked_description": "This rule is paused.",
        "icon": "check",
        "category": "recognition",
        "criteria_type": "tracer_completed",
        "active": False,
    })
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    try:
        alumni = auth_header(login(client, MARIA, "Alumni@2026")["access_token"])
        hidden = client.get("/api/alumni/achievements", headers=alumni).json()
        assert all(row["key"] != item["key"] for row in hidden["achievements"])
        assert db_session.query(AlumniBadge).filter(AlumniBadge.badge_key == item["key"]).count() == 0

        turned_on = client.post(f"/api/admin/badges/{item['id']}/toggle", headers=headers)
        assert turned_on.status_code == 200
        earned = client.get("/api/alumni/achievements", headers=alumni).json()
        assert any(row["key"] == item["key"] and row["earned"] for row in earned["achievements"])

        paused = client.post(f"/api/admin/badges/{item['id']}/toggle", headers=headers)
        assert paused.json()["item"]["active"] is False
        still_there = client.get("/api/alumni/achievements", headers=alumni).json()
        kept = next(row for row in still_there["achievements"] if row["key"] == item["key"])
        assert kept["earned"] is True

        blocked = client.delete(f"/api/admin/badges/{item['id']}", headers=headers)
        assert blocked.status_code == 200, blocked.text
        assert blocked.json()["removed"] is False
        assert blocked.json()["deactivated"] is True
        assert db_session.query(BadgeDefinition).filter(BadgeDefinition.key == item["key"]).one().active is False
        assert db_session.query(AlumniBadge).filter(AlumniBadge.badge_key == item["key"]).count() >= 1
    finally:
        _cleanup(db_session, item["key"])


def test_unused_custom_badge_can_be_deleted_and_system_badges_cannot(client, db_session):
    headers = _admin(client)
    created = client.post("/api/admin/badges", headers=headers, json={
        "name": "Temporary Mark",
        "description": "Not awarded yet.",
        "locked_description": "Claim the alumni card.",
        "icon": "id-card",
        "category": "recognition",
        "criteria_type": "alumni_card_holder",
        "active": False,
    })
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    removed = client.delete(f"/api/admin/badges/{item['id']}", headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["removed"] is True
    assert db_session.query(BadgeDefinition).filter(BadgeDefinition.id == item["id"]).count() == 0

    catalog = client.get("/api/admin/badges", headers=headers).json()
    system = next(row for row in catalog["items"] if row["key"] == "profile_complete")
    try:
        blocked = client.delete(f"/api/admin/badges/{system['id']}", headers=headers)
        assert blocked.status_code == 200, blocked.text
        assert blocked.json()["deactivated"] is True
        db_session.expire_all()
        stored = db_session.query(BadgeDefinition).filter(BadgeDefinition.key == "profile_complete").one()
        assert stored.active is False
    finally:
        db_session.expire_all()
        stored = db_session.query(BadgeDefinition).filter(BadgeDefinition.key == "profile_complete").one()
        stored.active = True
        db_session.commit()
