from io import BytesIO
from pathlib import Path

from PIL import Image

from app.models import AlumniBadge, BadgeDefinition
from app.services.achievements import CATALOG_KEYS
from app.services.files import unlink_contained_file
from tests.conftest import auth_header, login

MARIA = "maria.reyes@gmail.com"


def _admin(client):
    return auth_header(login(client, "admin@auf.edu.ph", "Admin@AUF2026")["access_token"])


def _cleanup(db_session, key: str) -> None:
    row = db_session.query(BadgeDefinition).filter(BadgeDefinition.key == key).one_or_none()
    stored = row.image_path if row else ""
    db_session.query(AlumniBadge).filter(AlumniBadge.badge_key == key).delete(synchronize_session=False)
    db_session.query(BadgeDefinition).filter(BadgeDefinition.key == key).delete(synchronize_session=False)
    db_session.commit()
    if stored:
        unlink_contained_file(stored)


def _image(fmt: str, width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (18, 46, 89)).save(buffer, format=fmt)
    return buffer.getvalue()


def test_badge_management_is_admin_only(client):
    assert client.get("/api/admin/badges").status_code in (401, 403)
    alumni = auth_header(login(client, MARIA, "Alumni@2026")["access_token"])
    assert client.get("/api/admin/badges", headers=alumni).status_code == 403
    assert client.post("/api/admin/badges", headers=alumni, json={"name": "Nope"}).status_code == 403
    listed = client.get("/api/admin/badges", headers=_admin(client))
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert [row["key"] for row in payload["items"] if row["is_system"]] == list(CATALOG_KEYS)
    assert all(row["has_image"] is False and row["image_url"] is None for row in payload["items"])


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


def _badge_payload(name, **extra):
    payload = {
        "name": name,
        "description": "A custom seal for this badge.",
        "locked_description": "Submit the Graduate Tracer Survey to earn this badge.",
        "icon": "star",
        "category": "recognition",
        "criteria_type": "tracer_completed",
        "active": True,
    }
    payload.update(extra)
    return payload


def test_badge_image_is_optional_and_icon_badges_stay_intact(client, db_session):
    headers = _admin(client)
    created = client.post("/api/admin/badges", headers=headers, json=_badge_payload("Icon Only Seal"))
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    assert item["has_image"] is False
    assert item["image_url"] is None
    assert item["icon"] == "star"
    try:
        alumni = auth_header(login(client, MARIA, "Alumni@2026")["access_token"])
        listed = client.get("/api/alumni/achievements", headers=alumni)
        match = next(row for row in listed.json()["achievements"] if row["key"] == item["key"])
        assert match["icon"] == "star"
        assert match["image_url"] is None
    finally:
        _cleanup(db_session, item["key"])


def test_custom_badge_image_upload_validation_and_display(client, db_session):
    headers = _admin(client)
    created = client.post("/api/admin/badges", headers=headers, json=_badge_payload("Painted Seal", active=False))
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    image_url = f"/api/admin/badges/{item['id']}/image"
    try:
        uploaded = client.post(
            image_url,
            headers=headers,
            files={"image": ("seal.png", _image("PNG", 128, 128), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        saved = uploaded.json()["item"]
        assert saved["has_image"] is True
        assert saved["icon"] == "star"
        assert saved["image_url"] == image_url
        stored = db_session.query(BadgeDefinition).filter(BadgeDefinition.id == item["id"]).one()
        db_session.refresh(stored)
        assert stored.image_path
        assert Path(stored.image_path).is_file()
        previous = stored.image_path

        fetched = client.get(image_url, headers=headers)
        assert fetched.status_code == 200, fetched.text
        assert fetched.content.startswith(b"\x89PNG")

        alumni = auth_header(login(client, MARIA, "Alumni@2026")["access_token"])
        assert client.get(image_url, headers=alumni).status_code == 403
        hidden = client.get(f"/api/alumni/achievements/{item['key']}/image", headers=alumni)
        assert hidden.status_code == 404

        replaced = client.post(
            image_url,
            headers=headers,
            files={"image": ("seal.jpg", _image("JPEG", 80, 96), "image/jpeg")},
        )
        assert replaced.status_code == 200, replaced.text
        jpeg = client.get(image_url, headers=headers)
        assert jpeg.content.startswith(b"\xff\xd8\xff")
        assert not Path(previous).exists()

        webp = client.post(
            image_url,
            headers=headers,
            files={"image": ("seal.webp", _image("WEBP", 100, 100), "image/webp")},
        )
        assert webp.status_code == 200, webp.text
        assert client.get(image_url, headers=headers).headers["content-type"].startswith("image/webp")

        invalid = client.post(image_url, headers=headers, files={"image": ("notes.txt", b"not an image", "text/plain")})
        assert invalid.status_code == 400
        assert "JPG, PNG, or WebP" in invalid.json()["detail"]

        broken = client.post(
            image_url,
            headers=headers,
            files={"image": ("broken.png", b"\x89PNG\r\n\x1a\n" + b"not-a-png", "image/png")},
        )
        assert broken.status_code == 400
        assert broken.json()["detail"] == "The file is not a valid image."

        tiny = client.post(image_url, headers=headers, files={"image": ("tiny.png", _image("PNG", 16, 16), "image/png")})
        assert tiny.status_code == 400
        assert "64 and 2048" in tiny.json()["detail"]

        huge = client.post(image_url, headers=headers, files={"image": ("huge.png", _image("PNG", 2049, 64), "image/png")})
        assert huge.status_code == 400

        empty = client.post(image_url, headers=headers, files={"image": ("empty.png", b"", "image/png")})
        assert empty.status_code == 400
        assert empty.json()["detail"] == "The uploaded file is empty."

        bulky = _image("PNG", 64, 64) + (b"0" * (5 * 1024 * 1024))
        oversized = client.post(image_url, headers=headers, files={"image": ("big.png", bulky, "image/png")})
        assert oversized.status_code == 400
        assert oversized.json()["detail"] == "Image must be 5 MB or smaller."

        still = client.get(image_url, headers=headers)
        assert still.status_code == 200
        assert still.headers["content-type"].startswith("image/webp")

        turned_on = client.post(f"/api/admin/badges/{item['id']}/toggle", headers=headers)
        assert turned_on.status_code == 200
        achievements = client.get("/api/alumni/achievements", headers=alumni)
        match = next(row for row in achievements.json()["achievements"] if row["key"] == item["key"])
        assert match["icon"] == "star"
        assert match["image_url"] == f"/api/alumni/achievements/{item['key']}/image"
        seen = client.get(match["image_url"], headers=alumni)
        assert seen.status_code == 200
        assert seen.headers["content-type"].startswith("image/webp")

        paused = client.post(f"/api/admin/badges/{item['id']}/toggle", headers=headers)
        assert paused.json()["item"]["active"] is False
        kept = client.get(match["image_url"], headers=alumni)
        assert kept.status_code == 200

        cleared = client.delete(image_url, headers=headers)
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["item"]["has_image"] is False
        assert cleared.json()["item"]["icon"] == "star"
        assert client.get(image_url, headers=headers).status_code == 404
        after = client.get("/api/alumni/achievements", headers=alumni).json()
        restored = next(row for row in after["achievements"] if row["key"] == item["key"])
        assert restored["image_url"] is None
        assert restored["icon"] == "star"
    finally:
        _cleanup(db_session, item["key"])


def test_deleted_badge_removes_its_image_file(client, db_session):
    headers = _admin(client)
    created = client.post("/api/admin/badges", headers=headers, json=_badge_payload("Disposable Seal", active=False, criteria_type="alumni_card_holder", locked_description="Claim the alumni card."))
    assert created.status_code == 200, created.text
    item = created.json()["item"]
    uploaded = client.post(
        f"/api/admin/badges/{item['id']}/image",
        headers=headers,
        files={"image": ("seal.png", _image("PNG", 72, 72), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    stored = db_session.query(BadgeDefinition).filter(BadgeDefinition.id == item["id"]).one()
    db_session.refresh(stored)
    path = Path(stored.image_path)
    assert path.is_file()
    removed = client.delete(f"/api/admin/badges/{item['id']}", headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["removed"] is True
    assert "image_path" not in removed.json()
    assert not path.exists()
