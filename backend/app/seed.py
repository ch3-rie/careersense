"""Idempotent seed for local/demo environments."""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.models import (
    AacAppointmentSlot,
    Account,
    AlignmentResult,
    AlumniCard,
    AlumniJob,
    AlumniNotification,
    AlumniPerk,
    AlumniPerkRedemption,
    AlumniProfile,
    AlumniSkill,
    FurtherStudy,
    GtsQuestion,
    SocCode,
    TracerSubmission,
    UniversityRecord,
)
from app.security import hash_password

PSOC_CSV = BACKEND_DIR / "data" / "psoc_seed.csv"
logger = logging.getLogger("careersense")

FALLBACK_SOC = [
    ("1330", "Information and Communications Technology Service Managers", "ICT",
     "it manager,information technology manager,mis manager,network manager,chief information officer",
     "information technology,computer science,information systems"),
    ("2512", "Software Developers", "ICT",
     "software developer,software engineer,web developer,full stack developer,backend developer,frontend developer,programmer,python developer",
     "information technology,computer science,information systems,computer engineering"),
    ("2511", "Systems Analysts", "ICT",
     "systems analyst,business systems analyst,it analyst,applications analyst",
     "information technology,computer science,information systems"),
    ("2522", "Systems Administrators", "ICT",
     "systems administrator,network administrator,it support specialist,help desk,technical support",
     "information technology,computer science,information systems"),
    ("3512", "Information and Communications Technology User Support Technicians", "ICT",
     "it support,computer technician,technical support specialist,helpdesk technician",
     "information technology,computer science"),
    ("2411", "Accountants", "Business and Administration",
     "accountant,auditor,bookkeeper,tax associate,accounting staff",
     "accountancy,accounting,business administration,finance"),
    ("1211", "Finance Managers", "Business and Administration",
     "finance manager,accounting manager,budgeting manager,comptroller",
     "accountancy,finance,business administration"),
    ("1221", "Sales and Marketing Managers", "Sales and Marketing",
     "sales manager,marketing manager,sales director,brand manager",
     "marketing,business administration,entrepreneurship"),
    ("2221", "Nursing Professionals", "Health",
     "staff nurse,registered nurse,clinical nurse,er nurse,icu nurse",
     "nursing,bachelor of science in nursing"),
    ("2341", "Primary School Teachers", "Education",
     "elementary teacher,primary school teacher,grade school teacher",
     "education,elementary education"),
    ("2330", "Secondary Education Teachers", "Education",
     "high school teacher,secondary teacher,subject teacher",
     "education,secondary education"),
    ("2142", "Civil Engineers", "Engineering",
     "civil engineer,structural engineer,site engineer",
     "civil engineering,engineering"),
    ("2152", "Electronics Engineers", "Engineering",
     "electronics engineer,ece,hardware engineer",
     "electronics engineering,computer engineering,engineering"),
    ("1412", "Restaurant Managers", "Hospitality",
     "restaurant manager,cafe manager,food and beverage manager",
     "hospitality management,hrm,business administration"),
    ("2431", "Advertising and Marketing Professionals", "Sales and Marketing",
     "marketing specialist,digital marketer,advertising associate",
     "marketing,mass communication,business administration"),
    ("2634", "Psychologists", "Social Sciences",
     "psychologist,guidance counselor,hr specialist,behavioral therapist",
     "psychology,guidance and counseling"),
    ("3212", "Medical and Pathology Laboratory Technicians", "Health",
     "medical technologist,lab technician,pathology technician",
     "medical technology,medical laboratory science"),
    ("2262", "Pharmacists", "Health",
     "pharmacist,clinical pharmacist,pharmacy staff",
     "pharmacy"),
    ("1120", "Managing Directors and Chief Executives", "Management",
     "chief executive officer,ceo,managing director,operations manager",
     "business administration,management,entrepreneurship"),
    ("4110", "General Office Clerks", "Clerical",
     "office clerk,administrative assistant,encoder,office staff",
     "office administration,business administration,information technology"),
]

UNIVERSITY_ROWS = [
    ("2020-0001", "Maria", "Cruz", "Reyes", "maria.reyes@gmail.com", "Bachelor of Science in Information Technology", "2022", "BSIT", "College of Computer Studies"),
    ("2020-0002", "Juan", "Santos", "Dela Cruz", "juan.delacruz@gmail.com", "Bachelor of Science in Information Technology", "2023", "BSIT", "College of Computer Studies"),
    ("2019-0144", "Ana", "Lopez", "Garcia", "ana.garcia@gmail.com", "Bachelor of Science in Nursing", "2021", "BSN", "College of Nursing"),
    ("2021-0088", "Carlos", "Villanueva", "Mendoza", "carlos.mendoza@gmail.com", "Bachelor of Science in Computer Science", "2024", "BSCS", "College of Computer Studies"),
    ("2018-0330", "Liza", "Pineda", "Torres", "liza.torres@gmail.com", "Bachelor of Science in Accountancy", "2020", "BSA", "College of Business and Accountancy"),
    ("2022-0112", "Paolo", "Diaz", "Navarro", "paolo.navarro@gmail.com", "Bachelor of Science in Civil Engineering", "2024", "BSCE", "College of Engineering"),
    ("2017-0201", "Sofia", "Ramos", "Lim", "sofia.lim@gmail.com", "Bachelor of Elementary Education", "2019", "BEED", "College of Education"),
    ("2020-0455", "Miguel", "Bautista", "Santos", "miguel.santos@gmail.com", "Bachelor of Science in Business Administration", "2022", "BSBA", "College of Business and Accountancy"),
]


def _upsert_soc_from_csv(db: Session) -> None:
    if not PSOC_CSV.exists():
        return
    with PSOC_CSV.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = (row.get("soc_code") or row.get("code") or "").strip()
            description = (row.get("description") or "").strip()
            if not code or not description:
                continue
            if db.get(SocCode, code) or db.query(SocCode).filter(SocCode.code == code).first():
                continue
            db.add(
                SocCode(
                    soc_code=code,
                    code=code,
                    description=description,
                    title_patterns=row.get("title_patterns") or "",
                    degree_patterns=row.get("degree_patterns") or "",
                    category=row.get("category") or "",
                    major_group=row.get("psoc_major_group") or "",
                )
            )


DEMO_JOB_TIMELINES = {
    "maria.reyes@gmail.com": [
        {
            "job_title": "Junior Software Developer",
            "company": "Pampanga Digital Labs",
            "start_date": date(2022, 7, 1),
            "end_date": date(2024, 2, 28),
            "is_current": False,
            "industry": "Information and communications technology",
            "location": "Angeles City",
        },
        {
            "job_title": "Software Engineer",
            "company": "North Luzon Systems Corp.",
            "start_date": date(2024, 3, 1),
            "end_date": None,
            "is_current": True,
            "industry": "Information and communications technology",
            "location": "Angeles City",
        },
    ],
    "liza.torres@gmail.com": [
        {
            "job_title": "Associate Auditor",
            "company": "Reyes & Co. CPAs",
            "start_date": date(2020, 8, 3),
            "end_date": date(2023, 4, 28),
            "is_current": False,
            "industry": "Finance and accounting",
            "location": "Angeles City",
        },
        {
            "job_title": "Restaurant Manager",
            "company": "Kapampangan Kitchen Group",
            "start_date": date(2023, 5, 2),
            "end_date": None,
            "is_current": True,
            "industry": "Hospitality and food service",
            "location": "Angeles City",
        },
    ],
}


def _ensure_demo_job_timelines(db: Session) -> None:
    for email, jobs in DEMO_JOB_TIMELINES.items():
        account = db.query(Account).filter(Account.personal_email == email).one_or_none()
        if not account:
            continue
        if account.profile is not None and account.profile.job_timeline_ready:
            continue
        if db.query(AlumniJob).filter(AlumniJob.account_id == account.id).count():
            continue
        for job in jobs:
            db.add(AlumniJob(account_id=account.id, **job))
        if account.profile is not None:
            account.profile.job_timeline_ready = True


DEMO_PERKS = [
    {
        "name": "AUF Library alumni access",
        "partner": "AUF University Library",
        "description": "Borrowing privileges with a valid Angelenean Alumni Card.",
        "discount": "Library access",
        "how_to_claim": "Present your AAC at the library circulation desk.",
        "category": "Campus",
        "eligibility": "Active Angelenean Alumni Card holders",
        "valid_from": date(2026, 1, 1),
        "valid_to": date(2026, 12, 31),
        "requires_active_card": True,
    },
    {
        "name": "Partner cafe discount",
        "partner": "Selected Angeles cafes",
        "description": "15% off food and drinks at AAPS partner cafes.",
        "discount": "15% off",
        "how_to_claim": "Show your AAC or claim code. One use per visit.",
        "category": "Dining",
        "eligibility": "AUF alumni",
        "valid_from": date(2026, 1, 1),
        "valid_to": date(2026, 12, 31),
        "requires_active_card": False,
    },
    {
        "name": "Homecoming early-bird rate",
        "partner": "AUF Alumni Homecoming",
        "description": "Reduced registration for the annual Angelenean homecoming.",
        "discount": "₱500 off",
        "how_to_claim": "Use the claim code when you register online.",
        "category": "Events",
        "eligibility": "AUF alumni",
        "valid_from": date(2026, 6, 1),
        "valid_to": date(2026, 9, 30),
        "requires_active_card": False,
    },
    {
        "name": "2025 Career Fair priority lane",
        "partner": "AAPS Career Fair",
        "description": "Priority check-in at last year’s placement fair. This offer has ended.",
        "discount": "Priority lane",
        "how_to_claim": "This benefit is no longer available.",
        "category": "Career",
        "eligibility": "AUF alumni",
        "valid_from": date(2025, 1, 1),
        "valid_to": date(2025, 12, 31),
        "requires_active_card": False,
    },
]


def _ensure_demo_perks(db: Session) -> None:
    by_name = {row.name: row for row in db.query(AlumniPerk).all()}
    for perk in DEMO_PERKS:
        row = by_name.get(perk["name"])
        if row is None:
            db.add(AlumniPerk(**perk))
            continue
        row.partner = perk.get("partner") or row.partner or ""
        row.description = perk["description"]
        row.discount = perk["discount"]
        row.how_to_claim = perk["how_to_claim"]
        if perk.get("category") and not row.category:
            row.category = perk["category"]
        if perk.get("eligibility") and not row.eligibility:
            row.eligibility = perk["eligibility"]
    db.flush()


def _ensure_aac_slots(db: Session) -> None:
    if db.query(AacAppointmentSlot).count():
        return
    today = date.today()
    times = ("09:00", "10:00", "13:00", "14:00")
    added = 0
    cursor = today + timedelta(days=1)
    while added < 8:
        if cursor.weekday() < 5:
            for slot_time in times:
                db.add(AacAppointmentSlot(slot_date=cursor, slot_time=slot_time, capacity=8, active=True))
            added += 1
        cursor += timedelta(days=1)


def _ensure_demo_cards_and_contact(db: Session) -> None:
    specs = {
        "maria.reyes@gmail.com": {
            "status": "Claimed",
            "card_number": "AUF-2022-0001",
            "phone": "+63 917 555 0101",
            "city": "Angeles City",
            "birth_date": date(2000, 5, 12),
        },
        "liza.torres@gmail.com": {
            "status": "NotYetApplied",
            "card_number": "",
            "phone": "+63 918 555 0144",
            "city": "Mabalacat",
            "birth_date": date(1998, 8, 20),
        },
    }
    now = datetime.now(timezone.utc)
    for email, spec in specs.items():
        account = db.query(Account).filter(Account.personal_email == email).one_or_none()
        if not account:
            continue
        if account.profile is not None:
            if not account.profile.phone:
                account.profile.phone = spec["phone"]
            if not account.profile.city:
                account.profile.city = spec["city"]
            if account.profile.birth_date is None:
                account.profile.birth_date = spec.get("birth_date")
        card = account.alumni_card
        if card is None:
            db.add(
                AlumniCard(
                    account_id=account.id,
                    status=spec["status"],
                    card_number=spec["card_number"],
                    issued_at=now if spec["status"] == "Claimed" else None,
                    expires_at=date(2028, 3, 31) if spec["status"] == "Claimed" else None,
                    pickup_location="AUF Main Campus, MacArthur Highway, Angeles City",
                )
            )
        elif spec["status"] == "Claimed" and card.status in {"Active", "Claimed", "ReadyForPickup"}:
            card.status = "Claimed"
            card.card_number = spec["card_number"] or card.card_number
            card.issued_at = card.issued_at or now
            card.expires_at = card.expires_at or date(2028, 3, 31)
        elif spec["status"] == "NotYetApplied" and card.status in {"ActionNeeded", "Pending", "pending"}:
            card.status = "NotYetApplied"


def _backfill_demo_job_details(db: Session) -> None:
    for email, jobs in DEMO_JOB_TIMELINES.items():
        account = db.query(Account).filter(Account.personal_email == email).one_or_none()
        if not account:
            continue
        by_title = {job["job_title"]: job for job in jobs}
        for row in db.query(AlumniJob).filter(AlumniJob.account_id == account.id).all():
            match = by_title.get(row.job_title)
            if not match:
                continue
            if not row.industry:
                row.industry = match.get("industry") or ""
            if not row.location:
                row.location = match.get("location") or ""


def _ensure_demo_perk_redemption(db: Session) -> None:
    maria = db.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one_or_none()
    perk = db.query(AlumniPerk).filter(AlumniPerk.name == "Homecoming early-bird rate").one_or_none()
    if not maria or not perk:
        return
    exists = (
        db.query(AlumniPerkRedemption)
        .filter(AlumniPerkRedemption.account_id == maria.id, AlumniPerkRedemption.perk_id == perk.id)
        .count()
    )
    if not exists:
        db.add(AlumniPerkRedemption(account_id=maria.id, perk_id=perk.id, code="AUF-HM-MARIA"))


def seed_if_empty(db: Session) -> None:
    settings = get_settings()
    seed_demo_people = not settings.is_production

    if seed_demo_people and db.query(UniversityRecord).count() == 0:
        for row in UNIVERSITY_ROWS:
            db.add(
                UniversityRecord(
                    student_id=row[0],
                    first_name=row[1],
                    middle_name=row[2],
                    last_name=row[3],
                    personal_email=row[4],
                    degree=row[5],
                    year_graduated=row[6],
                    course_code=row[7],
                    college=row[8],
                )
            )

    if db.query(SocCode).count() == 0:
        _upsert_soc_from_csv(db)
        db.flush()
        existing_codes = {row.soc_code for row in db.query(SocCode.soc_code).all()}
        existing_codes.update({row.code for row in db.query(SocCode.code).all() if row.code})
        for code, desc, category, titles, degrees in FALLBACK_SOC:
            if code in existing_codes:
                continue
            db.add(
                SocCode(
                    soc_code=code,
                    code=code,
                    description=desc,
                    title_patterns=titles,
                    degree_patterns=degrees,
                    category=category,
                )
            )
            existing_codes.add(code)
        db.flush()

    if seed_demo_people and db.query(Account).filter(Account.role == "Admin").count() == 0:
        db.add(
            Account(
                personal_email="admin@auf.edu.ph",
                password_hash=hash_password("Admin@AUF2026"),
                role="Admin",
                status="Active",
                is_verified=True,
                privacy_consent=True,
                first_name="CareerSense",
                last_name="Administrator",
            )
        )

    if seed_demo_people and db.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").count() == 0:
        maria = Account(
            personal_email="maria.reyes@gmail.com",
            password_hash=hash_password("Alumni@2026"),
            linked_student_id="2020-0001",
            role="Alumni",
            status="Active",
            is_verified=True,
            privacy_consent=True,
        )
        db.add(maria)
        db.flush()
        db.add(
            AlumniProfile(
                account_id=maria.id,
                first_name="Maria",
                middle_name="Cruz",
                last_name="Reyes",
                country_residence="Philippines",
                degree="Bachelor of Science in Information Technology",
                year_graduated="2022",
                guardian_type="Both Parents",
                guardian_degree_completed=True,
                birth_date=date(2000, 5, 12),
            )
        )
        payload = {
            "first_name": "Maria",
            "middle_name": "Cruz",
            "last_name": "Reyes",
            "country": "Philippines",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2022",
            "primary_guardian": "Both Parents",
            "guardian_degree_completed": "Yes",
            "ever_employed": "Yes",
            "time_to_first_job": "1 to 6 months",
            "first_related": "Yes",
            "find_job": "Recommended by someone",
            "first_occ": "Junior Software Developer",
            "first_emp": "Pampanga Digital Labs",
            "first_sal": "₱27,600 to ₱41,399",
            "first_stat": "Regular/Permanent",
            "is_currently_employed": "Yes",
            "present_job_is_first": "No",
            "pres_occ": "Software Engineer",
            "pres_emp": "North Luzon Systems Corp.",
            "pres_head": "Rico Alvarez",
            "pres_head_email": "rico.alvarez@nlsc.example",
            "pres_stay": "1 year(s) and 4 month(s)",
            "present_related_degree": "Yes",
            "enroll_further_studies": "No",
            "participated_seminars": "Yes",
            "seminars_helpful": "Yes",
            "mentoring_rating": 3,
            "advocacy_rating": 2,
            "volunteering_rating": 2,
            "engagement_desc": "AUF career seminars helped me prepare for technical interviews and alumni mentoring.",
            "curriculum_suggestions": {"develop_competencies": "More cloud and DevOps electives"},
            "skills": ["Python", "SQL", "React", "Git"],
            "current_occupation": "Software Engineer",
            "current_employer": "North Luzon Systems Corp.",
        }
        db.add(
            TracerSubmission(
                account_id=maria.id,
                student_id="2020-0001",
                data_json=payload,
                extra_answers={},
                alignment_status="Aligned",
                alignment_score=100,
                soc_code="2512",
            )
        )
        db.add(
            AlignmentResult(
                account_id=maria.id,
                overall_match_score=100,
                alignment_justification="Aligned",
                justification_detail="Software Engineer maps to PSOC 2512 (Software Developers), which matches BSIT.",
                suggested_career_paths=["software developer", "software engineer", "web developer"],
            )
        )
        for skill in ["Python", "SQL", "React", "Git"]:
            db.add(AlumniSkill(account_id=maria.id, skill_name=skill, category="Technical"))

    if seed_demo_people and db.query(Account).filter(Account.personal_email == "juan.delacruz@gmail.com").count() == 0:
        juan = Account(
            personal_email="juan.delacruz@gmail.com",
            password_hash=hash_password("Alumni@2026"),
            linked_student_id="2020-0002",
            role="Alumni",
            status="Pending",
            is_verified=True,
            privacy_consent=True,
        )
        db.add(juan)
        db.flush()
        db.add(
            AlumniProfile(
                account_id=juan.id,
                first_name="Juan",
                middle_name="Santos",
                last_name="Dela Cruz",
                country_residence="Philippines",
                degree="Bachelor of Science in Information Technology",
                year_graduated="2023",
                guardian_type="Father",
                guardian_degree_completed=False,
            )
        )
        payload = {
            "first_name": "Juan",
            "middle_name": "Santos",
            "last_name": "Dela Cruz",
            "country": "Philippines",
            "degree": "Bachelor of Science in Information Technology",
            "year_graduated": "2023",
            "ever_employed": "Yes",
            "time_to_first_job": "7 to 11 months",
            "first_related": "Yes",
            "find_job": "Public Employment Service Office / Job Fair",
            "first_occ": "IT Support Specialist",
            "first_emp": "Angeles Medical Center",
            "first_sal": "₱13,800 to ₱27,599",
            "first_stat": "Probationary",
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "pres_occ": "IT Support Specialist",
            "pres_emp": "Angeles Medical Center",
            "present_related_degree": "Yes",
            "enroll_further_studies": "No",
            "participated_seminars": "Yes",
            "skills": ["Troubleshooting", "Networking", "Windows Server"],
            "current_occupation": "IT Support Specialist",
            "current_employer": "Angeles Medical Center",
        }
        db.add(
            TracerSubmission(
                account_id=juan.id,
                student_id="2020-0002",
                data_json=payload,
                extra_answers={},
                alignment_status="Aligned",
                alignment_score=100,
                soc_code="2522",
            )
        )

    if seed_demo_people and db.query(Account).filter(Account.personal_email == "ana.garcia@gmail.com").count() == 0:
        ana = Account(
            personal_email="ana.garcia@gmail.com",
            password_hash=hash_password("Alumni@2026"),
            linked_student_id="2019-0144",
            role="Alumni",
            status="Rejected",
            is_verified=False,
            privacy_consent=True,
            rejection_reason="Submitted documents did not match the graduate record on file. Please contact OAAPS.",
        )
        db.add(ana)
        db.flush()
        db.add(
            AlumniProfile(
                account_id=ana.id,
                first_name="Ana",
                middle_name="Lopez",
                last_name="Garcia",
                degree="Bachelor of Science in Nursing",
                year_graduated="2021",
            )
        )

    if seed_demo_people and db.query(Account).filter(Account.personal_email == "liza.torres@gmail.com").count() == 0:
        liza = Account(
            personal_email="liza.torres@gmail.com",
            password_hash=hash_password("Alumni@2026"),
            linked_student_id="2018-0330",
            role="Alumni",
            status="Active",
            is_verified=True,
            privacy_consent=True,
        )
        db.add(liza)
        db.flush()
        db.add(
            AlumniProfile(
                account_id=liza.id,
                first_name="Liza",
                middle_name="Pineda",
                last_name="Torres",
                country_residence="Philippines",
                degree="Bachelor of Science in Accountancy",
                year_graduated="2020",
                guardian_type="Mother",
                guardian_degree_completed=True,
                birth_date=date(1998, 8, 20),
            )
        )
        payload = {
            "first_name": "Liza",
            "last_name": "Torres",
            "degree": "Bachelor of Science in Accountancy",
            "year_graduated": "2020",
            "ever_employed": "Yes",
            "time_to_first_job": "1 to 6 months",
            "first_related": "Yes",
            "first_occ": "Associate Auditor",
            "first_emp": "Reyes & Co. CPAs",
            "first_sal": "₱27,600 to ₱41,399",
            "first_stat": "Regular/Permanent",
            "is_currently_employed": "Yes",
            "present_job_is_first": "No",
            "pres_occ": "Restaurant Manager",
            "pres_emp": "Kapampangan Kitchen Group",
            "present_related_degree": "No",
            "enroll_further_studies": "Yes",
            "further_studies": [
                {
                    "course_degree": "Master in Business Administration",
                    "school": "Angeles University Foundation",
                    "year_enrolled": "2023",
                    "scholarship": "",
                    "is_graduated": "No",
                }
            ],
            "current_occupation": "Restaurant Manager",
            "current_employer": "Kapampangan Kitchen Group",
            "skills": ["Audit", "Excel", "Operations"],
        }
        db.add(
            TracerSubmission(
                account_id=liza.id,
                student_id="2018-0330",
                data_json=payload,
                extra_answers={},
                alignment_status="Misaligned",
                alignment_score=0,
                soc_code="1412",
            )
        )
        db.add(
            AlignmentResult(
                account_id=liza.id,
                overall_match_score=0,
                alignment_justification="Misaligned",
                justification_detail="Restaurant Manager maps to PSOC 1412, outside typical Accountancy pathways.",
                suggested_career_paths=["accountant", "auditor", "finance manager"],
            )
        )
        db.add(
            FurtherStudy(
                account_id=liza.id,
                course_degree="Master in Business Administration",
                school="Angeles University Foundation",
                year_enrolled="2023",
                is_graduated=False,
            )
        )

    if not seed_demo_people and db.query(Account).filter(Account.role == "Admin").count() == 0:
        logger.warning(
            "Production database has no administrator account. Create one before going live; "
            "demo passwords are not seeded in production."
        )

    if db.query(GtsQuestion).filter(GtsQuestion.is_core.is_(False)).count() == 0:
        db.add(
            GtsQuestion(
                section_key="feedback",
                label="How helpful was AUF internship or OJT support in your first job search?",
                input_type="scale",
                options=["1", "2", "3", "4", "5"],
                required=False,
                order_index=10,
                is_core=False,
                active=True,
            )
        )
        db.add(
            GtsQuestion(
                section_key="employment",
                label="Which work arrangement best describes your current job?",
                input_type="multiple_choice",
                options=["On-site", "Hybrid", "Fully remote", "Not applicable"],
                required=False,
                order_index=20,
                is_core=False,
                active=True,
            )
        )

    from app.services.survey import ensure_gts_survey

    ensure_gts_survey(db)

    if seed_demo_people:
        _ensure_demo_job_timelines(db)
        _ensure_demo_perks(db)
        _ensure_demo_cards_and_contact(db)
        _ensure_aac_slots(db)
        _backfill_demo_job_details(db)
        _ensure_demo_perk_redemption(db)

    db.commit()
