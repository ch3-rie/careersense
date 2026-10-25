"""Regression coverage for the production extraction pass."""

import json
from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException

from app.services.files import detect_resume_kind
from app.services.parser import (
    apply_verified_registry,
    extract_resume_info,
    map_to_gts_fields,
    reconcile_extractions,
)
from app.services.parser_course import align_occupation_to_degree
from app.services.parser_document import assess_text_quality, extract_document
from app.services.parser_extract import extract_salary
from app.services.parser_llm import extract_with_llm

HELD_OUT = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "parser_eval" / "heldout.json").read_text(encoding="utf-8")
)


def _norm(value):
    return " ".join(str(value or "").lower().split())


def _score_case(parsed, expected):
    checks = []
    gts = map_to_gts_fields(parsed)

    def add(predicted, wanted):
        checks.append((_norm(predicted) == _norm(wanted), bool(_norm(predicted)), bool(_norm(wanted))))

    for key in ("first_name", "middle_name", "last_name", "year_graduated", "country", "is_currently_employed"):
        if key in expected:
            add(parsed.get(key), expected[key])
    if "degree_contains" in expected:
        degree = parsed.get("degree") or ""
        checks.append((expected["degree_contains"].lower() in degree.lower(), bool(degree), True))
    if "current_title" in expected:
        add(gts.get("pres_occ"), expected["current_title"])
    if "current_employer" in expected:
        add(gts.get("pres_emp"), expected["current_employer"])
    if "first_title" in expected:
        add(gts.get("first_occ"), expected["first_title"])
    if "salary" in expected:
        found = next((job.get("salary_range", "") for job in parsed.get("experiences") or [] if job.get("salary_range")), "")
        add(found, expected["salary"])
    if "skills" in expected:
        predicted = {_norm(skill) for skill in parsed.get("skills") or []}
        wanted = {_norm(skill) for skill in expected["skills"]}
        for skill in wanted:
            checks.append((skill in predicted, skill in predicted, True))
        for skill in predicted - wanted:
            checks.append((False, True, False))
    return checks


def _metrics(rows):
    tp = sum(1 for ok, predicted, wanted in rows if ok and wanted)
    fp = sum(1 for ok, predicted, wanted in rows if predicted and not ok)
    fn = sum(1 for ok, predicted, wanted in rows if wanted and not ok)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def test_held_out_resumes_are_not_regressed():
    rows = []
    failures = []
    for case in HELD_OUT:
        parsed, _source = extract_resume_info(case["text"])
        scored = _score_case(parsed, case["expected"])
        rows.extend(scored)
        if any(not item[0] for item in scored):
            failures.append(case["id"])
    metrics = _metrics(rows)
    assert not failures, metrics
    assert metrics["f1"] >= 0.945
    assert metrics["precision"] >= 0.97


@pytest.mark.parametrize(
    ("degree", "title", "status"),
    [
        ("Bachelor of Science in Information Technology", "Software Engineer", "Aligned"),
        ("Bachelor of Science in Business Administration", "Marketing Specialist", "Aligned"),
        ("Bachelor of Science in Accountancy", "Accountant", "Aligned"),
        ("Bachelor of Science in Nursing", "Staff Nurse", "Aligned"),
        ("Bachelor of Science in Elementary Education", "Elementary Teacher", "Aligned"),
        ("Bachelor of Science in Psychology", "Guidance Counselor", "Aligned"),
        ("Bachelor of Science in Hospitality Management", "Front Desk", "Aligned"),
        ("Bachelor of Science in Civil Engineering", "Civil Engineer", "Aligned"),
        ("Bachelor of Science in Information Technology", "Accountant", "Misaligned"),
        ("Bachelor of Science in Information Technology", "Analyst", "Unknown"),
    ],
)
def test_course_domains(degree, title, status):
    result = align_occupation_to_degree(degree, title)
    assert result.status == status


def test_employer_industry_does_not_align_a_generic_title():
    result = align_occupation_to_degree(
        "Bachelor of Science in Information Technology",
        "Analyst",
        employer="Cloud Software Technologies",
        skills=["Excel"],
    )
    assert result.status == "Unknown"
    assert result.related_to_degree == ""


def test_provenance_and_missing_confidence_are_recorded():
    text = """\
Ana Cruz
ana@example.com
Philippines

Education
Bachelor of Science in Information Technology
Sample University
2018-2022

Experience
Software Engineer
North Labs
2022-Present

Skills
Python
"""
    parsed, _source = extract_resume_info(text)
    meta = parsed["extraction_meta"]
    assert meta["provenance"]
    degree = next(row for row in meta["provenance"] if row["field"] == "degree")
    assert degree["confidence"] == "high"
    assert degree["validation"] == "supported"
    assert degree["excerpt"]
    middle = next(row for row in meta["provenance"] if row["field"] == "middle_name")
    assert middle["confidence"] == "missing"
    assert meta["text_quality"]["sufficient"] is True
    assert "June" in meta["assumptions"][0]


def test_unsupported_model_employer_is_rejected_with_a_reason():
    resume = "Software Engineer\nNorth Labs\n2022-Present\n"
    merged, _confidence = reconcile_extractions(
        {"experiences": [{"job_title": "Software Engineer", "employer": "Invented Dynamics", "start_date": "2022"}]},
        {"experiences": [{"job_title": "Software Engineer", "employer": "North Labs", "start_date": "2022"}], "skills": []},
        resume,
    )
    assert merged["experiences"][0]["employer"] == "North Labs"
    assert any(row["value"] == "Invented Dynamics" for row in merged["_rejections"])


def test_same_employer_different_years_stay_separate_jobs():
    text = """\
Paolo Santos
psantos@example.com

Education
Bachelor of Science in Information Technology
Sample University
2015-2019

Experience
Junior Developer
Acme Software Inc.
2019-2021
Senior Developer
Acme Software Inc.
2021-Present

Skills
Java
"""
    parsed, _source = extract_resume_info(text)
    titles = [job["job_title"] for job in parsed["experiences"]]
    assert titles == ["Junior Developer", "Senior Developer"]
    assert parsed["is_currently_employed"] == "Yes"
    gts = map_to_gts_fields(parsed)
    assert gts["derivation"]["current_job_rule"] == "single_current"
    assert gts["first_occ"] == "Junior Developer"
    assert gts["pres_occ"] == "Senior Developer"


def test_missing_end_date_is_not_current_employment():
    text = """\
Elena Ramos
eramos@example.com

Education
Bachelor of Science in Accountancy
Sample College
2014-2018

Experience
Auditor
Reyes Audit Firm
2019

Skills
Excel
"""
    parsed, _source = extract_resume_info(text)
    job = parsed["experiences"][0]
    assert job["is_current"] == ""
    assert parsed["is_currently_employed"] == ""
    assert parsed["ever_employed"] == "Yes"
    gts = map_to_gts_fields(parsed)
    assert gts["pres_occ"] == ""
    assert gts["is_currently_employed"] == ""


def test_hourly_pay_is_not_forced_into_a_monthly_band():
    parsed = extract_salary("Salary: PHP 250 per hour")
    assert parsed["current"] == ""
    assert parsed["state"] == "uncertain"


def test_duty_skills_are_inferred_and_not_declared():
    text = """\
Liza Mendoza
lmendoza@example.com

Education
Bachelor of Science in Information Technology
Sample University
2018-2022

Experience
Software Engineer
Sample Labs
2022-Present
Built internal tools with Python for the clinic staff.
"""
    parsed, _source = extract_resume_info(text)
    assert parsed["skills"] == []
    assert any(row["name"].lower() == "python" and row["evidence_type"] == "job_description" for row in parsed["inferred_skills"])


def test_undated_jobs_do_not_become_unemployment():
    gts = map_to_gts_fields({
        "year_graduated": "2020",
        "experiences": [{"job_title": "Analyst", "employer": "Labs", "start_date": "", "end_date": "", "is_current": ""}],
    })
    assert gts["ever_employed"] == ""
    assert gts["derivation"]["employment_after_graduation"] == "unknown"


def test_text_quality_rejects_symbol_noise():
    noise = "? " * 80
    assert assess_text_quality(noise)["sufficient"] is False
    assert assess_text_quality("Ana Cruz software engineer at North Labs since 2022 with Python SQL and Git.")["sufficient"] is True


def test_pdf_page_limit_and_encryption_are_rejected():
    long_doc = fitz.open()
    for _index in range(21):
        long_doc.new_page()
    long_bytes = long_doc.tobytes()
    long_doc.close()
    with pytest.raises(HTTPException) as raised:
        detect_resume_kind(long_bytes, "resume.pdf", "application/pdf")
    assert raised.value.status_code == 400

    locked = fitz.open()
    locked.new_page()
    locked_bytes = locked.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner-secret", user_pw="user-secret")
    locked.close()
    with pytest.raises(HTTPException) as raised:
        detect_resume_kind(locked_bytes, "resume.pdf", "application/pdf")
    assert "password" in raised.value.detail.lower()


def test_unreadable_pdf_does_not_raise():
    view = extract_document("broken.pdf", b"%PDF-1.4\nnot-a-real-pdf")
    assert view.source in {"failed", "empty"}
    parsed, source = extract_resume_info(view.text, document=view)
    assert source in {"failed", "empty"}
    assert parsed == {} or not parsed.get("first_name")


def test_registry_degree_replaces_the_resume_guess():
    class Record:
        degree = "Bachelor of Science in Nursing"
        year_graduated = "2019"

    prefill = apply_verified_registry({"degree": "BS Information Technology", "year_graduated": "2022"}, Record())
    assert prefill["degree"] == "Bachelor of Science in Nursing"
    assert prefill["year_graduated"] == "2019"
    assert prefill["registry_overrides"][0]["source"] == "verified_registry"


def test_missing_model_package_returns_none(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    def _boom():
        raise ImportError("llama-index-llms-openai is not installed")

    monkeypatch.setattr("app.services.parser_llm._build_llm", _boom)
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert extract_with_llm("Ana Cruz\nSoftware Engineer\n") is None
    finally:
        get_settings.cache_clear()
