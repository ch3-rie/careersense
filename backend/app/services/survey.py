"""Published Graduate Tracer Survey schema and answer checks."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import GtsQuestion, SurveyDefinition, SurveyVersion
from app.survey_default import (
    apply_core_first_job_schema,
    apply_registration_instructions,
    apply_study_field_requirements,
    clone_schema,
    default_gts_schema,
    flatten_questions,
    iter_questions,
    merge_legacy_extras,
    option_values,
    question_count,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_visibility(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    if isinstance(raw, dict) and raw.get("rules"):
        rules = []
        for rule in raw.get("rules") or []:
            field_id = str(rule.get("field_id") or "").strip()
            if not field_id:
                continue
            rules.append(
                {
                    "field_id": field_id,
                    "op": rule.get("op") or "eq",
                    "value": rule.get("value", ""),
                }
            )
        if not rules:
            return None
        logic = raw.get("logic") if raw.get("logic") in {"and", "or"} else "and"
        return {"logic": logic, "rules": rules}
    if isinstance(raw, dict) and raw.get("field_id"):
        return {
            "logic": "and",
            "rules": [
                {
                    "field_id": str(raw.get("field_id")),
                    "op": raw.get("op") or "eq",
                    "value": raw.get("value", ""),
                }
            ],
        }
    return None


def sanitize_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    data = clone_schema(schema or default_gts_schema())
    data["title"] = str(data.get("title") or "Graduate Tracer Survey").strip() or "Graduate Tracer Survey"
    data["description"] = str(data.get("description") or "")
    data["intro"] = str(data.get("intro") or "")
    data["confirmation_message"] = str(data.get("confirmation_message") or "")
    data["accepting_responses"] = bool(data.get("accepting_responses", True))
    data["allow_alumni_edit"] = bool(data.get("allow_alumni_edit", True))
    data["start_date"] = data.get("start_date") or None
    data["end_date"] = data.get("end_date") or None
    sections = []
    seen_ids: set[str] = set()
    for index, section in enumerate(data.get("sections") or []):
        sid = str(section.get("id") or f"section_{index}").strip() or f"section_{index}"
        if sid in seen_ids:
            sid = f"{sid}_{index}"
        seen_ids.add(sid)
        subsections = []
        for sub_index, sub in enumerate(section.get("subsections") or []):
            sub_id = str(sub.get("id") or f"{sid}_sub_{sub_index}").strip() or f"{sid}_sub_{sub_index}"
            questions = []
            for q_index, question in enumerate(sub.get("questions") or []):
                qid = str(question.get("id") or f"q_{sid}_{sub_index}_{q_index}").strip()
                if not qid:
                    continue
                cleaned = deepcopy(question)
                cleaned["id"] = qid
                cleaned["label"] = str(question.get("label") or "Untitled question").strip() or "Untitled question"
                cleaned["description"] = str(question.get("description") or "")
                cleaned["placeholder"] = str(question.get("placeholder") or "")
                cleaned["type"] = str(question.get("type") or "short_answer")
                cleaned["visibility"] = _normalize_visibility(question.get("visibility"))
                cleaned["options"] = list(question.get("options") or [])
                cleaned["required"] = bool(question.get("required"))
                cleaned["storage"] = question.get("storage") or ("extra" if not question.get("field_key") else "core")
                if cleaned["storage"] == "extra":
                    cleaned["extra_key"] = str(question.get("extra_key") or qid)
                default_value = question.get("default_value")
                cleaned["default_value"] = default_value if default_value is not None else ""
                validation = question.get("validation")
                cleaned["validation"] = dict(validation) if isinstance(validation, dict) else {}
                questions.append(cleaned)
            subsections.append(
                {
                    "id": sub_id,
                    "name": str(sub.get("name") or ""),
                    "description": str(sub.get("description") or ""),
                    "questions": questions,
                }
            )
        if not subsections:
            subsections.append({"id": f"{sid}_main", "name": "", "description": "", "questions": []})
        sections.append(
            {
                "id": sid,
                "key": str(section.get("key") or sid),
                "name": str(section.get("name") or "Untitled section").strip() or "Untitled section",
                "description": str(section.get("description") or ""),
                "subsections": subsections,
            }
        )
    if not sections:
        data["sections"] = default_gts_schema()["sections"]
    else:
        data["sections"] = sections
    _scrub_visibility(data)
    return data


def _scrub_visibility(schema: dict[str, Any]) -> None:
    """Drop broken or circular rules so auto-save still succeeds after deletes."""
    by_id = {question["id"]: question for question in flatten_questions(schema)}
    for question in by_id.values():
        vis = _normalize_visibility(question.get("visibility"))
        if not vis:
            question["visibility"] = None
            continue
        rules = [
            rule
            for rule in vis.get("rules") or []
            if rule.get("field_id") in by_id and rule.get("field_id") != question["id"]
        ]
        question["visibility"] = {"logic": vis.get("logic") or "and", "rules": rules} if rules else None

    by_id = {question["id"]: question for question in flatten_questions(schema)}
    for question in by_id.values():
        seen: set[str] = set()
        current = question
        while current:
            qid = current["id"]
            if qid in seen:
                current["visibility"] = None
                break
            seen.add(qid)
            rules = (current.get("visibility") or {}).get("rules") or []
            if not rules:
                break
            current = by_id.get(rules[0].get("field_id"))



def _rule_matches(rule: dict[str, Any], answers: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    target = by_id.get(rule.get("field_id") or "")
    value = _answer_for(answers, target) if target else answers.get(rule.get("field_id"))
    expected = rule.get("value", "")
    op = rule.get("op") or "eq"
    if op == "includes":
        if isinstance(value, list):
            return expected in value
        return str(expected) in str(value or "")
    if op == "neq":
        return str(value or "") != str(expected or "")
    return str(value or "") == str(expected or "")


def _answer_for(answers: dict[str, Any], question: dict[str, Any] | None) -> Any:
    if not question:
        return None
    if question.get("storage") == "extra":
        extras = answers.get("extra_answers") or {}
        key = question.get("extra_key") or question.get("id")
        return extras.get(key, extras.get(str(question.get("id"))))
    key = question.get("field_key") or question.get("id")
    if "." in str(key):
        parent, child = str(key).split(".", 1)
        nested = answers.get(parent) or {}
        if isinstance(nested, dict):
            return nested.get(child)
        return None
    return answers.get(key)


def is_question_visible(question: dict[str, Any], answers: dict[str, Any], by_id: dict[str, dict[str, Any]], seen: set[str] | None = None) -> bool:
    vis = question.get("visibility") or {}
    rules = vis.get("rules") or []
    if not rules:
        return True
    seen = seen or set()
    qid = question.get("id")
    if qid in seen:
        return False
    seen.add(qid)
    results = []
    for rule in rules:
        parent = by_id.get(rule.get("field_id") or "")
        if parent and not is_question_visible(parent, answers, by_id, seen):
            results.append(False)
            continue
        results.append(_rule_matches(rule, answers, by_id))
    if vis.get("logic") == "or":
        return any(results)
    return all(results)


def survey_is_open(schema: dict[str, Any] | None, today: date | None = None) -> bool:
    if not schema:
        return True
    if not schema.get("accepting_responses", True):
        return False
    today = today or date.today()
    start = schema.get("start_date")
    end = schema.get("end_date")
    if start:
        try:
            start_d = date.fromisoformat(str(start)[:10])
            if today < start_d:
                return False
        except ValueError:
            pass
    if end:
        try:
            end_d = date.fromisoformat(str(end)[:10])
            if today > end_d:
                return False
        except ValueError:
            pass
    return True


SURVEY_CLOSED_DETAIL = "This survey is not currently accepting responses."
SURVEY_READONLY_DETAIL = "The Graduate Tracer Survey is currently read-only."


def require_survey_writable(schema: dict[str, Any] | None, *, alumni_status: str | None = None) -> None:
    if alumni_status == "Active" and not (schema or {}).get("allow_alumni_edit", True):
        raise HTTPException(status_code=403, detail=SURVEY_READONLY_DETAIL)
    if not survey_is_open(schema):
        raise HTTPException(status_code=400, detail=SURVEY_CLOSED_DETAIL)


def _repeatable_required_labels(question: dict[str, Any], answers: dict[str, Any]) -> list[str]:
    if question.get("type") != "repeatable_group":
        return []
    rows = _answer_for(answers, question)
    if not isinstance(rows, list):
        return []
    fields = (question.get("repeatable") or {}).get("fields") or []
    required_fields = [field for field in fields if isinstance(field, dict) and field.get("required")]
    missing: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in required_fields:
            if not str(row.get(field.get("id")) or "").strip():
                missing.append(str(field.get("label") or field.get("id") or "required field"))
    return missing


def required_answer_gaps(
    schema: dict[str, Any] | None,
    survey_data: dict[str, Any],
    extra_answers: dict[str, Any],
) -> list[str]:
    """Labels of visible required questions that are empty. Does not raise."""
    if not schema:
        return []
    answers = dict(survey_data or {})
    answers["extra_answers"] = extra_answers or {}
    by_id = {q["id"]: q for q in flatten_questions(schema)}
    missing: list[str] = []
    for question in by_id.values():
        if not is_question_visible(question, answers, by_id):
            continue
        if question.get("type") == "repeatable_group":
            missing.extend(_repeatable_required_labels(question, answers))
            continue
        if not question.get("required"):
            continue
        if question.get("type") == "skills":
            continue
        value = _answer_for(answers, question)
        if isinstance(value, list):
            empty = not any(str(item).strip() for item in value)
        else:
            empty = not str(value or "").strip()
        if empty:
            missing.append(str(question.get("label") or question.get("id") or "required question"))
    return missing


def validate_required_answers(schema: dict[str, Any], survey_data: dict[str, Any], extra_answers: dict[str, Any]) -> None:
    answers = dict(survey_data or {})
    answers["extra_answers"] = extra_answers or {}
    by_id = {q["id"]: q for q in flatten_questions(schema)}
    for question in by_id.values():
        if not is_question_visible(question, answers, by_id):
            continue
        if question.get("type") == "repeatable_group":
            gaps = _repeatable_required_labels(question, answers)
            if gaps:
                raise HTTPException(status_code=400, detail=f"Please answer: {gaps[0]}.")
            continue
        if not question.get("required"):
            continue
        if question.get("type") == "skills":
            continue
        value = _answer_for(answers, question)
        if isinstance(value, list):
            missing = not any(str(item).strip() for item in value)
            text = " ".join(str(item) for item in value)
        else:
            text = str(value or "").strip()
            missing = not text
        if missing:
            raise HTTPException(status_code=400, detail=f'Please answer: {question.get("label") or "required question"}.')
        rules = question.get("validation") if isinstance(question.get("validation"), dict) else {}
        min_length = rules.get("min_length")
        max_length = rules.get("max_length")
        if min_length not in (None, ""):
            try:
                if len(text) < int(min_length):
                    raise HTTPException(status_code=400, detail=f'Please enter at least {min_length} characters for: {question.get("label")}.')
            except (TypeError, ValueError):
                pass
        if max_length not in (None, ""):
            try:
                if len(text) > int(max_length):
                    raise HTTPException(status_code=400, detail=f'Please keep "{question.get("label")}" under {max_length} characters.')
            except (TypeError, ValueError):
                pass
        if question.get("type") == "number" and text:
            try:
                number = float(text)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f'Please enter a number for: {question.get("label")}.') from exc
            minimum = rules.get("min")
            maximum = rules.get("max")
            try:
                if minimum not in (None, "") and number < float(minimum):
                    raise HTTPException(status_code=400, detail=f'"{question.get("label")}" must be at least {minimum}.')
                if maximum not in (None, "") and number > float(maximum):
                    raise HTTPException(status_code=400, detail=f'"{question.get("label")}" must be at most {maximum}.')
            except (TypeError, ValueError):
                pass


def ensure_gts_survey(db: Session) -> SurveyDefinition:
    row = db.query(SurveyDefinition).filter(SurveyDefinition.slug == "gts").one_or_none()
    extras = (
        db.query(GtsQuestion)
        .filter(GtsQuestion.is_core.is_(False), GtsQuestion.active.is_(True))
        .order_by(GtsQuestion.order_index, GtsQuestion.id)
        .all()
    )
    if row:
        return row
    schema = merge_legacy_extras(default_gts_schema(), extras)
    schema = sanitize_schema(schema)
    now = _now()
    row = SurveyDefinition(
        slug="gts",
        draft_schema=schema,
        published_schema=schema,
        published_version=1,
        draft_updated_at=now,
        published_at=now,
        dirty=False,
    )
    db.add(row)
    db.flush()
    db.add(
        SurveyVersion(
            survey_id=row.id,
            version_number=1,
            schema_json=schema,
            question_count=question_count(schema),
            published_at=now,
        )
    )
    db.flush()
    return row


def get_published_schema(db: Session) -> dict[str, Any]:
    row = ensure_gts_survey(db)
    schema = clone_schema(row.published_schema or default_gts_schema())
    apply_core_first_job_schema(schema)
    apply_study_field_requirements(schema)
    apply_registration_instructions(schema)
    schema = sanitize_schema(schema)
    schema["accepting_responses"] = True
    schema["allow_alumni_edit"] = True
    schema["start_date"] = None
    schema["end_date"] = None
    return schema



def extras_payload(schema: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for section, _sub, question in iter_questions(schema):
        if question.get("storage") != "extra":
            continue
        extra_id = question.get("extra_key") or question.get("id")
        items.append(
            {
                "id": extra_id,
                "schema_id": question.get("id"),
                "section_key": section.get("key"),
                "label": question.get("label"),
                "input_type": _legacy_input_type(question.get("type")),
                "options": option_values(question),
                "required": bool(question.get("required")),
                "order_index": 0,
            }
        )
    return items


def _legacy_input_type(qtype: str | None) -> str:
    mapping = {
        "short_answer": "short_answer",
        "paragraph": "paragraph",
        "multiple_choice": "multiple_choice",
        "dropdown": "multiple_choice",
        "scale": "scale",
        "yes_no": "multiple_choice",
        "checkboxes": "multiple_choice",
        "date": "short_answer",
        "number": "short_answer",
        "email": "short_answer",
    }
    return mapping.get(qtype or "", "short_answer")


