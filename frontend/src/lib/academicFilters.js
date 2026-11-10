export function coursesForCollege(catalog, college) {
  const selected = String(college || "");
  const names = selected
    ? (catalog?.pairs || []).filter((item) => item.college === selected && item.course).map((item) => item.course)
    : (catalog?.courses || []);
  return [...new Set(names)].sort((left, right) => left.localeCompare(right));
}

export function programChoices(catalog, college) {
  const selected = String(college || "");
  const programs = catalog?.programs?.length
    ? catalog.programs
    : (catalog?.pairs || []).map((item) => ({ college: item.college, course: item.course, course_code: "" }));
  const seen = new Set();
  return programs
    .filter((item) => item.course && (!selected || item.college === selected))
    .filter((item) => {
      if (seen.has(item.course)) return false;
      seen.add(item.course);
      return true;
    })
    .sort((left, right) => left.course.localeCompare(right.course));
}

export function courseLabel(program) {
  const course = typeof program === "string" ? program : (program?.course || program?.program || program?.name || "");
  const kind = typeof program === "string" ? "" : (program?.kind || "");
  const note = {
    graduate: "graduate",
    professional: "professional",
    diploma: "diploma",
    certificate: "certificate",
    combined: "combined pathway",
    pathway: "pathway",
    major: "major",
    specialization: "specialization",
  }[kind];
  return note ? `${course} (${note})` : course;
}

export function courseCodeFor(catalog, college, course) {
  return programChoices(catalog, college).find((item) => item.course === course)?.course_code || "";
}

const STOP_WORDS = new Set(["of", "in", "and", "the", "for", "a", "an"]);
const WHOLE_TOKENS = new Set([
  "bs", "ab", "ba", "ma", "ms", "mba", "phd", "md", "jd",
  "beed", "bsed", "bsn", "bsa", "bsba", "bsit", "bscs",
]);

export function normalizeProgramName(value) {
  let text = String(value || "").trim().toLowerCase();
  text = text.replace(/[—–-]/g, " ");
  text = text.replace(/\b(major|specialization|specializing) in\b/g, " ");
  text = text.replace(/^bachelor of science in\s+/, "bs ");
  text = text.replace(/^bachelor of arts in\s+/, "ab ");
  text = text.replace(/[^a-z0-9]+/g, " ");
  return text.trim().replace(/\s+/g, " ");
}

export function compactProgramCode(value) {
  return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]/g, "");
}

function programCourse(program) {
  return String(program?.course || program?.name || program?.program || "").trim();
}

function significantWords(value) {
  return normalizeProgramName(value).split(" ").filter((word) => word && !STOP_WORDS.has(word));
}

function derivedAbbreviation(value) {
  return significantWords(value).map((word) => (WHOLE_TOKENS.has(word) || word.length <= 2 ? word : word[0])).join("");
}

function fieldInitials(value) {
  const words = significantWords(value).filter((word) => !WHOLE_TOKENS.has(word) && word.length > 2);
  if (words.length < 2) return "";
  return words.map((word) => word[0]).join("");
}

function codeRemainder(code) {
  const prefixes = ["bs", "ab", "ba", "ma", "ms"];
  const match = prefixes.find((prefix) => code.startsWith(prefix) && code.length - prefix.length >= 2);
  return match ? code.slice(match.length) : "";
}

function identity(program) {
  return `${String(program?.college || "").trim().toLowerCase()}|${programCourse(program).toLowerCase()}`;
}

function tokensMatch(queryNorm, nameNorm) {
  if (queryNorm && nameNorm.includes(queryNorm)) return true;
  const queryWords = queryNorm.split(" ").filter(Boolean);
  const nameWords = nameNorm.split(" ").filter(Boolean);
  if (!queryWords.length || !nameWords.length) return false;
  if (queryWords.length === 1) {
    const token = queryWords[0];
    if (token.length < 3) return false;
    return nameWords.some((word) => word.startsWith(token));
  }
  let start = 0;
  for (const token of queryWords) {
    if (token.length < 2) return false;
    let found = false;
    for (let index = start; index < nameWords.length; index += 1) {
      const word = nameWords[index];
      if (word === token || (token.length >= 3 && word.startsWith(token))) {
        start = index + 1;
        found = true;
        break;
      }
    }
    if (!found) return false;
  }
  return true;
}

export function createProgramIndex(programs) {
  const rows = (programs || []).map((program) => ({
    college: program?.college || "",
    course: programCourse(program),
    course_code: program?.course_code || program?.courseCode || "",
    kind: program?.kind || "",
  })).filter((program) => program.course);
  const byAlias = new Map();
  const programAliases = new Map();

  function grant(alias, matched) {
    byAlias.set(alias, matched);
    matched.forEach((program) => {
      const key = identity(program);
      const aliases = programAliases.get(key) || new Set();
      aliases.add(alias);
      programAliases.set(key, aliases);
    });
  }

  const codeAlias = new Map();
  const derivedAlias = new Map();
  const initialAlias = new Map();
  const remainderAlias = new Map();
  const push = (map, alias, program) => {
    const list = map.get(alias) || [];
    list.push(program);
    map.set(alias, list);
  };
  rows.forEach((program) => {
    const code = compactProgramCode(program.course_code);
    if (code.length >= 2) push(codeAlias, code, program);
    const derived = derivedAbbreviation(program.course);
    if (derived.length >= 2 && derived !== code) push(derivedAlias, derived, program);
    const initials = fieldInitials(program.course);
    if (initials.length >= 2 && initials !== code && initials !== derived && (!code || code.endsWith(initials))) {
      push(initialAlias, initials, program);
    }
    const remainder = codeRemainder(code);
    if (remainder.length >= 2 && remainder !== code && remainder !== derived && remainder !== initials) {
      push(remainderAlias, remainder, program);
    }
  });
  codeAlias.forEach((matched, alias) => grant(alias, matched));
  derivedAlias.forEach((matched, alias) => {
    if (!byAlias.has(alias) && matched.length === 1) grant(alias, matched);
  });
  initialAlias.forEach((matched, alias) => {
    if (!byAlias.has(alias) && matched.length === 1) grant(alias, matched);
  });
  remainderAlias.forEach((matched, alias) => {
    if (!byAlias.has(alias) && matched.length === 1) grant(alias, matched);
  });

  function add(found, seen, program) {
    const key = identity(program);
    if (seen.has(key)) return;
    seen.add(key);
    found.push(program);
  }

  function aliasesFor(program) {
    return programAliases.get(identity(program)) || new Set();
  }

  function storedInProgram(degree, courseCode, program) {
    const degreeName = normalizeProgramName(degree);
    const name = normalizeProgramName(program.course);
    if (degreeName && name && degreeName === name) return true;
    const aliases = aliasesFor(program);
    const degreeCode = compactProgramCode(degree);
    const recordCode = compactProgramCode(courseCode);
    if (degreeCode && aliases.has(degreeCode)) return true;
    if (recordCode && aliases.has(recordCode)) return true;
    return false;
  }

  function programsForTerm(term) {
    const text = String(term || "").trim();
    if (text.length < 2) return [];
    const queryNorm = normalizeProgramName(text);
    const queryCode = compactProgramCode(text);
    const found = [];
    const seen = new Set();
    if (queryCode.length >= 2 && byAlias.has(queryCode)) {
      byAlias.get(queryCode).forEach((program) => add(found, seen, program));
    }
    if (queryCode.length >= 3) {
      byAlias.forEach((matched, alias) => {
        if (alias.startsWith(queryCode) && alias !== queryCode) matched.forEach((program) => add(found, seen, program));
      });
    }
    if (queryNorm.length >= 3) {
      rows.forEach((program) => {
        if (tokensMatch(queryNorm, normalizeProgramName(program.course))) add(found, seen, program);
      });
    }
    return found;
  }

  return {
    programs: rows,
    programsForTerm,
    matchesRecord(term, record) {
      const degree = record?.degree || record?.course || record?.name || "";
      const courseCode = record?.courseCode || record?.course_code || "";
      return programsForTerm(term).some((program) => storedInProgram(degree, courseCode, program));
    },
    displayName(degree, courseCode = "", college = "") {
      const hits = rows.filter((program) => storedInProgram(degree, courseCode, program));
      const collegeName = String(college || "").trim().toLowerCase();
      if (collegeName) {
        const scoped = hits.filter((program) => String(program.college || "").trim().toLowerCase() === collegeName);
        if (scoped.length === 1) return scoped[0].course;
      }
      if (hits.length === 1) return hits[0].course;
      return String(degree || "").trim() || String(courseCode || "").trim();
    },
  };
}

export function displayProgramName(catalog, degree, courseCode = "", college = "") {
  const programs = catalog?.programs?.length
    ? catalog.programs
    : (catalog?.pairs || []).map((item) => ({ college: item.college, course: item.course, course_code: "" }));
  return createProgramIndex(programs).displayName(degree, courseCode, college);
}
