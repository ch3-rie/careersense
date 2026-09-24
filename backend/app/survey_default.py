"""Canonical Graduate Tracer Survey schema used to seed the form builder."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.constants import (
    EMPLOYMENT_STATUS_OPTIONS,
    GUARDIAN_OPTIONS,
    HOW_FOUND_FIRST_JOB,
    SALARY_OPTIONS,
    TIME_TO_FIRST_JOB_OPTIONS,
    UNEMPLOYMENT_REASONS,
)

YES_NO = ["Yes", "No"]
INSPIRE_OPTIONS = [
    {"value": "3", "label": "3 · Great extent"},
    {"value": "2", "label": "2 · Small extent"},
    {"value": "1", "label": "1 · Not at all"},
]

SYSTEM_FIELD_KEYS = {
    "first_name",
    "last_name",
    "degree",
    "year_graduated",
    "ever_employed",
    "is_currently_employed",
    "first_occ",
    "pres_occ",
    "present_job_is_first",
}

ALIGNMENT_FIELD_KEYS = {
    "first_occ",
    "pres_occ",
    "is_currently_employed",
    "present_job_is_first",
    "ever_employed",
}

IDENTITY_FIELD_KEYS = {
    "first_name",
    "last_name",
    "degree",
    "year_graduated",
}

QUESTION_TYPE_LABELS = {
    "short_answer": "Short Answer",
    "paragraph": "Paragraph",
    "multiple_choice": "Multiple Choice",
    "checkboxes": "Checkboxes",
    "dropdown": "Dropdown",
    "scale": "Linear Scale",
    "yes_no": "Yes/No",
    "date": "Date",
    "number": "Number",
    "email": "Email",
    "skills": "Skills list",
    "repeatable_group": "Repeatable group",
}

ADDABLE_TYPES = [
    "short_answer",
    "paragraph",
    "multiple_choice",
    "checkboxes",
    "dropdown",
    "scale",
    "yes_no",
    "date",
    "number",
]


def _show(field_id: str, value: str, op: str = "eq") -> dict[str, Any]:
    return {"logic": "and", "rules": [{"field_id": field_id, "op": op, "value": value}]}


def _show_all(*rules: tuple[str, str]) -> dict[str, Any]:
    return {"logic": "and", "rules": [{"field_id": field, "op": "eq", "value": value} for field, value in rules]}


def _q(
    qid: str,
    label: str,
    *,
    type: str = "short_answer",
    required: bool = False,
    options: list | None = None,
    placeholder: str = "",
    default_value: str | list | None = "",
    description: str = "",
    system: bool = False,
    system_tag: str | None = None,
    storage: str = "core",
    field_key: str | None = None,
    extra_key: str | None = None,
    visibility: dict | None = None,
    repeatable: dict | None = None,
) -> dict[str, Any]:
    return {
        "id": qid,
        "field_key": qid if field_key is None and storage == "core" else (field_key or ""),
        "extra_key": extra_key or "",
        "label": label,
        "description": description,
        "type": type,
        "required": required,
        "options": list(options or []),
        "placeholder": placeholder,
        "default_value": [] if default_value is None and type in {"checkboxes", "skills"} else default_value,
        "system": system,
        "system_tag": system_tag,
        "storage": storage,
        "visibility": visibility,
        "repeatable": repeatable,
    }


def default_gts_schema() -> dict[str, Any]:
    return {
        "title": "Graduate Tracer Survey",
        "description": "CHED-aligned graduate tracer used during registration and in the alumni portal.",
        "intro": "Please complete each section. Required fields are marked with an asterisk. Your occupation is used for career alignment.",
        "confirmation_message": "Thank you. Your Graduate Tracer Survey has been saved.",
        "accepting_responses": True,
        "start_date": None,
        "end_date": None,
        "allow_alumni_edit": True,
        "sections": [
            {
                "id": "general",
                "key": "general",
                "name": "General Information",
                "description": "Your name, degree, and household background.",
                "subsections": [
                    {
                        "id": "general_main",
                        "name": "",
                        "description": "",
                        "questions": [
                            _q("first_name", "Given name", required=True, placeholder="Enter your given name", system=True, system_tag="identity"),
                            _q("middle_name", "Middle name", placeholder="Enter your middle name"),
                            _q("last_name", "Last name", required=True, placeholder="Enter your last name", system=True, system_tag="identity"),
                            _q("husband_surname", "Husband's surname", placeholder="Enter your husband's surname", description="If applicable."),
                            _q("country", "Country of residence", placeholder="Enter your country of residence", default_value="Philippines"),
                            _q("year_graduated", "Year graduated", required=True, placeholder="Enter year graduated, e.g. 2024", system=True, system_tag="identity"),
                            _q("degree", "Bachelor's degree earned", required=True, placeholder="Enter your bachelor's degree", system=True, system_tag="identity"),
                            _q("primary_guardian", "Primary guardian/s", type="dropdown", options=list(GUARDIAN_OPTIONS)),
                            _q("guardian_degree_completed", "Did your primary guardian/s complete a college degree?", type="yes_no"),
                        ],
                    }
                ],
            },
            {
                "id": "employment",
                "key": "employment",
                "name": "Employment",
                "description": "Your first job after graduation and your current work.",
                "subsections": [
                    {
                        "id": "first_job",
                        "name": "First job after graduation",
                        "description": "Your first job after you earned your bachelor's degree.",
                        "questions": [
                            _q(
                                "ever_employed",
                                "Have you been employed after graduation?",
                                type="yes_no",
                                required=True,
                                system=True,
                                system_tag="alignment",
                                description="Include full-time, part-time, contractual, and self-employed work.",
                            ),
                            _q(
                                "first_related",
                                "Was your first job related to your college degree?",
                                type="yes_no",
                                required=True,
                                visibility=_show("ever_employed", "Yes"),
                            ),
                            _q(
                                "first_occ",
                                "Occupation (first job)",
                                placeholder="Enter your first job title after graduation",
                                required=True,
                                system=True,
                                system_tag="alignment",
                                visibility=_show("ever_employed", "Yes"),
                            ),
                            _q(
                                "first_emp",
                                "Employer (first job)",
                                placeholder="Enter your first employer after graduation",
                                required=True,
                                visibility=_show("ever_employed", "Yes"),
                            ),
                            _q(
                                "first_stat",
                                "Employment status (first job)",
                                type="multiple_choice",
                                options=list(EMPLOYMENT_STATUS_OPTIONS),
                                required=True,
                                visibility=_show("ever_employed", "Yes"),
                            ),
                            _q(
                                "time_to_first_job",
                                "After graduation, how long did it take you to be employed?",
                                type="dropdown",
                                options=list(TIME_TO_FIRST_JOB_OPTIONS),
                                visibility=_show("ever_employed", "Yes"),
                            ),
                            _q(
                                "find_job",
                                "How did you find your first job?",
                                type="dropdown",
                                options=list(HOW_FOUND_FIRST_JOB),
                                visibility=_show("ever_employed", "Yes"),
                            ),
                            _q(
                                "other_find_job",
                                "Please specify",
                                placeholder="Please specify how you found your first job",
                                visibility=_show("find_job", "Other"),
                            ),
                            _q(
                                "first_sal",
                                "Salary range (first job)",
                                type="dropdown",
                                options=list(SALARY_OPTIONS),
                                visibility=_show("ever_employed", "Yes"),
                            ),
                        ],
                    },
                    {
                        "id": "current_employment",
                        "name": "Current Employment",
                        "description": "The job you hold now.",
                        "questions": [
                            _q(
                                "is_currently_employed",
                                "Are you currently employed?",
                                type="yes_no",
                                required=True,
                                system=True,
                                system_tag="alignment",
                            ),
                            _q(
                                "present_job_is_first",
                                "Is your present job also your first job after college?",
                                type="yes_no",
                                system=True,
                                system_tag="alignment",
                                visibility=_show("is_currently_employed", "Yes"),
                            ),
                            _q(
                                "pres_occ",
                                "Occupation (present)",
                                placeholder="Enter your current job title",
                                system=True,
                                system_tag="alignment",
                                visibility=_show_all(("is_currently_employed", "Yes"), ("present_job_is_first", "No")),
                            ),
                            _q(
                                "pres_emp",
                                "Employer",
                                placeholder="Enter your current employer",
                                visibility=_show_all(("is_currently_employed", "Yes"), ("present_job_is_first", "No")),
                            ),
                            _q(
                                "pres_head",
                                "Immediate head",
                                placeholder="Enter your supervisor's name",
                                visibility=_show_all(("is_currently_employed", "Yes"), ("present_job_is_first", "No")),
                            ),
                            _q(
                                "pres_head_email",
                                "Immediate head email",
                                type="email",
                                placeholder="Enter your supervisor's email",
                                visibility=_show_all(("is_currently_employed", "Yes"), ("present_job_is_first", "No")),
                            ),
                            _q(
                                "pres_stay",
                                "Length of stay",
                                placeholder="Enter how long you have been in this job",
                                visibility=_show_all(("is_currently_employed", "Yes"), ("present_job_is_first", "No")),
                            ),
                            _q(
                                "present_related_degree",
                                "Related to your degree?",
                                type="yes_no",
                                visibility=_show_all(("is_currently_employed", "Yes"), ("present_job_is_first", "No")),
                            ),
                        ],
                    },
                    {
                        "id": "employment_details",
                        "name": "Employment Details",
                        "description": "Unemployment reasons and skills, if they apply.",
                        "questions": [
                            _q(
                                "reason_past",
                                "Reason/s (past unemployment)",
                                type="checkboxes",
                                options=list(UNEMPLOYMENT_REASONS),
                                default_value=[],
                                visibility=_show("ever_employed", "No"),
                            ),
                            _q(
                                "reason_past_other",
                                "Please specify",
                                placeholder="Please specify the reason",
                                visibility=_show("reason_past", "Other", "includes"),
                            ),
                            _q(
                                "reason_current",
                                "Reason/s (current unemployment)",
                                type="checkboxes",
                                options=list(UNEMPLOYMENT_REASONS),
                                default_value=[],
                                visibility=_show("is_currently_employed", "No"),
                            ),
                            _q(
                                "reason_current_other",
                                "Please specify",
                                placeholder="Please specify the reason",
                                visibility=_show("reason_current", "Other", "includes"),
                            ),
                            _q(
                                "skills",
                                "Skills",
                                type="skills",
                                description="Separate each skill with a comma.",
                                placeholder="Python, JavaScript, SQL",
                                default_value=[],
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "studies",
                "key": "studies",
                "name": "Further Studies",
                "description": "Programs you started after your bachelor's degree.",
                "subsections": [
                    {
                        "id": "studies_main",
                        "name": "",
                        "description": "",
                        "questions": [
                            _q(
                                "enroll_further_studies",
                                "Did you enroll in further studies after graduation?",
                                type="yes_no",
                                default_value="No",
                            ),
                            _q(
                                "further_studies",
                                "Study programs",
                                type="repeatable_group",
                                system=True,
                                system_tag="studies",
                                visibility=_show("enroll_further_studies", "Yes"),
                                default_value=[],
                                repeatable={
                                    "add_label": "Add program",
                                    "remove_label": "Remove",
                                    "item_label": "Program",
                                    "fields": [
                                        {"id": "school", "label": "Institution", "type": "short_answer", "placeholder": "Enter the school or university", "required": True},
                                        {"id": "course_degree", "label": "Program", "type": "short_answer", "placeholder": "Enter the program or degree", "required": True},
                                        {"id": "year_enrolled", "label": "Year enrolled", "type": "short_answer", "placeholder": "Enter the year enrolled"},
                                        {"id": "scholarship", "label": "Scholarship", "type": "short_answer", "placeholder": "Enter scholarship, if any"},
                                        {"id": "is_graduated", "label": "Graduated", "type": "yes_no", "default_value": "No"},
                                    ],
                                },
                            ),
                        ],
                    }
                ],
            },
            {
                "id": "feedback",
                "key": "feedback",
                "name": "Institutional Feedback",
                "description": "Seminars, engagement, and suggestions for AUF.",
                "subsections": [
                    {
                        "id": "feedback_main",
                        "name": "",
                        "description": "",
                        "questions": [
                            _q(
                                "participated_seminars",
                                "Did you participate in AUF career development seminars?",
                                type="yes_no",
                            ),
                            _q(
                                "seminars_helpful",
                                "Were these seminars helpful in your employment experience?",
                                type="yes_no",
                                visibility=_show("participated_seminars", "Yes"),
                            ),
                            _q(
                                "mentoring_rating",
                                "Mentoring others",
                                type="scale",
                                options=INSPIRE_OPTIONS,
                                description="How much has AUF inspired you to do each of the following?",
                            ),
                            _q(
                                "advocacy_rating",
                                "Participating in advocacy groups",
                                type="scale",
                                options=INSPIRE_OPTIONS,
                            ),
                            _q(
                                "volunteering_rating",
                                "Volunteering (unpaid service)",
                                type="scale",
                                options=INSPIRE_OPTIONS,
                            ),
                            _q(
                                "engagement_desc",
                                "Description of your engagements and their impact",
                                type="paragraph",
                                placeholder="Describe your engagements and their impact",
                            ),
                            _q(
                                "curriculum_suggestions.include_new_courses",
                                "Include new courses/subjects",
                                field_key="curriculum_suggestions.include_new_courses",
                                placeholder="Enter your suggestion",
                                description="Suggestions for improving the curriculum.",
                            ),
                            _q(
                                "curriculum_suggestions.develop_competencies",
                                "Develop more competencies",
                                field_key="curriculum_suggestions.develop_competencies",
                                placeholder="Enter your suggestion",
                            ),
                            _q(
                                "curriculum_suggestions.improve_teaching_methods",
                                "Improve teaching methods",
                                field_key="curriculum_suggestions.improve_teaching_methods",
                                placeholder="Enter your suggestion",
                            ),
                            _q(
                                "curriculum_suggestions.increase_ojt_duration",
                                "Increase OJT duration",
                                field_key="curriculum_suggestions.increase_ojt_duration",
                                placeholder="Enter your suggestion",
                            ),
                            _q(
                                "curriculum_suggestions.other",
                                "Other suggestions",
                                field_key="curriculum_suggestions.other",
                                placeholder="Enter your suggestion",
                            ),
                        ],
                    }
                ],
            },
        ],
    }


def clone_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    return deepcopy(schema or default_gts_schema())


FIRST_JOB_ORDER = (
    "ever_employed",
    "first_related",
    "first_occ",
    "first_emp",
    "first_stat",
    "time_to_first_job",
    "find_job",
    "other_find_job",
    "first_sal",
)

FIRST_JOB_PATCHES = {
    "ever_employed": {
        "label": "Have you been employed after graduation?",
        "description": "Include full-time, part-time, contractual, and self-employed work.",
        "required": True,
        "type": "yes_no",
    },
    "first_related": {
        "label": "Was your first job related to your college degree?",
        "required": True,
        "type": "yes_no",
        "visibility": _show("ever_employed", "Yes"),
    },
    "first_occ": {
        "label": "Occupation (first job)",
        "placeholder": "Enter your first job title after graduation",
        "required": True,
        "visibility": _show("ever_employed", "Yes"),
    },
    "first_emp": {
        "label": "Employer (first job)",
        "placeholder": "Enter your first employer after graduation",
        "required": True,
        "visibility": _show("ever_employed", "Yes"),
    },
    "first_stat": {
        "label": "Employment status (first job)",
        "type": "multiple_choice",
        "required": True,
        "options": list(EMPLOYMENT_STATUS_OPTIONS),
        "visibility": _show("ever_employed", "Yes"),
    },
    "first_sal": {
        "label": "Salary range (first job)",
        "visibility": _show("ever_employed", "Yes"),
    },
}


def apply_core_first_job_schema(schema: dict[str, Any] | None) -> bool:
    """Keep first-job identity questions visible, required, and in a consistent order."""
    data = schema if isinstance(schema, dict) else {}
    changed = False
    template_by_id = {
        question["id"]: deepcopy(question)
        for question in flatten_questions(default_gts_schema())
        if question.get("id") in FIRST_JOB_PATCHES
    }
    employment = next(
        (section for section in data.get("sections") or [] if (section.get("key") or section.get("id")) == "employment"),
        None,
    )
    if not employment:
        return False
    subsections = employment.setdefault("subsections", [])
    first_job = next((sub for sub in subsections if sub.get("id") == "first_job"), None)
    if first_job is None:
        first_job = {"id": "first_job", "name": "", "description": "", "questions": []}
        subsections.insert(0, first_job)
        changed = True
    wanted_name = "First job after graduation"
    wanted_desc = "Your first job after you earned your bachelor's degree."
    if first_job.get("name") != wanted_name:
        first_job["name"] = wanted_name
        changed = True
    if first_job.get("description") != wanted_desc:
        first_job["description"] = wanted_desc
        changed = True

    questions = first_job.setdefault("questions", [])
    by_id = {question.get("id"): question for question in questions}
    for qid, patch in FIRST_JOB_PATCHES.items():
        question = by_id.get(qid)
        if question is None:
            question = deepcopy(template_by_id.get(qid) or {"id": qid})
            questions.append(question)
            by_id[qid] = question
            changed = True
        for key, value in patch.items():
            current = question.get(key)
            if current != value:
                question[key] = deepcopy(value)
                changed = True

    known = [by_id[qid] for qid in FIRST_JOB_ORDER if qid in by_id]
    rest = [question for question in questions if question.get("id") not in FIRST_JOB_ORDER]
    reordered = known + rest
    if [question.get("id") for question in questions] != [question.get("id") for question in reordered]:
        first_job["questions"] = reordered
        changed = True
    return changed


SECTION_INSTRUCTIONS = {
    "general": "Your name, degree, and household background.",
    "employment": "Your first job after graduation and your current work.",
    "studies": "Programs you started after your bachelor's degree.",
    "feedback": "Seminars, engagement, and suggestions for AUF.",
}

SUBSECTION_INSTRUCTIONS = {
    "current_employment": "The job you hold now.",
    "employment_details": "Unemployment reasons and skills, if they apply.",
}

QUESTION_INSTRUCTIONS = {
    "skills": "Separate each skill with a comma.",
    "mentoring_rating": "How much has AUF inspired you to do each of the following?",
    "curriculum_suggestions.include_new_courses": "Suggestions for improving the curriculum.",
}


def apply_study_field_requirements(schema: dict[str, Any] | None) -> bool:
    """Program and institution are required on each further-study row the graduate keeps."""
    data = schema if isinstance(schema, dict) else {}
    changed = False
    for question in flatten_questions(data):
        if question.get("id") != "further_studies" or question.get("type") != "repeatable_group":
            continue
        repeatable = question.setdefault("repeatable", {})
        for field in repeatable.get("fields") or []:
            if field.get("id") in {"course_degree", "school"} and not field.get("required"):
                field["required"] = True
                changed = True
    return changed


def apply_registration_instructions(schema: dict[str, Any] | None) -> bool:
    """Keep alumni-facing section and question instructions short and consistent."""
    data = schema if isinstance(schema, dict) else {}
    changed = False
    for section in data.get("sections") or []:
        key = section.get("key") or section.get("id")
        wanted = SECTION_INSTRUCTIONS.get(key)
        if wanted and section.get("description") != wanted:
            section["description"] = wanted
            changed = True
        for subsection in section.get("subsections") or []:
            sub_wanted = SUBSECTION_INSTRUCTIONS.get(subsection.get("id"))
            if sub_wanted and subsection.get("description") != sub_wanted:
                subsection["description"] = sub_wanted
                changed = True
            for question in subsection.get("questions") or []:
                q_wanted = QUESTION_INSTRUCTIONS.get(question.get("id"))
                if q_wanted and question.get("description") != q_wanted:
                    question["description"] = q_wanted
                    changed = True
    return changed


def extra_question_from_row(row) -> dict[str, Any]:
    type_map = {
        "short_answer": "short_answer",
        "paragraph": "paragraph",
        "multiple_choice": "dropdown",
        "scale": "scale",
        "checkboxes": "checkboxes",
        "dropdown": "dropdown",
        "yes_no": "yes_no",
        "date": "date",
        "number": "number",
    }
    return _q(
        f"extra_{row.id}",
        row.label,
        type=type_map.get(row.input_type, "short_answer"),
        required=bool(row.required),
        options=list(row.options or []),
        storage="extra",
        field_key="",
        extra_key=str(row.id),
        system=False,
    )


def merge_legacy_extras(schema: dict[str, Any], rows: list) -> dict[str, Any]:
    schema = clone_schema(schema)
    existing = {question["id"] for _, _, question in iter_questions(schema)}
    by_section = {section["key"]: section for section in schema.get("sections") or []}
    for row in rows:
        qid = f"extra_{row.id}"
        if qid in existing:
            continue
        section = by_section.get(row.section_key) or by_section.get("feedback")
        if not section:
            continue
        subs = section.setdefault("subsections", [])
        if not subs:
            subs.append({"id": f"{section['id']}_main", "name": "", "description": "", "questions": []})
        subs[-1].setdefault("questions", []).append(extra_question_from_row(row))
        existing.add(qid)
    return schema


def iter_questions(schema: dict[str, Any]):
    for section in schema.get("sections") or []:
        for subsection in section.get("subsections") or []:
            for question in subsection.get("questions") or []:
                yield section, subsection, question


def flatten_questions(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return [question for _, _, question in iter_questions(schema)]


def question_count(schema: dict[str, Any]) -> int:
    return len(flatten_questions(schema))


def option_values(question: dict[str, Any]) -> list[str]:
    values = []
    for item in question.get("options") or []:
        if isinstance(item, dict):
            values.append(str(item.get("value", item.get("label", ""))))
        else:
            values.append(str(item))
    return values
