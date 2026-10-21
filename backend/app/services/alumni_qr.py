"""Stable alumni QR codes. The code carries a signed identifier, not personal data."""

from __future__ import annotations

import hashlib
import hmac
import re

import qrcode
import qrcode.image.svg
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Account
from app.services.email.service import app_url

_TOKEN_RE = re.compile(r"^v1\.(\d+)\.([0-9a-f]{64})$")


ALUMNI_OFFICE_LOCATION = "Room 307, 3rd Floor, Angeles Hall, Angeles City, Philippines, 2009"
ALUMNI_OFFICE_PHONE = "(045) 625 2888"
ALUMNI_OFFICE_EMAIL = "alumni@auf.edu.ph"
ALUMNI_OFFICE_TIMEZONE = "Asia/Manila"
ALUMNI_OFFICE_SCHEDULE = [
    {"day": "Monday", "opens": "08:00", "closes": "17:00"},
    {"day": "Tuesday", "opens": "08:00", "closes": "17:00"},
    {"day": "Wednesday", "opens": "08:00", "closes": "17:00"},
    {"day": "Thursday", "opens": "08:00", "closes": "17:00"},
    {"day": "Friday", "opens": "08:00", "closes": "17:00"},
    {"day": "Saturday", "closed": True},
    {"day": "Sunday", "closed": True},
]


def office_contact() -> dict:
    settings = get_settings()
    return {
        "name": "Alumni Office",
        "email": (settings.oaaps_email or "").strip() or ALUMNI_OFFICE_EMAIL,
        "phone": (settings.oaaps_phone or "").strip() or ALUMNI_OFFICE_PHONE,
        "hours": (settings.oaaps_hours or "").strip() or "Monday–Friday, 08:00–17:00",
        "location": ALUMNI_OFFICE_LOCATION,
        "timezone": ALUMNI_OFFICE_TIMEZONE,
        "schedule": ALUMNI_OFFICE_SCHEDULE,
    }


def alumni_qr_token(account_id: int) -> str:
    settings = get_settings()
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"alumni-qr:v1:{int(account_id)}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"v1.{int(account_id)}.{digest}"


def account_id_from_token(token: str) -> int | None:
    match = _TOKEN_RE.fullmatch((token or "").strip())
    if match is None:
        return None
    account_id = int(match.group(1))
    expected = alumni_qr_token(account_id).rsplit(".", 1)[-1]
    if not hmac.compare_digest(expected, match.group(2)):
        return None
    return account_id


def verify_url(account_id: int) -> str:
    return app_url(f"/verify/qr/{alumni_qr_token(account_id)}")


def qr_svg(payload: str) -> bytes:
    image = qrcode.make(
        payload,
        image_factory=qrcode.image.svg.SvgPathImage,
        border=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    raw = image.to_string()
    return raw.encode("utf-8") if isinstance(raw, str) else raw


def _joined_name(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def alumni_qr_identity(user: Account) -> dict[str, str]:
    """University record wins. Profile values fill only fields the registry does not have."""
    record = user.university_record
    profile = user.profile
    if record is not None:
        name = _joined_name(record.first_name, record.middle_name, record.last_name)
        course = (record.degree or "").strip()
        college = (record.college or "").strip()
        year = (record.year_graduated or "").strip()
        student_number = (record.student_id or "").strip()
    else:
        name = ""
        course = ""
        college = ""
        year = ""
        student_number = (user.linked_student_id or "").strip()
    if profile is not None:
        if not name:
            name = _joined_name(profile.first_name, profile.middle_name, profile.last_name)
        if not course:
            course = (profile.degree or "").strip()
        if not year:
            year = (profile.year_graduated or "").strip()
    if not name:
        name = _joined_name(user.first_name, user.last_name)
    return {
        "student_number": student_number,
        "name": name,
        "course": course,
        "college": college,
        "year_graduated": year,
    }


def verified_alumni_for_token(db: Session, token: str) -> Account | None:
    account_id = account_id_from_token(token)
    if account_id is None:
        return None
    user = db.get(Account, account_id)
    if user is None or user.role != "Alumni" or user.status != "Active":
        return None
    return user
