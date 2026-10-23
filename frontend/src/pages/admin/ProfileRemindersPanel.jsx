import { useEffect, useMemo, useState } from "react";
import { MailIcon } from "../../components/icons";
import { Panel } from "../../components/RecordViews";
import { Alert, Badge, Dialog, Empty, Field, Pager } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { showToast } from "../../lib/toasts";

function hourLabel(hour) {
  const value = Number(hour);
  const suffix = value >= 12 ? "PM" : "AM";
  const display = ((value + 11) % 12) + 1;
  return `${String(display)}:00 ${suffix}`;
}

function formFromSettings(data) {
  return {
    enabled: Boolean(data?.enabled),
    frequency: data?.frequency || "weekly",
    interval_days: data?.interval_days ?? 14,
    send_hour: data?.send_hour ?? 9,
    send_weekday: data?.send_weekday ?? 0,
    send_day_of_month: data?.send_day_of_month ?? 1,
    target_mode: data?.target_mode || "incomplete",
    target_year: data?.target_filters?.year || "",
    target_degree: data?.target_filters?.degree || "",
    target_completion: data?.target_filters?.completion || "",
    alumni_ids: data?.alumni_ids || [],
    requested_fields: data?.requested_fields || [],
    other_detail: data?.other_detail || "",
    subject: data?.subject || "",
    message: data?.message || "",
    min_days_between: data?.min_days_between ?? 14,
    skip_if_complete: data?.skip_if_complete !== false,
  };
}

const RECIPIENT_LABELS = {
  all_active: "All Active alumni",
  incomplete: "Active alumni with incomplete profiles",
  filtered: "Alumni filtered by class year, program, and profile completion",
  selected: "A hand-picked list of Active alumni",
};

const FIELD_COPY = {
  contact: "Name and contact details on the profile.",
  phone: "Phone number.",
  city: "City of residence.",
  country: "Country of residence.",
  profile_photo: "Profile photo.",
  education: "Degree and education details.",
  further_studies: "Studies completed after graduation.",
  employment: "Current employment information.",
  current_occupation: "Current job title.",
  graduate_tracer: "Graduate Tracer Survey.",
  work_history: "Previous positions.",
  alumni_card: "Details used for the Alumni Card.",
  other: "A custom note included with the request.",
};

const FIELD_GROUPS = [
  { title: "Contact information", text: "How the alumnus can be reached.", ids: ["contact", "phone", "city", "country"] },
  { title: "Profile photo and education", text: "Photo, education, and further studies.", ids: ["profile_photo", "education", "further_studies"] },
  { title: "Employment and Graduate Tracer Survey", text: "Current work and the tracer survey.", ids: ["employment", "current_occupation", "graduate_tracer"] },
  { title: "Work history", text: "Positions already recorded on the profile.", ids: ["work_history"] },
  { title: "Alumni Card information", text: "Information shown for the Alumni Card.", ids: ["alumni_card"] },
  { title: "Other profile information", text: "Anything else that needs a written note.", ids: ["other"] },
];

export function ProfileFieldOptions({ fields, selected, onToggle, otherValue, onOtherChange, otherInputId }) {
  const byId = Object.fromEntries((fields || []).map((item) => [item.id, item]));
  const used = new Set();
  const groups = FIELD_GROUPS.map((group) => {
    const items = group.ids.map((id) => byId[id]).filter(Boolean);
    items.forEach((item) => used.add(item.id));
    return { ...group, items };
  }).filter((group) => group.items.length);
  const extra = (fields || []).filter((item) => !used.has(item.id));
  if (extra.length) {
    groups.push({ title: "Additional profile areas", text: "", items: extra });
  }
  return (
    <div className="pur-field-groups">
      {groups.map((group) => (
        <fieldset key={group.title} className="pur-field-group">
          <legend>{group.title}</legend>
          {group.text ? <p>{group.text}</p> : null}
          <div className="pur-field-grid">
            {group.items.map((item) => (
              <label key={item.id} className={`pur-field check ${selected.includes(item.id) ? "on" : ""}`}>
                <input type="checkbox" checked={selected.includes(item.id)} onChange={() => onToggle(item.id)} />
                <span>
                  <strong>{item.label}</strong>
                  {FIELD_COPY[item.id] ? <small>{FIELD_COPY[item.id]}</small> : null}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      {selected.includes("other") ? (
        <Field
          label="Other profile information"
          hint={`${String(otherValue || "").length} / 400. Use at least 3 characters. This note is included in the notification.`}
        >
          <input
            id={otherInputId}
            value={otherValue}
            onChange={(event) => onOtherChange(event.target.value)}
            maxLength={400}
            placeholder="Please update your current employer and position."
          />
        </Field>
      ) : null}
    </div>
  );
}

function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "completed" || value === "sent") return "aligned";
  if (value === "partial" || value === "disabled" || value === "skipped") return "unknown";
  if (value.includes("fail")) return "misaligned";
  return "";
}

export default function ProfileRemindersPanel({ actions = null }) {
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState(formFromSettings());
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const [runs, setRuns] = useState(null);
  const [runPage, setRunPage] = useState(1);
  const [confirmRun, setConfirmRun] = useState(false);
  const [sending, setSending] = useState(false);
  const [selected, setSelected] = useState({});
  const [alumni, setAlumni] = useState(null);
  const [alumniPage, setAlumniPage] = useState(1);
  const [filters, setFilters] = useState({ q: "", year: "", degree: "", completion: "" });
  const [alumniBusy, setAlumniBusy] = useState(false);

  const fieldOptions = settings?.fields || [];
  const hours = useMemo(() => Array.from({ length: 24 }, (_, hour) => hour), []);

  async function loadSettings() {
    const data = await api("/api/admin/profile-reminders");
    setSettings(data);
    setForm(formFromSettings(data));
    const picked = {};
    for (const id of data.alumni_ids || []) picked[id] = { id, name: `Alumni #${id}`, email: "" };
    setSelected(picked);
    return data;
  }

  async function loadRuns(page = 1) {
    const data = await api(`/api/admin/profile-reminders/runs?page=${page}&page_size=5`);
    setRuns(data);
    setRunPage(page);
  }

  async function loadAlumni(page = 1, nextFilters = filters) {
    setAlumniBusy(true);
    try {
      const params = new URLSearchParams({
        q: nextFilters.q,
        year: nextFilters.year,
        degree: nextFilters.degree,
        completion: nextFilters.completion,
        page: String(page),
        page_size: "10",
      });
      const data = await api(`/api/admin/profile-update-requests/alumni?${params}`);
      setAlumni(data);
      setAlumniPage(page);
      setSelected((current) => {
        const next = { ...current };
        for (const row of data.items || []) {
          if (next[row.id] && !next[row.id].email) next[row.id] = row;
        }
        return next;
      });
    } finally {
      setAlumniBusy(false);
    }
  }

  useEffect(() => {
    Promise.all([loadSettings(), loadRuns(1)]).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (form.target_mode === "selected") {
      loadAlumni(1, filters).catch((err) => setError(err.message));
    }
  }, [form.target_mode]);

  function toggleField(id) {
    setForm((current) => {
      const has = current.requested_fields.includes(id);
      return {
        ...current,
        requested_fields: has ? current.requested_fields.filter((item) => item !== id) : [...current.requested_fields, id],
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

  function payload() {
    return {
      ...form,
      interval_days: Number(form.interval_days),
      send_hour: Number(form.send_hour),
      send_weekday: Number(form.send_weekday),
      send_day_of_month: Number(form.send_day_of_month),
      min_days_between: Number(form.min_days_between),
      alumni_ids: Object.keys(selected).map(Number),
    };
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const data = await api("/api/admin/profile-reminders", { method: "PUT", body: payload() });
      setSettings(data);
      setForm(formFromSettings(data));
      showToast("success", "Automated reminder settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function loadPreview() {
    setError("");
    try {
      await api("/api/admin/profile-reminders", { method: "PUT", body: payload() });
      const data = await api("/api/admin/profile-reminders/preview");
      setPreview(data);
      setSettings(data);
      setForm(formFromSettings(data));
    } catch (err) {
      setError(err.message);
    }
  }

  async function runNow(force = false) {
    setSending(true);
    setError("");
    try {
      await api("/api/admin/profile-reminders", { method: "PUT", body: payload() });
      const result = await api("/api/admin/profile-reminders/run", { method: "POST", body: { force } });
      setConfirmRun(false);
      const run = result.run || {};
      showToast(
        run.failed_count ? "warning" : "success",
        `Reminder run finished. ${run.sent_count || 0} sent, ${run.skipped_count || 0} skipped, ${run.failed_count || 0} failed.`,
      );
      await Promise.all([loadSettings(), loadRuns(1)]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  if (!settings) {
    if (!error) return null;
    return (
      <Panel id="automated-reminders" className="pur-reminder" title="Automated Profile Reminders" actions={actions}>
        <Alert type="error">{error}</Alert>
      </Panel>
    );
  }

  const selectedAlumni = Object.values(selected);
  const rows = alumni?.items || [];

  return (
    <Panel
      id="automated-reminders"
      className="pur-reminder"
      title="Automated Profile Reminders"
      description="This schedule applies to the entire portal. Messages use each alumnus’s registered email and never include passwords or PINs."
      actions={actions}
    >
      <Alert type="error">{error}</Alert>

      <section className="pur-group" aria-label="Reminder status">
        <div className="pur-status-row">
          <Badge tone={form.enabled ? "aligned" : "unknown"}>{form.enabled ? "Reminders on" : "Reminders off"}</Badge>
        </div>
        <label className={`pur-field check ${form.enabled ? "on" : ""}`}>
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
          />
          <span>
            <strong>Enable automated reminder emails</strong>
            <small>Turn the portal-wide schedule on or off. Saved settings stay in place either way.</small>
          </span>
        </label>
        {!settings.email_configured ? (
          <Alert type="warn">
            Email sending is not configured. You can still save these settings. Alumni will not receive mail until email sending is enabled.
          </Alert>
        ) : null}
      </section>

      <section className="pur-group">
        <h3>Who should receive reminders?</h3>
        <Field label="Recipients">
          <select value={form.target_mode} onChange={(event) => setForm({ ...form, target_mode: event.target.value })}>
            {(settings.target_modes || []).map((item) => (
              <option key={item.id} value={item.id}>{RECIPIENT_LABELS[item.id] || item.label}</option>
            ))}
          </select>
        </Field>

      {form.target_mode === "filtered" ? (
        <div className="pur-reminder-grid">
          <Field label="Class year">
            <input value={form.target_year} onChange={(event) => setForm({ ...form, target_year: event.target.value })} placeholder="2022" />
          </Field>
          <Field label="Program">
            <input value={form.target_degree} onChange={(event) => setForm({ ...form, target_degree: event.target.value })} placeholder="Degree or program" />
          </Field>
          <Field label="Profile completion">
            <select value={form.target_completion} onChange={(event) => setForm({ ...form, target_completion: event.target.value })}>
              <option value="">Any completion</option>
              <option value="incomplete">Incomplete profile</option>
              <option value="90-100">90–100%</option>
              <option value="70-89">70–89%</option>
              <option value="below-70">Below 70%</option>
            </select>
          </Field>
        </div>
      ) : null}

      {form.target_mode === "selected" ? (
        <div className="pur-reminder-select">
          <form
            className="filter-bar"
            onSubmit={(event) => {
              event.preventDefault();
              loadAlumni(1, filters).catch((err) => setError(err.message));
            }}
          >
            <Field label="Search">
              <input value={filters.q} onChange={(event) => setFilters({ ...filters, q: event.target.value })} placeholder="Name, email, or student ID" />
            </Field>
            <button className="btn btn-navy" type="submit" disabled={alumniBusy}>Search</button>
          </form>
          <p className="pur-selected-count"><strong>{selectedAlumni.length}</strong> {selectedAlumni.length === 1 ? "alumnus" : "alumni"} selected · Active alumni only. Selections stay in place when you change pages.</p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th><span className="sr-only">Select</span></th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Program</th>
                  <th>Completion</th>
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
                    <td>{row.degree || "—"}</td>
                    <td>{row.completion_percent}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={alumniPage} pageSize={alumni?.page_size || 10} total={alumni?.total || 0} onPage={(page) => loadAlumni(page)} />
        </div>
      ) : null}
        <p className="pur-limit">Each scheduled run processes at most {(settings.max_auto_recipients || 2000).toLocaleString()} alumni and skips accounts without a usable email address.</p>
      </section>

      <section className="pur-group">
        <h3>Requested Profile Updates</h3>
        <ProfileFieldOptions
          fields={fieldOptions}
          selected={form.requested_fields}
          onToggle={toggleField}
          otherValue={form.other_detail}
          onOtherChange={(value) => setForm({ ...form, other_detail: value })}
          otherInputId="reminder-other-detail"
        />
      </section>

      <section className="pur-group">
        <h3>Schedule and Sending Rules</h3>
        <div className="pur-reminder-grid">
          <Field label="Frequency">
            <select value={form.frequency} onChange={(event) => setForm({ ...form, frequency: event.target.value })}>
              {(settings.frequencies || []).map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Send time (Asia/Manila)">
            <select value={form.send_hour} onChange={(event) => setForm({ ...form, send_hour: Number(event.target.value) })}>
              {hours.map((hour) => (
                <option key={hour} value={hour}>{hourLabel(hour)}</option>
              ))}
            </select>
          </Field>
          {form.frequency === "weekly" ? (
            <Field label="Weekday">
              <select value={form.send_weekday} onChange={(event) => setForm({ ...form, send_weekday: Number(event.target.value) })}>
                {(settings.weekdays || []).map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            </Field>
          ) : null}
          {form.frequency === "monthly" ? (
            <Field label="Day of month">
              <select value={form.send_day_of_month} onChange={(event) => setForm({ ...form, send_day_of_month: Number(event.target.value) })}>
                {Array.from({ length: 28 }, (_, index) => index + 1).map((day) => (
                  <option key={day} value={day}>{day}</option>
                ))}
              </select>
            </Field>
          ) : null}
          {form.frequency === "interval" ? (
            <Field label="Every N days">
              <input
                type="number"
                min={1}
                max={365}
                value={form.interval_days}
                onChange={(event) => setForm({ ...form, interval_days: event.target.value })}
              />
            </Field>
          ) : null}
          <Field label="Minimum days between emails" hint="The same alumnus is not emailed again until this many days have passed. Default is 14 days.">
            <input
              type="number"
              min={1}
              max={365}
              value={form.min_days_between}
              onChange={(event) => setForm({ ...form, min_days_between: event.target.value })}
            />
          </Field>
        </div>
        <label className={`pur-field check ${form.skip_if_complete ? "on" : ""}`}>
          <input
            type="checkbox"
            checked={form.skip_if_complete}
            onChange={(event) => setForm({ ...form, skip_if_complete: event.target.checked })}
          />
          <span>
            <strong>Skip alumni who already completed the requested fields</strong>
            <small>Alumni who already filled in every requested field are left out of the next run.</small>
          </span>
        </label>
      </section>

      <section className="pur-group">
        <h3>Message</h3>
        <Field label="Email subject">
          <input value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} maxLength={200} />
        </Field>
        <Field label="Email message" hint={`${form.message.length} / 2,000`}>
          <textarea rows={8} value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} maxLength={2000} />
        </Field>
      </section>

      <p className="muted">
        Next scheduled run: {settings.next_run_at ? formatDateTime(settings.next_run_at) : "Not scheduled"}
        {settings.last_run_at ? ` · Last run ${formatDateTime(settings.last_run_at)}` : ""}
      </p>

      <div className="dialog-actions pur-actions">
        <button type="button" className="btn btn-outline" onClick={loadPreview}>Preview recipients</button>
        <button type="button" className="btn btn-outline" onClick={() => setConfirmRun(true)}>
          <MailIcon size={16} />
          Send now
        </button>
        <button type="button" className="btn btn-navy" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save reminder settings"}
        </button>
      </div>

      {preview ? (
        <div className="pur-preview is-email">
          <p className="eyebrow">Recipient preview</p>
          <p>
            {preview.send_estimate} alumni would be emailed now.
            {preview.skipped_estimate ? ` ${preview.skipped_estimate} would be skipped to avoid duplicates or completed fields.` : ""}
          </p>
          {!preview.items?.length ? (
            <Empty title="No matching Active alumni">Adjust the target or filters.</Empty>
          ) : (
            <ul className="pur-dup-list">
              {preview.items.map((row) => (
                <li key={row.id}>
                  {row.name} · {row.email}
                  {row.skip_reason ? ` · skipped (${row.skip_reason.replace("_", " ")})` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      <h3 className="pur-reminder-runs">Recent reminder runs</h3>
      {!runs?.items?.length ? (
        <Empty title="No automated reminder runs yet">Save a schedule or choose Send now to create the first run.</Empty>
      ) : (
        <div className="table-wrap">
          <table className="data stack">
            <thead>
              <tr>
                <th>Started</th>
                <th>Trigger</th>
                <th>Sent</th>
                <th>Skipped</th>
                <th>Failed</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.items.map((row) => (
                <tr key={row.id}>
                  <td data-label="Started">{formatDateTime(row.started_at)}</td>
                  <td data-label="Trigger">{row.triggered_by === "admin" ? "Admin" : "Schedule"}</td>
                  <td data-label="Sent">{row.sent_count}</td>
                  <td data-label="Skipped">{row.skipped_count}</td>
                  <td data-label="Failed">{row.failed_count}</td>
                  <td data-label="Status"><Badge tone={statusTone(row.status)}>{row.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={runPage} pageSize={runs?.page_size || 5} total={runs?.total || 0} onPage={loadRuns} />

      {confirmRun ? (
        <Dialog
          title="Send profile reminders now?"
          description="CareerSense will email matching Active alumni using the settings on this page. Alumni who already received this reminder recently are skipped unless you confirm a forced resend later."
          confirmLabel={sending ? "Sending…" : "Send reminders"}
          busy={sending}
          onConfirm={() => runNow(false)}
          onClose={() => { if (!sending) setConfirmRun(false); }}
        >
          <Alert type="error">{error}</Alert>
          <p>Subject: {form.subject}</p>
        </Dialog>
      ) : null}
    </Panel>
  );
}
