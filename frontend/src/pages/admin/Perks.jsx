import { useEffect, useMemo, useState } from "react";
import { EyeIcon, GiftIcon, PencilIcon, PlusIcon, TrashIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { RowActions } from "../../components/RowActions";
import { Alert, Badge, Dialog, Empty, Field, LoadError, PageHeader, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { safeHttpUrl } from "../../lib/safeUrl";
import { formatDate } from "../../lib/format";
import { filterAdminPerks } from "../../lib/perkFilters";

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

function tone(status) {
  if (status === "Active") return "active";
  return "unknown";
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

function validityLabel(row) {
  if (row.valid_from && row.valid_to) return `${formatDate(row.valid_from)} – ${formatDate(row.valid_to)}`;
  if (row.valid_to) return `Until ${formatDate(row.valid_to)}`;
  if (row.valid_from) return `From ${formatDate(row.valid_from)}`;
  return "";
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
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  const items = useMemo(
    () => filterAdminPerks(data?.items, { query, category, status, expiry }),
    [data, query, category, status, expiry]
  );

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
      valid_to: form.get("valid_to") || null,
      requires_active_card: form.get("requires_active_card") === "on",
      active: form.get("status") === "Active",
    };
    if (!payload.name?.trim() || !payload.discount?.trim()) {
      setError("Perk name and offer are required.");
      return;
    }
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
      <div className="admin-perks">
        <PageHeader
          actions={
            <button className="btn btn-navy" type="button" onClick={() => setEditor({ ...EMPTY })}>
              <PlusIcon size={16} />
              Add Perk
            </button>
          }
        />
        <Alert type="error">{error && data ? error : null}</Alert>
        <Alert type="ok">{ok}</Alert>
        {error && !data ? <LoadError onRetry={load}>{error}</LoadError> : null}

        <div className="perk-stats admin-perk-stats">
          <span className="perk-stat">Total perks: {data?.total ?? 0}</span>
          <span className="perk-stat">Active: {data?.active ?? 0}</span>
          <span className="perk-stat">Inactive: {data?.inactive ?? 0}</span>
          <span className="perk-stat">Expiring soon: {data?.expiring_soon ?? 0}</span>
        </div>

        <div className="filter-bar admin-perk-filters">
          <Field label="Search">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, partner, or offer" />
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

        <section className="card panel admin-perk-panel">
          {!items.length ? (
            <Empty title="No perks match" icon={<GiftIcon size={22} />}>Add a perk or adjust the filters.</Empty>
          ) : (
            <div className="table-wrap admin-perk-table">
              <table className="data">
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
                  {items.map((row) => (
                    <tr key={row.id} className="admin-perk-row" onClick={() => setViewItem(row)}>
                      <td>
                        <CellText value={row.partner || row.name} lines={3} />
                      </td>
                      <td>
                        <CellText value={row.discount || row.name} lines={3} />
                      </td>
                      <td>
                        <CellText value={row.category} lines={2} />
                      </td>
                      <td>
                        <CellText value={row.valid_to ? formatDate(row.valid_to) : ""} lines={2} />
                      </td>
                      <td className="cell-status">
                        <Badge tone={tone(row.status)}>{row.status}</Badge>
                      </td>
                      <td className="cell-actions">
                        <PerkActions
                          row={row}
                          onView={setViewItem}
                          onEdit={setEditor}
                          onToggle={toggle}
                          onDelete={setRemoveTarget}
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
        <Dialog title={editor.id ? "Edit perk" : "Add perk"} hideActions wide onClose={() => setEditor(null)}>
          <form onSubmit={savePerk} className="settings-form admin-perks-form">
            <div className="inline-fields">
              <Field label="Perk/Discount Name" required>
                <input name="name" defaultValue={editor.name || ""} required />
              </Field>
              <Field label="Partner Name">
                <input name="partner" defaultValue={editor.partner || ""} />
              </Field>
            </div>
            <div className="inline-fields">
              <Field label="Category">
                <input name="category" defaultValue={editor.category || ""} placeholder="Campus, Dining, Events, Career" />
              </Field>
              <Field label="Discount/Offer" required>
                <textarea name="discount" defaultValue={editor.discount || ""} required rows={2} />
              </Field>
            </div>
            <Field label="Description">
              <textarea name="description" defaultValue={editor.description || ""} rows={4} />
            </Field>
            <Field label="Eligibility">
              <textarea name="eligibility" defaultValue={editor.eligibility || ""} rows={4} />
            </Field>
            <Field label="Terms and Conditions">
              <textarea name="how_to_claim" defaultValue={editor.how_to_claim || ""} rows={5} />
            </Field>
            <div className="inline-fields">
              <Field label="Valid From"><input type="date" name="valid_from" defaultValue={editor.valid_from || ""} /></Field>
              <Field label="Valid Until"><input type="date" name="valid_to" defaultValue={editor.valid_to || ""} /></Field>
            </div>
            <div className="inline-fields">
              <Field label="Contact Information"><input name="contact" defaultValue={editor.contact || ""} /></Field>
              <Field label="Website"><input name="website" defaultValue={editor.website || ""} placeholder="https://" /></Field>
            </div>
            <Field label="Image/Logo">
              <input type="file" name="image" accept="image/png,image/jpeg,image/webp" />
            </Field>
            <label className="check">
              <input type="checkbox" name="requires_active_card" defaultChecked={Boolean(editor.requires_active_card)} />
              Requires an Angelenean Alumni Card
            </label>
            <Field label="Status">
              <select name="status" defaultValue={editor.active === false ? "Inactive" : "Active"}>
                <option>Active</option>
                <option>Inactive</option>
              </select>
            </Field>
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
              <DetailRow label="Status"><Badge tone={tone(viewItem.status)}>{viewItem.status}</Badge></DetailRow>
            </dl>
          </div>
        </Dialog>
      ) : null}

      {removeTarget ? (
        <Dialog
          title="Delete this perk?"
          description={`Are you sure you want to delete “${removeTarget.name || removeTarget.partner || "this perk"}”?`}
          confirmLabel="Delete perk"
          danger
          onConfirm={remove}
          onClose={() => setRemoveTarget(null)}
        >
          <p>It will no longer appear in the alumni Perks & Discounts list. This cannot be undone.</p>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
