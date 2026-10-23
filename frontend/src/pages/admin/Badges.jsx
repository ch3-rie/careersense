import { useEffect, useMemo, useState } from "react";
import {
  BriefcaseIcon,
  CheckIcon,
  ClipboardListIcon,
  CreditCardIcon,
  FileTextIcon,
  PencilIcon,
  PlusIcon,
  SearchIcon,
  StarIcon,
  TrashIcon,
} from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { RowActions } from "../../components/RowActions";
import { Alert, Badge, Dialog, Empty, Field, LoadError } from "../../components/ui";
import { api } from "../../lib/api";

const EMPTY = {
  name: "",
  description: "",
  locked_description: "",
  icon: "check",
  category: "recognition",
  criteria_type: "profile_complete",
  active: true,
  requirementTouched: false,
};

function BadgeSeal({ icon, inactive = false }) {
  const size = 18;
  let glyph = <CheckIcon size={size} />;
  if (icon === "file") glyph = <FileTextIcon size={size} />;
  else if (icon === "clipboard") glyph = <ClipboardListIcon size={size} />;
  else if (icon === "briefcase") glyph = <BriefcaseIcon size={size} />;
  else if (icon === "id-card") glyph = <CreditCardIcon size={size} />;
  else if (icon === "star") glyph = <StarIcon size={size} />;
  return <span className={`achievement-seal badge-admin-seal${inactive ? " is-inactive" : " is-earned"}`} aria-hidden="true">{glyph}</span>;
}

function removalCopy(row) {
  if (row.is_system) {
    return `${row.name} is built into CareerSense, so it cannot be permanently deleted. It will be deactivated instead. Alumni who already earned it keep the badge, and it will not be awarded again.`;
  }
  if (row.earned_count > 0) {
    const people = row.earned_count === 1 ? "1 alumnus has" : `${row.earned_count} alumni have`;
    return `${people} already earned ${row.name}. It will be deactivated instead of deleted, so those achievements stay on their profiles. It will not be awarded again.`;
  }
  return `${row.name} has not been earned. Removing it permanently deletes the badge from the catalog.`;
}

export default function AdminBadges() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [editor, setEditor] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [removeTarget, setRemoveTarget] = useState(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    setError("");
    try {
      setData(await api("/api/admin/badges"));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  const items = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data?.items || []).filter((row) => {
      if (category && row.category !== category) return false;
      if (status === "active" && !row.active) return false;
      if (status === "inactive" && row.active) return false;
      if (!needle) return true;
      return `${row.name} ${row.description} ${row.criteria_label}`.toLowerCase().includes(needle);
    });
  }, [data, query, category, status]);

  function openCreate() {
    const first = data?.criteria?.[0];
    setFieldErrors({});
    setFormError("");
    setEditor({
      ...EMPTY,
      criteria_type: first?.value || "profile_complete",
      locked_description: first?.detail || "",
    });
  }

  function openEdit(row) {
    setFieldErrors({});
    setFormError("");
    setEditor({ ...row, requirementTouched: true });
  }

  function setCriteria(value) {
    const option = (data?.criteria || []).find((item) => item.value === value);
    setEditor((current) => ({
      ...current,
      criteria_type: value,
      locked_description: current.requirementTouched ? current.locked_description : (option?.detail || ""),
    }));
  }

  function validate(current) {
    const next = {};
    if (current.name.trim().length < 2) next.name = "Enter a badge name.";
    if (current.description.trim().length < 2) next.description = "Enter a short description.";
    if (current.locked_description.trim().length < 2) next.locked_description = "Describe how an alumnus earns this badge.";
    if (!current.criteria_type) next.criteria_type = "Choose an awarding rule.";
    return next;
  }

  async function save(event) {
    event.preventDefault();
    const problems = validate(editor);
    setFieldErrors(problems);
    if (Object.keys(problems).length) {
      setFormError("Complete the required fields before saving.");
      return;
    }
    setSaving(true);
    setFormError("");
    const payload = {
      name: editor.name.trim(),
      description: editor.description.trim(),
      locked_description: editor.locked_description.trim(),
      icon: editor.icon,
      category: editor.category,
      criteria_type: editor.criteria_type,
      active: Boolean(editor.active),
    };
    try {
      const result = await api(editor.id ? `/api/admin/badges/${editor.id}` : "/api/admin/badges", {
        method: editor.id ? "PUT" : "POST",
        body: payload,
      });
      setOk(result.message || "Badge saved.");
      setEditor(null);
      await load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggle(row) {
    try {
      const result = await api(`/api/admin/badges/${row.id}/toggle`, { method: "POST" });
      setOk(result.message);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove() {
    if (!removeTarget) return;
    try {
      const result = await api(`/api/admin/badges/${removeTarget.id}`, { method: "DELETE" });
      setOk(result.message);
      setRemoveTarget(null);
      await load();
    } catch (err) {
      setError(err.message);
      setRemoveTarget(null);
    }
  }

  return (
    <PortalShell role="Admin">
      <div className="admin-badges setup-page">
        <section className="card panel badges-intro" aria-label="Badge Management">
          <header className="panel-head">
            <div>
              <h2>Badge Management</h2>
              <p className="lead">Badges are awarded automatically from alumni records. Review each rule, who has earned it, and whether it can be removed.</p>
            </div>
            <div className="panel-actions">
              <button className="btn btn-navy" type="button" onClick={openCreate}>
                <PlusIcon size={16} />
                Add Badge
              </button>
            </div>
          </header>
          <div className="setup-stats" aria-label="Badge catalog summary">
            <button type="button" className={`setup-stat ${!status ? "is-current" : ""}`} onClick={() => setStatus("")}>
              <strong>{data?.total ?? 0}</strong>
              <span>Total Badges</span>
            </button>
            <button type="button" className={`setup-stat ${status === "active" ? "is-current" : ""}`} onClick={() => setStatus((current) => current === "active" ? "" : "active")}>
              <strong>{data?.active ?? 0}</strong>
              <span>Active Badges</span>
            </button>
            <button type="button" className={`setup-stat ${status === "inactive" ? "is-current" : ""}`} onClick={() => setStatus((current) => current === "inactive" ? "" : "inactive")}>
              <strong>{data?.inactive ?? 0}</strong>
              <span>Inactive Badges</span>
            </button>
          </div>
        </section>
        <Alert type="error">{error && data ? error : null}</Alert>
        <Alert type="ok">{ok}</Alert>
        {error && !data ? <LoadError onRetry={load}>{error}</LoadError> : null}

        <section className="card panel admin-badge-panel">
        <div className="filter-bar admin-badge-filters">
          <Field label="Search">
            <div className="search-field">
              <SearchIcon size={16} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by badge name"
                aria-label="Search badges by name"
              />
            </div>
          </Field>
          <Field label="Category">
            <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter badges by category">
              <option value="">All categories</option>
              {(data?.categories || []).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </Field>
          <Field label="Status">
            <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter badges by status">
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </Field>
        </div>
          {!data ? null : !data.items.length ? (
            <Empty
              title="No badges yet"
              action={<button className="btn btn-navy" type="button" onClick={openCreate}>Add Badge</button>}
            >
              Add a badge to make it available in Alumni Badge Achievements.
            </Empty>
          ) : !items.length ? (
            <Empty title="No badges match these filters">
              Adjust the name, category, or status.
            </Empty>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Badge</th>
                    <th>Category</th>
                    <th>Awarding rule</th>
                    <th>Status</th>
                    <th>Earned</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <div className="badge-admin-name">
                          <BadgeSeal icon={row.icon} inactive={!row.active} />
                          <span className="badge-admin-copy">
                            <strong>{row.name}</strong>
                            {row.is_system ? <Badge tone="unknown">Built-in</Badge> : null}
                            <span>{row.description}</span>
                          </span>
                        </div>
                      </td>
                      <td>{row.category_label}</td>
                      <td>
                        <span className="badge-admin-copy">
                          <strong>{row.criteria_label}</strong>
                          <span>{row.locked_description}</span>
                        </span>
                      </td>
                      <td><Badge tone={row.active ? "active" : "unknown"}>{row.status}</Badge></td>
                      <td>{row.earned_count}</td>
                      <td className="cell-actions">
                        <RowActions
                          collapseQuery="(max-width: 1279px)"
                          primary={[
                            { id: "edit", label: "Edit", icon: PencilIcon, onClick: () => openEdit(row) },
                          ]}
                          more={[
                            {
                              id: "toggle",
                              label: row.active ? "Deactivate" : "Activate",
                              onClick: () => toggle(row),
                            },
                            {
                              id: "remove",
                              label: "Remove",
                              icon: TrashIcon,
                              danger: true,
                              onClick: () => setRemoveTarget(row),
                            },
                          ]}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {editor ? (
        <Dialog title={editor.id ? "Edit badge" : "Add badge"} hideActions wide onClose={() => setEditor(null)}>
          <form className="admin-badge-form" onSubmit={save}>
            {formError ? <Alert type="error">{formError}</Alert> : null}
            <fieldset className="setup-group">
              <legend>Badge Information</legend>
              <Field label="Badge name" required error={fieldErrors.name}>
                <input value={editor.name} onChange={(event) => setEditor({ ...editor, name: event.target.value })} maxLength={120} />
              </Field>
              <Field label="Description" required error={fieldErrors.description} hint="Shown after an alumnus earns the badge.">
                <textarea value={editor.description} onChange={(event) => setEditor({ ...editor, description: event.target.value })} rows={3} />
              </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Appearance</legend>
              <Field label="Icon" required>
                <select value={editor.icon} onChange={(event) => setEditor({ ...editor, icon: event.target.value })}>
                  {(data?.icons || []).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </Field>
              <div className="badge-admin-name" aria-live="polite">
                <BadgeSeal icon={editor.icon} inactive={!editor.active} />
                <span className="badge-admin-copy">
                  <strong>{editor.name.trim() || "Badge preview"}</strong>
                  <span>{editor.description.trim() || "Description appears here."}</span>
                </span>
              </div>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Classification</legend>
              <Field label="Category">
                <select value={editor.category} onChange={(event) => setEditor({ ...editor, category: event.target.value })}>
                  {(data?.categories || []).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Awarding Rules</legend>
              <Field label="Awarding rule" required error={fieldErrors.criteria_type} hint={editor.criteria_locked ? "This built-in badge uses a fixed awarding rule." : "CareerSense checks this rule before awarding the badge."}>
                <select
                  value={editor.criteria_type}
                  disabled={Boolean(editor.criteria_locked)}
                  onChange={(event) => setCriteria(event.target.value)}
                >
                  {(data?.criteria || []).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </Field>
              <p className="setup-help">{(data?.criteria || []).find((item) => item.value === editor.criteria_type)?.detail || "CareerSense awards this badge automatically when the rule is met."}</p>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Requirements</legend>
              <Field label="Requirements" required error={fieldErrors.locked_description} hint="Shown to alumni who have not earned the badge yet.">
                <textarea
                  value={editor.locked_description}
                  onChange={(event) => setEditor({ ...editor, locked_description: event.target.value, requirementTouched: true })}
                  rows={3}
                />
              </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Availability</legend>
              <Field label="Status">
                <select value={editor.active ? "active" : "inactive"} onChange={(event) => setEditor({ ...editor, active: event.target.value === "active" })}>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </Field>
              <p className="badge-admin-note">Deactivated badges are no longer newly awarded. Alumni who already earned a badge keep it on their profile.</p>
            </fieldset>
            <div className="dialog-actions">
              <button className="btn btn-outline" type="button" onClick={() => setEditor(null)}>Cancel</button>
              <button className="btn btn-navy" type="submit" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}

      {removeTarget ? (
        <Dialog
          title={`Remove ${removeTarget.name}?`}
          confirmLabel={removeTarget.can_delete ? "Remove badge" : "Deactivate badge"}
          danger
          onConfirm={remove}
          onClose={() => setRemoveTarget(null)}
        >
          <p>{removalCopy(removeTarget)}</p>
          {removeTarget.can_delete ? null : (
            <p>Deactivated badges are no longer newly awarded, and previously earned badges stay on alumni profiles.</p>
          )}
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
