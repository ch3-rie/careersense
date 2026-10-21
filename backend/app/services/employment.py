"""Authoritative current-employment rules for submitted GTS data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.constants import PROFILE_UNEMPLOYMENT_REASONS


def _text(value: Any) -> str:
    return str(value or "").strip()


def is_yes(value: Any) -> bool:
    return _text(value).lower() in {"yes", "y", "true", "1"}


def is_no(value: Any) -> bool:
    return _text(value).lower() in {"no", "n", "false", "0"}


def currently_employed(data: Mapping[str, Any] | None) -> bool:
    return is_yes((data or {}).get("is_currently_employed"))


@dataclass(frozen=True)
class CurrentEmployment:
    currently_employed: bool
    present_is_first: bool
    occupation: str
    employer: str
    first_occupation: str
    first_employer: str
    present_occupation: str
    present_employer: str


def resolve_current_employment(data: Mapping[str, Any] | None) -> CurrentEmployment:
    """Derive official current occupation/employer from submitted tracer answers.

    When the graduate says the present job is the first job, only first-job
    fields are official. Hidden or leftover present-job values are ignored.
    """
    data = data or {}
    first_occupation = _text(data.get("first_occ"))
    first_employer = _text(data.get("first_emp"))
    present_occupation = _text(data.get("pres_occ"))
    present_employer = _text(data.get("pres_emp"))
    employed = currently_employed(data)
    if not employed:
        return CurrentEmployment(
            currently_employed=False,
            present_is_first=False,
            occupation="",
            employer="",
            first_occupation=first_occupation,
            first_employer=first_employer,
            present_occupation=present_occupation,
            present_employer=present_employer,
        )
    present_is_first = not is_no(data.get("present_job_is_first"))
    if present_is_first:
        return CurrentEmployment(
            currently_employed=True,
            present_is_first=True,
            occupation=first_occupation,
            employer=first_employer,
            first_occupation=first_occupation,
            first_employer=first_employer,
            present_occupation=present_occupation,
            present_employer=present_employer,
        )
    return CurrentEmployment(
        currently_employed=True,
        present_is_first=False,
        occupation=present_occupation,
        employer=present_employer,
        first_occupation=first_occupation,
        first_employer=first_employer,
        present_occupation=present_occupation,
        present_employer=present_employer,
    )


def apply_current_employment(survey_data: dict[str, Any]) -> CurrentEmployment:
    current = resolve_current_employment(survey_data)
    survey_data["current_occupation"] = current.occupation
    survey_data["current_employer"] = current.employer
    return current


def unemployment_option(code: str) -> Optional[tuple[str, str, str]]:
    cleaned = str(code or "").strip()
    for item in PROFILE_UNEMPLOYMENT_REASONS:
        if item[0] == cleaned:
            return item
    return None


def unemployment_summary(code: str, details: str) -> str:
    option = unemployment_option(code)
    label = option[1] if option else ""
    extra = str(details or "").strip()
    if label and extra:
        return f"{label}: {extra}"[:500]
    return (label or extra)[:500]


def profile_reason_from_gts(reasons: Any, other_text: str = "") -> tuple[str, str]:
    """Map survey unemployment answers onto the single profile reason."""
    if isinstance(reasons, str):
        labels = [reasons.strip()] if reasons.strip() else []
    elif isinstance(reasons, list):
        labels = [str(item).strip() for item in reasons if str(item).strip()]
    else:
        labels = []
    for code, _label, gts_label in PROFILE_UNEMPLOYMENT_REASONS:
        if code == "other":
            continue
        if gts_label in labels:
            return code, ""
    specify = str(other_text or "").strip()[:500]
    if "Other" in labels or specify:
        return "other", specify
    return "", ""


def apply_survey_unemployment(profile: Any, survey_data: Mapping[str, Any] | None) -> None:
    """Keep the profile status aligned when a tracer survey is submitted."""
    if profile is None:
        return
    data = survey_data or {}
    if is_no(data.get("is_currently_employed")):
        code, details = profile_reason_from_gts(data.get("reason_current"), data.get("reason_current_other") or "")
        profile.currently_unemployed = True
        profile.unemployment_reason = code
        profile.unemployment_details = details
        profile.no_employment_reason = unemployment_summary(code, details)
        profile.employment_answer_before = ""
        return
    if is_yes(data.get("is_currently_employed")):
        profile.currently_unemployed = False
        profile.unemployment_reason = ""
        profile.unemployment_details = ""
        profile.no_employment_reason = ""
        profile.employment_answer_before = ""


def unemployment_public(profile: Any) -> dict[str, Any]:
    unemployed = bool(profile and getattr(profile, "currently_unemployed", False))
    code = str(getattr(profile, "unemployment_reason", "") or "") if unemployed else ""
    details = str(getattr(profile, "unemployment_details", "") or "") if unemployed else ""
    option = unemployment_option(code)
    return {
        "currently_unemployed": unemployed,
        "unemployment_reason": code,
        "unemployment_details": details,
        "unemployment_reason_label": option[1] if option else "",
        "no_employment_reason": str(getattr(profile, "no_employment_reason", "") or "") if profile else "",
    }


def apply_profile_unemployment(data: Mapping[str, Any] | None, profile: Any) -> dict[str, Any]:
    """A saved 'currently unemployed' profile overrides a tracer answer of Yes.

    Past occupation fields stay in the copy's source data. Current employment
    is reported as No, with the profile reason mapped to the survey category.
    """
    merged = dict(data or {})
    if not profile or not getattr(profile, "currently_unemployed", False):
        return merged
    merged["is_currently_employed"] = "No"
    option = unemployment_option(getattr(profile, "unemployment_reason", ""))
    if option:
        merged["reason_current"] = [option[2]]
    if str(getattr(profile, "unemployment_reason", "") or "") == "other":
        merged["reason_current_other"] = str(getattr(profile, "unemployment_details", "") or "")
    return merged


def infer_present_job_is_first(
    first_job: Optional[Mapping[str, Any]],
    present_job: Optional[Mapping[str, Any]],
) -> str:
    """Prefill-only. Same employer is not enough to treat two roles as one job."""
    if not first_job or not present_job:
        return ""
    if first_job is present_job:
        return "Yes"
    first_title = _text(first_job.get("job_title")).lower()
    present_title = _text(present_job.get("job_title")).lower()
    first_employer = _text(first_job.get("employer")).lower()
    present_employer = _text(present_job.get("employer")).lower()
    if first_title and present_title and first_title != present_title:
        return "No"
    if first_employer and present_employer and first_employer != present_employer:
        return "No"
    if first_title and present_title and first_title == present_title:
        if not first_employer or not present_employer or first_employer == present_employer:
            return "Yes"
    return ""
