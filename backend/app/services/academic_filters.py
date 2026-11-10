"""College and course filters from the shared academic catalog."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Query, Session, object_session

from app.models import Account, AcademicProgram, AlumniProfile, College, TracerSubmission, UniversityRecord
from app.services.program_match import ProgramIndex


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


def _load_programs(db: Session) -> list[dict]:
    """Read the catalog. This does not insert or update rows."""
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


def academic_programs(db: Session) -> list[dict]:
    """College, course, and the course code saved for that program."""
    ensure_academic_catalog(db)
    return _load_programs(db)


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


def program_index(db: Session) -> ProgramIndex:
    """Catalog index for this request. Rebuilt if the session has not loaded it yet."""
    cached = db.info.get("program_index")
    if isinstance(cached, ProgramIndex):
        return cached
    index = ProgramIndex(_load_programs(db))
    db.info["program_index"] = index
    return index


def program_index_for(row) -> ProgramIndex | None:
    session = object_session(row)
    if session is None:
        return None
    return program_index(session)


def _folded_keys(values: list[str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = clean_academic(value).casefold()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _stored_academic_values(db: Session) -> tuple[list[str], list[str]]:
    cached = db.info.get("academic_value_cache")
    if cached:
        return cached
    degrees: list[str] = []
    codes: list[str] = []
    for column in (UniversityRecord.degree, AlumniProfile.degree):
        for (value,) in db.query(column).distinct():
            text = clean_academic(value)
            if text:
                degrees.append(text)
    for (value,) in db.query(UniversityRecord.course_code).distinct():
        text = clean_academic(value)
        if text:
            codes.append(text)
    cached = (degrees, codes)
    db.info["academic_value_cache"] = cached
    return cached


def strings_for_programs(db: Session, programs: list[dict]) -> tuple[list[str], list[str]]:
    """Stored degree and course-code strings that belong to these catalog programs."""
    if not programs:
        return [], []
    index = program_index(db)
    degree_values: list[str] = []
    code_values: list[str] = []
    for program in programs:
        degree_values.append(program["course"])
        code = clean_academic(program.get("course_code"))
        if code:
            code_values.append(code)
            degree_values.append(code)
        for alias in index.aliases_for(program):
            degree_values.append(alias)
            code_values.append(alias)
    degrees, codes = _stored_academic_values(db)
    for value in degrees:
        if any(index.stored_in_program(value, "", program) for program in programs):
            degree_values.append(value)
    for value in codes:
        if any(
            index.stored_in_program("", value, program) or index.stored_in_program(value, "", program)
            for program in programs
        ):
            code_values.append(value)
            degree_values.append(value)
    return degree_values, code_values


def accounts_in_programs_clause(db: Session, programs: list[dict], account_id=Account.id, student_id=Account.linked_student_id, extra_degree_columns=()):
    """Match an account whose profile, registry row, or extra degree column is one of these programs."""
    if not programs:
        return None
    degree_values, code_values = strings_for_programs(db, programs)
    degree_keys = _folded_keys(degree_values)
    code_keys = _folded_keys(code_values)
    parts = []
    if degree_keys:
        parts.append(
            select(AlumniProfile.id)
            .where(
                AlumniProfile.account_id == account_id,
                func.lower(func.trim(AlumniProfile.degree)).in_(degree_keys),
            )
            .correlate(Account)
            .exists()
        )
        parts.append(
            select(UniversityRecord.student_id)
            .where(
                UniversityRecord.student_id == student_id,
                func.lower(func.trim(UniversityRecord.degree)).in_(degree_keys),
            )
            .correlate(Account)
            .exists()
        )
        for column in extra_degree_columns:
            parts.append(func.lower(func.trim(column)).in_(degree_keys))
    if code_keys:
        parts.append(
            select(UniversityRecord.student_id)
            .where(
                UniversityRecord.student_id == student_id,
                func.lower(func.trim(UniversityRecord.course_code)).in_(code_keys),
            )
            .correlate(Account)
            .exists()
        )
    if not parts:
        return None
    return or_(*parts)


def records_in_programs_clause(db: Session, programs: list[dict], degree_column, code_column=None):
    if not programs:
        return None
    degree_values, code_values = strings_for_programs(db, programs)
    degree_keys = _folded_keys(degree_values)
    code_keys = _folded_keys(code_values)
    parts = []
    if degree_keys:
        parts.append(func.lower(func.trim(degree_column)).in_(degree_keys))
    if code_keys and code_column is not None:
        parts.append(func.lower(func.trim(code_column)).in_(code_keys))
    if not parts:
        return None
    return or_(*parts)


def course_selection_clause(db: Session, course: str, *, degree_column=None, code_column=None, account_id=None, student_id=None, extra_degree_columns=()):
    """Filter by a chosen program name or an exact abbreviation such as BSCS or BS CS."""
    course_name = clean_academic(course)
    if not course_name:
        return None
    index = program_index(db)
    selected = index.programs_for_selection(course_name)
    if degree_column is not None:
        if selected:
            clause = records_in_programs_clause(db, selected, degree_column, code_column)
            if clause is not None:
                return clause
        key = course_name.casefold()
        parts = [func.lower(func.trim(degree_column)) == key]
        if code_column is not None:
            parts.append(func.lower(func.trim(code_column)) == key)
        return or_(*parts)
    if selected:
        clause = accounts_in_programs_clause(
            db,
            selected,
            account_id if account_id is not None else Account.id,
            student_id if student_id is not None else Account.linked_student_id,
            extra_degree_columns,
        )
        if clause is not None:
            return clause
    key = course_name.casefold()
    account = account_id if account_id is not None else Account.id
    student = student_id if student_id is not None else Account.linked_student_id
    parts = [
        select(AlumniProfile.id)
        .where(AlumniProfile.account_id == account, func.lower(func.trim(AlumniProfile.degree)) == key)
        .correlate(Account)
        .exists(),
        select(UniversityRecord.student_id)
        .where(
            UniversityRecord.student_id == student,
            or_(
                func.lower(func.trim(UniversityRecord.degree)) == key,
                func.lower(func.trim(UniversityRecord.course_code)) == key,
            ),
        )
        .correlate(Account)
        .exists(),
    ]
    for column in extra_degree_columns:
        parts.append(func.lower(func.trim(column)) == key)
    return or_(*parts)


def program_term_clause(db: Session, term: str, *, degree_column=None, code_column=None, account_id=None, student_id=None, extra_degree_columns=()):
    """Records whose program matches a full name, partial name, or recognized abbreviation."""
    text = clean_academic(term)
    if len(text) < 2:
        return None
    selected = program_index(db).programs_for_term(text)
    if not selected:
        return None
    if degree_column is not None:
        return records_in_programs_clause(db, selected, degree_column, code_column)
    return accounts_in_programs_clause(
        db,
        selected,
        account_id if account_id is not None else Account.id,
        student_id if student_id is not None else Account.linked_student_id,
        extra_degree_columns,
    )


def readable_program_name(db: Session, degree: str | None, course_code: str | None = "", college: str | None = "") -> str:
    return program_index(db).display_name(degree, course_code, college)


def apply_registry_academic_filters(query: Query, college: str = "", course: str = "", db: Session | None = None) -> Query:
    college_name = clean_academic(college)
    course_name = clean_academic(course)
    if college_name:
        query = query.filter(func.trim(UniversityRecord.college) == college_name)
    if course_name:
        if db is None:
            query = query.filter(func.trim(UniversityRecord.degree) == course_name)
        else:
            query = query.filter(
                course_selection_clause(
                    db,
                    course_name,
                    degree_column=UniversityRecord.degree,
                    code_column=UniversityRecord.course_code,
                )
            )
    return query


def _linked_record_value(column):
    """One registry column for the joined account, without adding that table to the outer query."""
    return (
        select(column)
        .where(UniversityRecord.student_id == Account.linked_student_id)
        .correlate(Account)
        .scalar_subquery()
    )


def _profile_degree_value():
    return (
        select(AlumniProfile.degree)
        .where(AlumniProfile.account_id == Account.id)
        .correlate(Account)
        .scalar_subquery()
    )


def _official_course():
    """Registry program, then profile, then the submitted survey. Not the resume parser."""
    submitted = TracerSubmission.data_json["degree"].as_string()
    return func.trim(
        func.coalesce(
            func.nullif(func.trim(_linked_record_value(UniversityRecord.degree)), ""),
            func.nullif(func.trim(_profile_degree_value()), ""),
            func.nullif(func.trim(submitted), ""),
        )
    )


def apply_tracer_academic_filters(query: Query, college: str = "", course: str = "", db: Session | None = None) -> Query:
    college_name = clean_academic(college)
    course_name = clean_academic(course)
    if not college_name and not course_name:
        return query
    if course_name:
        selected = program_index(db).programs_for_selection(course_name) if db is not None else []
        official = func.lower(_official_course())
        code = func.lower(func.trim(_linked_record_value(UniversityRecord.course_code)))
        if selected and db is not None:
            degree_values, code_values = strings_for_programs(db, selected)
            degree_keys = _folded_keys(degree_values)
            code_keys = _folded_keys(code_values)
            parts = []
            if degree_keys:
                parts.append(official.in_(degree_keys))
            if code_keys:
                parts.append(code.in_(code_keys))
            query = query.filter(or_(*parts) if parts else official == course_name.casefold())
        else:
            key = course_name.casefold()
            query = query.filter(or_(official == key, code == key))
    if college_name:
        query = query.filter(func.trim(_linked_record_value(UniversityRecord.college)) == college_name)
    return query
