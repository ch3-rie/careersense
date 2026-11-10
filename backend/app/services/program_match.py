"""Match catalog program names with course codes and recognized abbreviations.

Abbreviations come from the course code stored on a program, or from a unique
initialism of that program's name. A search that does not resolve to a catalog
program does not pull in unrelated programs.
"""

from __future__ import annotations

import re

_STOP_WORDS = {"of", "in", "and", "the", "for", "a", "an"}
# Degree tokens already used as words in catalog names. Keep them whole.
_WHOLE_TOKENS = {
    "bs", "ab", "ba", "ma", "ms", "mba", "phd", "md", "jd",
    "beed", "bsed", "bsn", "bsa", "bsba", "bsit", "bscs",
}


def clean(value: str | None) -> str:
    return str(value or "").strip()


def normalized_name(value: str | None) -> str:
    from app.services.academic_reference import normalize_program_name

    return normalize_program_name(value)


def compact(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", clean(value).casefold())


def _significant_words(value: str | None) -> list[str]:
    return [word for word in normalized_name(value).split() if word not in _STOP_WORDS]


def derived_abbreviation(value: str | None) -> str:
    parts: list[str] = []
    for word in _significant_words(value):
        if word in _WHOLE_TOKENS or len(word) <= 2:
            parts.append(word)
        else:
            parts.append(word[0])
    return "".join(parts)


def field_initials(value: str | None) -> str:
    words = [word for word in _significant_words(value) if word not in _WHOLE_TOKENS and len(word) > 2]
    if len(words) < 2:
        return ""
    return "".join(word[0] for word in words)


def code_remainder(code: str) -> str:
    """Drop a leading degree token so CPE matches the stored code BSCPE."""
    for prefix in ("bs", "ab", "ba", "ma", "ms"):
        if code.startswith(prefix) and len(code) - len(prefix) >= 2:
            return code[len(prefix):]
    return ""


def _identity(program: dict) -> tuple[str, str]:
    return (clean(program.get("college")).casefold(), clean(program.get("course")).casefold())


def _tokens_match(query_norm: str, name_norm: str) -> bool:
    if query_norm and query_norm in name_norm:
        return True
    query_words = query_norm.split()
    name_words = name_norm.split()
    if not query_words or not name_words:
        return False
    if len(query_words) == 1:
        token = query_words[0]
        if len(token) < 3:
            return False
        return any(word.startswith(token) for word in name_words)
    start = 0
    for token in query_words:
        if len(token) < 2:
            return False
        found = False
        for index in range(start, len(name_words)):
            word = name_words[index]
            exact = word == token
            prefix = len(token) >= 3 and word.startswith(token)
            if exact or prefix:
                start = index + 1
                found = True
                break
        if not found:
            return False
    return True


class ProgramIndex:
    def __init__(self, programs: list[dict]):
        self.programs = [program for program in programs if clean(program.get("course"))]
        self.by_alias: dict[str, list[dict]] = {}
        self.program_aliases: dict[tuple[str, str], set[str]] = {}
        self._build()

    def _grant(self, alias: str, programs: list[dict]) -> None:
        self.by_alias[alias] = programs
        for program in programs:
            self.program_aliases.setdefault(_identity(program), set()).add(alias)

    def _build(self) -> None:
        code_alias: dict[str, list[dict]] = {}
        derived_alias: dict[str, list[dict]] = {}
        initial_alias: dict[str, list[dict]] = {}
        remainder_alias: dict[str, list[dict]] = {}
        for program in self.programs:
            code = compact(program.get("course_code"))
            if len(code) >= 2:
                code_alias.setdefault(code, []).append(program)
            derived = derived_abbreviation(program.get("course"))
            if len(derived) >= 2 and derived != code:
                derived_alias.setdefault(derived, []).append(program)
            initials = field_initials(program.get("course"))
            if len(initials) >= 2 and initials not in {code, derived} and (not code or code.endswith(initials)):
                initial_alias.setdefault(initials, []).append(program)
            remainder = code_remainder(code)
            if len(remainder) >= 2 and remainder not in {code, derived, initials}:
                remainder_alias.setdefault(remainder, []).append(program)
        for alias, programs in code_alias.items():
            self._grant(alias, programs)
        for alias, programs in derived_alias.items():
            if alias not in self.by_alias and len(programs) == 1:
                self._grant(alias, programs)
        for alias, programs in initial_alias.items():
            if alias not in self.by_alias and len(programs) == 1:
                self._grant(alias, programs)
        for alias, programs in remainder_alias.items():
            if alias not in self.by_alias and len(programs) == 1:
                self._grant(alias, programs)

    def aliases_for(self, program: dict) -> set[str]:
        return self.program_aliases.get(_identity(program), set())

    def _add(self, found: list[dict], seen: set[tuple[str, str]], program: dict) -> None:
        key = _identity(program)
        if key in seen:
            return
        seen.add(key)
        found.append(program)

    def programs_for_selection(self, selected: str) -> list[dict]:
        """Dropdown value: the catalog name, the same name in another spelling, or an exact abbreviation."""
        text = clean(selected)
        if not text:
            return []
        key = normalized_name(text)
        code = compact(text)
        found: list[dict] = []
        seen: set[tuple[str, str]] = set()
        if key:
            for program in self.programs:
                if normalized_name(program.get("course")) == key:
                    self._add(found, seen, program)
        if code and code in self.by_alias:
            for program in self.by_alias[code]:
                self._add(found, seen, program)
        return found

    def programs_for_term(self, term: str) -> list[dict]:
        """Free-text search: full name, partial name, exact abbreviation, or a partial course code."""
        text = clean(term)
        if len(text) < 2:
            return []
        query_norm = normalized_name(text)
        query_code = compact(text)
        found: list[dict] = []
        seen: set[tuple[str, str]] = set()
        if len(query_code) >= 2 and query_code in self.by_alias:
            for program in self.by_alias[query_code]:
                self._add(found, seen, program)
        if len(query_code) >= 3:
            for alias, programs in self.by_alias.items():
                if alias.startswith(query_code) and alias != query_code:
                    for program in programs:
                        self._add(found, seen, program)
        if len(query_norm) >= 3:
            for program in self.programs:
                if _tokens_match(query_norm, normalized_name(program.get("course"))):
                    self._add(found, seen, program)
        return found

    def stored_in_program(self, degree: str | None, course_code: str | None, program: dict) -> bool:
        degree_name = normalized_name(degree)
        program_name = normalized_name(program.get("course"))
        if degree_name and program_name and degree_name == program_name:
            return True
        aliases = self.aliases_for(program)
        degree_code = compact(degree)
        record_code = compact(course_code)
        if degree_code and degree_code in aliases:
            return True
        if record_code and record_code in aliases:
            return True
        return False

    def record_matches_term(self, term: str, degree: str | None, course_code: str | None = "") -> bool:
        return any(self.stored_in_program(degree, course_code, program) for program in self.programs_for_term(term))

    def selection_matches(self, selected: str, degree: str | None, course_code: str | None = "") -> bool:
        text = clean(selected)
        if not text:
            return True
        found = self.programs_for_selection(text)
        if not found:
            folded = text.casefold()
            return clean(degree).casefold() == folded or clean(course_code).casefold() == folded
        return any(self.stored_in_program(degree, course_code, program) for program in found)

    def display_name(self, degree: str | None, course_code: str | None = "", college: str | None = "") -> str:
        """Catalog program name when the stored degree or course code identifies one program."""
        degree_text = clean(degree)
        code_text = clean(course_code)
        hits = [program for program in self.programs if self.stored_in_program(degree_text, code_text, program)]
        college_name = clean(college).casefold()
        if college_name:
            scoped = [program for program in hits if clean(program.get("college")).casefold() == college_name]
            if len(scoped) == 1:
                return scoped[0]["course"]
        if len(hits) == 1:
            return hits[0]["course"]
        return degree_text or code_text
