"""Resume extraction, normalization, and Graduate Tracer Survey field mapping.

Architecture:
  upload → validate → LlamaParse, then local text/OCR → built-in field parser
  → optional structured model when the first pass is incomplete
  → reconcile → normalize → GTS mapping → alumni review

Time-to-first-job uses the OAAPS June graduation assumption. That month is not
read from the resume. A year-only start date is placed in July only for that
bucket, and the result is marked as an estimate.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.constants import EMPLOYMENT_STATUS_OPTIONS, SALARY_OPTIONS
from app.services.employment import infer_present_job_is_first
from app.services.parser_course import (
    CourseAlignment,
    align_occupation_to_degree,
    related_yes_no,
    select_current_experience,
)
from app.services.parser_document import (
    DocumentView,
    assess_text_quality,
    extract_document,
    text_is_sufficient,
)
from app.services.parser_extract import (
    assess_extraction,
    evidence_excerpt,
    extract_heuristic,
    field_evidenced,
    further_studies_evidence,
    needs_deeper_extraction,
    _is_page_furniture,
    parse_date_range,
    parse_date_token,
)
from app.services.parser_llm import extract_with_llm as _extract_with_llm
from app.services.parser_llm import parse_with_llamaparse

EMPLOYMENT_STATUS_HINTS = {
    "regular": "Regular/Permanent",
    "permanent": "Regular/Permanent",
    "probationary": "Probationary",
    "probation": "Probationary",
    "contractual": "Contractual/Casual",
    "casual": "Contractual/Casual",
    "contract": "Contractual/Casual",
    "self-employed": "Self-Employed",
    "self employed": "Self-Employed",
}


def extract_text_from_bytes(filename: str, file_bytes: bytes) -> str:
    return extract_document(filename, file_bytes).text


def extract_resume_from_upload(filename: str, file_bytes: bytes) -> tuple[Dict[str, Any], str, str]:
    llama_text = parse_with_llamaparse(filename, file_bytes)
    if llama_text and text_is_sufficient(llama_text):
        document = DocumentView.from_text(llama_text, filename=filename or "resume.pdf", source="llamaparse")
        parsed, source = extract_resume_info(document.text, document=document)
        return parsed, source, document.text
    document = extract_document(filename, file_bytes)
    parsed, source = extract_resume_info(document.text, document=document)
    return parsed, source, document.text


def _as_yes_no(value: Any, default: str = "") -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"yes", "y", "true", "1", "current", "present", "now", "ongoing"}:
            return "Yes"
        if cleaned in {"no", "n", "false", "0"}:
            return "No"
    return default


def _normalize_name_case(name: str) -> str:
    if not name:
        return ""
    parts = [part for part in name.strip().split() if part]
    normalized = []
    for part in parts:
        if re.fullmatch(r"[A-Za-z]\.", part):
            normalized.append(part.upper())
            continue
        suffix = re.fullmatch(r"(jr|sr|ii|iii|iv)\.?", part, re.I)
        if suffix:
            label = {"jr": "Jr.", "sr": "Sr.", "ii": "II", "iii": "III", "iv": "IV"}[suffix.group(1).lower()]
            normalized.append(label)
            continue
        sub_parts = re.split(r"([\-'])", part.lower())
        sub_parts = [item.capitalize() if item not in {"-", "'"} else item for item in sub_parts]
        normalized.append("".join(sub_parts))
    return " ".join(normalized)


def _normalize_degree_text(degree: str) -> str:
    if not degree:
        return ""
    text = re.sub(r"\s+", " ", degree.strip())
    text = " ".join(word.capitalize() for word in text.split())
    acronym_fixes = {
        "It": "IT", "Mis": "MIS", "Ict": "ICT", "Bs": "BS", "Ba": "BA",
        "Sql": "SQL", "Ui": "UI", "Ux": "UX", "Bsit": "BSIT", "Bscs": "BSCS",
        "Bsis": "BSIS", "Bsn": "BSN", "Rn": "RN", "Mba": "MBA", "Phd": "PhD",
    }
    for src, dst in acronym_fixes.items():
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text)
    return text


def _infer_related_to_degree(
    job_title: str,
    degree: str,
    *,
    description: str = "",
    employer: str = "",
    skills: Optional[List[str]] = None,
) -> str:
    return related_yes_no(
        degree,
        job_title,
        description=description,
        employer=employer,
        skills=skills or [],
    )


def _infer_employment_status(job_title: str, is_current: str) -> str:
    title = (job_title or "").lower()
    if re.search(r"\bintern(ship)?\b|ojt|trainee|apprentice", title):
        return "Contractual/Casual"
    if re.search(r"self[- ]?employed|freelance", title):
        return "Self-Employed"
    return ""


def _normalize_employment_status(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()
    if cleaned in EMPLOYMENT_STATUS_OPTIONS:
        return cleaned
    lowered = cleaned.lower()
    for key, mapped in EMPLOYMENT_STATUS_HINTS.items():
        if key in lowered:
            return mapped
    return ""


def _normalize_salary_range(value: Any) -> str:
    if isinstance(value, str) and value.strip() in SALARY_OPTIONS:
        return value.strip()
    return ""


def _safe_year(value: Any) -> str:
    if value is None:
        return ""
    match = re.search(r"(19|20)\d{2}", str(value).strip())
    return match.group(0) if match else ""


def _normalize_stored_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if re.search(r"\b(present|current|now|ongoing)\b", text, re.I):
        return ""
    token = parse_date_token(text)
    if token == "present":
        return ""
    return token


def _date_rank(date_text: str) -> tuple:
    match = re.search(r"((19|20)\d{2})(?:[-/](\d{1,2}))?", date_text or "")
    if not match:
        return (9999, 99)
    return (int(match.group(1)), int(match.group(3) or 1))


def _parse_year_month(date_text: str) -> Optional[tuple]:
    match = re.search(r"((19|20)\d{2})(?:[-/](\d{1,2}))?", str(date_text or ""))
    if not match:
        return None
    month = int(match.group(3) or 1)
    if month < 1 or month > 12:
        month = 1
    return (int(match.group(1)), month)


def _months_between(start_ym: tuple, end_ym: tuple) -> int:
    return max(0, (end_ym[0] - start_ym[0]) * 12 + (end_ym[1] - start_ym[1]))


def _has_month(date_text: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])", str(date_text or "").strip()))


def _bucket_from_months(diff: int) -> str:
    if diff < 1:
        return "Less than a month"
    if diff <= 6:
        return "1 to 6 months"
    if diff <= 11:
        return "7 to 11 months"
    if diff < 24:
        return "1 year to less than 2 years"
    if diff < 36:
        return "2 years to less than 3 years"
    return "3 years or more"


def _employment_wait_bucket(year_graduated: str, first_start_date: str) -> str:
    grad_year = _safe_year(year_graduated)
    first_start = _parse_year_month(first_start_date)
    if not grad_year or not first_start:
        return ""
    if not _has_month(first_start_date):
        # Year only: place the start in July, the month after the June graduation assumption.
        return _bucket_from_months(_months_between((int(grad_year), 6), (first_start[0], 7)))
    return _bucket_from_months(_months_between((int(grad_year), 6), first_start))


def _spans_after_graduation(job: dict, year_graduated: str) -> bool:
    """True when this role was held on or after the June graduation assumed by the survey."""
    year = _safe_year(year_graduated)
    if not year or not isinstance(job, dict):
        return True
    cutoff = int(year)

    def _on_or_after(raw) -> bool:
        parsed = _parse_year_month(raw)
        if not parsed:
            return False
        if parsed[0] > cutoff:
            return True
        if parsed[0] < cutoff:
            return False
        return not _has_month(raw) or parsed[1] >= 6

    if _on_or_after(job.get("start_date")):
        return True
    if str(job.get("is_current") or "") == "Yes":
        start = _parse_year_month(job.get("start_date"))
        return start is None or start[0] <= cutoff
    return _on_or_after(job.get("end_date"))


def jobs_after_graduation(experiences: List[dict], year_graduated: str) -> List[dict]:
    rows = [job for job in experiences if isinstance(job, dict)]
    if not _safe_year(year_graduated):
        return rows
    return [job for job in rows if _spans_after_graduation(job, year_graduated)]


def _job_timing(job: dict, year_graduated: str) -> str:
    """after, before, or unknown relative to the June graduation assumption."""
    if not isinstance(job, dict):
        return "unknown"
    if not _safe_year(year_graduated):
        return "after"
    if _spans_after_graduation(job, year_graduated):
        return "after"
    if str(job.get("is_current") or "") == "Yes":
        return "after"
    if not _parse_year_month(job.get("start_date")) and not _parse_year_month(job.get("end_date")):
        return "unknown"
    return "before"


def employment_after_graduation_status(experiences: List[dict], year_graduated: str) -> str:
    """yes, no, or unknown. Unknown means the resume did not establish post-graduation work.

    ``no`` is used only when every extracted job is dated before the assumed graduation.
    A job the parser could not date does not by itself mean the alumnus was unemployed.
    """
    rows = [job for job in experiences if isinstance(job, dict)]
    if not rows:
        return "unknown"
    timings = [_job_timing(job, year_graduated) for job in rows]
    if "after" in timings:
        return "yes"
    if "unknown" in timings:
        return "unknown"
    if timings and all(item == "before" for item in timings):
        return "no"
    return "unknown"


def _ever_employed_from_jobs(experiences: List[dict], year_graduated: str, explicit: Any = "") -> str:
    status = employment_after_graduation_status(experiences, year_graduated)
    if status == "yes":
        return "Yes"
    if status == "no":
        return "No"
    return _as_yes_no(explicit, default="")


def _clean_credentials(rows: Any) -> List[dict]:
    cleaned: List[dict] = []
    seen: set[str] = set()
    if not isinstance(rows, list):
        return cleaned
    for row in rows:
        if isinstance(row, str):
            name, detail, year = row.strip(), "", ""
            awarding_body = location = organizer = issuer = description = ""
        elif isinstance(row, dict):
            name = str(row.get("name") or row.get("title") or "").strip()
            year = _safe_year(row.get("year") or row.get("awarded_on") or row.get("held_on"))
            awarding_body = str(row.get("awarding_body") or "").strip()
            location = str(row.get("location") or "").strip()
            organizer = str(row.get("organizer") or "").strip()
            issuer = str(row.get("issuer") or "").strip()
            description = str(row.get("description") or "").strip()
            detail = str(row.get("detail") or "").strip()
            if re.fullmatch(r"(?:19|20)\d{2}", detail):
                year = year or detail
                detail = ""
            if not awarding_body and detail and not location and not organizer and not issuer:
                awarding_body = detail
            if not issuer and detail and not awarding_body:
                issuer = detail
            if not location and detail and not awarding_body and not issuer:
                location = detail
        else:
            continue
        if _is_page_furniture(name):
            continue
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        if not detail:
            detail = awarding_body or issuer or location
        cleaned.append({
            "name": name[:180],
            "detail": detail[:180],
            "year": year,
            "awarding_body": awarding_body[:180],
            "location": location[:180],
            "organizer": organizer[:180],
            "issuer": issuer[:180],
            "description": description[:800],
        })
    return cleaned


def _format_length_of_stay(start_date: str, end_date: str, is_current: str) -> str:
    start_ym = _parse_year_month(start_date)
    if not start_ym:
        return ""
    if is_current == "Yes":
        today = date.today()
        end_ym = (today.year, today.month)
    else:
        parsed_end = _parse_year_month(end_date)
        if not parsed_end:
            return ""
        end_ym = parsed_end
    total_months = _months_between(start_ym, end_ym)
    years, months = divmod(total_months, 12)
    if years and months:
        return f"{years} year(s) and {months} month(s)"
    if years:
        return f"{years} year(s)"
    return f"{months} month(s)"


def _titles_refine(left: str, right: str) -> bool:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _merge_experiences(primary: List[Dict[str, str]], fallback: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not primary:
        return [dict(item) for item in fallback]
    merged = [dict(item) for item in primary]
    used = set()
    for fb in fallback:
        matched = False
        for index, row in enumerate(merged):
            if index in used:
                continue
            same_employer = row.get("employer", "").strip().lower() == fb.get("employer", "").strip().lower()
            related = _titles_refine(row.get("job_title", ""), fb.get("job_title", ""))
            left_start = str(row.get("start_date") or "")[:4]
            right_start = str(fb.get("start_date") or "")[:4]
            different_stint = bool(left_start and right_start and left_start != right_start)
            if different_stint:
                continue
            if related and (same_employer or not row.get("employer") or not fb.get("employer")):
                if len((fb.get("job_title") or "").strip()) > len((row.get("job_title") or "").strip()):
                    row["job_title"] = fb.get("job_title", "")
                for key, value in fb.items():
                    if key == "job_title":
                        continue
                    if not row.get(key) and value:
                        row[key] = value
                used.add(index)
                matched = True
                break
        if not matched:
            merged.append(dict(fb))
    return merged


def _confidence_label(value: str, resume_text: str, extra: bool = False) -> str:
    if not value:
        return "low"
    if not field_evidenced(value, resume_text):
        return "low"
    needle = re.sub(r"\s+", " ", value.strip().lower())
    haystack = re.sub(r"\s+", " ", (resume_text or "").lower())
    if needle and needle in haystack:
        return "high"
    return "medium"


def _pick_value(
    ai_value: Any,
    heuristic_value: Any,
    resume_text: str,
    *,
    field_name: str = "",
    warnings: Optional[List[str]] = None,
) -> tuple[str, str]:
    left = str(ai_value or "").strip()
    right = str(heuristic_value or "").strip()
    if left and right and left.lower() == right.lower():
        return right or left, "high"
    if left and right:
        left_ok = field_evidenced(left, resume_text)
        right_ok = field_evidenced(right, resume_text)
        if right_ok and left_ok and left.lower() != right.lower():
            if left.lower() in right.lower() or right.lower() in left.lower():
                longer = left if len(left) >= len(right) else right
                return longer, "high"
            if warnings is not None and field_name:
                warnings.append(f"conflict:{field_name}")
                warnings.append(f"conflict_detail:{field_name}|{left}|{right}")
            return right, "medium"
        if right_ok and not left_ok:
            return right, "medium"
        if left_ok and not right_ok:
            return left, "medium"
        return "", "low"
    chosen = left or right
    if not chosen:
        return "", "low"
    if left and not field_evidenced(chosen, resume_text):
        return right, _confidence_label(right, resume_text) if right else "low"
    return chosen, _confidence_label(chosen, resume_text, extra=bool(left and right))


def _heuristic_job_keys(jobs: List[Dict[str, str]]) -> set[tuple[str, str]]:
    return {
        (str(job.get("job_title") or "").strip().lower(), str(job.get("employer") or "").strip().lower())
        for job in jobs
    }


def _keep_reconciled_job(job: Dict[str, Any], heuristic_keys: set[tuple[str, str]], resume_text: str) -> bool:
    title = str(job.get("job_title") or "").strip()
    employer = str(job.get("employer") or "").strip()
    key = (title.lower(), employer.lower())
    if key in heuristic_keys or (title.lower(), "") in heuristic_keys:
        return True
    if any(title.lower() == existing[0] and title for existing in heuristic_keys):
        return True
    return bool(title and employer and field_evidenced(title, resume_text) and field_evidenced(employer, resume_text))


def reconcile_extractions(ai_data: Optional[Dict[str, Any]], heuristic: Dict[str, Any], resume_text: str) -> tuple[Dict[str, Any], Dict[str, str]]:
    ai_data = ai_data or {}
    merged: Dict[str, Any] = {}
    confidence: Dict[str, str] = {}
    warnings: List[str] = []
    conflicts: List[dict] = []
    rejections: List[dict] = []
    for key in ("first_name", "middle_name", "last_name", "country", "degree", "year_graduated"):
        value, level = _pick_value(
            ai_data.get(key),
            heuristic.get(key),
            resume_text,
            field_name=key,
            warnings=warnings,
        )
        merged[key] = value
        confidence[key] = level

    ai_jobs = ai_data.get("experiences") if isinstance(ai_data.get("experiences"), list) else []
    heuristic_jobs = heuristic.get("experiences") if isinstance(heuristic.get("experiences"), list) else []
    cleaned_ai = []
    for job in ai_jobs:
        if not isinstance(job, dict):
            continue
        title = str(job.get("job_title") or "").strip()
        employer = str(job.get("employer") or "").strip()
        if title and not field_evidenced(title, resume_text):
            rejections.append({
                "field": "job_title",
                "value": title,
                "reason": "The title is not supported by the resume text.",
            })
            continue
        if employer and not field_evidenced(employer, resume_text):
            rejections.append({
                "field": "employer",
                "value": employer,
                "reason": "The employer is not supported by the resume text.",
            })
            job = {**job, "employer": ""}
        cleaned_ai.append(job)
    if heuristic_jobs:
        merged_jobs = _merge_experiences(heuristic_jobs, cleaned_ai)
        heuristic_keys = _heuristic_job_keys(heuristic_jobs)
        merged["experiences"] = [
            job for job in merged_jobs if _keep_reconciled_job(job, heuristic_keys, resume_text)
        ]
    else:
        merged["experiences"] = cleaned_ai
    if merged["experiences"]:
        sample = merged["experiences"][0]
        confidence["job_title"] = _confidence_label(sample.get("job_title", ""), resume_text, extra=True)
        confidence["employer"] = _confidence_label(sample.get("employer", ""), resume_text, extra=True)
        confidence["start_date"] = "high" if sample.get("start_date") else "low"
        confidence["end_date"] = "medium" if sample.get("end_date") or sample.get("is_current") == "Yes" else "low"
    else:
        confidence.update({"job_title": "low", "employer": "low", "start_date": "low", "end_date": "low"})

    merged["ever_employed"] = heuristic.get("ever_employed") or ai_data.get("ever_employed") or ""
    merged["is_currently_employed"] = heuristic.get("is_currently_employed") or ""
    if not merged["is_currently_employed"]:
        ai_current = _as_yes_no(ai_data.get("is_currently_employed"), default="")
        if ai_current == "Yes" and any(
            str(job.get("is_current", "")).lower() in {"yes", "true"}
            or re.search(r"present|current", str(job.get("end_date", "")), re.I)
            for job in merged["experiences"]
        ):
            merged["is_currently_employed"] = "Yes"
        elif ai_current == "No" and merged["experiences"] and all(job.get("end_date") for job in merged["experiences"]):
            merged["is_currently_employed"] = "No"
    confidence["current_employment"] = "high" if merged["is_currently_employed"] else "low"

    ai_skills = ai_data.get("skills") if isinstance(ai_data.get("skills"), list) else []
    heuristic_skills = heuristic.get("skills") if isinstance(heuristic.get("skills"), list) else []
    skills = []
    seen = set()
    heuristic_keys = {str(item).strip().lower() for item in heuristic_skills}
    skill_candidates = list(heuristic_skills)
    if heuristic.get("skills_section_seen"):
        skill_candidates.extend(item for item in ai_skills if isinstance(item, str))
    for skill in skill_candidates:
        text = str(skill).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        if key not in heuristic_keys and not field_evidenced(text, resume_text):
            continue
        seen.add(key)
        skills.append(text)
    merged["skills"] = skills
    confidence["skills"] = "high" if skills else "low"

    ai_studies = ai_data.get("further_studies") if isinstance(ai_data.get("further_studies"), list) else []
    heuristic_studies = heuristic.get("further_studies") if isinstance(heuristic.get("further_studies"), list) else []
    merged["further_studies"] = heuristic_studies or [
        row for row in ai_studies
        if isinstance(row, dict) and field_evidenced(str(row.get("course_degree") or ""), resume_text)
    ]
    merged["education_records"] = heuristic.get("education_records") if isinstance(heuristic.get("education_records"), list) else []
    for key in ("certifications", "seminars", "awards", "projects", "inferred_skills", "skill_records"):
        merged[key] = heuristic.get(key) if isinstance(heuristic.get(key), list) else []
    for warning in warnings:
        if not warning.startswith("conflict_detail:"):
            continue
        payload = warning.split("|", 2)
        field_name = payload[0].split(":", 1)[-1]
        left = payload[1] if len(payload) > 1 else ""
        right = payload[2] if len(payload) > 2 else ""
        conflicts.append({
            "field": field_name,
            "model": left,
            "heuristic": right,
            "chosen": merged.get(field_name, right),
            "reason": "Both values appear in the resume. The documented heuristic value was kept.",
        })
    if warnings:
        merged["_reconcile_warnings"] = [item for item in warnings if not item.startswith("conflict_detail:")]
    if conflicts:
        merged["_conflicts"] = conflicts
    if rejections:
        merged["_rejections"] = rejections
    return merged, confidence


def normalize_extracted_resume_data(data: Dict[str, Any], resume_text: str) -> Dict[str, Any]:
    data = data or {}
    experiences = data.get("experiences", []) if isinstance(data.get("experiences"), list) else []
    studies = data.get("further_studies", []) if isinstance(data.get("further_studies"), list) else []

    normalized_experiences = []
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        start_date = _normalize_stored_date(exp.get("start_date"))
        end_raw = str(exp.get("end_date", "") or "").strip()
        range_start, range_end, range_current = parse_date_range(f"{start_date} - {end_raw}".strip(" -"))
        is_current = _as_yes_no(exp.get("is_current"), default="")
        if range_current == "Yes" or re.search(r"\b(present|current|now|ongoing)\b", end_raw, re.I):
            is_current = "Yes"
            end_date = ""
        else:
            end_date = _normalize_stored_date(range_end or end_raw)
            if is_current != "Yes" and end_date:
                is_current = "No"
        title = str(exp.get("job_title", "") or "").strip()
        employer = str(exp.get("employer", "") or "").strip()
        if not title and not employer:
            continue
        normalized_experiences.append({
            "job_title": title,
            "employer": employer,
            "start_date": start_date or range_start,
            "end_date": end_date,
            "is_current": is_current,
            "salary_range": _normalize_salary_range(exp.get("salary_range")),
            "employment_status": _normalize_employment_status(exp.get("employment_status")) or _infer_employment_status(title, is_current),
            "supervisor_name": str(exp.get("supervisor_name", "") or "").strip(),
            "supervisor_email": str(exp.get("supervisor_email", "") or "").strip(),
            "related_to_degree": _as_yes_no(exp.get("related_to_degree"), default=""),
            "description": str(exp.get("description", "") or "").strip(),
        })

    normalized_experiences = sorted(normalized_experiences, key=lambda item: _date_rank(item.get("start_date", "")))
    first_name = _normalize_name_case(str(data.get("first_name", "") or "").strip())
    middle_name = _normalize_name_case(str(data.get("middle_name", "") or "").strip())
    last_name = _normalize_name_case(str(data.get("last_name", "") or "").strip())
    degree_text = _normalize_degree_text(str(data.get("degree", "") or "").strip())

    current_flags = [item.get("is_current") for item in normalized_experiences]
    if any(flag == "Yes" for flag in current_flags):
        currently_employed = "Yes"
    elif normalized_experiences and all(item.get("end_date") for item in normalized_experiences):
        currently_employed = "No"
    else:
        currently_employed = _as_yes_no(data.get("is_currently_employed"), default="")

    graduated_year = _safe_year(data.get("year_graduated", ""))
    after_graduation = jobs_after_graduation(normalized_experiences, graduated_year)
    ever_employed = _ever_employed_from_jobs(
        normalized_experiences,
        graduated_year,
        data.get("ever_employed"),
    )

    normalized_studies = []
    for study in studies:
        if not isinstance(study, dict):
            continue
        course = str(study.get("course_degree", "") or "").strip()
        school = str(study.get("school", "") or "").strip()
        if not course and not school:
            continue
        normalized_studies.append({
            "course_degree": course,
            "school": school,
            "year_enrolled": _safe_year(study.get("year_enrolled", "")),
            "is_graduated": _as_yes_no(study.get("is_graduated"), default=""),
            "completion_status": str(study.get("completion_status") or "").strip(),
        })

    skills = data.get("skills", [])
    if isinstance(skills, str):
        skills = [skills]
    if not isinstance(skills, list):
        skills = []
    cleaned_skills, seen = [], set()
    for skill in skills:
        if not isinstance(skill, str):
            continue
        text = skill.strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        cleaned_skills.append(text)

    country = str(data.get("country", "") or "").strip()
    meta = data.get("extraction_meta") if isinstance(data.get("extraction_meta"), dict) else {}

    current_job = select_current_experience(normalized_experiences)
    previous_titles = [
        item.get("job_title", "")
        for item in normalized_experiences
        if item is not current_job
    ]
    for exp in normalized_experiences:
        prior = _as_yes_no(exp.get("related_to_degree"), default="")
        if prior in {"Yes", "No"}:
            continue
        use_skills = cleaned_skills if exp is current_job else []
        exp["related_to_degree"] = _infer_related_to_degree(
            exp.get("job_title", ""),
            degree_text,
            description=exp.get("description", ""),
            employer=exp.get("employer", ""),
            skills=use_skills,
        )

    first_after = after_graduation[0] if after_graduation else {}
    course_alignment = _course_alignment_payload(
        degree_text,
        current_job,
        currently_employed,
        cleaned_skills,
        previous_titles,
    )
    if current_job:
        prior = _as_yes_no(current_job.get("related_to_degree"), default="")
        course_rel = _as_yes_no(course_alignment.get("related_to_degree"), default="")
        if prior not in {"Yes", "No"} and course_rel in {"Yes", "No"}:
            current_job["related_to_degree"] = course_rel

    return {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "country": country,
        "degree": degree_text,
        "year_graduated": _safe_year(data.get("year_graduated", "")),
        "ever_employed": ever_employed,
        "is_currently_employed": currently_employed,
        "time_to_first_job": _employment_wait_bucket(graduated_year, first_after.get("start_date", "")) if first_after else "",
        "first_job_after_graduation": first_after,
        "experiences": normalized_experiences,
        "further_studies": normalized_studies,
        "certifications": _clean_credentials(data.get("certifications")),
        "seminars": _clean_credentials(data.get("seminars")),
        "awards": _clean_credentials(data.get("awards")),
        "further_studies_evidence": further_studies_evidence(
            normalized_studies,
            data.get("education_records") if isinstance(data.get("education_records"), list) else [],
            degree_text,
        ),
        "skills": cleaned_skills,
        "skill_records": data.get("skill_records") if isinstance(data.get("skill_records"), list) else [],
        "inferred_skills": data.get("inferred_skills") if isinstance(data.get("inferred_skills"), list) else [],
        "projects": _clean_credentials(data.get("projects")),
        "course_alignment": course_alignment,
        "extraction_meta": meta,
    }


def _course_alignment_payload(
    degree: str,
    current_job: dict,
    currently_employed: str,
    skills: List[str],
    previous_titles: List[str],
) -> dict:
    if currently_employed != "Yes" or not current_job:
        return {
            "status": "Unknown",
            "confidence": 0.2,
            "related_to_degree": "",
            "job_title": "",
            "detail": "No current job was identified for course alignment.",
        }
    result: CourseAlignment = align_occupation_to_degree(
        degree,
        current_job.get("job_title", ""),
        description=current_job.get("description", ""),
        employer=current_job.get("employer", ""),
        skills=skills,
        previous_titles=previous_titles,
    )
    return {
        "status": result.status,
        "confidence": result.confidence,
        "related_to_degree": result.related_to_degree,
        "job_title": current_job.get("job_title", ""),
        "detail": result.detail,
        "domain": result.domain,
    }


def _field_evidence(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Internal notes for reconciliation and QA. Values are copied, not inferred."""
    rows: List[Dict[str, Any]] = []
    for field in ("degree", "year_graduated", "country"):
        value = str(parsed.get(field) or "").strip()
        if value:
            rows.append({"field": field, "value": value, "source": "heuristic", "evidence": value})
    for job in parsed.get("experiences") or []:
        if not isinstance(job, dict):
            continue
        title = str(job.get("job_title") or "").strip()
        employer = str(job.get("employer") or "").strip()
        if not title and not employer:
            continue
        partial = bool(title) and not employer and not str(job.get("start_date") or "").strip()
        rows.append({
            "field": "employment",
            "value": title,
            "employer": employer,
            "source": "heuristic",
            "method": "heuristic",
            "status": "partial" if partial else "extracted",
            "evidence": " | ".join(part for part in (title, employer, str(job.get("start_date") or "")) if part),
        })
    for study in parsed.get("further_studies") or []:
        if not isinstance(study, dict):
            continue
        program = str(study.get("course_degree") or "").strip()
        school = str(study.get("school") or "").strip()
        if program or school:
            rows.append({
                "field": "further_studies",
                "value": True,
                "source": "education_section",
                "evidence": " | ".join(part for part in (program, school) if part),
            })
    return rows


def _provenance_rows(
    parsed: Dict[str, Any],
    confidence: Dict[str, str],
    resume_text: str,
    *,
    text_source: str,
    conflicts: List[dict],
) -> List[dict]:
    """Field provenance. Legacy confidence ``low`` on an empty value is reported here as ``missing``."""
    conflict_by_field = {row.get("field"): row for row in conflicts if isinstance(row, dict)}
    reader = "ocr" if text_source == "ocr" else "document"
    rows = []
    for field in ("first_name", "middle_name", "last_name", "country", "degree", "year_graduated"):
        value = str(parsed.get(field) or "").strip()
        legacy = confidence.get(field) or ("low" if value else "missing")
        label = "missing" if not value else legacy
        conflict = conflict_by_field.get(field)
        supported = bool(value) and field_evidenced(value, resume_text)
        rows.append({
            "field": field,
            "value": value,
            "original": value,
            "source": "heuristic" if text_source != "ocr" else "ocr",
            "reader": reader,
            "excerpt": evidence_excerpt(value, resume_text),
            "validation": "supported" if supported else ("missing" if not value else "unverified"),
            "confidence": label,
            "conflict": conflict,
            "review_reason": (conflict or {}).get("reason", ""),
        })
    return rows


def extract_resume_info(resume_text: str, document: DocumentView | None = None) -> tuple[Dict[str, Any], str]:
    view = document or DocumentView.from_text(resume_text or "")
    text = (view.text or resume_text or "").strip()
    if view.source == "failed" and not text:
        return {}, "failed"
    if not text or not text_is_sufficient(text):
        return {}, "empty" if view.source != "failed" else "failed"

    heuristic = extract_heuristic(view)
    assessment = assess_extraction(heuristic)
    # One structured-model attempt, and only when the first pass left a gap.
    model_called = False
    ai_data = None
    if needs_deeper_extraction(assessment):
        model_called = True
        ai_data = _extract_with_llm(text)
    used_model = bool(ai_data)

    merged, confidence = reconcile_extractions(ai_data, heuristic, text)
    extra_warnings = list(merged.pop("_reconcile_warnings", []) or [])
    conflicts = list(merged.pop("_conflicts", []) or [])
    rejections = list(merged.pop("_rejections", []) or [])
    local_retry = bool(heuristic.get("local_retry"))
    merged["extraction_meta"] = {
        "text_source": view.source,
        "columns": view.columns,
        "confidence": confidence,
        "assessment": assessment,
        "model_called": model_called,
        "second_pass": "structured_model" if model_called else ("local_retry" if local_retry else "none"),
        "warnings": list(view.warnings) + extra_warnings,
        "conflicts": conflicts,
        "rejections": rejections,
        "ocr_pages": list(getattr(view, "ocr_pages", []) or []),
        "ocr_confidence": getattr(view, "ocr_confidence", None),
        "text_quality": getattr(view, "quality", None) or assess_text_quality(text),
        "assumptions": [
            "Time to first job uses the OAAPS June graduation assumption when the resume has only a graduation year. That month is not a date extracted from the resume.",
            "A start date with no month is placed in July only when calculating that bucket, and the bucket is an estimate.",
            "When more than one role is marked current, the present job is the one with the latest start date.",
        ],
    }
    parsed = normalize_extracted_resume_data(merged, text)
    parsed["extraction_meta"] = merged["extraction_meta"]
    parsed["extraction_meta"]["field_evidence"] = _field_evidence(parsed)
    parsed["extraction_meta"]["provenance"] = _provenance_rows(
        parsed,
        confidence,
        text,
        text_source=view.source,
        conflicts=conflicts,
    )
    parsed["extraction_meta"]["employment_evidence"] = employment_after_graduation_status(
        parsed.get("experiences") or [],
        parsed.get("year_graduated") or "",
    )
    current_roles = [
        job for job in parsed.get("experiences") or []
        if str(job.get("is_current") or "") == "Yes"
    ]
    parsed["extraction_meta"]["current_job_count"] = len(current_roles)
    if len(current_roles) > 1:
        parsed["extraction_meta"]["current_job_rule"] = "latest_start_among_current"

    heuristic_used = bool(heuristic.get("experiences") or heuristic.get("degree") or heuristic.get("first_name"))
    if view.source == "ocr":
        source = "ocr"
    elif view.source == "llamaparse" and heuristic_used:
        source = "llamaparse+heuristic"
    elif view.source == "llamaparse":
        source = "llamaparse"
    elif used_model and heuristic_used:
        source = "llamaindex+heuristic"
    elif used_model:
        source = "llamaindex"
    else:
        source = "heuristic"
    return parsed, source


def map_to_gts_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    if "experiences" not in data and ("current_occupation" in data or "current_employer" in data):
        return data

    exps = data.get("experiences", []) if isinstance(data.get("experiences"), list) else []
    after_graduation = jobs_after_graduation(exps, data.get("year_graduated", ""))
    first_job = after_graduation[0] if after_graduation else {}
    present_job = select_current_experience(exps)
    ever_employed = _ever_employed_from_jobs(exps, data.get("year_graduated", ""), data.get("ever_employed", ""))
    first_start = first_job.get("start_date", "") if first_job else ""
    if first_job and _safe_year(data.get("year_graduated", "")) and _has_month(first_start):
        wait_basis = "confirmed"
    elif first_job and _safe_year(data.get("year_graduated", "")):
        wait_basis = "estimated"
    else:
        wait_basis = ""
    current_roles = [job for job in exps if str(job.get("is_current") or "") == "Yes"]
    course = data.get("course_alignment") if isinstance(data.get("course_alignment"), dict) else {}

    is_same = infer_present_job_is_first(first_job, present_job)

    studies = data.get("further_studies", [])
    has_further_studies = "Yes" if isinstance(studies, list) and any(
        isinstance(item, dict) and (item.get("course_degree") or item.get("school")) for item in studies
    ) else ""

    current_title = present_job.get("job_title", "") if present_job else ""
    current_employer = present_job.get("employer", "") if present_job else ""

    return {
        "first_name": data.get("first_name", ""),
        "middle_name": data.get("middle_name", ""),
        "last_name": data.get("last_name", ""),
        "country": data.get("country", ""),
        "degree": data.get("degree", ""),
        "year_graduated": data.get("year_graduated", ""),
        "ever_employed": ever_employed,
        "is_currently_employed": data.get("is_currently_employed", ""),
        "present_job_is_first": is_same,
        "after_grad_employment_duration": _employment_wait_bucket(
            data.get("year_graduated", ""), first_job.get("start_date", "")
        ),
        "time_to_first_job": _employment_wait_bucket(
            data.get("year_graduated", ""), first_job.get("start_date", "")
        ),
        "first_related": first_job.get("related_to_degree", "") if first_job else "",
        "current_occupation": current_title,
        "current_employer": current_employer,
        "first_occ": first_job.get("job_title", ""),
        "first_emp": first_job.get("employer", ""),
        "first_sal": first_job.get("salary_range", ""),
        "first_stat": first_job.get("employment_status", ""),
        "pres_occ": current_title,
        "pres_emp": current_employer,
        "pres_head": present_job.get("supervisor_name", "") if present_job else "",
        "pres_head_email": present_job.get("supervisor_email", "") if present_job else "",
        "pres_stay": _format_length_of_stay(
            present_job.get("start_date", ""),
            present_job.get("end_date", ""),
            present_job.get("is_current", "No"),
        ) if present_job else "",
        "present_related_degree": (
            course["related_to_degree"]
            if course.get("related_to_degree") in {"Yes", "No"}
            else (present_job.get("related_to_degree", "") if present_job else "")
        ),
        "enroll_further_studies": has_further_studies,
        "further_studies_raw": data.get("further_studies", []),
        "further_studies": data.get("further_studies", []),
        "certifications": _clean_credentials(data.get("certifications")),
        "seminars": _clean_credentials(data.get("seminars")),
        "awards": _clean_credentials(data.get("awards")),
        "skills": data.get("skills", []),
        "inferred_skills": data.get("inferred_skills", []),
        "projects": _clean_credentials(data.get("projects")),
        "experiences": exps,
        "course_alignment": course or {
            "status": "Unknown",
            "confidence": 0.2,
            "related_to_degree": "",
            "job_title": current_title,
        },
        "derivation": {
            "time_to_first_job_basis": wait_basis,
            "current_job_count": len(current_roles),
            "current_job_rule": "latest_start_among_current" if len(current_roles) > 1 else ("single_current" if current_roles else "none"),
            "employment_after_graduation": employment_after_graduation_status(exps, data.get("year_graduated", "")),
            "graduation_month_assumption": "June of year_graduated is an OAAPS survey assumption, not a date read from the resume.",
            "year_only_start_assumption": "A start date with no month is placed in July only for the time-to-first-job bucket.",
        },
    }


def apply_verified_registry(prefill: Dict[str, Any], record: Any) -> Dict[str, Any]:
    """Keep degree and graduation year from a verified university record.

    Resume extraction does not replace those values. The stored resume parse is unchanged.
    """
    if record is None or not isinstance(prefill, dict):
        return prefill
    updated = dict(prefill)
    overrides = []
    degree = str(getattr(record, "degree", "") or "").strip()
    year = str(getattr(record, "year_graduated", "") or "").strip()
    if degree and str(updated.get("degree") or "") != degree:
        overrides.append({
            "field": "degree",
            "resume_value": updated.get("degree") or "",
            "registry_value": degree,
            "source": "verified_registry",
            "reason": "Verified university record. Resume extraction cannot replace it.",
        })
        updated["degree"] = degree
    elif degree:
        updated["degree"] = degree
    if year and str(updated.get("year_graduated") or "") != year:
        overrides.append({
            "field": "year_graduated",
            "resume_value": updated.get("year_graduated") or "",
            "registry_value": year,
            "source": "verified_registry",
            "reason": "Verified university record. Resume extraction cannot replace it.",
        })
        updated["year_graduated"] = year
    elif year:
        updated["year_graduated"] = year
    if overrides:
        updated["registry_overrides"] = overrides
    return updated
