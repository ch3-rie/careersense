import { useEffect, useState } from "react";
import { Alert, Dialog, Empty, Field } from "./ui";
import { MapPinIcon, PencilIcon, PlusIcon, TrashIcon } from "./icons";
import { api } from "../lib/api";
import { formatEmploymentPeriod } from "../lib/format";
import { showToast } from "../lib/toasts";
import { friendlyError } from "../lib/userMessages";

const EMPTY_FORM = {
  job_title: "",
  company: "",
  start_date: "",
  end_date: "",
  is_current: false,
  industry: "",
  location: "",
  description: "",
};

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

export function JobTimeline({ jobs, onJobsChange, className = "", summary = false, onManage, limit }) {
  const [items, setItems] = useState(jobs || []);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const formOpen = editing !== null;
  const displayItems = orderedJobs(items);

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
      description: job.description || "",
    });
  }

  function closeForm() {
    if (busy) return;
    setEditing(null);
    setError("");
    setForm(EMPTY_FORM);
  }

  async function saveJob() {
    const title = form.job_title.trim();
    const company = form.company.trim();
    if (!title || !company) {
      setError("Occupation and company are required.");
      return;
    }
    if (form.start_date && form.end_date && !form.is_current && form.end_date < form.start_date) {
      setError("End date must be on or after the start date.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = {
        job_title: title,
        company,
        start_date: form.start_date || null,
        end_date: form.is_current ? null : form.end_date || null,
        is_current: Boolean(form.is_current),
        industry: form.industry.trim(),
        location: form.location.trim(),
        description: form.description.trim(),
      };
      const isEdit = editing && editing !== "new";
      const result = await api(isEdit ? `/api/alumni/jobs/${editing.id}` : "/api/alumni/jobs", {
        method: isEdit ? "PUT" : "POST",
        body,
      });
      applyJobs(result.jobs);
      setEditing(null);
      setForm(EMPTY_FORM);
      showToast("success", isEdit ? "Work experience updated." : "Work experience added.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't save this work experience. Please try again."));
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

  if (summary) {
    const visible = typeof limit === "number" ? displayItems.slice(0, limit) : displayItems;
    const hidden = Math.max(0, displayItems.length - visible.length);
    return (
      <section className={`alumni-block ${className}`.trim()} aria-label="Work History">
        <header className="profile-section-head">
          <div>
            <h2>Work History</h2>
          </div>
          {onManage ? (
            <button type="button" className="btn btn-outline btn-sm" onClick={onManage}>
              View full record
            </button>
          ) : null}
        </header>
        {!displayItems.length ? (
          <Empty
            compact
            title="No work history yet"
            action={onManage ? (
              <button type="button" className="btn btn-navy btn-sm" onClick={onManage}>
                Add position
              </button>
            ) : null}
          >
            Your employment history will appear here once you add your first position.
          </Empty>
        ) : (
          <>
            <ol className="job-summary">
              {visible.map((job) => (
                <li key={job.id} className={job.is_current ? "is-current" : ""}>
                  <span className="job-dot" aria-hidden="true" />
                  <div>
                    {periodLine(job, true) ? <p className="job-when">{periodLine(job, true)}</p> : null}
                    <strong>{job.job_title}</strong>
                    <p>{job.company}</p>
                    {job.location ? <p className="muted">{job.location}</p> : null}
                  </div>
                </li>
              ))}
            </ol>
            {hidden ? <p className="muted">{hidden} earlier {hidden === 1 ? "position" : "positions"} on your full record.</p> : null}
          </>
        )}
        <p className="profile-note">Official current occupation comes from your submitted Graduate Tracer Survey, not from this list.</p>
      </section>
    );
  }

  return (
    <section className={`alumni-block job-timeline-panel ${className}`.trim()} id="work-history" aria-label="Work History">
      <header className="profile-section-head">
        <div>
          <h2>Work History</h2>
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-navy btn-sm" onClick={openAdd}>
            <PlusIcon size={16} />
            Add position
          </button>
        </div>
      </header>
      <Alert type="error">{!formOpen && !removing ? error : null}</Alert>
      {!items.length ? (
        <div className="job-timeline-empty">
          <Empty
            compact
            title="No work history yet"
            action={(
              <button type="button" className="btn btn-navy btn-sm" onClick={openAdd}>
                <PlusIcon size={16} />
                Add position
              </button>
            )}
          >
            Your employment history will appear here once you add your first position.
          </Empty>
        </div>
      ) : (
        <ol className="job-timeline" aria-label="Work History, current and most recent first">
          {displayItems.map((job) => {
            const when = periodLine(job, true);
            return (
              <li key={job.id} className={`job-timeline-item${job.is_current ? " is-current" : " is-past"}`}>
                <span className="job-dot" aria-hidden="true" />
                <article className="job-card">
                  <div className="job-card-top">
                    <div className="job-card-copy">
                      <strong>{job.job_title}</strong>
                      {job.company ? <p className="job-company">{job.company}</p> : null}
                      {when || job.is_current || job.duration ? (
                        <p className="job-when">
                          {when || job.duration ? (
                            <span>
                              {when}
                              {when && job.duration ? " · " : ""}
                              {job.duration}
                            </span>
                          ) : null}
                          {job.is_current ? <span className="job-now">Current</span> : null}
                        </p>
                      ) : null}
                      {job.location ? (
                        <p className="job-location">
                          <MapPinIcon size={14} />
                          <span>{job.location}</span>
                        </p>
                      ) : null}
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
                  {job.description ? <p className="job-description">{job.description}</p> : null}
                </article>
              </li>
            );
          })}
        </ol>
      )}
      {formOpen ? (
        <Dialog
          title={editing === "new" ? "Add work experience" : "Edit work experience"}
          confirmLabel="Save"
          busy={busy}
          onConfirm={saveJob}
          onClose={closeForm}
        >
          <Alert type="error">{error}</Alert>
          <Field label="Occupation" required>
            <input
              value={form.job_title}
              onChange={(e) => setForm({ ...form, job_title: e.target.value })}
              maxLength={200}
            />
          </Field>
          <Field label="Company" required>
            <input
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
              maxLength={200}
            />
          </Field>
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
          <div className="inline-fields">
            <Field label="Start date">
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </Field>
            <Field label="End date" hint={form.is_current ? "Current roles do not need an end date." : undefined}>
              <input
                type="date"
                value={form.is_current ? "" : form.end_date}
                disabled={form.is_current}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </Field>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={form.is_current}
              onChange={(e) => setForm({ ...form, is_current: e.target.checked, end_date: e.target.checked ? "" : form.end_date })}
            />
            Currently in this role
          </label>
          <Field label="Description" hint={`${form.description.length}/800`}>
            <textarea
              rows={4}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              maxLength={800}
            />
          </Field>
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
