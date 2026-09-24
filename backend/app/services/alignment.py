"""PSOC/SOC matching and degree-to-career alignment."""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models import JobTitleMapping, SocCode
from app.services.parser_course import align_occupation_to_degree

_soc_cache: list[tuple[str, str, str, str, str]] | None = None


def invalidate_soc_cache() -> None:
    global _soc_cache
    _soc_cache = None


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _soc_rows(db: Session) -> list[tuple[str, str, str, str, str]]:
    global _soc_cache
    if _soc_cache is None:
        _soc_cache = [
            (
                row.soc_code,
                row.description or "",
                row.title_patterns or "",
                row.degree_patterns or "",
                row.category or "",
            )
            for row in db.query(SocCode).all()
        ]
    return _soc_cache


def get_soc_match(db: Session, job_title: str) -> Optional[SocCode]:
    if not job_title:
        return None

    job_title_lower = job_title.strip().lower()
    mapping = (
        db.query(JobTitleMapping)
        .filter(JobTitleMapping.normalized_title == job_title_lower, JobTitleMapping.approved.is_(True))
        .first()
    )
    if mapping and mapping.soc_code:
        return db.get(SocCode, mapping.soc_code)

    job_tokens = _tokenize(job_title_lower)
    if not job_tokens:
        return None

    best_code: Optional[str] = None
    best_score = -1
    for soc_code, description, title_patterns, _degree_patterns, _category in _soc_rows(db):
        patterns = [p.strip().lower() for p in title_patterns.split(",") if p.strip()]
        if not patterns:
            patterns = [description.lower()]
        row_score = 0
        for pattern in patterns:
            pat_tokens = _tokenize(pattern)
            if not pat_tokens:
                continue
            if pattern == job_title_lower:
                row_score = max(row_score, 100)
                continue
            if pat_tokens.issubset(job_tokens):
                row_score = max(row_score, 90)
                continue
            overlap = len(job_tokens.intersection(pat_tokens))
            if overlap >= 2:
                row_score = max(row_score, 70 + overlap)
            elif overlap == 1 and len(pat_tokens) == 1:
                row_score = max(row_score, 55)
        if row_score > best_score:
            best_score = row_score
            best_code = soc_code

    if best_code and best_score >= 70:
        return db.get(SocCode, best_code)
    return None


def analyze_career_alignment(
    db: Session,
    extracted_job: str,
    user_degree: str,
    job_context: str = "",
) -> tuple[str, str, Optional[SocCode], list[str]]:
    job_query = (extracted_job or "").strip()
    degree_query = (user_degree or "").strip().lower()
    if not job_query:
        return "Unknown", "No job title was provided for alignment.", None, []

    record = get_soc_match(db, job_query)
    suggestions: list[str] = []
    if record:
        degree_patterns = [d.strip().lower() for d in (record.degree_patterns or "").split(",") if d.strip()]
        related_roles = [p.strip() for p in (record.title_patterns or "").split(",") if p.strip()][:6]
        suggestions = related_roles or [record.description]
        if not degree_patterns:
            return (
                "Unknown",
                (
                    f"The role “{job_query}” maps to PSOC {record.soc_code} ({record.description}), "
                    "but no degree pathways are configured for this occupation yet."
                ),
                record,
                suggestions,
            )
        degree_matches = any(pattern in degree_query for pattern in degree_patterns)
        if degree_matches:
            return (
                "Aligned",
                f"The role “{job_query}” maps to PSOC {record.soc_code} ({record.description}), which matches {user_degree or 'the recorded degree'}.",
                record,
                suggestions,
            )
        return (
            "Misaligned",
            f"The role “{job_query}” maps to PSOC {record.soc_code} ({record.description}), which is outside the typical pathways for {user_degree or 'this degree'}.",
            record,
            suggestions,
        )

    course = align_occupation_to_degree(user_degree, job_query, description=job_context)
    if course.status in {"Aligned", "Misaligned"}:
        return course.status, course.detail, None, course.suggestions
    return "Unknown", "No matching PSOC/SOC career path was found for this job title.", None, []


def alignment_score(status: str) -> int:
    """Legacy status encoding stored in the database. Not a similarity percentage."""
    return {"Aligned": 100, "Unknown": 50, "Misaligned": 0}.get(status, 50)
