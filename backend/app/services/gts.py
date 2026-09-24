from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AlignmentResult,
    AlumniProfile,
    AlumniSkill,
    FurtherStudy,
    SurveyDefinition,
    TracerSubmission,
)
from app.services.alignment import alignment_score, analyze_career_alignment
from app.services.employment import apply_current_employment
from app.services.jobs import sync_job_timeline_from_gts
from app.services.validation import normalize_skills, require_owned_resume, validate_employed_job_title
from app.survey_default import flatten_questions


def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"yes", "true", "1"}:
            return True
        if lowered in {"no", "false", "0"}:
            return False
    return None


def _study_field(item: dict, *keys: str) -> str:
    for key in keys:
        if item.get(key) not in (None, ""):
            return str(item.get(key))
    return ""


def persist_tracer_submission(
    db: Session,
    account: Account,
    survey_data: dict[str, Any],
    extra_answers: Optional[dict[str, Any]] = None,
    resume_id: Optional[int] = None,
) -> TracerSubmission:
    survey_data = dict(survey_data or {})
    extra_answers = extra_answers or survey_data.get("extra_answers") or {}
    validate_employed_job_title(survey_data)
    owned_resume_id = require_owned_resume(db, account.id, resume_id or survey_data.get("resume_id"))
    skills = normalize_skills(survey_data.get("skills"))
    survey_data["skills"] = skills

    current = apply_current_employment(survey_data)
    job_title = current.occupation
    current_employer = current.employer
    degree = survey_data.get("degree") or (account.profile.degree if account.profile else "")
    job_context = " ".join(part for part in [current_employer, " ".join(skills)] if part)
    status, detail, soc, suggestions = analyze_career_alignment(db, job_title, degree, job_context=job_context)
    score = alignment_score(status)
    survey_data.update({
        "current_occupation": job_title,
        "current_employer": current_employer,
        "job_description": detail,
        "soc_code": soc.soc_code if soc else survey_data.get("soc_code", ""),
        "soc_description": soc.description if soc else survey_data.get("soc_description", ""),
        "soc_category": soc.category if soc else survey_data.get("soc_category", ""),
        "alignment_status": status,
        "alignment_detail": detail,
    })

    published_row = db.query(SurveyDefinition).filter(SurveyDefinition.slug == "gts").one_or_none()
    survey_version = int(published_row.published_version) if published_row and published_row.published_version else None
    extra_labels = {}
    published_schema = (published_row.published_schema if published_row else None) or {}
    for question in flatten_questions(published_schema):
        if question.get("storage") != "extra":
            continue
        key = str(question.get("extra_key") or question.get("id") or "")
        if key:
            extra_labels[key] = question.get("label") or key
    survey_data["_survey_version"] = survey_version
    if extra_labels:
        survey_data["_extra_labels"] = extra_labels

    account.first_name = (survey_data.get("first_name") or account.first_name or "")[:80]
    account.last_name = (survey_data.get("last_name") or account.last_name or "")[:80]

    profile = account.profile or AlumniProfile(account_id=account.id)
    profile.first_name = survey_data.get("first_name", "") or profile.first_name
    profile.middle_name = survey_data.get("middle_name", "") or ""
    profile.last_name = survey_data.get("last_name", "") or profile.last_name
    profile.husband_surname = survey_data.get("husband_surname", "") or ""
    profile.country_residence = survey_data.get("country", "Philippines") or "Philippines"
    profile.degree = survey_data.get("degree", "") or profile.degree
    profile.year_graduated = survey_data.get("year_graduated", "") or profile.year_graduated
    profile.guardian_type = survey_data.get("primary_guardian") or ""
    profile.guardian_degree_completed = _to_bool(survey_data.get("guardian_degree_completed"))
    db.add(profile)

    db.query(FurtherStudy).filter(FurtherStudy.account_id == account.id).delete()
    db.flush()
    studies = survey_data.get("further_studies") or []
    if isinstance(studies, list):
        for item in studies:
            if not isinstance(item, dict):
                continue
            course = _study_field(item, "course_degree", "Course/Degree")
            school = _study_field(item, "school", "School")
            year = _study_field(item, "year_enrolled", "Year of First Enrollment")
            scholarship = _study_field(item, "scholarship", "Scholarship")
            graduated = item.get("is_graduated", item.get("Graduated"))
            if not any([course, school, year, scholarship]):
                continue
            db.add(
                FurtherStudy(
                    account_id=account.id,
                    course_degree=course,
                    school=school,
                    year_enrolled=str(year),
                    scholarship=scholarship,
                    is_graduated=_to_bool(graduated),
                )
            )

    db.query(AlumniSkill).filter(AlumniSkill.account_id == account.id).delete()
    db.flush()
    for skill in skills:
        db.add(AlumniSkill(account_id=account.id, skill_name=skill))

    alignment = account.alignment or AlignmentResult(account_id=account.id)
    alignment.overall_match_score = score
    alignment.alignment_justification = status
    alignment.justification_detail = detail
    alignment.suggested_career_paths = suggestions
    db.add(alignment)

    submission = TracerSubmission(
        account_id=account.id,
        student_id=account.linked_student_id,
        resume_id=owned_resume_id,
        data_json=survey_data,
        extra_answers=extra_answers,
        survey_version=survey_version,
        alignment_status=status,
        alignment_score=score,
        soc_code=soc.soc_code if soc else None,
    )
    db.add(submission)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Could not save tracer data. Please review your answers and try again.",
        ) from exc
    sync_job_timeline_from_gts(db, account, survey_data)
    return submission
