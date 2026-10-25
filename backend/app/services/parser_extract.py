"""Format-agnostic heuristic extraction of resume entities."""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.services.parser_document import DocumentView

MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
MONTH_PATTERN = r"(?:january|february|march|april|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
YEAR_PATTERN = r"(?:19|20)\d{2}"
PRESENT_PATTERN = r"(?:present|current|now|ongoing)"
DATE_TOKEN = rf"(?:{MONTH_PATTERN}\s+\.?\s*{YEAR_PATTERN}|{YEAR_PATTERN}\s*[-/]\s*(?:0?[1-9]|1[0-2])(?!\d)|(?:0?[1-9]|1[0-2])(?!\d)\s*[-/]\s*{YEAR_PATTERN}|{YEAR_PATTERN})"
RANGE_SEPARATOR = r"\s*[-–—to]+\s*"

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "education": (
        "education", "educational background", "educational attainment", "academic background",
        "academic qualifications", "academic history", "qualifications", "scholastic background",
        "academic", "education and training",
    ),
    "experience": (
        "experience", "work experience", "employment history", "professional experience",
        "career history", "work history", "employment", "professional background",
        "professional history", "relevant experience", "work", "career experience",
        "employment history and internships", "experience and internships",
        "experience & internships", "internships", "employment record", "employment records",
        "job history", "work record", "professional work experience",
    ),
    "skills": (
        "skills", "technical skills", "core skills", "core competencies", "competencies",
        "expertise", "technical expertise", "tools", "technologies", "tools/technologies",
        "key skills", "skill set", "technical competencies", "professional skills",
        "skills & tools", "skills and tools",
    ),
    "certifications": (
        "certifications", "licenses", "credentials", "professional certifications",
        "licensure", "certificates", "certifications and licenses",
        "licenses and certifications", "professional licenses",
    ),
    "seminars": (
        "seminars", "seminars attended", "seminars and trainings", "trainings attended",
        "training attended", "workshops", "workshops attended", "training and seminars",
        "trainings", "training", "seminars trainings and workshops",
        "seminars and workshops", "trainings and workshops",
    ),
    "awards": (
        "awards", "achievements", "honors", "honours", "awards and achievements",
        "awards or achievements", "achievements received", "honors and awards",
        "awards and honors", "honors and achievements",
    ),
    "projects": (
        "projects", "academic projects", "selected projects", "relevant projects",
        "personal projects", "key campaign projects", "campaign projects",
    ),
    "publications": (
        "publications", "publication", "selected publications", "peer-reviewed publications",
        "research publications", "published works",
    ),
    "organizations": (
        "organizations", "leadership", "affiliations", "activities",
        "extracurricular activities", "volunteer", "volunteering",
    ),
    "further_studies": (
        "further studies", "graduate studies", "postgraduate", "post-graduate",
        "continuing education", "higher education",
    ),
    "personal": (
        "personal information", "personal details", "applicant information",
        "personal data", "contact", "contact information", "contact details",
    ),
    "summary": (
        "summary", "professional summary", "career objective", "objective",
        "professional profile", "profile summary", "summary of qualifications", "profile",
    ),
}

JOB_TITLE_HINTS = {
    "engineer", "developer", "programmer", "analyst", "manager", "intern", "internship",
    "specialist", "strategist", "marketer", "buyer", "officer", "assistant", "consultant", "coordinator", "administrator",
    "nurse", "teacher", "instructor", "accountant", "designer", "architect", "technician",
    "associate", "lead", "head", "director", "supervisor", "clerk", "cashier", "staff",
    "administrator", "administrator", "scientist", "researcher", "writer", "editor",
    "representative", "executive", "president", "founder", "owner", "freelancer",
    "trainee", "apprentice", "ojt", "support", "administrator", "hr", "recruiter",
    "pharmacist", "therapist", "counselor", "lawyer", "attorney", "auditor",
    "investigator", "physician", "surgeon", "professor", "clinician",
    "tutor", "writer", "chef", "cook", "barista", "crew", "cashier",
    "software", "frontend", "backend", "full-stack", "fullstack", "qa", "tester",
}
# Role words that must never be split into a person's name. "Clinical" and
# "research" stay out of JOB_TITLE_HINTS so a duty sentence is not turned into a job.
NAME_ROLE_WORDS = JOB_TITLE_HINTS | {
    "principal", "clinical", "investigator", "physician", "surgeon", "professor",
    "clinician", "pathologist", "epidemiologist", "resident", "fellow",
    "medical", "research", "trial", "trials",
}
EMPLOYER_HINTS = {
    "inc", "corp", "corporation", "ltd", "llc", "university", "college", "hospital",
    "technologies", "technology", "company", "bank", "school", "academy", "institute",
    "foundation", "department", "office", "clinic", "agency", "solutions", "systems",
    "group", "studio", "labs", "laboratory", "ph", "philippines", "services", "consulting",
    "co", "builders", "firm", "enterprises", "industries",
}
DEGREE_PATTERN = re.compile(
    r"\b(?:bachelor(?:'s)?(?:\s+of\s+(?:science|arts|education|business))?(?:\s+in)?|"
    r"master(?:'s)?(?:\s+of\s+(?:science|arts|business))?(?:\s+in)?|"
    r"doctor(?:ate)?(?:\s+of)?|ph\.?d|mba|"
    r"associate(?:'s)?(?:\s+degree|\s+in)|"
    r"diploma(?:\s+in)?|post-?graduate\s+diploma|graduate\s+certificate|"
    r"certificate\s+in|tesda|technical-vocational|"
    r"b\.?\s*s\.?|b\.?\s*a\.?|m\.?\s*s\.?|m\.?\s*a\.?|"
    r"bsit|bscs|bsis|bsn|bsba|bsce|bsee|bsme|bsa|ab)\b",
    re.I,
)
BACHELORS_PATTERN = re.compile(
    r"\b(?:bachelor|b\.?\s*s\.?|b\.?\s*a\.?|bsit|bscs|bsis|bsn|bsba|bsce|bsee|bsme|bsa|ab)\b",
    re.I,
)
GRADUATE_PATTERN = re.compile(
    r"\b(?:master|mba|m\.?\s*s\.?|m\.?\s*a\.?|doctor(?:ate)?|ph\.?d|"
    r"post[-\s]?graduate(?:\s+(?:stud(?:y|ies)|program|diploma|certificate))?|"
    r"graduate\s+stud(?:y|ies)|graduate\s+program|"
    r"continuing\s+education)\b",
    re.I,
)
INSTITUTION_PATTERN = re.compile(
    r"\b(?:university|college|institute|academy|school|auf|angeles university|"
    r"polytechnic|campus)\b",
    re.I,
)
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[\s\-\.]?)?(?:\(?\d{2,4}\)?[\s\-\.]?)\d{3,4}[\s\-\.]?\d{3,4}")
NAME_STOP = re.compile(
    r"resume|curriculum vitae|\bcv\b|phone|address|email|profile|objective|"
    r"professional summary|contact|linkedin|github|portfolio|personal information|"
    r"applicant information|personal details",
    re.I,
)
LOCATION_STOP = re.compile(
    r"\b(philippines|city|province|barangay|street|avenue|road|village|subdivision|"
    r"email|phone|mobile|tel|fax|linkedin|github)\b",
    re.I,
)
SURNAME_PARTICLES = {
    "de", "del", "dela", "della", "da", "di", "dos", "das", "la", "las", "los",
    "san", "santa", "sta", "sto", "van", "von", "bin", "ibn", "le", "mc", "mac",
}
COMPOUND_GIVEN_PREFIXES = {
    "maria", "ma", "marie", "mary", "ana", "anna", "ann", "anne", "juana",
    "juan", "jose", "john", "jean", "sean", "shaun", "angel", "angela",
    "carlo", "carlos", "mark", "mae", "lou", "luz", "rose", "joy", "grace",
    "paul", "paolo", "miguel", "antonio", "luis", "luisa", "ma.",
}
DUTY_START = re.compile(
    r"^(?:developed|maintained|configured|managed|performed|created|implemented|"
    r"designed|built|responsible|worked|gathered|tested|deployed|wrote|led|"
    r"assisted|provided|analyzed|monitored|supported|collaborated|optimized|"
    r"automated|integrated|handled|conducted|coordinated|reviewed|spearheaded|"
    r"directed|increased|achieved|reduced|delivered|executed|launched|generated)\b",
    re.I,
)
NAME_FIELD_PATTERNS = (
    ("first_name", re.compile(r"^(?:first\s*name|given\s*name|firstname|given)\s*[:\-]\s*(.+)$", re.I)),
    ("middle_name", re.compile(r"^(?:middle\s*name|middle\s*initial|mi)\s*[:\-]\s*(.+)$", re.I)),
    ("last_name", re.compile(r"^(?:last\s*name|surname|family\s*name|lastname)\s*[:\-]\s*(.+)$", re.I)),
    ("full_name", re.compile(
        r"^(?:full\s*name|complete\s*name|applicant\s*name|candidate\s*name|name of applicant)\s*[:\-]\s*(.+)$",
        re.I,
    )),
)
BARE_NAME_LABEL = re.compile(r"^(?:name|full\s*name|applicant\s*name)\s*[:\-]\s*(.+)$", re.I)
KNOWN_SKILLS = {
    "python", "javascript", "typescript", "java", "php", "sql", "mysql", "postgresql",
    "mongodb", "react", "angular", "vue", "node.js", "nodejs", "html", "css", "git",
    "docker", "kubernetes", "aws", "azure", "gcp", "rest", "graphql", "django", "flask",
    "laravel", "spring", "excel", "powerpoint", "word", "figma", "photoshop", "linux",
    "c++", "c#", ".net", "pandas", "numpy", "tensorflow", "pytorch", "next.js", "express",
    "redis", "firebase", "tailwind", "bootstrap", "kotlin", "swift", "go", "rust",
    "power bi", "tableau", "jira", "figma", "canva", "sap", "quickbooks",
}
SKILL_CANON = {
    "js": "JavaScript", "javascript": "JavaScript", "ts": "TypeScript", "typescript": "TypeScript",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js", "reactjs": "React",
    "react": "React", "python": "Python", "php": "PHP", "sql": "SQL", "html": "HTML",
    "css": "CSS", "git": "Git", "postgresql": "PostgreSQL", "mysql": "MySQL",
}

SEPARATORS = re.compile(r"\s*[|•·—]\s*")
TITLE_STOP = re.compile(
    r"references|curriculum vitae|confidential|available upon|phone|email|address|linkedin|github",
    re.I,
)
COUNTRY_NAMES = {"philippines", "singapore", "japan", "canada", "australia"}


def _is_page_furniture(text: str) -> bool:
    """Page counters such as 'Page 1 of 1' are not resume records."""
    compact = re.sub(r"\s+", " ", _strip_bullet(text or "")).strip(" -–—|:.")
    if not compact:
        return False
    return bool(
        re.fullmatch(r"(?:page|pg)\.?\s*\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?", compact, re.I)
        or re.fullmatch(r"\d{1,4}\s*(?:of|/)\s*\d{1,4}", compact, re.I)
    )


def lines_from_document(document: DocumentView) -> list[str]:
    """Keep the document reader's order.

    PDF and DOCX extraction already rebuilds columns, date rails, and table rows.
    Splitting those blocks again by horizontal position pulls a date or a skill
    out of the record it belongs to.
    """
    if document.blocks:
        lines: list[str] = []
        for block in document.blocks:
            for piece in (getattr(block, "text", "") or "").splitlines():
                cleaned = _strip_bullet(piece)
                if cleaned and not _is_page_furniture(cleaned):
                    lines.append(cleaned)
        if lines:
            return lines
    return [
        cleaned for line in (document.text or "").splitlines()
        if (cleaned := _strip_bullet(line)) and not _is_page_furniture(cleaned)
    ]


def _strip_bullet(text: str) -> str:
    return re.sub(r"^[\u2022\u25cf\u25e6\u25aa\-\*\u2013\u2014]\s*", "", (text or "").strip())


def classify_sections(lines: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {key: [] for key in SECTION_ALIASES}
    buckets["other"] = []
    seen: set[str] = set()
    current = "other"
    for line in lines:
        heading = _heading_key(line)
        if heading:
            seen.add(heading)
            current = heading
            continue
        buckets.setdefault(current, []).append(line)
    buckets["_seen"] = sorted(seen)
    return buckets


def _normalize_heading(text: str) -> str:
    compact = re.sub(r"[:\-–—|]+$", "", (text or "").strip())
    compact = re.sub(r"\s+", " ", compact).lower()
    compact = re.sub(r"\bsection\b", " ", compact)
    normalized = re.sub(r"[^a-z0-9]+", " ", compact)
    normalized = re.sub(r"\b(?:and|or)\b", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _heading_key(line: str) -> str | None:
    normalized = _normalize_heading(line)
    if not normalized or len(normalized) > 60:
        return None
    if EMAIL_PATTERN.search(normalized) or PHONE_PATTERN.search(line):
        return None
    words = normalized.split()
    if len(words) > 8:
        return None
    for key, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            alias_norm = _normalize_heading(alias)
            if not alias_norm:
                continue
            if normalized == alias_norm:
                return key
            if len(alias_norm) >= 10 and " " in alias_norm and alias_norm in normalized and len(words) <= 8:
                return key
    return None


def parse_date_token(text: str) -> str:
    if not text:
        return ""
    lowered = text.strip().lower()
    if re.fullmatch(PRESENT_PATTERN, lowered):
        return "present"
    month = None
    for token, number in MONTH_MAP.items():
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            month = number
            break
    numeric = re.search(r"\b(0?[1-9]|1[0-2])\s*[-/]\s*((?:19|20)\d{2})\b", text)
    year_month = re.search(r"\b((?:19|20)\d{2})\s*[-/]\s*(0?[1-9]|1[0-2])\b", text)
    year_match = re.search(rf"\b({YEAR_PATTERN})\b", text)
    if not year_match:
        return ""
    year = year_match.group(1)
    if month:
        return f"{year}-{month:02d}"
    if numeric:
        return f"{numeric.group(2)}-{int(numeric.group(1)):02d}"
    if year_month:
        return f"{year_month.group(1)}-{int(year_month.group(2)):02d}"
    return year


def parse_date_range(text: str) -> tuple[str, str, str]:
    if not text:
        return ("", "", "")
    present = bool(re.search(rf"\b{PRESENT_PATTERN}\b", text, re.I))
    parts = re.split(r"\s*[-–—]\s*|\s+to\s+", text, maxsplit=1, flags=re.I)
    if len(parts) == 1:
        token = parse_date_token(parts[0])
        if token == "present":
            return ("", "", "Yes")
        return (token, "", "Yes" if present else "")
    start = parse_date_token(parts[0])
    if start == "present":
        start = ""
    end_raw = parts[1].strip()
    if re.search(rf"\b{PRESENT_PATTERN}\b", end_raw, re.I):
        return (start, "", "Yes")
    end = parse_date_token(end_raw)
    if end == "present":
        return (start, "", "Yes")
    return (start, end, "No" if start and end else "")


def _looks_like_title(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered or DEGREE_PATTERN.search(text) or INSTITUTION_PATTERN.search(text):
        return False
    if EMAIL_PATTERN.search(text) or TITLE_STOP.search(text) or _heading_key(text) or DUTY_START.search(text):
        return False
    if lowered in COUNTRY_NAMES:
        return False
    tokens = set(re.findall(r"[a-z]+", lowered))
    if tokens & JOB_TITLE_HINTS:
        return True
    if tokens & EMPLOYER_HINTS:
        return False
    words = text.split()
    if _looks_like_person_name(text):
        return False
    return 2 <= len(words) <= 8 and text[0].isalpha()


def _looks_like_person_name(text: str) -> bool:
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    if tokens & EMPLOYER_HINTS or tokens & NAME_ROLE_WORDS:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'\-]+", text)
    return 2 <= len(words) <= 4 and len(words) == len(text.split())


def _looks_like_employer(text: str) -> bool:
    lowered = text.lower()
    if EMAIL_PATTERN.search(text) or parse_date_token(text) or DEGREE_PATTERN.search(text):
        return False
    if TITLE_STOP.search(text) or _heading_key(text) or lowered in COUNTRY_NAMES:
        return False
    if _looks_like_person_name(text):
        return False
    tokens = set(re.findall(r"[a-z]+", lowered))
    if tokens & EMPLOYER_HINTS:
        return True
    words = re.findall(r"[A-Za-z][A-Za-z&.\-']+", text)
    return 1 <= len(words) <= 10 and not (set(word.lower() for word in words) & JOB_TITLE_HINTS)


def _split_job_line(text: str) -> list[str]:
    parts = [part.strip(" -:|•·") for part in SEPARATORS.split(text) if part.strip(" -:|•·")]
    return parts or [text.strip()]


def _label_beside_dates(part: str) -> str:
    cleaned = re.sub(rf"\b{PRESENT_PATTERN}\b", " ", part or "", flags=re.I)
    cleaned = re.sub(DATE_TOKEN, " ", cleaned, flags=re.I)
    cleaned = re.sub(r"[-–—/|,()]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _collapse_dates(dates: list[tuple[str, str, str]]) -> tuple[str, str, str]:
    start = end = is_current = ""
    tokens: list[str] = []
    for token_start, token_end, current in dates:
        if current == "Yes":
            is_current = "Yes"
        if token_start:
            tokens.append(token_start)
        if token_end:
            tokens.append(token_end)
    if tokens:
        start = tokens[0]
        if is_current == "Yes":
            end = ""
        elif len(tokens) > 1:
            end = tokens[-1]
            is_current = "No"
    return start, end, is_current


def _classify_job_parts(parts: list[str]) -> dict[str, str]:
    title = employer = ""
    dates: list[tuple[str, str, str]] = []
    unused: list[str] = []
    for part in parts:
        if EMAIL_PATTERN.search(part) or PHONE_PATTERN.search(part) or _heading_key(part) or DEGREE_PATTERN.search(part):
            continue
        start_date, end_date, current = parse_date_range(part)
        is_present = current == "Yes" or parse_date_token(part) == "present"
        if start_date or end_date or is_present:
            dates.append((start_date, end_date, "Yes" if is_present else current))
            label = _label_beside_dates(part)
            if label and label.lower() != part.strip().lower() and _looks_like_title(label) and not title:
                title = label
            continue
        if _looks_like_title(part) and not title:
            title = part
            continue
        if not employer and (_looks_like_employer(part) or (title and (_plausible_org(part) or _companyish(part)))):
            employer = part
            continue
        unused.append(part)
    start, end, is_current = _collapse_dates(dates)
    for part in unused:
        if EMAIL_PATTERN.search(part) or TITLE_STOP.search(part) or DEGREE_PATTERN.search(part):
            continue
        if not title and _looks_like_title(part):
            title = part
        elif not employer and (_looks_like_employer(part) or (title and (_plausible_org(part) or _companyish(part)))):
            employer = part
    return {
        "job_title": title,
        "employer": employer,
        "start_date": start,
        "end_date": end,
        "is_current": is_current,
    }


def _supervisor_from_line(line: str) -> tuple[str, str]:
    if not re.match(r"^(immediate head|supervisor|reported to|manager)\s*[:\-]", line, re.I):
        return ("", "")
    payload = line.split(":", 1)[1].strip() if ":" in line else re.sub(r"^[^:]+\s+", "", line)
    email_match = EMAIL_PATTERN.search(payload)
    email = email_match.group(0) if email_match else ""
    name = payload.replace(email, "").strip(" ()-,")
    return (name, email)


def extract_experiences(lines: list[str], sections: dict[str, list[str]]) -> list[dict[str, str]]:
    focused = sections.get("experience") or []
    if focused:
        return _parse_job_lines(focused, allow_partial=True)
    skipped = set()
    for key in (
        "education", "skills", "certifications", "seminars", "awards", "summary",
        "projects", "publications", "further_studies",
    ):
        skipped.update(sections.get(key) or [])
    return _parse_job_lines([line for line in lines if line not in skipped], allow_partial=False)


def _companyish(text: str) -> bool:
    """Organization line that merely contains a job word, such as 'Sample Software'."""
    if not text or not _looks_like_title(text) or _heading_key(text):
        return False
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    role_words = JOB_TITLE_HINTS | {
        "senior", "junior", "staff", "lead", "part", "time", "full", "web", "qa", "data", "it",
        "digital", "technical", "customer", "service", "project", "product", "human", "resource",
    }
    if not tokens or all(token in role_words for token in tokens):
        return False
    return True


def _date_follows(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    follower = lines[index + 1]
    return _is_date_only(follower) or bool(re.search(DATE_TOKEN, follower, re.I) and not _looks_like_title(follower))


def _plausible_org(text: str) -> bool:
    """An organization line that should stay with the job above it, not become the next title."""
    if not text or _looks_like_title(text) or _heading_key(text):
        return False
    if EMAIL_PATTERN.search(text) or DEGREE_PATTERN.search(text) or DUTY_START.search(text):
        return False
    if _is_date_only(text):
        return False
    if _looks_like_employer(text):
        return True
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9&.\-']*", text)
    return 1 <= len(words) <= 8


def _is_date_only(line: str) -> bool:
    leftover = line
    previous = None
    while previous != leftover:
        previous = leftover
        leftover = re.sub(DATE_TOKEN, "", leftover, count=1, flags=re.I)
    leftover = re.sub(PRESENT_PATTERN, "", leftover, flags=re.I)
    leftover = re.sub(r"[-–—to/\s]+", "", leftover, flags=re.I)
    start, end, current = parse_date_range(line)
    return bool(start or end or current) and len(leftover) < 3


def _clear_role_title(line: str) -> bool:
    """A short line that names a role, even when the employer and dates are missing."""
    if not line or len(line.split()) > 8 or not _looks_like_title(line):
        return False
    tokens = set(re.findall(r"[a-z]+", line.lower()))
    return bool(tokens & JOB_TITLE_HINTS)


def _parse_job_lines(lines: list[str], allow_partial: bool = False) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    skip_until = -1
    for index, line in enumerate(lines):
        if index < skip_until:
            continue
        if _heading_key(line) or NAME_STOP.search(line) or TITLE_STOP.search(line):
            continue
        if EMAIL_PATTERN.search(line) or DEGREE_PATTERN.search(line):
            continue
        if INSTITUTION_PATTERN.search(line) and not _looks_like_title(line):
            continue
        if _looks_like_person_name(line) and not (set(re.findall(r"[a-z]+", line.lower())) & JOB_TITLE_HINTS):
            continue
        if not _looks_like_title(line) and not re.search(DATE_TOKEN, line, re.I):
            continue
        if _is_date_only(line) and index and (DEGREE_PATTERN.search(lines[index - 1]) or INSTITUTION_PATTERN.search(lines[index - 1])):
            continue
        window = lines[index:index + 5]
        joined = " | ".join(window)
        has_dates = bool(re.search(DATE_TOKEN, joined, re.I) or re.search(PRESENT_PATTERN, joined, re.I))
        partial_title = allow_partial and _clear_role_title(line)
        if not has_dates and not partial_title and not (
            _looks_like_title(line) and index + 1 < len(lines) and _looks_like_employer(lines[index + 1])
        ):
            continue
        parts = _split_job_line(line)
        parsed = _classify_job_parts(parts)
        consumed = 1
        if index + 1 < len(lines):
            nxt = lines[index + 1]
            own_job = _standalone_job_line(nxt)
            needs_employer = not parsed.get("employer")
            # "Title" on one line and "Hospital | 2022 - Present" on the next.
            # The dated line can stand alone, but it belongs to the title above it
            # when that line has no role word of its own.
            dated_org = needs_employer and _dated_org_line(nxt)
            can_take_next = (not own_job or dated_org) and (
                _is_date_only(nxt)
                or _looks_like_employer(nxt)
                or _plausible_org(nxt)
                or "|" in nxt
                or bool(re.search(DATE_TOKEN, nxt, re.I))
                or (_looks_like_title(nxt) and not parsed.get("job_title"))
            ) and not (DUTY_START.search(nxt) or nxt.startswith(("•", "-", "*")))
            if can_take_next:
                one_line = _classify_job_parts(parts + _split_job_line(nxt))
                if _job_score(one_line) >= _job_score(parsed):
                    parsed = one_line
                    consumed = 2
        cursor = index + consumed
        while consumed < 5 and cursor < len(lines):
            nxt = lines[cursor]
            if _heading_key(nxt) or DUTY_START.search(nxt) or nxt.startswith(("•", "-", "*")):
                break
            if _standalone_job_line(nxt) and parsed.get("job_title"):
                break
            if (
                _looks_like_title(nxt)
                and parsed.get("job_title")
                and not re.search(DATE_TOKEN, nxt, re.I)
                and not _date_follows(lines, cursor)
            ):
                break
            trial = _classify_job_parts(
                _split_job_line(" | ".join(lines[index:cursor + 1]))
            )
            if _job_score(trial) > _job_score(parsed):
                parsed = trial
                consumed += 1
                cursor += 1
                continue
            if cursor + 1 < len(lines) and consumed < 4:
                ahead = _classify_job_parts(_split_job_line(" | ".join(lines[index:cursor + 2])))
                if _job_score(ahead) > _job_score(parsed) and not _standalone_job_line(lines[cursor + 1]):
                    parsed = ahead
                    consumed += 2
                    cursor += 2
                    continue
            break
        if _job_score(parsed) < 2 and not (allow_partial and _clear_role_title(parsed.get("job_title", ""))):
            continue
        supervisor_name = supervisor_email = ""
        look = index + consumed
        while look < min(len(lines), index + consumed + 3):
            name, email = _supervisor_from_line(lines[look])
            if name or email:
                supervisor_name, supervisor_email = name, email
                look += 1
                continue
            break
        description_parts: list[str] = []
        while look < min(len(lines), index + consumed + 8):
            nxt = lines[look]
            if _heading_key(nxt) or EMAIL_PATTERN.search(nxt) or DEGREE_PATTERN.search(nxt):
                break
            if _supervisor_from_line(nxt)[0] or _supervisor_from_line(nxt)[1]:
                look += 1
                continue
            if _looks_like_title(nxt) and not DUTY_START.search(nxt):
                break
            if _looks_like_employer(nxt) and not DUTY_START.search(nxt) and not nxt.startswith(("•", "-", "*")):
                if _job_score(_classify_job_parts(_split_job_line(nxt))) >= 2:
                    break
            if _is_date_only(nxt):
                break
            if re.search(r"(?:₱|php|salary|compensation)", nxt, re.I):
                local_salary = extract_salary(nxt)
                if local_salary.get("current") and not parsed.get("salary_range"):
                    parsed["salary_range"] = local_salary["current"]
                look += 1
                continue
            if DUTY_START.search(nxt) or nxt.startswith(("•", "-", "*")) or len(nxt.split()) >= 6:
                description_parts.append(_strip_bullet(nxt))
                look += 1
                continue
            break
        parsed.update({
            "salary_range": parsed.get("salary_range", ""),
            "employment_status": _status_from_title(parsed.get("job_title", "")) or _status_from_context(
                " ".join(description_parts)
            ),
            "supervisor_name": supervisor_name,
            "supervisor_email": supervisor_email,
            "related_to_degree": "",
            "description": " ".join(description_parts).strip(),
        })
        jobs.append(parsed)
        skip_until = look
    return _dedupe_jobs(jobs)


def _dated_org_line(line: str) -> bool:
    """An organization and a date, with no job-title word of its own."""
    if not line or not (re.search(DATE_TOKEN, line, re.I) or re.search(PRESENT_PATTERN, line, re.I)):
        return False
    for part in _split_job_line(line):
        if re.search(DATE_TOKEN, part, re.I) or re.search(PRESENT_PATTERN, part, re.I):
            continue
        tokens = set(re.findall(r"[a-z]+", part.lower()))
        if tokens & JOB_TITLE_HINTS:
            return False
    return True


def _standalone_job_line(line: str) -> bool:
    """A line that already contains its own title plus a date or employer."""
    job = _classify_job_parts(_split_job_line(line))
    return bool(job.get("job_title") and (job.get("start_date") or job.get("is_current") == "Yes" or job.get("employer")))


def _job_score(job: dict[str, str]) -> int:
    return sum(1 for key in ("job_title", "employer", "start_date") if job.get(key))


def _status_from_title(title: str) -> str:
    lowered = (title or "").lower()
    if re.search(r"self[- ]?employed|freelance|freelancer", lowered):
        return "Self-Employed"
    if re.search(r"\b(?:intern(?:ship)?|ojt|trainee|apprentice)\b", lowered):
        return "Contractual/Casual"
    return ""


def _status_from_context(text: str) -> str:
    lowered = (text or "").lower()
    labeled = re.search(
        r"(?:employment\s+status|status)\s*[:\-]\s*(regular(?:/permanent)?|permanent|probationary|contractual|casual|self[-\s]?employed|freelance)",
        lowered,
    )
    if not labeled:
        return ""
    token = labeled.group(1)
    if "self" in token or "freelance" in token:
        return "Self-Employed"
    if "probation" in token:
        return "Probationary"
    if "contract" in token or "casual" in token:
        return "Contractual/Casual"
    return "Regular/Permanent"


def _dedupe_jobs(jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []
    for job in jobs:
        key = (
            job.get("job_title", "").lower(),
            job.get("employer", "").lower(),
            job.get("start_date", ""),
        )
        if key in seen or not any(key):
            continue
        seen.add(key)
        unique.append(job)
    return unique


def _completion_status(blob: str, current: str, year_graduated: str, year_confidence: str) -> str:
    if re.search(r"\bexpected\b", blob or "", re.I):
        return "expected"
    if current == "Yes" or re.search(r"\b(?:ongoing|in progress|currently pursuing|pursuing)\b", blob or "", re.I):
        return "ongoing"
    if re.search(r"\b(?:incomplete|withdrawn|did not finish)\b", blob or "", re.I):
        return "incomplete"
    if year_graduated and year_confidence == "high":
        return "graduated"
    if year_graduated:
        return "unknown"
    return "unknown"


def _education_year(blob: str, start: str, end: str) -> tuple[str, str]:
    """Return a graduation year only when the text says which year it is."""
    if re.search(r"\bexpected\b", blob, re.I):
        token = end or start
        return ((token or "")[:4], "medium" if token else "low")
    if re.search(r"\b(?:graduated|class of)\b", blob, re.I):
        token = end or start
        return ((token or "")[:4], "high" if token else "low")
    if start and end and start[:4] != end[:4]:
        return (end[:4], "high")
    if start and end and start[:4] == end[:4]:
        return (end[:4], "medium")
    return ("", "low")


def extract_education(lines: list[str], sections: dict[str, list[str]]) -> list[dict[str, str]]:
    pool = list(sections.get("education") or [])
    pool.extend(sections.get("further_studies") or [])
    if pool:
        return _parse_education_lines(pool)
    certifications = set(sections.get("certifications") or [])
    return _parse_education_lines([line for line in lines if line not in certifications])


def _parse_education_lines(lines: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for index, line in enumerate(lines):
        if not DEGREE_PATTERN.search(line) and not INSTITUTION_PATTERN.search(line) and not GRADUATE_PATTERN.search(line):
            continue
        pieces = [line]
        previous_school_belongs_above = (
            index >= 2
            and INSTITUTION_PATTERN.search(lines[index - 1])
            and (DEGREE_PATTERN.search(lines[index - 2]) or GRADUATE_PATTERN.search(lines[index - 2]))
        )
        if (
            index
            and not previous_school_belongs_above
            and INSTITUTION_PATTERN.search(lines[index - 1])
            and not DEGREE_PATTERN.search(lines[index - 1])
            and not GRADUATE_PATTERN.search(lines[index - 1])
        ):
            pieces.insert(0, lines[index - 1])
        for offset in (1, 2):
            if index + offset >= len(lines):
                break
            nxt = lines[index + offset]
            if DEGREE_PATTERN.search(nxt) or GRADUATE_PATTERN.search(nxt):
                break
            if re.match(r"major in\b", nxt, re.I):
                pieces.append(nxt)
                continue
            if (
                INSTITUTION_PATTERN.search(nxt)
                or _is_date_only(nxt)
                or re.search(r"\b(?:expected|graduated|class of)\b", nxt, re.I)
            ):
                pieces.append(nxt)
                continue
            break
        blob = " | ".join(pieces)
        degree = next((piece for piece in pieces if DEGREE_PATTERN.search(piece) or GRADUATE_PATTERN.search(piece)), "")
        major = next((piece for piece in pieces if re.match(r"major in\b", piece, re.I)), "")
        if degree and major and major.lower() not in degree.lower():
            degree = f"{degree} {major}".strip()
        institution = next((piece for piece in pieces if INSTITUTION_PATTERN.search(piece) and piece != degree), "")
        start, end, current = parse_date_range(blob)
        year_graduated, year_confidence = _education_year(blob, start, end)
        if not degree and not institution:
            continue
        records.append({
            "degree": degree,
            "institution": institution,
            "year_graduated": year_graduated,
            "year_enrolled": start[:4] if start and (end or year_confidence == "high") else "",
            "year_confidence": year_confidence,
            "is_graduated": "No" if current == "Yes" or re.search(r"\bexpected\b", blob, re.I) else ("Yes" if year_graduated else ""),
            "completion_status": _completion_status(blob, current, year_graduated, year_confidence),
            "is_bachelors": bool(BACHELORS_PATTERN.search(degree or blob)),
            "is_graduate": bool(GRADUATE_PATTERN.search(degree or blob)),
        })
    return _dedupe_education(records)


def _dedupe_education(records: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []
    for record in records:
        key = (record.get("degree", "").lower(), record.get("institution", "").lower(), record.get("year_graduated", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def select_bachelors(records: list[dict[str, str]]) -> dict[str, str]:
    """The primary bachelor's degree is the earliest one, not a later second degree."""
    bachelors = [row for row in records if row.get("is_bachelors")]
    pool = bachelors or [row for row in records if not row.get("is_graduate")]
    if not pool:
        return {}

    def sort_key(row: dict[str, str]) -> tuple:
        year = str(row.get("year_graduated") or "")
        return (0 if year else 1, year or "9999")

    return sorted(pool, key=sort_key)[0]


def further_study_level(program: str) -> str:
    text = program or ""
    if re.search(r"\b(?:ph\.?d|doctor|doctorate)\b", text, re.I):
        return "doctorate"
    if re.search(r"\b(?:master|mba|m\.?\s*s\.?|m\.?\s*a\.?)\b", text, re.I):
        return "master"
    if re.search(r"\b(?:post-?graduate\s+diploma|graduate\s+certificate|diploma(?:\s+in)?)\b", text, re.I):
        return "diploma"
    if re.search(r"\b(?:post-?graduate|postgraduate|graduate studies|graduate study|graduate program|postgraduate studies|postgraduate study|post-graduate studies|continuing education)\b", text, re.I):
        return "graduate"
    if re.search(r"\b(?:certificate\s+in|tesda|technical-vocational|vocational training)\b", text, re.I):
        return "certificate"
    if re.search(r"\bassociate(?:'s)?(?:\s+degree|\s+in)\b", text, re.I):
        return "associate"
    if BACHELORS_PATTERN.search(text):
        return "bachelor"
    return ""


def further_studies_evidence(
    studies: list[dict] | None = None,
    education: list[dict] | None = None,
    degree_text: str = "",
) -> dict:
    """Structured resume evidence. Missing dates stay blank and are not invented."""
    entries = []
    seen = set()
    primary = select_bachelors(education or [])
    primary_key = (
        str(primary.get("degree", "")).strip().lower(),
        str(primary.get("institution", "")).strip().lower(),
    )

    def add(program: str, institution: str, start: str = "", end: str = "", graduated: str = ""):
        program = str(program or "").strip()
        institution = str(institution or "").strip()
        level = further_study_level(program)
        if not program and not institution:
            return
        key = (program.lower(), institution.lower(), level)
        if key in seen:
            return
        seen.add(key)
        if level == "bachelor" and key[:2] == primary_key:
            return
        specific = level in {"master", "doctorate", "certificate", "bachelor", "diploma", "associate"} and len(program) > 12
        if program and institution and level:
            confidence = "high"
        elif specific:
            confidence = "medium"
        else:
            confidence = "low"
        entries.append({
            "institution": institution,
            "program": program,
            "degree_level": level,
            "start_date": str(start or "").strip(),
            "end_date": str(end or "").strip() if str(graduated or "").lower() != "no" else "",
            "source_text": " | ".join(part for part in (program, institution) if part),
            "confidence": confidence,
        })

    for row in studies or []:
        if not isinstance(row, dict):
            continue
        add(
            row.get("course_degree") or row.get("degree"),
            row.get("school") or row.get("institution"),
            row.get("year_enrolled") or row.get("start_date"),
            row.get("year_graduated") or row.get("end_date"),
            row.get("is_graduated"),
        )
    for row in education or []:
        if not isinstance(row, dict):
            continue
        program = row.get("degree", "")
        level = further_study_level(program)
        if level not in {"master", "doctorate", "graduate", "certificate", "bachelor", "diploma", "associate"}:
            continue
        if level == "bachelor":
            key = (str(program).strip().lower(), str(row.get("institution", "")).strip().lower())
            if key == primary_key:
                continue
        add(program, row.get("institution", ""), row.get("year_enrolled", ""), row.get("year_graduated", ""), row.get("is_graduated"))

    if not entries and further_study_level(degree_text) in {"master", "doctorate", "graduate"}:
        add(degree_text, "")

    usable = [row for row in entries if row["confidence"] in {"high", "medium"}]
    if usable:
        return {"status": "detected", "entries": usable}
    if entries:
        return {"status": "unclear", "entries": entries}
    return {"status": "not_detected", "entries": []}


def further_studies_from_education(records: list[dict[str, str]], primary: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Formal further study only. The primary bachelor's degree is not repeated here."""
    primary = primary or select_bachelors(records)
    primary_key = (
        str(primary.get("degree", "")).strip().lower(),
        str(primary.get("institution", "")).strip().lower(),
    )
    studies = []
    for record in records:
        program = record.get("degree", "")
        institution = record.get("institution", "")
        level = further_study_level(program)
        key = (str(program).strip().lower(), str(institution).strip().lower())
        if primary_key[0] and key == primary_key:
            continue
        formal = level in {"master", "doctorate", "graduate", "diploma"}
        second_bachelor = level == "bachelor" and bool(record.get("is_bachelors"))
        vocational = level == "certificate"
        if not (formal or second_bachelor or vocational):
            continue
        studies.append({
            "course_degree": program,
            "school": institution,
            "year_enrolled": record.get("year_enrolled", ""),
            "is_graduated": record.get("is_graduated") or "",
            "completion_status": record.get("completion_status") or "",
        })
    return studies


def extract_skills(lines: list[str], sections: dict[str, list[str]], resume_text: str) -> list[str]:
    """Read skills from a skills section only. Job text is not scanned for a skill list."""
    del resume_text
    skill_lines = list(sections.get("skills") or [])
    for line in lines:
        match = re.match(r"^(?:technical\s+|core\s+|key\s+|professional\s+)?skills\s*[:\-]\s*(.+)$", line, re.I)
        if match:
            skill_lines.append(match.group(1))
    if not skill_lines:
        return []
    wrapped: list[str] = []
    for line in skill_lines:
        previous = wrapped[-1] if wrapped else ""
        tail = re.split(r"[•·|;]", previous)[-1].strip() if previous else ""
        wrapped_item = (
            bool(previous)
            and re.search(r"[•·|;]", previous)
            and not re.search(r"[•·|;]\s*$", previous)
            and 0 < len(tail) <= 12
            and " " not in tail
            and not NAME_STOP.search(line)
            and not _heading_key(line)
        )
        if wrapped_item:
            wrapped[-1] = f"{previous} {line}"
        else:
            wrapped.append(line)
    blob = "\n".join(wrapped[:12])
    collected = [part.strip(" -:|") for part in re.split(r",|•|·|\||;|\n", blob) if part.strip()]
    cleaned, seen = [], set()
    for skill in collected:
        text = re.sub(r"\s+", " ", skill).strip()
        text = re.sub(r"^(?:and|or)\s+", "", text, flags=re.I).strip()
        if NAME_STOP.search(text) or _is_page_furniture(text):
            continue
        if not text or len(text) > 48 or len(text) < 2:
            continue
        if re.fullmatch(r"(and|or|the|with|using|including)", text, re.I):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(SKILL_CANON.get(key, text))
    return cleaned


def extract_inferred_skills(experiences: list[dict[str, str]], explicit: list[str]) -> list[dict[str, str]]:
    """Skills mentioned only inside job duties. These are not declared skill-section entries."""
    declared = {item.strip().lower() for item in explicit}
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for job in experiences:
        description = job.get("description") or ""
        if not description:
            continue
        for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
            if not re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", description, re.I):
                continue
            canon = SKILL_CANON.get(skill, skill)
            key = canon.lower()
            if key in declared or key in seen:
                continue
            seen.add(key)
            found.append({
                "name": canon if canon[:1].isupper() else canon,
                "evidence_type": "job_description",
                "excerpt": description[:180],
                "job_title": job.get("job_title", ""),
            })
    return found


def extract_name(document: DocumentView, lines: list[str], resume_text: str) -> dict[str, str]:
    labeled = _extract_labeled_name(lines)
    if labeled.get("first_name") and labeled.get("last_name"):
        return labeled
    if labeled.get("full_name"):
        split = _split_name(labeled["full_name"])
        if labeled.get("middle_name") and not split.get("middle_name"):
            split["middle_name"] = labeled["middle_name"]
        return split

    email = extract_email(resume_text)
    candidates: list[tuple[float, str]] = []
    top_blocks = [block for block in document.blocks if block.page == 0][:16]
    max_font = max((block.font_size for block in top_blocks), default=0)
    for block in top_blocks:
        for piece in block.text.splitlines():
            labeled_line = BARE_NAME_LABEL.match(piece.strip())
            payload = _strip_name_decorations(labeled_line.group(1) if labeled_line else piece)
            if not _name_candidate(payload):
                continue
            score = 1.0
            if labeled_line:
                score += 4
            if max_font and block.font_size >= max_font * 0.9:
                score += 3
            if block.y0 <= 120:
                score += 2
            if _email_matches_name(email, payload):
                score += 3
            candidates.append((score, payload))
    for index, line in enumerate(lines[:16]):
        labeled_line = BARE_NAME_LABEL.match(line.strip())
        payload = _strip_name_decorations(labeled_line.group(1) if labeled_line else line)
        if index and _is_name_heading(lines[index - 1]) and _name_candidate(payload):
            candidates.append((4.5, payload))
            continue
        if _name_candidate(payload):
            score = 2.5 if labeled_line else (1.5 if index <= 2 else 0.8)
            if _email_matches_name(email, payload):
                score += 3
            candidates.append((score, payload))
    if not candidates:
        return {"first_name": "", "middle_name": "", "last_name": ""}
    candidates.sort(key=lambda item: item[0], reverse=True)
    return _split_name(candidates[0][1])


def _extract_labeled_name(lines: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in lines[:40]:
        stripped = line.strip()
        for key, pattern in NAME_FIELD_PATTERNS:
            match = pattern.match(stripped)
            if match and key not in found:
                found[key] = match.group(1).strip(" -:|")
        bare = BARE_NAME_LABEL.match(stripped)
        if bare and "full_name" not in found and "first_name" not in found:
            found["full_name"] = bare.group(1).strip(" -:|")
    if found.get("first_name") and found.get("last_name"):
        return {
            "first_name": found["first_name"],
            "middle_name": found.get("middle_name", ""),
            "last_name": found["last_name"],
        }
    return found


def _is_name_heading(line: str) -> bool:
    compact = re.sub(r"[:\-–—|]+$", "", (line or "").strip()).lower()
    return compact in {
        "name", "full name", "applicant name", "complete name",
        "personal information", "personal details", "applicant information",
    }


def _strip_name_decorations(line: str) -> str:
    """Drop a leading honorific and a trailing credential so the name itself can be read."""
    text = BARE_NAME_LABEL.sub(lambda match: match.group(1), line or "").strip()
    text = re.sub(r"^(?:dr|mr|mrs|ms|miss|prof|engr|atty)\.?\s+", "", text, flags=re.I)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(
            r"(?:,|\s)+(?:ph\.?d|m\.?d|md|rn|mba|cpa|rph|mph|msn|dmd|dds|do|llb|llm)\.?$",
            "",
            text,
            flags=re.I,
        ).strip(" ,")
    return text.strip()


def _email_matches_name(email: str, payload: str) -> bool:
    local = (email or "").split("@")[0].lower()
    tokens = [part for part in re.split(r"[^a-z]+", local) if len(part) >= 3]
    haystack = payload.lower()
    return any(part in haystack for part in tokens)


def _name_candidate(line: str) -> bool:
    payload = _strip_name_decorations(line)
    if not payload or not payload[0].isupper() or "|" in payload:
        return False
    if NAME_STOP.search(payload) or EMAIL_PATTERN.search(payload) or _heading_key(payload):
        return False
    if re.search(r"\d", payload) or LOCATION_STOP.search(payload):
        return False
    if DEGREE_PATTERN.search(payload) or INSTITUTION_PATTERN.search(payload):
        return False
    tokens = set(re.findall(r"[a-z]+", payload.lower()))
    if tokens & NAME_ROLE_WORDS or tokens & EMPLOYER_HINTS:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'\-.]+", payload)
    return 2 <= len(words) <= 5


def _take_surname(words: list[str]) -> tuple[list[str], str]:
    if not words:
        return [], ""
    index = len(words) - 1
    surname = [words[index]]
    index -= 1
    while index >= 0 and words[index].lower().rstrip(".") in SURNAME_PARTICLES:
        surname.insert(0, words[index])
        index -= 1
    return words[: index + 1], " ".join(surname)


def _split_name(line: str) -> dict[str, str]:
    cleaned = _strip_name_decorations(line)
    words = re.findall(r"[A-Za-z][A-Za-z'\-.]+", cleaned)
    suffix = ""
    if words and words[-1].lower().rstrip(".") in {"jr", "sr", "ii", "iii", "iv"}:
        suffix = words[-1]
        words = words[:-1]
    if not words:
        return {"first_name": "", "middle_name": "", "last_name": suffix}
    given, last_name = _take_surname(words)
    if suffix:
        last_name = f"{last_name} {suffix}".strip()
    if not given:
        return {"first_name": last_name, "middle_name": "", "last_name": ""}
    if len(given) == 1:
        return {"first_name": given[0], "middle_name": "", "last_name": last_name}
    if len(given) == 2 and re.fullmatch(r"[A-Za-z]\.?", given[1]):
        initial = given[1] if given[1].endswith(".") else f"{given[1]}."
        return {"first_name": given[0], "middle_name": initial, "last_name": last_name}
    if len(given) == 2:
        return {"first_name": " ".join(given), "middle_name": "", "last_name": last_name}
    prefix = given[0].lower().rstrip(".")
    if len(given) >= 3 and prefix in COMPOUND_GIVEN_PREFIXES:
        return {
            "first_name": " ".join(given[:2]),
            "middle_name": " ".join(given[2:]),
            "last_name": last_name,
        }
    return {"first_name": " ".join(given), "middle_name": "", "last_name": last_name}


def extract_email(text: str) -> str:
    match = EMAIL_PATTERN.search(text or "")
    return match.group(0) if match else ""


def extract_country(text: str) -> str:
    first = " ".join((text or "").splitlines()[:25])
    if re.search(r"\bphilippines\b", first, re.I):
        return "Philippines"
    match = re.search(r"\b(united states|usa|canada|singapore|japan|australia|united kingdom)\b", first, re.I)
    if not match:
        return ""
    found = match.group(1).lower()
    if found == "usa":
        return "United States"
    return found.title()


_SALARY_BANDS = (
    (13800, "Below ₱13,800"),
    (27600, "₱13,800 to ₱27,599"),
    (41400, "₱27,600 to ₱41,399"),
    (55200, "₱41,400 to ₱55,199"),
    (69000, "₱55,200 to ₱68,999"),
    (10**12, "₱69,000 and above"),
)


def _amount_to_monthly(raw: str, annual: bool) -> float | None:
    match = re.search(r"(\d{1,3}(?:,\d{3})+|\d{2,7})(\s*k)?", raw or "", re.I)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    if match.group(2):
        value *= 1000
    if annual or re.search(r"\b(?:annual|per\s+year|a\s+year|/yr)\b", raw or "", re.I):
        value /= 12
    return value


def salary_band_for_monthly(amount: float) -> str:
    for ceiling, label in _SALARY_BANDS:
        if amount < ceiling:
            return label
    return "₱69,000 and above"


def extract_salary(text: str) -> dict[str, str]:
    """Return current and expected salary bands. A missing amount stays blank."""
    current = ""
    expected = ""
    saw_hint = False
    parsed = False
    for line in (text or "").splitlines():
        if not re.search(r"(?:₱|php|salary|compensation)", line, re.I):
            continue
        if re.search(r"\b(?:sales|revenue|spend|budget|roi|gross|pipeline|campaign)\b", line, re.I):
            continue
        if re.search(r"\d\s*(?:m|mn|million|b|bn|billion)\b", line, re.I):
            continue
        if re.search(r"\b(?:per\s+hour|an\s+hour|hourly|/hour|/hr|per\s+day|daily|per\s+week|weekly)\b", line, re.I):
            saw_hint = True
            continue
        saw_hint = True
        amounts = re.findall(r"(\d{1,3}(?:,\d{3})+|\d{2,7})\s*(k)?", line, re.I)
        if len(amounts) >= 2:
            continue
        annual = bool(re.search(r"\bannual\b|/yr|per\s+year", line, re.I))
        amount = _amount_to_monthly(line, annual)
        if amount is None:
            continue
        parsed = True
        band = salary_band_for_monthly(amount)
        if re.search(r"\bexpected\b", line, re.I):
            expected = band
        else:
            current = band
    if parsed:
        state = "present"
    elif saw_hint:
        state = "uncertain"
    else:
        state = "absent"
    return {"current": current, "expected": expected, "state": state}


def extract_heuristic(document: DocumentView) -> dict[str, Any]:
    text = document.text or ""
    lines = lines_from_document(document)
    sections = classify_sections(lines)
    seen = set(sections.pop("_seen", []))
    name = extract_name(document, lines, text)
    education = extract_education(lines, sections)
    bachelor = select_bachelors(education)
    experiences = extract_experiences(lines, sections)
    local_retry = False
    if (sections.get("experience") or []) and not experiences:
        local_retry = True
        experiences = _parse_job_lines(lines)
    skills = extract_skills(lines, sections, text)
    studies = further_studies_from_education(education, bachelor)
    studies.extend(_studies_from_section(sections.get("further_studies") or []))
    credentials = extract_credentials(sections)
    salary = extract_salary(text)
    open_current = [job for job in experiences if job.get("is_current") == "Yes" and not job.get("salary_range")]
    if salary["current"] and len(open_current) == 1:
        open_current[0]["salary_range"] = salary["current"]
        open_current[0]["salary_kind"] = "current"
    inferred = extract_inferred_skills(experiences, skills)
    evidence = further_studies_evidence(studies, education, bachelor.get("degree", ""))
    current_flags = [job.get("is_current") for job in experiences]
    if any(flag == "Yes" for flag in current_flags):
        currently = "Yes"
    elif experiences and all(job.get("end_date") for job in experiences) and all(flag == "No" or not flag for flag in current_flags):
        currently = "No"
    else:
        currently = ""
    ever = "Yes" if experiences else ""
    return {
        "first_name": name.get("first_name", ""),
        "middle_name": name.get("middle_name", ""),
        "last_name": name.get("last_name", ""),
        "country": extract_country(text),
        "degree": bachelor.get("degree", ""),
        "year_graduated": bachelor.get("year_graduated", ""),
        "ever_employed": ever,
        "is_currently_employed": currently,
        "experiences": experiences,
        "further_studies": _dedupe_studies(studies),
        "further_studies_evidence": evidence,
        "education_records": education,
        "skills": skills,
        "skill_records": [
            {"name": skill, "evidence_type": "skills_section", "excerpt": skill}
            for skill in skills
        ],
        "inferred_skills": inferred,
        "certifications": credentials["certifications"],
        "seminars": credentials["seminars"],
        "awards": credentials["awards"],
        "projects": credentials["projects"],
        "local_retry": local_retry,
        "skills_section_seen": "skills" in seen,
        "further_studies_section_seen": "further_studies" in seen,
        "salary_state": salary["state"],
        "expected_salary": salary["expected"],
        "email": extract_email(text),
        "education_year_confidence": bachelor.get("year_confidence", ""),
    }


def extract_credentials(sections: dict[str, list[str]]) -> dict[str, list[dict[str, str]]]:
    """Certifications, seminars, and awards named in their own resume sections."""
    return {
        "certifications": _credential_rows(sections.get("certifications") or [], "certification"),
        "seminars": _credential_rows(sections.get("seminars") or [], "seminar"),
        "awards": _credential_rows(sections.get("awards") or [], "award"),
        "projects": _credential_rows(sections.get("projects") or [], "project"),
    }


_PLACE_HINT = re.compile(
    r"\b(?:city|province|campus|online|virtual|philippines|manila|angeles|hall|room|"
    r"building|street|barangay|zoom|municipality|barangay)\b",
    re.I,
)


def _looks_like_place(text: str) -> bool:
    return bool(_PLACE_HINT.search(text or ""))


def _credential_pieces(line: str) -> tuple[list[str], str]:
    """Split a credential line and lift a trailing year out of the other fields."""
    raw_parts = [part.strip(" ,") for part in re.split(r"\s+[|\-–—]\s+", line) if part.strip(" ,")]
    pieces: list[str] = []
    year = ""
    for part in raw_parts:
        if re.fullmatch(r"(?:19|20)\d{2}", part):
            year = part
            continue
        match = re.search(r"\b((?:19|20)\d{2})\b", part)
        remainder = part
        if match:
            remainder = re.sub(r"\s*[,(-]*\s*\b(?:19|20)\d{2}\b\s*\)?", "", part).strip(" ,-()")
            year = year or match.group(1)
        if remainder and not re.fullmatch(r"[\d\W]+", remainder):
            pieces.append(remainder)
    return pieces, year


_CREDENTIAL_TITLE = re.compile(
    r"\b(?:certificate|certification|license|licensure|diploma|award|seminar|workshop|training|dean)\b",
    re.I,
)
_ORG_HINT = re.compile(
    r"\b(?:inc|corp|corporation|company|university|college|institute|hospital|labs|laboratory|"
    r"services|board|council|commission|office|foundation|agency|department|prc|tesda)\b",
    re.I,
)
_AWARD_NOTE = re.compile(r"^(?:recognized|awarded|for outstanding|for academic|for being)\b", re.I)


def _blank_credential(title: str, year: str, extra: list[str], kind: str) -> dict[str, str]:
    awarding_body = location = organizer = issuer = description = ""
    if kind == "seminar":
        places = [part for part in extra if _looks_like_place(part)]
        others = [part for part in extra if part not in places]
        location = places[0] if places else ""
        organizer = others[0] if others else ""
        if not location and len(others) > 1:
            location = others[1]
            organizer = others[0]
    elif kind == "award":
        issuer = extra[0] if extra else ""
        description = " ".join(extra[1:]).strip()
    else:
        awarding_body = extra[0] if extra else ""
        if len(extra) > 1:
            description = " ".join(extra[1:]).strip()
    if kind == "seminar":
        detail = location
    elif kind == "award":
        detail = issuer
    else:
        detail = awarding_body
    return {
        "name": title,
        "detail": detail,
        "year": year,
        "awarding_body": awarding_body,
        "location": location,
        "organizer": organizer,
        "issuer": issuer,
        "description": description,
    }


def _refresh_credential_detail(row: dict[str, str], kind: str) -> None:
    if kind == "seminar":
        row["detail"] = row.get("location") or row.get("organizer") or ""
    elif kind == "award":
        row["detail"] = row.get("issuer") or ""
    else:
        row["detail"] = row.get("awarding_body") or ""


def _continue_credential(row: dict[str, str], text: str, year: str, kind: str) -> bool:
    """Attach a following year, place, organization, or award note to the open record."""
    if year and not text:
        if not row.get("year"):
            row["year"] = year
        return True
    if not text:
        return False
    if _CREDENTIAL_TITLE.search(text):
        return False
    if kind == "seminar" and _looks_like_place(text) and not row.get("location"):
        row["location"] = text
        _refresh_credential_detail(row, kind)
        if year and not row.get("year"):
            row["year"] = year
        return True
    if _ORG_HINT.search(text) and len(text.split()) <= 8:
        target = {"seminar": "organizer", "award": "issuer"}.get(kind, "awarding_body")
        if not row.get(target):
            row[target] = text
            _refresh_credential_detail(row, kind)
            if year and not row.get("year"):
                row["year"] = year
            return True
        return False
    if kind == "award" and not row.get("description") and (_AWARD_NOTE.search(text) or len(text.split()) >= 6):
        row["description"] = text
        return True
    return False


def _credential_rows(lines: list[str], kind: str = "certification") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        name = re.sub(r"\s+", " ", _strip_bullet(line)).strip(" -–—:|")
        if len(name) < 3 or len(name) > 180 or _is_page_furniture(name):
            continue
        if re.fullmatch(r"(?:19|20)\d{2}", name):
            if rows:
                _continue_credential(rows[-1], "", name, kind)
            continue
        pieces, year = _credential_pieces(name)
        if not pieces:
            continue
        title = pieces[0]
        if rows and _continue_credential(rows[-1], title, year, kind):
            continue
        key = title.lower()
        if key in seen or _is_page_furniture(title):
            continue
        seen.add(key)
        rows.append(_blank_credential(title, year, pieces[1:], kind))
    return rows


def _studies_from_section(lines: list[str]) -> list[dict[str, str]]:
    records = []
    for record in _parse_education_lines(lines):
        records.append({
            "course_degree": record.get("degree", ""),
            "school": record.get("institution", ""),
            "year_enrolled": record.get("year_enrolled", ""),
            "is_graduated": record.get("is_graduated") or "No",
            "completion_status": record.get("completion_status") or "",
        })
    return records


def _dedupe_studies(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []
    for row in rows:
        key = (row.get("course_degree", "").lower(), row.get("school", "").lower())
        if not any(key) or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


_COMMON_EVIDENCE_TOKENS = {
    "with", "from", "that", "this", "have", "been", "were", "your", "their", "and",
    "university", "college", "sample", "bachelor", "science", "degree", "master",
    "present", "current", "company", "group", "inc", "corp", "the",
}


def field_evidenced(value: str, resume_text: str) -> bool:
    """True when the value is a phrase in the resume, or its distinctive words are.

    Scattered common words are not enough to support a complete record.
    """
    if not value or not resume_text:
        return False
    needle = re.sub(r"\s+", " ", value.strip().lower())
    haystack = re.sub(r"\s+", " ", resume_text.lower())
    if needle and needle in haystack:
        return True

    def squash(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    if squash(needle) and squash(needle) in squash(haystack):
        return True
    tokens = [
        token for token in re.findall(r"[a-z0-9]{4,}", needle)
        if token not in _COMMON_EVIDENCE_TOKENS
    ]
    if len(tokens) >= 2:
        return all(re.search(rf"\b{re.escape(token)}\b", haystack) for token in tokens)
    if len(tokens) == 1 and len(tokens[0]) >= 6:
        return bool(re.search(rf"\b{re.escape(tokens[0])}\b", haystack))
    return False


def evidence_excerpt(value: str, resume_text: str, window: int = 28) -> str:
    needle = re.sub(r"\s+", " ", (value or "").strip())
    if len(needle) < 2 or not resume_text:
        return ""
    flat = re.sub(r"\s+", " ", resume_text)
    match = re.search(re.escape(needle), flat, re.I)
    if not match:
        return ""
    start = max(0, match.start() - window)
    end = min(len(flat), match.end() + window)
    return flat[start:end].strip()


def assess_extraction(data: dict[str, Any]) -> dict[str, str]:
    """Field states: present, missing, uncertain, absent.

    ``absent`` means the resume was checked and the field is not there.
    That does not by itself request another parser.
    """
    name = "present" if data.get("first_name") and data.get("last_name") else "missing"
    degree = str(data.get("degree") or "").strip()
    year = str(data.get("year_graduated") or "").strip()
    year_confidence = str(data.get("education_year_confidence") or "")
    if degree and year and year_confidence != "low":
        education = "present"
    elif degree and not year:
        education = "uncertain"
    elif degree:
        education = "uncertain" if year_confidence == "low" else "present"
    else:
        education = "missing"
    jobs = data.get("experiences") if isinstance(data.get("experiences"), list) else []
    employment = "present" if any(
        job.get("job_title") and (job.get("employer") or job.get("start_date")) for job in jobs if isinstance(job, dict)
    ) else "missing"
    skills = data.get("skills") if isinstance(data.get("skills"), list) else []
    if skills:
        skill_state = "present"
    elif data.get("skills_section_seen"):
        skill_state = "missing"
    else:
        skill_state = "absent"
    evidence = data.get("further_studies_evidence") if isinstance(data.get("further_studies_evidence"), dict) else {}
    if data.get("further_studies"):
        studies = "present"
    elif evidence.get("status") == "detected":
        studies = "present"
    elif evidence.get("status") == "unclear":
        studies = "uncertain"
    elif data.get("further_studies_section_seen"):
        studies = "missing"
    elif evidence.get("status") == "not_detected":
        studies = "absent"
    else:
        studies = "missing"
    salary_state = str(data.get("salary_state") or "absent")
    if salary_state not in {"present", "missing", "uncertain", "absent"}:
        salary_state = "uncertain"
    return {
        "name": name,
        "education": education,
        "employment": employment,
        "skills": skill_state,
        "further_studies": studies,
        "salary": salary_state,
    }


def needs_deeper_extraction(assessment: dict[str, str]) -> bool:
    return any(state in {"missing", "uncertain", "low_confidence"} for state in assessment.values())


def heuristic_is_sufficient(data: dict[str, Any]) -> bool:
    return not needs_deeper_extraction(assess_extraction(data))
