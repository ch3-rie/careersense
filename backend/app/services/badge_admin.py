"""OAAPS badge catalog. Awarding still uses the CareerSense achievement rules."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AlumniBadge, BadgeDefinition
from app.services.achievements import ACHIEVEMENTS, CATALOG_KEYS, PROFILE_COMPLETE_ALIASES

ICONS = (
    ("check", "Check"),
    ("file", "Document"),
    ("clipboard", "Clipboard"),
    ("briefcase", "Briefcase"),
    ("id-card", "Alumni card"),
    ("star", "Star"),
)

CATEGORIES = (
    ("core", "Core"),
    ("milestone", "Milestone"),
    ("recognition", "Recognition"),
)

# These values are the only awarding rules the achievement engine evaluates.
CRITERIA = {
    "profile_complete": {
        "label": "Profile is complete",
        "detail": "Awarded when every applicable profile section is complete.",
        "route": "/alumni",
        "cta": "Complete Profile",
        "cta_edit": True,
    },
    "resume_ready": {
        "label": "Resume is ready",
        "detail": "Awarded when a resume is on file and the Graduate Tracer Survey has been submitted.",
        "route": "/alumni/resume",
        "cta": "Review resume",
        "cta_edit": False,
    },
    "tracer_completed": {
        "label": "Tracer survey is submitted",
        "detail": "Awarded when the current Graduate Tracer Survey is submitted with the required answers.",
        "route": "/alumni/resume",
        "cta": "Open tracer survey",
        "cta_edit": False,
    },
    "career_updated": {
        "label": "Current employment is on file",
        "detail": "Awarded when current occupation, employer, and degree alignment are recorded.",
        "route": "/alumni/resume",
        "cta": "Update Information",
        "cta_edit": False,
    },
    "alumni_card_holder": {
        "label": "Alumni card is claimed",
        "detail": "Awarded when the official Angelenean Alumni Card status is Claimed.",
        "route": "/alumni/card",
        "cta": "Open Alumni Card",
        "cta_edit": False,
    },
    "careersense_alumni": {
        "label": "All five core badges",
        "detail": "Awarded when Profile Complete, Resume Ready, Tracer Completed, Career Updated, and Alumni Card Holder have all been earned.",
        "route": "/alumni#alumni-badges",
        "cta": "Open Alumni Badge Achievements",
        "cta_edit": False,
    },
}

ICON_VALUES = {key for key, _label in ICONS}
CATEGORY_VALUES = {key for key, _label in CATEGORIES}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value) -> str:
    return str(value or "").strip()


def criteria_options() -> list[dict]:
    return [{"value": key, "label": spec["label"], "detail": spec["detail"]} for key, spec in CRITERIA.items()]


def icon_options() -> list[dict]:
    return [{"value": key, "label": label} for key, label in ICONS]


def category_options() -> list[dict]:
    return [{"value": key, "label": label} for key, label in CATEGORIES]


def _system_row(key: str, index: int) -> BadgeDefinition:
    spec = ACHIEVEMENTS[key]
    rule = CRITERIA[key]
    return BadgeDefinition(
        key=key,
        name=spec["name"],
        description=spec["description"],
        locked_description=spec["locked_description"],
        icon=spec["icon"],
        category=spec["category"],
        criteria_type=key,
        route=spec.get("route") or rule["route"],
        cta=spec.get("cta") or rule["cta"],
        cta_edit=bool(spec.get("cta_edit")),
        active=True,
        is_system=True,
        sort_order=(index + 1) * 10,
        created_at=_now(),
        updated_at=_now(),
    )


def ensure_system_badges(db: Session, *, commit: bool = False) -> None:
    """Insert the built-in catalog once. Later admin edits are left in place."""
    existing = {row.key for row in db.query(BadgeDefinition.key).all()}
    added = False
    for index, key in enumerate(CATALOG_KEYS):
        if key in existing:
            continue
        db.add(_system_row(key, index))
        added = True
    if not added:
        return
    if commit:
        db.commit()
    else:
        db.flush()


def _counts(db: Session) -> dict[str, int]:
    rows = db.query(AlumniBadge.badge_key, func.count(AlumniBadge.id)).group_by(AlumniBadge.badge_key).all()
    counts = {key: count for key, count in rows}
    alias_total = sum(counts.get(key, 0) for key in PROFILE_COMPLETE_ALIASES)
    if alias_total:
        counts["profile_complete"] = alias_total
    return counts


def serialize_definition(row: BadgeDefinition, earned_count: int = 0) -> dict:
    rule = CRITERIA.get(row.criteria_type) or {}
    can_delete = not row.is_system and earned_count == 0
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "description": row.description or "",
        "locked_description": row.locked_description or "",
        "icon": row.icon or "check",
        "category": row.category or "recognition",
        "category_label": dict(CATEGORIES).get(row.category, row.category or ""),
        "criteria_type": row.criteria_type,
        "criteria_label": rule.get("label") or row.criteria_type,
        "criteria_detail": rule.get("detail") or "",
        "criteria_locked": bool(row.is_system),
        "route": row.route or "/alumni",
        "cta": row.cta or "Continue",
        "cta_edit": bool(row.cta_edit),
        "active": bool(row.active),
        "status": "Active" if row.active else "Inactive",
        "is_system": bool(row.is_system),
        "earned_count": earned_count,
        "can_delete": can_delete,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def as_catalog_dict(row: BadgeDefinition) -> dict:
    """Shape consumed by the alumni achievement serializer."""
    return {
        "key": row.key,
        "name": row.name,
        "description": row.description or "",
        "locked_description": row.locked_description or "",
        "icon": row.icon or "check",
        "category": row.category or "core",
        "route": row.route or "/alumni",
        "cta": row.cta or "Continue",
        "cta_edit": bool(row.cta_edit),
        "criteria_type": row.criteria_type or row.key,
        "active": bool(row.active),
    }


def load_definition_dicts(db: Session) -> list[dict]:
    ensure_system_badges(db, commit=False)
    rows = db.query(BadgeDefinition).order_by(BadgeDefinition.sort_order.asc(), BadgeDefinition.id.asc()).all()
    return [as_catalog_dict(row) for row in rows]


def visible_definition_dicts(db: Session, earned_keys: set[str]) -> list[dict]:
    return [row for row in load_definition_dicts(db) if row["active"] or row["key"] in earned_keys]


def list_badges(db: Session) -> dict:
    ensure_system_badges(db, commit=False)
    counts = _counts(db)
    rows = db.query(BadgeDefinition).order_by(BadgeDefinition.sort_order.asc(), BadgeDefinition.name.asc()).all()
    items = [serialize_definition(row, counts.get(row.key, 0)) for row in rows]
    return {
        "items": items,
        "total": len(items),
        "active": sum(1 for row in items if row["active"]),
        "inactive": sum(1 for row in items if not row["active"]),
        "criteria": criteria_options(),
        "icons": icon_options(),
        "categories": category_options(),
    }


def _slug(name: str, db: Session) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60] or "badge"
    if base in CATALOG_KEYS:
        base = f"custom_{base}"[:70]
    candidate = base
    suffix = 2
    while db.query(BadgeDefinition).filter(BadgeDefinition.key == candidate).first():
        candidate = f"{base[:70]}_{suffix}"
        suffix += 1
    return candidate


def _unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    query = db.query(BadgeDefinition).filter(func.lower(BadgeDefinition.name) == name.lower())
    if exclude_id is not None:
        query = query.filter(BadgeDefinition.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail="A badge with this name already exists.")


def _clean_payload(data: dict, *, partial_system: bool = False) -> dict:
    name = _text(data.get("name"))
    description = _text(data.get("description"))
    requirement = _text(data.get("locked_description"))
    icon = _text(data.get("icon")) or "check"
    category = _text(data.get("category")) or "recognition"
    criteria_type = _text(data.get("criteria_type"))
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Badge name is required.")
    if len(name) > 120:
        raise HTTPException(status_code=400, detail="Badge name must be 120 characters or fewer.")
    if len(description) < 2:
        raise HTTPException(status_code=400, detail="Badge description is required.")
    if len(requirement) < 2:
        raise HTTPException(status_code=400, detail="Awarding requirements are required.")
    if icon not in ICON_VALUES:
        raise HTTPException(status_code=400, detail="Choose a badge icon from the list.")
    if category not in CATEGORY_VALUES:
        raise HTTPException(status_code=400, detail="Choose a badge category from the list.")
    if not partial_system and criteria_type not in CRITERIA:
        raise HTTPException(status_code=400, detail="Choose an awarding rule CareerSense can check.")
    return {
        "name": name,
        "description": description,
        "locked_description": requirement,
        "icon": icon,
        "category": category,
        "criteria_type": criteria_type,
        "active": bool(data.get("active", True)),
    }


def create_badge(db: Session, data: dict) -> BadgeDefinition:
    ensure_system_badges(db, commit=False)
    cleaned = _clean_payload(data)
    _unique_name(db, cleaned["name"])
    rule = CRITERIA[cleaned["criteria_type"]]
    row = BadgeDefinition(
        key=_slug(cleaned["name"], db),
        name=cleaned["name"],
        description=cleaned["description"],
        locked_description=cleaned["locked_description"],
        icon=cleaned["icon"],
        category=cleaned["category"],
        criteria_type=cleaned["criteria_type"],
        route=rule["route"],
        cta=rule["cta"],
        cta_edit=bool(rule["cta_edit"]),
        active=cleaned["active"],
        is_system=False,
        sort_order=1000 + db.query(func.count(BadgeDefinition.id)).scalar(),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    return row


def update_badge(db: Session, row: BadgeDefinition, data: dict) -> BadgeDefinition:
    cleaned = _clean_payload(data, partial_system=row.is_system)
    _unique_name(db, cleaned["name"], exclude_id=row.id)
    if row.is_system and cleaned["criteria_type"] and cleaned["criteria_type"] != row.criteria_type:
        raise HTTPException(status_code=400, detail="The awarding rule for this CareerSense badge is fixed.")
    row.name = cleaned["name"]
    row.description = cleaned["description"]
    row.locked_description = cleaned["locked_description"]
    row.icon = cleaned["icon"]
    row.category = cleaned["category"]
    row.active = cleaned["active"]
    row.updated_at = _now()
    if not row.is_system:
        rule = CRITERIA[cleaned["criteria_type"]]
        row.criteria_type = cleaned["criteria_type"]
        row.route = rule["route"]
        row.cta = rule["cta"]
        row.cta_edit = bool(rule["cta_edit"])
    return row


def remove_badge(db: Session, row: BadgeDefinition) -> dict:
    earned = _counts(db).get(row.key, 0)
    if row.is_system or earned:
        row.active = False
        row.updated_at = _now()
        if row.is_system:
            message = (
                f"{row.name} is a CareerSense badge, so it was deactivated instead of deleted. "
                "Alumni who already earned it keep the badge, and it will not be awarded again."
            )
        else:
            message = (
                f"{row.name} has been earned by {earned} alumni, so it was deactivated instead of deleted. "
                "Those alumni keep the badge, and it will not be awarded again."
            )
        return {"removed": False, "deactivated": True, "message": message}
    name = row.name
    db.delete(row)
    return {"removed": True, "deactivated": False, "message": f"{name} was removed."}
