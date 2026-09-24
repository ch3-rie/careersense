import { useEffect, useState } from "react";
import { EyeIcon, PencilIcon, PlusIcon, RefreshIcon, UsersIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { RowActions } from "../../components/RowActions";
import { Alert, Badge, Dialog, Empty, Field, LoadError, PageHeader, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDate, formatDateTime } from "../../lib/format";

const EMPTY = { first_name: "", last_name: "", email: "", role: "Admin", status: "Active" };

export default function AdminUsers() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [editor, setEditor] = useState(null);
  const [viewItem, setViewItem] = useState(null);
  const [confirmCreate, setConfirmCreate] = useState(null);
  const [tempPassword, setTempPassword] = useState("");
  const [action, setAction] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      setData(await api("/api/admin/users"));
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

  async function createAdmin() {
    setBusy(true);
    setError("");
    try {
      const result = await api("/api/admin/users", { method: "POST", body: { ...confirmCreate, confirm: true } });
      setTempPassword(result.temporary_password);
      setOk(result.message || "Administrator created successfully");
      setConfirmCreate(null);
      setEditor(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    if (!editor.id) {
      const payload = {
        first_name: form.get("first_name"),
        last_name: form.get("last_name"),
        email: form.get("email"),
        role: form.get("role") || "Admin",
        status: form.get("status") || "Active",
      };
      setConfirmCreate(payload);
      return;
    }
    setBusy(true);
    try {
      const result = await api(`/api/admin/users/${editor.id}`, {
        method: "PATCH",
        body: {
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          email: form.get("email"),
          role: form.get("role"),
          status: form.get("status"),
        },
      });
      setOk(result.message || "Administrator updated");
      setEditor(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runAction() {
    if (!action) return;
    setBusy(true);
    try {
      const result = await api(`/api/admin/users/${action.id}/${action.path}`, { method: "POST" });
      if (result.temporary_password) setTempPassword(result.temporary_password);
      setOk(result.message);
      setAction(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <PageHeader
        actions={
          <button className="btn btn-navy" type="button" onClick={() => setEditor({ ...EMPTY })}>
            <PlusIcon size={16} />
            Add Admin User
          </button>
        }
      />
      <Alert type="error">{error && data ? error : null}</Alert>
      <Alert type="ok">{ok}</Alert>
      {error && !data ? <LoadError onRetry={load}>{error}</LoadError> : null}

      <div className="perk-stats admin-perk-stats">
        <span className="perk-stat">Total administrators: {data?.total ?? 0}</span>
        <span className="perk-stat">Active: {data?.active ?? 0}</span>
        <span className="perk-stat">Inactive: {data?.inactive ?? 0}</span>
      </div>

      <section className="card panel">
        {!data?.items?.length ? (
          <Empty title="No administrators" icon={<UsersIcon size={22} />}>Add an administrator to share portal access.</Empty>
        ) : (
          <div className="table-wrap admin-users-table">
            <table className="data stack">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Last Login</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td data-label="Name">{row.name}</td>
                    <td data-label="Email">{row.email}</td>
                    <td data-label="Role"><Badge>{row.role}</Badge></td>
                    <td data-label="Status"><Badge tone={row.status === "Active" ? "active" : "unknown"}>{row.status}</Badge></td>
                    <td data-label="Created">{formatDate(row.created_at)}</td>
                    <td data-label="Last Login">{row.last_login_at ? formatDateTime(row.last_login_at) : "—"}</td>
                    <td className="cell-actions">
                      <RowActions
                        primary={[
                          { id: "view", label: "View", icon: EyeIcon, onClick: () => setViewItem(row) },
                          { id: "edit", label: "Edit", icon: PencilIcon, onClick: () => setEditor(row) },
                        ]}
                        more={[
                          row.status === "Active"
                            ? {
                              id: "deactivate",
                              label: "Deactivate",
                              danger: true,
                              disabled: row.id === user?.id || data.active <= 1,
                              disabledReason: row.id === user?.id
                                ? "You cannot deactivate your own account."
                                : "The last active administrator cannot be deactivated.",
                              onClick: () => setAction({
                                id: row.id,
                                path: "deactivate",
                                title: "Deactivate administrator?",
                                body: "They will no longer be able to sign in to the Admin Portal.",
                              }),
                            }
                            : {
                              id: "activate",
                              label: "Activate",
                              onClick: () => setAction({
                                id: row.id,
                                path: "activate",
                                title: "Activate administrator?",
                                body: "They will regain access to the Admin Portal.",
                              }),
                            },
                          {
                            id: "reset",
                            label: "Reset password",
                            icon: RefreshIcon,
                            onClick: () => setAction({
                              id: row.id,
                              path: "reset-password",
                              title: "Reset password?",
                              body: "A new temporary password will be generated. It will be shown once and is not stored in plain text.",
                            }),
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

      {editor ? (
        <Dialog title={editor.id ? "Edit administrator" : "Add administrator"} hideActions onClose={() => setEditor(null)}>
          <form onSubmit={saveEdit} className="settings-form">
            <div className="inline-fields">
              <Field label="First Name" required><input name="first_name" defaultValue={editor.first_name || ""} required /></Field>
              <Field label="Last Name" required><input name="last_name" defaultValue={editor.last_name || ""} required /></Field>
            </div>
            <Field label="Email" required><input type="email" name="email" defaultValue={editor.email || ""} required /></Field>
            <div className="inline-fields">
              <Field label="Role">
                <select name="role" defaultValue={editor.role || "Admin"}>
                  {(data?.roles || ["Admin"]).map((role) => <option key={role}>{role}</option>)}
                </select>
              </Field>
              <Field label="Account status">
                <select name="status" defaultValue={editor.status || "Active"}>
                  <option>Active</option>
                  <option>Inactive</option>
                </select>
              </Field>
            </div>
            <div className="dialog-actions">
              <button type="button" className="btn btn-outline" onClick={() => setEditor(null)}>Cancel</button>
              <button className="btn btn-navy" disabled={busy}>{editor.id ? "Save" : "Continue"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}

      {confirmCreate ? (
        <Dialog title="Create this administrator?" confirmLabel="Create account" busy={busy} onConfirm={createAdmin} onClose={() => setConfirmCreate(null)}>
          <p>A secure temporary password will be generated. It is hashed immediately and shown only once. The new administrator must change it after first login.</p>
          <p><strong>{confirmCreate.first_name} {confirmCreate.last_name}</strong><br />{confirmCreate.email}<br />Role: {confirmCreate.role}</p>
        </Dialog>
      ) : null}

      {viewItem ? (
        <Dialog title={viewItem.name} confirmLabel="Close" onConfirm={() => setViewItem(null)} onClose={() => setViewItem(null)}>
          <p>{viewItem.email}</p>
          <p>Role: {viewItem.role}</p>
          <p>Status: {viewItem.status}</p>
          <p>Created: {formatDateTime(viewItem.created_at)}</p>
          <p>Last login: {viewItem.last_login_at ? formatDateTime(viewItem.last_login_at) : "Never"}</p>
        </Dialog>
      ) : null}

      {action ? (
        <Dialog title={action.title} confirmLabel="Confirm" danger={action.path === "deactivate"} busy={busy} onConfirm={runAction} onClose={() => setAction(null)}>
          <p>{action.body}</p>
        </Dialog>
      ) : null}

      {tempPassword ? (
        <Dialog title="Temporary password" confirmLabel="I have copied it" onConfirm={() => setTempPassword("")} onClose={() => setTempPassword("")}>
          <p>Share this password securely. It will not be shown again and is not stored as plain text.</p>
          <p className="temp-password">{tempPassword}</p>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
