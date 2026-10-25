import { useEffect, useMemo, useRef, useState } from "react";
import { AlignmentHint, SubmitConfirm } from "./AuthFlow";
import { DateField } from "./DateField";
import { CalendarIcon, FileTextIcon, GraduationIcon, InfoIcon, StarIcon } from "./icons";
import { Alert, CheckGroup, Dialog, Field, RadioChoiceList, TabList } from "./ui";
import {
  emptyFormFromSchema,
  flattenQuestions,
  getFormValue,
  isQuestionVisible,
  optionLabel,
  optionValue,
  parseSkills,
  questionIndex,
  setFormValue,
} from "../lib/surveySchema";
import { resumeGuidance } from "../lib/resumeGuidance";
import {
  BLANK_PROGRAM,
  STUDIES_SECTION_TITLE,
  credentialIsPopulated,
  credentialReportChoice,
  isSuggestedCredential,
  isSuggestedProgram,
  programIsPopulated,
} from "../lib/studiesSection";
import { omitQuestions } from "../lib/surveySchema";
import { showToast } from "../lib/toasts";

function T(value) {
  return value;
}

function questionIsRequired(question, form) {
  if (question.required) return true;
  const needsCurrentTitle = form.is_currently_employed === "Yes";
  if (question.id === "pres_occ") return needsCurrentTitle && form.present_job_is_first === "No";
  if (question.id === "first_occ") return needsCurrentTitle && form.present_job_is_first !== "No";
  return false;
}

function repeatableFieldErrors(question, rows) {
  const fields = (question.repeatable?.fields || []).filter((field) => field.required);
  const next = {};
  (Array.isArray(rows) ? rows : []).forEach((row, index) => {
    fields.forEach((field) => {
      if (!String(row?.[field.id] || "").trim()) {
        next[`${question.id}:${index}:${field.id}`] = `Please answer: ${field.label}`;
      }
    });
  });
  return next;
}

function coerceValue(question, value) {
  const type = question.type || "short_answer";
  if (type === "checkboxes") {
    if (Array.isArray(value)) return value;
    if (value == null || value === "") return [];
    return [value];
  }
  if (Array.isArray(value)) return value.join(", ");
  if (value == null) return "";
  return value;
}

function questionHelp(question, form) {
  if (question.id === "present_job_is_first") {
    if (form.present_job_is_first === "Yes") {
      return "Your first occupation is also saved as your current occupation.";
    }
    if (form.present_job_is_first === "No") {
      return "Enter your present job separately from your first job.";
    }
    return "If this is still your first job, that occupation is saved as your current one.";
  }
  if (question.id === "first_occ" && form.present_job_is_first === "Yes") {
    return "Also saved as your current occupation.";
  }
  if (question.id === "first_emp" && form.present_job_is_first === "Yes") {
    return "Also saved as your current employer.";
  }
  if (question.id === "pres_occ") {
    return "Saved as your current occupation.";
  }
  if (question.id === "pres_emp") {
    return "Saved as your current employer.";
  }
  return question.description || "";
}

function controlFor(question, value, onChange, disabled, error, required) {
  const type = question.type || "short_answer";
  const placeholder = question.placeholder || "";
  const options = question.options || [];
  const rules = question.validation || {};
  value = coerceValue(question, value);
  if (type === "paragraph") {
    const tall = question.id === "engagement_desc";
    return (
      <textarea
        rows={tall ? 6 : 4}
        className={tall ? "is-tall" : undefined}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        minLength={rules.min_length || undefined}
        maxLength={rules.max_length || undefined}
      />
    );
  }
  if (type === "yes_no") {
    return (
      <RadioChoiceList
        name={question.id}
        value={value}
        onChange={onChange}
        disabled={disabled}
        error={error}
        options={[
          { value: "Yes", label: "Yes" },
          { value: "No", label: "No" },
        ]}
      />
    );
  }
  if (type === "multiple_choice" || type === "scale") {
    const scale = options.length ? options : type === "scale" ? ["1", "2", "3", "4", "5"] : [];
    return (
      <RadioChoiceList
        name={question.id}
        value={value}
        onChange={onChange}
        disabled={disabled}
        error={error}
        options={scale.map((opt) => ({ value: optionValue(opt), label: optionLabel(opt) }))}
      />
    );
  }
  if (type === "dropdown") {
    const scale = options;
    return (
      <select value={value || ""} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
        <option value="">{T("Select")}</option>
        {scale.map((opt) => {
          const val = optionValue(opt);
          return <option key={val} value={val}>{T(optionLabel(opt))}</option>;
        })}
      </select>
    );
  }
  if (type === "checkboxes") {
    const selected = Array.isArray(value) ? value : [];
    return (
      <CheckGroup legend={question.label} required={required} error={error}>
        <div className="choice-list">
          {options.map((opt) => {
            const val = optionValue(opt);
            return (
              <label key={val} className={`choice-option ${selected.includes(val) ? "is-selected" : ""}`}>
                <input
                  type="checkbox"
                  checked={selected.includes(val)}
                  disabled={disabled}
                  onChange={() => onChange(selected.includes(val) ? selected.filter((item) => item !== val) : [...selected, val])}
                />
                <span className="choice-option-text">{optionLabel(opt)}</span>
              </label>
            );
          })}
        </div>
      </CheckGroup>
    );
  }
  if (type === "date") {
    return <DateField value={value || ""} placeholder={placeholder || undefined} onChange={(e) => onChange(e.target.value)} disabled={disabled} />;
  }
  if (type === "number") {
    return (
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        min={rules.min ?? undefined}
        max={rules.max ?? undefined}
      />
    );
  }
  if (type === "email") {
    return <input type="email" value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} disabled={disabled} />;
  }
  return <input value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} disabled={disabled} />;
}

const CREDENTIAL_GROUPS = [
  {
    key: "certifications",
    title: "Certifications",
    entryLabel: "Certification",
    flag: "report_certifications",
    question: "Do you have certifications?",
    icon: FileTextIcon,
    summary: "Professional credentials and certifications.",
    empty: "No certifications added.",
    addLabel: "Add certification",
    removeTitle: "Remove this certification?",
    blank: { name: "", awarding_body: "", detail: "", year: "" },
    fields: [
      ["name", "Name", "Certification name"],
      ["awarding_body", "Awarding body", "Awarding organization"],
      ["year", "Date or year awarded", "Year or date"],
    ],
  },
  {
    key: "seminars",
    title: "Seminars Attended",
    entryLabel: "Seminar",
    flag: "report_seminars",
    question: "Did you attend seminars?",
    icon: CalendarIcon,
    summary: "Seminars and training you attended.",
    empty: "No seminars added.",
    addLabel: "Add seminar",
    removeTitle: "Remove this seminar?",
    blank: { name: "", location: "", organizer: "", detail: "", year: "" },
    fields: [
      ["name", "Name", "Seminar name"],
      ["location", "Location of Seminar", "Where it was held"],
      ["organizer", "Organizer", "Who organized it"],
      ["year", "Date or year", "Year or date"],
    ],
  },
  {
    key: "awards",
    title: "Awards and Achievements",
    entryLabel: "Award",
    flag: "report_awards",
    question: "Have you received awards or achievements?",
    icon: StarIcon,
    summary: "Awards or achievements you received.",
    empty: "No awards or achievements added.",
    addLabel: "Add award or achievement",
    removeTitle: "Remove this award?",
    blank: { name: "", issuer: "", detail: "", year: "", description: "" },
    fields: [
      ["name", "Title", "Award title"],
      ["issuer", "Awarded by", "Awarding organization"],
      ["year", "Date or year", "Year or date"],
      ["description", "Description", "What it recognizes"],
    ],
  },
];

function findQuestion(section, id) {
  for (const sub of section?.subsections || []) {
    const found = (sub.questions || []).find((question) => question.id === id);
    if (found) return found;
  }
  return null;
}

function takeIds(questions, ids, used) {
  const picked = [];
  for (const id of ids) {
    const found = questions.find((question) => question.id === id);
    if (!found) continue;
    picked.push(found);
    used.add(found.id);
  }
  return picked;
}

function isCurriculumQuestion(question) {
  const id = String(question?.id || "");
  const key = String(question?.field_key || "");
  return id.startsWith("curriculum_suggestions") || key.startsWith("curriculum_suggestions");
}

const JOB_PARTNERS = {
  first_occ: "first_emp",
  pres_occ: "pres_emp",
  pres_head: "pres_head_email",
};

function Guidance({ children }) {
  if (!children) return null;
  return (
    <p className="resume-guidance" role="note">
      <InfoIcon size={16} />
      <span>{children}</span>
    </p>
  );
}

function credentialValue(row, field) {
  if (field === "awarding_body") return row.awarding_body || row.detail || "";
  if (field === "location") {
    if (row.location) return row.location;
    if (row.detail && row.detail !== row.organizer && row.detail !== row.issuer) return row.detail;
    return "";
  }
  if (field === "organizer") return row.organizer || "";
  if (field === "issuer") return row.issuer || row.detail || "";
  return row[field] || "";
}

function StudiesSection({
  form,
  resume,
  disabled,
  showLead,
  fieldErrors,
  onEnroll,
  onEditDegree,
  onChangeProgram,
  onAddProgram,
  onRemoveProgram,
  onChangeCredential,
  onReport,
}) {
  const [pending, setPending] = useState(null);
  const enrolled = form.enroll_further_studies === "Yes";
  const programs = Array.isArray(form.further_studies) ? form.further_studies : [];
  const degree = String(form.degree || "").trim();
  const year = String(form.year_graduated || "").trim();
  const enrollNote = resumeGuidance("enroll_further_studies", form.enroll_further_studies || "No", resume);
  const programNote = enrolled ? resumeGuidance("further_studies", programs, resume) : "";
  const programHasError = Object.keys(fieldErrors).some((key) => key === "further_studies" || key.startsWith("further_studies:"));
  const degreeNote = resumeGuidance("degree", form.degree, resume);
  const yearNote = resumeGuidance("year_graduated", form.year_graduated, resume);

  function requestRemove(kind, index, row) {
    const populated = kind === "program" ? programIsPopulated(row) : credentialIsPopulated(row, kind);
    if (!populated) {
      if (kind === "program") onRemoveProgram(index);
      else onChangeCredential(kind, index, null, null);
      return;
    }
    setPending({ kind, index });
  }

  function confirmRemove() {
    if (!pending) return;
    if (pending.kind === "program") onRemoveProgram(pending.index);
    else onChangeCredential(pending.kind, pending.index, null, null);
    setPending(null);
  }

  const pendingGroup = CREDENTIAL_GROUPS.find((group) => group.key === pending?.kind);

  return (
    <div className="studies-section">
      {showLead ? (
        <header className="studies-lead">
          <h3>{STUDIES_SECTION_TITLE}</h3>
          <p>Report additional education, certifications, seminars, and awards.</p>
        </header>
      ) : null}

      <article className="studies-degree">
        <span className="studies-degree-icon" aria-hidden="true"><GraduationIcon size={20} /></span>
        <div className="studies-degree-copy">
          <p className="studies-kicker">From General Information</p>
          <strong>{degree || "Degree not available"}</strong>
          <p>{year ? `Year graduated: ${year}` : "Year graduated: Not available"}</p>
        </div>
        {onEditDegree ? (
          <button type="button" className="btn btn-outline btn-sm" onClick={onEditDegree}>
            Edit in General Information
          </button>
        ) : null}
      </article>
      <Guidance>{fieldErrors.degree ? "" : degreeNote}</Guidance>
      <Guidance>{fieldErrors.year_graduated ? "" : yearNote}</Guidance>

      <section className="studies-block" aria-labelledby="studies-further-heading">
        <div className="studies-block-head">
          <span className="studies-degree-icon" aria-hidden="true"><GraduationIcon size={18} /></span>
          <div>
            <h3 id="studies-further-heading">Further studies</h3>
            <p>Programs you started after your bachelor's degree.</p>
          </div>
        </div>
        <CheckGroup
          legend="Did you enroll in further studies after graduation?"
          error={fieldErrors.enroll_further_studies}
          note={enrollNote}
        >
          <RadioChoiceList
            name="enroll_further_studies"
            value={form.enroll_further_studies || "No"}
            onChange={onEnroll}
            disabled={disabled}
            options={[{ value: "Yes", label: "Yes" }, { value: "No", label: "No" }]}
          />
        </CheckGroup>
        {enrolled ? (
          <div className="studies-programs">
            {programs.length ? programs.map((row, index) => (
              <article className="studies-program" key={`program-${index}`}>
                <div className="studies-card-head">
                  <div className="studies-card-title">
                    <strong>Program {index + 1}</strong>
                    {isSuggestedProgram(row, resume) ? <span className="studies-suggested">Suggested from your resume</span> : null}
                  </div>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    disabled={disabled}
                    aria-label={`Remove program ${index + 1}`}
                    onClick={() => requestRemove("program", index, row)}
                  >
                    Remove
                  </button>
                </div>
                <div className="studies-grid">
                  <Field label="Institution" required error={fieldErrors[`further_studies:${index}:school`]}>
                    <input value={row.school || ""} disabled={disabled} placeholder="School or university" onChange={(e) => onChangeProgram(index, "school", e.target.value)} />
                  </Field>
                  <Field label="Address of Institution" error={fieldErrors[`further_studies:${index}:institution_address`]}>
                    <input value={row.institution_address || ""} disabled={disabled} placeholder="School or institution address" onChange={(e) => onChangeProgram(index, "institution_address", e.target.value)} />
                  </Field>
                  <div className="studies-span">
                    <Field label="Program" required error={fieldErrors[`further_studies:${index}:course_degree`]}>
                      <input value={row.course_degree || ""} disabled={disabled} placeholder="Program or degree" onChange={(e) => onChangeProgram(index, "course_degree", e.target.value)} />
                    </Field>
                  </div>
                  <div className="studies-pair studies-span">
                    <Field label="Year enrolled" error={fieldErrors[`further_studies:${index}:year_enrolled`]}>
                      <input value={row.year_enrolled || ""} disabled={disabled} inputMode="numeric" placeholder="Year enrolled" onChange={(e) => onChangeProgram(index, "year_enrolled", e.target.value)} />
                    </Field>
                    <Field label="Scholarship" error={fieldErrors[`further_studies:${index}:scholarship`]}>
                      <input value={row.scholarship || ""} disabled={disabled} placeholder="Scholarship, if any" onChange={(e) => onChangeProgram(index, "scholarship", e.target.value)} />
                    </Field>
                  </div>
                  <div className="studies-span">
                    <CheckGroup legend="Graduated">
                      <RadioChoiceList
                        name={`further-graduated-${index}`}
                        value={row.is_graduated || "No"}
                        onChange={(value) => onChangeProgram(index, "is_graduated", value)}
                        disabled={disabled}
                        options={[{ value: "Yes", label: "Yes" }, { value: "No", label: "No" }]}
                      />
                    </CheckGroup>
                  </div>
                </div>
              </article>
            )) : <p className="studies-empty">No programs added yet.</p>}
            <button type="button" className="btn btn-outline" disabled={disabled} onClick={onAddProgram}>
              Add another program
            </button>
            <Guidance>{programHasError ? "" : programNote}</Guidance>
          </div>
        ) : null}
      </section>

      {CREDENTIAL_GROUPS.map((group) => {
        const Icon = group.icon;
        const rows = Array.isArray(form[group.key]) ? form[group.key] : [];
        const reporting = credentialReportChoice(form[group.flag], rows) === "Yes";
        const choiceNote = resumeGuidance(group.flag, reporting ? "Yes" : "No", resume);
        const note = reporting ? resumeGuidance(group.key, rows, resume) : "";
        return (
          <section className="studies-block" key={group.key} aria-labelledby={`studies-${group.key}-heading`}>
            <div className="studies-block-head">
              <span className="studies-degree-icon" aria-hidden="true"><Icon size={18} /></span>
              <div>
                <h3 id={`studies-${group.key}-heading`}>{group.title}</h3>
                <p>{group.summary} Every detail is optional.</p>
              </div>
            </div>
            <CheckGroup legend={group.question} note={choiceNote}>
              <RadioChoiceList
                name={group.flag}
                value={reporting ? "Yes" : "No"}
                onChange={(value) => onReport(group.flag, value)}
                disabled={disabled}
                options={[{ value: "Yes", label: "Yes" }, { value: "No", label: "No" }]}
              />
            </CheckGroup>
            {reporting ? (rows.length ? rows.map((row, index) => (
              <article className="studies-entry" key={`${group.key}-${index}`}>
                <div className="studies-card-head">
                  <div className="studies-card-title">
                    <strong>{group.entryLabel} {index + 1}</strong>
                    {isSuggestedCredential(row, resume, group.key) ? <span className="studies-suggested">Suggested from your resume</span> : null}
                  </div>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    disabled={disabled}
                    aria-label={`Remove ${group.title.toLowerCase()} ${index + 1}`}
                    onClick={() => requestRemove(group.key, index, row)}
                  >
                    Remove
                  </button>
                </div>
                <div className={`studies-fields is-${group.key}`}>
                  {group.fields.map(([field, label, placeholder]) => (
                    <Field label={label} key={field}>
                      {field === "description" ? (
                        <textarea
                          rows={3}
                          maxLength={800}
                          value={credentialValue(row, field)}
                          disabled={disabled}
                          placeholder={placeholder}
                          onChange={(e) => onChangeCredential(group.key, index, field, e.target.value)}
                        />
                      ) : (
                        <input
                          value={credentialValue(row, field)}
                          disabled={disabled}
                          placeholder={placeholder}
                          onChange={(e) => onChangeCredential(group.key, index, field, e.target.value)}
                        />
                      )}
                    </Field>
                  ))}
                </div>
              </article>
            )) : <p className="studies-empty">{group.empty}</p>) : null}
            {reporting ? (
              <button
                type="button"
                className="btn btn-outline"
                disabled={disabled}
                onClick={() => onChangeCredential(group.key, -1, null, group.blank)}
              >
                {group.addLabel}
              </button>
            ) : null}
            <Guidance>{note}</Guidance>
          </section>
        );
      })}

      {pending ? (
        <Dialog
          title={pending.kind === "program" ? "Remove this program?" : pendingGroup?.removeTitle || "Remove this entry?"}
          danger
          confirmLabel="Remove"
          onConfirm={confirmRemove}
          onClose={() => setPending(null)}
        >
          <p>The details in this entry will be removed from your survey answers.</p>
        </Dialog>
      ) : null}
    </div>
  );
}

export default function GtsSchemaForm({
  schema: sourceSchema,
  initial,
  onSubmit,
  submitLabel = "Submit",
  busy,
  extraNotice,
  preview = false,
  readOnly = false,
  closedMessage = "",
  confirmSubmit = false,
  alignmentHint,
  variant,
  resume = null,
  hideQuestionIds = [],
  browse = false,
}) {
  const schema = useMemo(
    () => omitQuestions(sourceSchema, hideQuestionIds),
    [sourceSchema, hideQuestionIds],
  );
  const [tab, setTab] = useState(schema?.sections?.[0]?.key || schema?.sections?.[0]?.id || "general");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [confirming, setConfirming] = useState(false);
  const errorRef = useRef(null);
  const confirmRef = useRef(null);
  const submitLock = useRef(false);
  const [focusTick, setFocusTick] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(() => emptyFormFromSchema(schema, initial));
  const [skillsText, setSkillsText] = useState(() =>
    Array.isArray(initial?.skills) ? initial.skills.join(", ") : String(initial?.skills || "")
  );
  const schemaRef = useRef(schema);
  schemaRef.current = schema;

  const sections = schema?.sections || [];
  const tabs = sections.map((section) => {
    const id = section.key || section.id;
    return [id, id === "studies" ? STUDIES_SECTION_TITLE : section.name];
  });
  const byId = useMemo(() => questionIndex(schema), [schema]);
  const flat = useMemo(() => flattenQuestions(schema), [schema]);
  const questionIdsKey = useMemo(
    () => flattenQuestions(schema).map(({ question }) => question.id).join("|"),
    [schema]
  );

  const tabIds = tabs.map((item) => item[0]);
  const tabKey = tabIds.join("|");

  useEffect(() => {
    if (preview) return undefined;
    setForm(emptyFormFromSchema(schemaRef.current, initial));
    setSkillsText(Array.isArray(initial?.skills) ? initial.skills.join(", ") : String(initial?.skills || ""));
    return undefined;
  }, [initial, preview]);

  useEffect(() => {
    if (preview) return undefined;
    setForm((prev) => emptyFormFromSchema(schemaRef.current, prev));
    return undefined;
  }, [questionIdsKey, preview]);

  useEffect(() => {
    if (tabIds.length && !tabIds.includes(tab)) setTab(tabIds[0]);
  }, [tab, tabKey]);

  useEffect(() => {
    if (!error || focusTick) return undefined;
    errorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    errorRef.current?.focus?.();
    return undefined;
  }, [error, tab, focusTick]);

  useEffect(() => {
    if (!focusTick) return undefined;
    let second = 0;
    const first = window.requestAnimationFrame(() => {
      second = window.requestAnimationFrame(() => {
        const invalid = document.querySelector(".gts-panel .has-error");
        const node = invalid?.matches?.("input, select, textarea")
          ? invalid
          : invalid?.querySelector?.("input, select, textarea") || invalid;
        if (!node) return;
        node.scrollIntoView({ behavior: "smooth", block: "center" });
        if (typeof node.focus === "function") node.focus({ preventScroll: true });
      });
    });
    return () => {
      window.cancelAnimationFrame(first);
      window.cancelAnimationFrame(second);
    };
  }, [focusTick, tab]);

  useEffect(() => {
    setConfirming(false);
  }, [tab]);

  useEffect(() => {
    if (!confirming) return;
    confirmRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [confirming]);

  function updateQuestion(question, value) {
    setConfirming(false);
    setForm((prev) => setFormValue(prev, question, value));
  }

  function visibleQuestions() {
    return flat.filter(({ question }) => isQuestionVisible(question, form, byId));
  }

  function validate() {
    const next = {};
    const visible = visibleQuestions();
    for (const { question, section } of visible) {
      if (question.type === "skills") continue;
      if (question.type === "repeatable_group") {
        Object.assign(next, repeatableFieldErrors(question, getFormValue(form, question)));
        continue;
      }
      const value = getFormValue(form, question);
      const empty = Array.isArray(value) ? !value.length : !String(value ?? "").trim();
      if (questionIsRequired(question, form) && empty) {
        if (question.id === "pres_emp" || question.id === "first_emp") {
          next[question.id] = "Enter the name of your current employer.";
        } else if (question.id === "pres_occ" || question.id === "first_occ") {
          next[question.id] = "Enter your current occupation.";
        } else {
          next[question.id] = `Please answer: ${question.label}`;
        }
        continue;
      }
      const rules = question.validation || {};
      const text = Array.isArray(value) ? value.join(" ") : String(value ?? "").trim();
      if (!empty && rules.min_length && text.length < Number(rules.min_length)) {
        next[question.id] = `Please enter at least ${rules.min_length} characters.`;
      }
      if (!empty && rules.max_length && text.length > Number(rules.max_length)) {
        next[question.id] = `Please keep this under ${rules.max_length} characters.`;
      }
      if (!empty && question.type === "number") {
        const number = Number(text);
        if (Number.isNaN(number)) next[question.id] = `Please enter a number for: ${question.label}`;
        else if (rules.min !== "" && rules.min != null && number < Number(rules.min)) {
          next[question.id] = `${question.label} must be at least ${rules.min}.`;
        } else if (rules.max !== "" && rules.max != null && number > Number(rules.max)) {
          next[question.id] = `${question.label} must be at most ${rules.max}.`;
        }
      }
    }
    if (form.is_currently_employed === "Yes") {
      const title = form.present_job_is_first === "No" ? form.pres_occ : form.first_occ;
      if (!String(title || "").trim()) {
        if (form.present_job_is_first === "No") next.pres_occ = "Job title is required.";
        else next.first_occ = "Job title is required.";
      }
    }
    setFieldErrors(next);
    const first = visible.find(({ question }) => (
      next[question.id]
      || next[question.field_key]
      || Object.keys(next).some((key) => key.startsWith(`${question.id}:`))
    ));
    if (next.pres_occ || next.first_occ) {
      setTab("employment");
      return "Please enter your job title. Alignment cannot be computed without an occupation.";
    }
    if (first) {
      setTab(first.section.key || first.section.id);
      const repeatableMessage = Object.entries(next).find(([key]) => key.startsWith(`${first.question.id}:`))?.[1];
      return next[first.question.id] || repeatableMessage || `Please answer: ${first.question.label}`;
    }
    return "";
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (preview || readOnly || browse || busy || submitting || submitLock.current) return;
    const message = validate();
    if (message) {
      setConfirming(false);
      setFocusTick((value) => value + 1);
      showToast("warning", "Please correct the highlighted fields before continuing.");
      return;
    }
    setError("");
    if (confirmSubmit && !confirming) {
      setConfirming(true);
      return;
    }
    const skills = parseSkills(skillsText || (Array.isArray(form.skills) ? form.skills.join(", ") : form.skills));
    setSkillsText(skills.join(", "));
    const payload = {
      ...form,
      mentoring_rating: form.mentoring_rating === "" ? null : Number(form.mentoring_rating),
      advocacy_rating: form.advocacy_rating === "" ? null : Number(form.advocacy_rating),
      volunteering_rating: form.volunteering_rating === "" ? null : Number(form.volunteering_rating),
      skills,
    };
    for (const questionId of hideQuestionIds) delete payload[questionId];
    for (const group of CREDENTIAL_GROUPS) {
      const choice = credentialReportChoice(form[group.flag], form[group.key]);
      payload[group.flag] = choice;
      if (choice !== "Yes") payload[group.key] = [];
    }
    if (form.is_currently_employed === "Yes" && form.present_job_is_first !== "No") {
      payload.current_occupation = form.first_occ || "";
      payload.current_employer = form.first_emp || "";
    } else if (form.is_currently_employed === "Yes") {
      payload.current_occupation = form.pres_occ || "";
      payload.current_employer = form.pres_emp || "";
    } else {
      payload.current_occupation = "";
      payload.current_employer = "";
    }
    submitLock.current = true;
    setSubmitting(true);
    try {
      await onSubmit?.(payload);
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  }

  const tabIndex = Math.max(0, tabIds.indexOf(tab));
  const current = sections[tabIndex] || sections[0];
  const controlsDisabled = Boolean(readOnly);
  const lastSection = tabIndex >= tabIds.length - 1;
  const currentOccupation = form.present_job_is_first === "No" ? form.pres_occ : form.first_occ;

  const sectionDone = {};
  const sectionErrors = {};
  for (const section of sections) {
    const sid = section.key || section.id;
    const questions = (section.subsections || []).flatMap((sub) => sub.questions || []);
    const requiredVisible = questions.filter((question) => {
      if (!isQuestionVisible(question, form, byId)) return false;
      if (question.type === "repeatable_group") return (question.repeatable?.fields || []).some((field) => field.required);
      return questionIsRequired(question, form);
    });
    sectionDone[sid] = requiredVisible.every((question) => {
      if (question.type === "repeatable_group") {
        return Object.keys(repeatableFieldErrors(question, getFormValue(form, question))).length === 0;
      }
      const value = getFormValue(form, question);
      return Array.isArray(value) ? value.length : String(value || "").trim();
    });
    sectionErrors[sid] = questions.some((question) => (
      fieldErrors[question.id]
      || fieldErrors[question.field_key]
      || Object.keys(fieldErrors).some((key) => key.startsWith(`${question.id}:`))
    ));
  }
  const completedCount = Object.values(sectionDone).filter(Boolean).length;

  function goToTab(id) {
    setConfirming(false);
    setTab(id);
  }

  function showAlignmentAfter(question) {
    if (!alignmentHint) return false;
    if (form.is_currently_employed !== "Yes") return false;
    if (question.id === "pres_occ") return form.present_job_is_first === "No";
    if (question.id === "first_occ") return form.present_job_is_first !== "No";
    return false;
  }

  function renderQuestion(question, options = {}) {
    const { embedAlignment = true, hideDescription = false } = options;
    const alignment = embedAlignment && showAlignmentAfter(question) ? (
      <AlignmentHint alignment={alignmentHint} occupation={currentOccupation} />
    ) : null;
    const help = questionHelp(question, form);
    const description = hideDescription ? "" : (question.description || "");
    const extraHelp = help && help !== question.description ? help : "";
    const hint = hideDescription && help === question.description ? extraHelp : (help || description);
    const questionClass = [
      "gts-question",
      question.id === "first_stat" ? "gts-status-choices" : "",
      question.type === "scale" ? "gts-scale" : "",
    ].filter(Boolean).join(" ");
    if (question.type === "checkboxes") {
      const value = getFormValue(form, question);
      return (
        <div key={question.id} className={questionClass} data-question={question.id}>
          {description ? <p className="muted">{description}</p> : null}
          {controlFor(question, value, (next) => updateQuestion(question, next), controlsDisabled, fieldErrors[question.id], questionIsRequired(question, form))}
          {alignment}
        </div>
      );
    }
    if (question.type === "skills") {
      return (
        <div key={question.id} className={questionClass} data-question={question.id}>
          <Field label={question.label} hint={hint} required={questionIsRequired(question, form)} error={fieldErrors[question.id]}>
            <input
              value={skillsText}
              disabled={controlsDisabled}
              onChange={(e) => setSkillsText(e.target.value)}
              onBlur={() => {
                const skills = parseSkills(skillsText);
                setSkillsText(skills.join(", "));
                setForm((prev) => ({ ...prev, skills }));
              }}
              placeholder={question.placeholder || "Python, JavaScript, SQL"}
            />
          </Field>
          {alignment}
        </div>
      );
    }
    if (question.type === "repeatable_group") {
      const rows = Array.isArray(form.further_studies) ? form.further_studies : [];
      const fields = question.repeatable?.fields || [];
      const studiesGuidance = Object.keys(fieldErrors).some((key) => key === question.id || key.startsWith(`${question.id}:`))
        ? ""
        : resumeGuidance(question.id, rows, resume);
      return (
        <div key={question.id} className={questionClass} data-question={question.id}>
          {rows.map((row, index) => (
            <div className="study-card" key={`${question.id}-${index}`}>
              {fields.map((field) => (
                <Field
                  key={field.id}
                  label={field.label}
                  required={Boolean(field.required)}
                  error={fieldErrors[`${question.id}:${index}:${field.id}`]}
                >
                  {field.type === "yes_no" ? (
                    <select
                      value={row[field.id] || field.default_value || "No"}
                      disabled={controlsDisabled}
                      onChange={(e) => {
                        setForm((prev) => {
                          const next = [...(prev.further_studies || [])];
                          next[index] = { ...next[index], [field.id]: e.target.value };
                          return { ...prev, further_studies: next };
                        });
                      }}
                    >
                      <option value="Yes">{T("Yes")}</option>
                      <option value="No">{T("No")}</option>
                    </select>
                  ) : (
                    <input
                      value={row[field.id] || ""}
                      disabled={controlsDisabled}
                      placeholder={field.placeholder}
                      onChange={(e) => {
                        setForm((prev) => {
                          const next = [...(prev.further_studies || [])];
                          next[index] = { ...next[index], [field.id]: e.target.value };
                          return { ...prev, further_studies: next };
                        });
                      }}
                    />
                  )}
                </Field>
              ))}
              <div className="study-remove">
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  disabled={controlsDisabled}
                  onClick={() => setForm((prev) => ({ ...prev, further_studies: prev.further_studies.filter((_, i) => i !== index) }))}
                >
                  {T(question.repeatable?.remove_label || "Remove")}
                </button>
              </div>
            </div>
          ))}
          <button
            type="button"
            className="btn btn-outline"
            disabled={controlsDisabled}
            onClick={() => setForm((prev) => ({
              ...prev,
              further_studies: [
                ...(prev.further_studies || []),
                { course_degree: "", school: "", institution_address: "", year_enrolled: "", scholarship: "", is_graduated: "No" },
              ],
            }))}
          >
            {T(question.repeatable?.add_label || "Add program")}
          </button>
          {studiesGuidance ? <p className="resume-guidance" role="note">{studiesGuidance}</p> : null}
          {alignment}
        </div>
      );
    }
    const value = getFormValue(form, question);
    const required = questionIsRequired(question, form);
    const fieldError = fieldErrors[question.id] || fieldErrors[question.field_key];
    const guidance = fieldError ? "" : resumeGuidance(question.id, value, resume);
    if (question.type === "yes_no" || question.type === "multiple_choice" || question.type === "scale") {
      return (
        <div key={question.id} className={questionClass} data-question={question.id}>
          <CheckGroup legend={question.label} required={required} error={fieldError} note={guidance}>
            {description ? <p className="muted field-help">{description}</p> : null}
            {extraHelp ? <p className="muted field-help">{extraHelp}</p> : null}
            {controlFor(question, value, (next) => updateQuestion(question, next), controlsDisabled, fieldError, required)}
          </CheckGroup>
          {alignment}
        </div>
      );
    }
    return (
      <div key={question.id} className={questionClass} data-question={question.id}>
        <Field
          label={question.label}
          hint={hint}
          required={required}
          error={fieldError}
          note={guidance}
        >
          {controlFor(question, value, (next) => updateQuestion(question, next), controlsDisabled, fieldError, required)}
        </Field>
        {alignment}
      </div>
    );
  }

  function renderQuestionList(questions, hideDescriptionIds = []) {
    const hidden = new Set(hideDescriptionIds);
    const nodes = [];
    const skipped = new Set();
    questions.forEach((question, index) => {
      if (skipped.has(question.id)) return;
      const next = questions[index + 1];
      const partnerId = JOB_PARTNERS[question.id];
      const options = { hideDescription: hidden.has(question.id) };
      if (partnerId && next?.id === partnerId) {
        skipped.add(next.id);
        nodes.push(
          <div className="gts-job-pair" key={`${question.id}-pair`}>
            {renderQuestion(question, { ...options, embedAlignment: false })}
            {renderQuestion(next, { hideDescription: hidden.has(next.id), embedAlignment: false })}
          </div>
        );
        if (showAlignmentAfter(question)) {
          nodes.push(
            <div className="gts-align-slot" key={`${question.id}-alignment`}>
              <AlignmentHint alignment={alignmentHint} occupation={currentOccupation} />
            </div>
          );
        }
        return;
      }
      nodes.push(renderQuestion(question, options));
    });
    return nodes;
  }

  function renderGeneralGroups(questions) {
    const used = new Set();
    const personal = takeIds(questions, ["first_name", "middle_name", "last_name", "husband_surname"], used);
    const country = takeIds(questions, ["country"], used);
    const degree = takeIds(questions, ["degree", "year_graduated"], used);
    const rest = questions.filter((question) => !used.has(question.id));
    if (!personal.length && !country.length && !degree.length) return null;
    return (
      <div className="gts-groups" key="general-groups">
        {personal.length ? (
          <section className="form-section" aria-labelledby="gts-personal-heading">
            <h3 id="gts-personal-heading">{T("Personal information")}</h3>
            <p className="muted">{T("Your name as it should appear on this record.")}</p>
            <div className="gts-field-grid">{personal.map((question) => renderQuestion(question))}</div>
          </section>
        ) : null}
        {country.length ? (
          <section className="form-section" aria-labelledby="gts-residence-heading">
            <h3 id="gts-residence-heading">{T("Residence")}</h3>
            <p className="muted">{T("Where you live now.")}</p>
            {country.map((question) => renderQuestion(question))}
          </section>
        ) : null}
        {degree.length ? (
          <section className="form-section" aria-labelledby="gts-degree-heading">
            <h3 id="gts-degree-heading">{T("Degree information")}</h3>
            <p className="muted">{T("Your bachelor's degree and the year you graduated.")}</p>
            {degree.length > 1 ? (
              <div className="gts-job-pair">{degree.map((question) => renderQuestion(question))}</div>
            ) : degree.map((question) => renderQuestion(question))}
          </section>
        ) : null}
        {rest.length ? <section className="form-section" key="general-rest">{renderQuestionList(rest)}</section> : null}
      </div>
    );
  }

  function renderFeedbackGroups(questions) {
    const used = new Set();
    const seminars = takeIds(questions, ["participated_seminars", "seminars_helpful"], used);
    const ratings = takeIds(questions, ["mentoring_rating", "advocacy_rating", "volunteering_rating", "engagement_desc"], used);
    const curriculum = questions.filter((question) => !used.has(question.id) && isCurriculumQuestion(question));
    curriculum.forEach((question) => used.add(question.id));
    const rest = questions.filter((question) => !used.has(question.id));
    if (!seminars.length && !ratings.length && !curriculum.length) return null;
    const ratingLead = ratings.find((question) => question.id === "mentoring_rating")?.description
      || "How much has AUF inspired you to do each of the following?";
    const curriculumLead = curriculum.find((question) => question.description)?.description
      || "Suggestions for improving the curriculum.";
    const hideDescription = [
      ratings.find((question) => question.id === "mentoring_rating" && question.description)?.id,
      curriculum.find((question) => question.description)?.id,
    ].filter(Boolean);
    return (
      <div className="gts-groups" key="feedback-groups">
        {seminars.length ? (
          <section className="form-section" aria-labelledby="gts-seminar-heading">
            <h3 id="gts-seminar-heading">{T("AUF career-development seminars")}</h3>
            <p className="muted">{T("Whether you joined AUF seminars, and whether they helped with employment.")}</p>
            {renderQuestionList(seminars)}
          </section>
        ) : null}
        {ratings.length ? (
          <section className="form-section" aria-labelledby="gts-engagement-heading">
            <h3 id="gts-engagement-heading">{T("Engagement and inspiration")}</h3>
            <p className="muted">{T(ratingLead)}</p>
            {renderQuestionList(ratings, hideDescription)}
          </section>
        ) : null}
        {curriculum.length ? (
          <section className="form-section" aria-labelledby="gts-curriculum-heading">
            <h3 id="gts-curriculum-heading">{T("Curriculum or program suggestions")}</h3>
            <p className="muted">{T(curriculumLead)}</p>
            {renderQuestionList(curriculum, hideDescription)}
          </section>
        ) : null}
        {rest.length ? <section className="form-section" key="feedback-rest">{renderQuestionList(rest)}</section> : null}
      </div>
    );
  }

  const formClass = [preview ? "gts-preview-form" : "", variant === "review" || browse ? "gts-review" : "", browse ? "gts-browse" : ""].filter(Boolean).join(" ");
  const tabListLabel = "Graduate Tracer Survey sections";
  const tabSlug = tabListLabel.replace(/\s+/g, "-").toLowerCase();
  const sectionId = current?.key || current?.id;
  const savingLabel = confirming ? "Submitting tracer information…" : "Saving…";
  const controlsBusy = Boolean(busy || submitting);

  return (
    <form className={formClass} onSubmit={handleSubmit} aria-busy={controlsBusy || undefined}>
      {schema?.intro && variant !== "review" ? <p className="muted gts-intro">{schema.intro}</p> : null}
      <p className="gts-required-legend"><span className="req" aria-hidden="true">*</span> Required field</p>
      {error ? (
        <Alert type="error" alertRef={errorRef} title="Please review the highlighted questions">
          {error}
        </Alert>
      ) : null}
      {closedMessage ? <Alert type="info">{closedMessage}</Alert> : null}
      {extraNotice}
      <div className="gts-progress">
        <p className="section-progress">
          <strong>{T(`Section ${tabIndex + 1} of ${tabs.length} — ${tabs[tabIndex]?.[1] || ""}`)}</strong>
          <span>{T(`${completedCount} of ${tabs.length} sections completed`)}</span>
        </p>
        <div
          className="gts-meter"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={tabs.length || 0}
          aria-valuenow={completedCount}
          aria-label={`${completedCount} of ${tabs.length} sections completed`}
        >
          <span style={{ width: `${tabs.length ? (completedCount / tabs.length) * 100 : 0}%` }} />
        </div>
      </div>
      <TabList
        label={tabListLabel}
        value={tab}
        onChange={goToTab}
        appearance="steps"
        tabs={tabs.map(([id, label]) => [id, T(label)])}
        doneMap={sectionDone}
        errorMap={sectionErrors}
      />

      {current ? (
        <div
          className="gts-panel"
          role="tabpanel"
          id={`panel-${tabSlug}-${sectionId}`}
          aria-labelledby={`tab-${tabSlug}-${sectionId}`}
          inert={browse ? "" : undefined}
        >
          {variant === "review" ? (
            <header className="gts-section-banner">
              <p className="eyebrow">{T(`Section ${tabIndex + 1} of ${tabs.length}`)}</p>
              <h3>{T((current.key === "studies" || current.id === "studies") ? STUDIES_SECTION_TITLE : current.name)}</h3>
              {current.description ? <p className="muted">{T(current.description)}</p> : null}
            </header>
          ) : null}
          {(current.key === "studies" || current.id === "studies") ? (
            <StudiesSection
              form={form}
              resume={resume}
              disabled={controlsDisabled}
              showLead={variant !== "review"}
              fieldErrors={fieldErrors}
              onEnroll={(value) => {
                const question = findQuestion(current, "enroll_further_studies");
                if (question) updateQuestion(question, value);
                else setForm((prev) => ({ ...prev, enroll_further_studies: value }));
              }}
              onEditDegree={() => {
                const general = sections.find((section) => (section.key || section.id) === "general");
                if (general) goToTab(general.key || general.id);
              }}
              onChangeProgram={(index, field, value) => {
                setForm((prev) => {
                  const next = [...(prev.further_studies || [])];
                  next[index] = { ...next[index], [field]: value };
                  return { ...prev, further_studies: next };
                });
              }}
              onAddProgram={() => {
                setForm((prev) => ({
                  ...prev,
                  further_studies: [...(prev.further_studies || []), { ...BLANK_PROGRAM }],
                }));
              }}
              onRemoveProgram={(index) => {
                setForm((prev) => ({
                  ...prev,
                  further_studies: (prev.further_studies || []).filter((_, item) => item !== index),
                }));
              }}
              onReport={(flag, value) => setForm((prev) => ({ ...prev, [flag]: value }))}
              onChangeCredential={(key, index, field, value) => {
                setForm((prev) => {
                  const rows = [...(prev[key] || [])];
                  if (index < 0) return { ...prev, [key]: [...rows, { ...(value || { name: "", detail: "", year: "" }) }] };
                  if (!field) return { ...prev, [key]: rows.filter((_, item) => item !== index) };
                  const next = { ...rows[index], [field]: value };
                  if (field === "awarding_body" || field === "issuer" || field === "location") next.detail = value;
                  rows[index] = next;
                  return { ...prev, [key]: rows };
                });
              }}
            />
          ) : null}
          {(current.subsections || []).map((sub) => {
            const sectionKey = current.key || current.id;
            const studiesStep = sectionKey === "studies";
            const questions = (sub.questions || []).filter((question) => {
              if (studiesStep && (question.id === "enroll_further_studies" || question.id === "further_studies")) return false;
              return isQuestionVisible(question, form, byId);
            });
            if (!questions.length && !sub.name) return null;
            if (sectionKey === "general" && !sub.name) {
              const grouped = renderGeneralGroups(questions);
              if (grouped) return grouped;
            }
            if (sectionKey === "feedback" && !sub.name) {
              const grouped = renderFeedbackGroups(questions);
              if (grouped) return grouped;
            }
            const showJobCallout = sectionKey === "employment" && sub.id === "current_employment" && form.is_currently_employed === "Yes";
            return (
              <section className={`form-section${sub.id === "first_job" ? " is-first-job" : ""}`} key={sub.id}>
                {sub.name ? <h3>{T(sub.name)}</h3> : null}
                {sub.description ? <p className="muted">{T(sub.description)}</p> : null}
                {showJobCallout ? (
                  <p className="gts-callout">
                    {form.present_job_is_first === "No"
                      ? "Your current occupation comes from your present job, not your first job."
                      : "If this is still your first job, that occupation is saved as your current occupation."}
                  </p>
                ) : null}
                {renderQuestionList(questions)}
              </section>
            );
          })}
        </div>
      ) : null}

      {preview ? (
        <p className="muted preview-note">Live preview — answers here are not saved to alumni records.</p>
      ) : confirming ? (
        <div ref={confirmRef}>
          <SubmitConfirm busy={controlsBusy} confirmLabel={submitLabel} onCancel={() => setConfirming(false)} />
        </div>
      ) : (
        <div className="form-nav">
          <button
            type="button"
            className="btn btn-outline"
            disabled={tabIndex === 0 || controlsBusy}
            onClick={() => goToTab(tabIds[Math.max(0, tabIndex - 1)])}
          >
            {T("Previous")}
          </button>
          <div className="form-nav-actions">
            {!lastSection ? (
              <button type="button" className="btn btn-navy" disabled={controlsBusy} onClick={() => goToTab(tabIds[tabIndex + 1])}>
                {T("Continue")}
              </button>
            ) : null}
            {readOnly || browse ? null : (
              <button
                type="submit"
                className={lastSection ? "btn btn-navy" : "btn btn-outline btn-submit-alt"}
                disabled={controlsBusy}
                aria-busy={controlsBusy || undefined}
              >
                {controlsBusy ? T(savingLabel) : T(submitLabel)}
              </button>
            )}
          </div>
        </div>
      )}
      {!preview && controlsBusy ? <p className="save-status is-saving" role="status">{savingLabel}</p> : null}
    </form>
  );
}
