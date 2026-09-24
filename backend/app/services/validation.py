import re
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Account, Resume
from app.services.employment import resolve_current_employment

EMAIL_HINT = "Please enter a valid email address."
PASSWORD_HINT = "Password must be at least 8 characters and include letters and numbers."


def normalize_email(value: str) -> str:
    try:
        result = validate_email(str(value or "").strip(), check_deliverability=False)
        return result.normalized.lower()
    except EmailNotValidError as exc:
        raise HTTPException(status_code=400, detail=EMAIL_HINT) from exc


def validate_password_strength(password: str) -> None:
    value = str(password or "")
    if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise HTTPException(status_code=400, detail=PASSWORD_HINT)


def normalize_skills(skills: Any) -> list[str]:
    if isinstance(skills, str):
        parts = skills.split(",")
    elif isinstance(skills, list):
        parts = skills
    else:
        parts = []
    seen: set[str] = set()
    result: list[str] = []
    for item in parts:
        raw = " ".join(str(item or "").split()).strip()
        if not raw:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(raw[:120])
    return result


def existing_account_message(account: Account) -> str:
    if account.status == "Pending":
        return "An account with this email is already awaiting review. Please sign in to check your status."
    if account.status == "Rejected":
        return "An account with this email already exists. Please sign in or contact the Alumni Office."
    return "An account with this email already exists."


def student_id_in_use(db: Session, student_id: Optional[str], exclude_account_id: Optional[int] = None) -> Optional[Account]:
    if not student_id:
        return None
    query = db.query(Account).filter(Account.linked_student_id == student_id)
    if exclude_account_id is not None:
        query = query.filter(Account.id != exclude_account_id)
    return query.first()


def require_owned_resume(db: Session, account_id: int, resume_id: Optional[int]) -> Optional[int]:
    if resume_id in (None, "", 0):
        return None
    try:
        rid = int(resume_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid resume reference.") from exc
    row = db.get(Resume, rid)
    if not row or row.account_id != account_id:
        raise HTTPException(status_code=400, detail="The selected resume does not belong to this account.")
    return rid


def validate_employed_job_title(survey: dict[str, Any]) -> None:
    if survey.get("is_currently_employed") != "Yes":
        return
    current = resolve_current_employment(survey)
    if current.occupation:
        return
    if current.present_is_first:
        raise HTTPException(
            status_code=400,
            detail="Please enter your job title. Alignment cannot be computed without an occupation.",
        )
    raise HTTPException(
        status_code=400,
        detail="Please enter your present job title. Alignment cannot be computed without an occupation.",
    )


def csv_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return f"'{text}"
    return text


def sanitize_http_url(value: str, *, strict: bool = False) -> str:
    """Allow only http(s) URLs. Reject javascript:, data:, and credentialed URLs."""
    raw = " ".join(str(value or "").split()).strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme:
        parsed = urlparse(f"https://{raw}")
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        if strict:
            raise HTTPException(status_code=400, detail="Website must be an http or https URL.")
        return ""
    cleaned = urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return cleaned[:500]


def sanitize_alumni_path(value: str) -> str:
    """Allow in-app alumni routes only. Blocks protocol-relative and traversal paths."""
    raw = str(value or "").strip()
    if not raw.startswith("/alumni"):
        return ""
    if raw.startswith("//") or "\\" in raw or ".." in raw:
        return ""
    path_only = raw.split("#", 1)[0].split("?", 1)[0]
    if ":" in path_only:
        return ""
    return raw[:200]
