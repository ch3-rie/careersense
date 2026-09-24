"""Central CareerSense alumni achievement catalog and evaluation.

Badges recognize meaningful record milestones. They are not a game: there are
no points, XP, levels, leaderboards, streaks, or rewards.

Evaluation reads authoritative CareerSense data (profile completion, submitted
GTS, resolve_current_employment, AAC status, owned resume attached to a
submitted tracer). Parser output is never treated as verified information.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, AlumniBadge, AlumniNotification

logger = logging.getLogger("careersense")

PROFILE_COMPLETE_KEY = "profile_complete"
RESUME_READY_KEY = "resume_ready"
TRACER_COMPLETED_KEY = "tracer_completed"
CAREER_UPDATED_KEY = "career_updated"
ALUMNI_CARD_HOLDER_KEY = "alumni_card_holder"
CAREERSENSE_ALUMNI_KEY = "careersense_alumni"

PROFILE_COMPLETE_ALIASES = (PROFILE_COMPLETE_KEY, "record_complete")

CORE_ACHIEVEMENT_KEYS = (
    PROFILE_COMPLETE_KEY,
    RESUME_READY_KEY,
    TRACER_COMPLETED_KEY,
    CAREER_UPDATED_KEY,
    ALUMNI_CARD_HOLDER_KEY,
)
MILESTONE_KEY = CAREERSENSE_ALUMNI_KEY
CATALOG_KEYS = CORE_ACHIEVEMENT_KEYS + (MILESTONE_KEY,)

NOTIFICATION_TITLE = "Achievement unlocked"
NOTIFICATION_CATEGORY = "achievement"

# Reserved for later cycles without changing persistence:
# lifelong_learner, perks_explorer, tracer_updated
FUTURE_ACHIEVEMENT_KEYS = ("lifelong_learner", "perks_explorer", "tracer_updated")

ACHIEVEMENTS: dict[str, dict[str, Any]] = {
    PROFILE_COMPLETE_KEY: {
        "key": PROFILE_COMPLETE_KEY,
        "name": "Profile Complete",
        "description": "All applicable alumni information has been completed.",
        "locked_description": "Complete all applicable alumni information to earn this achievement.",
        "icon": "check",
        "category": "core",
        "route": "/alumni",
        "cta": "Complete Profile",
        "cta_edit": True,
    },
    RESUME_READY_KEY: {
        "key": RESUME_READY_KEY,
        "name": "Resume Ready",
        "description": "Your resume information has been reviewed and verified.",
        "locked_description": (
            "Upload a resume, review the extracted information, and submit the "
            "Graduate Tracer Survey to earn this achievement."
        ),
        "icon": "file",
        "category": "core",
        "route": "/alumni/resume",
        "cta": "Review resume",
    },
    TRACER_COMPLETED_KEY: {
        "key": TRACER_COMPLETED_KEY,
        "name": "Tracer Completed",
        "description": "Your Graduate Tracer Survey has been successfully submitted.",
        "locked_description": (
            "Submit the current Graduate Tracer Survey with all required answers "
            "to earn this achievement."
        ),
        "icon": "clipboard",
        "category": "core",
        "route": "/alumni/resume",
        "cta": "Open tracer survey",
    },
    CAREER_UPDATED_KEY: {
        "key": CAREER_UPDATED_KEY,
        "name": "Career Updated",
        "description": "Your current employment information is up to date.",
        "locked_description": "Complete your current employment information to earn this achievement.",
        "icon": "briefcase",
        "category": "core",
        "route": "/alumni/resume",
        "cta": "Update Information",
    },
    ALUMNI_CARD_HOLDER_KEY: {
        "key": ALUMNI_CARD_HOLDER_KEY,
        "name": "Alumni Card Holder",
        "description": "Your official Angelenean Alumni Card has been claimed.",
        "locked_description": "Claim your official Angelenean Alumni Card to earn this achievement.",
        "icon": "id-card",
        "category": "core",
        "route": "/alumni/card",
        "cta": "Open Alumni Card",
    },
    CAREERSENSE_ALUMNI_KEY: {
        "key": CAREERSENSE_ALUMNI_KEY,
        "name": "CareerSense Alumni",
        "description": "Your CareerSense alumni profile and services are fully set up.",
        "locked_description": "Earn the five core CareerSense achievements to unlock this milestone.",
        "icon": "star",
        "category": "milestone",
        "route": "/alumni",
        "cta": "View achievements",
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _present(value: Any) -> bool:
    return bool(_text(value))


def _canonical_key(badge_key: str | None) -> str | None:
    key = _text(badge_key)
    if key in PROFILE_COMPLETE_ALIASES:
        return PROFILE_COMPLETE_KEY
    return key or None


def notification_link(key: str) -> str:
    return f"/alumni#achievement-{key}"


def catalog_entry(key: str) -> dict[str, Any]:
    return dict(ACHIEVEMENTS.get(key) or {})


def resume_extraction_usable(resume: Any | None) -> bool:
    """True when parser output can prefill a review — not when it is official."""
    if resume is None:
        return False
    parsed = getattr(resume, "parsed_json", None) or {}
    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, (list, dict)):
                if value:
                    return True
            elif _present(value):
                return True
    return bool(_text(getattr(resume, "extracted_text", "")))


def evaluate_profile_complete(snapshot: dict, progress: dict[str, Any]) -> bool:
    return bool(progress.get("is_complete")) and int(progress.get("percent") or 0) == 100


def evaluate_resume_ready(snapshot: dict, progress: dict[str, Any] | None = None) -> bool:
    if not snapshot.get("has_tracer") or not snapshot.get("tracer_required_ok"):
        return False
    if not snapshot.get("resume_id"):
        return False
    return bool(snapshot.get("resume_usable"))


def evaluate_tracer_completed(snapshot: dict, progress: dict[str, Any] | None = None) -> bool:
    return bool(snapshot.get("has_tracer") and snapshot.get("tracer_required_ok"))


def evaluate_career_updated(snapshot: dict, progress: dict[str, Any] | None = None) -> bool:
    """Current employment only. Unemployed or old jobs alone do not qualify."""
    if not snapshot.get("has_tracer") or not snapshot.get("tracer_required_ok"):
        return False
    if not snapshot.get("currently_employed"):
        return False
    return bool(
        _present(snapshot.get("occupation"))
        and _present(snapshot.get("employer"))
        and _present(snapshot.get("related"))
    )


def evaluate_alumni_card_holder(snapshot: dict, progress: dict[str, Any] | None = None) -> bool:
    return _text(snapshot.get("card_status")) == "Claimed"


def evaluate_careersense_alumni(earned_keys: Iterable[str]) -> bool:
    have = {_canonical_key(key) for key in earned_keys}
    return all(key in have for key in CORE_ACHIEVEMENT_KEYS)


def requirement_met(key: str, snapshot: dict, progress: dict[str, Any], earned_keys: Iterable[str]) -> bool:
    if key == PROFILE_COMPLETE_KEY:
        return evaluate_profile_complete(snapshot, progress)
    if key == RESUME_READY_KEY:
        return evaluate_resume_ready(snapshot, progress)
    if key == TRACER_COMPLETED_KEY:
        return evaluate_tracer_completed(snapshot, progress)
    if key == CAREER_UPDATED_KEY:
        return evaluate_career_updated(snapshot, progress)
    if key == ALUMNI_CARD_HOLDER_KEY:
        return evaluate_alumni_card_holder(snapshot, progress)
    if key == CAREERSENSE_ALUMNI_KEY:
        return evaluate_careersense_alumni(earned_keys)
    return False


def _award_metadata(key: str, snapshot: dict) -> dict[str, Any] | None:
    if key != TRACER_COMPLETED_KEY:
        return None
    label = _text(snapshot.get("survey_label")) or "Graduate Tracer Survey"
    payload: dict[str, Any] = {"survey_label": label}
    version = snapshot.get("survey_version")
    if version not in (None, ""):
        payload["survey_version"] = version
    return payload


def serialize_achievement(
    key: str,
    row: AlumniBadge | None,
    snapshot: dict | None = None,
    progress: dict[str, Any] | None = None,
    earned_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    definition = catalog_entry(key)
    snapshot = snapshot or {}
    progress = progress or {}
    earned = row is not None
    percent = int(progress.get("percent") or 0)
    metadata = None
    if row is not None:
        metadata = getattr(row, "award_metadata", None) or None
    if not metadata:
        metadata = _award_metadata(key, snapshot) if earned else None
    locked_hint = definition.get("locked_description") or ""
    if not earned and key == PROFILE_COMPLETE_KEY:
        locked_hint = f"Current progress: profile completion {percent}%."
    elif not earned and key == CAREERSENSE_ALUMNI_KEY:
        missing = [catalog_entry(item)["name"] for item in CORE_ACHIEVEMENT_KEYS if item not in set(earned_keys or [])]
        if missing:
            locked_hint = f"Earn {', '.join(missing)} to unlock this milestone."
    payload = {
        "key": key,
        "name": definition.get("name") or key,
        "title": definition.get("name") or key,
        "description": definition.get("description") or "",
        "locked_description": locked_hint,
        "icon": definition.get("icon") or "check",
        "category": definition.get("category") or "core",
        "earned": earned,
        "awarded": earned,
        "awarded_at": row.awarded_at if row else None,
        "route": definition.get("route") or "/alumni",
        "cta": definition.get("cta") or "Continue",
        "cta_edit": bool(definition.get("cta_edit")),
        "metadata": metadata,
    }
    if key == TRACER_COMPLETED_KEY and metadata and metadata.get("survey_label"):
        payload["detail"] = metadata["survey_label"]
    return payload


def next_achievement_hint(items: list[dict[str, Any]], progress: dict[str, Any]) -> dict[str, Any] | None:
    locked = next((row for row in items if not row.get("earned")), None)
    if locked is None:
        return {
            "key": None,
            "headline": "You're all set.",
            "detail": "Your CareerSense alumni profile is complete.",
            "route": "/alumni",
            "cta": None,
        }
    if locked["key"] == PROFILE_COMPLETE_KEY:
        missing = (progress.get("next_actions") or progress.get("missing_sections") or [])
        first = missing[0] if missing else {}
        detail = first.get("detail") or first.get("hint") or locked.get("locked_description")
        route = first.get("route") or locked.get("route") or "/alumni"
        return {
            "key": locked["key"],
            "headline": "You're almost there.",
            "detail": detail,
            "route": route,
            "cta": locked.get("cta") or "Complete Profile",
            "cta_edit": route in {"/alumni", "/alumni#contact"} or first.get("key") in {"contact", "identity", "photo"},
        }
    return {
        "key": locked["key"],
        "headline": "You're almost there.",
        "detail": locked.get("locked_description") or locked.get("description"),
        "route": locked.get("route") or "/alumni",
        "cta": locked.get("cta"),
        "cta_edit": bool(locked.get("cta_edit")),
    }


def serialize_catalog(
    progress: dict[str, Any],
    rows: Iterable[AlumniBadge],
    snapshot: dict | None = None,
) -> dict[str, Any]:
    by_key: dict[str, AlumniBadge] = {}
    for row in rows:
        key = _canonical_key(row.badge_key)
        if not key or key in by_key:
            continue
        by_key[key] = row
    earned_keys = set(by_key)
    items = [
        serialize_achievement(key, by_key.get(key), snapshot, progress, earned_keys)
        for key in CATALOG_KEYS
    ]
    profile_badge = next(item for item in items if item["key"] == PROFILE_COMPLETE_KEY)
    payload = dict(progress)
    payload["badge"] = profile_badge
    payload["badges"] = [profile_badge]
    payload["achievements"] = items
    payload["earned_count"] = sum(1 for item in items if item["earned"])
    payload["total_count"] = len(items)
    payload["next_achievement"] = next_achievement_hint(items, progress)
    payload["percentage"] = int(payload.get("percent") or 0)
    payload["is_complete"] = bool(payload.get("is_complete"))
    return payload


def load_badge_rows(db: Session, user: Account) -> list[AlumniBadge]:
    return (
        db.query(AlumniBadge)
        .filter(AlumniBadge.account_id == user.id)
        .order_by(AlumniBadge.awarded_at.asc())
        .all()
    )


def _notification_exists(db: Session, user: Account, key: str) -> bool:
    link = notification_link(key)
    name = catalog_entry(key).get("name") or key
    existing = (
        db.query(AlumniNotification)
        .filter(
            AlumniNotification.account_id == user.id,
            AlumniNotification.category == NOTIFICATION_CATEGORY,
        )
        .all()
    )
    for row in existing:
        if row.link == link:
            return True
        body = (row.body or "").lower()
        if f"you earned the {name.lower()} badge" in body:
            return True
        if key == PROFILE_COMPLETE_KEY and (row.title or "").strip().lower() == "profile complete":
            return True
    return False


def _notify(db: Session, user: Account, key: str) -> None:
    if _notification_exists(db, user, key):
        return
    definition = catalog_entry(key)
    name = definition.get("name") or key
    description = definition.get("description") or ""
    db.add(
        AlumniNotification(
            account_id=user.id,
            title=NOTIFICATION_TITLE,
            body=f"You earned the {name} badge.\n{description}",
            category=NOTIFICATION_CATEGORY,
            link=notification_link(key),
        )
    )


class AchievementService:
    """Single place that awards CareerSense achievements."""

    evaluate_profile_complete = staticmethod(evaluate_profile_complete)
    evaluate_resume_ready = staticmethod(evaluate_resume_ready)
    evaluate_tracer_completed = staticmethod(evaluate_tracer_completed)
    evaluate_career_updated = staticmethod(evaluate_career_updated)
    evaluate_alumni_card_holder = staticmethod(evaluate_alumni_card_holder)
    evaluate_careersense_alumni = staticmethod(evaluate_careersense_alumni)

    @staticmethod
    def serialize(progress: dict[str, Any], rows: Iterable[AlumniBadge], snapshot: dict | None = None) -> dict[str, Any]:
        return serialize_catalog(progress, rows, snapshot)

    @staticmethod
    def evaluate_all(
        db: Session,
        user: Account,
        snapshot: dict,
        progress: dict[str, Any],
        *,
        notify: bool = False,
    ) -> dict[str, Any]:
        rows = load_badge_rows(db, user)
        payload = serialize_catalog(progress, rows, snapshot)
        if user.role != "Alumni" or user.status != "Active":
            return payload

        earned = {_canonical_key(row.badge_key) for row in rows}
        pending: list[str] = []
        for key in CORE_ACHIEVEMENT_KEYS:
            if key in earned:
                continue
            if requirement_met(key, snapshot, progress, earned):
                pending.append(key)
                earned.add(key)
        if MILESTONE_KEY not in earned and evaluate_careersense_alumni(earned):
            pending.append(MILESTONE_KEY)
            earned.add(MILESTONE_KEY)
        if not pending:
            return payload

        awarded_at = _now()
        try:
            for key in pending:
                db.add(
                    AlumniBadge(
                        account_id=user.id,
                        badge_key=key,
                        awarded_at=awarded_at,
                        award_metadata=_award_metadata(key, snapshot),
                    )
                )
                if notify:
                    _notify(db, user, key)
            db.commit()
        except IntegrityError:
            logger.info("Achievement uniqueness blocked a duplicate award for account %s", user.id)
            try:
                db.rollback()
            except Exception:
                pass
        except Exception:
            logger.exception("Achievement evaluation failed for account %s", user.id)
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.refresh(user)
        except Exception:
            pass
        return serialize_catalog(progress, load_badge_rows(db, user), snapshot)
