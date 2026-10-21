import { useEffect, useState } from "react";
import { DateField } from "./DateField";
import { Alert, Dialog, Empty, Field, SectionTitle } from "./ui";
import { PencilIcon, PlusIcon, TrashIcon } from "./icons";
import { api } from "../lib/api";
import { showToast } from "../lib/toasts";
import { friendlyError } from "../lib/userMessages";

const EMPTY_FORM = {
  course_degree: "",
  school: "",
  institution_address: "",
  year_enrolled: "",
  scholarship: "",
  status: "",
};

function studyPeriod(row) {
  const year = String(row.year_enrolled || "").trim();
  if (row.is_graduated === false) {
    return year ? `${year} — Present` : "Present";
  }
  return year;
}

function orderedStudies(items) {
  return [...items].sort((a, b) => {
    const currentA = a.is_graduated === false;
    const currentB = b.is_graduated === false;
    if (currentA !== currentB) return currentA ? -1 : 1;
    const yearA = String(a.year_enrolled || "");
    const yearB = String(b.year_enrolled || "");
    if (yearA !== yearB) return yearB.localeCompare(yearA);
    return (b.id || 0) - (a.id || 0);
  });
}

function statusFromRow(row) {
  if (row.is_graduated === false) return "enrolled";
  if (row.is_graduated === true) return "completed";
  return "";
}

function isGraduatedFromStatus(status) {
  if (status === "enrolled") return false;
  if (status === "completed") return true;
  return null;
}

export function StudyTimeline({ studies, onStudiesChange, embedded = false, index, lead, degreeRecord = null }) {
  const [items, setItems] = useState(studies || []);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const formOpen = editing !== null;
  const displayItems = orderedStudies(items);

  useEffect(() => {
    setItems(studies || []);
  }, [studies]);

  function applyStudies(next) {
    setItems(next);
    onStudiesChange?.(next);
  }

  function openAdd() {
    setError("");
    setEditing("new");
    setForm(EMPTY_FORM);
  }

  function openEdit(row) {
    setError("");
    setEditing(row);
    setForm({
      course_degree: row.course_degree || "",
      school: row.school || "",
      institution_address: row.institution_address || "",
      year_enrolled: row.year_enrolled || "",
      scholarship: row.scholarship || "",
      status: statusFromRow(row),
    });
  }

  function closeForm() {
    if (busy) return;
    setEditing(null);
    setError("");
    setForm(EMPTY_FORM);
  }

  async function saveStudy() {
    const course = form.course_degree.trim();
    const school = form.school.trim();
    if (!course || !school) {
      setError("Program and institution are required.");
      return;
    }
    const year = form.year_enrolled.trim();
    if (year && !/^\d{4}$/.test(year)) {
      setError("Year enrolled must be a four-digit year.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = {
        course_degree: course,
        school,
        institution_address: form.institution_address.trim(),
        year_enrolled: year,
        scholarship: form.scholarship.trim(),
        is_graduated: isGraduatedFromStatus(form.status),
      };
      const isEdit = editing && editing !== "new";
      const result = await api(isEdit ? `/api/alumni/studies/${editing.id}` : "/api/alumni/studies", {
        method: isEdit ? "PUT" : "POST",
        body,
      });
      applyStudies(result.studies);
      setEditing(null);
      setForm(EMPTY_FORM);
      showToast("success", isEdit ? "Further study updated." : "Further study added.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't save this further study. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!removing) return;
    setBusy(true);
    setError("");
    try {
      const result = await api(`/api/alumni/studies/${removing.id}`, { method: "DELETE" });
      applyStudies(result.studies);
      setRemoving(null);
      showToast("success", "Further study removed.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't delete this further study. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`alumni-block study-timeline-panel${embedded ? " is-embedded" : ""}`} id="further-studies" aria-label="Further Studies / Degrees Earned">
      <header className="profile-section-head">
        <SectionTitle
          index={embedded ? undefined : index}
          as={embedded ? "h3" : "h2"}
          title="Further Studies / Degrees Earned"
          lead={embedded ? undefined : (lead || "Your AUF bachelor’s degree stays on this record. Add later programs below.")}
        />
        <div className="panel-actions">
          <button type="button" className="btn btn-navy btn-sm" onClick={openAdd}>
            <PlusIcon size={16} />
            Add further study
          </button>
        </div>
      </header>
      <Alert type="error">{!formOpen && !removing ? error : null}</Alert>
      {degreeRecord ? (
        <article className="profile-degree-earned">
          <p className="eyebrow">Bachelor’s degree earned</p>
          <strong>{degreeRecord.degree || "Degree not on file"}</strong>
          {degreeRecord.college ? <p>{degreeRecord.college}</p> : null}
          <p className="job-when">{degreeRecord.yearGraduated ? `Graduated ${degreeRecord.yearGraduated}` : "Graduation year not on file"}</p>
        </article>
      ) : null}
      {!items.length ? (
        <Empty
          compact
          title="No further studies or degrees recorded yet"
        >
          Add a later degree or program when you are ready.
        </Empty>
      ) : (
        <ol className="job-timeline" aria-label="Further Studies / Degrees Earned, current and most recent first">
          {displayItems.map((row) => {
            const when = studyPeriod(row);
            const current = row.is_graduated === false;
            return (
              <li key={row.id} className={`job-timeline-item${current ? " is-current" : " is-past"}`}>
                <span className="job-dot" aria-hidden="true" />
                <article className="job-card">
                  <div className="job-card-top">
                    <div className="job-card-copy">
                      {when || current ? (
                        <p className="job-when">
                          {when ? <time>{when}</time> : null}
                          {current ? <span className="job-now">Current</span> : null}
                        </p>
                      ) : null}
                      <strong>{row.course_degree || "Program"}</strong>
                      {row.school ? <p className="job-company">{row.school}</p> : null}
                    </div>
                    <div className="job-card-actions">
                      <button
                        type="button"
                        className="btn btn-text btn-sm icon-btn"
                        aria-label={`Edit ${row.course_degree || "further study"}`}
                        title="Edit"
                        onClick={() => openEdit(row)}
                      >
                        <PencilIcon size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-text btn-sm icon-btn"
                        aria-label={`Remove ${row.course_degree || "further study"}`}
                        title="Remove"
                        onClick={() => { setError(""); setRemoving(row); }}
                      >
                        <TrashIcon size={16} />
                      </button>
                    </div>
                  </div>
                  {row.institution_address || row.scholarship ? (
                    <ul className="timeline-facts">
                      {row.institution_address ? <li>{row.institution_address}</li> : null}
                      {row.scholarship ? <li>{row.scholarship}</li> : null}
                    </ul>
                  ) : null}
                </article>
              </li>
            );
          })}
        </ol>
      )}
      {formOpen ? (
        <Dialog
          title={editing === "new" ? "Add further study" : "Edit further study"}
          confirmLabel="Save"
          busy={busy}
          wide
          onConfirm={saveStudy}
          onClose={closeForm}
        >
          <Alert type="error">{error}</Alert>
          <fieldset className="profile-edit-group">
            <legend>Program</legend>
            <div className="inline-fields">
              <Field label="Program" required>
                <input
                  value={form.course_degree}
                  onChange={(e) => setForm({ ...form, course_degree: e.target.value })}
                  maxLength={200}
                />
              </Field>
              <Field label="Institution" required>
                <input
                  value={form.school}
                  onChange={(e) => setForm({ ...form, school: e.target.value })}
                  maxLength={200}
                />
              </Field>
            </div>
            <Field label="Address of Institution" hint="Optional. Street or campus address of the school.">
              <input
                value={form.institution_address}
                onChange={(e) => setForm({ ...form, institution_address: e.target.value })}
                maxLength={240}
              />
            </Field>
          </fieldset>
          <fieldset className="profile-edit-group">
            <legend>Enrollment</legend>
            <div className="inline-fields">
              <Field label="Year enrolled" hint="Four-digit year, if known.">
                <DateField
                  mode="year"
                  min="1950"
                  max={String(new Date().getFullYear() + 8)}
                  value={form.year_enrolled}
                  onChange={(e) => setForm({ ...form, year_enrolled: e.target.value })}
                />
              </Field>
              <Field label="Status">
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  <option value="">Not specified</option>
                  <option value="enrolled">Currently enrolled</option>
                  <option value="completed">Completed</option>
                </select>
              </Field>
            </div>
            <Field label="Scholarship" hint="Optional.">
              <input
                value={form.scholarship}
                onChange={(e) => setForm({ ...form, scholarship: e.target.value })}
                maxLength={200}
              />
            </Field>
          </fieldset>
        </Dialog>
      ) : null}
      {removing ? (
        <Dialog
          title="Delete this further study?"
          confirmLabel="Delete"
          danger
          busy={busy}
          onConfirm={confirmRemove}
          onClose={() => { if (!busy) setRemoving(null); }}
        >
          <Alert type="error">{error}</Alert>
          <p>
            {removing.course_degree} at {removing.school} will be removed from your alumni profile.
          </p>
        </Dialog>
      ) : null}
    </section>
  );
}
