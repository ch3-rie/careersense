"""Alumni further-studies timeline — stored in FurtherStudy, rewritten on GTS submit."""

from __future__ import annotations

import re
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Account, FurtherStudy
from app.schemas import StudyIn


def serialize_study(row: FurtherStudy) -> dict:
    return {
        "id": row.id,
        "course_degree": row.course_degree or "",
        "school": row.school or "",
        "year_enrolled": row.year_enrolled or "",
        "scholarship": row.scholarship or "",
        "is_graduated": row.is_graduated,
    }


def serialize_studies(db: Session, account_id: int) -> list[dict]:
    rows = db.query(FurtherStudy).filter(FurtherStudy.account_id == account_id).all()
    return [serialize_study(row) for row in rows]


def _year_enrolled(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if not re.fullmatch(r"\d{4}", text):
        raise HTTPException(status_code=400, detail="Year enrolled must be a four-digit year.")
    year = int(text)
    latest = date.today().year + 8
    if year < 1950 or year > latest:
        raise HTTPException(status_code=400, detail="Please enter a valid enrollment year.")
    return text


def _apply_payload(row: FurtherStudy, payload: StudyIn) -> None:
    course = payload.course_degree.strip()
    school = payload.school.strip()
    if not course or not school:
        raise HTTPException(status_code=400, detail="Program and institution are required.")
    row.course_degree = course
    row.school = school
    row.year_enrolled = _year_enrolled(payload.year_enrolled)
    row.scholarship = (payload.scholarship or "").strip()
    row.is_graduated = payload.is_graduated


def _owned_study(db: Session, user: Account, study_id: int) -> FurtherStudy:
    row = db.get(FurtherStudy, study_id)
    if not row or row.account_id != user.id:
        raise HTTPException(status_code=404, detail="Further study not found.")
    return row


def create_study(db: Session, user: Account, payload: StudyIn) -> list[dict]:
    row = FurtherStudy(account_id=user.id)
    _apply_payload(row, payload)
    db.add(row)
    db.commit()
    return serialize_studies(db, user.id)


def update_study(db: Session, user: Account, study_id: int, payload: StudyIn) -> list[dict]:
    row = _owned_study(db, user, study_id)
    _apply_payload(row, payload)
    db.commit()
    return serialize_studies(db, user.id)


def delete_study(db: Session, user: Account, study_id: int) -> list[dict]:
    row = _owned_study(db, user, study_id)
    db.delete(row)
    db.commit()
    return serialize_studies(db, user.id)
