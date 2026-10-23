"""Alumni rows behind admin dashboard and report snapshots.

Each cohort uses the same records as the figure on screen, so an empty search
returns the same count as that snapshot.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload, subqueryload

from app.services.validation import csv_safe

from app.models import Account, AlignmentResult, AlumniProfile, TracerSubmission, UniversityRecord
from app.services.employment import apply_profile_unemployment, is_no, is_yes
from app.services.reports import (
    NOT_REPORTED_REASON,
    _latest_tracer_rows,
    _matches_filters,
    _record_matches,
    _relatedness,
    _text as report_text,
    _unemployment_reason_labels,
    classify_graduate,
    latest_submissions,
    matches_population,
    parse_report_date,
    prepare_employment_row,
    productivity_membership,
)

_SORT_KEYS = {"name", "student_id", "course", "year_graduated", "status", "employment_status"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _name(account: Account | None) -> str:
    if account is None:
        return ""
    profile = account.profile
    if profile:
        parts = [profile.first_name, profile.middle_name, profile.last_name]
        name = " ".join(part.strip() for part in parts if part and part.strip())
        if name:
            return name
    record = account.university_record
    if record:
        parts = [record.first_name, record.middle_name, record.last_name]
        name = " ".join(part.strip() for part in parts if part and part.strip())
        if name:
            return name
    return account.personal_email or ""


def _course(account: Account | None) -> str:
    if account is None:
        return ""
    record = account.university_record
    profile = account.profile
    if record and _text(record.degree):
        return _text(record.degree)
    if profile and _text(profile.degree):
        return _text(profile.degree)
    if record and _text(record.course_code):
        return _text(record.course_code)
    return ""


def _year(account: Account | None, *, profile_only: bool = False) -> str:
    if account is None:
        return ""
    profile = account.profile
    record = account.university_record
    if profile_only:
        return _text(profile.year_graduated) if profile else ""
    if record and _text(record.year_graduated):
        return _text(record.year_graduated)
    if profile and _text(profile.year_graduated):
        return _text(profile.year_graduated)
    return ""


def _employment_label(data: dict | None) -> str:
    if not data:
        return ""
    answer = data.get("is_currently_employed")
    if is_yes(answer):
        return "Employed"
    if is_no(answer):
        return "Unemployed"
    return "Not reported"


def _prepared(row: TracerSubmission) -> dict:
    profile = row.account.profile if row.account else None
    return apply_profile_unemployment(row.data_json or {}, profile)


def _person(
    account: Account | None,
    *,
    submission: TracerSubmission | None = None,
    employment: str = "",
    year: str | None = None,
) -> dict[str, Any]:
    return {
        "id": account.id if account else (submission.account_id if submission else 0),
        "submission_id": submission.id if submission else None,
        "name": _name(account),
        "email": account.personal_email if account else "",
        "student_id": (account.linked_student_id if account and account.linked_student_id else "")
        or (submission.student_id if submission and submission.student_id else ""),
        "course": _course(account),
        "year_graduated": year if year is not None else _year(account),
        "status": account.status if account else "",
        "employment_status": employment,
    }


def _accounts(db: Session):
    return (
        db.query(Account)
        .options(joinedload(Account.profile), joinedload(Account.university_record))
        .filter(Account.role == "Alumni")
    )


def _latest_map(rows: list[TracerSubmission]) -> dict[int, TracerSubmission]:
    return {row.account_id: row for row in rows if row.account_id}


def _from_account(account: Account, latest: dict[int, TracerSubmission], *, year: str | None = None) -> dict[str, Any]:
    submission = latest.get(account.id)
    data = _prepared(submission) if submission else None
    return _person(account, submission=submission, employment=_employment_label(data), year=year)


def _from_submission(row: TracerSubmission, *, employment: str | None = None, year: str | None = None) -> dict[str, Any]:
    data = _prepared(row)
    return _person(
        row.account,
        submission=row,
        employment=employment if employment is not None else _employment_label(data),
        year=year,
    )


def _cohort(db: Session, **filters: str) -> tuple[str, str, list[dict[str, Any]]]:
    cohort = _text(filters.get("cohort")) or "all"
    status = _text(filters.get("status"))
    alignment = _text(filters.get("alignment"))
    year = _text(filters.get("year"))
    answer = _text(filters.get("answer")).lower()
    reason = _text(filters.get("reason"))
    college = _text(filters.get("college"))
    program = _text(filters.get("program"))
    location = _text(filters.get("location"))
    employment = _text(filters.get("employment"))
    award = _text(filters.get("award"))
    further = _text(filters.get("further"))
    latest = latest_submissions(db)

    if cohort == "all":
        rows = [_from_account(account, _latest_map(latest)) for account in _accounts(db).order_by(Account.id).all()]
        return "All alumni", "Every alumni account on file.", rows

    if cohort == "status":
        if status not in {"Pending", "Active", "Rejected"}:
            raise HTTPException(status_code=400, detail="Choose a pending, active, or rejected account status.")
        titles = {
            "Pending": ("Pending accounts", "Alumni accounts waiting for review."),
            "Active": ("Approved alumni", "Alumni accounts with Active status."),
            "Rejected": ("Rejected accounts", "Alumni accounts that were not approved."),
        }
        title, description = titles[status]
        rows = [
            _from_account(account, _latest_map(latest))
            for account in _accounts(db).filter(Account.status == status).order_by(Account.id).all()
        ]
        return title, description, rows

    if cohort == "employed_overview":
        rows = [
            _from_submission(row, employment="Employed")
            for row in latest
            if _prepared(row).get("is_currently_employed") == "Yes"
        ]
        return "Employed alumni", "Latest tracer records answered currently employed.", rows

    if cohort == "related":
        rows = [
            _from_submission(row)
            for row in latest
            if _relatedness(_prepared(row), row.alignment_status or "") == "related"
        ]
        return "Degree-related jobs", "Latest tracer records whose current work matches the degree.", rows

    if cohort == "alignment":
        if alignment not in {"Aligned", "Unknown", "Misaligned"}:
            raise HTTPException(status_code=400, detail="Choose an alignment category.")
        found = (
            db.query(AlignmentResult)
            .options(
                joinedload(AlignmentResult.account).joinedload(Account.profile),
                joinedload(AlignmentResult.account).joinedload(Account.university_record),
            )
            .filter(AlignmentResult.alignment_justification == alignment)
            .all()
        )
        mapped = _latest_map(latest)
        rows = [_from_account(result.account, mapped) for result in found if result.account]
        return f"{alignment} alumni", f"Alumni whose employment alignment is {alignment}.", rows

    if cohort == "year":
        label = year or "Unknown"
        profiles = (
            db.query(AlumniProfile)
            .options(joinedload(AlumniProfile.account).joinedload(Account.university_record))
            .all()
        )
        mapped = _latest_map(latest)
        rows = []
        for profile in profiles:
            shown = _text(profile.year_graduated) or "Unknown"
            if shown != label or profile.account is None:
                continue
            rows.append(_from_account(profile.account, mapped, year=shown if shown != "Unknown" else ""))
        return f"Batch {label}", f"Alumni profiles recorded for graduation year {label}.", rows

    if cohort == "analytics":
        if answer not in {"all", "employed", "unemployed", "unknown", "known"}:
            raise HTTPException(status_code=400, detail="Choose an employment snapshot.")
        rows = []
        for row in _latest_tracer_rows(db):
            try:
                prepared = prepare_employment_row(row, college, program, year, location, employment)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if prepared is None:
                continue
            data, kind = prepared
            if answer == "known" and kind == "unknown":
                continue
            if answer not in {"all", "known"} and kind != answer:
                continue
            if reason:
                labels = _unemployment_reason_labels(data) if kind == "unemployed" else []
                reported = labels or [NOT_REPORTED_REASON]
                if reason not in reported:
                    continue
            rows.append(_from_submission(row, employment={"employed": "Employed", "unemployed": "Unemployed"}.get(kind, "Not reported")))
        titles = {
            "all": ("Tracer records", "Latest tracer record for each alumnus in this report filter."),
            "employed": ("Employed alumni", "Latest tracer records answered currently employed."),
            "unemployed": ("Unemployed alumni", "Latest tracer records answered not currently employed."),
            "unknown": ("Employment not reported", "Latest tracer records without a Yes or No employment answer."),
            "known": ("Employment rate", "Alumni with a Yes or No answer. The rate is employed divided by this list."),
        }
        title, description = titles[answer]
        if reason:
            title = reason
            description = "Unemployed alumni who reported this reason."
        return title, description, rows

    if cohort == "productivity":
        return _productivity_cohort(db, filters)

    raise HTTPException(status_code=400, detail="Unknown dashboard snapshot.")


def _registry_person(record: UniversityRecord, account: Account | None, latest: dict[int, TracerSubmission]) -> dict[str, Any]:
    if account is not None:
        row = _from_account(account, latest)
        row["student_id"] = row["student_id"] or record.student_id
        row["course"] = row["course"] or report_text(record.degree) or report_text(record.course_code)
        row["year_graduated"] = row["year_graduated"] or report_text(record.year_graduated)
        return row
    parts = [record.first_name, record.middle_name, record.last_name]
    name = " ".join(part.strip() for part in parts if part and part.strip())
    return {
        "id": 0,
        "submission_id": None,
        "name": name or record.personal_email or "",
        "email": record.personal_email or "",
        "student_id": record.student_id or "",
        "course": report_text(record.degree) or report_text(record.course_code),
        "year_graduated": report_text(record.year_graduated),
        "status": "Not registered",
        "employment_status": "",
    }


def _productivity_cohort(db: Session, filters: dict[str, str]) -> tuple[str, str, list[dict[str, Any]]]:
    indicator = report_text(filters.get("indicator"))
    college = report_text(filters.get("college"))
    program = report_text(filters.get("program"))
    year = report_text(filters.get("year"))
    period_from = report_text(filters.get("period_from"))
    period_to = report_text(filters.get("period_to"))
    award = report_text(filters.get("award"))
    further = report_text(filters.get("further"))
    membership = productivity_membership(indicator)
    if membership == "unknown":
        raise HTTPException(status_code=400, detail="Unknown report category.")
    try:
        submitted_from = parse_report_date(period_from)
        submitted_to = parse_report_date(period_to, end_of_day=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Reporting period dates must use YYYY-MM-DD.") from exc
    if submitted_from and submitted_to and submitted_from > submitted_to:
        raise HTTPException(status_code=400, detail="Reporting period start date must be on or before the end date.")

    if membership == "empty":
        return (
            indicator,
            "This indicator is not collected in the Graduate Tracer Survey, so there are no matching records.",
            [],
        )

    if membership == "records":
        latest = _latest_map(latest_submissions(db))
        accounts = {
            account.linked_student_id: account
            for account in (
                _accounts(db)
                .options(subqueryload(Account.awards), subqueryload(Account.studies))
                .all()
            )
            if account.linked_student_id
        }
        rows = []
        for record in db.query(UniversityRecord).all():
            if not _record_matches(record, college, program, year):
                continue
            account = accounts.get(record.student_id)
            submission = latest.get(account.id) if account else None
            data = _prepared(submission) if submission else {}
            if not matches_population(account, data, award, further):
                continue
            rows.append(_registry_person(record, account, latest))
        return indicator, "Graduate registry records counted in this total.", rows

    rows = []
    for row in latest_submissions(db, submitted_from, submitted_to):
        classified = classify_graduate(row)
        if not _matches_filters(classified["context"], college, program, year):
            continue
        if not matches_population(row.account, _prepared(row), award, further):
            continue
        if not membership(classified):
            continue
        rows.append(_from_submission(row))
    return indicator, "Graduates counted in this figure. A percentage on the report uses this list as its numerator.", rows


def _matches_search(row: dict[str, Any], term: str) -> bool:
    if not term:
        return True
    haystack = " ".join(
        str(row.get(key) or "")
        for key in ("name", "email", "student_id", "course", "year_graduated", "status", "employment_status")
    ).lower()
    return term.lower() in haystack


_EXPORT_FIELDS = (
    ("name", "Name"),
    ("student_id", "Student ID"),
    ("email", "Email"),
    ("course", "Course"),
    ("year_graduated", "Batch year"),
    ("status", "Account status"),
    ("employment_status", "Employment"),
)


def _sorted_rows(db: Session, *, q: str, sort_by: str, sort_dir: str, **filters: str):
    title, description, cohort_rows = _cohort(db, **filters)
    term = _text(q)
    matched = [row for row in cohort_rows if _matches_search(row, term)]
    key = sort_by if sort_by in _SORT_KEYS else "name"
    descending = _text(sort_dir).lower() == "desc"
    matched.sort(key=lambda row: (str(row.get(key) or "").lower(), row.get("id") or 0), reverse=descending)
    return title, description, matched, len(cohort_rows), term, key, "desc" if descending else "asc"


def directory_page(db: Session, *, page: int, page_size: int, q: str, sort_by: str, sort_dir: str, **filters: str) -> dict[str, Any]:
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    title, description, matched, snapshot_total, term, key, direction = _sorted_rows(
        db, q=q, sort_by=sort_by, sort_dir=sort_dir, **filters
    )
    start = (page - 1) * page_size
    return {
        "title": title,
        "description": description,
        "items": matched[start:start + page_size],
        "total": len(matched),
        "snapshot_total": snapshot_total,
        "page": page,
        "page_size": page_size,
        "q": term,
        "sort_by": key,
        "sort_dir": direction,
    }


def directory_export_rows(db: Session, *, q: str, sort_by: str, sort_dir: str, **filters: str) -> tuple[str, list[dict[str, Any]]]:
    title, _description, matched, _snapshot, _term, _key, _direction = _sorted_rows(
        db, q=q, sort_by=sort_by, sort_dir=sort_dir, **filters
    )
    return title, matched


def directory_filename(title: str, extension: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "alumni-list").lower()).strip("-") or "alumni-list"
    stamp = datetime.now().strftime("%Y%m%d")
    return f"careersense-{slug}-{stamp}.{extension}"


def render_directory_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([label for _key, label in _EXPORT_FIELDS])
    for row in rows:
        writer.writerow([csv_safe(row.get(key) or "") for key, _label in _EXPORT_FIELDS])
    return output.getvalue()


def render_directory_xlsx(rows: list[dict[str, Any]]) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Alumni"
    sheet.append([label for _key, label in _EXPORT_FIELDS])
    for row in rows:
        sheet.append([csv_safe(row.get(key) or "") for key, _label in _EXPORT_FIELDS])
    sheet.freeze_panes = "A2"
    payload = io.BytesIO()
    book.save(payload)
    return payload.getvalue()
