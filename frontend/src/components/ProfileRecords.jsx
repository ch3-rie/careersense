import { useEffect, useState } from "react";
import { isoFromDate } from "./AacCalendar";
import { DateField } from "./DateField";
import { Alert, Dialog, Empty, Field, SectionTitle } from "./ui";
import { FileDrop } from "./FileDrop";
import { FileIcon, PencilIcon, PlusIcon, TrashIcon } from "./icons";
import { api } from "../lib/api";
import { safeHttpUrl } from "../lib/safeUrl";
import { showToast } from "../lib/toasts";
import { CERTIFICATE_ACCEPT, certificateFileError, friendlyError } from "../lib/userMessages";

const WHEN_HINT = "Four-digit year, such as 2024, or a date in YYYY-MM-DD format.";

function ordered(items, field) {
  return [...items].sort((a, b) => {
    const left = String(a[field] || "");
    const right = String(b[field] || "");
    if (left !== right) return right.localeCompare(left);
    return (b.id || 0) - (a.id || 0);
  });
}

async function openAuthorized(path) {
  const blob = await api(path, { blob: true, toast: false });
  const url = URL.createObjectURL(blob);
  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (!opened) {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener";
    link.click();
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function RecordSection({ id, label, title, index, lead, action, error, children }) {
  return (
    <section className="alumni-block study-timeline-panel" id={id} aria-label={label}>
      <header className="profile-section-head">
        <SectionTitle index={index} title={title} lead={lead} />
        {action}
      </header>
      <Alert type="error">{error}</Alert>
      {children}
    </section>
  );
}

function RowActions({ label, onEdit, onRemove }) {
  return (
    <div className="job-card-actions">
      <button type="button" className="btn btn-text btn-sm icon-btn" aria-label={`Edit ${label}`} title="Edit" onClick={onEdit}>
        <PencilIcon size={16} />
      </button>
      <button type="button" className="btn btn-text btn-sm icon-btn" aria-label={`Remove ${label}`} title="Remove" onClick={onRemove}>
        <TrashIcon size={16} />
      </button>
    </div>
  );
}

function useRecordList(initial) {
  const [items, setItems] = useState(initial || []);
  const [editing, setEditing] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setItems(initial || []);
  }, [initial]);
  return { items, setItems, editing, setEditing, removing, setRemoving, error, setError, busy, setBusy };
}

export function SeminarList({ seminars, onChange, index, lead }) {
  const state = useRecordList(seminars);
  const [form, setForm] = useState({ title: "", location: "", held_on: "", organizer: "" });
  const displayItems = ordered(state.items, "held_on");
  const formOpen = state.editing !== null;

  function openAdd() {
    state.setError("");
    state.setEditing("new");
    setForm({ title: "", location: "", held_on: "", organizer: "" });
  }

  function openEdit(row) {
    state.setError("");
    state.setEditing(row);
    setForm({
      title: row.title || "",
      location: row.location || "",
      held_on: row.held_on || "",
      organizer: row.organizer || "",
    });
  }

  async function save() {
    if (!form.title.trim() || !form.location.trim()) {
      state.setError("Seminar name and location are required.");
      return;
    }
    state.setBusy(true);
    state.setError("");
    try {
      const isEdit = state.editing && state.editing !== "new";
      const result = await api(isEdit ? `/api/alumni/seminars/${state.editing.id}` : "/api/alumni/seminars", {
        method: isEdit ? "PUT" : "POST",
        body: {
          title: form.title.trim(),
          location: form.location.trim(),
          held_on: form.held_on.trim(),
          organizer: form.organizer.trim(),
        },
      });
      state.setItems(result.seminars);
      onChange?.(result.seminars);
      state.setEditing(null);
      showToast("success", isEdit ? "Seminar updated." : "Seminar added.");
    } catch (err) {
      state.setError(friendlyError(err, "We couldn't save this seminar. Please try again."));
    } finally {
      state.setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!state.removing) return;
    state.setBusy(true);
    state.setError("");
    try {
      const result = await api(`/api/alumni/seminars/${state.removing.id}`, { method: "DELETE" });
      state.setItems(result.seminars);
      onChange?.(result.seminars);
      state.setRemoving(null);
      showToast("success", "Seminar removed.");
    } catch (err) {
      state.setError(friendlyError(err, "We couldn't delete this seminar. Please try again."));
    } finally {
      state.setBusy(false);
    }
  }

  return (
    <RecordSection
      id="seminars"
      index={index}
      lead={lead || "Seminar name and location are required."}
      label="Seminars Attended"
      title="Seminars Attended"
      error={!formOpen && !state.removing ? state.error : null}
      action={(
        <div className="panel-actions">
          <button type="button" className="btn btn-navy btn-sm" onClick={openAdd}>
            <PlusIcon size={16} />
            Add seminar
          </button>
        </div>
      )}
    >
      {!state.items.length ? (
        <Empty compact title="No seminars added yet">
          Add a seminar when you are ready.
        </Empty>
      ) : (
        <ol className="job-timeline" aria-label="Seminars attended, most recent first">
          {displayItems.map((row) => (
            <li key={row.id} className="job-timeline-item is-past">
              <span className="job-dot" aria-hidden="true" />
              <article className="job-card">
                <div className="job-card-top">
                  <div className="job-card-copy">
                    {row.held_on ? <p className="job-when"><time>{row.held_on}</time></p> : null}
                    <strong>{row.title}</strong>
                    {row.organizer ? <p className="job-company">{row.organizer}</p> : null}
                  </div>
                  <RowActions label={row.title || "seminar"} onEdit={() => openEdit(row)} onRemove={() => { state.setError(""); state.setRemoving(row); }} />
                </div>
                {row.location ? (
                  <ul className="timeline-facts">
                    <li>{row.location}</li>
                  </ul>
                ) : null}
              </article>
            </li>
          ))}
        </ol>
      )}
      {formOpen ? (
        <Dialog title={state.editing === "new" ? "Add seminar" : "Edit seminar"} confirmLabel="Save" busy={state.busy} wide onConfirm={save} onClose={() => { if (!state.busy) state.setEditing(null); }}>
          <Alert type="error">{state.error}</Alert>
          <fieldset className="profile-edit-group">
            <legend>Seminar</legend>
            <Field label="Seminar" required>
              <input value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </Field>
            <Field label="Location of Seminar" required>
              <input value={form.location} maxLength={200} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            </Field>
            <div className="inline-fields">
              <Field label="Date or year" hint={WHEN_HINT}>
                <DateField allowYear max={isoFromDate(new Date())} value={form.held_on} onChange={(e) => setForm({ ...form, held_on: e.target.value })} />
              </Field>
              <Field label="Organizer" hint="Optional.">
                <input value={form.organizer} maxLength={200} onChange={(e) => setForm({ ...form, organizer: e.target.value })} />
              </Field>
            </div>
          </fieldset>
        </Dialog>
      ) : null}
      {state.removing ? (
        <Dialog title="Delete this seminar?" confirmLabel="Delete" danger busy={state.busy} onConfirm={confirmRemove} onClose={() => { if (!state.busy) state.setRemoving(null); }}>
          <Alert type="error">{state.error}</Alert>
          <p>{state.removing.title} will be removed from your alumni profile.</p>
        </Dialog>
      ) : null}
    </RecordSection>
  );
}

const EMPTY_CERT = { name: "", awarded_on: "", awarding_body: "", verification_url: "", file: null };

export function CertificationList({ certifications, onChange, index, lead }) {
  const state = useRecordList(certifications);
  const [form, setForm] = useState(EMPTY_CERT);
  const displayItems = ordered(state.items, "awarded_on");
  const formOpen = state.editing !== null;

  function openAdd() {
    state.setError("");
    state.setEditing("new");
    setForm(EMPTY_CERT);
  }

  function openEdit(row) {
    state.setError("");
    state.setEditing(row);
    setForm({
      name: row.name || "",
      awarded_on: row.awarded_on || "",
      awarding_body: row.awarding_body || "",
      verification_url: row.verification_url || "",
      file: null,
    });
  }

  async function viewFile(row) {
    state.setError("");
    try {
      await openAuthorized(`/api/alumni/certifications/${row.id}/file`);
    } catch (err) {
      state.setError(friendlyError(err, "We couldn't open this certificate. Please try again."));
    }
  }

  async function save() {
    if (!form.name.trim() || !form.awarding_body.trim() || !form.awarded_on.trim()) {
      state.setError("Certification name, awarding body, and award date or year are required.");
      return;
    }
    const link = form.verification_url.trim();
    const safeLink = link ? safeHttpUrl(link) : "";
    let linkHost = "";
    try {
      linkHost = safeLink ? new URL(safeLink).hostname : "";
    } catch {
      linkHost = "";
    }
    if (link && (/\s/.test(link) || !safeLink || !linkHost.includes("."))) {
      state.setError("Enter a valid http or https verification link, or leave it blank.");
      return;
    }
    const isEdit = state.editing && state.editing !== "new";
    if (!isEdit && !form.file) {
      state.setError("Upload a certificate or badge (PDF, JPG, PNG, or WebP).");
      return;
    }
    state.setBusy(true);
    state.setError("");
    try {
      let rows;
      if (!isEdit) {
        const body = new FormData();
        body.append("name", form.name.trim());
        body.append("awarded_on", form.awarded_on.trim());
        body.append("awarding_body", form.awarding_body.trim());
        body.append("verification_url", link);
        body.append("certificate", form.file);
        const result = await api("/api/alumni/certifications", { method: "POST", form: body });
        rows = result.certifications;
      } else {
        const result = await api(`/api/alumni/certifications/${state.editing.id}`, {
          method: "PUT",
          body: {
            name: form.name.trim(),
            awarded_on: form.awarded_on.trim(),
            awarding_body: form.awarding_body.trim(),
            verification_url: link,
          },
        });
        rows = result.certifications;
        if (form.file) {
          const body = new FormData();
          body.append("certificate", form.file);
          const replaced = await api(`/api/alumni/certifications/${state.editing.id}/file`, { method: "POST", form: body });
          rows = replaced.certifications;
        }
      }
      state.setItems(rows);
      onChange?.(rows);
      state.setEditing(null);
      showToast("success", isEdit ? "Certification updated." : "Certification added.");
    } catch (err) {
      state.setError(friendlyError(err, "We couldn't save this certification. Please try again."));
    } finally {
      state.setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!state.removing) return;
    state.setBusy(true);
    state.setError("");
    try {
      const result = await api(`/api/alumni/certifications/${state.removing.id}`, { method: "DELETE" });
      state.setItems(result.certifications);
      onChange?.(result.certifications);
      state.setRemoving(null);
      showToast("success", "Certification removed.");
    } catch (err) {
      state.setError(friendlyError(err, "We couldn't delete this certification. Please try again."));
    } finally {
      state.setBusy(false);
    }
  }

  return (
    <RecordSection
      id="certifications"
      index={index}
      lead={lead || "Name, awarding body, date, and a certificate file are required."}
      label="Certifications"
      title="Certifications"
      error={!formOpen && !state.removing ? state.error : null}
      action={(
        <div className="panel-actions">
          <button type="button" className="btn btn-navy btn-sm" onClick={openAdd}>
            <PlusIcon size={16} />
            Add certification
          </button>
        </div>
      )}
    >
      {!state.items.length ? (
        <Empty compact title="No certifications added yet">
          Add a certificate or badge when you are ready.
        </Empty>
      ) : (
        <ol className="job-timeline" aria-label="Certifications, most recent first">
          {displayItems.map((row) => {
            const verify = safeHttpUrl(row.verification_url);
            return (
              <li key={row.id} className="job-timeline-item is-past">
                <span className="job-dot" aria-hidden="true" />
                <article className="job-card">
                  <div className="job-card-top">
                    <div className="job-card-copy">
                      {row.awarded_on ? <p className="job-when"><time>{row.awarded_on}</time></p> : null}
                      <strong>{row.name}</strong>
                      <p className="job-company">{row.awarding_body}</p>
                      <div className="cert-links">
                        {row.has_certificate ? (
                          <button type="button" className="btn btn-text btn-sm cert-file-link" onClick={() => viewFile(row)}>
                            <FileIcon size={14} />
                            {row.certificate_filename || "View certificate"}
                          </button>
                        ) : null}
                        {verify ? (
                          <a className="cert-file-link" href={verify} target="_blank" rel="noopener noreferrer">
                            Verify badge
                          </a>
                        ) : (
                          <span className="muted">No verification link</span>
                        )}
                      </div>
                    </div>
                    <RowActions label={row.name || "certification"} onEdit={() => openEdit(row)} onRemove={() => { state.setError(""); state.setRemoving(row); }} />
                  </div>
                </article>
              </li>
            );
          })}
        </ol>
      )}
      {formOpen ? (
        <Dialog title={state.editing === "new" ? "Add certification" : "Edit certification"} confirmLabel="Save" busy={state.busy} wide onConfirm={save} onClose={() => { if (!state.busy) state.setEditing(null); }}>
          <Alert type="error">{state.error}</Alert>
          <fieldset className="profile-edit-group">
            <legend>Certification</legend>
            <div className="inline-fields">
              <Field label="Certification" required>
                <input value={form.name} maxLength={200} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Field>
              <Field label="Awarding body" required>
                <input value={form.awarding_body} maxLength={200} onChange={(e) => setForm({ ...form, awarding_body: e.target.value })} />
              </Field>
            </div>
            <Field label="Date or year awarded" required hint={WHEN_HINT}>
              <DateField allowYear max={isoFromDate(new Date())} value={form.awarded_on} onChange={(e) => setForm({ ...form, awarded_on: e.target.value })} />
            </Field>
          </fieldset>
          <fieldset className="profile-edit-group">
            <legend>Proof</legend>
            <FileDrop
              file={form.file}
              currentName={state.editing && state.editing !== "new" ? (state.editing.certificate_filename || "Current certificate") : ""}
              accept={CERTIFICATE_ACCEPT}
              validate={certificateFileError}
              required={state.editing === "new"}
              disabled={state.busy}
              compact
              status={state.busy && form.file ? "uploading" : "idle"}
              label="Certificate or badge"
              formats="PDF, JPG, PNG, or WebP"
              maxSize="Maximum 10 MB"
              description={state.editing === "new" ? "A certificate or badge is required for a new certification." : "Replace the file only if you want to update the one already on file."}
              onChange={(file) => setForm({ ...form, file })}
            />
            <Field label="Verification URL" hint="Optional. A public page where this badge or certificate can be checked.">
              <input value={form.verification_url} maxLength={500} placeholder="https://" onChange={(e) => setForm({ ...form, verification_url: e.target.value })} />
            </Field>
          </fieldset>
        </Dialog>
      ) : null}
      {state.removing ? (
        <Dialog title="Delete this certification?" confirmLabel="Delete" danger busy={state.busy} onConfirm={confirmRemove} onClose={() => { if (!state.busy) state.setRemoving(null); }}>
          <Alert type="error">{state.error}</Alert>
          <p>{state.removing.name} and its uploaded certificate will be removed from your alumni profile.</p>
        </Dialog>
      ) : null}
    </RecordSection>
  );
}

const EMPTY_AWARD = { title: "", issuer: "", awarded_on: "", description: "" };

export function AwardList({ awards, onChange, index, lead }) {
  const state = useRecordList(awards);
  const [form, setForm] = useState(EMPTY_AWARD);
  const displayItems = ordered(state.items, "awarded_on");
  const formOpen = state.editing !== null;

  function openAdd() {
    state.setError("");
    state.setEditing("new");
    setForm(EMPTY_AWARD);
  }

  function openEdit(row) {
    state.setError("");
    state.setEditing(row);
    setForm({
      title: row.title || "",
      issuer: row.issuer || "",
      awarded_on: row.awarded_on || "",
      description: row.description || "",
    });
  }

  async function save() {
    if (!form.title.trim()) {
      state.setError("Award or achievement title is required.");
      return;
    }
    state.setBusy(true);
    state.setError("");
    try {
      const isEdit = state.editing && state.editing !== "new";
      const result = await api(isEdit ? `/api/alumni/awards/${state.editing.id}` : "/api/alumni/awards", {
        method: isEdit ? "PUT" : "POST",
        body: {
          title: form.title.trim(),
          issuer: form.issuer.trim(),
          awarded_on: form.awarded_on.trim(),
          description: form.description.trim(),
        },
      });
      state.setItems(result.awards);
      onChange?.(result.awards);
      state.setEditing(null);
      showToast("success", isEdit ? "Award updated." : "Award added.");
    } catch (err) {
      state.setError(friendlyError(err, "We couldn't save this award. Please try again."));
    } finally {
      state.setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!state.removing) return;
    state.setBusy(true);
    state.setError("");
    try {
      const result = await api(`/api/alumni/awards/${state.removing.id}`, { method: "DELETE" });
      state.setItems(result.awards);
      onChange?.(result.awards);
      state.setRemoving(null);
      showToast("success", "Award removed.");
    } catch (err) {
      state.setError(friendlyError(err, "We couldn't delete this award. Please try again."));
    } finally {
      state.setBusy(false);
    }
  }

  return (
    <RecordSection
      id="awards"
      index={index}
      lead={lead || "The award or achievement title is required."}
      label="Awards / Achievements Received"
      title="Awards / Achievements Received"
      error={!formOpen && !state.removing ? state.error : null}
      action={(
        <div className="panel-actions">
          <button type="button" className="btn btn-navy btn-sm" onClick={openAdd}>
            <PlusIcon size={16} />
            Add award
          </button>
        </div>
      )}
    >
      {!state.items.length ? (
        <Empty compact title="No awards or achievements added yet">
          Add an award or achievement when you are ready.
        </Empty>
      ) : (
        <ol className="job-timeline" aria-label="Awards and achievements, most recent first">
          {displayItems.map((row) => (
            <li key={row.id} className="job-timeline-item is-past">
              <span className="job-dot" aria-hidden="true" />
              <article className="job-card">
                <div className="job-card-top">
                  <div className="job-card-copy">
                    {row.awarded_on ? <p className="job-when"><time>{row.awarded_on}</time></p> : null}
                    <strong>{row.title}</strong>
                    {row.issuer ? <p className="job-company">{row.issuer}</p> : null}
                  </div>
                  <RowActions label={row.title || "award"} onEdit={() => openEdit(row)} onRemove={() => { state.setError(""); state.setRemoving(row); }} />
                </div>
                {row.description ? <p className="job-description">{row.description}</p> : null}
              </article>
            </li>
          ))}
        </ol>
      )}
      {formOpen ? (
        <Dialog title={state.editing === "new" ? "Add award or achievement" : "Edit award or achievement"} confirmLabel="Save" busy={state.busy} wide onConfirm={save} onClose={() => { if (!state.busy) state.setEditing(null); }}>
          <Alert type="error">{state.error}</Alert>
          <fieldset className="profile-edit-group">
            <legend>Award</legend>
            <Field label="Award or achievement" required>
              <input value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </Field>
            <div className="inline-fields">
              <Field label="Awarded by" hint="Optional.">
                <input value={form.issuer} maxLength={200} onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
              </Field>
              <Field label="Date or year" hint={WHEN_HINT}>
                <DateField allowYear max={isoFromDate(new Date())} value={form.awarded_on} onChange={(e) => setForm({ ...form, awarded_on: e.target.value })} />
              </Field>
            </div>
            <Field label="Description" hint={`${form.description.length}/800`}>
              <textarea rows={4} maxLength={800} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
          </fieldset>
        </Dialog>
      ) : null}
      {state.removing ? (
        <Dialog title="Delete this award?" confirmLabel="Delete" danger busy={state.busy} onConfirm={confirmRemove} onClose={() => { if (!state.busy) state.setRemoving(null); }}>
          <Alert type="error">{state.error}</Alert>
          <p>{state.removing.title} will be removed from your alumni profile.</p>
        </Dialog>
      ) : null}
    </RecordSection>
  );
}
