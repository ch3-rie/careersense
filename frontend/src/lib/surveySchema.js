export const QUESTION_TYPES = [
  ["short_answer", "Short Answer"],
  ["paragraph", "Paragraph"],
  ["multiple_choice", "Multiple Choice"],
  ["checkboxes", "Checkboxes"],
  ["dropdown", "Dropdown"],
  ["scale", "Linear Scale"],
  ["yes_no", "Yes/No"],
  ["date", "Date"],
  ["number", "Number"],
];

export const SYSTEM_FIELD_KEYS = new Set([
  "first_name",
  "last_name",
  "degree",
  "year_graduated",
  "ever_employed",
  "is_currently_employed",
  "first_occ",
  "pres_occ",
  "present_job_is_first",
]);

export const ALIGNMENT_FIELD_KEYS = new Set([
  "first_occ",
  "pres_occ",
  "is_currently_employed",
  "present_job_is_first",
  "ever_employed",
]);

export function cloneSurvey(schema) {
  return JSON.parse(JSON.stringify(schema || { sections: [] }));
}

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

export function visibilitySummary(question, byId) {
  const rules = question?.visibility?.rules || [];
  if (!rules.length) return "";
  const parts = rules.map((rule) => {
    const parent = byId[rule.field_id];
    const label = parent?.label || rule.field_id;
    const op = rule.op === "neq" ? "is not" : rule.op === "includes" ? "includes" : "is";
    return `"${label}" ${op} "${rule.value}"`;
  });
  const join = question.visibility?.logic === "or" ? " or " : " and ";
  return `Show when ${parts.join(join)}`;
}

export function wouldCreateCycle(schema, questionId, fieldId) {
  if (!fieldId || fieldId === questionId) return true;
  const byId = questionIndex(schema);
  const seen = new Set([questionId]);
  let current = byId[fieldId];
  while (current) {
    if (seen.has(current.id)) return true;
    seen.add(current.id);
    const nextId = current.visibility?.rules?.[0]?.field_id || current.visibility?.field_id;
    if (!nextId) break;
    current = byId[nextId];
  }
  return false;
}

export function newQuestionId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return `q_${crypto.randomUUID()}`;
  return `q_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export function createQuestion(partial = {}) {
  const id = partial.id || newQuestionId();
  return {
    field_key: "",
    label: "Untitled question",
    description: "",
    type: "short_answer",
    required: false,
    options: [],
    placeholder: "",
    default_value: "",
    system: false,
    system_tag: null,
    storage: "extra",
    visibility: null,
    repeatable: null,
    validation: {},
    ...partial,
    id,
    extra_key: partial.extra_key || id,
    field_key: partial.field_key || "",
    storage: partial.storage || "extra",
  };
}

export function duplicateQuestion(question) {
  const id = newQuestionId();
  return createQuestion({
    ...question,
    id,
    extra_key: id,
    field_key: "",
    storage: "extra",
    system: false,
    system_tag: null,
    label: `${question.label || "Untitled question"} (copy)`,
  });
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
      year_enrolled: row.year_enrolled || row["Year of First Enrollment"] || "",
      scholarship: row.scholarship || row.Scholarship || "",
      is_graduated: row.is_graduated || row.Graduated || "No",
    })),
    skills: initial?.skills || [],
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

export function moveItem(list, from, to) {
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function findQuestionLocation(schema, questionId) {
  for (let s = 0; s < (schema?.sections || []).length; s += 1) {
    const section = schema.sections[s];
    for (let b = 0; b < (section.subsections || []).length; b += 1) {
      const subsection = section.subsections[b];
      const q = (subsection.questions || []).findIndex((item) => item.id === questionId);
      if (q >= 0) return { sectionIndex: s, subsectionIndex: b, questionIndex: q, section, subsection, question: subsection.questions[q] };
    }
  }
  return null;
}

export const CORE_SECTION_KEYS = ["general", "employment", "studies", "feedback"];
export const CHOICE_TYPES = new Set(["multiple_choice", "checkboxes", "dropdown", "scale"]);

export function findSectionLocation(schema, sectionId) {
  const sectionIndex = (schema?.sections || []).findIndex((section) => section.id === sectionId);
  if (sectionIndex < 0) return null;
  return { sectionIndex, section: schema.sections[sectionIndex] };
}

export function createSection(partial = {}) {
  const id = partial.id || `section_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
  return {
    id,
    key: partial.key || id,
    name: partial.name || "Untitled section",
    description: partial.description || "",
    subsections: partial.subsections || [
      { id: `${id}_main`, name: "", description: "", questions: [] },
    ],
  };
}

export function optionText(item) {
  return typeof item === "object" ? String(item.label ?? item.value ?? "") : String(item ?? "");
}

export function cleanOptions(options = []) {
  return options
    .map((item) => {
      if (typeof item === "object") {
        const value = String(item.value ?? item.label ?? "").trim();
        const label = String(item.label ?? item.value ?? "").trim();
        if (!value && !label) return null;
        return { ...item, value: value || label, label: label || value };
      }
      const text = String(item ?? "").trim();
      return text || null;
    })
    .filter(Boolean);
}

export function optionsForType(type, existing = []) {
  const cleaned = cleanOptions(existing);
  if (!CHOICE_TYPES.has(type)) return [];
  if (cleaned.length) return cleaned;
  if (type === "scale") return ["1", "2", "3", "4", "5"];
  return ["Option 1", "Option 2"];
}

export function schemaIssues(schema) {
  const issues = [];
  for (const { question } of flattenQuestions(schema)) {
    if (!String(question.label || "").trim()) {
      issues.push("Every question needs a title.");
      continue;
    }
    if (CHOICE_TYPES.has(question.type)) {
      const opts = cleanOptions(question.options).map(optionValue).filter(Boolean);
      if (opts.length < 2) {
        issues.push(`"${question.label}" needs at least two choices.`);
      }
    }
  }
  return [...new Set(issues)];
}

export function systemWarning(question) {
  const key = question?.field_key || question?.id;
  if (question?.system_tag === "alignment" || ALIGNMENT_FIELD_KEYS.has(key)) {
    return "This field is used by CareerSense for registration validation, reporting, or career alignment. Changing or removing it may affect other system functions.";
  }
  if (question?.system_tag === "identity" || SYSTEM_FIELD_KEYS.has(key)) {
    return "This field is used by CareerSense for registration validation, reporting, or career alignment. Changing or removing it may affect other system functions.";
  }
  if (question?.type === "repeatable_group") {
    return "This group stores multiple further-study records. Removing it will hide the program list on new responses; historical program records stay saved.";
  }
  return "";
}
