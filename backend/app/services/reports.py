from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, subqueryload

from app.constants import UNEMPLOYMENT_REASONS
from app.models import Account, TracerSubmission, UniversityRecord
from app.services.employment import is_no, is_yes, resolve_current_employment

SEEKING_REASON = "Looking for a job, but cannot find one"
SELF_EMPLOYED = "Self-Employed"
REGULAR = "Regular/Permanent"
CONTRACTUAL = "Contractual/Casual"

TIME_TO_BUCKET = {
    "Less than a month": "within_3_months",
    "1 to 6 months": "within_6_months",
    "7 to 11 months": "within_12_months",
    "1 year to less than 2 years": "more_than_12_months",
    "2 years to less than 3 years": "more_than_12_months",
    "3 years or more": "more_than_12_months",
}

UNAVAILABLE = {
    "freelance_project_based",
    "employed_locally",
    "employed_internationally",
    "remote_wfh",
    "full_time",
    "part_time",
    "with_benefits",
    "supervisory_managerial",
    "employed_before_graduation",
    "received_promotion",
    "increased_salary",
    "assumed_supervisory",
    "assumed_managerial",
    "higher_level_position",
    "passed_licensure",
    "professional_certification",
    "industry_training",
    "additional_credentials",
    "professional_organizations",
    "professional_awards",
    "top_achievements",
    "published_research",
    "presented_research",
    "academic_award",
    "became_faculty",
    "academic_organizations",
}


def latest_submission_ids(db: Session, submitted_from=None, submitted_to=None):
    query = db.query(func.max(TracerSubmission.id))
    if submitted_from is not None:
        query = query.filter(TracerSubmission.submitted_at >= submitted_from)
    if submitted_to is not None:
        query = query.filter(TracerSubmission.submitted_at <= submitted_to)
    return query.group_by(TracerSubmission.account_id)


def latest_submissions(db: Session, submitted_from=None, submitted_to=None) -> list[TracerSubmission]:
    rows = (
        db.query(TracerSubmission)
        .options(
            joinedload(TracerSubmission.account).joinedload(Account.university_record),
            joinedload(TracerSubmission.account).joinedload(Account.profile),
            joinedload(TracerSubmission.account).subqueryload(Account.studies),
        )
        .filter(TracerSubmission.id.in_(latest_submission_ids(db, submitted_from, submitted_to)))
        .order_by(TracerSubmission.submitted_at.desc())
        .all()
    )
    seen: set[int] = set()
    unique_rows: list[TracerSubmission] = []
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        unique_rows.append(row)
    return unique_rows


def parse_report_date(value: str, *, end_of_day: bool = False) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    parsed = datetime.strptime(raw, "%Y-%m-%d")
    if end_of_day:
        return parsed.replace(hour=23, minute=59, second=59)
    return parsed


def pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def metric(count: int, denominator: int, available: bool = True) -> dict[str, Any]:
    if not available:
        return {"available": False, "count": None, "percentage": None}
    return {"available": True, "count": int(count), "percentage": pct(count, denominator)}


def _yes(value: Any) -> bool:
    return str(value or "").strip().lower() == "yes"


def _no(value: Any) -> bool:
    return str(value or "").strip().lower() == "no"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _reasons(data: dict, key: str) -> list[str]:
    value = data.get(key) or []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _boolish(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if _yes(value):
        return True
    if _no(value):
        return False
    return None


def _current_employment_status(data: dict) -> Optional[str]:
    if not _yes(data.get("is_currently_employed")):
        return None
    if data.get("present_job_is_first") == "No":
        return None
    status = _text(data.get("first_stat"))
    return status or None


def _relatedness(data: dict, alignment_status: str) -> Optional[str]:
    current = resolve_current_employment(data)
    if not current.currently_employed:
        return None
    related = data.get("first_related") if current.present_is_first else data.get("present_related_degree")
    if _yes(related):
        return "related"
    if _no(related):
        return "different"
    status = _text(alignment_status)
    if status == "Aligned":
        return "related"
    if status == "Misaligned":
        return "different"
    return None


def _studies(account: Optional[Account], data: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if account and account.studies:
        for item in account.studies:
            rows.append(
                {
                    "course": _text(item.course_degree),
                    "graduated": item.is_graduated,
                    "scholarship": _text(item.scholarship),
                }
            )
        return rows
    for item in data.get("further_studies") or []:
        if not isinstance(item, dict):
            continue
        course = _text(item.get("course_degree") or item.get("Course/Degree"))
        scholarship = _text(item.get("scholarship") or item.get("Scholarship"))
        graduated = _boolish(item.get("is_graduated", item.get("Graduated")))
        if not any([course, scholarship, _text(item.get("school") or item.get("School"))]):
            continue
        rows.append({"course": course, "graduated": graduated, "scholarship": scholarship})
    return rows


def classify_further_study(course: str, graduated: Optional[bool]) -> str:
    text = (course or "").lower()
    if any(token in text for token in ("ph.d", "phd", "doctor of", "doctoral", "doctorate", "ed.d", "edd")):
        return "completed_doctorate" if graduated else "pursuing_doctorate"
    if any(token in text for token in ("master", "mba", "m.s", "m.a", "msc", "llm")):
        return "completed_masters" if graduated else "pursuing_masters"
    if any(token in text for token in ("certificate", "diploma", "postgraduate", "post-graduate", "post graduate")):
        return "postgrad_cert"
    if any(token in text for token in ("bachelor", "second degree")):
        return "second_degree"
    return "other"


def _person_context(row: TracerSubmission) -> dict[str, Any]:
    account = row.account
    data = row.data_json or {}
    record = account.university_record if account else None
    profile = account.profile if account else None
    college = _text(record.college if record else "")
    program = _text(
        (record.degree if record else "")
        or (profile.degree if profile else "")
        or data.get("degree")
    )
    course_code = _text(record.course_code if record else "")
    year = _text(
        (record.year_graduated if record else "")
        or (profile.year_graduated if profile else "")
        or data.get("year_graduated")
    )
    first = _text(data.get("first_name") or (profile.first_name if profile else ""))
    last = _text(data.get("last_name") or (profile.last_name if profile else ""))
    current = resolve_current_employment(data)
    return {
        "college": college or "Unspecified",
        "program": program or course_code or "Unspecified",
        "year": year or "Unknown",
        "name": " ".join(part for part in (first, last) if part) or "Unnamed graduate",
        "organization": current.employer,
        "position": current.occupation,
    }


def _matches_filters(ctx: dict[str, Any], college: str, program: str, year: str) -> bool:
    if college and ctx["college"] != college:
        return False
    if year and ctx["year"] != year:
        return False
    if program and ctx["program"] != program:
        return False
    return True


def _record_matches(record: UniversityRecord, college: str, program: str, year: str) -> bool:
    ctx = {
        "college": _text(record.college) or "Unspecified",
        "program": _text(record.degree) or _text(record.course_code) or "Unspecified",
        "year": _text(record.year_graduated) or "Unknown",
    }
    return _matches_filters(ctx, college, program, year)


def classify_graduate(row: TracerSubmission) -> dict[str, Any]:
    data = row.data_json or {}
    studies = _studies(row.account, data)
    currently_employed = _yes(data.get("is_currently_employed"))
    status = _current_employment_status(data)
    related = _relatedness(data, row.alignment_status or "")
    reasons = _reasons(data, "reason_current")
    seeking = _no(data.get("is_currently_employed")) and SEEKING_REASON in reasons
    not_seeking = _no(data.get("is_currently_employed")) and not seeking
    academic_flags: set[str] = set()
    has_scholarship = False
    for item in studies:
        bucket = classify_further_study(item["course"], item["graduated"])
        academic_flags.add(bucket)
        if item["scholarship"]:
            has_scholarship = True
    if _yes(data.get("enroll_further_studies")) and not academic_flags:
        academic_flags.add("other")

    workforce = currently_employed
    professional = currently_employed and status == SELF_EMPLOYED
    academic = bool(academic_flags) or _yes(data.get("enroll_further_studies"))
    productive = workforce or professional or academic
    dimensions = sum(1 for flag in (workforce, professional, academic) if flag)

    return {
        "currently_employed": currently_employed,
        "employment_status": status,
        "self_employed": currently_employed and status == SELF_EMPLOYED,
        "wage_employed": currently_employed and status != SELF_EMPLOYED,
        "unemployed_seeking": seeking,
        "unemployed_not_seeking": not_seeking,
        "relatedness": related,
        "permanent": currently_employed and status == REGULAR,
        "contractual": currently_employed and status == CONTRACTUAL,
        "time_bucket": TIME_TO_BUCKET.get(_text(data.get("time_to_first_job"))),
        "academic_flags": academic_flags,
        "has_scholarship": has_scholarship,
        "workforce": workforce,
        "professional": professional,
        "academic": academic,
        "productive": productive,
        "multiple": dimensions >= 2,
        "context": _person_context(row),
    }


UNKNOWN_EMPLOYMENT = "Unknown / Not Reported"
NOT_REPORTED_REASON = "Not reported"


def filter_options(db: Session) -> dict[str, Any]:
    records = db.query(UniversityRecord).all()
    colleges = sorted({_text(row.college) for row in records if _text(row.college)})
    programs = sorted({_text(row.degree) for row in records if _text(row.degree)})
    years = sorted({_text(row.year_graduated) for row in records if _text(row.year_graduated)}, reverse=True)
    seen: set[tuple[str, str]] = set()
    pairs = []
    for row in records:
        college = _text(row.college)
        program = _text(row.degree)
        key = (college, program)
        if key in seen or not (college or program):
            continue
        seen.add(key)
        pairs.append({"college": college, "program": program})
    pairs.sort(key=lambda item: (item["college"], item["program"]))
    return {"colleges": colleges, "programs": programs, "years": years, "pairs": pairs}


def _latest_tracer_rows(db: Session) -> list[TracerSubmission]:
    """Latest submission per alumnus, with the registry fields needed for filters."""
    rows = (
        db.query(TracerSubmission)
        .options(
            joinedload(TracerSubmission.account).joinedload(Account.university_record),
            joinedload(TracerSubmission.account).joinedload(Account.profile),
        )
        .filter(TracerSubmission.id.in_(latest_submission_ids(db)))
        .all()
    )
    seen: set[int] = set()
    unique: list[TracerSubmission] = []
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        unique.append(row)
    return unique


def _academic_context(row: TracerSubmission) -> dict[str, str]:
    """College, course, and year from the same sources as the OAAPS report."""
    account = row.account
    data = row.data_json or {}
    record = account.university_record if account else None
    profile = account.profile if account else None
    program = _text(
        (record.degree if record else "")
        or (profile.degree if profile else "")
        or data.get("degree")
    )
    year = _text(
        (record.year_graduated if record else "")
        or (profile.year_graduated if profile else "")
        or data.get("year_graduated")
    )
    return {
        "college": _text(record.college if record else "") or "Unspecified",
        "program": program or _text(record.course_code if record else "") or "Unspecified",
        "year": year or "Unknown",
    }


def _unemployment_reason_labels(data: dict) -> list[str]:
    """Configured checkbox answers only. Free-text 'please specify' is not a category."""
    labels: list[str] = []
    for raw in _reasons(data, "reason_current"):
        label = _text(raw)
        if not label or label in labels:
            continue
        labels.append(label)
    return labels


def employment_analytics(
    db: Session,
    *,
    college: str = "",
    program: str = "",
    year: str = "",
) -> dict[str, Any]:
    """Aggregate official submitted GTS employment answers.

    Employment rate is employed / (employed + unemployed). Records with no
    reliable Yes/No answer are Unknown and are left out of that denominator.
    Unemployment reasons count only records answered No. A graduate who
    selects more than one reason is counted in each selected category.
    """
    college = _text(college)
    program = _text(program)
    year = _text(year)
    employed = 0
    unemployed = 0
    unknown = 0
    reason_counts: dict[str, int] = defaultdict(int)

    for row in _latest_tracer_rows(db):
        if not _matches_filters(_academic_context(row), college, program, year):
            continue
        data = row.data_json or {}
        answer = data.get("is_currently_employed")
        if is_yes(answer):
            employed += 1
            continue
        if not is_no(answer):
            unknown += 1
            continue
        unemployed += 1
        labels = _unemployment_reason_labels(data)
        if not labels:
            reason_counts[NOT_REPORTED_REASON] += 1
            continue
        for label in labels:
            reason_counts[label] += 1

    total = employed + unemployed + unknown
    known = employed + unemployed
    status = [
        {"label": "Employed", "count": employed, "percent": pct(employed, total)},
        {"label": "Unemployed", "count": unemployed, "percent": pct(unemployed, total)},
    ]
    if unknown:
        status.append({"label": UNKNOWN_EMPLOYMENT, "count": unknown, "percent": pct(unknown, total)})

    ordered = list(UNEMPLOYMENT_REASONS) + [NOT_REPORTED_REASON]
    reasons = [{"label": label, "count": reason_counts[label]} for label in ordered if reason_counts.get(label)]
    extras = sorted(label for label in reason_counts if label not in ordered)
    reasons.extend({"label": label, "count": reason_counts[label]} for label in extras)

    return {
        "total": total,
        "employed": employed,
        "unemployed": unemployed,
        "unknown": unknown,
        "employment_rate": pct(employed, known),
        "status": status if total else [],
        "reasons": reasons if unemployed else [],
    }


def _header_labels(college: str, program: str, year: str, period_from: str, period_to: str) -> dict[str, str]:
    if period_from and period_to:
        period = f"{period_from} to {period_to}"
    elif period_from:
        period = f"From {period_from}"
    elif period_to:
        period = f"Through {period_to}"
    else:
        period = "All records"
    if college and program:
        college_program = f"{college} / {program}"
    elif college:
        college_program = college
    elif program:
        college_program = program
    else:
        college_program = "All colleges/programs"
    return {
        "reporting_period": period,
        "batch_cohort": year or "All batches",
        "college_program": college_program,
    }


def build_oaaps_report(
    db: Session,
    *,
    college: str = "",
    program: str = "",
    year: str = "",
    period_from: str = "",
    period_to: str = "",
    submitted_from=None,
    submitted_to=None,
) -> dict[str, Any]:
    college = _text(college)
    program = _text(program)
    year = _text(year)
    labels = _header_labels(college, program, year, _text(period_from), _text(period_to))

    records = [
        row
        for row in db.query(UniversityRecord).all()
        if _record_matches(row, college, program, year)
    ]
    total_graduates = len(records)

    people = []
    for row in latest_submissions(db, submitted_from, submitted_to):
        classified = classify_graduate(row)
        if not _matches_filters(classified["context"], college, program, year):
            continue
        people.append(classified)

    traced = len(people)
    employed = sum(1 for item in people if item["currently_employed"])
    professional_n = sum(1 for item in people if item["professional"])
    academic_n = sum(1 for item in people if item["academic"])
    multiple_n = sum(1 for item in people if item["multiple"])
    productive_n = sum(1 for item in people if item["productive"])
    workforce_n = sum(1 for item in people if item["workforce"])
    denom = traced

    executive = [
        {"indicator": "Total Graduates", **metric(total_graduates, total_graduates or 1), "percentage": 100.0 if total_graduates else 0.0},
        {"indicator": "Graduates Traced", **metric(traced, total_graduates)},
        {"indicator": "Employed Graduates", **metric(employed, denom)},
        {"indicator": "Graduates with Professional Advancement", **metric(professional_n, denom)},
        {"indicator": "Graduates Pursuing Further Studies", **metric(academic_n, denom)},
        {"indicator": "Graduates with Multiple Productivity Indicators", **metric(multiple_n, denom)},
        {"indicator": "Overall Graduate Productivity Rate", **metric(productive_n, denom)},
    ]
    if total_graduates:
        executive[0]["percentage"] = 100.0

    employment_status = [
        {"indicator": "Employed", **metric(sum(1 for item in people if item["wage_employed"]), denom)},
        {"indicator": "Self-Employed / Entrepreneur", **metric(sum(1 for item in people if item["self_employed"]), denom)},
        {"indicator": "Freelance / Project-Based", **metric(0, denom, available=False)},
        {
            "indicator": "Unemployed – Seeking Employment",
            **metric(sum(1 for item in people if item["unemployed_seeking"]), denom),
        },
        {
            "indicator": "Not Seeking Employment",
            **metric(sum(1 for item in people if item["unemployed_not_seeking"]), denom),
        },
        {"indicator": "Total Traced", **metric(traced, denom), "percentage": 100.0 if traced else 0.0},
    ]

    employment_relevance = [
        {
            "indicator": "Employed in a field related to degree",
            **metric(sum(1 for item in people if item["relatedness"] == "related"), denom),
        },
        {
            "indicator": "Employed in a different field",
            **metric(sum(1 for item in people if item["relatedness"] == "different"), denom),
        },
        {"indicator": "Employed locally", **metric(0, denom, available=False)},
        {"indicator": "Employed internationally", **metric(0, denom, available=False)},
        {"indicator": "Remote/Work-from-Home", **metric(0, denom, available=False)},
    ]

    employment_quality = [
        {"indicator": "Full-Time Employment", **metric(0, denom, available=False)},
        {"indicator": "Part-Time Employment", **metric(0, denom, available=False)},
        {"indicator": "Permanent/Regular", **metric(sum(1 for item in people if item["permanent"]), denom)},
        {"indicator": "Contractual/Project-Based", **metric(sum(1 for item in people if item["contractual"]), denom)},
        {"indicator": "With Benefits", **metric(0, denom, available=False)},
        {"indicator": "Supervisory/Managerial Position", **metric(0, denom, available=False)},
    ]

    time_to_employment = [
        {"indicator": "Employed before graduation", **metric(0, denom, available=False)},
        {
            "indicator": "Employed within 3 months",
            **metric(sum(1 for item in people if item["time_bucket"] == "within_3_months"), denom),
        },
        {
            "indicator": "Employed within 6 months",
            **metric(sum(1 for item in people if item["time_bucket"] == "within_6_months"), denom),
        },
        {
            "indicator": "Employed within 12 months",
            **metric(sum(1 for item in people if item["time_bucket"] == "within_12_months"), denom),
        },
        {
            "indicator": "More than 12 months",
            **metric(sum(1 for item in people if item["time_bucket"] == "more_than_12_months"), denom),
        },
    ]

    career_progression = [
        {"indicator": "Received Promotion", **metric(0, denom, available=False)},
        {"indicator": "Increased Salary/Compensation", **metric(0, denom, available=False)},
        {"indicator": "Assumed Supervisory Role", **metric(0, denom, available=False)},
        {"indicator": "Assumed Managerial/Leadership Role", **metric(0, denom, available=False)},
        {"indicator": "Changed to Higher-Level Position", **metric(0, denom, available=False)},
        {"indicator": "Established Own Business", **metric(professional_n, denom)},
    ]

    credentials = [
        {"indicator": "Passed Licensure/Board Examination", **metric(0, denom, available=False)},
        {"indicator": "Obtained Professional Certification", **metric(0, denom, available=False)},
        {"indicator": "Completed Industry Training", **metric(0, denom, available=False)},
        {"indicator": "Obtained Additional Professional Credentials", **metric(0, denom, available=False)},
        {"indicator": "Participated in Professional Organizations", **metric(0, denom, available=False)},
        {"indicator": "Received Professional/Industry Awards", **metric(0, denom, available=False)},
    ]

    further_education = [
        {
            "indicator": "Pursuing Master’s Degree",
            **metric(sum(1 for item in people if "pursuing_masters" in item["academic_flags"]), denom),
        },
        {
            "indicator": "Completed Master’s Degree",
            **metric(sum(1 for item in people if "completed_masters" in item["academic_flags"]), denom),
        },
        {
            "indicator": "Pursuing Doctorate",
            **metric(sum(1 for item in people if "pursuing_doctorate" in item["academic_flags"]), denom),
        },
        {
            "indicator": "Completed Doctorate",
            **metric(sum(1 for item in people if "completed_doctorate" in item["academic_flags"]), denom),
        },
        {
            "indicator": "Pursuing Postgraduate Certificate/Diploma",
            **metric(sum(1 for item in people if "postgrad_cert" in item["academic_flags"]), denom),
        },
        {
            "indicator": "Pursuing Second Degree",
            **metric(sum(1 for item in people if "second_degree" in item["academic_flags"]), denom),
        },
        {
            "indicator": "Other Further Studies",
            **metric(sum(1 for item in people if "other" in item["academic_flags"]), denom),
        },
    ]

    academic_achievements = [
        {"indicator": "Published Research", **metric(0, denom, available=False)},
        {"indicator": "Presented Research", **metric(0, denom, available=False)},
        {"indicator": "Received Academic Award", **metric(0, denom, available=False)},
        {
            "indicator": "Received Scholarship/Fellowship",
            **metric(sum(1 for item in people if item["has_scholarship"]), denom),
        },
        {"indicator": "Became Faculty/Educator", **metric(0, denom, available=False)},
        {"indicator": "Participated in Academic/Research Organizations", **metric(0, denom, available=False)},
    ]

    workforce_rate = pct(workforce_n, denom)
    professional_rate = pct(professional_n, denom)
    academic_rate = pct(academic_n, denom)
    overall_rate = pct(productive_n, denom)

    scorecard = [
        {
            "dimension": "Workforce Integration",
            "key_indicator": "Graduates productively employed/engaged",
            "target": None,
            "actual_rate": workforce_rate,
            "status": None,
        },
        {
            "dimension": "Professional Advancement",
            "key_indicator": "Graduates with career/professional advancement",
            "target": None,
            "actual_rate": professional_rate,
            "status": None,
        },
        {
            "dimension": "Academic Advancement",
            "key_indicator": "Graduates pursuing/completing further studies",
            "target": None,
            "actual_rate": academic_rate,
            "status": None,
        },
        {
            "dimension": "Overall Productivity",
            "key_indicator": "Graduates demonstrating ≥1 productivity outcome",
            "target": None,
            "actual_rate": overall_rate,
            "status": None,
        },
    ]

    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {
            "graduates": 0,
            "traced": 0,
            "workforce": 0,
            "professional": 0,
            "academic": 0,
            "productive": 0,
        }
    )
    for record in records:
        key = (
            _text(record.college) or "Unspecified",
            _text(record.degree) or _text(record.course_code) or "Unspecified",
            _text(record.year_graduated) or "Unknown",
        )
        grouped[key]["graduates"] += 1
    for item in people:
        ctx = item["context"]
        key = (ctx["college"], ctx["program"], ctx["year"])
        grouped[key]["traced"] += 1
        grouped[key]["workforce"] += int(item["workforce"])
        grouped[key]["professional"] += int(item["professional"])
        grouped[key]["academic"] += int(item["academic"])
        grouped[key]["productive"] += int(item["productive"])

    by_program = []
    for (college_name, program_name, batch), values in sorted(grouped.items()):
        row_traced = values["traced"]
        by_program.append(
            {
                "college_program": f"{college_name} / {program_name}",
                "batch_year": batch,
                "graduates": values["graduates"],
                "traced": row_traced,
                "workforce": metric(values["workforce"], row_traced),
                "professional": metric(values["professional"], row_traced),
                "academic": metric(values["academic"], row_traced),
                "overall_productivity": metric(values["productive"], row_traced),
            }
        )
    by_program.append(
        {
            "college_program": "TOTAL",
            "batch_year": "",
            "graduates": total_graduates,
            "traced": traced,
            "workforce": metric(workforce_n, denom),
            "professional": metric(professional_n, denom),
            "academic": metric(academic_n, denom),
            "overall_productivity": metric(productive_n, denom),
            "is_total": True,
        }
    )

    return {
        "title": "OVERALL GRADUATE PRODUCTIVITY REPORT",
        "header": {
            **labels,
            "total_graduates": total_graduates,
            "graduates_traced": traced,
            "response_rate": metric(traced, total_graduates),
        },
        "filters": {
            "college": college,
            "program": program,
            "year": year,
            "period_from": _text(period_from),
            "period_to": _text(period_to),
        },
        "options": filter_options(db),
        "executive_summary": executive,
        "overall_productivity_rate": overall_rate,
        "profile": {
            "total_graduates": total_graduates,
            "traced": traced,
            "productive": productive_n,
            "not_yet_engaged": max(traced - productive_n, 0),
        },
        "distribution": {
            "workforce": workforce_rate,
            "professional": professional_rate,
            "academic": academic_rate,
        },
        "workforce": {
            "description": "Measures the extent to which graduates successfully enter and participate in the workforce.",
            "employment_status": employment_status,
            "employment_relevance": employment_relevance,
            "employment_quality": employment_quality,
            "time_to_employment": time_to_employment,
            "key_rate": workforce_rate,
        },
        "professional": {
            "description": "Measures the career growth, professional development, and achievements of graduates after entering the workforce.",
            "career_progression": career_progression,
            "credentials": credentials,
            "achievements": [],
            "achievements_available": False,
            "key_rate": professional_rate,
        },
        "academic": {
            "description": "Measures graduates who pursue further education, specialization, research, and academic achievement.",
            "further_education": further_education,
            "achievements": academic_achievements,
            "key_rate": academic_rate,
        },
        "scorecard": scorecard,
        "by_program": by_program,
        "unavailable_indicators": sorted(UNAVAILABLE),
        "formula": (
            "Overall Graduate Productivity Rate = "
            "Number of graduates with at least one productivity outcome "
            "÷ Number of graduates successfully traced × 100"
        ),
    }
