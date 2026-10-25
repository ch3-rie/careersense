export const STUDIES_SECTION_TITLE = "Further Education and Professional Development";

export function credentialReportChoice(explicit, rows) {
  const raw = String(explicit ?? "").trim().toLowerCase();
  if (raw === "yes") return "Yes";
  if (raw === "no") return "No";
  return Array.isArray(rows) && rows.some((row) => String(row?.name || row?.title || "").trim()) ? "Yes" : "No";
}

export const BLANK_PROGRAM = {
  course_degree: "",
  school: "",
  institution_address: "",
  year_enrolled: "",
  scholarship: "",
  is_graduated: "No",
};

const CREDENTIAL_TEXT = {
  certifications: ["name", "awarding_body", "detail", "year"],
  seminars: ["name", "location", "organizer", "detail", "year"],
  awards: ["name", "issuer", "detail", "year", "description"],
};

function text(value) {
  return String(value ?? "").trim();
}

function same(left, right) {
  return text(left).toLowerCase() === text(right).toLowerCase();
}

export function resumeCanSuggest(resume) {
  if (!resume || typeof resume !== "object") return false;
  const source = text(resume.parser_source).toLowerCase();
  return source !== "failed" && source !== "empty";
}

export function programIsPopulated(row) {
  if (!row || typeof row !== "object") return false;
  if (["school", "institution_address", "course_degree", "year_enrolled", "scholarship"].some((key) => text(row[key]))) {
    return true;
  }
  return text(row.is_graduated) === "Yes";
}

export function isSuggestedProgram(row, resume) {
  if (!resumeCanSuggest(resume) || !row) return false;
  const studies = Array.isArray(resume.further_studies) ? resume.further_studies : [];
  return studies.some((item) => {
    const program = text(item?.course_degree);
    const school = text(item?.school);
    if (!program && !school) return false;
    return same(item?.course_degree, row.course_degree) && same(item?.school, row.school);
  });
}

export function credentialIsPopulated(row, kind) {
  if (!row || typeof row !== "object") return false;
  const fields = CREDENTIAL_TEXT[kind] || ["name", "detail", "year"];
  return fields.some((key) => text(row[key]));
}

export function isSuggestedCredential(row, resume, kind) {
  if (!resumeCanSuggest(resume) || !text(row?.name)) return false;
  const rows = Array.isArray(resume?.[kind]) ? resume[kind] : [];
  return rows.some((item) => same(item?.name || item?.title, row.name));
}
