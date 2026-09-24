"""Campus-local time helpers for reminder scheduling. Never logs secrets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import get_settings

MANILA_OFFSET = timezone(timedelta(hours=8))


def campus_tz():
    name = (get_settings().email_timezone or "Asia/Manila").strip() or "Asia/Manila"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, Exception):
        if name in {"Asia/Manila", "Asia/Hong_Kong", "Asia/Singapore"}:
            return MANILA_OFFSET
        return timezone.utc


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return now_utc().astimezone(campus_tz())


def aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
