"""One college and course catalog for the import list, reports, and verification.

Rows already stored on graduate records are copied in. Later edits keep the
catalog spelling and course code, and graduate labels change only after an
administrator confirms the update.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AcademicProgram, AdminLog, College, UniversityRecord
from app.services.academic_filters import clean_academic

COLLEGE_NAME_LIMIT = 160
COLLEGE_CODE_LIMIT = 40
COURSE_NAME_LIMIT = 200
COURSE_CODE_LIMIT = 40

PROGRAM_KINDS = (
    "undergraduate",
    "graduate",
    "professional",
    "diploma",
    "certificate",
    "combined",
    "pathway",
    "major",
    "specialization",
)
KIND_LABELS = {
    "undergraduate": "Undergraduate",
    "graduate": "Graduate",
    "professional": "Professional",
    "diploma": "Diploma",
    "certificate": "Certificate",
    "combined": "Combined pathway",
    "pathway": "Pathway",
    "major": "Major",
    "specialization": "Specialization",
}
REVIEW_STATUSES = ("on_record", "needs_review")
REVIEW_LABELS = {
    "on_record": "On record",
    "needs_review": "Needs review",
}


class CatalogError(Exception):
    def __init__(self, message: str, status: int = 400, **extra):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra


def sync_catalog_from_records(db: Session) -> bool:
    """Add catalog rows for colleges and courses already stored on graduates.

    Existing catalog names and course codes are left as the administrator saved
    them. Nothing is deleted, and graduate records are not rewritten.
    """
    db.flush()
    changed = False
    colleges = {row.name.casefold(): row for row in db.query(College).all()}
    for (college_name,) in db.query(UniversityRecord.college).distinct():
        name = clean_academic(college_name)
        if not name or name.casefold() in colleges:
            continue
        if len(name) > COLLEGE_NAME_LIMIT:
            continue
        row = College(name=name, code="")
        db.add(row)
        db.flush()
        colleges[name.casefold()] = row
        changed = True

    programs = {
        (program.college_id, program.name.casefold()): program
        for program in db.query(AcademicProgram).all()
    }
    grouped: dict[tuple[str, str], list[str]] = {}
    rows = db.query(UniversityRecord.college, UniversityRecord.degree, UniversityRecord.course_code).all()
    for college_name, degree, code in rows:
        college = clean_academic(college_name)
        course = clean_academic(degree)
        if not college or not course or len(course) > COURSE_NAME_LIMIT:
            continue
        grouped.setdefault((college, course), []).append(clean_academic(code))

    for (college_name, course_name), codes in grouped.items():
        college = colleges.get(college_name.casefold())
        if not college:
            continue
        key = (college.id, course_name.casefold())
        if key in programs:
            continue
        code = _preferred_code(codes)
        if len(code) > COURSE_CODE_LIMIT:
            code = code[:COURSE_CODE_LIMIT]
        program = AcademicProgram(college_id=college.id, name=course_name, course_code=code)
        db.add(program)
        programs[key] = program
        changed = True
    if changed:
        db.flush()
    return changed


def course_code_owner(db: Session, code: str, *, exclude_id: int | None = None) -> dict | None:
    key = clean_academic(code).casefold()
    if not key:
        return None
    for program, college in db.query(AcademicProgram, College).join(College, AcademicProgram.college_id == College.id):
        if exclude_id and program.id == exclude_id:
            continue
        if clean_academic(program.course_code).casefold() == key:
            return {"id": program.id, "course": program.name, "college": college.name, "course_code": program.course_code}
    return None


def list_academics(db: Session) -> dict:
    from app.services.academic_reference import apply_auf_reference

    apply_auf_reference(db)
    db.commit()
    colleges = db.query(College).order_by(func.lower(College.name), College.id).all()
    programs = (
        db.query(AcademicProgram, College)
        .join(College, AcademicProgram.college_id == College.id)
        .order_by(func.lower(College.name), func.lower(AcademicProgram.name), AcademicProgram.id)
        .all()
    )
    record_rows = db.query(UniversityRecord.college, UniversityRecord.degree).all()
    college_counts: dict[str, int] = {}
    course_counts: dict[tuple[str, str], int] = {}
    for college_name, degree in record_rows:
        college_key = clean_academic(college_name).casefold()
        course_key = clean_academic(degree).casefold()
        if college_key:
            college_counts[college_key] = college_counts.get(college_key, 0) + 1
        if college_key and course_key:
            pair = (college_key, course_key)
            course_counts[pair] = course_counts.get(pair, 0) + 1
    course_totals = {college.id: 0 for college in colleges}
    parents = {program.id: program for program, _college in programs}
    course_rows = []
    for program, college in programs:
        course_totals[college.id] = course_totals.get(college.id, 0) + 1
        course_rows.append(_course_row(program, college, course_counts, parents))
    return {
        "colleges": [
            {
                "id": college.id,
                "name": college.name,
                "code": college.code or "",
                "course_count": course_totals.get(college.id, 0),
                "graduate_count": college_counts.get(college.name.casefold(), 0),
            }
            for college in colleges
        ],
        "courses": course_rows,
    }


def create_college(db: Session, name: str, code: str, admin_id: int | None) -> dict:
    cleaned_name = _required_text(name, "Enter a college name.", COLLEGE_NAME_LIMIT, "College name")
    cleaned_code = _optional_text(code, COLLEGE_CODE_LIMIT, "College code")
    _ensure_college_name(db, cleaned_name)
    _ensure_college_code(db, cleaned_code)
    row = College(name=cleaned_name, code=cleaned_code)
    db.add(row)
    db.flush()
    _log(db, admin_id, "CREATE_COLLEGE", row.id, None, {"name": row.name, "code": row.code})
    db.commit()
    db.refresh(row)
    return _college_payload(db, row)


def update_college(db: Session, college_id: int, name: str, code: str, confirm: bool, admin_id: int | None) -> dict:
    row = db.get(College, college_id)
    if not row:
        raise CatalogError("This college was not found.", 404)
    cleaned_name = _required_text(name, "Enter a college name.", COLLEGE_NAME_LIMIT, "College name")
    cleaned_code = _optional_text(code, COLLEGE_CODE_LIMIT, "College code")
    _ensure_college_name(db, cleaned_name, exclude_id=row.id)
    _ensure_college_code(db, cleaned_code, exclude_id=row.id)
    name_changed = cleaned_name != row.name
    if not name_changed and cleaned_code == (row.code or ""):
        return _college_payload(db, row)
    graduates = _college_records(db, row.name) if name_changed else []
    if graduates and not confirm:
        raise CatalogError(
            (
                f"{_uses(len(graduates))} this college. Saving will update the college name on those records "
                "so the import list, verification, and reports stay aligned. Other graduate information will stay the same."
            ),
            409,
            graduate_count=len(graduates),
            requires_confirmation=True,
        )
    old = {"name": row.name, "code": row.code or ""}
    row.name = cleaned_name
    row.code = cleaned_code
    row.updated_at = datetime.now(timezone.utc)
    for record in graduates:
        record.college = cleaned_name
    _log(db, admin_id, "UPDATE_COLLEGE", row.id, old, {"name": row.name, "code": row.code, "graduates_updated": len(graduates)})
    db.commit()
    db.refresh(row)
    return _college_payload(db, row)


def delete_college(db: Session, college_id: int, admin_id: int | None) -> dict:
    row = db.get(College, college_id)
    if not row:
        raise CatalogError("This college was not found.", 404)
    course_count = db.query(AcademicProgram).filter(AcademicProgram.college_id == row.id).count()
    if course_count:
        noun = "course" if course_count == 1 else "courses"
        raise CatalogError(
            (
                f"This college still has {course_count} {noun}. Move or delete those courses before deleting the college. "
                "Graduate records were not changed."
            ),
            409,
            course_count=course_count,
        )
    graduates = _college_records(db, row.name)
    if graduates:
        raise CatalogError(
            (
                f"This college is used by {_count_label(len(graduates))}. It was not deleted, and those graduate records "
                "were left unchanged. Edit the college if its official name changed."
            ),
            409,
            graduate_count=len(graduates),
        )
    old = {"name": row.name, "code": row.code or ""}
    db.delete(row)
    _log(db, admin_id, "DELETE_COLLEGE", college_id, old, None)
    db.commit()
    return {"ok": True}


def create_course(
    db: Session,
    college_id: int | None,
    name: str,
    course_code: str,
    admin_id: int | None,
    *,
    kind: str = "",
    parent_id: int | None = None,
    review_status: str = "",
) -> dict:
    college = _college_or_error(db, college_id)
    cleaned_name = _required_text(name, "Enter a course name.", COURSE_NAME_LIMIT, "Course name")
    cleaned_code = _optional_text(course_code, COURSE_CODE_LIMIT, "Course code")
    cleaned_kind = _kind_or_error(kind)
    cleaned_review = _review_or_error(review_status or "needs_review")
    parent = _parent_or_error(db, college.id, parent_id, None)
    _ensure_course_name(db, college.id, cleaned_name)
    _ensure_course_code(db, cleaned_code)
    program = AcademicProgram(
        college_id=college.id,
        parent_id=parent.id if parent else None,
        name=cleaned_name,
        course_code=cleaned_code,
        kind=cleaned_kind,
        review_status=cleaned_review,
    )
    db.add(program)
    db.flush()
    _log(
        db,
        admin_id,
        "CREATE_COURSE",
        program.id,
        None,
        {"name": program.name, "course_code": program.course_code, "college": college.name, "kind": program.kind},
    )
    db.commit()
    db.refresh(program)
    return _course_payload(db, program, college)


def update_course(
    db: Session,
    course_id: int,
    college_id: int | None,
    name: str,
    course_code: str,
    confirm: bool,
    admin_id: int | None,
    *,
    kind: str = "",
    parent_id: int | None = None,
    review_status: str = "",
) -> dict:
    program = db.get(AcademicProgram, course_id)
    if not program:
        raise CatalogError("This course was not found.", 404)
    college = _college_or_error(db, college_id)
    cleaned_name = _required_text(name, "Enter a course name.", COURSE_NAME_LIMIT, "Course name")
    cleaned_code = _optional_text(course_code, COURSE_CODE_LIMIT, "Course code")
    cleaned_kind = _kind_or_error(kind if kind or program.kind else "undergraduate")
    cleaned_review = _review_or_error(review_status or program.review_status or "on_record")
    parent = _parent_or_error(db, college.id, parent_id, program.id)
    _ensure_course_name(db, college.id, cleaned_name, exclude_id=program.id)
    _ensure_course_code(db, cleaned_code, exclude_id=program.id)
    current_college = program.college
    college_changed = college.id != program.college_id
    name_changed = cleaned_name != program.name
    code_changed = cleaned_code != (program.course_code or "")
    detail_changed = (
        cleaned_kind != (program.kind or "")
        or cleaned_review != (program.review_status or "")
        or (parent.id if parent else None) != program.parent_id
    )
    if not college_changed and not name_changed and not code_changed and not detail_changed:
        return _course_payload(db, program, current_college)
    identity_changed = college_changed or name_changed or code_changed
    graduates = _course_records(db, current_college.name, program.name) if identity_changed else []
    if graduates and not confirm:
        labels = []
        if college_changed:
            labels.append("college")
        if name_changed:
            labels.append("course name")
        if code_changed:
            labels.append("course code")
        raise CatalogError(
            (
                f"{_uses(len(graduates))} this course. Saving will update the {_join(labels)} on those records "
                "so the import list, verification, and reports stay aligned. Other graduate information will stay the same."
            ),
            409,
            graduate_count=len(graduates),
            requires_confirmation=True,
        )
    old = {"name": program.name, "course_code": program.course_code or "", "college": current_college.name}
    program.college_id = college.id
    program.parent_id = parent.id if parent else None
    program.name = cleaned_name
    program.course_code = cleaned_code
    program.kind = cleaned_kind
    program.review_status = cleaned_review
    program.updated_at = datetime.now(timezone.utc)
    for record in graduates:
        record.college = college.name
        record.degree = cleaned_name
        record.course_code = cleaned_code
    _log(
        db,
        admin_id,
        "UPDATE_COURSE",
        program.id,
        old,
        {"name": program.name, "course_code": program.course_code, "college": college.name, "graduates_updated": len(graduates)},
    )
    db.commit()
    db.refresh(program)
    return _course_payload(db, program, college)


def delete_course(db: Session, course_id: int, admin_id: int | None) -> dict:
    program = db.get(AcademicProgram, course_id)
    if not program:
        raise CatalogError("This course was not found.", 404)
    college = program.college
    child_count = db.query(AcademicProgram).filter(AcademicProgram.parent_id == program.id).count()
    if child_count:
        noun = "program" if child_count == 1 else "programs"
        raise CatalogError(
            (
                f"This program still has {child_count} related {noun}. Move or delete those majors, "
                "specializations, or pathways first. Graduate records were not changed."
            ),
            409,
            course_count=child_count,
        )
    graduates = _course_records(db, college.name, program.name)
    if graduates:
        raise CatalogError(
            (
                f"This course is used by {_count_label(len(graduates))}. It was not deleted, and those graduate records "
                "were left unchanged. Edit the course if its official name or course code changed."
            ),
            409,
            graduate_count=len(graduates),
        )
    old = {"name": program.name, "course_code": program.course_code or "", "college": college.name}
    db.delete(program)
    _log(db, admin_id, "DELETE_COURSE", course_id, old, None)
    db.commit()
    return {"ok": True}


def _college_or_error(db: Session, college_id: int | None) -> College:
    if not college_id:
        raise CatalogError("Select the college this course belongs to.")
    college = db.get(College, college_id)
    if not college:
        raise CatalogError("Select the college this course belongs to.")
    return college


def _required_text(value: str, empty_message: str, limit: int, label: str) -> str:
    cleaned = clean_academic(value)
    if not cleaned:
        raise CatalogError(empty_message)
    if len(cleaned) > limit:
        raise CatalogError(f"{label} must be {limit} characters or fewer.")
    return cleaned


def _optional_text(value: str, limit: int, label: str) -> str:
    cleaned = clean_academic(value)
    if len(cleaned) > limit:
        raise CatalogError(f"{label} must be {limit} characters or fewer.")
    return cleaned


def _ensure_college_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    for row in db.query(College).all():
        if exclude_id and row.id == exclude_id:
            continue
        if row.name.casefold() == name.casefold():
            raise CatalogError("A college with this name already exists.")


def _ensure_college_code(db: Session, code: str, exclude_id: int | None = None) -> None:
    if not code:
        return
    for row in db.query(College).all():
        if exclude_id and row.id == exclude_id:
            continue
        if clean_academic(row.code).casefold() == code.casefold():
            raise CatalogError("A college with this code already exists.")


def _ensure_course_name(db: Session, college_id: int, name: str, exclude_id: int | None = None) -> None:
    for row in db.query(AcademicProgram).filter(AcademicProgram.college_id == college_id):
        if exclude_id and row.id == exclude_id:
            continue
        if row.name.casefold() == name.casefold():
            raise CatalogError("A course with this name already exists in the selected college.")


def _ensure_course_code(db: Session, code: str, exclude_id: int | None = None) -> None:
    owner = course_code_owner(db, code, exclude_id=exclude_id)
    if owner:
        raise CatalogError(f"Course code {code} is already used by {owner['course']}.")


def _college_records(db: Session, name: str) -> list[UniversityRecord]:
    key = clean_academic(name).casefold()
    if not key:
        return []
    return db.query(UniversityRecord).filter(func.lower(func.trim(UniversityRecord.college)) == key).all()


def _course_records(db: Session, college: str, course: str) -> list[UniversityRecord]:
    college_key = clean_academic(college).casefold()
    course_key = clean_academic(course).casefold()
    if not college_key or not course_key:
        return []
    return (
        db.query(UniversityRecord)
        .filter(
            func.lower(func.trim(UniversityRecord.college)) == college_key,
            func.lower(func.trim(UniversityRecord.degree)) == course_key,
        )
        .all()
    )


def _college_payload(db: Session, row: College) -> dict:
    course_count = db.query(AcademicProgram).filter(AcademicProgram.college_id == row.id).count()
    return {
        "id": row.id,
        "name": row.name,
        "code": row.code or "",
        "course_count": course_count,
        "graduate_count": len(_college_records(db, row.name)),
    }


def _course_payload(db: Session, program: AcademicProgram, college: College) -> dict:
    parent = db.get(AcademicProgram, program.parent_id) if program.parent_id else None
    return {
        "id": program.id,
        "college_id": college.id,
        "college": college.name,
        "parent_id": program.parent_id,
        "parent_name": parent.name if parent else "",
        "name": program.name,
        "course_code": program.course_code or "",
        "kind": program.kind or "",
        "kind_label": KIND_LABELS.get(program.kind or "", "Program"),
        "review_status": program.review_status or "on_record",
        "review_label": REVIEW_LABELS.get(program.review_status or "", "On record"),
        "graduate_count": len(_course_records(db, college.name, program.name)),
    }


def _course_row(program: AcademicProgram, college: College, course_counts: dict, parents: dict[int, AcademicProgram]) -> dict:
    parent = parents.get(program.parent_id) if program.parent_id else None
    return {
        "id": program.id,
        "college_id": college.id,
        "college": college.name,
        "parent_id": program.parent_id,
        "parent_name": parent.name if parent else "",
        "name": program.name,
        "course_code": program.course_code or "",
        "kind": program.kind or "",
        "kind_label": KIND_LABELS.get(program.kind or "", "Program"),
        "review_status": program.review_status or "on_record",
        "review_label": REVIEW_LABELS.get(program.review_status or "", "On record"),
        "graduate_count": course_counts.get((college.name.casefold(), program.name.casefold()), 0),
    }


def _kind_or_error(kind: str) -> str:
    cleaned = clean_academic(kind).casefold().replace(" ", "_")
    if cleaned in {"combined_pathway"}:
        cleaned = "combined"
    if not cleaned:
        return ""
    if cleaned not in PROGRAM_KINDS:
        raise CatalogError("Select the program type.")
    return cleaned


def _review_or_error(status: str) -> str:
    cleaned = clean_academic(status).casefold().replace(" ", "_")
    if cleaned not in REVIEW_STATUSES:
        raise CatalogError("Select whether this program is on record or still needs review.")
    return cleaned


def _parent_or_error(db: Session, college_id: int, parent_id: int | None, program_id: int | None) -> AcademicProgram | None:
    if not parent_id:
        return None
    if program_id and parent_id == program_id:
        raise CatalogError("A program cannot be its own parent.")
    parent = db.get(AcademicProgram, parent_id)
    if not parent or parent.college_id != college_id:
        raise CatalogError("Select a parent program from the same college.")
    return parent


def _preferred_code(codes: list[str]) -> str:
    counts: dict[str, int] = {}
    for code in codes:
        if code:
            counts[code] = counts.get(code, 0) + 1
    if not counts:
        return ""
    best = max(counts.values())
    winners = sorted((code for code, count in counts.items() if count == best), key=str.casefold)
    return winners[0]


def _uses(count: int) -> str:
    if count == 1:
        return "1 graduate record uses"
    return f"{count} graduate records use"


def _count_label(count: int) -> str:
    noun = "graduate record" if count == 1 else "graduate records"
    return f"{count} {noun}"


def _join(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _log(db: Session, admin_id: int | None, action: str, target_id, old, new) -> None:
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=action,
            target_id=str(target_id or ""),
            old_value=old,
            new_value=new,
        )
    )
