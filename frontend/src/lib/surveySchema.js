import { credentialReportChoice } from "./studiesSection.js";

export function flattenQuestions(schema) {
  const items = [];
  for (const section of schema?.sections || []) {
    for (const subsection of section.subsections || []) {
      for (const question of subsection.questions || []) {
        items.push({ section, subsection, question });
      }
    }
  }
  return items;
}

export function questionIndex(schema) {
  return Object.fromEntries(flattenQuestions(schema).map(({ question }) => [question.id, question]));
}

export function optionValue(item) {
  if (item && typeof item === "object") return String(item.value ?? item.label ?? "");
  return String(item ?? "");
}

export function optionLabel(item) {
  if (item && typeof item === "object") return String(item.label ?? item.value ?? "");
  return String(item ?? "");
}

export function extraAnswerKey(question) {
  return question?.extra_key || question?.id;
}

export function readExtraAnswer(extras, question) {
  const store = extras || {};
  for (const key of [extraAnswerKey(question), question?.id, question?.extra_key]) {
    if (key != null && key !== "" && store[key] !== undefined) return store[key];
  }
  return undefined;
}

export function getFormValue(form, question) {
  if (!question) return "";
  if (question.storage === "extra") {
    const stored = readExtraAnswer(form.extra_answers, question);
    if (stored !== undefined) return stored;
    return question.default_value ?? (question.type === "checkboxes" ? [] : "");
  }
  const key = question.field_key || question.id;
  if (String(key).includes(".")) {
    const [parent, child] = String(key).split(".");
    return form[parent]?.[child] ?? "";
  }
  if (question.type === "checkboxes" || question.type === "skills" || question.type === "repeatable_group") {
    return form[key] ?? question.default_value ?? (question.type === "repeatable_group" ? [] : question.type === "checkboxes" ? [] : "");
  }
  return form[key] ?? question.default_value ?? "";
}

export function setFormValue(form, question, value) {
  const next = { ...form, extra_answers: { ...(form.extra_answers || {}) } };
  if (question.storage === "extra") {
    next.extra_answers = { ...next.extra_answers, [extraAnswerKey(question)]: value };
    return next;
  }
  const key = question.field_key || question.id;
  if (String(key).includes(".")) {
    const [parent, child] = String(key).split(".");
    next[parent] = { ...(form[parent] || {}), [child]: value };
    return next;
  }
  next[key] = value;
  return next;
}

function ruleMatches(rule, form, byId) {
  const parent = byId[rule.field_id];
  const value = parent ? getFormValue(form, parent) : form[rule.field_id];
  const expected = rule.value;
  const op = rule.op || "eq";
  if (op === "includes") {
    if (Array.isArray(value)) return value.includes(expected);
    return String(value || "").includes(String(expected ?? ""));
  }
  if (op === "neq") return String(value ?? "") !== String(expected ?? "");
  return String(value ?? "") === String(expected ?? "");
}

export function isQuestionVisible(question, form, byId, seen = new Set()) {
  const vis = question?.visibility;
  const rules = vis?.rules || (vis?.field_id ? [{ field_id: vis.field_id, op: vis.op || "eq", value: vis.value }] : []);
  if (!rules.length) return true;
  if (seen.has(question.id)) return false;
  seen.add(question.id);
  const results = rules.map((rule) => {
    const parent = byId[rule.field_id];
    if (parent && !isQuestionVisible(parent, form, byId, seen)) return false;
    return ruleMatches(rule, form, byId);
  });
  return vis?.logic === "or" ? results.some(Boolean) : results.every(Boolean);
}

export function parseSkills(text) {
  const seen = new Set();
  const result = [];
  for (const part of String(text || "").split(",")) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(trimmed);
  }
  return result;
}

export const ALUMNI_HIDDEN_QUESTIONS = ["primary_guardian", "guardian_degree_completed"];

export function omitQuestions(schema, hiddenIds = []) {
  const hidden = new Set(hiddenIds || []);
  if (!schema || !hidden.size) return schema;
  const sections = (schema.sections || []).map((section) => ({
    ...section,
    subsections: (section.subsections || []).map((sub) => ({
      ...sub,
      questions: (sub.questions || []).filter((question) => !hidden.has(question.id) && !hidden.has(question.field_key)),
    })).filter((sub) => (sub.questions || []).length),
  })).filter((section) => (section.subsections || []).some((sub) => (sub.questions || []).length));
  return { ...schema, sections };
}

function credentialRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => {
    const rawDetail = String(row?.detail || "").trim();
    const yearOnly = /^(?:19|20)\d{2}$/.test(rawDetail);
    const year = String(row?.year || row?.awarded_on || row?.held_on || (yearOnly ? rawDetail : "")).trim();
    return {
      name: String(row?.name || row?.title || "").trim(),
      detail: yearOnly ? "" : rawDetail,
      year,
      awarding_body: String(row?.awarding_body || "").trim(),
      location: String(row?.location || "").trim(),
      organizer: String(row?.organizer || "").trim(),
      issuer: String(row?.issuer || "").trim(),
      description: String(row?.description || "").trim(),
    };
  }).filter((row) => row.name);
}

export function emptyFormFromSchema(schema, initial = {}) {
  const form = {
    first_name: "",
    middle_name: "",
    last_name: "",
    husband_surname: "",
    country: "Philippines",
    degree: "",
    year_graduated: "",
    primary_guardian: "",
    guardian_degree_completed: "",
    ever_employed: "",
    time_to_first_job: "",
    first_related: "",
    find_job: "",
    other_find_job: "",
    is_currently_employed: "",
    present_job_is_first: "",
    reason_past: [],
    reason_past_other: "",
    reason_current: [],
    reason_current_other: "",
    first_occ: "",
    first_emp: "",
    first_sal: "",
    first_stat: "",
    pres_occ: "",
    pres_emp: "",
    pres_head: "",
    pres_head_email: "",
    pres_stay: "",
    present_related_degree: "",
    enroll_further_studies: "No",
    further_studies: [],
    participated_seminars: "",
    seminars_helpful: "",
    mentoring_rating: "",
    advocacy_rating: "",
    volunteering_rating: "",
    engagement_desc: "",
    curriculum_suggestions: {
      include_new_courses: "",
      develop_competencies: "",
      improve_teaching_methods: "",
      increase_ojt_duration: "",
      other: "",
    },
    skills: [],
    extra_answers: {},
    ...initial,
    curriculum_suggestions: {
      include_new_courses: "",
      develop_competencies: "",
      improve_teaching_methods: "",
      increase_ojt_duration: "",
      other: "",
      ...(initial?.curriculum_suggestions || {}),
    },
    extra_answers: { ...(initial?.extra_answers || {}) },
    enroll_further_studies: initial?.enroll_further_studies || "No",
    further_studies: (initial?.further_studies || initial?.further_studies_raw || []).map((row) => ({
      course_degree: row.course_degree || row["Course/Degree"] || "",
      school: row.school || row.School || "",
      institution_address: row.institution_address || row["Address of Institution"] || "",
      year_enrolled: row.year_enrolled || row["Year of First Enrollment"] || "",
      scholarship: row.scholarship || row.Scholarship || "",
      is_graduated: row.is_graduated || row.Graduated || "No",
    })),
    skills: initial?.skills || [],
    certifications: credentialRows(initial?.certifications),
    seminars: credentialRows(initial?.seminars),
    awards: credentialRows(initial?.awards),
    report_certifications: credentialReportChoice(initial?.report_certifications, initial?.certifications),
    report_seminars: credentialReportChoice(initial?.report_seminars, initial?.seminars),
    report_awards: credentialReportChoice(initial?.report_awards, initial?.awards),
    reason_past: initial?.reason_past || [],
    reason_current: initial?.reason_current || [],
  };
  for (const { question } of flattenQuestions(schema)) {
    if (question.storage === "extra") {
      const key = extraAnswerKey(question);
      if (form.extra_answers[key] == null) form.extra_answers[key] = question.default_value ?? "";
    }
  }
  return form;
}

