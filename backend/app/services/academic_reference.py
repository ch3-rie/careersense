"""AUF academic programs used to update the shared college and course catalog.

The list is a public reference, not a Registrar's Office master file. Existing
catalog rows, course codes, and graduate records are kept. New programs are
added without a course code and marked for review. Nothing is deleted.
"""

from __future__ import annotations

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AcademicProgram, College, UniversityRecord
from app.services.academic_filters import clean_academic

TRACK = " \u2014 "
ENGINEERING_ALIAS = "college of engineering"
ENGINEERING_NAME = "College of Engineering and Architecture"

# name is used when the program is new. track creates a child of parent, using
# the parent row's saved name so an existing degree is not renamed.
REFERENCE_COLLEGES = [
    {
        "name": "College of Allied Medical Professions",
        "code": "CAMP",
        "programs": [
            {"key": "bsmt", "name": "BS Medical Technology", "kind": "undergraduate"},
            {"key": "bsot", "name": "BS Occupational Therapy", "kind": "undergraduate"},
            {"key": "bspharm", "name": "BS Pharmacy", "kind": "undergraduate"},
            {"key": "bscp", "name": "BS Clinical Pharmacy", "kind": "undergraduate"},
            {"key": "bsrt", "name": "BS Radiologic Technology", "kind": "undergraduate"},
            {"key": "bspt", "name": "BS Physical Therapy", "kind": "undergraduate"},
            {"parent": "bspt", "track": "Professional Enhancement Program", "kind": "pathway"},
            {"key": "msmls", "name": "Master of Science in Medical Laboratory Science", "kind": "graduate"},
        ],
    },
    {
        "name": "College of Arts and Sciences",
        "code": "CAS",
        "programs": [
            {"key": "abcomm", "name": "AB Communication", "kind": "undergraduate"},
            {"parent": "abcomm", "track": "Creative Media", "kind": "specialization"},
            {"key": "bsbio", "name": "BS Biology", "kind": "undergraduate"},
            {"parent": "bsbio", "track": "Three-Year Accelerated Program", "kind": "pathway"},
            {"key": "bspsych", "name": "BS Psychology", "kind": "undergraduate"},
            {"key": "abpsych", "name": "AB Psychology", "kind": "undergraduate"},
            {"parent": "abpsych", "track": "International Students", "kind": "pathway"},
            {"parent": "abpsych", "name": "Straight AB Psychology \u2013 MA Psychology Program", "kind": "combined"},
            {"key": "bshb", "name": "BS Human Biology", "kind": "undergraduate"},
            {"key": "mapsych", "name": "Master of Arts in Psychology", "kind": "graduate"},
            {"parent": "mapsych", "track": "Clinical Psychology", "kind": "major"},
        ],
    },
    {
        "name": "College of Business and Accountancy",
        "code": "CBA",
        "programs": [
            {"key": "bsa", "name": "BS Accountancy", "kind": "undergraduate"},
            {"key": "bsma", "name": "BS Management Accounting", "kind": "undergraduate"},
            {"key": "bsba", "name": "BS Business Administration", "kind": "undergraduate"},
            {"parent": "bsba", "track": "Legal Management", "kind": "specialization"},
            {"parent": "bsba", "track": "Marketing Management", "kind": "specialization"},
            {"parent": "bsba", "track": "Management and Entrepreneurship", "kind": "specialization"},
            {"key": "bshm", "name": "BS Hospitality Management", "kind": "undergraduate"},
            {"key": "bstm", "name": "BS Tourism Management", "kind": "undergraduate"},
            {"key": "phdman", "name": "Doctor of Philosophy in Management", "kind": "graduate"},
            {"key": "dba", "name": "Doctor of Business Administration", "kind": "graduate"},
            {"key": "mba", "name": "Master in Business Administration", "kind": "graduate"},
        ],
    },
    {
        "name": "College of Computer Studies",
        "code": "CCS",
        "programs": [
            {"key": "bmma", "name": "Bachelor of Multimedia Arts", "kind": "undergraduate"},
            {"key": "bscs", "name": "BS Computer Science", "kind": "undergraduate"},
            {"key": "bsit", "name": "BS Information Technology", "kind": "undergraduate"},
            {"key": "dit", "name": "Doctor of Information Technology", "kind": "graduate"},
            {"parent": "dit", "track": "Business Intelligence and Data Analytics", "kind": "specialization"},
            {"key": "mit", "name": "Master in Information Technology", "kind": "graduate"},
            {"key": "mds", "name": "Master in Data Science", "kind": "graduate"},
        ],
    },
    {
        "name": "College of Criminal Justice Education",
        "code": "CCJE",
        "programs": [
            {"key": "bscrim", "name": "BS Criminology", "kind": "undergraduate"},
            {"key": "mscj", "name": "Master of Science in Criminal Justice", "kind": "graduate"},
            {"parent": "mscj", "track": "Criminology", "kind": "specialization"},
        ],
    },
    {
        "name": ENGINEERING_NAME,
        "code": "CEA",
        "aliases": [ENGINEERING_ALIAS],
        "programs": [
            {"key": "bsarch", "name": "BS Architecture", "kind": "undergraduate"},
            {"key": "bsce", "name": "BS Civil Engineering", "kind": "undergraduate"},
            {"key": "bscpe", "name": "BS Computer Engineering", "kind": "undergraduate"},
            {"key": "bsece", "name": "BS Electronics Engineering", "kind": "undergraduate"},
        ],
    },
    {
        "name": "College of Education",
        "code": "CED",
        "programs": [
            {"key": "beed", "name": "Bachelor of Elementary Education", "kind": "undergraduate"},
            {"key": "bsed", "name": "Bachelor of Secondary Education", "kind": "undergraduate"},
            {"parent": "bsed", "track": "English", "kind": "major"},
            {"parent": "bsed", "track": "English and Chinese Language Teaching", "kind": "major"},
            {"parent": "bsed", "track": "Mathematics", "kind": "major"},
            {"parent": "bsed", "track": "Science", "kind": "major"},
            {"parent": "bsed", "track": "Social Studies", "kind": "major"},
            {"parent": "bsed", "track": "Values Education", "kind": "major"},
            {"key": "bece", "name": "Bachelor of Early Childhood Education", "kind": "undergraduate"},
            {"key": "bsned", "name": "Bachelor of Special Needs Education", "kind": "undergraduate"},
            {"key": "pcct", "name": "Professional Certificate Course in Teaching", "kind": "certificate"},
            {"key": "phdci", "name": "Doctor of Philosophy in Curriculum and Instruction", "kind": "graduate"},
            {"parent": "phdci", "track": "English Language Teaching", "kind": "major"},
            {"key": "phded", "name": "Doctor of Philosophy in Education", "kind": "graduate"},
            {"parent": "phded", "track": "Educational Management", "kind": "major"},
            {"key": "maed", "name": "Master of Arts in Education", "kind": "graduate"},
            {"parent": "maed", "track": "Educational Management", "kind": "major"},
            {"parent": "maed", "track": "English", "kind": "major"},
            {"parent": "maed", "track": "General Science", "kind": "major"},
            {"parent": "maed", "track": "Early Childhood Education", "kind": "major"},
            {"parent": "maed", "track": "Chinese Language Teaching", "kind": "major"},
            {"parent": "maed", "track": "Special Needs and Inclusive Education", "kind": "major"},
            {"key": "diped", "name": "Diploma in Education", "kind": "diploma"},
            {"parent": "diped", "track": "Educational Management", "kind": "major"},
            {"parent": "diped", "track": "English Language Teaching", "kind": "major"},
        ],
    },
    {
        "name": "College of Nursing",
        "code": "CON",
        "programs": [
            {"key": "bsn", "name": "BS Nursing", "kind": "undergraduate"},
            {"key": "man", "name": "Master of Arts in Nursing", "kind": "graduate"},
            {"parent": "man", "track": "Medical-Surgical Nursing", "kind": "major"},
            {"parent": "man", "track": "Maternal and Child Health", "kind": "major"},
            {"key": "mn", "name": "Master in Nursing", "kind": "graduate"},
            {"parent": "mn", "track": "Medical-Surgical Nursing", "kind": "major"},
            {"parent": "mn", "track": "Maternal and Child Health", "kind": "major"},
        ],
    },
    {
        "name": "School of Law",
        "code": "",
        "programs": [
            {"key": "jd", "name": "Juris Doctor", "kind": "professional"},
        ],
    },
    {
        "name": "School of Medicine",
        "code": "",
        "programs": [
            {"key": "md", "name": "Doctor of Medicine", "kind": "professional"},
        ],
    },
    {
        "name": "Graduate School",
        "code": "",
        "programs": [
            {"key": "drph", "name": "Doctor of Public Health", "kind": "graduate"},
            {"parent": "drph", "track": "Health Promotion and Education", "kind": "major"},
            {"key": "mph", "name": "Master in Public Health", "kind": "graduate"},
            {"parent": "mph", "track": "Non-Thesis", "kind": "pathway"},
            {"key": "msph", "name": "Master of Science in Public Health", "kind": "graduate"},
        ],
    },
]


def normalize_program_name(value: str | None) -> str:
    """Compare degree titles without treating abbreviations as different programs."""
    text = clean_academic(value).casefold()
    text = text.replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    text = re.sub(r"\b(major|specialization|specializing) in\b", " ", text)
    text = re.sub(r"^bachelor of science in\s+", "bs ", text)
    text = re.sub(r"^bachelor of arts in\s+", "ab ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def apply_auf_reference(db: Session) -> bool:
    """Add the reference colleges and programs onto the existing catalog."""
    from app.services.academic_catalog import sync_catalog_from_records

    changed = sync_catalog_from_records(db)
    colleges = {row.name.casefold(): row for row in db.query(College).all()}
    if _rename_engineering(db, colleges):
        changed = True
    programs = list(db.query(AcademicProgram).all())
    by_college: dict[int, dict[str, AcademicProgram]] = {}
    for program in programs:
        by_college.setdefault(program.college_id, {})[normalize_program_name(program.name)] = program

    for entry in REFERENCE_COLLEGES:
        college = _ensure_college(db, colleges, entry["name"], entry.get("code") or "", entry.get("aliases") or [])
        if college is None:
            continue
        changed = True if college[1] else changed
        college_row = college[0]
        indexed = by_college.setdefault(college_row.id, {})
        saved: dict[str, AcademicProgram] = {}
        for item in entry["programs"]:
            parent = saved.get(item.get("parent") or "")
            if item.get("parent") and parent is None:
                continue
            name = _display_name(item, parent)
            if len(name) > 200:
                continue
            key = normalize_program_name(name)
            program = indexed.get(key)
            if program is None:
                program = AcademicProgram(
                    college_id=college_row.id,
                    parent_id=parent.id if parent else None,
                    name=name,
                    course_code="",
                    kind=item["kind"],
                    review_status="needs_review",
                )
                db.add(program)
                db.flush()
                indexed[key] = program
                changed = True
            else:
                if not clean_academic(program.kind):
                    program.kind = item["kind"]
                    changed = True
                if parent and not program.parent_id and parent.id != program.id:
                    program.parent_id = parent.id
                    changed = True
            if item.get("key"):
                saved[item["key"]] = program
    if changed:
        db.flush()
    return changed


def _display_name(item: dict, parent: AcademicProgram | None) -> str:
    if item.get("track"):
        base = parent.name if parent else item.get("name") or item["track"]
        return f"{base}{TRACK}{item['track']}"
    return item["name"]


def _ensure_college(db: Session, colleges: dict[str, College], name: str, code: str, aliases: list[str]) -> tuple[College, bool] | None:
    changed = False
    row = colleges.get(name.casefold())
    if row is None:
        for alias in aliases:
            row = colleges.get(alias.casefold())
            if row:
                break
    if row is None:
        row = College(name=name, code=code)
        db.add(row)
        db.flush()
        colleges[name.casefold()] = row
        return row, True
    if code and not clean_academic(row.code):
        row.code = code
        changed = True
    return row, changed


def _rename_engineering(db: Session, colleges: dict[str, College]) -> bool:
    """Keep civil-engineering graduates on the architecture college without rewriting their degrees."""
    old = colleges.get(ENGINEERING_ALIAS)
    official = colleges.get(ENGINEERING_NAME.casefold())
    if not old or official:
        return False
    old.name = ENGINEERING_NAME
    if not clean_academic(old.code):
        old.code = "CEA"
    db.flush()
    records = (
        db.query(UniversityRecord)
        .filter(func.lower(func.trim(UniversityRecord.college)) == ENGINEERING_ALIAS)
        .all()
    )
    for record in records:
        record.college = ENGINEERING_NAME
    colleges[ENGINEERING_NAME.casefold()] = old
    colleges.pop(ENGINEERING_ALIAS, None)
    return True
