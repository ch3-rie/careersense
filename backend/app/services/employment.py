"""Authoritative current-employment rules for submitted GTS data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


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
