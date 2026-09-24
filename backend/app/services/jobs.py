"""Alumni employment timeline — stored separately from GTS JSON."""

from __future__ import annotations

import re
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models import Account, AlumniJob, Resume, TracerSubmission
from app.schemas import JobIn
from app.services.employment import resolve_current_employment


def job_duration(start: date | None, end: date | None, is_current: bool) -> str:
    if not start:
        return ""
    finish = date.today() if is_current or not end else end
    if finish < start:
        return ""
    months = (finish.year - start.year) * 12 + (finish.month - start.month)
    if finish.day < start.day:
        months -= 1
    months = max(months, 0)
    years, leftover = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if leftover:
        parts.append(f"{leftover} month{'s' if leftover != 1 else ''}")
    return " ".join(parts) or "Less than a month"


def serialize_job(row: AlumniJob) -> dict:
    return {
        "id": row.id,
        "job_title": row.job_title,
        "company": row.company,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "is_current": bool(row.is_current),
        "industry": row.industry or "",
        "location": row.location or "",
        "description": row.description or "",
        "duration": job_duration(row.start_date, row.end_date, bool(row.is_current)),
    }


def _query_jobs(db: Session, account_id: int) -> list[AlumniJob]:
    return (
        db.query(AlumniJob)
        .filter(AlumniJob.account_id == account_id)
        .order_by(
            case((AlumniJob.start_date.is_(None), 0), else_=1),
            AlumniJob.start_date.asc(),
            AlumniJob.id.asc(),
        )
        .all()
    )


def serialize_jobs(db: Session, account_id: int) -> list[dict]:
    return [serialize_job(row) for row in _query_jobs(db, account_id)]


def parse_job_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or re.search(r"\b(present|current)\b", text, re.I):
        return None
    for fmt, size in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            return datetime.strptime(text[:size], fmt).date()
        except ValueError:
            continue
    return None


def _truthy_current(value) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def _jobs_from_resume(db: Session, account_id: int) -> list[dict]:
    resumes = (
        db.query(Resume)
        .filter(Resume.account_id == account_id)
        .order_by(Resume.created_at.desc())
        .all()
    )
    for resume in resumes:
        experiences = (resume.parsed_json or {}).get("experiences") or []
        rows = []
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            title = str(exp.get("job_title") or "").strip()
            company = str(exp.get("employer") or "").strip()
            if not title and not company:
                continue
            is_current = _truthy_current(exp.get("is_current"))
            rows.append(
                {
                    "job_title": title or "Untitled role",
                    "company": company or "Not specified",
                    "start_date": parse_job_date(exp.get("start_date")),
                    "end_date": None if is_current else parse_job_date(exp.get("end_date")),
                    "is_current": is_current,
                    "description": str(exp.get("description") or "").strip()[:800],
                }
            )
        if rows:
            return rows
    return []


def _jobs_from_gts(data: dict) -> list[dict]:
    current = resolve_current_employment(data)
    first_title = current.first_occupation
    first_company = current.first_employer
    present_title = current.occupation if not current.present_is_first else ""
    present_company = current.employer if not current.present_is_first else ""

    jobs: list[dict] = []
    if first_title or first_company:
        jobs.append(
            {
                "job_title": first_title or "Untitled role",
                "company": first_company or "Not specified",
                "start_date": None,
                "end_date": None,
                "is_current": current.currently_employed and current.present_is_first,
            }
        )
    same_as_first = present_title == first_title and present_company == first_company
    if current.currently_employed and not current.present_is_first and (present_title or present_company) and not same_as_first:
        jobs.append(
            {
                "job_title": present_title or "Untitled role",
                "company": present_company or "Not specified",
                "start_date": None,
                "end_date": None,
                "is_current": True,
            }
        )
    return jobs


def _mark_ready(user: Account) -> None:
    if user.profile is not None:
        user.profile.job_timeline_ready = True


def sync_job_timeline_from_gts(db: Session, user: Account, data: dict) -> None:
    """Keep GTS-derived stubs in sync after an official tracer save.

    Dated jobs the graduate edited on the timeline are left alone.
    """
    desired = _jobs_from_gts(data or {})
    existing = _query_jobs(db, user.id)
    auto_rows = [row for row in existing if row.start_date is None and row.end_date is None]
    manual_rows = [row for row in existing if row not in auto_rows]
    if manual_rows:
        _mark_ready(user)
        return
    for row in existing:
        db.delete(row)
    db.flush()
    for item in desired:
        db.add(AlumniJob(account_id=user.id, **item))
    _mark_ready(user)


def ensure_job_timeline(db: Session, user: Account) -> list[dict]:
    profile = user.profile
    if profile is not None and not profile.job_timeline_ready:
        latest = (
            db.query(TracerSubmission)
            .filter(TracerSubmission.account_id == user.id)
            .order_by(TracerSubmission.submitted_at.desc())
            .first()
        )
        imported = _jobs_from_gts(latest.data_json or {}) if latest else []
        if not imported:
            imported = _jobs_from_resume(db, user.id)
        for item in imported:
            db.add(AlumniJob(account_id=user.id, **item))
        profile.job_timeline_ready = True
        db.commit()
    return serialize_jobs(db, user.id)


def _apply_payload(row: AlumniJob, payload: JobIn) -> None:
    title = payload.job_title.strip()
    company = payload.company.strip()
    if not title or not company:
        raise HTTPException(status_code=400, detail="Job title and company are required.")
    end = None if payload.is_current else payload.end_date
    if payload.start_date and end and end < payload.start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after the start date.")
    row.job_title = title
    row.company = company
    row.start_date = payload.start_date
    row.end_date = end
    row.is_current = bool(payload.is_current)
    row.industry = (payload.industry or "").strip()
    row.location = (payload.location or "").strip()
    row.description = (payload.description or "").strip()[:800]


def _owned_job(db: Session, user: Account, job_id: int) -> AlumniJob:
    row = db.get(AlumniJob, job_id)
    if not row or row.account_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return row


def create_job(db: Session, user: Account, payload: JobIn) -> list[dict]:
    row = AlumniJob(account_id=user.id, job_title="", company="")
    _apply_payload(row, payload)
    db.add(row)
    _mark_ready(user)
    db.commit()
    return serialize_jobs(db, user.id)


def update_job(db: Session, user: Account, job_id: int, payload: JobIn) -> list[dict]:
    row = _owned_job(db, user, job_id)
    _apply_payload(row, payload)
    _mark_ready(user)
    db.commit()
    return serialize_jobs(db, user.id)


def delete_job(db: Session, user: Account, job_id: int) -> list[dict]:
    row = _owned_job(db, user, job_id)
    db.delete(row)
    _mark_ready(user)
    db.commit()
    return serialize_jobs(db, user.id)
