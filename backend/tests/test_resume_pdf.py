import fitz

from app.models import Account, Resume
from app.services.resume_pdf import MARGIN_X, PAGE_W, build_resume_pdf, merge_resume_content, resume_preview
from tests.conftest import auth_header, login


def _text(pdf: bytes) -> str:
    document = fitz.open(stream=pdf, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in document)
    finally:
        document.close()


def test_sparse_profile_omits_empty_sections():
    pdf = build_resume_pdf({
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "",
        "address": "",
        "city": "",
        "country": "",
        "bio": "",
        "degree": "",
        "college": "",
        "year_graduated": "",
        "studies": [],
        "jobs": [],
        "skills": [],
        "certifications": [],
        "seminars": [],
        "awards": [],
    })
    text = _text(pdf)
    assert "Ada Lovelace" in text
    assert "ada@example.com" in text
    assert "EDUCATION" not in text
    assert "EXPERIENCE" not in text
    assert "Primary guardian" not in text
    assert pdf.startswith(b"%PDF")


def test_resume_includes_saved_profile_sections():
    pdf = build_resume_pdf({
        "name": "Maria Cruz Reyes",
        "email": "maria.reyes@gmail.com",
        "phone": "+63 917 555 0101",
        "address": "Sto. Rosario Street",
        "city": "Angeles City",
        "country": "Philippines",
        "bio": "I am Maria",
        "degree": "Bachelor of Science in Information Technology",
        "college": "College of Computer Studies",
        "year_graduated": "2022",
        "studies": [{
            "course_degree": "Master of Information Technology",
            "school": "Angeles University Foundation",
            "institution_address": "Angeles City",
            "year_enrolled": "2025",
            "scholarship": "AUF Graduate Scholarship",
            "is_graduated": False,
        }],
        "jobs": [{
            "job_title": "Software Engineer",
            "company": "North Luzon Systems Corp.",
            "start_date": "2024-03-01",
            "is_current": True,
            "location": "Angeles City",
            "duration": "2 years",
            "description": "Builds alumni systems.",
        }],
        "skills": ["Python", "SQL"],
        "certifications": [{"name": "AWS Cloud Practitioner", "awarding_body": "Amazon", "awarded_on": "2024-06-01"}],
        "seminars": [],
        "awards": [],
    })
    text = _text(pdf)
    assert "Maria Cruz Reyes" in text
    assert "I am Maria" in text
    assert "Software Engineer" in text
    assert "North Luzon Systems Corp." in text
    assert "Python, SQL" in text
    assert "AWS Cloud Practitioner" in text
    assert "Master of Information Technology" in text
    assert "AUF Graduate Scholarship" in text
    assert "Angeles City" in text
    assert "Primary guardian" not in text
    assert "Employment Status" not in text


def test_alumni_can_download_profile_resume(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.get("/api/alumni/resume/export", headers=auth_header(data["access_token"]))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    text = _text(response.content)
    assert "Maria" in text
    assert "Reyes" in text
    assert "Primary guardian" not in text
    assert "Both Parents" not in text


def test_pending_alumni_cannot_export_resume(client):
    data = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    response = client.get("/api/alumni/resume/export", headers=headers)
    assert response.status_code == 403
    assert client.get("/api/alumni/resume/preview", headers=headers).status_code == 403
    assert client.get("/api/alumni/resume/document", headers=headers).status_code == 403


def test_saved_resume_document_is_exported(client, db_session):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    loaded = client.get("/api/alumni/resume/document", headers=headers)
    assert loaded.status_code == 200, loaded.text
    body = loaded.json()
    assert body["saved"] is False
    assert "Maria" in body["document"]["name"]
    assert "Both Parents" not in str(body)
    assert "Primary guardian" not in str(body)
    document = {
        "name": "Maria Cruz Reyes",
        "phone": "+63 917 555 0101",
        "email": "maria.reyes@gmail.com",
        "address": "Sto. Rosario Street, Angeles City, Philippines",
        "sections": [
            {"type": "summary", "text": "Final edited summary for the PDF."},
            {"type": "experience", "entries": [{
                "title": "Edited Role",
                "company": "Edited Company",
                "dates": "2020 - 2021",
                "location": "Manila",
                "description": "Rewrote the resume by hand.",
            }]},
        ],
    }
    try:
        saved = client.put("/api/alumni/resume/document", headers=headers, json=document)
        assert saved.status_code == 200, saved.text
        pdf = client.get("/api/alumni/resume/export", headers=headers)
        assert pdf.status_code == 200, pdf.text
        text = _text(pdf.content)
        assert "Final edited summary for the PDF." in text
        assert "Edited Role" in text
        assert "Edited Company" in text
        assert "Rewrote the resume by hand." in text
        assert "WORK EXPERIENCE" in text
        assert "Software Engineer" not in text
        assert "Primary guardian" not in text
    finally:
        user = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
        user.profile.resume_document = None
        db_session.commit()


def test_saved_profile_wins_over_conflicting_upload():
    profile = {
        "name": "Maria Cruz Reyes",
        "email": "maria.reyes@gmail.com",
        "phone": "+63 917 555 0101",
        "bio": "I am Maria",
        "degree": "Bachelor of Science in Information Technology",
        "college": "College of Computer Studies",
        "year_graduated": "2022",
        "studies": [{"course_degree": "Master of Information Technology", "school": "Angeles University Foundation", "year_enrolled": "2025", "is_graduated": False}],
        "jobs": [{
            "job_title": "Software Engineer",
            "company": "North Luzon Systems Corp.",
            "start_date": "2024-03-01",
            "is_current": True,
            "description": "Builds alumni systems.",
            "salary_range": "PHP 90000",
        }],
        "skills": ["Python"],
        "certifications": [{
            "name": "AWS Cloud Practitioner",
            "awarding_body": "Amazon",
            "awarded_on": "2024-06-01",
            "skills": ["SQL"],
        }],
        "guardian_type": "Both Parents",
        "student_id": "2020-0001",
    }
    uploads = [
        {
            "parser_source": "failed",
            "parsed": {"skills": ["ShouldNotAppear"], "experiences": [{"job_title": "Hidden Role", "employer": "Hidden Co"}]},
            "text": "Certifications\nHidden Certificate\nProjects\nHidden project\n",
        },
        {
            "parser_source": "heuristic",
            "parsed": {
                "degree": "Bachelor of Arts in History",
                "year_graduated": "1999",
                "summary": "This extracted summary must not replace the saved biography of Maria.",
                "experiences": [
                    {
                        "job_title": "Software Engineer",
                        "employer": "North Luzon Systems",
                        "description": "This extracted description must not replace the saved one.",
                        "is_current": "Yes",
                        "salary_range": "PHP 90000",
                        "employment_status": "Regular",
                        "supervisor_name": "Secret Supervisor",
                    },
                    {
                        "job_title": "Data Analyst",
                        "employer": "Example Labs",
                        "start_date": "2021-01-15",
                        "end_date": "2022-06-01",
                        "is_current": "No",
                        "description": "Analyzed enrollment records.",
                    },
                ],
                "skills": ["Python", "Kubernetes"],
                "further_studies": [{
                    "course_degree": "Master of Information Technology",
                    "school": "Angeles University Foundation",
                    "year_enrolled": "2020",
                    "is_graduated": "Yes",
                }, {
                    "course_degree": "Master of Data Science",
                    "school": "Example University",
                    "year_enrolled": "2023",
                    "is_graduated": "No",
                }],
                "is_currently_employed": "Yes",
                "first_name": "Not",
                "last_name": "Maria",
            },
            "text": (
                "Certifications\n"
                "AWS Cloud Practitioner, Amazon\n"
                "Kubernetes Administrator\n"
                "Projects\n"
                "Campus career portal\n"
            ),
        },
    ]
    merged = merge_resume_content(profile, uploads)
    pdf = build_resume_pdf(merged)
    text = _text(pdf)
    assert "I am Maria" in text
    assert "extracted summary must not replace" not in text
    assert "Builds alumni systems." in text
    assert "extracted description must not replace" not in text
    assert "Bachelor of Science in Information Technology" in text
    assert "Bachelor of Arts" not in text
    assert "1999" not in text
    assert "2022" in text
    assert "Data Analyst" in text
    assert "Example Labs" in text
    assert "Analyzed enrollment records." in text
    assert "Master of Data Science" in text
    assert text.count("Master of Information Technology") == 1
    assert "Kubernetes" in text
    assert "SQL" in text
    assert "Kubernetes Administrator" in text
    assert "Campus career portal" in text
    assert "ShouldNotAppear" not in text
    assert "Hidden Role" not in text
    assert "Hidden Certificate" not in text
    assert "Secret Supervisor" not in text
    assert "PHP 90000" not in text
    assert "Both Parents" not in text
    assert "2020-0001" not in text
    assert "Primary guardian" not in text
    preview = resume_preview(merged)
    labels = [section["label"] for section in preview["sections"]]
    assert "Projects" in labels
    assert "Primary guardian" not in labels
    assert "Employment Status" not in labels


def test_garbled_resume_parse_does_not_replace_saved_profile():
    merged = merge_resume_content(
        {
            "name": "Maria Cruz Reyes",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2022",
            "jobs": [{
                "job_title": "Software Engineer",
                "company": "North Luzon Systems Corp.",
                "is_current": True,
                "description": "",
            }],
            "skills": ["Python"],
            "studies": [],
            "certifications": [],
        },
        [{
            "parser_source": "heuristic",
            "parsed": {
                "degree": "Profile Data Analyst with years of experience. Experience Data Analyst Harborpoint Logistics.",
                "year_graduated": "present",
                "experiences": [
                    {
                        "job_title": "Microsoft Power BI Data Analyst LANGUAGES English",
                        "employer": "Professional",
                        "is_current": "Yes",
                    },
                    {
                        "job_title": "PROFILE Data Analyst with 3+ years of experience transforming operational data. EXPERIENCE Data Analyst",
                        "employer": "Filipino",
                        "is_current": "Yes",
                        "description": "Education BS Information Technology. Experience Reporting Specialist.",
                    },
                ],
                "skills": [
                    "PostgreSQL",
                    "Python",
                    "A long sentence that describes years of reporting experience rather than naming one skill",
                ],
            },
            "text": "Certifications\nProfile Data Analyst with years of experience and education details that should not become a certification name\n",
        }],
    )
    assert [job["job_title"] for job in merged["jobs"]] == ["Software Engineer"]
    assert merged["jobs"][0]["description"] == ""
    assert merged["degree"] == "Bachelor of Science in Information Technology"
    assert merged["year_graduated"] == "2022"
    assert merged["skills"] == ["Python", "PostgreSQL"]
    assert merged["certifications"] == []
    text = _text(build_resume_pdf(merged))
    assert "LANGUAGES" not in text
    assert "Harborpoint" not in text
    assert "PostgreSQL" in text


def test_inline_upload_adds_readable_sections_without_replacing_profile():
    text = "\n".join([
        "MAYA SANTOS DATA ANALYST CONTACT Cebu City, Philippines",
        "+63 918 555 0268",
        "maya.santos@example.com",
        "linkedin.com/in/mayasantos CORE SKILLS SQL & PostgreSQL",
        "Python & Pandas",
        "Power BI",
        "Data Cleaning",
        "Dashboard Design CERTIFICATIONS Google Data Analytics",
        "Microsoft Power BI Data Analyst LANGUAGES English - Professional",
        "Filipino - Native PROFILE Data Analyst with 3+ years of experience transforming operational data into dashboards, reports, and actionable insights for business teams.",
        "EXPERIENCE Data Analyst | HarborPoint Logistics, Cebu City | 2024-Present Created Power BI dashboards tracking delivery performance and service-level metrics. Reporting Specialist | Axis Retail Group, Cebu City | 2022-2024 Maintained sales and inventory reports for regional operations teams.",
        "EDUCATION BS Information Technology | University of San Carlos | 2022 SELECTED PROJECTS Sales Performance Dashboard - Built a Power BI dashboard combining monthly sales, product, and branch data. Delivery KPI Automation - Developed a Python workflow for cleaning CSV files and generating standardized reports.",
        "TOOLS Power BI, Excel, Git, Tableau",
    ])
    merged = merge_resume_content(
        {
            "name": "Maria Cruz Reyes",
            "email": "maria.reyes@gmail.com",
            "phone": "+63 917 555 0101",
            "bio": "I am Maria",
            "degree": "Bachelor of Science in Information Technology",
            "college": "College of Computer Studies",
            "year_graduated": "2022",
            "jobs": [{
                "job_title": "Software Engineer",
                "company": "North Luzon Systems Corp.",
                "is_current": True,
                "description": "Builds alumni systems.",
            }],
            "skills": ["Python", "SQL"],
        },
        [{"parser_source": "heuristic", "parsed": {"experiences": [], "skills": []}, "text": text}],
    )
    pdf = build_resume_pdf(merged)
    body = _text(pdf)
    assert "I am Maria" in body
    assert "Builds alumni systems." in body
    assert "Data Analyst" in body
    assert "HarborPoint Logistics" in body
    assert "Reporting Specialist" in body
    assert "Axis Retail Group" in body
    assert "Created Power BI dashboards" in body
    assert "Google Data Analytics" in body
    assert "Microsoft Power BI Data Analyst" in body
    assert "Sales Performance Dashboard" in body
    assert "Delivery KPI Automation" in body
    assert "Data Cleaning" in body
    assert "Tableau" in body
    assert "English - Professional" in body
    assert "Filipino - Native" in body
    assert "University of San Carlos" not in body
    assert "maya.santos@example.com" not in body
    assert "+63 918 555 0268" not in body
    assert "College of Computer Studies" in body
    analyst = next(job for job in merged["jobs"] if job["job_title"] == "Data Analyst")
    specialist = next(job for job in merged["jobs"] if job["job_title"] == "Reporting Specialist")
    assert analyst["start_date"] == "2024"
    assert analyst["is_current"] is True
    assert "Created Power BI" in analyst["description"]
    assert "Maintained sales" not in analyst["description"]
    assert specialist["start_date"] == "2022"
    assert str(specialist["end_date"]).startswith("2024")
    assert specialist["is_current"] is False


def test_upload_fills_blank_profile_without_inventing_contact():
    merged = merge_resume_content(
        {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "",
            "bio": "",
            "degree": "",
            "year_graduated": "",
            "jobs": [],
            "skills": [],
            "studies": [],
            "certifications": [],
        },
        [{
            "parser_source": "heuristic",
            "parsed": {
                "degree": "Bachelor of Science in Mathematics",
                "year_graduated": "2021",
                "summary": "Mathematician who writes careful analytical notes for published work.",
                "phone": "+63 900 000 0000",
                "experiences": [],
                "skills": [],
            },
            "text": "",
        }],
    )
    assert merged["degree"] == "Bachelor of Science in Mathematics"
    assert merged["year_graduated"] == "2021"
    assert merged["bio"].startswith("Mathematician")
    assert merged["phone"] == ""
    assert merged["email"] == "ada@example.com"
    text = _text(build_resume_pdf(merged))
    assert "Bachelor of Science in Mathematics" in text
    assert "+63 900 000 0000" not in text
    assert "EDUCATION" in text


def test_long_resume_paginates_without_clipping():
    jobs = [
        {
            "job_title": f"Role {index:02d}",
            "company": "Wide Margin Labs",
            "start_date": f"20{index:02d}-01-01",
            "is_current": index == 17,
            "description": ("Coordinated delivery across teams. " * 18) + ("W" * 80),
        }
        for index in range(18)
    ]
    pdf = build_resume_pdf({
        "name": "Long Example",
        "email": "long@example.com",
        "jobs": jobs,
        "bio": "A biography that stays with the saved profile.",
    })
    document = fitz.open(stream=pdf, filetype="pdf")
    try:
        assert document.page_count >= 2
        text = "\n".join(page.get_text() for page in document)
        for index in range(18):
            assert f"Role {index:02d}" in text
        for page in document:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines") or []:
                    for span in line.get("spans") or []:
                        x0, _y0, x1, _y1 = span["bbox"]
                        assert x0 >= MARGIN_X - 2
                        assert x1 <= PAGE_W - MARGIN_X + 2
    finally:
        document.close()


def test_export_includes_uploaded_resume_for_the_same_account(client, db_session):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    user = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    row = Resume(
        account_id=user.id,
        original_filename="extra-resume.txt",
        stored_path="uploads/resumes/test-extra.txt",
        mime_type="text/plain",
        extracted_text="Certifications\nKubernetes Administrator\nProjects\nCampus career portal\n",
        parsed_json={
            "degree": "Bachelor of Arts in History",
            "year_graduated": "1999",
            "experiences": [
                {
                    "job_title": "Software Engineer",
                    "employer": "North Luzon Systems Corp.",
                    "description": "Filled from the uploaded resume because the saved role had no description.",
                    "is_current": "Yes",
                    "salary_range": "PHP 90000",
                    "supervisor_name": "Secret Supervisor",
                },
                {
                    "job_title": "Data Analyst",
                    "employer": "Example Labs",
                    "start_date": "2021-01-15",
                    "end_date": "2022-06-01",
                    "is_current": "No",
                    "description": "Analyzed enrollment records.",
                },
            ],
            "skills": ["Kubernetes", "Python"],
            "further_studies": [{
                "course_degree": "Master of Data Science",
                "school": "Example University",
                "year_enrolled": "2023",
                "is_graduated": "No",
            }],
        },
        parser_source="heuristic",
    )
    ignored = Resume(
        account_id=user.id,
        original_filename="failed.txt",
        stored_path="uploads/resumes/test-failed.txt",
        mime_type="text/plain",
        extracted_text="Certifications\nShouldNotAppear Certificate\n",
        parsed_json={"skills": ["ShouldNotAppear"], "experiences": [{"job_title": "Hidden Role", "employer": "Hidden Co"}]},
        parser_source="failed",
    )
    db_session.add(row)
    db_session.add(ignored)
    db_session.commit()
    headers = auth_header(data["access_token"])
    try:
        preview = client.get("/api/alumni/resume/preview", headers=headers)
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert "Maria" in body["name"]
        experience = next(section for section in body["sections"] if section["label"] == "Experience")
        assert experience["ready"] is True
        assert "Data Analyst" in experience["detail"]
        response = client.get("/api/alumni/resume/export", headers=headers)
        assert response.status_code == 200, response.text
        text = _text(response.content)
        assert "Data Analyst" in text
        assert "Example Labs" in text
        assert "Kubernetes" in text
        assert "Master of Data Science" in text
        assert "Kubernetes Administrator" in text
        assert "Campus career portal" in text
        assert "Filled from the uploaded resume" in text
        assert "Bachelor of Science in Information Technology" in text
        assert "Bachelor of Arts" not in text
        assert "1999" not in text
        assert "ShouldNotAppear" not in text
        assert "Hidden Role" not in text
        assert "Secret Supervisor" not in text
        assert "PHP 90000" not in text
        assert "Primary guardian" not in text
        assert "Both Parents" not in text
        assert "AUF-2022" not in text
    finally:
        db_session.delete(row)
        db_session.delete(ignored)
        db_session.commit()
