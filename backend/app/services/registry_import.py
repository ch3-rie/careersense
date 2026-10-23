"""Import Registrar's Office graduate lists into the existing university registry."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile
from zoneinfo import ZoneInfo

from email_validator import EmailNotValidError, validate_email
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl import load_workbook
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RegistryImport, UniversityRecord

MANILA = ZoneInfo("Asia/Manila")
MAX_ROWS = 5000
REQUIRED_FIELDS = (
    "student_number",
    "first_name",
    "middle_name",
    "last_name",
    "college",
    "course",
    "course_code",
)
FIELD_LABELS = {
    "student_number": "Student Number",
    "first_name": "First Name",
    "middle_name": "Middle Name",
    "last_name": "Last Name",
    "college": "College",
    "course": "Course",
    "course_code": "Course Code",
}
HEADER_ALIASES = {
    "student_number": {"student number", "student no", "student id", "student id number", "id number"},
    "first_name": {"first name", "firstname", "given name"},
    "middle_name": {"middle name", "middlename", "middle initial", "middle"},
    "last_name": {"last name", "lastname", "surname", "family name"},
    "college": {"college", "college name"},
    "course": {"course", "program", "degree", "course name", "program name", "course program"},
    "course_code": {"course code", "coursecode", "program code", "degree code"},
    "email": {"email", "e mail", "personal email", "email address"},
    "year_graduated": {"year graduated", "year of graduation", "graduation year", "year"},
}
PUBLIC_FIELDS = (
    "row_number",
    "student_number",
    "first_name",
    "middle_name",
    "last_name",
    "college",
    "course",
    "course_code",
    "status",
    "message",
)
STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ./_-]{0,39}$")


class RegistryImportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def latest_registry_import(db: Session) -> dict | None:
    row = db.query(RegistryImport).order_by(RegistryImport.created_at.desc(), RegistryImport.id.desc()).first()
    if not row:
        return None
    return _batch_payload(row)


def preview_registry_import(db: Session, data: bytes, filename: str) -> dict:
    parsed, rows = _prepare(db, data, filename)
    return {
        "filename": parsed["filename"],
        "summary": _summary(rows),
        "rows": [_public_row(row) for row in rows],
        "last_import": latest_registry_import(db),
    }


def commit_registry_import(db: Session, data: bytes, filename: str, admin_id: int | None) -> dict:
    parsed, rows = _prepare(db, data, filename)
    ready = [row for row in rows if row["status"] == "ready"]
    try:
        for row in ready:
            record = UniversityRecord(
                student_id=row["student_number"],
                first_name=row["first_name"],
                middle_name=row["middle_name"],
                last_name=row["last_name"],
                personal_email=row["email"],
                degree=row["course"],
                year_graduated=row["year_graduated"],
                course_code=row["course_code"],
                college=row["college"],
            )
            try:
                with db.begin_nested():
                    db.add(record)
                    db.flush()
            except IntegrityError:
                row["status"] = "skipped"
                row["message"] = (
                    "This student number or email is already in the import list. "
                    "The existing record was left unchanged."
                )
                continue
            row["status"] = "imported"
            row["message"] = ""
        summary = _summary(rows)
        batch = None
        if summary["imported"]:
            from app.services.academic_catalog import sync_catalog_from_records

            sync_catalog_from_records(db)
            batch = RegistryImport(
                file_sha256=parsed["file_sha256"],
                content_sha256=parsed["content_sha256"],
                filename=parsed["filename"],
                imported_count=summary["imported"],
                skipped_count=summary["skipped"],
                invalid_count=summary["invalid"],
                admin_id=admin_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(batch)
            db.commit()
            db.refresh(batch)
        else:
            db.rollback()
    except IntegrityError:
        db.rollback()
        duplicate = _find_duplicate(db, parsed["file_sha256"], parsed["content_sha256"])
        if duplicate:
            raise RegistryImportError(_duplicate_message(duplicate), 409) from None
        raise RegistryImportError(
            "The import could not be saved. No records were changed. Upload the file again.",
            409,
        ) from None
    return {
        "ok": True,
        "filename": parsed["filename"],
        "summary": _summary(rows),
        "issues": [_public_row(row) for row in rows if row["status"] in {"skipped", "invalid"}],
        "last_import": _batch_payload(batch) if batch else latest_registry_import(db),
    }


def _prepare(db: Session, data: bytes, filename: str) -> tuple[dict, list[dict]]:
    parsed = parse_workbook(data, filename)
    duplicate = _find_duplicate(db, parsed["file_sha256"], parsed["content_sha256"])
    if duplicate:
        raise RegistryImportError(_duplicate_message(duplicate), 409)
    return parsed, classify_rows(db, parsed["rows"])


def parse_workbook(data: bytes, filename: str) -> dict:
    if not data:
        raise RegistryImportError("The uploaded Excel file is empty.")
    limit = max(1, get_settings().max_upload_mb) * 1024 * 1024
    if len(data) > limit:
        raise RegistryImportError(f"The Excel file is larger than {get_settings().max_upload_mb} MB.")
    clean_name = _clean_filename(filename)
    suffix = Path(clean_name).suffix.lower()
    if suffix and suffix not in {".xlsx", ".xlsm"}:
        raise RegistryImportError("Upload an Excel workbook (.xlsx) from the Registrar's Office.")
    try:
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=False)
    except (InvalidFileException, BadZipFile, OSError, ValueError, KeyError) as exc:
        raise RegistryImportError(
            "This file is not a valid Excel workbook. Save the Registrar's Office list as .xlsx and try again."
        ) from exc
    try:
        header_row, columns, sheet_rows = _locate_table(workbook)
        parsed_rows = _read_rows(sheet_rows, header_row, columns)
    finally:
        workbook.close()
    if not parsed_rows:
        raise RegistryImportError("The Excel file has no graduate records to import.")
    if len(parsed_rows) > MAX_ROWS:
        raise RegistryImportError(
            f"This workbook has more than {MAX_ROWS:,} data rows. Split it into smaller Excel files and import each one."
        )
    return {
        "filename": clean_name,
        "file_sha256": hashlib.sha256(data).hexdigest(),
        "content_sha256": _content_sha256(parsed_rows),
        "rows": parsed_rows,
    }


def _align_academic_fields(db: Session, row: dict) -> str:
    """Use the shared catalog when the college and course already exist."""
    from app.services.academic_catalog import course_code_owner
    from app.services.academic_filters import ProgramSelectionError, academic_programs, resolve_program_selection

    try:
        college, course, code = resolve_program_selection(db, row["college"], row["course"], row["course_code"])
    except ProgramSelectionError as exc:
        return exc.message
    known = next(
        (
            item
            for item in academic_programs(db)
            if item["college"].casefold() == college.casefold() and item["course"].casefold() == course.casefold()
        ),
        None,
    )
    if known:
        row["college"] = known["college"]
        row["course"] = known["course"]
        row["course_code"] = known["course_code"] or code
        return ""
    owner = course_code_owner(db, code)
    if owner:
        return (
            f"Course code {code} is already used by {owner['course']} in {owner['college']}. "
            "Use that program or choose a different course code."
        )
    row["college"] = college
    row["course"] = course
    row["course_code"] = code
    return ""


def _new_code_conflict(row: dict, introduced: dict[str, tuple[str, str]]) -> str:
    code = str(row.get("course_code") or "").strip().casefold()
    if not code:
        return ""
    identity = (str(row.get("college") or "").casefold(), str(row.get("course") or "").casefold())
    previous = introduced.get(code)
    if previous and previous != identity:
        return f"Course code {row['course_code']} is already used by another course in this file."
    introduced[code] = identity
    return ""


def classify_rows(db: Session, rows: list[dict]) -> list[dict]:
    existing_ids = {
        (student_id or "").strip().casefold()
        for (student_id,) in db.query(UniversityRecord.student_id).all()
        if (student_id or "").strip()
    }
    existing_emails = {
        email.strip().casefold()
        for (email,) in db.query(UniversityRecord.personal_email).filter(UniversityRecord.personal_email.isnot(None)).all()
        if email and email.strip()
    }
    claimed_ids: set[str] = set()
    claimed_emails: set[str] = set()
    introduced_codes: dict[str, tuple[str, str]] = {}
    classified = []
    for source in rows:
        row = dict(source)
        errors = _row_errors(row)
        student_key = row["student_number"].casefold()
        email = row.get("email") or ""
        email_key = email.casefold()
        program_error = "" if errors else _align_academic_fields(db, row)
        if errors or program_error:
            row["status"] = "invalid"
            row["message"] = " ".join(errors) if errors else program_error
        elif student_key in existing_ids:
            row["status"] = "skipped"
            row["message"] = (
                "This student number is already in the import list. The existing record was left unchanged."
            )
            claimed_ids.add(student_key)
        elif student_key in claimed_ids:
            row["status"] = "skipped"
            row["message"] = "Duplicate student number in this file. Only the first row is imported."
        elif email_key and email_key in claimed_emails:
            row["status"] = "skipped"
            row["message"] = "Duplicate email in this file. Only the first row is imported."
        elif email_key and email_key in existing_emails:
            row["status"] = "skipped"
            row["message"] = (
                "This email is already used by another graduate record. "
                "This row was skipped so the existing record stays unchanged."
            )
        elif (code_conflict := _new_code_conflict(row, introduced_codes)):
            row["status"] = "invalid"
            row["message"] = code_conflict
        else:
            row["status"] = "ready"
            row["message"] = ""
            claimed_ids.add(student_key)
            if email_key:
                claimed_emails.add(email_key)
        classified.append(row)
    return classified


def _locate_table(workbook):
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        for index, raw in enumerate(rows[:20]):
            cells = [_cell_text(value) for value in raw]
            columns = _map_headers(cells)
            if "student_number" in columns and "last_name" in columns:
                missing = [FIELD_LABELS[field] for field in REQUIRED_FIELDS if field not in columns]
                if missing:
                    raise RegistryImportError(
                        "The Excel file is missing required columns: "
                        + ", ".join(missing)
                        + ". Include Student Number, First Name, Middle Name, Last Name, College, Course, and Course Code."
                    )
                return index, columns, rows
    raise RegistryImportError(
        "The Excel file does not include a recognized header row. "
        "Add columns for Student Number, First Name, Middle Name, Last Name, College, Course, and Course Code."
    )


def _read_rows(sheet_rows, header_row: int, columns: dict[str, int]) -> list[dict]:
    parsed = []
    for offset, raw in enumerate(sheet_rows[header_row + 1 :], start=header_row + 2):
        values = [_cell_text(value) for value in raw]
        if not any(values):
            continue
        mapped = {field: _value_at(values, index) for field, index in columns.items()}
        if not any(mapped.get(field) for field in REQUIRED_FIELDS):
            continue
        student_number, student_error = _clean_student_number(mapped.get("student_number", ""))
        first_name, first_error = _clean_name(mapped.get("first_name", ""), "First name", required=True)
        middle_name, middle_error = _clean_name(mapped.get("middle_name", ""), "Middle name", required=False)
        last_name, last_error = _clean_name(mapped.get("last_name", ""), "Last name", required=True)
        college, college_error = _clean_limited(mapped.get("college", ""), "College", 160, required=True)
        course, course_error = _clean_limited(mapped.get("course", ""), "Course", 200, required=True)
        course_code, code_error = _clean_limited(mapped.get("course_code", ""), "Course code", 40, required=True)
        email, email_error = _clean_email(mapped.get("email", ""))
        year_graduated, year_error = _clean_year(mapped.get("year_graduated", ""))
        formula_error = "Replace formulas with values before importing this row." if _has_formula(raw) else ""
        parsed.append(
            {
                "row_number": offset,
                "student_number": student_number,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "college": college,
                "course": course,
                "course_code": course_code,
                "email": email,
                "year_graduated": year_graduated,
                "errors": [
                    message
                    for message in (
                        student_error,
                        first_error,
                        middle_error,
                        last_error,
                        college_error,
                        course_error,
                        code_error,
                        email_error,
                        year_error,
                        formula_error,
                    )
                    if message
                ],
            }
        )
    return parsed


def _row_errors(row: dict) -> list[str]:
    return list(row.get("errors") or [])


def _map_headers(cells: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, cell in enumerate(cells):
        field = _match_header(cell)
        if field and field not in columns:
            columns[field] = index
    return columns


def _match_header(value: str) -> str | None:
    header = _norm_header(value)
    if not header:
        return None
    for field, aliases in HEADER_ALIASES.items():
        if header in aliases:
            return field
    return None


def _norm_header(value: str) -> str:
    text = str(value or "").replace("\n", " ").replace("_", " ").replace("/", " ").replace("-", " ")
    text = text.replace(".", "").replace("#", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _value_at(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return values[index]


def _cell_text(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).replace("\xa0", " ").strip()


def _has_formula(raw) -> bool:
    for value in raw:
        if isinstance(value, str) and value.startswith("="):
            return True
    return False


def _clean_student_number(value: str) -> tuple[str, str]:
    text = " ".join(str(value or "").split())
    if not text:
        return "", "Student number is required."
    if len(text) > 40 or not STUDENT_ID_RE.fullmatch(text):
        return text[:40], "Student number must be 40 characters or fewer and use letters, numbers, spaces, or - / . _."
    return text, ""


def _clean_name(value: str, label: str, required: bool) -> tuple[str, str]:
    text = " ".join(str(value or "").split())
    if not text:
        return "", f"{label} is required." if required else ""
    if any(ord(char) < 32 for char in text):
        return "", f"{label} contains invalid characters."
    if len(text) > 80:
        return text[:80], f"{label} must be 80 characters or fewer."
    return text, ""


def _clean_limited(value: str, label: str, limit: int, required: bool) -> tuple[str, str]:
    text = " ".join(str(value or "").split())
    if not text:
        return "", f"{label} is required." if required else ""
    if any(ord(char) < 32 for char in text):
        return "", f"{label} contains invalid characters."
    if len(text) > limit:
        return text[:limit], f"{label} must be {limit} characters or fewer."
    return text, ""


def _clean_email(value: str) -> tuple[str | None, str]:
    text = str(value or "").strip()
    if not text:
        return None, ""
    try:
        return validate_email(text, check_deliverability=False).normalized.lower(), ""
    except EmailNotValidError:
        return None, "Email must be a valid email address."


def _clean_year(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        text = text[:4]
    if re.fullmatch(r"\d{4}\.0", text):
        text = text[:4]
    if not re.fullmatch(r"\d{4}", text) or not 1950 <= int(text) <= 2100:
        return "", "Year graduated must be a four-digit year."
    return text, ""


def _content_sha256(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        lines.append(
            "|".join(
                [
                    row.get("student_number", "").casefold(),
                    row.get("first_name", "").casefold(),
                    row.get("middle_name", "").casefold(),
                    row.get("last_name", "").casefold(),
                    row.get("college", "").casefold(),
                    row.get("course", "").casefold(),
                    row.get("course_code", "").casefold(),
                    (row.get("email") or "").casefold(),
                    row.get("year_graduated", ""),
                ]
            )
        )
    payload = "\n".join(sorted(lines))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _find_duplicate(db: Session, file_sha256: str, content_sha256: str) -> RegistryImport | None:
    return (
        db.query(RegistryImport)
        .filter(
            (RegistryImport.file_sha256 == file_sha256) | (RegistryImport.content_sha256 == content_sha256)
        )
        .order_by(RegistryImport.created_at.desc(), RegistryImport.id.desc())
        .first()
    )


def _duplicate_message(row: RegistryImport) -> str:
    stamp = _manila_stamp(row.created_at)
    return (
        f"This Excel file has already been imported on {stamp}. "
        "The same records were not imported again."
    )


def _manila_stamp(value: datetime | None) -> str:
    if value is None:
        return "an earlier date"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(MANILA)
    clock = local.strftime("%I:%M %p").lstrip("0")
    return f"{local.strftime('%B')} {local.day}, {local.year} at {clock}"


def _summary(rows: list[dict]) -> dict:
    counts = {"ready": 0, "imported": 0, "skipped": 0, "invalid": 0, "total": len(rows)}
    for row in rows:
        status = row.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def _public_row(row: dict) -> dict:
    return {field: row.get(field, "") if row.get(field) is not None else "" for field in PUBLIC_FIELDS}


def _batch_payload(row: RegistryImport | None) -> dict | None:
    if row is None:
        return None
    return {
        "imported_at": _iso_utc(row.created_at),
        "filename": row.filename or "",
        "imported_count": row.imported_count or 0,
        "skipped_count": row.skipped_count or 0,
        "invalid_count": row.invalid_count or 0,
    }


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _clean_filename(filename: str) -> str:
    base = Path(str(filename or "graduates.xlsx")).name.strip() or "graduates.xlsx"
    return base[:255]
