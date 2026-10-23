import { useEffect, useMemo, useState } from "react";
import { AlertTriangleIcon, CheckCircleIcon, ClockIcon, EyeIcon, GiftIcon, PencilIcon, PlusIcon, SearchIcon, TrashIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { RowActions } from "../../components/RowActions";
import { DateField } from "../../components/DateField";
import { FileDrop } from "../../components/FileDrop";
import { Alert, Badge, Dialog, Empty, Field, LoadError, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { safeHttpUrl } from "../../lib/safeUrl";
import { formatDate } from "../../lib/format";
import { filterAdminPerks, perkIsExpired } from "../../lib/perkFilters";
import { PHOTO_ACCEPT, imageFileError } from "../../lib/profilePhoto";

const EMPTY = {
  name: "",
  partner: "",
  category: "",
  description: "",
  discount: "",
  how_to_claim: "",
  eligibility: "",
  contact: "",
  website: "",
  valid_from: "",
  valid_to: "",
  requires_active_card: false,
  active: true,
};

function currentStatus(row) {
  if (perkIsExpired(row)) return { label: "Expired", tone: "expired" };
  if (row?.status === "Active") return { label: "Active", tone: "active" };
  return { label: row?.status || "Inactive", tone: "unknown" };
}

function websiteProblem(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const withScheme = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
    const url = new URL(withScheme);
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname || url.username || url.password) {
      return "Website must be an http or https URL.";
    }
  } catch {
    return "Website must be an http or https URL.";
  }
  return "";
}

function CellText({ value, lines = 2 }) {
  const text = String(value || "").trim();
  if (!text) return "—";
  return (
    <span className={`perk-cell-text perk-lines-${lines}`} title={text}>
      {text}
    </span>
  );
}

function openEnded(row) {
  return Boolean(row?.valid_until_further_notice) || !row?.valid_to;
}

function validityLabel(row) {
  if (openEnded(row)) {
    return row.valid_from ? `From ${formatDate(row.valid_from)} · Until Further Notice` : "Until Further Notice";
  }
  if (row.valid_from && row.valid_to) return `${formatDate(row.valid_from)} – ${formatDate(row.valid_to)}`;
  return `Until ${formatDate(row.valid_to)}`;
}

function DetailRow({ label, children }) {
  if (children == null || children === "") return null;
  return (
    <div className="deflist-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function PerkActions({ row, onView, onEdit, onToggle, onDelete }) {
  return (
    <RowActions
      collapseQuery="(max-width: 1279px)"
      primary={[
        { id: "view", label: "View", icon: EyeIcon, onClick: () => onView(row) },
        { id: "edit", label: "Edit", icon: PencilIcon, onClick: () => onEdit(row) },
      ]}
      more={[
        {
          id: "toggle",
          label: row.active ? "Deactivate" : "Activate",
          onClick: () => onToggle(row),
        },
        {
          id: "delete",
          label: "Delete",
          icon: TrashIcon,
          danger: true,
          onClick: () => onDelete(row),
        },
      ]}
    />
  );
}

export default function AdminPerks() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [expiry, setExpiry] = useState("");
  const [editor, setEditor] = useState(null);
  const [viewItem, setViewItem] = useState(null);
  const [removeTarget, setRemoveTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [validityMode, setValidityMode] = useState("until_further_notice");
  const [validTo, setValidTo] = useState("");
  const [perkErrors, setPerkErrors] = useState({});
  const [logoPreview, setLogoPreview] = useState("");

  async function load() {
    setError("");
    try {
      setData(await api("/api/admin/perks"));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!editor) return;
    const until = editor.id ? openEnded(editor) : true;
    setValidityMode(until ? "until_further_notice" : "end_date");
    setValidTo(until ? "" : editor.valid_to || "");
    setPerkErrors({});
    setLogoPreview((current) => {
      if (current) URL.revokeObjectURL(current);
      return "";
    });
  }, [editor]);
  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  const items = useMemo(
    () => filterAdminPerks(data?.items, { query, category, status, expiry }),
    [data, query, category, status, expiry]
  );
  const stats = useMemo(() => {
    const rows = data?.items || [];
    return {
      total: rows.length,
      active: rows.filter((row) => row.status === "Active" && !perkIsExpired(row)).length,
      expired: rows.filter((row) => perkIsExpired(row)).length,
      expiring: rows.filter((row) => row.expiring_soon && !perkIsExpired(row)).length,
    };
  }, [data]);

  async function savePerk(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    const payload = {
      name: form.get("name"),
      partner: form.get("partner"),
      category: form.get("category"),
      description: form.get("description"),
      discount: form.get("discount"),
      how_to_claim: form.get("how_to_claim"),
      eligibility: form.get("eligibility"),
      contact: form.get("contact"),
      website: form.get("website"),
      valid_from: form.get("valid_from") || null,
      valid_to: validityMode === "until_further_notice" ? null : (validTo || null),
      valid_until_further_notice: validityMode === "until_further_notice",
      requires_active_card: form.get("requires_active_card") === "on",
      active: form.get("status") === "Active",
    };
    const problems = {};
    const name = String(payload.name || "").trim();
    const offer = String(payload.discount || "").trim();
    if (name.length < 2) problems.name = "Enter a perk name of at least 2 characters.";
    else if (name.length > 160) problems.name = "Perk name must be 160 characters or fewer.";
    if (!offer) problems.discount = "Enter the discount or offer.";
    else if (offer.length > 80) problems.discount = "Offer must be 80 characters or fewer.";
    if (validityMode === "end_date" && !payload.valid_to) {
      problems.valid_to = "Enter a validity end date or choose Until Further Notice.";
    }
    if (payload.valid_from && payload.valid_to && payload.valid_to < payload.valid_from) {
      problems.valid_to = "The end date must be on or after the start date.";
    }
    const website = websiteProblem(payload.website);
    if (website) problems.website = website;
    setPerkErrors(problems);
    if (Object.keys(problems).length) return;
    setBusy(true);
    setError("");
    try {
      const result = editor.id
        ? await api(`/api/admin/perks/${editor.id}`, { method: "PUT", body: payload })
        : await api("/api/admin/perks", { method: "POST", body: payload });
      const file = form.get("image");
      if (file && file.size) {
        const imageForm = new FormData();
        imageForm.append("image", file);
        await api(`/api/admin/perks/${result.item.id}/image`, { method: "POST", form: imageForm });
      }
      setOk(result.message || (editor.id ? "Perk updated successfully" : "Perk added successfully"));
      setEditor(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(row) {
    try {
      const result = await api(`/api/admin/perks/${row.id}/toggle`, { method: "POST" });
      setOk(result.message);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove() {
    if (!removeTarget) return;
    try {
      await api(`/api/admin/perks/${removeTarget.id}`, { method: "DELETE" });
      setOk("Perk deleted");
      setRemoveTarget(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <div className="admin-perks setup-page">
        <section className="card panel perks-intro" aria-label="Perks">
          <header className="panel-head">
            <div>
              <h2>Perks</h2>
              <p className="lead">Manage the alumni benefit catalog.</p>
            </div>
            <div className="panel-actions">
              <button className="btn btn-navy" type="button" onClick={() => setEditor({ ...EMPTY })}>
                <PlusIcon size={16} />
                Add Perk
              </button>
            </div>
          </header>
          <div className="perk-stats" role="group" aria-label="Perk catalog summary">
            <button type="button" className={`perk-stat${!status && !expiry ? " is-current" : ""}`} aria-pressed={!status && !expiry} onClick={() => { setStatus(""); setExpiry(""); }}>
              <span className="perk-stat-icon" aria-hidden="true"><GiftIcon size={18} /></span>
              <span className="perk-stat-copy">
                <span>Total Perks</span>
                <small>In the catalog</small>
              </span>
              <strong>{stats.total}</strong>
            </button>
            <button type="button" className={`perk-stat${status === "active" && !expiry ? " is-current" : ""}`} aria-pressed={status === "active" && !expiry} onClick={() => { setExpiry(""); setStatus((current) => current === "active" && !expiry ? "" : "active"); }}>
              <span className="perk-stat-icon" aria-hidden="true"><CheckCircleIcon size={18} /></span>
              <span className="perk-stat-copy">
                <span>Active</span>
                <small>Available now</small>
              </span>
              <strong>{stats.active}</strong>
            </button>
            <button type="button" className={`perk-stat${expiry === "expired" && !status ? " is-current" : ""}`} aria-pressed={expiry === "expired" && !status} onClick={() => { if (expiry === "expired" && !status) setExpiry(""); else { setStatus(""); setExpiry("expired"); } }}>
              <span className="perk-stat-icon" aria-hidden="true"><AlertTriangleIcon size={18} /></span>
              <span className="perk-stat-copy">
                <span>Expired</span>
                <small>Ended</small>
              </span>
              <strong>{stats.expired}</strong>
            </button>
            <button type="button" className={`perk-stat is-soon${expiry === "expiring" && !status ? " is-current" : ""}`} aria-pressed={expiry === "expiring" && !status} onClick={() => { if (expiry === "expiring" && !status) setExpiry(""); else { setStatus(""); setExpiry("expiring"); } }}>
              <span className="perk-stat-icon" aria-hidden="true"><ClockIcon size={18} /></span>
              <span className="perk-stat-copy">
                <span>Expiring Soon</span>
                <small>Within 30 days</small>
              </span>
              <strong>{stats.expiring}</strong>
            </button>
          </div>
        </section>
        <Alert type="error">{error && data ? error : null}</Alert>
        <Alert type="ok">{ok}</Alert>
        {error && !data ? <LoadError onRetry={load}>{error}</LoadError> : null}

        <section className="card panel admin-perk-panel">
        <div className="filter-bar admin-perk-filters">
          <Field label="Search">
            <div className="search-field">
              <SearchIcon size={16} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search name, partner, or offer"
                aria-label="Search by perk name, partner, or offer"
              />
            </div>
          </Field>
          <Field label="Category">
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {(data?.categories || []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field>
          <Field label="Status">
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </Field>
          <Field label="Expiration">
            <select value={expiry} onChange={(e) => setExpiry(e.target.value)}>
              <option value="">Any date</option>
              <option value="expiring">Expiring soon</option>
              <option value="expired">Expired</option>
            </select>
          </Field>
        </div>
          {!data?.items?.length ? (
            <Empty
              title="No perks yet"
              icon={<GiftIcon size={22} />}
              action={<button className="btn btn-navy" type="button" onClick={() => setEditor({ ...EMPTY })}>Add Perk</button>}
            >
              Add a perk to publish it in the alumni benefit list.
            </Empty>
          ) : !items.length ? (
            <Empty
              title="No perks match these filters"
              icon={<GiftIcon size={22} />}
              action={<button className="btn btn-outline" type="button" onClick={() => { setQuery(""); setCategory(""); setStatus(""); setExpiry(""); }}>Clear filters</button>}
            >
              Adjust the search, category, status, or expiration, or clear the filters.
            </Empty>
          ) : (
            <div className="table-wrap admin-perk-table">
              <table className="data stack">
                <colgroup>
                  <col className="perk-col-partner" />
                  <col className="perk-col-offer" />
                  <col className="perk-col-category" />
                  <col className="perk-col-date" />
                  <col className="perk-col-status" />
                  <col className="perk-col-actions" />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">Partner</th>
                    <th scope="col">Offer</th>
                    <th scope="col">Category</th>
                    <th scope="col">Valid Until</th>
                    <th scope="col" className="cell-status">Status</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => {
                    const statusView = currentStatus(row);
                    return (
                    <tr key={row.id} className={`admin-perk-row${row.expiring_soon ? " is-soon" : ""}`} onClick={() => setViewItem(row)}>
                      <td data-label="Partner">
                        <CellText value={row.partner || row.name} lines={3} />
                      </td>
                      <td data-label="Offer">
                        <CellText value={row.discount || row.name} lines={3} />
                      </td>
                      <td data-label="Category">
                        <CellText value={row.category} lines={2} />
                      </td>
                      <td data-label="Valid Until">
                        <CellText value={openEnded(row) ? "Until Further Notice" : formatDate(row.valid_to)} lines={2} />
                      </td>
                      <td className="cell-status" data-label="Status">
                        <div className="perk-status-stack">
                          <Badge tone={statusView.tone}>{statusView.label}</Badge>
                          {row.expiring_soon && !perkIsExpired(row) ? <Badge tone="pending">Expiring soon</Badge> : null}
                        </div>
                      </td>
                      <td className="cell-actions" data-label="Actions" onClick={(event) => event.stopPropagation()}>
                        <PerkActions
                          row={row}
                          onView={setViewItem}
                          onEdit={setEditor}
                          onToggle={toggle}
                          onDelete={setRemoveTarget}
                        />
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {editor ? (
        <Dialog title={editor.id ? "Edit perk" : "Add perk"} hideActions wide onClose={() => setEditor(null)}>
          <form onSubmit={savePerk} className="settings-form admin-perks-form">
            <fieldset className="setup-group">
              <legend>Basic Information</legend>
              <div className="inline-fields">
                <Field label="Perk/Discount Name" required error={perkErrors.name}>
                  <input name="name" defaultValue={editor.name || ""} maxLength={160} required />
                </Field>
                <Field label="Discount/Offer" required error={perkErrors.discount}>
                  <textarea name="discount" defaultValue={editor.discount || ""} required rows={2} maxLength={80} />
                </Field>
              </div>
              <div className="inline-fields">
                <Field label="Partner Name">
                  <input name="partner" defaultValue={editor.partner || ""} maxLength={160} />
                </Field>
                <Field label="Category" hint="Campus, Dining, Events, and Career are common. Other categories already in use can be kept.">
                  <input name="category" defaultValue={editor.category || ""} list="perk-category-suggestions" maxLength={80} />
                </Field>
              </div>
              <datalist id="perk-category-suggestions">
                {[...new Set(["Campus", "Dining", "Events", "Career", ...(data?.categories || [])])].map((item) => (
                  <option key={item} value={item} />
                ))}
              </datalist>
              <Field label="Description">
                <textarea name="description" defaultValue={editor.description || ""} rows={4} />
              </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Eligibility and Terms</legend>
              <Field label="Eligibility">
                <textarea name="eligibility" defaultValue={editor.eligibility || ""} rows={4} />
              </Field>
              <Field label="Terms and Conditions">
                <textarea name="how_to_claim" defaultValue={editor.how_to_claim || ""} rows={5} />
              </Field>
              <label className="check">
                <input type="checkbox" name="requires_active_card" defaultChecked={Boolean(editor.requires_active_card)} />
                Requires an Angelenean Alumni Card
              </label>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Validity and Status</legend>
              <div className="inline-fields">
                <label className="check">
                  <input type="radio" name="validity_mode" checked={validityMode === "end_date"} onChange={() => setValidityMode("end_date")} />
                  Specific end date
                </label>
                <label className="check">
                  <input type="radio" name="validity_mode" checked={validityMode === "until_further_notice"} onChange={() => setValidityMode("until_further_notice")} />
                  Until Further Notice
                </label>
              </div>
              <div className="inline-fields">
                <Field label="Valid From"><DateField name="valid_from" defaultValue={editor.valid_from || ""} /></Field>
                {validityMode === "end_date" ? (
                  <Field label="Valid Until" required error={perkErrors.valid_to}>
                    <DateField name="valid_to" value={validTo} onChange={(event) => setValidTo(event.target.value)} />
                  </Field>
                ) : null}
              </div>
              <Field label="Status">
                <select name="status" defaultValue={editor.active === false ? "Inactive" : "Active"}>
                  <option>Active</option>
                  <option>Inactive</option>
                </select>
              </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Contact and Branding</legend>
              <div className="inline-fields">
                <Field label="Contact Information"><input name="contact" defaultValue={editor.contact || ""} maxLength={255} /></Field>
                <Field label="Website" error={perkErrors.website}><input name="website" defaultValue={editor.website || ""} placeholder="https://" maxLength={500} /></Field>
              </div>
              {(logoPreview || editor.image_url) ? (
                <img className="perk-logo-preview" src={logoPreview || editor.image_url} alt="Perk logo preview" />
              ) : null}
              <FileDrop
                key={editor.id || "new"}
                name="image"
                accept={PHOTO_ACCEPT}
                validate={imageFileError}
                disabled={busy}
                compact
                currentName={editor.has_image ? "Current image" : ""}
                label="Image or Logo"
                formats="JPG, PNG, or WebP"
                maxSize="Maximum 5 MB"
                description={editor.has_image ? "Optional. A new image replaces the current one." : "Optional. Add a logo if you have one."}
                onChange={(file) => {
                  setLogoPreview((current) => {
                    if (current) URL.revokeObjectURL(current);
                    return file ? URL.createObjectURL(file) : "";
                  });
                }}
              />
            </fieldset>
            <div className="dialog-actions">
              <button type="button" className="btn btn-outline" onClick={() => setEditor(null)}>Cancel</button>
              <button className="btn btn-navy" disabled={busy}>{busy ? "Saving..." : editor.id ? "Save perk" : "Add perk"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}

      {viewItem ? (
        <Dialog title="Perk details" confirmLabel="Close" wide onConfirm={() => setViewItem(null)} onClose={() => setViewItem(null)}>
          <div className="perk-detail">
            <dl className="deflist">
              <DetailRow label="Partner">{viewItem.partner || "—"}</DetailRow>
              <DetailRow label="Perk title">{viewItem.name || "—"}</DetailRow>
              <DetailRow label="Offer">{viewItem.discount || "—"}</DetailRow>
              <DetailRow label="Category">{viewItem.category || "—"}</DetailRow>
              <DetailRow label="Description">{viewItem.description || "—"}</DetailRow>
              <DetailRow label="Eligibility">{viewItem.eligibility || "—"}</DetailRow>
              <DetailRow label="Terms and conditions">{viewItem.how_to_claim || "—"}</DetailRow>
              <DetailRow label="Validity">{validityLabel(viewItem) || "No dates set"}</DetailRow>
              <DetailRow label="Contact">{viewItem.contact || "—"}</DetailRow>
              <DetailRow label="Website">
                {safeHttpUrl(viewItem.website) ? (
                  <a href={safeHttpUrl(viewItem.website)} target="_blank" rel="noopener noreferrer">{viewItem.website}</a>
                ) : "—"}
              </DetailRow>
              <DetailRow label="Alumni card">{viewItem.requires_active_card ? "Required" : "Not required"}</DetailRow>
              <DetailRow label="Status">
                <div className="perk-status-stack">
                  <Badge tone={currentStatus(viewItem).tone}>{currentStatus(viewItem).label}</Badge>
                  {viewItem.expiring_soon && !perkIsExpired(viewItem) ? <Badge tone="pending">Expiring soon</Badge> : null}
                </div>
              </DetailRow>
            </dl>
          </div>
        </Dialog>
      ) : null}

      {removeTarget ? (
        <Dialog
          title="Delete this perk?"
          description={`Delete “${removeTarget.name || removeTarget.partner || "this perk"}”?`}
          confirmLabel="Delete perk"
          danger
          onConfirm={remove}
          onClose={() => setRemoveTarget(null)}
        >
          <p>Deleting this perk removes it from the alumni-facing list and clears its claim records. This cannot be undone.</p>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
