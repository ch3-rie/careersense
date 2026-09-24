"""Degree-to-occupation alignment used by the resume parser.

Maps a bachelor's degree to a professional domain, then scores the
*current* job (title, responsibilities, employer, skills) against that
domain. This is independent of PSOC/SOC matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

AMBIGUOUS_TITLE_TOKENS = {
    "analyst", "coordinator", "specialist", "officer", "consultant",
    "associate", "manager", "assistant", "staff", "representative",
    "executive", "lead", "head", "intern", "trainee", "member",
}

GENERIC_TITLE_STOP = {
    "the", "and", "of", "for", "in", "to", "a", "an", "jr", "sr", "i", "ii", "iii",
}

DOMAINS: dict[str, dict[str, tuple[str, ...]]] = {
    "computing": {
        "degree": (
            "information technology", "computer science", "information systems",
            "software engineering", "computer engineering", "information and communications",
            "bsit", "bscs", "bsis", "bsse", "bsceit", "it", "computing", "informatics",
        ),
        "occupations": (
            "software developer", "software engineer", "web developer", "web designer",
            "frontend developer", "backend developer", "full stack developer", "fullstack developer",
            "programmer", "systems analyst", "system analyst", "business analyst",
            "it support", "it specialist", "it officer", "technical support",
            "network administrator", "network engineer", "systems administrator", "system administrator",
            "database administrator", "database developer", "qa engineer", "quality assurance",
            "software tester", "test engineer", "cybersecurity analyst", "security analyst",
            "cloud engineer", "devops engineer", "data analyst", "data engineer", "data scientist",
            "it project coordinator", "it project manager",
            "help desk", "helpdesk", "information technology", "application developer",
            "mobile developer", "machine learning", "ai engineer", "site reliability",
            "solutions architect", "technical analyst", "programmer analyst",
        ),
        "duties": (
            "web application", "software development", "software testing", "wrote code",
            "developed software", "developed web", "maintained databases", "database",
            "configured network", "network infrastructure", "cloud services", "cloud",
            "system requirements", "process models", "rest api", "api", "deployed",
            "debugging", "programming", "information system", "servers", "cybersecurity",
            "automated", "ci/cd", "front-end", "back-end",
        ),
        "employer": (
            "software", "technology", "technologies", "systems", "digital", "tech",
            "information technology", "it services", "cloud",
        ),
        "skills": (
            "python", "javascript", "java", "php", "sql", "react", "node", "html",
            "css", "git", "docker", "aws", "linux", "c++", "c#", "typescript",
        ),
    },
    "business": {
        "degree": (
            "business administration", "bsba", "management", "marketing", "entrepreneurship",
            "office administration", "business management",
        ),
        "occupations": (
            "marketing specialist", "marketing officer", "marketing coordinator",
            "sales associate", "sales executive", "sales manager", "business development",
            "operations manager", "operations officer", "entrepreneur", "business owner",
            "human resources officer", "hr officer", "hr specialist", "human resource",
            "administrative assistant", "office administrator", "account executive",
            "brand manager", "product manager",
        ),
        "duties": (
            "marketing campaign", "sales target", "customer acquisition", "brand",
            "human resources", "recruitment", "payroll", "operations",
        ),
        "employer": ("marketing", "retail", "sales", "consulting", "bpo"),
        "skills": ("excel", "powerpoint", "crm", "salesforce"),
    },
    "accountancy": {
        "degree": (
            "accountancy", "accounting", "bsa", "internal audit", "financial management",
        ),
        "occupations": (
            "accountant", "auditor", "bookkeeper", "tax associate", "tax analyst",
            "accounts payable", "accounts receivable", "financial analyst",
            "audit associate", "accounting staff", "controller", "cpa",
        ),
        "duties": (
            "financial statements", "audit", "bookkeeping", "tax return", "accounts payable",
            "reconciliation", "general ledger",
        ),
        "employer": ("audit", "accounting", "cpa", "bank", "finance"),
        "skills": ("excel", "quickbooks", "sap", "taxation"),
    },
    "nursing": {
        "degree": ("nursing", "bsn", "midwifery"),
        "occupations": (
            "registered nurse", "staff nurse", "nurse", "clinical nurse",
            "nursing attendant", "midwife",
        ),
        "duties": (
            "patient care", "vital signs", "clinical", "medication administration",
            "ward", "nursing",
        ),
        "employer": ("hospital", "clinic", "medical center", "health"),
        "skills": ("bls", "acls", "patient care"),
    },
    "education": {
        "degree": (
            "education", "elementary education", "secondary education", "beed", "bsed",
            "teaching",
        ),
        "occupations": (
            "elementary teacher", "teacher", "instructor", "educator", "professor",
            "high school teacher", "subject teacher", "preschool teacher",
        ),
        "duties": ("lesson plan", "classroom", "taught", "instruction", "students"),
        "employer": ("school", "university", "college", "academy"),
        "skills": ("classroom management", "lesson planning"),
    },
    "psychology": {
        "degree": ("psychology", "guidance and counseling"),
        "occupations": (
            "psychologist", "guidance counselor", "behavioral therapist", "psychometrician",
            "hr specialist",
        ),
        "duties": ("counseling", "assessment", "behavioral", "psychometric"),
        "employer": ("clinic", "school", "hr"),
        "skills": ("counseling", "assessment"),
    },
    "hospitality": {
        "degree": (
            "hospitality", "hotel and restaurant", "tourism", "hrm", "hospitality management",
        ),
        "occupations": (
            "restaurant crew", "waiter", "waitress", "bartender", "chef", "cook",
            "hotel staff", "front desk", "housekeeping", "food and beverage",
            "restaurant manager", "hotel supervisor",
        ),
        "duties": ("guest service", "food preparation", "front desk", "housekeeping"),
        "employer": ("hotel", "restaurant", "resort", "cafe"),
        "skills": ("customer service", "food safety"),
    },
    "engineering": {
        "degree": (
            "civil engineering", "electrical engineering", "mechanical engineering",
            "electronics engineering", "chemical engineering", "industrial engineering",
            "engineering", "bsce", "bsee", "bsme",
        ),
        "occupations": (
            "civil engineer", "electrical engineer", "mechanical engineer",
            "electronics engineer", "industrial engineer", "project engineer",
            "site engineer", "structural engineer",
        ),
        "duties": (
            "construction", "structural", "site inspection", "cad", "blueprints",
            "electrical system", "mechanical system",
        ),
        "employer": ("construction", "engineering", "contractor"),
        "skills": ("autocad", "staad", "matlab"),
    },
}

# Occupations that are unrelated to computing unless the description says otherwise.
CLEAR_NON_COMPUTING = {
    "accountant", "auditor", "registered nurse", "staff nurse", "nurse",
    "elementary teacher", "teacher", "sales associate", "restaurant crew",
    "human resources officer", "waiter", "waitress", "cashier", "bartender",
}


@dataclass
class CourseAlignment:
    status: str
    confidence: float
    related_to_degree: str
    detail: str = ""
    domain: str = ""
    suggestions: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", _normalize(text)))


def _contains_phrase(haystack: str, phrase: str) -> bool:
    if not phrase:
        return False
    tokens = [re.escape(token) + r"s?" for token in phrase.split()]
    pattern = rf"(?<![a-z0-9]){' '.join(tokens)}(?![a-z0-9])"
    return bool(re.search(pattern, haystack))


def _has_degree_pattern(blob: str, pattern: str) -> bool:
    if not pattern:
        return False
    if " " in pattern or len(pattern) >= 4:
        return pattern in blob
    return bool(re.search(rf"\b{re.escape(pattern)}\b", blob))


def degree_domains(degree: str) -> list[str]:
    blob = _normalize(degree)
    if not blob:
        return []
    matched = []
    for key, spec in DOMAINS.items():
        if any(_has_degree_pattern(blob, pattern) for pattern in spec["degree"]):
            matched.append(key)
    if "computing" in matched and "engineering" in matched and "computer engineering" not in blob:
        if not re.search(r"computer|software|information", blob):
            matched = [key for key in matched if key != "computing"]
    if "engineering" in matched and re.search(r"computer|software|information technology", blob):
        matched = [key for key in matched if key != "engineering"] or matched
    return matched


def _title_is_ambiguous(title: str) -> bool:
    tokens = [token for token in _tokens(title) if token not in GENERIC_TITLE_STOP]
    if not tokens:
        return True
    return set(tokens).issubset(AMBIGUOUS_TITLE_TOKENS)


def _domain_title_score(title: str, spec: dict[str, tuple[str, ...]]) -> float:
    blob = _normalize(title)
    if not blob:
        return 0.0
    best = 0.0
    for phrase in spec["occupations"]:
        if _contains_phrase(blob, phrase) or blob == phrase:
            best = max(best, 0.92 if len(phrase.split()) >= 2 or phrase in blob else 0.88)
            continue
        phrase_tokens = _tokens(phrase)
        title_tokens = _tokens(blob)
        if not phrase_tokens:
            continue
        overlap = phrase_tokens & title_tokens
        if phrase_tokens.issubset(title_tokens) and len(phrase_tokens) >= 2:
            best = max(best, 0.9)
        elif overlap and len(overlap) / len(phrase_tokens) >= 0.7 and len(overlap) >= 2:
            best = max(best, 0.78)
        elif overlap == phrase_tokens and len(phrase_tokens) == 1 and phrase not in AMBIGUOUS_TITLE_TOKENS:
            best = max(best, 0.72)
    return best


def _phrase_score(text: str, phrases: Sequence[str], hit: float, cap: float) -> float:
    blob = _normalize(text)
    if not blob:
        return 0.0
    score = 0.0
    for phrase in phrases:
        if _contains_phrase(blob, phrase) or phrase in blob:
            score += hit
            if score >= cap:
                return cap
    return min(cap, score)


def _score_domain(
    spec: dict[str, tuple[str, ...]],
    title: str,
    description: str,
    employer: str,
    skills: Iterable[str],
) -> float:
    title_score = _domain_title_score(title, spec)
    duty_score = _phrase_score(description, spec["duties"], 0.2, 0.5)
    employer_score = _phrase_score(employer, spec["employer"], 0.08, 0.16)
    skill_blob = " ".join(str(item) for item in skills)
    skill_score = _phrase_score(skill_blob, spec["skills"], 0.04, 0.12)
    if title_score >= 0.85:
        return min(0.98, title_score + 0.3 * duty_score)
    if _title_is_ambiguous(title):
        return min(0.9, 0.2 + duty_score + employer_score + skill_score)
    if title_score >= 0.7:
        return min(0.95, title_score + 0.5 * duty_score + 0.3 * employer_score)
    return min(0.7, title_score + duty_score + employer_score + 0.5 * skill_score)


def align_occupation_to_degree(
    degree: str,
    job_title: str,
    *,
    description: str = "",
    employer: str = "",
    skills: Iterable[str] | None = None,
    previous_titles: Iterable[str] | None = None,
) -> CourseAlignment:
    """Score whether a specific occupation belongs with the bachelor's degree."""
    title = (job_title or "").strip()
    degree_text = (degree or "").strip()
    if not title or not degree_text:
        return CourseAlignment("Unknown", 0.2, "", "Not enough information to compare the job with the degree.")

    domains = degree_domains(degree_text)
    skill_list = [str(item) for item in (skills or []) if str(item).strip()]
    description = description or ""
    employer = employer or ""

    domain_scores = {
        key: _score_domain(spec, title, description, employer, skill_list)
        for key, spec in DOMAINS.items()
    }
    own_score = max((domain_scores[key] for key in domains), default=0.0)
    own_domain = max(domains, key=lambda key: domain_scores[key]) if domains else ""
    other_keys = [key for key in DOMAINS if key not in domains]
    other_score = max((domain_scores[key] for key in other_keys), default=0.0)
    other_domain = max(other_keys, key=lambda key: domain_scores[key]) if other_keys else ""

    previous = [str(item) for item in (previous_titles or []) if str(item).strip()]
    if previous and own_score >= 0.45:
        prior_bonus = 0.0
        for prior in previous:
            prior_bonus = max(
                prior_bonus,
                max((_score_domain(DOMAINS[key], prior, "", "", []) for key in domains), default=0.0),
            )
        if prior_bonus >= 0.7:
            own_score = min(0.95, own_score + 0.04)

    suggestions = list(DOMAINS.get(own_domain, {}).get("occupations", ()))[:6]

    if own_score >= 0.6 and own_score >= other_score - 0.05:
        confidence = round(min(0.98, own_score), 2)
        return CourseAlignment(
            "Aligned",
            confidence,
            "Yes",
            f"The current role “{title}” fits the {degree_text} professional domain.",
            own_domain,
            suggestions,
        )

    clearly_other = other_score >= 0.7 and own_score < 0.45
    computing_mismatch = (
        "computing" in domains
        and any(_contains_phrase(_normalize(title), phrase) or _normalize(title) == phrase for phrase in CLEAR_NON_COMPUTING)
    )
    if clearly_other or computing_mismatch:
        confidence = round(min(0.96, max(other_score, 0.8 if computing_mismatch else 0.7)), 2)
        return CourseAlignment(
            "Misaligned",
            confidence,
            "No",
            f"The current role “{title}” is outside the typical pathways for {degree_text}.",
            other_domain,
            suggestions,
        )

    if _title_is_ambiguous(title) and own_score < 0.6:
        return CourseAlignment(
            "Unknown",
            0.42,
            "",
            f"The current title “{title}” is too generic to classify without stronger evidence.",
            own_domain,
            suggestions,
        )

    return CourseAlignment(
        "Unknown",
        0.4,
        "",
        "There is not enough evidence to decide whether the current role matches the degree.",
        own_domain,
        suggestions,
    )


def related_yes_no(
    degree: str,
    job_title: str,
    *,
    description: str = "",
    employer: str = "",
    skills: Iterable[str] | None = None,
) -> str:
    return align_occupation_to_degree(
        degree,
        job_title,
        description=description,
        employer=employer,
        skills=skills,
    ).related_to_degree


def select_current_experience(experiences: Sequence[dict]) -> dict:
    """Return the current job; do not fall back to the newest historical role."""
    current = [row for row in experiences if str(row.get("is_current") or "").lower() in {"yes", "true"}]
    if not current:
        return {}
    def rank(row: dict) -> tuple:
        match = re.search(r"((19|20)\d{2})(?:[-/](\d{1,2}))?", str(row.get("start_date") or ""))
        if not match:
            return (0, 0)
        return (int(match.group(1)), int(match.group(3) or 1))
    return sorted(current, key=rank)[-1]
