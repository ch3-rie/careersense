import { useEffect, useMemo, useState } from "react";
import { MailIcon, PlusIcon } from "../../components/icons";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import {
  Alert,
  Badge,
  Dialog,
  Empty,
  Field,
  LoadError,
  Pager,
  PageHeader,
  PageSkeleton,
} from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate, formatDateTime } from "../../lib/format";
import { showToast } from "../../lib/toasts";
import ProfileRemindersPanel from "./ProfileRemindersPanel";

const STEPS = [
  ["alumni", "Select alumni"],
  ["fields", "Select updates"],
  ["message", "Write message"],
  ["preview", "Preview"],
];

function emptyComposer(options) {
  return {
    subject: options?.default_subject || "Action Required: Please Update Your CareerSense Profile",
    message: options?.default_message || "",
    fields: [],
    other_detail: "",
  };
}

function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "completed" || value === "updated" || value === "sent") return "aligned";
  if (value.includes("partial") || value === "viewed" || value === "disabled") return "unknown";
  if (value.includes("fail") || value.includes("not yet")) return "misaligned";
  return "";
}

export default function AdminProfileUpdates() {
  const [options, setOptions] = useState(null);
  const [list, setList] = useState(null);
  const [listPage, setListPage] = useState(1);
  const [error, setError] = useState("");
  const [composing, setComposing] = useState(false);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(emptyComposer());
  const [selected, setSelected] = useState({});
  const [alumni, setAlumni] = useState(null);
  const [alumniPage, setAlumniPage] = useState(1);
  const [filters, setFilters] = useState({ q: "", year: "", degree: "", completion: "" });
  const [applied, setApplied] = useState({ q: "", year: "", degree: "", completion: "" });
  const [alumniBusy, setAlumniBusy] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);
  const [duplicates, setDuplicates] = useState(null);
  const [sending, setSending] = useState(false);
  const [detail, setDetail] = useState(null);

  const fieldOptions = options?.fields || list?.fields || [];
  const selectedAlumni = useMemo(() => Object.values(selected), [selected]);
  const selectedFields = fieldOptions.filter((item) => form.fields.includes(item.id));

  async function loadList(page = 1) {
    setError("");
    try {
      const data = await api(`/api/admin/profile-update-requests?page=${page}&page_size=10`);
      setList(data);
      setListPage(page);
      if (!options) setOptions(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadAlumni(page = 1, nextFilters = applied) {
    setAlumniBusy(true);
    setError("");
    try {
      const params = new URLSearchParams({
        q: nextFilters.q,
        year: nextFilters.year,
        degree: nextFilters.degree,
        completion: nextFilters.completion,
        page: String(page),
        page_size: "10",
      });
      setAlumni(await api(`/api/admin/profile-update-requests/alumni?${params}`));
      setAlumniPage(page);
      setApplied(nextFilters);
    } catch (err) {
      setError(err.message);
    } finally {
      setAlumniBusy(false);
    }
  }

  useEffect(() => {
    loadList(1);
    api("/api/admin/profile-update-requests/options").then(setOptions).catch(() => {});
  }, []);

  function startComposer() {
    setForm(emptyComposer(options || list));
    setSelected({});
    setStep(0);
    setComposing(true);
    setDuplicates(null);
    loadAlumni(1, { q: "", year: "", degree: "", completion: "" });
    setFilters({ q: "", year: "", degree: "", completion: "" });
  }

  function toggleField(id) {
    setForm((current) => {
      const has = current.fields.includes(id);
      return {
        ...current,
        fields: has ? current.fields.filter((item) => item !== id) : [...current.fields, id],
        other_detail: id === "other" && has ? "" : current.other_detail,
      };
    });
  }

  function toggleAlumni(row) {
    setSelected((current) => {
      const next = { ...current };
      if (next[row.id]) delete next[row.id];
      else next[row.id] = row;
      return next;
    });
  }

  function selectVisible() {
    setSelected((current) => {
      const next = { ...current };
      for (const row of alumni?.items || []) next[row.id] = row;
      return next;
    });
  }

  function stepError() {
    if (step === 0 && !selectedAlumni.length) return "Select at least one Active alumnus.";
    if (step === 1 && !form.fields.length) return "Select the information that needs updating.";
    if (step === 1 && form.fields.includes("other") && form.other_detail.trim().length < 3) {
      return "Describe the other profile information that needs updating.";
    }
    if (step === 2 && form.subject.trim().length < 3) return "Enter a subject.";
    if (step === 2 && form.message.trim().length < 10) return "Write a short instruction for alumni.";
    return "";
  }

  async function sendRequest(forceResend = false) {
    setSending(true);
    setError("");
    try {
      const result = await api("/api/admin/profile-update-requests", {
        method: "POST",
        body: {
          alumni_ids: selectedAlumni.map((row) => row.id),
          requested_fields: form.fields,
          other_detail: form.other_detail,
          subject: form.subject,
          message: form.message,
          force_resend: forceResend,
        },
      });
      setConfirmSend(false);
      setDuplicates(null);
      setComposing(false);
      const failed = result.email_failed_count || 0;
      showToast(
        failed ? "warning" : "success",
        failed
          ? `Notification created. ${result.message_summary}`
          : `Notification created successfully. ${result.message_summary}`,
      );
      await loadList(1);
    } catch (err) {
      const payload = err.payload?.detail;
      if (err.status === 409 && payload?.duplicates) {
        setDuplicates(payload);
        setConfirmSend(false);
      } else {
        setError(err.message);
      }
    } finally {
      setSending(false);
    }
  }

  async function openDetail(id) {
    try {
      setDetail(await api(`/api/admin/profile-update-requests/${id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  if (!list && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const rows = alumni?.items || [];
  const allVisibleSelected = rows.length > 0 && rows.every((row) => selected[row.id]);

  return (
    <PortalShell role="Admin">
      <PageHeader
        actions={
          composing ? null : (
            <button className="btn btn-navy" type="button" onClick={startComposer}>
              <PlusIcon size={16} />
              New Update Request
            </button>
          )
        }
      />
      <Alert type="error">{error && !confirmSend ? error : null}</Alert>
      {error && !list ? <LoadError onRetry={() => loadList(1)}>{error}</LoadError> : null}

      {!composing ? <ProfileRemindersPanel /> : null}

      {composing ? (
        <section className="card pur-composer" aria-label="New profile update request">
          <ol className="pur-steps" aria-label="Request steps">
            {STEPS.map(([id, label], index) => (
              <li key={id} className={`${index === step ? "on" : ""} ${index < step ? "done" : ""}`}>
                <span className="gts-dot" />
                <span>Step {index + 1}<br />{label}</span>
              </li>
            ))}
          </ol>

          {step === 0 ? (
            <>
              <form
                className="filter-bar"
                onSubmit={(event) => {
                  event.preventDefault();
                  loadAlumni(1, filters);
                }}
              >
                <Field label="Search">
                  <input
                    value={filters.q}
                    onChange={(e) => setFilters({ ...filters, q: e.target.value })}
                    placeholder="Name, email, or student ID"
                  />
                </Field>
                <Field label="Class year">
                  <input value={filters.year} onChange={(e) => setFilters({ ...filters, year: e.target.value })} placeholder="2022" />
                </Field>
                <Field label="Program">
                  <input value={filters.degree} onChange={(e) => setFilters({ ...filters, degree: e.target.value })} placeholder="Degree or program" />
                </Field>
                <Field label="Profile completion">
                  <select value={filters.completion} onChange={(e) => setFilters({ ...filters, completion: e.target.value })}>
                    <option value="">All Active alumni</option>
                    <option value="incomplete">Incomplete profile</option>
                    <option value="90-100">90–100%</option>
                    <option value="70-89">70–89%</option>
                    <option value="below-70">Below 70%</option>
                  </select>
                </Field>
                <button className="btn btn-navy" type="submit" disabled={alumniBusy}>Search</button>
              </form>
              <div className="pur-toolbar">
                <p className="muted">{selectedAlumni.length} selected · Active alumni only</p>
                <div className="panel-actions">
                  <button type="button" className="btn btn-outline btn-sm" onClick={selectVisible} disabled={!rows.length}>
                    {allVisibleSelected ? "Visible selected" : "Select all visible"}
                  </button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setSelected({})} disabled={!selectedAlumni.length}>
                    Clear selection
                  </button>
                </div>
              </div>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>
                        <span className="sr-only">Select</span>
                      </th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Student ID</th>
                      <th>Program</th>
                      <th>Completion</th>
                      <th>Last updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <label className="check">
                            <input type="checkbox" checked={Boolean(selected[row.id])} onChange={() => toggleAlumni(row)} />
                            <span className="sr-only">Select {row.name}</span>
                          </label>
                        </td>
                        <td>{row.name}</td>
                        <td>{row.email}</td>
                        <td>{row.student_id || "—"}</td>
                        <td>{row.degree || "—"}</td>
                        <td>{row.completion_percent}%</td>
                        <td>{row.last_updated ? formatDate(row.last_updated) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!rows.length ? <Empty title="No Active alumni match these filters">Adjust the search or completion filter.</Empty> : null}
              <Pager page={alumniPage} pageSize={alumni?.page_size || 10} total={alumni?.total || 0} onPage={(page) => loadAlumni(page)} />
            </>
          ) : null}

          {step === 1 ? (
            <fieldset className="pur-fields">
              <legend>Information requiring attention</legend>
              <div className="pur-field-grid">
                {fieldOptions.map((item) => (
                  <label key={item.id} className={`pur-field check ${form.fields.includes(item.id) ? "on" : ""}`}>
                    <input type="checkbox" checked={form.fields.includes(item.id)} onChange={() => toggleField(item.id)} />
                    <span>{item.label}</span>
                  </label>
                ))}
              </div>
              {form.fields.includes("other") ? (
                <Field label="Other profile information" hint="This note is included in the alumni notification.">
                  <input
                    value={form.other_detail}
                    onChange={(e) => setForm({ ...form, other_detail: e.target.value })}
                    maxLength={400}
                    placeholder="Please update your current employer and position."
                  />
                </Field>
              ) : null}
            </fieldset>
          ) : null}

          {step === 2 ? (
            <div className="form-section">
              <Field label="Subject">
                <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} maxLength={200} />
              </Field>
              <Field label="Message" hint={`${form.message.length} / 2000`}>
                <textarea rows={10} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} maxLength={2000} />
              </Field>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="pur-preview-grid">
              <section className="pur-preview">
                <p className="eyebrow">In-system notification</p>
                <strong>{form.subject}</strong>
                <p>Your CareerSense profile needs to be updated.</p>
                <p><strong>Please update:</strong></p>
                <ul>
                  {selectedFields.map((item) => (
                    <li key={item.id}>{item.id === "other" && form.other_detail.trim() ? `Other: ${form.other_detail.trim()}` : item.label}</li>
                  ))}
                </ul>
                <p className="muted" style={{ whiteSpace: "pre-wrap" }}>{form.message}</p>
                <span className="pur-cta">Update My Profile</span>
              </section>
              <section className="pur-preview is-email">
                <p className="eyebrow">Email preview</p>
                <p className="muted">Sent to each alumnus’s registered CareerSense email. Recipients cannot be changed here.</p>
                <strong>CareerSense – Profile Update Required</strong>
                <p>Dear [Alumni Name],</p>
                <p>The Angeles University Foundation Office of Alumni Affairs and Placement Services is requesting that you review and update information in your CareerSense alumni profile.</p>
                <p><strong>Information requiring attention:</strong></p>
                <ul>
                  {selectedFields.map((item) => (
                    <li key={item.id}>{item.id === "other" && form.other_detail.trim() ? `Other: ${form.other_detail.trim()}` : item.label}</li>
                  ))}
                </ul>
                <p><strong>Message from AAPS:</strong></p>
                <p style={{ whiteSpace: "pre-wrap" }}>{form.message}</p>
                <span className="pur-cta">Update My Profile</span>
              </section>
            </div>
          ) : null}

          <div className="dialog-actions pur-actions">
            <button type="button" className="btn btn-outline" onClick={() => (step === 0 ? setComposing(false) : setStep(step - 1))}>
              {step === 0 ? "Cancel" : "Back"}
            </button>
            {step < 3 ? (
              <button
                type="button"
                className="btn btn-navy"
                onClick={() => {
                  const problem = stepError();
                  if (problem) {
                    setError(problem);
                    return;
                  }
                  setError("");
                  setStep(step + 1);
                }}
              >
                Continue
              </button>
            ) : (
              <button type="button" className="btn btn-navy" onClick={() => { setError(""); setConfirmSend(true); }}>
                <MailIcon size={16} />
                Send Notification
              </button>
            )}
          </div>
        </section>
      ) : null}

      <Panel title="Previous requests" description="Delivery status is shown separately from whether the alumnus has updated the requested information.">
        {!list?.items?.length ? (
          <Empty title="No profile update requests yet">Create a request to notify Active alumni by CareerSense notification and email.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Date sent</th>
                  <th>Recipients</th>
                  <th>Requested updates</th>
                  <th>Sent by</th>
                  <th>Email status</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDateTime(row.created_at)}</td>
                    <td>{row.recipient_count}</td>
                    <td>{(row.requested_labels || []).join(", ")}</td>
                    <td>{row.sent_by || row.sent_by_email}</td>
                    <td><Badge tone={statusTone(row.email_status)}>{row.email_status}</Badge></td>
                    <td><Badge tone={statusTone(row.status)}>{row.status}</Badge></td>
                    <td>
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => openDetail(row.id)}>View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager page={listPage} pageSize={list?.page_size || 10} total={list?.total || 0} onPage={loadList} />
      </Panel>

      {confirmSend ? (
        <Dialog
          title="Send profile update request?"
          description={`You are about to notify ${selectedAlumni.length} active alumni by in-system notification and email.`}
          confirmLabel={sending ? "Sending…" : "Send Notification"}
          busy={sending}
          onConfirm={() => sendRequest(false)}
          onClose={() => { if (!sending) setConfirmSend(false); }}
        >
          <Alert type="error">{error}</Alert>
          <p><strong>Please update:</strong> {(selectedFields.map((item) => item.label)).join(", ")}</p>
        </Dialog>
      ) : null}

      {duplicates ? (
        <Dialog
          title="Send this request again?"
          description={duplicates.message}
          confirmLabel={sending ? "Sending…" : "Send anyway"}
          busy={sending}
          onConfirm={() => sendRequest(true)}
          onClose={() => { if (!sending) setDuplicates(null); }}
        >
          <ul className="pur-dup-list">
            {(duplicates.duplicates || []).map((row) => (
              <li key={row.alumni_id}>{row.name} · {row.email}</li>
            ))}
          </ul>
        </Dialog>
      ) : null}

      {detail ? (
        <Dialog
          title={detail.subject}
          description={`Sent ${formatDateTime(detail.created_at)} · ${detail.status}`}
          confirmLabel="Close"
          onConfirm={() => setDetail(null)}
          onClose={() => setDetail(null)}
          wide
        >
          <p className="muted">{detail.message_summary || `${detail.email_sent_count} emails sent. ${detail.email_failed_count} failed.`}</p>
          <p><strong>Requested updates:</strong> {(detail.requested_labels || []).join(", ")}</p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Alumni</th>
                  <th>Registered email</th>
                  <th>Email</th>
                  <th>Viewed</th>
                  <th>Update</th>
                </tr>
              </thead>
              <tbody>
                {(detail.recipients || []).map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td>{row.email}</td>
                    <td>
                      <Badge tone={statusTone(row.email_status === "sent" ? "Sent" : row.email_status === "disabled" ? "Disabled" : "Failed")}>
                        {row.email_status === "sent" ? "Email sent" : row.email_status === "disabled" ? "Email disabled" : "Email failed"}
                      </Badge>
                    </td>
                    <td>{row.viewed_at ? formatDateTime(row.viewed_at) : "Not viewed"}</td>
                    <td>{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
