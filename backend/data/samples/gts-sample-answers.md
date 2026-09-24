# Sample Graduate Tracer Survey answers

Use these values when the resume parser leaves a field blank. Match the **exact** dropdown wording.

Supplementary questions already seeded:

- Internship/OJT support: choose **4**
- Work arrangement: **On-site** (Sofia: **Hybrid**; Elena: **Not applicable**)

---

## Carlos Mendoza (happy path, present job = first job)

| Field | Answer |
|-------|--------|
| Given name / Middle / Last | Carlos / Villanueva / Mendoza |
| Country | Philippines |
| Year graduated | 2024 |
| Bachelor's degree | Bachelor of Science in Computer Science |
| Primary guardian/s | Both Parents |
| Guardian completed college | Yes |
| Ever employed after graduation | Yes |
| Time to first job | Less than a month |
| First job related to degree | Yes |
| How first job was found | Recommended by someone |
| Occupation (first) | Junior Software Developer |
| Employer (first) | Pampanga Digital Labs |
| Salary range | ₱27,600 to ₱41,399 |
| Employment status | Probationary |
| Currently employed | Yes |
| Present job is also first job | Yes |
| Skills | Python, JavaScript, SQL, Git, React |
| Further studies | No |
| Career seminars | Yes |
| Seminars helpful | Yes |
| Mentoring / advocacy / volunteering | 3 / 2 / 2 |
| Engagements | AUF career talks helped me prepare for technical interviews. |
| Develop more competencies | More cloud and software engineering electives |

Expected after submit: **Pending** account, alignment **Aligned** (PSOC 2512 Software Developers) once occupation is saved.

---

## Paolo Navarro (civil engineering)

| Field | Answer |
|-------|--------|
| Given / Middle / Last | Paolo / Diaz / Navarro |
| Year / Degree | 2024 / Bachelor of Science in Civil Engineering |
| Ever employed | Yes |
| Time to first job | 1 to 6 months |
| First related | Yes |
| How found | As walk-in applicant |
| First occupation / employer | Site Engineer / North Luzon Builders |
| Salary | ₱27,600 to ₱41,399 |
| Status | Probationary |
| Currently employed | Yes |
| Present job is first | Yes |
| Skills | AutoCAD, Project coordination, Quantity surveying |
| Further studies | No |

Expected alignment: **Aligned**, PSOC **2142** Civil Engineers.

---

## Sofia Lim (education)

| Field | Answer |
|-------|--------|
| Given / Middle / Last | Sofia / Ramos / Lim |
| Year / Degree | 2019 / Bachelor of Elementary Education |
| Ever employed | Yes |
| Time to first job | Less than a month |
| First related | Yes |
| How found | Arranged by AUF |
| First occupation / employer | Grade School Teacher / Holy Angel Demonstration School |
| Salary | ₱13,800 to ₱27,599 |
| Status | Regular/Permanent |
| Currently employed | Yes |
| Present job is first | Yes |
| Skills | Lesson planning, Classroom management |
| Further studies | Yes |
| Program | Master of Arts in Education — Angeles University Foundation — 2024 — No (not yet graduated) |

Expected alignment: **Aligned**, PSOC **2341** Primary School Teachers.

---

## Miguel Santos (marketing; present job is not first)

| Field | Answer |
|-------|--------|
| Given / Middle / Last | Miguel / Bautista / Santos |
| Year / Degree | 2022 / Bachelor of Science in Business Administration |
| Ever employed | Yes |
| Time to first job | 1 to 6 months |
| First related | Yes |
| How found | Response to an advertisement |
| First occupation / employer | Marketing Associate / Kapampangan Brands Inc. |
| First salary / status | ₱13,800 to ₱27,599 / Probationary |
| Currently employed | Yes |
| Present job is first | **No** |
| Present occupation / employer | Marketing Specialist / Kapampangan Brands Inc. |
| Immediate head / email | Lara Perez / lara.perez@kbi.example |
| Length of stay | 1 year(s) and 4 month(s) |
| Present related to degree | Yes |
| Skills | Digital marketing, Social media, Excel |

Expected alignment: **Aligned** to marketing (PSOC 2431 or 1221).

---

## Elena Ramos (never employed)

Add her to **Admin → Registry** first (`registry-sample.csv`).

| Field | Answer |
|-------|--------|
| Given / Middle / Last | Elena / Cruz / Ramos |
| Year / Degree | 2023 / Bachelor of Science in Nursing |
| Ever employed | **No** |
| Reason (past unemployment) | Board or Licensure Examination Preparation |
| Currently employed | **No** |
| Reason (current unemployment) | Board or Licensure Examination Preparation |
| Skills | Patient care, Vital signs, First aid |
| Further studies | No |

Do not fill first-job or present-job titles. Alignment may be Unknown; that is expected.

---

## Unmatched applicant

| Field | Answer |
|-------|--------|
| Email | tester.unmatched@example.com |
| Name | Rico Salazar Tan |
| Degree / year | Bachelor of Science in Information Technology / 2022 |
| Occupation | IT Support Specialist |
| Employer | Clark Helpdesk Services |
| Ever / currently employed | Yes / Yes |
| Present job is first | Yes |

Admin **Verify** should report no graduate record. Reject with: `QA reject — no matching AUF graduate record.`
