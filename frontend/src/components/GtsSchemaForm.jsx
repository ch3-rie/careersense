import { useEffect, useMemo, useRef, useState } from "react";
import { AlignmentHint, SubmitConfirm } from "./AuthFlow";
import { Alert, CheckGroup, Field, RadioChoiceList, TabList } from "./ui";
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
    return <textarea value={value ?? ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} disabled={disabled} minLength={rules.min_length || undefined} maxLength={rules.max_length || undefined} />;
  }
  if (type === "yes_no") {
    return (
      <RadioChoiceList
        name={question.id}
        value={value}
        onChange={onChange}
        disabled={disabled}
        options={[
          { value: "Yes", label: "Yes" },
          { value: "No", label: "No" },
        ]}
      />
    );
  }
  if (type === "dropdown" || type === "multiple_choice" || type === "scale") {
    const scale = options.length ? options : type === "scale" ? ["1", "2", "3", "4", "5"] : [];
    if (type === "multiple_choice") {
      return (
        <RadioChoiceList
          name={question.id}
          value={value}
          onChange={onChange}
          disabled={disabled}
          options={scale.map((opt) => ({ value: optionValue(opt), label: optionLabel(opt) }))}
        />
      );
    }
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
    return <input type="date" value={value || ""} onChange={(e) => onChange(e.target.value)} disabled={disabled} />;
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

export default function GtsSchemaForm({
  schema,
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
}) {
  const [tab, setTab] = useState(schema?.sections?.[0]?.key || schema?.sections?.[0]?.id || "general");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [confirming, setConfirming] = useState(false);
  const errorRef = useRef(null);
  const confirmRef = useRef(null);
  const [focusTick, setFocusTick] = useState(0);
  const [form, setForm] = useState(() => emptyFormFromSchema(schema, initial));
  const [skillsText, setSkillsText] = useState(() =>
    Array.isArray(initial?.skills) ? initial.skills.join(", ") : String(initial?.skills || "")
  );
  const schemaRef = useRef(schema);
  schemaRef.current = schema;

  const sections = schema?.sections || [];
  const tabs = sections.map((section) => [section.key || section.id, section.name]);
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
        const node = document.querySelector(
          ".gts-panel .has-error input, .gts-panel .has-error select, .gts-panel .has-error textarea, .gts-panel .field.has-error"
        );
        if (!node) return;
        node.scrollIntoView({ behavior: "smooth", block: "center" });
        node.focus?.({ preventScroll: true });
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
    if (preview || readOnly) return;
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
    await onSubmit?.(payload);
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

  function renderQuestion(question) {
    const alignment = showAlignmentAfter(question) ? (
      <AlignmentHint alignment={alignmentHint} occupation={currentOccupation} />
    ) : null;
    const help = questionHelp(question, form);
    const extraHelp = help && help !== question.description ? help : "";
    if (question.type === "checkboxes") {
      const value = getFormValue(form, question);
      return (
        <div key={question.id} className="gts-question">
          {question.description ? <p className="muted">{question.description}</p> : null}
          {controlFor(question, value, (next) => updateQuestion(question, next), controlsDisabled, fieldErrors[question.id], questionIsRequired(question, form))}
          {alignment}
        </div>
      );
    }
    if (question.type === "skills") {
      return (
        <div key={question.id} className="gts-question">
          <Field label={question.label} hint={help || question.description} required={questionIsRequired(question, form)} error={fieldErrors[question.id]}>
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
      return (
        <div key={question.id} className="gts-question">
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
                { course_degree: "", school: "", year_enrolled: "", scholarship: "", is_graduated: "No" },
              ],
            }))}
          >
            {T(question.repeatable?.add_label || "Add program")}
          </button>
          {alignment}
        </div>
      );
    }
    const value = getFormValue(form, question);
    const required = questionIsRequired(question, form);
    const fieldError = fieldErrors[question.id] || fieldErrors[question.field_key];
    const guidance = fieldError ? "" : resumeGuidance(question.id, value, resume);
    if (question.type === "yes_no" || question.type === "multiple_choice") {
      return (
        <div key={question.id} className={`gts-question${question.id === "first_stat" ? " gts-status-choices" : ""}`} data-question={question.id}>
          <CheckGroup legend={question.label} required={required} error={fieldError} note={guidance}>
            {question.description ? <p className="muted field-help">{question.description}</p> : null}
            {extraHelp ? <p className="muted field-help">{extraHelp}</p> : null}
            {controlFor(question, value, (next) => updateQuestion(question, next), controlsDisabled)}
          </CheckGroup>
          {alignment}
        </div>
      );
    }
    return (
      <div key={question.id} className="gts-question" data-question={question.id}>
        <Field
          label={question.label}
          hint={help || question.description}
          required={required}
          error={fieldError}
          note={guidance}
        >
          {controlFor(question, value, (next) => updateQuestion(question, next), controlsDisabled)}
        </Field>
        {alignment}
      </div>
    );
  }

  function renderQuestionList(questions) {
    const nodes = [];
    const skipped = new Set();
    questions.forEach((question, index) => {
      if (skipped.has(question.id)) return;
      const next = questions[index + 1];
      if (question.id === "first_occ" && next?.id === "first_emp") {
        skipped.add(next.id);
        nodes.push(
          <div className="gts-job-pair" key="first-job-pair">
            {renderQuestion(question)}
            {renderQuestion(next)}
          </div>
        );
        return;
      }
      nodes.push(renderQuestion(question));
    });
    return nodes;
  }

  const formClass = [preview ? "gts-preview-form" : "", variant === "review" ? "gts-review" : ""].filter(Boolean).join(" ");

  return (
    <form className={formClass} onSubmit={handleSubmit}>
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
      </div>
      <TabList
        label="Graduate Tracer Survey sections"
        value={tab}
        onChange={goToTab}
        appearance="steps"
        tabs={tabs.map(([id, label]) => [id, T(label)])}
        doneMap={sectionDone}
        errorMap={sectionErrors}
      />

      {current ? (
        <div className="gts-panel" role="tabpanel" id={`panel-gts-${current.key || current.id}`}>
          {variant === "review" ? (
            <header className="gts-section-banner">
              <p className="eyebrow">{T(`Section ${tabIndex + 1} of ${tabs.length}`)}</p>
              <h3>{T(current.name)}</h3>
              {current.description ? <p className="muted">{T(current.description)}</p> : null}
            </header>
          ) : null}
          {(current.key === "employment" || current.id === "employment") && form.is_currently_employed === "Yes" ? (
            <p className="gts-callout">
              {form.present_job_is_first === "No"
                ? "Your current occupation comes from your present job, not your first job."
                : "If this is still your first job, that occupation is saved as your current occupation."}
            </p>
          ) : null}
          {(current.subsections || []).map((sub) => {
            const questions = (sub.questions || []).filter((question) => isQuestionVisible(question, form, byId));
            if (!questions.length && !sub.name) return null;
            return (
              <section className={`form-section${sub.id === "first_job" ? " is-first-job" : ""}`} key={sub.id}>
                {sub.name ? <h3>{T(sub.name)}</h3> : null}
                {sub.description ? <p className="muted">{T(sub.description)}</p> : null}
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
          <SubmitConfirm busy={busy} confirmLabel={submitLabel} onCancel={() => setConfirming(false)} />
        </div>
      ) : (
        <div className="form-nav">
          <button
            type="button"
            className="btn btn-outline"
            disabled={tabIndex === 0 || busy}
            onClick={() => goToTab(tabIds[Math.max(0, tabIndex - 1)])}
          >
            {T("Previous")}
          </button>
          <div className="form-nav-actions">
            {!lastSection ? (
              <button type="button" className="btn btn-navy" disabled={busy} onClick={() => goToTab(tabIds[tabIndex + 1])}>
                {T("Continue")}
              </button>
            ) : null}
            {readOnly ? null : (
              <button
                type="submit"
                className={lastSection ? "btn btn-navy" : "btn btn-outline btn-submit-alt"}
                disabled={busy}
              >
                {busy ? T("Saving…") : T(submitLabel)}
              </button>
            )}
          </div>
        </div>
      )}
      {!preview && busy ? <p className="save-status is-saving" role="status">Saving…</p> : null}
    </form>
  );
}
