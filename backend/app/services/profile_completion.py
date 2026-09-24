"""Single source of truth for alumni profile completeness.

The frontend must display these results. Do not recompute percent in React.
Weights are documented in docs/profile-completion.md and always sum to 100.
Achievement evaluation lives in app.services.achievements and consumes this
completion result; it does not invent a second percent formula.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Account, AlumniJob, FurtherStudy, Resume, TracerSubmission
from app.services.achievements import PROFILE_COMPLETE_KEY, serialize_achievement
from app.services.employment import is_no, is_yes, resolve_current_employment

logger = logging.getLogger("careersense")

CATEGORY_WEIGHTS: dict[str, int] = {
    "identity": 10,
    "education": 15,
    "contact": 20,
    "photo": 10,
    "employment": 20,
    "further_studies": 10,
    "tracer": 15,
}

assert sum(CATEGORY_WEIGHTS.values()) == 100

COMPLETE_MESSAGE = "All applicable alumni information has been completed."
INCOMPLETE_MESSAGE = "Complete the remaining information to finish your CareerSense profile."
ALMOST_MESSAGE = "You're almost there. Complete the remaining information to finish your profile."
PROFILE_COMPLETE_NAME = "Profile Complete"
PROFILE_COMPLETE_DESCRIPTION = "All applicable alumni information has been completed."
PROFILE_COMPLETE_KEYS = (PROFILE_COMPLETE_KEY, "record_complete")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _present(value: Any) -> bool:
    return bool(_text(value))


def _study_complete(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    course = _text(item.get("course_degree") or item.get("course") or item.get("Course/Degree"))
    school = _text(item.get("school") or item.get("School"))
    return bool(course and school)


def _latest_submission(db: Session, account_id: int) -> TracerSubmission | None:
    return (
        db.query(TracerSubmission)
        .filter(TracerSubmission.account_id == account_id)
        .order_by(TracerSubmission.submitted_at.desc())
        .first()
    )


def field_snapshot(db: Session, user: Account) -> dict:
    from app.services.survey import get_published_schema, required_answer_gaps

    profile = user.profile
    record = user.university_record
    latest = _latest_submission(db, user.id)
    data = latest.data_json if latest else {}
    extra = latest.extra_answers if latest else {}
    employment = resolve_current_employment(data)
    jobs = db.query(AlumniJob).filter(AlumniJob.account_id == user.id).all()
    studies = db.query(FurtherStudy).filter(FurtherStudy.account_id == user.id).all()
    study_rows = [
        {"course_degree": row.course_degree, "school": row.school}
        for row in studies
    ]
    if not study_rows:
        study_rows = [item for item in (data.get("further_studies") or []) if isinstance(item, dict)]
    related = ""
    if employment.currently_employed:
        related = data.get("first_related") if employment.present_is_first else data.get("present_related_degree") or ""
    tracer_required_ok = False
    schema = {}
    if latest:
        schema = get_published_schema(db)
        tracer_required_ok = not required_answer_gaps(schema, data, extra or {})
    first_name = (profile.first_name if profile else "") or user.first_name or (record.first_name if record else "")
    last_name = (profile.last_name if profile else "") or user.last_name or (record.last_name if record else "")
    degree = (profile.degree if profile else "") or (record.degree if record else "")
    year_graduated = (profile.year_graduated if profile else "") or (record.year_graduated if record else "")
    from app.services.achievements import resume_extraction_usable
    from app.services.alumni_hub import canonical_card_status

    resume = None
    if latest and latest.resume_id:
        resume = db.get(Resume, latest.resume_id)
        if resume is not None and resume.account_id != user.id:
            resume = None
    survey_title = (schema.get("title") if schema else "") or "Graduate Tracer Survey"
    survey_year = datetime.now(timezone.utc).year
    survey_label = survey_title if str(survey_year) in survey_title else f"{survey_year} {survey_title}"
    return {
        "phone": profile.phone if profile else "",
        "city": profile.city if profile else "",
        "country": (profile.country_residence if profile else "") or "Philippines",
        "photo_path": profile.photo_path if profile else "",
        "first_name": first_name,
        "last_name": last_name,
        "degree": degree,
        "year_graduated": year_graduated,
        "college": record.college if record else "",
        "has_tracer": latest is not None,
        "tracer_required_ok": tracer_required_ok,
        "currently_employed": employment.currently_employed,
        "present_is_first": employment.present_is_first,
        "current_employment_answer": data.get("is_currently_employed") or "",
        "ever_employed": data.get("ever_employed") or "",
        "occupation": employment.occupation,
        "employer": employment.employer,
        "first_occ": employment.first_occupation,
        "first_emp": employment.first_employer,
        "related": related,
        "enroll_further_studies": data.get("enroll_further_studies") or "",
        "studies": study_rows,
        "jobs": [
            {"title": job.job_title, "employer": job.company, "is_current": job.is_current}
            for job in jobs
        ],
        "job_count": len(jobs),
        "card_status": canonical_card_status(user.alumni_card),
        "resume_id": resume.id if resume else None,
        "has_resume": resume is not None,
        "resume_usable": resume_extraction_usable(resume),
        "survey_label": survey_label,
        "survey_version": latest.survey_version if latest else None,
    }


def field_is_present(field_id, snapshot=None) -> bool:
    if isinstance(field_id, dict):
        snapshot, field_id = field_id, snapshot
    snapshot = snapshot or {}
    field_id = str(field_id or "")
    if field_id in {"contact", "phone"}:
        return bool(snapshot.get("phone"))
    if field_id == "city":
        return bool(snapshot.get("city"))
    if field_id == "country":
        return bool(snapshot.get("country"))
    if field_id == "profile_photo":
        return bool(snapshot.get("photo_path"))
    if field_id in {"employment", "current_occupation"}:
        if not snapshot.get("has_tracer"):
            return False
        if not snapshot.get("currently_employed"):
            return True
        return bool(snapshot.get("occupation"))
    if field_id == "work_history":
        if not snapshot.get("has_tracer"):
            return False
        if is_no(snapshot.get("ever_employed")):
            return True
        return bool(snapshot.get("jobs") or snapshot.get("first_occ"))
    if field_id == "education":
        return bool(snapshot.get("degree") and snapshot.get("year_graduated"))
    if field_id == "further_studies":
        if not snapshot.get("has_tracer"):
            return False
        if is_no(snapshot.get("enroll_further_studies")):
            return True
        if is_yes(snapshot.get("enroll_further_studies")):
            return any(_study_complete(item) for item in snapshot.get("studies") or [])
        return False
    if field_id == "graduate_tracer":
        return bool(snapshot.get("has_tracer") and snapshot.get("tracer_required_ok", True))
    if field_id == "alumni_card":
        return (snapshot.get("card_status") or "") not in {"", "NotYetApplied"}
    return False


def field_satisfied(field_id: str, baseline: dict, current: dict) -> bool:
    if field_is_present(field_id, current):
        return True
    return field_is_present(field_id, baseline)


def _item_score(items: list[tuple[bool, str]]) -> tuple[int, float, list[str]]:
    if not items:
        return 100, 1.0, []
    filled = sum(1 for ok, _ in items if ok)
    missing = [label for ok, label in items if not ok]
    ratio = filled / len(items)
    return round(100 * ratio), ratio, missing


def _employment_category(snapshot: dict) -> tuple[int, float, list[str], str | None]:
    route = "/alumni/resume"
    if not snapshot.get("has_tracer"):
        return 0, 0.0, ["Submit the Graduate Tracer Survey"], route
    ever_yes = is_yes(snapshot.get("ever_employed"))
    ever_no = is_no(snapshot.get("ever_employed"))
    current_answer = _text(snapshot.get("current_employment_answer"))
    current_yes = bool(snapshot.get("currently_employed"))
    if ever_no:
        return 100, 1.0, [], None
    checks: list[tuple[bool, str]] = []
    if not ever_yes and not current_answer:
        return 0, 0.0, ["Employment status after graduation"], route
    if ever_yes:
        history_ok = bool(snapshot.get("first_occ") or snapshot.get("job_count"))
        employer_ok = bool(snapshot.get("first_emp") or snapshot.get("job_count"))
        checks.append((history_ok, "First job or work history"))
        checks.append((employer_ok, "First employer or work history"))
    if current_yes:
        checks.append((bool(snapshot.get("occupation")), "Current occupation"))
        checks.append((bool(snapshot.get("employer")), "Current employer"))
        checks.append((_present(snapshot.get("related")), "Whether your work is related to your degree"))
    elif current_answer:
        pass
    else:
        checks.append((False, "Current employment status"))
    percent, ratio, missing = _item_score(checks)
    return percent, ratio, missing, (route if missing else None)


def _studies_category(snapshot: dict) -> tuple[int, float, list[str], str | None]:
    route = "/alumni/resume"
    if not snapshot.get("has_tracer"):
        return 0, 0.0, ["Submit the Graduate Tracer Survey"], route
    enroll = snapshot.get("enroll_further_studies")
    if is_no(enroll):
        return 100, 1.0, [], None
    if not is_yes(enroll):
        return 0, 0.0, ["Whether you enrolled in further studies after graduation"], route
    if any(_study_complete(item) for item in snapshot.get("studies") or []):
        return 100, 1.0, [], None
    return 0, 0.0, ["Program and institution for your further studies"], route


def _tracer_category(snapshot: dict) -> tuple[int, float, list[str], str | None]:
    route = "/alumni/resume"
    if not snapshot.get("has_tracer"):
        return 0, 0.0, ["Submit the current Graduate Tracer Survey"], route
    if snapshot.get("tracer_required_ok", True):
        return 100, 1.0, [], None
    return 0, 0.0, ["Complete the required Graduate Tracer Survey questions"], route


def _category(
    category_id: str,
    label: str,
    percent: int,
    ratio: float,
    missing: list[str],
    route: str | None,
    hint: str,
) -> dict[str, Any]:
    complete = percent >= 100 and not missing
    return {
        "id": category_id,
        "label": label,
        "weight": CATEGORY_WEIGHTS[category_id],
        "percent": percent,
        "complete": complete,
        "applicable": True,
        "missing": missing,
        "route": route if missing else None,
        "hint": hint if missing else "",
    }, ratio


def progress_from_snapshot(snapshot: dict) -> dict[str, Any]:
    identity_percent, identity_ratio, identity_missing = _item_score(
        [
            (_present(snapshot.get("first_name")), "Given name"),
            (_present(snapshot.get("last_name")), "Last name"),
        ]
    )
    education_percent, education_ratio, education_missing = _item_score(
        [
            (_present(snapshot.get("degree")), "Bachelor’s degree"),
            (_present(snapshot.get("year_graduated")), "Graduation year"),
        ]
    )
    contact_percent, contact_ratio, contact_missing = _item_score(
        [
            (_present(snapshot.get("phone")), "Phone number"),
            (_present(snapshot.get("city")), "City"),
            (_present(snapshot.get("country")), "Country"),
        ]
    )
    has_photo = bool(snapshot.get("photo_path"))
    photo_percent, photo_ratio, photo_missing = (100, 1.0, []) if has_photo else (0, 0.0, ["Profile photo"])
    emp_percent, emp_ratio, emp_missing, emp_route = _employment_category(snapshot)
    studies_percent, studies_ratio, studies_missing, studies_route = _studies_category(snapshot)
    tracer_percent, tracer_ratio, tracer_missing, tracer_route = _tracer_category(snapshot)

    identity, identity_ratio = _category(
        "identity",
        "Basic information",
        identity_percent,
        identity_ratio,
        identity_missing,
        "/alumni",
        "Confirm your name on the alumni record.",
    )
    education, education_ratio = _category(
        "education",
        "Education",
        education_percent,
        education_ratio,
        education_missing,
        "/alumni",
        "Degree and graduation year come from the AUF graduate registry when they are on file.",
    )
    contact, contact_ratio = _category(
        "contact",
        "Contact information",
        contact_percent,
        contact_ratio,
        contact_missing,
        "/alumni#contact",
        "Add a phone number, city, and country so AAPS can reach you.",
    )
    photo, photo_ratio = _category(
        "photo",
        "Profile photo",
        photo_percent,
        photo_ratio,
        photo_missing,
        "/alumni",
        "Add a profile photo to your alumni record.",
    )
    employment, emp_ratio = _category(
        "employment",
        "Employment",
        emp_percent,
        emp_ratio,
        emp_missing,
        emp_route or "/alumni/resume",
        "Record your employment status in the Graduate Tracer Survey.",
    )
    further_studies, studies_ratio = _category(
        "further_studies",
        "Further studies",
        studies_percent,
        studies_ratio,
        studies_missing,
        studies_route or "/alumni/resume",
        "Answer whether you enrolled in further studies after graduation.",
    )
    tracer, tracer_ratio = _category(
        "tracer",
        "Graduate Tracer Survey",
        tracer_percent,
        tracer_ratio,
        tracer_missing,
        tracer_route or "/alumni/resume",
        "Submit the current Graduate Tracer Survey.",
    )

    categories = [identity, education, contact, photo, employment, further_studies, tracer]
    ratios = {
        "identity": identity_ratio,
        "education": education_ratio,
        "contact": contact_ratio,
        "photo": photo_ratio,
        "employment": emp_ratio,
        "further_studies": studies_ratio,
        "tracer": tracer_ratio,
    }
    earned = sum(CATEGORY_WEIGHTS[row["id"]] * ratios[row["id"]] for row in categories)
    percent = int(round(earned))
    all_complete = all(row["complete"] for row in categories)
    if all_complete:
        percent = 100
    elif percent >= 100:
        percent = 99
    percent = max(0, min(100, percent))

    next_actions = []
    for row in categories:
        if row["complete"]:
            continue
        next_actions.append(
            {
                "id": row["id"],
                "label": row["label"],
                "detail": row["missing"][0] if row["missing"] else row["hint"],
                "hint": row["hint"],
                "route": row["route"] or "/alumni",
            }
        )
    missing_sections = [
        {
            "key": row["id"],
            "label": row["label"],
            "route": row["route"] or "/alumni",
            "detail": row.get("detail") or row.get("hint") or "",
        }
        for row in next_actions
    ]
    is_complete = bool(all_complete and percent == 100)
    if is_complete:
        status = "Complete"
        message = COMPLETE_MESSAGE
    elif percent >= 70:
        status = "Almost complete"
        message = next_actions[0].get("hint") if next_actions else ALMOST_MESSAGE
    else:
        status = "In progress"
        message = next_actions[0].get("hint") if next_actions else INCOMPLETE_MESSAGE
    return {
        "percent": percent,
        "percentage": percent,
        "is_complete": is_complete,
        "status": status,
        "message": message,
        "weights": dict(CATEGORY_WEIGHTS),
        "categories": categories,
        "missing_sections": missing_sections,
        "next_actions": next_actions,
        "badge": serialize_badge(None),
        "badges": [serialize_badge(None)],
    }


def profile_completion_percent(snapshot: dict) -> int:
    return int(progress_from_snapshot(snapshot)["percent"])


def profile_completion_percent_for(db: Session, user: Account) -> int:
    return profile_completion_percent(field_snapshot(db, user))


def serialize_badge(row=None) -> dict[str, Any]:
    return serialize_achievement(PROFILE_COMPLETE_KEY, row)


def serialize_completion(progress: dict[str, Any], badge=None, snapshot: dict | None = None, rows=None) -> dict[str, Any]:
    from app.services.achievements import AchievementService

    if rows is not None:
        return AchievementService.serialize(progress, rows, snapshot)
    if badge is not None:
        return AchievementService.serialize(progress, [badge], snapshot)
    payload = dict(progress)
    badge_payload = serialize_badge(None)
    payload["badge"] = badge_payload
    payload["badges"] = [badge_payload]
    payload["achievements"] = payload.get("achievements") or []
    payload["percentage"] = int(payload.get("percent") or 0)
    payload["is_complete"] = bool(payload.get("is_complete"))
    return payload


def evaluate_profile_progress(db: Session, user: Account) -> dict[str, Any]:
    from app.services.achievements import AchievementService, load_badge_rows

    snapshot = field_snapshot(db, user)
    progress = progress_from_snapshot(snapshot)
    return AchievementService.serialize(progress, load_badge_rows(db, user), snapshot)


def refresh_alumni_progress(db: Session, user: Account, *, notify: bool = False) -> dict[str, Any] | None:
    """Recompute completeness and award achievements without breaking caller saves."""
    snapshot = None
    progress = None
    try:
        snapshot = field_snapshot(db, user)
        progress = progress_from_snapshot(snapshot)
    except Exception:
        logger.exception("Could not calculate profile completion for account %s", getattr(user, "id", None))
        return None
    try:
        from app.services.achievements import AchievementService

        return AchievementService.evaluate_all(db, user, snapshot, progress, notify=notify)
    except Exception:
        logger.exception("Achievement evaluation failed for account %s", getattr(user, "id", None))
        try:
            db.rollback()
        except Exception:
            pass
        try:
            from app.services.achievements import AchievementService, load_badge_rows

            return AchievementService.serialize(progress, load_badge_rows(db, user), snapshot)
        except Exception:
            logger.exception("Could not serialize achievements for account %s", getattr(user, "id", None))
            return progress
