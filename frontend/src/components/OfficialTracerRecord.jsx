import { useMemo, useState } from "react";
import { InfoGrid, ProfileActivityReview, StatusBadge } from "./AdminReview";
import GtsForm from "./GtsForm";
import { formatLongDate, formatTime } from "../lib/format";
import {
  extraAnswerKey,
  flattenQuestions,
  getFormValue,
  isQuestionVisible,
  optionLabel,
  optionValue,
  questionIndex,
} from "../lib/surveySchema";

const UNANSWERED = "—";
const SKIPPED_KEYS = new Set([
  "extra_answers",
  "_extra_labels",
  "_survey_version",
  "soc_code",
  "soc_description",
  "soc_category",
]);

export function recordName(record) {
  const saved = String(record?.name || "").trim();
  if (saved) return saved;
  const data = record?.data || {};
  const fromSurvey = [data.first_name, data.middle_name, data.last_name]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join(" ");
  return fromSurvey;
}

export function recordStudentNumber(record) {
  return String(record?.student_id || record?.data?.student_id || record?.data?.student_number || "").trim();
}

function isBlank(value) {
  if (value == null) return true;
  if (typeof value === "string") return !value.trim();
  if (typeof value === "number" || typeof value === "boolean") return false;
  if (Array.isArray(value)) return value.length === 0 || value.every(isBlank);
  if (typeof value === "object") return !Object.values(value).some((item) => item !== false && !isBlank(item));
  return false;
}

function optionText(options, value) {
  const match = (options || []).find((item) => optionValue(item) === String(value));
  return match ? optionLabel(match) : String(value);
}

function humanize(key, labels) {
  const known = labels?.[key] || labels?.[String(key)];
  if (known) return known;
  return String(key || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function AnswerValue({ value }) {
  const [open, setOpen] = useState(false);
  if (value == null || value === UNANSWERED) return <p className="tracer-unanswered">{UNANSWERED}</p>;
  if (Array.isArray(value)) {
    return (
      <div className="tracer-repeat-stack">
        {value.map((row, index) => (
          <article className="tracer-repeat" key={row.key || index}>
            {row.title ? <strong>{row.title}</strong> : null}
            <InfoGrid items={row.items} />
          </article>
        ))}
      </div>
    );
  }
  const text = String(value);
  if (text.length < 240) return <p className="tracer-answer">{text}</p>;
  return (
    <div>
      <p className={`tracer-answer ${open ? "" : "is-clamped"}`}>{text}</p>
      <button className="qa-more" type="button" onClick={() => setOpen((current) => !current)}>
        {open ? "Show less" : "Show more"}
      </button>
    </div>
  );
}

function formatScalar(question, value) {
  if (isBlank(value)) return UNANSWERED;
  if (Array.isArray(value)) {
    const labels = value
      .map((item) => (item && typeof item === "object" ? "" : optionText(question?.options, item)))
      .filter(Boolean);
    return labels.length ? labels.join(", ") : UNANSWERED;
  }
  if (typeof value === "object") {
    const selected = Object.entries(value)
      .filter(([, item]) => item && item !== false)
      .map(([key]) => optionText(question?.options, key));
    return selected.length ? selected.join(", ") : UNANSWERED;
  }
  return optionText(question?.options, value);
}

function repeatableAnswer(question, value) {
  const rows = Array.isArray(value) ? value.filter((row) => row && typeof row === "object" && !isBlank(row)) : [];
  if (!rows.length) return UNANSWERED;
  const fields = question?.repeatable?.fields || [];
  return rows.map((row, index) => {
    const items = fields.length
      ? fields.map((field) => ({
          label: field.label || humanize(field.id),
          value: formatScalar(field, row[field.id]),
        }))
      : Object.entries(row)
          .filter(([key]) => !key.startsWith("_"))
          .map(([key, item]) => ({ label: humanize(key), value: formatScalar(null, item) }));
    const title = fields.length > 1 ? `Entry ${index + 1}` : "";
    return { key: `${question?.id || "row"}-${index}`, title, items };
  });
}

function answerFor(question, form) {
  const value = getFormValue(form, question);
  if (question?.type === "repeatable_group") return repeatableAnswer(question, value);
  return formatScalar(question, value);
}

function coveredKeys(schema) {
  const dataKeys = new Set(SKIPPED_KEYS);
  const extraKeys = new Set(["_extra_labels", "_survey_version"]);
  flattenQuestions(schema).forEach(({ question }) => {
    if (question.storage === "extra") {
      extraKeys.add(String(extraAnswerKey(question)));
      if (question.id) extraKeys.add(String(question.id));
      return;
    }
    const key = String(question.field_key || question.id || "");
    if (!key) return;
    if (key.includes(".")) dataKeys.add(key.split(".")[0]);
    dataKeys.add(key);
  });
  return { dataKeys, extraKeys };
}

function savedForm(record) {
  const data = record?.data || {};
  return {
    ...data,
    extra_answers: {
      ...(data.extra_answers || {}),
      ...(record?.extra_answers || {}),
    },
  };
}

function displayForm(record, schema) {
  const form = savedForm(record);
  form.extra_answers = { ...(form.extra_answers || {}) };
  flattenQuestions(schema).forEach(({ question }) => {
    if (question.storage === "extra") {
      const key = extraAnswerKey(question);
      if (key != null && form.extra_answers[key] == null) form.extra_answers[key] = "";
      return;
    }
    const key = question.field_key || question.id;
    if (!key || String(key).includes(".")) return;
    if (!(key in form)) form[key] = question.type === "checkboxes" || question.type === "repeatable_group" ? [] : "";
  });
  return form;
}

function formatLoose(value) {
  if (isBlank(value)) return UNANSWERED;
  if (Array.isArray(value)) {
    if (value.every((item) => item == null || typeof item !== "object")) {
      const labels = value.map((item) => String(item ?? "").trim()).filter(Boolean);
      return labels.length ? labels.join(", ") : UNANSWERED;
    }
    return value
      .map((row, index) => {
        const parts = Object.entries(row || {})
          .filter(([key, item]) => !String(key).startsWith("_") && !isBlank(item))
          .map(([key, item]) => `${humanize(key)}: ${formatLoose(item)}`);
        return parts.length ? `Entry ${index + 1}: ${parts.join("; ")}` : "";
      })
      .filter(Boolean)
      .join("\n") || UNANSWERED;
  }
  if (typeof value === "object") {
    const lines = Object.entries(value)
      .filter(([key, item]) => !String(key).startsWith("_") && item !== false && !isBlank(item))
      .map(([key, item]) => `${humanize(key)}: ${formatLoose(item)}`);
    return lines.length ? lines.join("\n") : UNANSWERED;
  }
  return String(value);
}

function leftoverItems(record, schema, labels) {
  const form = savedForm(record);
  const { dataKeys, extraKeys } = coveredKeys(schema);
  const items = [];
  Object.entries(form).forEach(([key, value]) => {
    if (dataKeys.has(key) || key.startsWith("_")) return;
    const formatted = formatLoose(value);
    if (formatted === UNANSWERED) return;
    items.push({ label: humanize(key, labels), value: formatted });
  });
  Object.entries(form.extra_answers || {}).forEach(([key, value]) => {
    if (extraKeys.has(key) || key.startsWith("_")) return;
    const formatted = formatLoose(value);
    if (formatted === UNANSWERED) return;
    items.push({ label: humanize(key, { ...(form._extra_labels || {}), ...(labels || {}) }), value: formatted });
  });
  return items;
}

function schemaSections(record, schema) {
  const form = displayForm(record, schema);
  const byId = questionIndex(schema);
  return (schema?.sections || [])
    .map((section) => {
      const subsections = (section.subsections || [])
        .map((subsection) => {
          const questions = (subsection.questions || []).filter((question) => {
            const visible = isQuestionVisible(question, form, byId);
            const value = answerFor(question, form);
            return visible || (value !== UNANSWERED && !isBlank(getFormValue(form, question)));
          });
          if (!questions.length) return null;
          return { id: subsection.id, name: subsection.name, description: subsection.description, questions };
        })
        .filter(Boolean);
      if (!subsections.length) return null;
      return { id: section.id || section.key, name: section.name, description: section.description, subsections };
    })
    .filter(Boolean);
}

function furtherStudyItems(record, schema) {
  const studies = Array.isArray(record?.further_studies) ? record.further_studies : [];
  if (!studies.length) return [];
  const form = savedForm(record);
  const alreadyShown = flattenQuestions(schema).some((item) => {
    const question = item.question;
    if (question?.type !== "repeatable_group") return false;
    const key = String(question.field_key || question.id || "");
    return /stud/i.test(key) && !isBlank(getFormValue(form, question));
  });
  if (alreadyShown) return [];
  return studies.map((row, index) => ({
    key: row.id || index,
    title: row.course_degree || "Further study",
    items: [
      { label: "School", value: row.school || UNANSWERED },
      { label: "Address of Institution", value: row.institution_address || UNANSWERED },
      { label: "Year enrolled", value: row.year_enrolled || UNANSWERED },
      { label: "Scholarship", value: row.scholarship || UNANSWERED },
      { label: "Graduated", value: row.is_graduated || UNANSWERED },
    ],
  }));
}

function QuestionList({ questions, form }) {
  return (
    <div className="tracer-fields">
      {questions.map((question) => (
        <div className="tracer-field" key={question.id}>
          <p className="tracer-label">{question.label || humanize(question.id)}</p>
          <AnswerValue value={answerFor(question, form)} />
        </div>
      ))}
    </div>
  );
}

export function RecordDossier({ record, schema, questionLabels, surveyLayout = false }) {
  const surveyInitial = useMemo(() => (record ? savedForm(record) : null), [record]);
  if (!record) return null;
  const form = schema?.sections?.length ? displayForm(record, schema) : savedForm(record);
  const sections = schema?.sections?.length ? schemaSections(record, schema) : [];
  const extras = leftoverItems(record, schema, questionLabels);
  const studies = furtherStudyItems(record, schema);
  const name = recordName(record);
  const studentNumber = recordStudentNumber(record);
  const email = record.email || "";
  const status = record.alignment || "Unknown";
  const support = [record.job_title, record.soc_description].filter(Boolean).join(" → ");
  const classification = [record.soc_code, record.soc_category].filter(Boolean).join(" · ");

  return (
    <div className="record-sections">
      <section className="detail-section">
        <h2>Alumni Information</h2>
        <InfoGrid
          items={[
            { label: "Name", value: name || UNANSWERED },
            { label: "Student number", value: studentNumber || UNANSWERED },
            { label: "Email address", value: email ? <a href={`mailto:${email}`}>{email}</a> : UNANSWERED },
          ]}
        />
      </section>

      <section className="detail-section">
        <h2>Submission Details</h2>
        <InfoGrid
          items={[
            { label: "Submitted date", value: formatLongDate(record.submitted_at) },
            { label: "Submitted time", value: formatTime(record.submitted_at) },
          ]}
        />
      </section>

      <section className="detail-section">
        <h2>Official Tracer Record</h2>
        {surveyLayout && schema?.sections?.length ? (
          <GtsForm variant="review" browse schema={schema} initial={surveyInitial} />
        ) : sections.length ? (
          sections.map((section) => (
            <div className="tracer-section" key={section.id}>
              <h3>{section.name || "Survey section"}</h3>
              {section.description ? <p className="muted tracer-section-note">{section.description}</p> : null}
              {section.subsections.map((subsection) => (
                <div className="tracer-subsection" key={subsection.id}>
                  {subsection.name ? <h4>{subsection.name}</h4> : null}
                  {subsection.description ? <p className="muted tracer-section-note">{subsection.description}</p> : null}
                  <QuestionList questions={subsection.questions} form={form} />
                </div>
              ))}
            </div>
          ))
        ) : extras.length ? null : (
          <p className="muted">No saved survey answers were found on this submission.</p>
        )}
        {studies.length ? (
          <div className="tracer-section">
            <h3>Further Studies</h3>
            <AnswerValue value={studies} />
          </div>
        ) : null}
        {!surveyLayout && extras.length ? (
          <div className="tracer-section">
            <h3>Additional saved answers</h3>
            <div className="tracer-fields">
              {extras.map((item) => (
                <div className="tracer-field" key={item.label}>
                  <p className="tracer-label">{item.label}</p>
                  <AnswerValue value={item.value} />
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {!surveyLayout && record.profile_activity ? (
        <section className="detail-section">
          <h2>Profile Activity</h2>
          <ProfileActivityReview activity={record.profile_activity} />
        </section>
      ) : null}

      <section className="detail-section record-alignment">
        <h2>Employment Alignment</h2>
        <div className="alignment-summary">
          <div>
            {surveyLayout ? null : <p className="tracer-label">Classification</p>}
            <StatusBadge kind="alignment" value={status} />
            {support ? <p>{support}</p> : null}
            {classification ? <p>{classification}</p> : null}
          </div>
        </div>
      </section>
    </div>
  );
}
