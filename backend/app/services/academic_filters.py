"""College and course filters drawn from official university records."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.models import Account, AlumniProfile, TracerSubmission, UniversityRecord


def clean_academic(value: str | None) -> str:
    return str(value or "").strip()


def academic_catalog(db: Session) -> dict:
    """Distinct colleges and courses from the graduate registry."""
    rows = db.query(UniversityRecord.college, UniversityRecord.degree).all()
    pairs = []
    seen: set[tuple[str, str]] = set()
    for college, degree in rows:
        college_name = clean_academic(college)
        course_name = clean_academic(degree)
        if not college_name and not course_name:
            continue
        key = (college_name, course_name)
        if key in seen:
            continue
        seen.add(key)
        pairs.append({"college": college_name, "course": course_name})
    colleges = sorted({item["college"] for item in pairs if item["college"]})
    courses = sorted({item["course"] for item in pairs if item["course"]})
    return {"colleges": colleges, "courses": courses, "pairs": pairs}


def apply_registry_academic_filters(query: Query, college: str = "", course: str = "") -> Query:
    college_name = clean_academic(college)
    course_name = clean_academic(course)
    if college_name:
        query = query.filter(func.trim(UniversityRecord.college) == college_name)
    if course_name:
        query = query.filter(func.trim(UniversityRecord.degree) == course_name)
    return query


def _official_course():
    """Registry program, then profile, then the submitted survey. Not the resume parser."""
    submitted = TracerSubmission.data_json["degree"].as_string()
    return func.trim(
        func.coalesce(
            func.nullif(func.trim(UniversityRecord.degree), ""),
            func.nullif(func.trim(AlumniProfile.degree), ""),
            func.nullif(func.trim(submitted), ""),
        )
    )


def apply_tracer_academic_filters(query: Query, college: str = "", course: str = "") -> Query:
    college_name = clean_academic(college)
    course_name = clean_academic(course)
    if not college_name and not course_name:
        return query
    query = query.outerjoin(UniversityRecord, Account.linked_student_id == UniversityRecord.student_id)
    if course_name:
        query = query.outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
        query = query.filter(_official_course() == course_name)
    if college_name:
        query = query.filter(func.trim(UniversityRecord.college) == college_name)
    return query
