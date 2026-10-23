"""College and course filters from the shared academic catalog."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.models import Account, AcademicProgram, AlumniProfile, College, TracerSubmission, UniversityRecord


class ProgramSelectionError(ValueError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def clean_academic(value: str | None) -> str:
    return str(value or "").strip()


def ensure_academic_catalog(db: Session, *, commit: bool = False) -> None:
    """Copy missing colleges and courses from graduate records, then add the AUF reference list."""
    from app.services.academic_reference import apply_auf_reference

    if apply_auf_reference(db) and commit:
        db.commit()


def academic_programs(db: Session) -> list[dict]:
    """College, course, and the course code saved for that program."""
    ensure_academic_catalog(db)
    rows = (
        db.query(AcademicProgram, College)
        .join(College, AcademicProgram.college_id == College.id)
        .all()
    )
    programs = [
        {
            "college": college.name,
            "course": program.name,
            "course_code": program.course_code or "",
            "kind": program.kind or "",
        }
        for program, college in rows
        if college.name and program.name
    ]
    programs.sort(key=lambda item: (item["college"].casefold(), item["course"].casefold()))
    return programs


def academic_catalog(db: Session) -> dict:
    """Colleges and courses maintained for the whole system."""
    programs = academic_programs(db)
    pairs = [{"college": item["college"], "course": item["course"]} for item in programs]
    colleges = [row.name for row in db.query(College).all() if clean_academic(row.name)]
    known = {name.casefold() for name in colleges}
    for item in programs:
        if item["college"].casefold() not in known:
            colleges.append(item["college"])
            known.add(item["college"].casefold())
    colleges.sort(key=str.casefold)
    courses = sorted({item["course"] for item in pairs if item["course"]}, key=str.casefold)
    return {"colleges": colleges, "courses": courses, "pairs": pairs, "programs": programs}


def resolve_program_selection(db: Session, college: str, course: str, course_code: str = "") -> tuple[str, str, str]:
    """Keep a manually chosen course inside its college and fill the stored course code."""
    college_name = clean_academic(college)
    course_name = clean_academic(course)
    code = clean_academic(course_code)
    if not course_name:
        raise ProgramSelectionError("Course is required.")
    if len(college_name) > 160:
        raise ProgramSelectionError("College must be 160 characters or fewer.")
    if len(course_name) > 200:
        raise ProgramSelectionError("Course must be 200 characters or fewer.")
    if len(code) > 40:
        raise ProgramSelectionError("Course code must be 40 characters or fewer.")
    matches = [item for item in academic_programs(db) if item["course"].casefold() == course_name.casefold()]
    pair = next((item for item in matches if item["college"].casefold() == college_name.casefold()), None)
    if matches and not pair:
        raise ProgramSelectionError("The selected course does not belong to the selected college.")
    if pair:
        return pair["college"], pair["course"], pair["course_code"] or code
    return college_name, course_name, code


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
