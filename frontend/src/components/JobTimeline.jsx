import { useEffect, useState } from "react";
import { DateField } from "./DateField";
import { Alert, Dialog, Empty, Field, SectionTitle } from "./ui";
import { PencilIcon, PlusIcon, TrashIcon } from "./icons";
import { api } from "../lib/api";
import { formatEmploymentPeriod } from "../lib/format";
import { showToast } from "../lib/toasts";
import { friendlyError } from "../lib/userMessages";

const SALARY_RANGES = [
  "Below ₱13,800",
  "₱13,800 to ₱27,599",
  "₱27,600 to ₱41,399",
  "₱41,400 to ₱55,199",
  "₱55,200 to ₱68,999",
  "₱69,000 and above",
];

const EMPTY_FORM = {
  job_title: "",
  company: "",
  start_date: "",
  end_date: "",
  is_current: false,
  industry: "",
  location: "",
  salary_range: "",
  description: "",
};

const UNEMPLOYMENT_REASONS = [
  ["seeking", "Currently Seeking Employment"],
  ["further_studies", "Pursuing Further Studies"],
  ["personal_family", "Personal or Family Reasons"],
  ["health", "Health Reasons"],
  ["not_seeking", "Not Currently Seeking Employment"],
  ["other", "Other"],
];

const INDUSTRIES = [
  "Information and communications technology",
  "Finance and accounting",
  "Hospitality and food service",
  "Education",
  "Health care",
  "Engineering and construction",
  "Government and public service",
  "Retail and sales",
  "Other",
];

function toInputDate(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function periodLine(job, compact = false) {
  const range = formatEmploymentPeriod(job.start_date, job.end_date, job.is_current);
  if (compact) return range;
  return job.duration && range ? `${range} · ${job.duration}` : range;
}

function orderedJobs(items) {
  return [...items].sort((a, b) => {
    if (Boolean(a.is_current) !== Boolean(b.is_current)) return a.is_current ? -1 : 1;
    const startA = a.start_date || "";
    const startB = b.start_date || "";
    if (startA !== startB) return startB.localeCompare(startA);
    return (b.id || 0) - (a.id || 0);
  });
}

function reasonLabel(code) {
  return UNEMPLOYMENT_REASONS.find(([value]) => value === code)?.[1] || "";
}

export function JobTimeline({
  jobs,
  onJobsChange,
  currentlyUnemployed = false,
  unemploymentReason = "",
  unemploymentDetails = "",
  onEmploymentChange,
  className = "",
  summary = false,
  onManage,
  limit,
  index,
  lead,
}) {
  const [items, setItems] = useState(jobs || []);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftStatus, setDraftStatus] = useState(currentlyUnemployed ? "unemployed" : "employed");
  const [draftReason, setDraftReason] = useState(unemploymentReason || "");
  const [draftDetails, setDraftDetails] = useState(unemploymentDetails || "");
  const formOpen = editing !== null;
  const displayItems = orderedJobs(items);
  const unemployed = Boolean(currentlyUnemployed);
  const draftingUnemployed = draftStatus === "unemployed";

  useEffect(() => {
    setItems(jobs || []);
  }, [jobs]);

  function applyJobs(next) {
    setItems(next);
    onJobsChange?.(next);
  }

  function openAdd() {
    setError("");
    setEditing("new");
    setForm(EMPTY_FORM);
    setDraftStatus(currentlyUnemployed ? "unemployed" : "employed");
    setDraftReason(unemploymentReason || "");
    setDraftDetails(unemploymentDetails || "");
  }

  function openEdit(job) {
    setError("");
    setEditing(job);
    setForm({
      job_title: job.job_title || "",
      company: job.company || "",
      start_date: toInputDate(job.start_date),
      end_date: toInputDate(job.end_date),
      is_current: Boolean(job.is_current),
      industry: job.industry || "",
      location: job.location || "",
      salary_range: job.salary_range || "",
      description: job.description || "",
    });
  }

  function closeForm() {
    if (busy) return;
    setEditing(null);
    setError("");
    setForm(EMPTY_FORM);
  }

  function jobStarted() {
    return Boolean(
      form.job_title.trim()
      || form.company.trim()
      || form.start_date
      || form.end_date
      || form.industry.trim()
      || form.location.trim()
      || form.salary_range.trim()
      || form.description.trim()
    );
  }

  async function saveStatus(unemployedNow) {
    const result = await api("/api/alumni/employment-status", {
      method: "PUT",
      body: {
        currently_unemployed: unemployedNow,
        unemployment_reason: unemployedNow ? draftReason : "",
        unemployment_details: unemployedNow ? draftDetails.trim() : "",
      },
    });
    onEmploymentChange?.(result);
  }

  async function saveJob() {
    const title = form.job_title.trim();
    const company = form.company.trim();
    const isEdit = editing && editing !== "new";
    const adding = !isEdit;
    const unemployedNow = adding ? draftingUnemployed : unemployed;
    const includeJob = isEdit || jobStarted();
    const statusChanged = adding && (
      unemployedNow !== unemployed
      || (unemployedNow && (draftReason !== (unemploymentReason || "") || draftDetails.trim() !== (unemploymentDetails || "")))
    );
    if (adding && unemployedNow && !draftReason) {
      setError("Select a reason.");
      return;
    }
    if (adding && unemployedNow && draftReason === "other" && !draftDetails.trim()) {
      setError("Add a short explanation when you select Other.");
      return;
    }
    if (includeJob && (!title || !company)) {
      setError("Occupation and company are required.");
      return;
    }
    if (!includeJob && !statusChanged) {
      setError("Occupation and company are required.");
      return;
    }
    const keepCurrent = unemployedNow ? Boolean(isEdit && editing.is_current) : Boolean(form.is_current);
    if (includeJob && form.start_date && form.end_date && !keepCurrent && form.end_date < form.start_date) {
      setError("End date must be on or after the start date.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (statusChanged) await saveStatus(unemployedNow);
      if (includeJob) {
        const body = {
          job_title: title,
          company,
          start_date: form.start_date || null,
          end_date: keepCurrent ? null : form.end_date || null,
          is_current: keepCurrent,
          industry: form.industry.trim(),
          location: form.location.trim(),
          salary_range: form.salary_range.trim(),
          description: form.description.trim(),
        };
        const result = await api(isEdit ? `/api/alumni/jobs/${editing.id}` : "/api/alumni/jobs", {
          method: isEdit ? "PUT" : "POST",
          body,
        });
        applyJobs(result.jobs);
      }
      setEditing(null);
      setForm(EMPTY_FORM);
      showToast("success", includeJob ? (isEdit ? "Work experience updated." : "Work experience added.") : "Employment status saved.");
    } catch (err) {
      setError(friendlyError(err, includeJob ? "We couldn't save this work experience. Please try again." : "We couldn't save this employment status. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!removing) return;
    setBusy(true);
    setError("");
    try {
      const result = await api(`/api/alumni/jobs/${removing.id}`, { method: "DELETE" });
      applyJobs(result.jobs);
      setRemoving(null);
      showToast("success", "Work experience removed.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't delete this work experience. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  function asRecorded(job) {
    if (!unemployed || !job.is_current) return job;
    return { ...job, is_current: false };
  }

  const unemploymentCopy = `${reasonLabel(unemploymentReason) || "Reason not recorded"}${unemploymentDetails ? ` — ${unemploymentDetails}` : ""}`;

  if (summary) {
    const visible = typeof limit === "number" ? displayItems.slice(0, limit) : displayItems;
    const hidden = Math.max(0, displayItems.length - visible.length);
    return (
      <section className={`alumni-block ${className}`.trim()} aria-label="Employment History">
        <header className="profile-section-head">
          <SectionTitle title="Employment History" />
          {onManage ? (
            <button type="button" className="btn btn-outline btn-sm" onClick={onManage}>
              View full record
            </button>
          ) : null}
        </header>
        {!displayItems.length && !unemployed ? (
          <Empty
            compact
            title="No employment history added yet"
            action={onManage ? (
              <button type="button" className="btn btn-navy btn-sm" onClick={onManage}>
                Add position
              </button>
            ) : null}
          >
            Add a position when you are ready.
          </Empty>
        ) : (
          <>
            <ol className="job-summary">
              {unemployed ? (
                <li className="is-current">
                  <span className="job-dot" aria-hidden="true" />
                  <div>
                    <p className="job-when">Current</p>
                    <strong>Unemployed</strong>
                    <p>{unemploymentCopy}</p>
                  </div>
                </li>
              ) : null}
              {visible.map((job) => {
                const shown = asRecorded(job);
                return (
                <li key={job.id} className={shown.is_current ? "is-current" : ""}>
                  <span className="job-dot" aria-hidden="true" />
                  <div>
                    {periodLine(shown, true) ? <p className="job-when">{periodLine(shown, true)}</p> : null}
                    <strong>{shown.job_title}</strong>
                    <p>{shown.company}</p>
                    {shown.location ? <p className="muted">{shown.location}</p> : null}
                    {shown.industry ? <p className="muted">{shown.industry}</p> : null}
                    {shown.salary_range ? <p className="muted">Salary range: {shown.salary_range}</p> : null}
                  </div>
                </li>
                );
              })}
            </ol>
            {hidden ? <p className="muted">{hidden} earlier {hidden === 1 ? "position" : "positions"} on your full record.</p> : null}
          </>
        )}
      </section>
    );
  }

  return (
    <section className={`alumni-block job-timeline-panel ${className}`.trim()} id="work-history" aria-label="Employment History">
      <header className="profile-section-head">
        <SectionTitle
          index={index}
          title="Employment History"
          lead={lead || "Occupation and company are required. Salary range can be left blank."}
        />
        <div className="panel-actions">
          <button type="button" className="btn btn-navy btn-sm" onClick={openAdd}>
            <PlusIcon size={16} />
            Add position
          </button>
        </div>
      </header>
      <Alert type="error">{!formOpen && !removing ? error : null}</Alert>
      {!items.length && !unemployed ? (
        <Empty
          compact
          title="No employment history added yet"
        >
          Add a position when you are ready.
        </Empty>
      ) : (
        <ol className="job-timeline" aria-label="Employment History, current and most recent first">
          {unemployed ? (
            <li className="job-timeline-item is-current">
              <span className="job-dot" aria-hidden="true" />
              <article className="job-card">
                <div className="job-card-top">
                  <div className="job-card-copy">
                    <p className="job-when"><span className="job-now">Current</span></p>
                    <strong>Unemployed</strong>
                    <p className="job-company">{unemploymentCopy}</p>
                  </div>
                  <div className="job-card-actions">
                    <button
                      type="button"
                      className="btn btn-text btn-sm icon-btn"
                      aria-label="Edit employment status"
                      title="Edit"
                      onClick={openAdd}
                    >
                      <PencilIcon size={16} />
                    </button>
                  </div>
                </div>
              </article>
            </li>
          ) : null}
          {displayItems.map((job) => {
            const shown = asRecorded(job);
            const when = periodLine(shown, true);
            return (
              <li key={job.id} className={`job-timeline-item${shown.is_current ? " is-current" : " is-past"}`}>
                <span className="job-dot" aria-hidden="true" />
                <article className="job-card">
                  <div className="job-card-top">
                    <div className="job-card-copy">
                      {when || shown.is_current || job.duration ? (
                        <p className="job-when">
                          {when || job.duration ? (
                            <span>
                              {when}
                              {when && job.duration ? " · " : ""}
                              {job.duration}
                            </span>
                          ) : null}
                          {shown.is_current ? <span className="job-now">Current</span> : null}
                        </p>
                      ) : null}
                      <strong>{job.job_title}</strong>
                      {job.company ? <p className="job-company">{job.company}</p> : null}
                    </div>
                    <div className="job-card-actions">
                      <button
                        type="button"
                        className="btn btn-text btn-sm icon-btn"
                        aria-label={`Edit ${job.job_title || "work experience"}`}
                        title="Edit"
                        onClick={() => openEdit(job)}
                      >
                        <PencilIcon size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-text btn-sm icon-btn"
                        aria-label={`Remove ${job.job_title || "work experience"}`}
                        title="Remove"
                        onClick={() => { setError(""); setRemoving(job); }}
                      >
                        <TrashIcon size={16} />
                      </button>
                    </div>
                  </div>
                  {job.location || job.industry || job.salary_range ? (
                    <ul className="timeline-facts">
                      {job.location ? <li>{job.location}</li> : null}
                      {job.industry ? <li>{job.industry}</li> : null}
                      {job.salary_range ? <li>Salary range: {job.salary_range}</li> : null}
                    </ul>
                  ) : null}
                  {job.description ? <p className="job-description">{job.description}</p> : null}
                </article>
              </li>
            );
          })}
        </ol>
      )}
      {formOpen ? (
        <Dialog
          title={editing === "new" ? "Add position" : "Edit work experience"}
          confirmLabel="Save"
          busy={busy}
          wide
          onConfirm={saveJob}
          onClose={closeForm}
        >
          <Alert type="error">{error}</Alert>
          <fieldset className="profile-edit-group">
            <legend>Employment</legend>
            {editing === "new" ? (
              <label className={`dialog-choice${draftingUnemployed ? " is-selected" : ""}`}>
                <input
                  type="checkbox"
                  checked={draftingUnemployed}
                  disabled={busy}
                  onChange={(e) => setDraftStatus(e.target.checked ? "unemployed" : "employed")}
                />
                <span>Unemployed</span>
              </label>
            ) : null}
            {editing === "new" && draftingUnemployed ? (
              <>
                <Field label="Reason" required>
                  <select value={draftReason} onChange={(e) => setDraftReason(e.target.value)} disabled={busy}>
                    <option value="">Select a reason</option>
                    {UNEMPLOYMENT_REASONS.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={draftReason === "other" ? "Please specify" : "Additional details"}
                  required={draftReason === "other"}
                  hint={draftReason === "other" ? `${draftDetails.length}/500` : `Optional. ${draftDetails.length}/500`}
                >
                  <textarea
                    rows={3}
                    value={draftDetails}
                    maxLength={500}
                    disabled={busy}
                    placeholder={draftReason === "other" ? "Add a short explanation." : "Add a note if you want to share more."}
                    onChange={(e) => setDraftDetails(e.target.value)}
                  />
                </Field>
              </>
            ) : (
            <>
            <div className="inline-fields">
              <Field label="Occupation" required={editing !== "new" || !draftingUnemployed}>
                <input
                  value={form.job_title}
                  onChange={(e) => setForm({ ...form, job_title: e.target.value })}
                  maxLength={200}
                />
              </Field>
              <Field label="Company" required={editing !== "new" || !draftingUnemployed}>
                <input
                  value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })}
                  maxLength={200}
                />
              </Field>
            </div>
            <div className="inline-fields">
              <Field label="Industry">
                <select value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}>
                  <option value="">Select industry</option>
                  {form.industry && !INDUSTRIES.includes(form.industry) ? (
                    <option value={form.industry}>{form.industry}</option>
                  ) : null}
                  {INDUSTRIES.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </Field>
              <Field label="Location">
                <input
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  maxLength={120}
                />
              </Field>
            </div>
            </>
            )}
          </fieldset>
          {editing === "new" && draftingUnemployed ? null : (
          <>
          <fieldset className="profile-edit-group">
            <legend>Dates</legend>
            <div className="inline-fields">
              <Field label="Start date">
                <DateField
                  value={form.start_date}
                  onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                />
              </Field>
              <Field
                label="End date"
                hint={
                  unemployed && form.is_current
                    ? "This role stays on your record. Update your employment status before changing whether it is current."
                    : form.is_current
                      ? "Current roles do not need an end date."
                      : undefined
                }
              >
                <DateField
                  value={form.is_current ? "" : form.end_date}
                  disabled={form.is_current}
                  onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                />
              </Field>
            </div>
            {(editing === "new" ? draftingUnemployed : unemployed) ? null : (
              <label className="check">
                <input
                  type="checkbox"
                  checked={form.is_current}
                  onChange={(e) => setForm({ ...form, is_current: e.target.checked, end_date: e.target.checked ? "" : form.end_date })}
                />
                Currently in this role
              </label>
            )}
          </fieldset>
          <fieldset className="profile-edit-group">
            <legend>Compensation</legend>
            <Field label="Salary range" hint="Optional. You can leave this blank.">
              <select value={form.salary_range} onChange={(e) => setForm({ ...form, salary_range: e.target.value })}>
                <option value="">Not specified</option>
                {form.salary_range && !SALARY_RANGES.includes(form.salary_range) ? (
                  <option value={form.salary_range}>{form.salary_range}</option>
                ) : null}
                {SALARY_RANGES.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </Field>
          </fieldset>
          <fieldset className="profile-edit-group">
            <legend>Details</legend>
            <Field label="Description" hint={`${form.description.length}/800`}>
              <textarea
                rows={4}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                maxLength={800}
              />
            </Field>
          </fieldset>
          </>
          )}
        </Dialog>
      ) : null}
      {removing ? (
        <Dialog
          title="Delete this work experience?"
          confirmLabel="Delete"
          danger
          busy={busy}
          onConfirm={confirmRemove}
          onClose={() => { if (!busy) setRemoving(null); }}
        >
          <Alert type="error">{error}</Alert>
          <p>
            {removing.job_title} at {removing.company} will be removed from your work history.
          </p>
        </Dialog>
      ) : null}
    </section>
  );
}
