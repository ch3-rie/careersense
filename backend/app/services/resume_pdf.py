"""Profile-based resume PDF for the alumni Export Resume page.

Saved profile records are the authority. Uploaded resumes contribute only
details that were already extracted for that account and are not already
confirmed on the profile.
"""

from __future__ import annotations

import re
from typing import Any

import fitz

from app.services.parser_document import DocumentView
from app.services.parser_extract import (
    SECTION_ALIASES,
    classify_sections,
    further_study_level,
    lines_from_document,
    parse_date_range,
)

NAVY = (11 / 255, 46 / 255, 89 / 255)
GOLD = (181 / 255, 138 / 255, 58 / 255)
RULE = (0.847, 0.863, 0.91)
INK = (0.16, 0.18, 0.22)
MUTED = (0.33, 0.36, 0.42)
PAGE_W = 595
PAGE_H = 842
MARGIN_X = 48
MARGIN_BOTTOM = 46
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_UNUSABLE_SOURCES = {"failed", "empty"}
_SUMMARY_KEYS = ("professional_summary", "summary", "objective", "profile_summary")
_YES = {"yes", "true", "1"}
_NO = {"no", "false", "0"}
_PRESENT = {"present", "current", "now", "ongoing"}
_SECTION_WORDS = re.compile(
    r"\b(?:languages?|profile|summary|objective|experience|education|skills|certifications?|projects|tools)\b",
    re.I,
)
_EXTRA_HEADINGS = (
    ("professional summary", "profile"),
    ("professional profile", "profile"),
    ("profile", "profile"),
    ("summary", "profile"),
    ("objective", "profile"),
    ("languages", "languages"),
    ("language", "languages"),
    ("contact information", "contact"),
    ("contact", "contact"),
)
_HEADING_ALIASES = sorted(
    [(name.lower(), key) for key, names in SECTION_ALIASES.items() for name in names]
    + list(_EXTRA_HEADINGS),
    key=lambda item: len(item[0]),
    reverse=True,
)
_LANGUAGE_LEVEL = (
    r"(?:native|professional|fluent|intermediate|beginner|advanced|basic|conversational|elementary|limited)"
)
_LANGUAGE_LABELS = {
    "english",
    "filipino",
    "tagalog",
    "cebuano",
    "spanish",
    "chinese",
    "japanese",
    "korean",
    "native",
    "professional",
    "fluent",
    "intermediate",
    "beginner",
    "advanced",
    "basic",
    "bilingual",
}


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _text(value: Any) -> str:
    return _plain(value).replace("\u2013", "-").replace("\u2014", "-").encode("latin-1", "replace").decode("latin-1")


def _norm(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _plain(value).lower()).split())


def _loose_same(left: Any, right: Any, minimum: int = 8) -> bool:
    a, b = _norm(left), _norm(right)
    if a == b:
        return bool(a)
    if not a or not b:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= minimum and short in long


def _month_year(value: Any) -> str:
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})", text)
    if match:
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{MONTHS[month - 1]} {match.group(1)}"
    if re.fullmatch(r"\d{4}", text):
        return text
    return _text(text)


def _join(parts: list[str], sep: str = " | ") -> str:
    return sep.join(part for part in (_text(item) for item in parts) if part)


def _clip(value: str, limit: int = 240) -> str:
    text = _plain(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _is_yes(value: Any) -> bool:
    return value is True or _plain(value).lower() in _YES


def _current_flag(row: dict) -> bool:
    end = _plain(row.get("end_date")).lower()
    if end in _PRESENT:
        return True
    return _is_yes(row.get("is_current"))


def _graduated(value: Any) -> bool | None:
    if value is True:
        return True
    if value is False:
        return False
    text = _plain(value).lower()
    if text in _YES:
        return True
    if text in _NO:
        return False
    return None


class _ResumeDoc:
    def __init__(self) -> None:
        self.doc = fitz.open()
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = 0.0
        self._paint_banner()

    def _paint_banner(self) -> None:
        self.page.draw_rect(fitz.Rect(0, 0, PAGE_W, 8), color=NAVY, fill=NAVY, width=0)
        self.y = 36

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self._paint_banner()

    def _width(self) -> float:
        return PAGE_W - (MARGIN_X * 2)

    def _pieces(self, word: str, font: str, size: float, limit: float) -> list[str]:
        if fitz.get_text_length(word, fontname=font, fontsize=size) <= limit or len(word) <= 1:
            return [word]
        parts: list[str] = []
        chunk = ""
        for char in word:
            trial = f"{chunk}{char}"
            if chunk and fitz.get_text_length(trial, fontname=font, fontsize=size) > limit:
                parts.append(chunk)
                chunk = char
            else:
                chunk = trial
        if chunk:
            parts.append(chunk)
        return parts

    def _wrap(self, text: str, font: str, size: float, width: float | None = None) -> list[str]:
        words = _text(text).split(" ")
        if not words or words == [""]:
            return []
        lines: list[str] = []
        current = ""
        limit = self._width() if width is None else width
        for word in words:
            for piece in self._pieces(word, font, size, limit):
                trial = piece if not current else f"{current} {piece}"
                if fitz.get_text_length(trial, fontname=font, fontsize=size) <= limit:
                    current = trial
                else:
                    if current:
                        lines.append(current)
                    current = piece
        if current:
            lines.append(current)
        return lines

    def _ensure(self, height: float) -> None:
        if self.y + height > PAGE_H - MARGIN_BOTTOM:
            self._new_page()

    def _line(
        self,
        text: str,
        *,
        size: float,
        font: str,
        color: tuple[float, float, float],
        gap: float = 3,
        align: str = "left",
        width: float | None = None,
        x: float | None = None,
    ) -> None:
        clean = _text(text)
        if not clean:
            return
        origin = MARGIN_X if x is None else x
        limit = self._width() if width is None else width
        for line in self._wrap(clean, font, size, limit):
            self._ensure(size + gap + 2)
            line_x = origin
            if align == "center":
                line_width = fitz.get_text_length(line, fontname=font, fontsize=size)
                line_x = MARGIN_X + max(0, (self._width() - line_width) / 2)
            self.page.insert_text((line_x, self.y + size), line, fontsize=size, fontname=font, color=color)
            self.y += size + gap

    def heading(self, name: str, contact: str, *, centered: bool = False, rule: tuple[float, float, float] = GOLD) -> None:
        align = "center" if centered else "left"
        self._line(name or "Alumni", size=22, font="tibo", color=NAVY, gap=6, align=align)
        if contact:
            self._line(contact, size=10, font="helv", color=MUTED, gap=8, align=align)
        self._ensure(10)
        rule_y = self.y + 2
        self.page.draw_line(
            fitz.Point(MARGIN_X, rule_y),
            fitz.Point(PAGE_W - MARGIN_X, rule_y),
            color=rule,
            width=1.2,
        )
        self.y = rule_y + 16

    def section(self, title: str, *, rule: tuple[float, float, float] = GOLD) -> None:
        self._ensure(78)
        self.y += 8
        self._line(title.upper(), size=11, font="hebo", color=NAVY, gap=4)
        self._ensure(8)
        rule_y = self.y
        self.page.draw_line(
            fitz.Point(MARGIN_X, rule_y),
            fitz.Point(PAGE_W - MARGIN_X, rule_y),
            color=rule,
            width=0.6,
        )
        self.y = rule_y + 12

    def body(self, text: str) -> None:
        self._line(text, size=10.5, font="helv", color=INK, gap=3)

    def bullets(self, lines: list[str]) -> None:
        size = 10.5
        gap = 3
        indent = 14
        for item in lines:
            clean = _text(item)
            if not clean:
                continue
            wrapped = self._wrap(clean, "helv", size, self._width() - indent)
            for index, line in enumerate(wrapped):
                self._ensure(size + gap + 2)
                if index == 0:
                    self.page.draw_circle(fitz.Point(MARGIN_X + 3, self.y + size - 3), 1.15, color=INK, fill=INK, width=0)
                self.page.insert_text((MARGIN_X + indent, self.y + size), line, fontsize=size, fontname="helv", color=INK)
                self.y += size + gap

    def muted(self, text: str) -> None:
        self._line(text, size=10, font="heit", color=MUTED, gap=2)

    def strong(self, text: str) -> None:
        self._line(text, size=11.5, font="hebo", color=INK, gap=2)

    def spacer(self, amount: float = 8) -> None:
        self.y += amount

    def note(self, text: str) -> None:
        self._line(text, size=10, font="heit", color=MUTED, gap=3)

    def bytes(self) -> bytes:
        payload = self.doc.tobytes()
        self.doc.close()
        return payload


def _contact_line(profile: dict[str, Any], *, sep: str = " | ") -> str:
    address = _join(
        [profile.get("address") or "", profile.get("city") or "", profile.get("country") or ""],
        ", ",
    )
    return _join([profile.get("phone") or "", profile.get("email") or "", address], sep)


def _block_text(value: Any) -> str:
    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [_text(line) for line in raw.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(line for line in lines if line)


def _write_detail(doc: _ResumeDoc, value: Any, *, bullets: bool = False) -> None:
    block = _block_text(value)
    lines = [line for line in block.split("\n") if line]
    if not lines:
        return
    if bullets and len(lines) > 1:
        doc.bullets(lines)
        return
    doc.body(" ".join(lines))


def _pair_entries(rows: list) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        program = _text(row.get("program") or row.get("title") or row.get("name"))
        institution = _text(row.get("institution"))
        detail = _text(row.get("detail"))
        heading = program or institution or detail
        if not heading:
            continue
        meta = _join([institution if program else "", detail if heading != detail else ""])
        entries.append((heading, meta))
    return entries


def _education_entries(profile: dict[str, Any]) -> list[tuple[str, str]]:
    custom = profile.get("education_entries")
    if isinstance(custom, list):
        return _pair_entries(custom)
    entries: list[tuple[str, str]] = []
    degree = _text(profile.get("degree"))
    college = _text(profile.get("college"))
    year = _text(profile.get("year_graduated"))
    if degree or college or year:
        heading = degree or college or f"Class of {year}"
        detail = _join([
            college if degree else "",
            f"Graduated {year}" if year and heading != f"Class of {year}" else "",
        ])
        entries.append((heading, detail))
    for study in profile.get("studies") or []:
        if not isinstance(study, dict):
            continue
        title = _text(study.get("course_degree"))
        school = _text(study.get("school"))
        enrolled = _text(study.get("year_enrolled"))
        address = _text(study.get("institution_address"))
        scholarship = _text(study.get("scholarship"))
        completed = _text(study.get("year_completed"))
        graduated = _graduated(study.get("is_graduated"))
        status = f"Graduated {completed}".strip() if graduated is True else ""
        if not any([title, school, enrolled, status, scholarship]):
            continue
        heading = title or school
        detail = _join([
            school if title else "",
            address,
            f"Enrolled {enrolled}" if enrolled else "",
            status,
            scholarship,
        ])
        entries.append((heading, detail))
    return entries


def _job_entries(profile: dict[str, Any]) -> list[dict[str, str]]:
    rows = [row for row in (profile.get("jobs") or []) if isinstance(row, dict)]
    if not profile.get("preserve_order"):
        rows.sort(key=lambda row: str(row.get("start_date") or ""), reverse=True)
        rows.sort(key=lambda row: 0 if row.get("is_current") else 1)
    prepared = []
    for row in rows:
        title = _text(row.get("job_title"))
        company = _text(row.get("company"))
        if not title and not company:
            continue
        start = _month_year(row.get("start_date"))
        end = "Present" if row.get("is_current") else _month_year(row.get("end_date"))
        dates = _text(row.get("dates")) or _join([start, end] if start or end else [], " - ")
        if profile.get("document_layout"):
            meta = _join([dates, _text(row.get("location"))], " · ")
            description = _block_text(row.get("description"))
        else:
            meta = _join([dates, row.get("duration") or "", row.get("location") or "", row.get("industry") or ""])
            description = _text(row.get("description"))
        prepared.append({
            "title": title or company,
            "company": company if title else "",
            "meta": meta,
            "description": description,
        })
    return prepared


def _skill_list(profile: dict[str, Any]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for item in profile.get("skills") or []:
        text = _text(item)
        key = _norm(item)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        skills.append(text)
    return skills


def _named_rows(profile: dict[str, Any], key: str, label: str) -> list[dict]:
    rows = []
    for row in profile.get(key) or []:
        if isinstance(row, dict) and _text(row.get(label)):
            rows.append(row)
    return rows


def _project_lines(profile: dict[str, Any]) -> list[str]:
    lines = []
    seen: set[str] = set()
    for item in profile.get("projects") or []:
        text = _text(item)
        key = _norm(item)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        lines.append(text)
    return lines


def _string_list(value: Any, *, limit: int = 60) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,;|]", value)
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            item = item.get("name") or item.get("skill") or ""
        text = _plain(item)
        key = _norm(text)
        if not text or not key or key in seen or len(text) > limit or len(text.split()) > 6:
            continue
        if not re.search(r"[A-Za-z]", text):
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _extend_unique(target: list[str], values: list[str]) -> None:
    seen = {_norm(item) for item in target}
    for value in values:
        key = _norm(value)
        if not key or key in seen:
            continue
        seen.add(key)
        target.append(value)


def _copy_job(row: dict) -> dict:
    return {
        "job_title": _plain(row.get("job_title")),
        "company": _plain(row.get("company")),
        "start_date": row.get("start_date") or "",
        "end_date": row.get("end_date") or "",
        "is_current": bool(row.get("is_current")),
        "location": _plain(row.get("location")),
        "industry": _plain(row.get("industry")),
        "duration": _plain(row.get("duration")),
        "description": _plain(row.get("description")),
    }


def _copy_study(row: dict) -> dict:
    return {
        "course_degree": _plain(row.get("course_degree")),
        "school": _plain(row.get("school")),
        "institution_address": _plain(row.get("institution_address")),
        "year_enrolled": _plain(row.get("year_enrolled")),
        "year_completed": _plain(row.get("year_completed")),
        "scholarship": _plain(row.get("scholarship")),
        "is_graduated": row.get("is_graduated"),
    }


def _jobs_match(saved: dict, extracted: dict) -> bool:
    extracted_title = extracted.get("job_title") or extracted.get("title")
    extracted_company = extracted.get("employer") or extracted.get("company")
    if not _loose_same(saved.get("job_title"), extracted_title, minimum=4):
        return False
    return _loose_same(saved.get("company"), extracted_company, minimum=6)


def _studies_match(saved: dict, course: str, school: str) -> bool:
    if not _loose_same(saved.get("course_degree"), course, minimum=8):
        return False
    saved_school = _norm(saved.get("school"))
    extracted_school = _norm(school)
    if not saved_school or not extracted_school:
        return True
    return _loose_same(saved_school, extracted_school, minimum=6)


def _usable_uploads(uploads: list[dict] | None) -> list[dict]:
    usable = []
    for item in uploads or []:
        if not isinstance(item, dict):
            continue
        source = _plain(item.get("parser_source")).lower()
        if source in _UNUSABLE_SOURCES:
            continue
        parsed = item.get("parsed") if isinstance(item.get("parsed"), dict) else {}
        text = item.get("text") if isinstance(item.get("text"), str) else ""
        if not parsed and not text.strip():
            continue
        usable.append({"parsed": parsed, "text": text})
    return usable


def _reliable_label(value: Any, *, max_len: int, max_words: int) -> str:
    """Keep a short extracted label. Paragraphs and section headings are not resume fields."""
    text = _plain(value)
    if not text or len(text) > max_len or len(text.split()) > max_words:
        return ""
    if not re.search(r"[A-Za-z]", text) or _SECTION_WORDS.search(text):
        return ""
    return text


def _reliable_year(value: Any) -> str:
    text = _plain(value)
    return text if re.fullmatch(r"(?:19|20)\d{2}", text) else ""


def _reliable_degree(value: Any) -> str:
    text = _reliable_label(value, max_len=120, max_words=14)
    if not text:
        return ""
    if further_study_level(text):
        return text
    if re.search(r"\b(?:bachelor|master|doctor|phd|ph\.d|diploma|associate|bs|ba|b\.s|m\.s|mba)\b", text, re.I):
        return text
    return ""


def _reliable_title(value: Any) -> str:
    return _reliable_label(value, max_len=80, max_words=12)


def _reliable_employer(value: Any) -> str:
    text = _reliable_label(value, max_len=80, max_words=12)
    if _norm(text) in _LANGUAGE_LABELS:
        return ""
    return text


def _reliable_description(value: Any) -> str:
    text = _plain(value)[:2000]
    if not text or len(_SECTION_WORDS.findall(text)) >= 2:
        return ""
    return text


def _entry_line(value: str) -> str:
    text = _plain(value)
    if len(text) < 3 or len(text) > 180 or len(text.split()) > 16 or "@" in text:
        return ""
    if not re.search(r"[A-Za-z]", text) or len(_SECTION_WORDS.findall(text)) >= 2:
        return ""
    digits = re.sub(r"\D", "", text)
    compact = re.sub(r"\s", "", text)
    if compact and len(digits) >= 10 and len(digits) >= len(compact) * 0.6:
        return ""
    return text


def _document_sections(text: str) -> dict[str, list[str]]:
    if not text.strip():
        return {}
    view = DocumentView.from_text(text)
    return classify_sections(lines_from_document(view))


def _separate_headings(text: str) -> str:
    """Put inline resume headings on their own lines so section text can be read."""
    hits: list[tuple[int, int]] = []
    occupied: list[tuple[int, int]] = []
    lower = text.lower()
    for alias, _key in _HEADING_ALIASES:
        start = 0
        while True:
            idx = lower.find(alias, start)
            if idx < 0:
                break
            end = idx + len(alias)
            before = idx == 0 or not lower[idx - 1].isalnum()
            after = end == len(lower) or not lower[end].isalnum()
            raw = text[idx:end]
            overlap = any(not (end <= left or idx >= right) for left, right in occupied)
            if before and after and (raw.isupper() or raw.istitle()) and not overlap:
                hits.append((idx, end))
                occupied.append((idx, end))
            start = idx + 1
    if not hits:
        return text
    hits.sort()
    pieces: list[str] = []
    cursor = 0
    for start, end in hits:
        pieces.append(text[cursor:start].strip())
        pieces.append("\n" + text[start:end].strip() + "\n")
        cursor = end
    pieces.append(text[cursor:].strip())
    return re.sub(r"\n{2,}", "\n", "\n".join(piece for piece in pieces if piece)).strip()


def _line_heading(line: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", " ", line.strip().lower()).strip()
    for alias, key in _HEADING_ALIASES:
        if compact == alias:
            return key
    return ""


def _walk_sections(text: str) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    current = ""
    for raw in _separate_headings(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        key = _line_heading(line)
        if key:
            current = key
            continue
        if current and current != "contact":
            buckets.setdefault(current, []).append(line.strip(" |"))
    return buckets


def _pipe_job(line: str) -> dict[str, str] | None:
    if "|" not in line:
        return None
    parts = [part.strip(" -") for part in line.split("|")]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return None
    duty = ""
    last = parts[-1]
    peeled = re.match(
        r"(?i)^((?:.*?(?:19|20)\d{2})(?:\s*[-–—]\s*(?:present|current|(?:19|20)\d{2}))?)\s+([A-Z].+)$",
        last,
    )
    if peeled and any(parse_date_range(peeled.group(1))):
        last = peeled.group(1).strip()
        duty = peeled.group(2).strip()
        parts[-1] = last
    start, end, current = parse_date_range(last)
    if not any((start, end, current)):
        return None
    title = parts[0]
    employer = parts[1] if len(parts) >= 3 else ""
    location = ""
    if "," in employer:
        head, tail = [part.strip() for part in employer.rsplit(",", 1)]
        if head and tail and len(tail.split()) <= 4 and not re.search(r"\b(?:inc|corp|ltd|llc|co|cpas)\b", tail, re.I):
            employer, location = head, tail
    if not _reliable_title(title) or (employer and not _reliable_employer(employer)):
        return None
    return {
        "job_title": title,
        "employer": employer,
        "location": location,
        "start_date": start,
        "end_date": "" if current == "Yes" else end,
        "is_current": "Yes" if current == "Yes" else "No",
        "description": duty,
    }


def _split_job_entries(line: str) -> list[str]:
    parts = re.split(r"(?<=\.)\s+(?=[A-Z][^|\n]{2,80}\|)", line)
    return [part.strip() for part in parts if part.strip()]


def _jobs_from_section(lines: list[str]) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    expanded: list[str] = []
    for line in lines:
        expanded.extend(_split_job_entries(line))
    for line in expanded:
        parsed = _pipe_job(line)
        if parsed:
            if current:
                jobs.append(current)
            current = parsed
            continue
        if current is None:
            continue
        extra = _plain(line).strip(" |")
        if len(extra.split()) < 4 and not extra[:1] in "•-*":
            continue
        current["description"] = _plain(f"{current.get('description') or ''} {extra}")
    if current:
        jobs.append(current)
    return jobs


def _studies_from_section(lines: list[str]) -> list[dict[str, str]]:
    studies = []
    for line in lines:
        parts = [part.strip(" .") for part in re.split(r"\s*\|\s*", line) if part.strip(" .")]
        if not parts or not _reliable_degree(parts[0]):
            continue
        school = ""
        year = ""
        for part in parts[1:]:
            if _reliable_year(part):
                year = _reliable_year(part)
            elif not school:
                school = part
        studies.append({
            "course_degree": parts[0],
            "school": school,
            "year_graduated": year,
            "is_graduated": "Yes" if year else "",
        })
    return studies


def _skills_from_section(lines: list[str]) -> list[str]:
    found: list[str] = []
    for line in lines:
        if line.isupper() and len(line.split()) >= 3:
            continue
        if re.search(r"@|https?://|linkedin\.com|\bphilippines\b", line, re.I):
            continue
        chunks = re.split(r"\s*(?:&|,|;|\||·|•)\s*", line)
        _extend_unique(found, _string_list(chunks, limit=40))
    return found


def _language_line(line: str) -> str:
    text = _plain(line).strip(" |")
    if re.match(rf"^[A-Za-z][A-Za-z .'-]{{1,40}}\s*[-–—]\s*{_LANGUAGE_LEVEL}$", text, re.I):
        return text.replace("\u2013", "-").replace("\u2014", "-")
    return ""


def _projects_from_section(lines: list[str]) -> list[str]:
    projects: list[str] = []
    for line in lines:
        for piece in re.split(r"(?<=\.)\s+(?=[A-Z])", line):
            item = _entry_line(piece)
            if item:
                _extend_unique(projects, [item])
    return projects


def _profile_summary(lines: list[str]) -> str:
    text = _plain(" ".join(lines)).strip(" |")
    if 40 <= len(text) <= 700 and " " in text:
        return text
    return ""


def _extract_document(text: str) -> dict[str, Any]:
    sections = _walk_sections(text)
    return {
        "summary": _profile_summary(sections.get("profile") or []),
        "experiences": _jobs_from_section(sections.get("experience") or []),
        "studies": _studies_from_section(sections.get("education") or []) + _studies_from_section(sections.get("further_studies") or []),
        "skills": _skills_from_section(sections.get("skills") or []),
        "certifications": [
            _entry_line(line)
            for line in (sections.get("certifications") or [])
            if _entry_line(line) and not _language_line(line)
        ],
        "projects": _projects_from_section(sections.get("projects") or []),
        "languages": [line for line in (_language_line(item) for item in (sections.get("languages") or [])) if line],
    }


def _summary_text(parsed: dict) -> str:
    for key in _SUMMARY_KEYS:
        value = parsed.get(key)
        if not isinstance(value, str):
            continue
        text = _plain(value)
        if 40 <= len(text) <= 600 and " " in text and len(_SECTION_WORDS.findall(text)) < 2:
            return text
    return ""


def _add_study(merged: dict, course: str, school: str, enrolled: str, graduated: bool | None, completed: str) -> None:
    course = _plain(course)
    school = _plain(school)
    enrolled = _plain(enrolled)
    completed = _plain(completed)
    if not course and not school:
        return
    if course and _loose_same(merged.get("degree"), course, minimum=10):
        if completed and not _plain(merged.get("year_graduated")) and graduated is not False:
            merged["year_graduated"] = completed
        return
    if course and _plain(merged.get("degree")) and further_study_level(course) == "bachelor":
        return
    for study in merged["studies"]:
        if not _studies_match(study, course, school):
            continue
        if school and not _plain(study.get("school")):
            study["school"] = school
        if enrolled and not _plain(study.get("year_enrolled")):
            study["year_enrolled"] = enrolled
        if completed and not _plain(study.get("year_completed")) and graduated is True:
            study["year_completed"] = completed
        if study.get("is_graduated") is None and graduated is not None:
            study["is_graduated"] = graduated
        return
    merged["studies"].append({
        "course_degree": course,
        "school": school,
        "institution_address": "",
        "year_enrolled": enrolled,
        "year_completed": completed if graduated is True else "",
        "scholarship": "",
        "is_graduated": graduated,
    })


def _study_from_record(row: dict) -> tuple[str, str, str, bool | None, str]:
    course = _plain(row.get("course_degree") or row.get("degree"))
    school = _plain(row.get("school") or row.get("institution"))
    enrolled = _plain(row.get("year_enrolled"))
    completed = _plain(row.get("year_graduated") or row.get("year_completed"))
    graduated = _graduated(row.get("is_graduated"))
    if graduated is None and completed and not enrolled:
        graduated = True
    return course, school, enrolled, graduated, completed


def _remember_experience(merged: dict[str, Any], exp: dict) -> None:
    raw_title = _plain(exp.get("job_title"))
    raw_company = _plain(exp.get("employer") or exp.get("company"))
    title = _reliable_title(raw_title)
    company = _reliable_employer(raw_company)
    if not title or (raw_company and not company):
        return
    description = _reliable_description(exp.get("description"))
    matched = next((job for job in merged["jobs"] if _jobs_match(job, exp)), None)
    if matched is not None:
        if description and not _plain(matched.get("description")):
            matched["description"] = description
        if company and not _plain(matched.get("company")):
            matched["company"] = company
        location = _plain(exp.get("location"))
        if location and not _plain(matched.get("location")):
            matched["location"] = location
        return
    current = _current_flag(exp)
    merged["jobs"].append({
        "job_title": title,
        "company": company,
        "start_date": exp.get("start_date") or "",
        "end_date": "" if current else (exp.get("end_date") or ""),
        "is_current": current,
        "location": _plain(exp.get("location")),
        "industry": "",
        "duration": "",
        "description": description,
    })


def _supplement_from_text(merged: dict[str, Any], text: str) -> None:
    extracted = _extract_document(text)
    if extracted["summary"] and not merged["bio"]:
        merged["bio"] = extracted["summary"]
    for study in extracted["studies"]:
        course, school, enrolled, graduated, completed = _study_from_record(study)
        if course and not merged["degree"] and further_study_level(course) == "bachelor":
            merged["degree"] = course
            if completed and not merged["year_graduated"]:
                merged["year_graduated"] = completed
            if school and not merged["college"]:
                merged["college"] = school
            continue
        _add_study(merged, course, school, enrolled, graduated, completed)
    for exp in extracted["experiences"]:
        _remember_experience(merged, exp)
    _extend_unique(merged["skills"], extracted["skills"])
    for name in extracted["certifications"]:
        if any(_loose_same(existing.get("name"), name, minimum=8) for existing in merged["certifications"]):
            continue
        merged["certifications"].append({"name": name, "awarding_body": "", "awarded_on": ""})
    _extend_unique(merged["projects"], extracted["projects"])
    _extend_unique(merged["languages"], extracted["languages"])


def merge_resume_content(profile: dict[str, Any], uploads: list[dict] | None = None) -> dict[str, Any]:
    """Combine the saved profile with reliable extracts from that account's resumes.

    Confirmed profile values stay in place. An upload can fill a blank field on
    the same item, or add an item the profile does not already contain.
    """
    merged: dict[str, Any] = {
        "name": _plain(profile.get("name")),
        "email": _plain(profile.get("email")),
        "phone": _plain(profile.get("phone")),
        "address": _plain(profile.get("address")),
        "city": _plain(profile.get("city")),
        "country": _plain(profile.get("country")),
        "bio": _plain(profile.get("bio")),
        "degree": _plain(profile.get("degree")),
        "college": _plain(profile.get("college")),
        "year_graduated": _plain(profile.get("year_graduated")),
        "studies": [_copy_study(row) for row in (profile.get("studies") or []) if isinstance(row, dict)],
        "jobs": [_copy_job(row) for row in (profile.get("jobs") or []) if isinstance(row, dict)],
        "skills": _string_list(profile.get("skills"), limit=80),
        "certifications": [],
        "seminars": [dict(row) for row in (profile.get("seminars") or []) if isinstance(row, dict)],
        "awards": [dict(row) for row in (profile.get("awards") or []) if isinstance(row, dict)],
        "projects": [],
        "languages": _string_list(profile.get("languages"), limit=60),
    }
    for row in profile.get("certifications") or []:
        if not isinstance(row, dict):
            continue
        _extend_unique(merged["skills"], _string_list(row.get("skills") or row.get("skills_covered")))
        merged["certifications"].append({
            "name": _plain(row.get("name")),
            "awarding_body": _plain(row.get("awarding_body")),
            "awarded_on": row.get("awarded_on") or "",
        })

    for upload in _usable_uploads(uploads):
        parsed = upload["parsed"]
        if not merged["bio"]:
            summary = _summary_text(parsed)
            if summary:
                merged["bio"] = summary

        parsed_degree = _reliable_degree(parsed.get("degree"))
        parsed_year = _reliable_year(parsed.get("year_graduated"))
        if parsed_degree and not merged["degree"]:
            merged["degree"] = parsed_degree
            if parsed_year and not merged["year_graduated"]:
                merged["year_graduated"] = parsed_year
        elif (
            parsed_degree
            and parsed_year
            and not merged["year_graduated"]
            and _loose_same(merged["degree"], parsed_degree, minimum=8)
        ):
            merged["year_graduated"] = parsed_year

        for exp in parsed.get("experiences") or []:
            if isinstance(exp, dict):
                _remember_experience(merged, exp)

        for study in parsed.get("further_studies") or []:
            if isinstance(study, dict):
                course, school, enrolled, graduated, completed = _study_from_record(study)
                _add_study(merged, course, school, enrolled, graduated, completed)
        for record in parsed.get("education_records") or []:
            if isinstance(record, dict):
                course, school, enrolled, graduated, completed = _study_from_record(record)
                _add_study(merged, course, school, enrolled, graduated, completed)

        _extend_unique(merged["skills"], _string_list(parsed.get("skills"), limit=80))

        sections = _document_sections(upload["text"])
        for line in sections.get("certifications") or []:
            name = _entry_line(line)
            if not name:
                continue
            if any(_loose_same(existing.get("name"), name, minimum=8) for existing in merged["certifications"]):
                continue
            merged["certifications"].append({"name": name, "awarding_body": "", "awarded_on": ""})
        for line in (sections.get("projects") or [])[:40]:
            project = _entry_line(line)
            if project:
                _extend_unique(merged["projects"], [project])

        if not merged["skills"]:
            for line in sections.get("skills") or []:
                _extend_unique(merged["skills"], _string_list(line, limit=80))
        _supplement_from_text(merged, upload["text"])

    return merged


def build_resume_pdf(profile: dict[str, Any]) -> bytes:
    """Build a resume from consolidated profile and upload data. Empty sections are omitted."""
    bio = _text(profile.get("bio"))
    education = _education_entries(profile)
    further = _pair_entries(profile.get("further_study_entries") or []) if isinstance(profile.get("further_study_entries"), list) else []
    jobs = _job_entries(profile)
    projects = _project_lines(profile)
    skills = _skill_list(profile)
    languages = _string_list(profile.get("languages"), limit=60)
    certifications = _named_rows(profile, "certifications", "name")
    seminars = _named_rows(profile, "seminars", "title")
    awards = _named_rows(profile, "awards", "title")
    has_body = any([bio, education, further, jobs, projects, skills, languages, certifications, seminars, awards])
    document_layout = bool(profile.get("document_layout"))
    experience_title = "Work experience" if document_layout else "Experience"
    education_title = "Educational background" if document_layout else "Education"
    further_title = "Further studies and additional qualifications" if document_layout else "Further studies"
    seminar_title = "Seminars and training" if document_layout else "Seminars"
    award_title = "Awards and achievements" if document_layout else "Awards"
    certification_title = "Certifications and licenses" if document_layout else "Certifications"
    rule = RULE if document_layout else GOLD

    doc = _ResumeDoc()
    name = _text(profile.get("name")) or "Alumni"
    doc.heading(
        name,
        _contact_line(profile, sep=" · " if document_layout else " | "),
        centered=document_layout,
        rule=NAVY if document_layout else GOLD,
    )

    def write_summary() -> None:
        if bio:
            doc.section("Professional summary", rule=rule)
            doc.body(bio)

    def write_study_rows(title: str, rows: list) -> None:
        visible = [row for row in rows if isinstance(row, dict) and _entry_has_content(row)]
        if not visible:
            return
        doc.section(title, rule=rule)
        for row in visible:
            program = _text(row.get("program"))
            institution = _text(row.get("institution"))
            detail = _text(row.get("detail"))
            heading = program or institution or detail
            if not heading:
                continue
            doc.strong(heading)
            if institution and program:
                doc.body(institution)
            if detail and detail != heading:
                doc.muted(detail)
            doc.spacer(6)

    def write_education() -> None:
        if document_layout:
            write_study_rows(education_title, profile.get("education_entries") or [])
            return
        if education:
            doc.section(education_title, rule=rule)
            for title, detail in education:
                doc.strong(title)
                if detail:
                    doc.muted(detail)
                doc.spacer(6)

    def write_further() -> None:
        if document_layout:
            write_study_rows(further_title, profile.get("further_study_entries") or [])
            return
        if further:
            doc.section(further_title, rule=rule)
            for title, detail in further:
                doc.strong(title)
                if detail:
                    doc.muted(detail)
                doc.spacer(6)

    def write_jobs() -> None:
        if not jobs:
            return
        doc.section(experience_title, rule=rule)
        for job in jobs:
            doc.strong(job["title"])
            if job["company"]:
                doc.body(job["company"])
            if job["meta"]:
                doc.muted(job["meta"])
            if job["description"]:
                _write_detail(doc, job["description"], bullets=document_layout)
            doc.spacer(6)

    def write_projects() -> None:
        if not projects:
            return
        doc.section("Projects", rule=rule)
        for project in projects:
            doc.body(project)
            doc.spacer(4)

    def write_skills() -> None:
        if skills:
            doc.section("Skills", rule=rule)
            doc.body(", ".join(skills))

    def write_languages() -> None:
        if languages:
            doc.section("Languages", rule=rule)
            doc.body(", ".join(languages))

    def write_certifications() -> None:
        if not certifications:
            return
        doc.section(certification_title, rule=rule)
        for row in certifications:
            doc.strong(_text(row.get("name")))
            detail = _text(row.get("detail")) or _join([row.get("awarding_body") or "", _month_year(row.get("awarded_on"))])
            if detail:
                doc.muted(detail)
            doc.spacer(6)

    def write_seminars() -> None:
        if not seminars:
            return
        doc.section(seminar_title, rule=rule)
        for row in seminars:
            doc.strong(_text(row.get("title")))
            detail = _text(row.get("detail")) or _join([row.get("organizer") or "", row.get("location") or "", _month_year(row.get("held_on"))])
            if detail:
                doc.muted(detail)
            doc.spacer(6)

    def write_awards() -> None:
        if not awards:
            return
        doc.section(award_title, rule=rule)
        for row in awards:
            doc.strong(_text(row.get("title")))
            detail = _text(row.get("detail")) or _join([row.get("issuer") or "", _month_year(row.get("awarded_on"))])
            if detail:
                doc.muted(detail)
            if _block_text(row.get("description")):
                _write_detail(doc, row.get("description"), bullets=document_layout)
            doc.spacer(6)

    writers = (
        [write_summary, write_jobs, write_education, write_further, write_skills, write_certifications, write_seminars, write_awards, write_projects, write_languages]
        if document_layout
        else [write_summary, write_education, write_further, write_jobs, write_projects, write_skills, write_languages, write_certifications, write_seminars, write_awards]
    )
    for write in writers:
        write()

    if not has_body:
        doc.note("Profile sections you add on Home, such as a biography, education, experience, skills, and certifications, will appear here.")

    return doc.bytes()




def resume_preview(profile: dict[str, Any]) -> dict[str, Any]:
    """Section list for the Export Resume page. It uses the same consolidated source as the PDF."""
    contact = _contact_line(profile)
    bio = _text(profile.get("bio"))
    education = _education_entries(profile)
    jobs = _job_entries(profile)
    projects = _project_lines(profile)
    skills = _skill_list(profile)
    languages = _string_list(profile.get("languages"), limit=60)
    certifications = _named_rows(profile, "certifications", "name")
    seminars = _named_rows(profile, "seminars", "title")
    awards = _named_rows(profile, "awards", "title")

    def row(label: str, ready: bool, detail: str) -> dict[str, Any]:
        return {
            "label": label,
            "ready": ready,
            "detail": _clip(detail) if ready else "Nothing saved for this section yet.",
        }

    sections = [
        row("Contact details", bool(contact), contact),
        row("Professional summary", bool(bio), bio),
        row("Education", bool(education), " · ".join(title for title, _detail in education)),
        row("Experience", bool(jobs), " · ".join(_join([job["title"], job["company"]], ", ") for job in jobs)),
    ]
    if projects:
        sections.append(row("Projects", True, " · ".join(projects)))
    sections.append(row("Skills", bool(skills), ", ".join(skills)))
    if languages:
        sections.append(row("Languages", True, ", ".join(languages)))
    sections.extend([
        row("Certifications", bool(certifications), ", ".join(_text(item.get("name")) for item in certifications)),
        row("Seminars", bool(seminars), ", ".join(_text(item.get("title")) for item in seminars)),
        row("Awards", bool(awards), ", ".join(_text(item.get("title")) for item in awards)),
    ])
    return {"name": _text(profile.get("name")) or "Alumni", "sections": sections}


_DOCUMENT_TYPES = (
    "summary",
    "experience",
    "education",
    "further_studies",
    "skills",
    "certifications",
    "seminars",
    "awards",
    "projects",
    "languages",
)
_ENTRY_FIELDS = {
    "experience": ("title", "company", "dates", "location", "description"),
    "education": ("program", "institution", "detail"),
    "further_studies": ("program", "institution", "detail"),
    "certifications": ("name", "detail"),
    "seminars": ("title", "detail"),
    "awards": ("title", "detail", "description"),
}
_ITEM_TYPES = {"skills", "projects", "languages"}
_FIELD_LIMITS = {"description": 2000, "detail": 500, "text": 2000}
_DEFAULT_LIMIT = 200


def _clip_field(value: Any, limit: int) -> str:
    text = re.sub(r"<[^>]+>", "", _plain(value))
    return text[:limit]


def _clip_block(value: Any, limit: int) -> str:
    raw = re.sub(r"<[^>]+>", "", str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in raw.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)[:limit]


def _date_label(row: dict) -> str:
    start = _month_year(row.get("start_date"))
    end = "Present" if row.get("is_current") else _month_year(row.get("end_date"))
    return " - ".join(part for part in (start, end) if part)


def _address_line(profile: dict[str, Any]) -> str:
    return ", ".join(part for part in (_plain(profile.get("address")), _plain(profile.get("city")), _plain(profile.get("country"))) if part)


def resume_document_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Initial editable resume. Empty sections are left out."""
    sections: list[dict[str, Any]] = []
    summary = _plain(profile.get("bio"))
    if summary:
        sections.append({"type": "summary", "text": summary})

    experience = []
    job_rows = [row for row in (profile.get("jobs") or []) if isinstance(row, dict)]
    job_rows.sort(key=lambda row: str(row.get("start_date") or ""), reverse=True)
    job_rows.sort(key=lambda row: 0 if _current_flag(row) else 1)
    for row in job_rows:
        if not isinstance(row, dict):
            continue
        title = _plain(row.get("job_title"))
        company = _plain(row.get("company"))
        if not title and not company:
            continue
        experience.append({
            "title": title,
            "company": company,
            "dates": _date_label(row),
            "location": _plain(row.get("location")),
            "description": _plain(row.get("description")),
        })
    if experience:
        sections.append({"type": "experience", "entries": experience})

    education = []
    degree = _plain(profile.get("degree"))
    college = _plain(profile.get("college"))
    year = _plain(profile.get("year_graduated"))
    if degree or college or year:
        education.append({
            "program": degree or college or f"Class of {year}",
            "institution": college if degree else "",
            "detail": f"Graduated {year}" if year and (degree or college) else "",
        })
    if education:
        sections.append({"type": "education", "entries": education})

    studies = []
    for row in profile.get("studies") or []:
        if not isinstance(row, dict):
            continue
        program = _plain(row.get("course_degree"))
        school = _plain(row.get("school"))
        enrolled = _plain(row.get("year_enrolled"))
        completed = _plain(row.get("year_completed"))
        graduated = _graduated(row.get("is_graduated"))
        detail = ", ".join(part for part in (
            _plain(row.get("institution_address")),
            f"Enrolled {enrolled}" if enrolled else "",
            f"Graduated {completed}".strip() if graduated is True else "",
            _plain(row.get("scholarship")),
        ) if part)
        if program or school or detail:
            studies.append({"program": program or school, "institution": school if program else "", "detail": detail})
    if studies:
        sections.append({"type": "further_studies", "entries": studies})

    skills = _string_list(profile.get("skills"), limit=80)
    if skills:
        sections.append({"type": "skills", "items": skills})

    certifications = []
    for row in profile.get("certifications") or []:
        if isinstance(row, dict) and _plain(row.get("name")):
            certifications.append({
                "name": _plain(row.get("name")),
                "detail": ", ".join(part for part in (_plain(row.get("awarding_body")), _month_year(row.get("awarded_on"))) if part),
            })
    if certifications:
        sections.append({"type": "certifications", "entries": certifications})

    seminars = []
    for row in profile.get("seminars") or []:
        if isinstance(row, dict) and _plain(row.get("title")):
            seminars.append({
                "title": _plain(row.get("title")),
                "detail": ", ".join(part for part in (_plain(row.get("organizer")), _plain(row.get("location")), _month_year(row.get("held_on"))) if part),
            })
    if seminars:
        sections.append({"type": "seminars", "entries": seminars})

    awards = []
    for row in profile.get("awards") or []:
        if isinstance(row, dict) and _plain(row.get("title")):
            awards.append({
                "title": _plain(row.get("title")),
                "detail": ", ".join(part for part in (_plain(row.get("issuer")), _month_year(row.get("awarded_on"))) if part),
                "description": _plain(row.get("description")),
            })
    if awards:
        sections.append({"type": "awards", "entries": awards})

    projects = [_plain(item) for item in (profile.get("projects") or []) if _plain(item)]
    if projects:
        sections.append({"type": "projects", "items": projects[:40]})
    languages = _string_list(profile.get("languages"), limit=60)
    if languages:
        sections.append({"type": "languages", "items": languages})

    return {
        "name": _plain(profile.get("name")),
        "phone": _plain(profile.get("phone")),
        "email": _plain(profile.get("email")),
        "address": _address_line(profile),
        "sections": sections,
    }


def _clean_entry(kind: str, row: dict) -> dict[str, str]:
    cleaned = {}
    for field in _ENTRY_FIELDS[kind]:
        limit = _FIELD_LIMITS.get(field, _DEFAULT_LIMIT)
        cleaned[field] = _clip_block(row.get(field), limit) if field == "description" else _clip_field(row.get(field), limit)
    return cleaned


def _entry_has_content(row: dict) -> bool:
    return any(_plain(value) for value in row.values())


def sanitize_resume_document(payload: Any) -> dict[str, Any]:
    """Keep only resume fields. Empty added sections stay so the editor can reopen them."""
    source = payload if isinstance(payload, dict) else {}
    sections = []
    seen: set[str] = set()
    for section in source.get("sections") or []:
        if not isinstance(section, dict):
            continue
        kind = _plain(section.get("type"))
        if kind not in _DOCUMENT_TYPES or kind in seen:
            continue
        seen.add(kind)
        if kind == "summary":
            sections.append({"type": kind, "text": _clip_field(section.get("text"), 2000)})
            continue
        if kind in _ITEM_TYPES:
            items = []
            for item in (section.get("items") or [])[:60]:
                text = _clip_field(item, 200)
                if text:
                    items.append(text)
            sections.append({"type": kind, "items": items})
            continue
        entries = []
        for row in (section.get("entries") or [])[:40]:
            if not isinstance(row, dict):
                continue
            entries.append(_clean_entry(kind, row))
        sections.append({"type": kind, "entries": entries})
    return {
        "name": _clip_field(source.get("name"), 160),
        "phone": _clip_field(source.get("phone"), 40),
        "email": _clip_field(source.get("email"), 255),
        "address": _clip_field(source.get("address"), 300),
        "sections": sections,
    }


def profile_from_document(document: dict[str, Any]) -> dict[str, Any]:
    """Map a saved resume onto the PDF builder. Blank entries are omitted."""
    clean = sanitize_resume_document(document)
    profile: dict[str, Any] = {
        "name": clean["name"],
        "phone": clean["phone"],
        "email": clean["email"],
        "address": clean["address"],
        "city": "",
        "country": "",
        "bio": "",
        "jobs": [],
        "skills": [],
        "certifications": [],
        "seminars": [],
        "awards": [],
        "projects": [],
        "languages": [],
        "education_entries": [],
        "further_study_entries": [],
        "preserve_order": True,
        "document_layout": True,
    }
    for section in clean["sections"]:
        kind = section["type"]
        if kind == "summary" and _plain(section.get("text")):
            profile["bio"] = section["text"]
        elif kind == "experience":
            for row in section.get("entries") or []:
                if _plain(row.get("title")) or _plain(row.get("company")):
                    profile["jobs"].append({
                        "job_title": row.get("title") or "",
                        "company": row.get("company") or "",
                        "dates": row.get("dates") or "",
                        "location": row.get("location") or "",
                        "description": row.get("description") or "",
                    })
        elif kind == "education":
            profile["education_entries"] = [row for row in section.get("entries") or [] if _entry_has_content(row)]
        elif kind == "further_studies":
            profile["further_study_entries"] = [row for row in section.get("entries") or [] if _entry_has_content(row)]
        elif kind == "skills":
            profile["skills"] = section.get("items") or []
        elif kind == "projects":
            profile["projects"] = section.get("items") or []
        elif kind == "languages":
            profile["languages"] = section.get("items") or []
        elif kind == "certifications":
            profile["certifications"] = [row for row in section.get("entries") or [] if _plain(row.get("name"))]
        elif kind == "seminars":
            profile["seminars"] = [row for row in section.get("entries") or [] if _plain(row.get("title"))]
        elif kind == "awards":
            profile["awards"] = [row for row in section.get("entries") or [] if _plain(row.get("title"))]
    return profile


def resume_filename(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", _text(name)).strip("-") or "Alumni"
    return f"{slug}-Resume.pdf"
