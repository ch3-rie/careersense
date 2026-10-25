"""Alumni seminars, certifications, awards, and the no-employment explanation."""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import Account, AlumniAward, AlumniCertification, AlumniJob, AlumniProfile, AlumniSeminar, Resume, TracerSubmission
from app.schemas import AwardIn, CertificationIn, EmploymentStatusIn, SeminarIn
from app.services.employment import (
    apply_current_employment,
    unemployment_option,
    unemployment_public,
    unemployment_summary,
)
from app.services.files import save_certificate_file, unlink_contained_file
from app.services.jobs import serialize_jobs


def _clean(value: str, limit: int) -> str:
    return (value or "").strip()[:limit]


def normalize_when(value: str, *, required: bool, label: str) -> str:
    text = (value or "").strip()
    if not text:
        if required:
            raise HTTPException(status_code=400, detail=f"Enter the year or date for {label}.")
        return ""
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        if year < 1950 or year > date.today().year + 1:
            raise HTTPException(status_code=400, detail="Enter a valid year.")
        return text
    try:
        parsed = datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Enter a four-digit year, such as 2024, or a date in YYYY-MM-DD format.",
        ) from exc
    if parsed.year < 1950 or parsed > date.today():
        raise HTTPException(status_code=400, detail="Enter a date that is not in the future.")
    return parsed.isoformat()


def normalize_http_url(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if any(char.isspace() for char in text):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid http or https verification link, or leave it blank.",
        )
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or not host or "." not in host or parsed.username or parsed.password:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid http or https verification link, or leave it blank.",
        )
    if len(candidate) > 500:
        raise HTTPException(status_code=400, detail="Verification link must be 500 characters or fewer.")
    return candidate


def _sort_when(value: str, row_id: int) -> tuple:
    return (value or "", row_id)


def serialize_seminar(row: AlumniSeminar) -> dict:
    return {
        "id": row.id,
        "title": row.title or "",
        "location": row.location or "",
        "held_on": row.held_on or "",
        "organizer": row.organizer or "",
    }


def serialize_seminars(db: Session, account_id: int) -> list[dict]:
    rows = db.query(AlumniSeminar).filter(AlumniSeminar.account_id == account_id).all()
    rows.sort(key=lambda row: _sort_when(row.held_on, row.id), reverse=True)
    return [serialize_seminar(row) for row in rows]


def _awarded_label(row: AlumniCertification) -> str:
    if row.awarded_on:
        return row.awarded_on
    if row.date_issued:
        return row.date_issued.isoformat()
    return ""


def serialize_certification(row: AlumniCertification) -> dict:
    return {
        "id": row.id,
        "name": row.certification_name or "",
        "awarded_on": _awarded_label(row),
        "awarding_body": row.issuing_organization or "",
        "verification_url": row.verification_url or "",
        "has_certificate": bool(row.certificate_path),
        "certificate_filename": row.certificate_filename or "",
        "certificate_mime": row.certificate_mime or "",
    }


def serialize_certifications(db: Session, account_id: int) -> list[dict]:
    rows = db.query(AlumniCertification).filter(AlumniCertification.account_id == account_id).all()
    rows.sort(key=lambda row: _sort_when(_awarded_label(row), row.id), reverse=True)
    return [serialize_certification(row) for row in rows]


def serialize_award(row: AlumniAward) -> dict:
    return {
        "id": row.id,
        "title": row.title or "",
        "issuer": row.issuer or "",
        "awarded_on": row.awarded_on or "",
        "description": row.description or "",
    }


def serialize_awards(db: Session, account_id: int) -> list[dict]:
    rows = db.query(AlumniAward).filter(AlumniAward.account_id == account_id).all()
    rows.sort(key=lambda row: _sort_when(row.awarded_on, row.id), reverse=True)
    return [serialize_award(row) for row in rows]


def _latest_submission(db: Session, account_id: int) -> TracerSubmission | None:
    return (
        db.query(TracerSubmission)
        .filter(TracerSubmission.account_id == account_id)
        .order_by(TracerSubmission.submitted_at.desc(), TracerSubmission.id.desc())
        .first()
    )


def _sync_tracer_current_employment(db: Session, user: Account, restore: str) -> None:
    """Write the profile's current status onto the latest tracer submission.

    Earlier positions and the original occupation answers stay on the survey.
    Only the current-employment answer and its reason change.
    """
    latest = _latest_submission(db, user.id)
    if latest is None:
        return
    data = dict(latest.data_json or {})
    profile = user.profile
    if profile is not None and profile.currently_unemployed:
        data["is_currently_employed"] = "No"
        option = unemployment_option(profile.unemployment_reason)
        data["reason_current"] = [option[2]] if option else []
        data["reason_current_other"] = profile.unemployment_details if profile.unemployment_reason == "other" else ""
    else:
        has_current = (
            db.query(AlumniJob)
            .filter(AlumniJob.account_id == user.id, AlumniJob.is_current.is_(True))
            .first()
            is not None
        )
        previous = (restore or "").strip()
        if previous == "Yes" or has_current:
            data["is_currently_employed"] = "Yes"
            data["reason_current"] = []
            data["reason_current_other"] = ""
        elif previous == "No":
            data["is_currently_employed"] = "No"
    apply_current_employment(data)
    latest.data_json = data
    flag_modified(latest, "data_json")


def set_employment_status(db: Session, user: Account, payload: EmploymentStatusIn) -> dict:
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=400, detail="No alumni profile is on file.")
    details = (payload.unemployment_details or "").strip()
    if len(details) > 500:
        raise HTTPException(status_code=400, detail="Keep this explanation to 500 characters or fewer.")
    restore = profile.employment_answer_before or ""
    if payload.currently_unemployed:
        option = unemployment_option(payload.unemployment_reason)
        if option is None:
            raise HTTPException(status_code=400, detail="Select a reason for unemployment.")
        if option[0] == "other" and not details:
            raise HTTPException(status_code=400, detail="Add a short explanation when you select Other.")
        if not profile.currently_unemployed:
            latest = _latest_submission(db, user.id)
            previous = str((latest.data_json or {}).get("is_currently_employed") or "") if latest else ""
            profile.employment_answer_before = previous[:8]
        profile.currently_unemployed = True
        profile.unemployment_reason = option[0]
        profile.unemployment_details = details
        profile.no_employment_reason = unemployment_summary(option[0], details)
    else:
        profile.currently_unemployed = False
        profile.unemployment_reason = ""
        profile.unemployment_details = ""
        profile.no_employment_reason = ""
        profile.employment_answer_before = ""
    _sync_tracer_current_employment(db, user, restore)
    db.commit()
    return unemployment_public(profile)


def seed_resume_activity(db: Session, user: Account, *, fill_empty: bool = False) -> None:
    """Copy certifications, seminars, and awards from the latest resume onto the alumni home.

    The first visit copies them once. A later resume upload can fill a section
    that is still empty. Sections the graduate already edited are left alone.
    The full employment history is stored with the job timeline, not here.
    """
    profile = user.profile
    if profile is None or (profile.resume_activity_seeded and not fill_empty):
        return
    parsed: dict = {}
    resumes = (
        db.query(Resume)
        .filter(Resume.account_id == user.id)
        .order_by(Resume.created_at.desc())
        .all()
    )
    for resume in resumes:
        data = resume.parsed_json if isinstance(resume.parsed_json, dict) else {}
        if data.get("certifications") or data.get("seminars") or data.get("awards"):
            parsed = data
            break
    latest = _latest_submission(db, user.id)
    survey = latest.data_json if latest and isinstance(latest.data_json, dict) else {}

    def _rows(key: str):
        flag = {
            "certifications": "report_certifications",
            "seminars": "report_seminars",
            "awards": "report_awards",
        }[key]
        if str(survey.get(flag) or "").strip().lower() == "no":
            return []
        if key in survey and isinstance(survey.get(key), list):
            return survey.get(key)
        return parsed.get(key)

    if not db.query(AlumniCertification).filter(AlumniCertification.account_id == user.id).first():
        for item in _credential_items(_rows("certifications")):
            db.add(
                AlumniCertification(
                    account_id=user.id,
                    certification_name=item["name"][:200],
                    issuing_organization=(item["awarding_body"] or item["detail"])[:200],
                    awarded_on=item["year"],
                )
            )
    if not db.query(AlumniSeminar).filter(AlumniSeminar.account_id == user.id).first():
        for item in _credential_items(_rows("seminars")):
            db.add(
                AlumniSeminar(
                    account_id=user.id,
                    title=item["name"][:200],
                    location=(item["location"] or item["detail"] or "")[:200],
                    held_on=item["year"],
                    organizer=(item["organizer"] or "")[:200],
                )
            )
    if not db.query(AlumniAward).filter(AlumniAward.account_id == user.id).first():
        for item in _credential_items(_rows("awards")):
            db.add(
                AlumniAward(
                    account_id=user.id,
                    title=item["name"][:200],
                    issuer=(item["issuer"] or item["detail"])[:200],
                    awarded_on=item["year"],
                    description=(item["description"] or "")[:800],
                )
            )
    profile.resume_activity_seeded = True
    db.flush()


def _credential_items(rows) -> list[dict]:
    items = []
    seen = set()
    if not isinstance(rows, list):
        return items
    for row in rows:
        if isinstance(row, str):
            name, detail, year = row.strip(), "", ""
            awarding_body = location = organizer = issuer = description = ""
        elif isinstance(row, dict):
            name = str(row.get("name") or row.get("title") or "").strip()
            detail = str(row.get("detail") or "").strip()
            year = str(row.get("year") or row.get("awarded_on") or row.get("held_on") or "").strip()[:20]
            awarding_body = str(row.get("awarding_body") or "").strip()
            location = str(row.get("location") or "").strip()
            organizer = str(row.get("organizer") or "").strip()
            issuer = str(row.get("issuer") or "").strip()
            description = str(row.get("description") or "").strip()
            if not awarding_body and detail and not location and not organizer and not issuer:
                awarding_body = detail
            if not issuer:
                issuer = str(row.get("issuer") or "").strip()
            if not location and detail and not awarding_body and not issuer:
                location = detail
        else:
            continue
        key = name.lower()
        if not name or key in seen or re.fullmatch(r"(?:page|pg)\.?\s*\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?", name, re.I):
            continue
        seen.add(key)
        items.append({
            "name": name,
            "detail": detail,
            "year": year,
            "awarding_body": awarding_body,
            "location": location or (detail if not awarding_body and not issuer else ""),
            "organizer": organizer,
            "issuer": issuer or (detail if not awarding_body and not location else ""),
            "description": description,
        })
    return items


def serialize_activity(db: Session, account_id: int) -> dict:
    profile = db.query(AlumniProfile).filter(AlumniProfile.account_id == account_id).one_or_none()
    return {
        **unemployment_public(profile),
        "jobs": serialize_jobs(db, account_id),
        "seminars": serialize_seminars(db, account_id),
        "certifications": serialize_certifications(db, account_id),
        "awards": serialize_awards(db, account_id),
    }


def _owned(db: Session, model, user: Account, row_id: int, label: str):
    row = db.get(model, row_id)
    if not row or row.account_id != user.id:
        raise HTTPException(status_code=404, detail=f"{label} not found.")
    return row


def _apply_seminar(row: AlumniSeminar, payload: SeminarIn) -> None:
    title = _clean(payload.title, 200)
    location = _clean(payload.location, 200)
    if not title or not location:
        raise HTTPException(status_code=400, detail="Seminar name and location are required.")
    row.title = title
    row.location = location
    row.held_on = normalize_when(payload.held_on, required=False, label="this seminar")
    row.organizer = _clean(payload.organizer, 200)


def create_seminar(db: Session, user: Account, payload: SeminarIn) -> list[dict]:
    row = AlumniSeminar(account_id=user.id)
    _apply_seminar(row, payload)
    db.add(row)
    db.commit()
    return serialize_seminars(db, user.id)


def update_seminar(db: Session, user: Account, seminar_id: int, payload: SeminarIn) -> list[dict]:
    row = _owned(db, AlumniSeminar, user, seminar_id, "Seminar")
    _apply_seminar(row, payload)
    db.commit()
    return serialize_seminars(db, user.id)


def delete_seminar(db: Session, user: Account, seminar_id: int) -> list[dict]:
    row = _owned(db, AlumniSeminar, user, seminar_id, "Seminar")
    db.delete(row)
    db.commit()
    return serialize_seminars(db, user.id)


def _apply_certification(row: AlumniCertification, payload: CertificationIn) -> None:
    name = _clean(payload.name, 200)
    body = _clean(payload.awarding_body, 200)
    if not name or not body:
        raise HTTPException(status_code=400, detail="Certification name and awarding body are required.")
    awarded = normalize_when(payload.awarded_on, required=True, label="this certification")
    row.certification_name = name
    row.issuing_organization = body
    row.awarded_on = awarded
    row.date_issued = datetime.strptime(awarded, "%Y-%m-%d").date() if len(awarded) == 10 else None
    row.verification_url = normalize_http_url(payload.verification_url)
    row.is_verified = bool(row.certificate_path)


def create_certification(
    db: Session,
    user: Account,
    payload: CertificationIn,
    file_bytes: bytes,
    filename: str,
) -> list[dict]:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Upload a certificate or badge (PDF, JPG, PNG, or WebP).")
    row = AlumniCertification(account_id=user.id, certification_name="Pending", issuing_organization="")
    _apply_certification(row, payload)
    stored, mime, original = save_certificate_file(user.id, file_bytes, filename)
    row.certificate_path = str(stored)
    row.certificate_mime = mime
    row.certificate_filename = original
    row.is_verified = True
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        unlink_contained_file(stored)
        raise
    return serialize_certifications(db, user.id)


def update_certification(db: Session, user: Account, certification_id: int, payload: CertificationIn) -> list[dict]:
    row = _owned(db, AlumniCertification, user, certification_id, "Certification")
    _apply_certification(row, payload)
    db.commit()
    return serialize_certifications(db, user.id)


def replace_certificate(
    db: Session,
    user: Account,
    certification_id: int,
    file_bytes: bytes,
    filename: str,
) -> list[dict]:
    row = _owned(db, AlumniCertification, user, certification_id, "Certification")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Upload a certificate or badge (PDF, JPG, PNG, or WebP).")
    stored, mime, original = save_certificate_file(user.id, file_bytes, filename)
    previous = row.certificate_path
    row.certificate_path = str(stored)
    row.certificate_mime = mime
    row.certificate_filename = original
    row.is_verified = True
    try:
        db.commit()
    except Exception:
        db.rollback()
        unlink_contained_file(stored)
        raise
    if previous and previous != str(stored):
        unlink_contained_file(previous)
    return serialize_certifications(db, user.id)


def delete_certification(db: Session, user: Account, certification_id: int) -> list[dict]:
    row = _owned(db, AlumniCertification, user, certification_id, "Certification")
    previous = row.certificate_path
    db.delete(row)
    db.commit()
    unlink_contained_file(previous)
    return serialize_certifications(db, user.id)


def certification_file(db: Session, certification_id: int, *, account_id: int | None = None) -> AlumniCertification:
    row = db.get(AlumniCertification, certification_id)
    if not row or (account_id is not None and row.account_id != account_id) or not row.certificate_path:
        raise HTTPException(status_code=404, detail="Certificate file not found.")
    return row


def _apply_award(row: AlumniAward, payload: AwardIn) -> None:
    title = _clean(payload.title, 200)
    if not title:
        raise HTTPException(status_code=400, detail="Award or achievement title is required.")
    row.title = title
    row.issuer = _clean(payload.issuer, 200)
    row.awarded_on = normalize_when(payload.awarded_on, required=False, label="this award")
    row.description = _clean(payload.description, 800)


def create_award(db: Session, user: Account, payload: AwardIn) -> list[dict]:
    row = AlumniAward(account_id=user.id, title="")
    _apply_award(row, payload)
    db.add(row)
    db.commit()
    return serialize_awards(db, user.id)


def update_award(db: Session, user: Account, award_id: int, payload: AwardIn) -> list[dict]:
    row = _owned(db, AlumniAward, user, award_id, "Award")
    _apply_award(row, payload)
    db.commit()
    return serialize_awards(db, user.id)


def delete_award(db: Session, user: Account, award_id: int) -> list[dict]:
    row = _owned(db, AlumniAward, user, award_id, "Award")
    db.delete(row)
    db.commit()
    return serialize_awards(db, user.id)
