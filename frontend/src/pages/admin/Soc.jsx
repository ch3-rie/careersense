import { useEffect, useState } from "react";
import { Panel, TagList } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { PlusIcon, SearchIcon } from "../../components/icons";
import { Alert, Empty, Field, LoadError, Pager } from "../../components/ui";
import { api } from "../../lib/api";
import { splitList } from "../../lib/format";

export default function AdminSoc() {
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ soc_code: "", description: "", category: "", title_patterns: "", degree_patterns: "" });
  const [map, setMap] = useState({ raw_title: "", soc_code: "", admin_notes: "" });

  async function load(term = q, nextPage = 1) {
    setError("");
    setBusy(true);
    try {
      const result = await api(`/api/admin/soc?q=${encodeURIComponent(term)}&page=${nextPage}&page_size=25`);
      setData(result);
      setPage(nextPage);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load("", 1);
  }, []);

  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  async function addSoc(e) {
    e.preventDefault();
    setError("");
    setOk("");
    setSaving(true);
    try {
      await api("/api/admin/soc", { method: "POST", body: form });
      setOk(`SOC ${form.soc_code} saved.`);
      setForm({ soc_code: "", description: "", category: "", title_patterns: "", degree_patterns: "" });
      setShowAdd(false);
      await load("", 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function addMapping(e) {
    e.preventDefault();
    setError("");
    setOk("");
    setSaving(true);
    try {
      await api("/api/admin/job-mappings", { method: "POST", body: map });
      setOk(`Mapped “${map.raw_title}” to ${map.soc_code}.`);
      setMap({ raw_title: "", soc_code: "", admin_notes: "" });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const rows = data?.items || [];

  return (
    <PortalShell role="Admin">
      <Alert type="error">{error && data ? error : null}</Alert>
      <Alert type="ok">{ok}</Alert>
      {error && !data ? <LoadError onRetry={() => load(q, page)}>{error}</LoadError> : null}

      <Panel
        title="Occupational codes"
        actions={
          <button className="btn btn-navy" type="button" onClick={() => setShowAdd(true)}>
            <PlusIcon size={16} />
            Add SOC Code
          </button>
        }
      >
        <form
          className="filter-bar"
          onSubmit={(event) => {
            event.preventDefault();
            load(q, 1);
          }}
        >
          <Field label="Search by code, description, or job-title pattern">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by code, description, or job-title pattern" />
          </Field>
          <button className="btn btn-navy" disabled={busy} type="submit">
            <SearchIcon size={16} />
            {busy ? "Searching…" : "Search"}
          </button>
        </form>
        {!rows.length ? (
          <Empty title="No codes found">Adjust the search or add a new SOC code.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data stack">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Job Title Patterns</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.soc_code}>
                    <td data-label="Code"><strong>{row.soc_code}</strong></td>
                    <td className="cell-title" data-label="Description">{row.description}</td>
                    <td data-label="Category">{row.category || "—"}</td>
                    <td data-label="Job Title Patterns"><TagList compact items={splitList(row.title_patterns)} empty="—" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data?.total ? (
          <Pager
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPage={(next) => load(q, next)}
          />
        ) : null}
      </Panel>

      {showAdd ? (
        <form className="card panel" id="add-soc" onSubmit={addSoc}>
          <header className="panel-head">
            <div>
              <h2>Add SOC Code</h2>
              <p className="lead">Use this when a new occupation should be available for alignment.</p>
            </div>
            <button className="btn btn-outline btn-sm" type="button" onClick={() => setShowAdd(false)}>Cancel</button>
          </header>
          <Field label="PSOC/SOC Code" required>
            <input value={form.soc_code} onChange={(e) => setForm({ ...form, soc_code: e.target.value })} required />
          </Field>
          <Field label="Description" required>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
          </Field>
          <Field label="Category">
            <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
          </Field>
          <Field label="Job Title Patterns" hint="Add common job titles that should map to this occupation. Use comma-separated keywords.">
            <textarea value={form.title_patterns} onChange={(e) => setForm({ ...form, title_patterns: e.target.value })} placeholder="software engineer, developer, programmer" />
          </Field>
          <Field label="Degree Patterns" hint="Comma-separated degree keywords.">
            <textarea value={form.degree_patterns} onChange={(e) => setForm({ ...form, degree_patterns: e.target.value })} />
          </Field>
          <button className="btn btn-navy" disabled={saving}>{saving ? "Saving…" : "Save code"}</button>
        </form>
      ) : null}

      <form className="card panel" id="map-title" onSubmit={addMapping}>
        <header className="panel-head">
          <div>
            <h2>Map a Raw Job Title</h2>
            <p className="lead">These mappings influence whether tracer and resume job titles are classified as Aligned, Misaligned, or Unknown.</p>
          </div>
        </header>
        <div className="inline-fields">
          <Field label="Resume Job Title" required>
            <input value={map.raw_title} onChange={(e) => setMap({ ...map, raw_title: e.target.value })} required />
          </Field>
          <Field label="Target SOC Code" required>
            <input value={map.soc_code} onChange={(e) => setMap({ ...map, soc_code: e.target.value })} required />
          </Field>
        </div>
        <Field label="Optional Notes">
          <textarea value={map.admin_notes} onChange={(e) => setMap({ ...map, admin_notes: e.target.value })} />
        </Field>
        <button className="btn btn-navy" disabled={saving}>{saving ? "Saving…" : "Save Mapping"}</button>
      </form>
    </PortalShell>
  );
}
