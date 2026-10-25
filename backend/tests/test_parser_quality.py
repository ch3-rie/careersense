"""Regression tests and scored evaluation for resume extraction."""

import json
from pathlib import Path

import pytest

from app.services.parser import extract_resume_info, map_to_gts_fields, reconcile_extractions
from app.services.parser_document import DocumentView, TextBlock
from app.services.parser_extract import (
    assess_extraction,
    extract_country,
    extract_heuristic,
    extract_salary,
    further_study_level,
    needs_deeper_extraction,
)

CASES = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "parser_eval" / "cases.json").read_text(encoding="utf-8")
)

COMPLETE = """\
Ana B. Dela Cruz
ana.delacruz@example.com
Angeles City, Pampanga, Philippines

Education
Bachelor of Science in Information Technology
Sample University
2018-2022

Work Experience
Software Engineer
North Labs
2022-Present

Skills
Python, SQL, Project Management
"""


@pytest.fixture
def no_model(monkeypatch):
    calls = []

    def _blocked(text):
        calls.append(True)
        return None

    monkeypatch.setattr("app.services.parser._extract_with_llm", _blocked)
    return calls


def test_structured_model_runs_only_when_the_first_pass_is_incomplete(monkeypatch):
    order = []
    real_heuristic = extract_heuristic

    def _llm(text):
        order.append("llm")
        return None

    def _heuristic(document):
        order.append("heuristic")
        return real_heuristic(document)

    monkeypatch.setattr("app.services.parser._extract_with_llm", _llm)
    monkeypatch.setattr("app.services.parser.extract_heuristic", _heuristic)
    parsed, source = extract_resume_info(COMPLETE)
    assert order == ["heuristic"]
    assert source == "heuristic"
    assert parsed["extraction_meta"]["model_called"] is False
    assert parsed["extraction_meta"]["second_pass"] == "none"

    incomplete = COMPLETE.replace("Python, SQL, Project Management\n", "")
    order.clear()
    parsed, _source = extract_resume_info(incomplete)
    assert order == ["heuristic", "llm"]
    assert parsed["extraction_meta"]["model_called"] is True
    assert parsed["extraction_meta"]["second_pass"] == "structured_model"


def test_complete_resume_keeps_builtin_fields_when_the_model_returns_nothing(no_model):
    parsed, source = extract_resume_info(COMPLETE)
    assert source == "heuristic"
    assert parsed["extraction_meta"]["model_called"] is False
    assert no_model == []
    assessment = parsed["extraction_meta"]["assessment"]
    assert assessment["name"] == "present"
    assert assessment["education"] == "present"
    assert assessment["employment"] == "present"
    assert assessment["skills"] == "present"
    assert assessment["salary"] == "absent"
    assert assessment["further_studies"] == "absent"


def test_empty_skills_section_requests_deeper_extraction(no_model):
    text = COMPLETE.replace("Python, SQL, Project Management\n", "")
    parsed, _source = extract_resume_info(text)
    assert parsed["extraction_meta"]["assessment"]["skills"] == "missing"
    assert parsed["extraction_meta"]["model_called"] is True
    assert no_model


def test_unparsed_further_studies_section_requests_deeper_extraction(no_model):
    text = COMPLETE + "\nFurther Studies\nAdvanced coursework\n"
    parsed, _source = extract_resume_info(text)
    assert parsed["extraction_meta"]["assessment"]["further_studies"] == "missing"
    assert parsed["extraction_meta"]["model_called"] is True
    assert no_model


def test_unparsed_salary_requests_deeper_extraction(no_model):
    parsed, _source = extract_resume_info(COMPLETE + "\nSalary: negotiable\n")
    assert parsed["extraction_meta"]["assessment"]["salary"] == "uncertain"
    assert parsed["extraction_meta"]["model_called"] is True
    assert no_model


def test_master_reaches_gts_prefill(no_model):
    parsed, _source = extract_resume_info(CASES[1]["text"])
    gts = map_to_gts_fields(parsed)
    assert gts["enroll_further_studies"] == "Yes"
    assert any("Master of Information Technology" in row["course_degree"] for row in gts["further_studies"])


def test_no_further_study_evidence_is_not_no(no_model):
    parsed, _source = extract_resume_info(COMPLETE)
    gts = map_to_gts_fields(parsed)
    assert gts["enroll_further_studies"] == ""
    assert parsed["further_studies_evidence"]["status"] == "not_detected"


@pytest.mark.parametrize(
    "phrase",
    [
        "Graduate Studies",
        "graduate studies in Business Administration",
        "Currently pursuing graduate studies",
        "Postgraduate Studies",
        "Post-graduate studies",
        "graduate program",
        "postgraduate program",
    ],
)
def test_graduate_studies_phrases(phrase):
    assert further_study_level(phrase) == "graduate"


def test_second_bachelor_diploma_and_certificate_rules(no_model):
    text = """\
Liza Santos
lsantos@example.com

Education
Bachelor of Science in Information Technology
Sample University
2014-2018
Bachelor of Science in Education
Sample College
2019-2023
Diploma in Teaching
Sample Institute
2024
Certificate in Nursing
Sample Hospital School
2024-2025

Certifications
AWS Cloud Practitioner
Google Analytics Certificate

Experience
Teacher
Sample School
2023-Present

Skills
Classroom Management
"""
    parsed, _source = extract_resume_info(text)
    programs = " ".join(row["course_degree"] for row in parsed["further_studies"])
    assert "Information Technology" in programs or "Education" in programs
    assert parsed["degree"] not in programs
    assert "Diploma in Teaching" in programs
    assert "Certificate in Nursing" in programs
    assert "AWS" not in programs
    assert "Google Analytics" not in programs
    assert map_to_gts_fields(parsed)["enroll_further_studies"] == "Yes"


def test_associate_and_expected_year(no_model):
    text = """\
Omar Santos
osantos@example.com

Education
Associate Degree in Computer Technology
Sample College
Expected 2026

Experience
Trainee
Sample Labs
2025-Present

Skills
Customer Service
"""
    parsed, _source = extract_resume_info(text)
    assert "Associate" in parsed["degree"] or any("Associate" in row.get("degree", "") for row in parsed.get("further_studies", []))
    records = extract_heuristic(DocumentView.from_text(text))["education_records"]
    associate = next(row for row in records if "Associate" in row["degree"])
    assert associate["year_graduated"] == "2026"
    assert associate["is_graduated"] == "No"


def test_lone_year_is_not_graduation_year(no_model):
    parsed, _source = extract_resume_info(CASES[6]["text"])
    assert parsed["year_graduated"] == ""


def test_job_fields_across_lines(no_model):
    text = """\
Ana Dela Cruz
ana@example.com
Philippines

Education
Bachelor of Science in Information Technology
Sample University
2018-2022

Experience
Senior Software Engineer

ABC Corporation

2022-Present

Skills
Python
"""
    parsed, _source = extract_resume_info(text)
    job = next(row for row in parsed["experiences"] if "Software Engineer" in row["job_title"])
    assert "ABC Corporation" in job["employer"]
    assert job["is_current"] == "Yes"


def test_two_column_skills_are_not_jobs(no_model):
    rows = [
        ("Ana Dela Cruz", 40, 10),
        ("ana@example.com", 40, 24),
        ("Philippines", 40, 38),
        ("Education", 40, 60),
        ("Bachelor of Science in Information Technology", 40, 78),
        ("Sample University", 40, 96),
        ("2018-2022", 40, 114),
        ("Experience", 40, 140),
        ("Software Engineer", 40, 158),
        ("ABC Corporation", 40, 176),
        ("2022-Present", 40, 194),
        ("Skills", 340, 60),
        ("Python", 340, 78),
        ("SQL", 340, 96),
        ("JavaScript", 340, 114),
    ]
    blocks = [TextBlock(text=text, x0=x, y0=y, x1=x + 160, y1=y + 12, font_size=12) for text, x, y in rows]
    view = DocumentView(
        text="\n".join(block.text for block in blocks),
        blocks=blocks,
        source="digital_pdf",
        columns=2,
    )
    parsed, _source = extract_resume_info(view.text, document=view)
    titles = [job["job_title"] for job in parsed["experiences"]]
    assert any("Software Engineer" in title for title in titles)
    assert "Python" not in titles
    assert "SQL" not in titles
    assert "Python" in parsed["skills"]


def test_employment_heading_with_internships(no_model):
    parsed, _source = extract_resume_info(CASES[8]["text"])
    gts = map_to_gts_fields(parsed)
    assert gts["first_occ"] == "Software Engineer"
    assert gts["pres_occ"] == "Software Engineer"
    assert any("IT Intern" in job["job_title"] for job in gts["experiences"])


def test_model_can_correct_a_shorter_title():
    resume = "Senior Software Engineer\nABC Corporation\n2022-Present\n"
    heuristic = {
        "first_name": "Ana",
        "last_name": "Cruz",
        "degree": "Bachelor of Science in Information Technology",
        "year_graduated": "2022",
        "experiences": [{
            "job_title": "Software Engineer",
            "employer": "ABC Corporation",
            "start_date": "2022",
            "is_current": "Yes",
        }],
        "skills": [],
        "further_studies": [],
    }
    model = {
        "experiences": [{
            "job_title": "Senior Software Engineer",
            "employer": "ABC Corporation",
            "start_date": "2022",
            "is_current": "Yes",
        }]
    }
    merged, _confidence = reconcile_extractions(model, heuristic, resume)
    titles = [job["job_title"] for job in merged["experiences"]]
    assert titles == ["Senior Software Engineer"]


def test_multiword_skills_and_job_words_stay_separate(no_model):
    text = """\
Ana Dela Cruz
ana@example.com

Education
Bachelor of Science in Information Technology
Sample University
2018-2022

Experience
Software Engineer
Sample Labs
2022-Present
Used python to support hospital staff.

Skills
Project Management, Microsoft Excel, Data Analysis, Customer Service, Social Media Management
"""
    parsed, _source = extract_resume_info(text)
    skills = parsed["skills"]
    assert "Project Management" in skills
    assert "Social Media Management" in skills
    assert "python" not in [skill.lower() for skill in skills]
    assert "hospital" not in [skill.lower() for skill in skills]


def test_two_column_llamaparse_text_keeps_name_degree_and_jobs():
    from app.services.parser_llm import linearize_llamaparse_text

    aligned = """\
Sean Gabriel Santos               Taguig City, Metro Manila, Philippines
SENIOR DIGITAL MARKETING SPECIALIST

WORK EXPERIENCE                                                      SKILLS & TOOLS
Senior Digital Marketing Lead                                      2023 - Present     Meta Ads Manager
Apex Media Group Philippines                                                          Google Ads & GA4
Spearheaded paid performance campaigns managing monthly ad spend.
Growth Marketing Strategist                                           2021 - 2023     Copywriting
Nexus Digital Labs
SEO & Content Specialist                                              2019 - 2021     EDUCATION
Vanguard Creative Agency                                                              BS Business Administration
                                                                                      Major in Marketing
                                                                                      De La Salle University (2015-2019)
KEY CAMPAIGN PROJECTS
E-Commerce Mega Sale Launch (2024)
Achieved ₱18M in gross sales over a 3-day activation.
"""
    parsed, _source = extract_resume_info(linearize_llamaparse_text(aligned))
    assert parsed["first_name"] == "Sean Gabriel"
    assert parsed["last_name"] == "Santos"
    assert "Business Administration" in parsed["degree"]
    assert "Marketing" in parsed["degree"]
    assert parsed["year_graduated"] == "2019"
    titles = [job["job_title"] for job in parsed["experiences"]]
    assert "Senior Digital Marketing Lead" in titles
    assert not any(title.lower().startswith("spearheaded") for title in titles)
    assert any("Apex Media" in job["employer"] for job in parsed["experiences"])
    assert "Meta Certified Media Buyer" not in parsed["first_name"]
    assert all(not job["salary_range"] for job in parsed["experiences"])
    assert "Meta Ads Manager" in parsed["skills"]


def test_campaign_revenue_is_not_salary():
    parsed = extract_salary("Achieved ₱18M in gross sales over a 3-day activation.")
    assert parsed["current"] == ""
    assert parsed["state"] == "absent"


def test_salary_kinds():
    monthly = extract_salary("Salary: PHP 25,000/month")
    assert monthly["current"] == "₱13,800 to ₱27,599"
    assert monthly["expected"] == ""
    annual = extract_salary("Annual Salary: ₱600,000")
    assert annual["current"] == "₱41,400 to ₱55,199"
    expected = extract_salary("Expected Salary: 40,000")
    assert expected["current"] == ""
    assert expected["expected"] == "₱27,600 to ₱41,399"
    ranged = extract_salary("Salary: 25,000 - 35,000")
    assert ranged["current"] == ""
    assert ranged["state"] == "uncertain"
    assert extract_salary("Software Engineer at Sample Labs")["state"] == "absent"


def test_expected_salary_is_not_stored_as_current(no_model):
    parsed, _source = extract_resume_info(CASES[5]["text"])
    assert all(not job.get("salary_range") for job in parsed["experiences"])


def test_a_titled_job_without_an_employer_stays_partial(no_model):
    text = """\
Nora Santos
nora.santos@example.com

Experience
Staff Nurse
Monitored patients and prepared shift reports.

Education
Bachelor of Science in Nursing
Sample University
2016-2020
"""
    parsed, _source = extract_resume_info(text)
    assert parsed["experiences"]
    job = parsed["experiences"][0]
    assert job["job_title"] == "Staff Nurse"
    assert job["employer"] == ""
    assert job["is_current"] == ""
    assert parsed["is_currently_employed"] == ""
    notes = [row for row in parsed["extraction_meta"]["field_evidence"] if row["field"] == "employment"]
    assert notes and notes[0]["status"] == "partial"


def test_a_headline_outside_experience_is_not_a_job(no_model):
    text = """\
Nora Santos
nora.santos@example.com
Staff Nurse

Education
Bachelor of Science in Nursing
Sample University
2016-2020
"""
    parsed, _source = extract_resume_info(text)
    assert parsed["experiences"] == []
    assert "Nursing" in parsed["degree"]


def test_dates_and_degrees_without_section_headings(no_model):
    text = """\
Carlo Ramos
carlo.ramos@example.com

Bachelor of Science in Accountancy
Sample University
2014-2018
Accountant
Sample Ledger Office
2019-Present
"""
    parsed, _source = extract_resume_info(text)
    assert "Accountancy" in parsed["degree"]
    assert parsed["year_graduated"] == "2018"
    assert parsed["experiences"][0]["job_title"] == "Accountant"
    assert "Ledger" in parsed["experiences"][0]["employer"]
    assert parsed["experiences"][0]["is_current"] == "Yes"
    assert parsed["is_currently_employed"] == "Yes"


def test_credential_name_is_not_replaced_by_a_job_title(no_model):
    text = """\
Dr. Marcus Vance, Ph.D.
m.vance@bioresearch.org

Experience
Principal Clinical Investigator
St. Luke's Medical Center | 2022 - Present
Oversee clinical trials for autoimmune disorders.

Education
B.S. in Biochemistry
Sample University
2011-2015

Skills
Flow Cytometry
"""
    parsed, _source = extract_resume_info(text)
    assert parsed["first_name"] == "Marcus"
    assert parsed["last_name"] == "Vance"
    assert "principal" not in parsed["first_name"].lower()
    assert "investigator" not in parsed["last_name"].lower()
    assert "disorders" not in parsed["last_name"].lower()
    assert any("Principal Clinical Investigator" in job["job_title"] for job in parsed["experiences"])


def test_name_suffix_and_curriculum_vitae(no_model):
    parsed, _source = extract_resume_info(CASES[7]["text"])
    assert parsed["first_name"] == "Sean Gabriel"
    assert parsed["middle_name"] == ""
    assert parsed["last_name"] == "Santos Jr."

    vitae = """\
CURRICULUM VITAE
PROFESSIONAL PROFILE

Maria Clara Santos
maria.santos@example.com
Philippines

Education
Bachelor of Science in Information Technology
Sample University
2018-2022

Experience
Software Engineer
Sample Labs
2022-Present

Skills
Python
"""
    parsed, _source = extract_resume_info(vitae)
    assert parsed["first_name"] == "Maria Clara"
    assert parsed["last_name"] == "Santos"
    assert "curriculum" not in parsed["first_name"].lower()


def test_country_requires_a_real_name():
    assert extract_country("Mobile 0917 ph") == ""
    assert extract_country("Angeles City, Pampanga, Philippines") == "Philippines"
    assert extract_country("Manila address, Philippines") == "Philippines"


def test_country_stays_blank_without_evidence(no_model):
    parsed, _source = extract_resume_info(CASES[9]["text"])
    assert parsed["country"] == ""


def test_assessment_labels():
    assessment = assess_extraction({
        "first_name": "Ana",
        "last_name": "Cruz",
        "degree": "BS Information Technology",
        "year_graduated": "",
        "education_year_confidence": "low",
        "experiences": [{"job_title": "Engineer", "employer": "Labs"}],
        "skills": [],
        "skills_section_seen": False,
        "further_studies": [],
        "further_studies_evidence": {"status": "not_detected"},
        "salary_state": "absent",
    })
    assert assessment["education"] == "uncertain"
    assert assessment["skills"] == "absent"
    assert needs_deeper_extraction(assessment) is True


def _norm(value):
    return " ".join(str(value or "").lower().split())


def _case_scores(parsed, expected):
    checks = []
    gts = map_to_gts_fields(parsed)

    def add(predicted, wanted, comparable=True):
        if not comparable:
            return
        checks.append((_norm(predicted) == _norm(wanted), bool(_norm(predicted)), bool(_norm(wanted))))

    if "first_name" in expected:
        add(parsed.get("first_name"), expected["first_name"])
    if "middle_name" in expected:
        add(parsed.get("middle_name"), expected["middle_name"])
    if "last_name" in expected:
        add(parsed.get("last_name"), expected["last_name"])
    if "year_graduated" in expected:
        add(parsed.get("year_graduated"), expected["year_graduated"])
    if "country" in expected:
        add(parsed.get("country"), expected["country"])
    if "degree_contains" in expected:
        degree = parsed.get("degree") or ""
        checks.append((expected["degree_contains"].lower() in degree.lower(), bool(degree), True))
    if "current_title" in expected:
        add(gts.get("pres_occ"), expected["current_title"])
    if "current_employer" in expected:
        add(gts.get("pres_emp"), expected["current_employer"])
    if "first_title" in expected:
        add(gts.get("first_occ"), expected["first_title"])
    if "further_studies" in expected:
        add(gts.get("enroll_further_studies"), expected["further_studies"])
    if "further_program_contains" in expected:
        blob = " ".join(row.get("course_degree", "") for row in gts.get("further_studies") or [])
        checks.append((expected["further_program_contains"].lower() in blob.lower(), bool(blob), True))
    if "is_currently_employed" in expected:
        add(parsed.get("is_currently_employed"), expected["is_currently_employed"])
    if "salary" in expected:
        salaries = [job.get("salary_range", "") for job in parsed.get("experiences") or []]
        found = next((item for item in salaries if item), "")
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


def test_reading_order_keeps_a_date_with_its_job(no_model):
    """A date beside a job must stay with that job, not move into a later column."""
    rows = [
        ("Ana Dela Cruz", 40, 10),
        ("ana@example.com", 40, 24),
        ("Education", 40, 50),
        ("Bachelor of Science in Information Technology", 40, 68),
        ("Sample University", 40, 86),
        ("2018-2022", 40, 104),
        ("Experience", 40, 130),
        ("Software Engineer", 40, 148),
        ("North Labs", 40, 166),
        ("2022-Present", 320, 166),
        ("Skills", 340, 50),
        ("Python", 340, 68),
        ("SQL", 340, 86),
    ]
    blocks = [TextBlock(text=text, x0=x, y0=y, x1=x + 140, y1=y + 12, font_size=12) for text, x, y in rows]
    view = DocumentView(text="\n".join(block.text for block in blocks), blocks=blocks, source="digital_pdf", columns=2)
    parsed, _source = extract_resume_info(view.text, document=view)
    job = next(row for row in parsed["experiences"] if "Software Engineer" in row["job_title"])
    assert job["employer"] == "North Labs"
    assert job["is_current"] == "Yes"
    assert "Python" not in [row["job_title"] for row in parsed["experiences"]]
    assert "Python" in parsed["skills"]


def test_earliest_bachelors_degree_stays_primary(no_model):
    text = """\
Liza Santos
lsantos@example.com

Education
Bachelor of Science in Information Technology
Sample University
2014-2018
Bachelor of Science in Education
Sample College
2019-2023

Experience
Teacher
Sample School
2023-Present

Skills
Classroom Management
"""
    parsed, _source = extract_resume_info(text)
    assert "Information Technology" in parsed["degree"]
    assert parsed["year_graduated"] == "2018"
    programs = " ".join(row["course_degree"] for row in parsed["further_studies"])
    assert "Education" in programs
    assert "Information Technology" not in programs


def test_heading_variants_and_multiline_credentials(no_model):
    text = """\
Paolo Reyes
preyes@example.com
Philippines

Job History
IT Support Specialist
Sample Office
2022-Present

Licenses & Certifications
AWS Cloud Practitioner
Amazon Web Services
2023

Seminars, Trainings, and Workshops
Career Fair
Angeles City
AUF Alumni Office
2022

Honors & Awards
Dean Lister
Sample University
2021
Recognized for academic rank

Skills
Python, SQL, and Project Management
"""
    parsed, _source = extract_resume_info(text)
    assert parsed["experiences"][0]["job_title"] == "IT Support Specialist"
    cert = parsed["certifications"][0]
    assert cert["name"] == "AWS Cloud Practitioner"
    assert cert["awarding_body"] == "Amazon Web Services"
    assert cert["year"] == "2023"
    seminar = parsed["seminars"][0]
    assert seminar["name"] == "Career Fair"
    assert seminar["location"] == "Angeles City"
    assert seminar["organizer"] == "AUF Alumni Office"
    assert seminar["year"] == "2022"
    award = parsed["awards"][0]
    assert award["name"] == "Dean Lister"
    assert award["issuer"] == "Sample University"
    assert award["year"] == "2021"
    assert "academic rank" in award["description"]
    assert parsed["skills"] == ["Python", "SQL", "Project Management"]
    assert "Amazon Web Services" not in [row["name"] for row in parsed["certifications"]]


def test_table_text_inside_a_table_box_is_not_duplicated():
    from app.services.parser_document import TextBlock, _block_inside

    inside = TextBlock(text="Software Engineer", x0=10, y0=10, x1=80, y1=24)
    outside = TextBlock(text="Education", x0=10, y0=80, x1=80, y1=94)
    boxes = [(0.0, 0.0, 200.0, 40.0)]
    assert _block_inside(inside, boxes) is True
    assert _block_inside(outside, boxes) is False


def test_evaluation_dataset(no_model):
    rows = []
    failures = []
    for case in CASES:
        parsed, _source = extract_resume_info(case["text"])
        scored = _case_scores(parsed, case["expected"])
        rows.extend(scored)
        missed = [item for item in scored if not item[0]]
        if missed:
            failures.append(case["id"])
    metrics = _metrics(rows)
    assert len(CASES) >= 12
    assert not failures, metrics
    assert metrics["precision"] >= 0.9
    assert metrics["recall"] >= 0.9
    assert metrics["f1"] >= 0.9
