import { useEffect, useState } from "react";
import { Panel, TagList } from "../../components/RecordViews";
import { FileDrop } from "../../components/FileDrop";
import { PortalShell } from "../../components/Layout";
import { PencilIcon, PlusIcon, SearchIcon, UploadIcon } from "../../components/icons";
import { Alert, Dialog, Empty, Field, LoadError, Pager } from "../../components/ui";
import { api } from "../../lib/api";
import { splitList } from "../../lib/format";

function CodeField({ value, onChange, catalog, required = true }) {
  const [filter, setFilter] = useState("");
  const needle = filter.trim().toLowerCase();
  const choices = catalog.filter((row) => (
    !needle
    || row.soc_code === value
    || `${row.soc_code} ${row.description || ""}`.toLowerCase().includes(needle)
  ));
  return (
    <>
      <Field label="Find a code" hint="The selected code must already exist in the catalog.">
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Search code or description" />
      </Field>
      <Field label="Target SOC/PSOC Code" required={required}>
        <select value={value} onChange={(event) => onChange(event.target.value)} required={required}>
          <option value="">Select a code</option>
          {choices.map((row) => (
            <option key={row.soc_code} value={row.soc_code}>{row.soc_code} — {row.description}</option>
          ))}
        </select>
      </Field>
    </>
  );
}

const EMPTY_CODE = {
  soc_code: "",
  description: "",
  category: "",
  title_patterns: "",
  degree_patterns: "",
  major_group: "",
};

const EMPTY_MAP = { raw_title: "", soc_code: "", admin_notes: "" };

const WORKBOOK_ACCEPT = ".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12";

function validateWorkbook(file) {
  const name = String(file?.name || "").toLowerCase();
  if (!name.endsWith(".xlsx") && !name.endsWith(".xlsm")) return "Upload an Excel workbook (.xlsx).";
  if (file.size > 5 * 1024 * 1024) return "The workbook must be 5 MB or smaller.";
  return "";
}

export default function AdminSoc() {
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [workbook, setWorkbook] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [form, setForm] = useState(EMPTY_CODE);
  const [editor, setEditor] = useState(null);
  const [map, setMap] = useState(EMPTY_MAP);
  const [catalog, setCatalog] = useState([]);
  const [confirmCode, setConfirmCode] = useState(false);

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

  async function loadCatalog() {
    const collected = [];
    let pageNo = 1;
    let total = 0;
    do {
      const result = await api(`/api/admin/soc?page=${pageNo}&page_size=100`);
      collected.push(...(result.items || []));
      total = result.total || 0;
      pageNo += 1;
    } while (collected.length < total && pageNo <= 20);
    setCatalog(collected);
  }

  useEffect(() => {
    load("", 1);
    loadCatalog().catch(() => {});
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
      setForm(EMPTY_CODE);
      setShowAdd(false);
      await load(q, 1);
      await loadCatalog();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function requestSaveSoc(event) {
    event.preventDefault();
    if (!editor?.original_code) return;
    if (!editor.soc_code.trim() || !editor.description.trim()) {
      setError("SOC code and description are required.");
      return;
    }
    if (editor.soc_code.trim() !== editor.original_code) {
      setConfirmCode(true);
      return;
    }
    saveSoc();
  }

  async function saveSoc() {
    if (!editor?.original_code) return;
    setError("");
    setOk("");
    setSaving(true);
    try {
      const result = await api(`/api/admin/soc/${encodeURIComponent(editor.original_code)}`, {
        method: "PUT",
        body: {
          soc_code: editor.soc_code.trim(),
          description: editor.description.trim(),
          category: editor.category,
          title_patterns: editor.title_patterns,
          degree_patterns: editor.degree_patterns,
          major_group: editor.major_group,
        },
      });
      setOk(result.message || "SOC mapping updated.");
      setConfirmCode(false);
      setEditor(null);
      await load(q, page);
      await loadCatalog();
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
      setMap(EMPTY_MAP);
      setShowMap(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function closeUpload() {
    if (saving) return;
    setShowUpload(false);
    setWorkbook(null);
    setUploadResult(null);
  }

  async function uploadWorkbook(event) {
    event.preventDefault();
    if (!workbook) return;
    setError("");
    setOk("");
    setSaving(true);
    setUploadResult(null);
    try {
      const body = new FormData();
      body.append("file", workbook);
      const result = await api("/api/admin/soc/import", { method: "POST", form: body });
      setUploadResult(result);
      if (result.added) {
        setOk(result.message);
        await load(q, 1);
        await loadCatalog();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const rows = data?.items || [];

  return (
    <PortalShell role="Admin">
      <div className="admin-soc setup-page">
        <section className="card panel soc-intro" aria-label="SOC Mapping">
          <header className="panel-head">
            <div>
              <h2>SOC Mapping</h2>
              <p className="lead">Maintain the occupational-code catalog, map raw job titles to existing codes, and see how those mappings affect degree alignment.</p>
            </div>
            <div className="panel-actions">
              <button className="btn btn-outline" type="button" onClick={() => { setMap(EMPTY_MAP); setShowMap(true); }}>
                Map Job Title
              </button>
              <button className="btn btn-outline" type="button" onClick={() => { setWorkbook(null); setUploadResult(null); setShowUpload(true); }}>
                <UploadIcon size={16} />
                Upload Excel
              </button>
              <button className="btn btn-navy" type="button" onClick={() => { setForm(EMPTY_CODE); setShowAdd(true); }}>
                <PlusIcon size={16} />
                Add SOC Code
              </button>
            </div>
          </header>
          <details className="setup-details">
            <summary>How Alignment Works</summary>
            <ol>
              <li>An approved job-title mapping that matches the job title, ignoring capitalization, is used first.</li>
              <li>If no approved mapping applies, CareerSense compares the title with occupational-code patterns, or with the code description when no patterns are configured.</li>
              <li>When an occupation matches, its degree patterns decide whether the result is Aligned, Misaligned, or Unknown.</li>
              <li>If no occupational code matches, a separate course-based check may still decide alignment. Otherwise the result is Unknown.</li>
            </ol>
          </details>
        </section>
        <Alert type="error">{error && data ? error : null}</Alert>
        <Alert type="ok">{ok}</Alert>
        {error && !data ? <LoadError onRetry={() => load(q, page)}>{error}</LoadError> : null}

        <Panel
          className="soc-catalog"
          title="Occupational-Code Catalog"
          description="Search covers code, description, category, and job-title patterns."
        >
          <form
            className="soc-search"
            onSubmit={(event) => {
              event.preventDefault();
              load(q, 1);
            }}
          >
            <Field label="Search">
              <div className="search-field">
                <SearchIcon size={16} />
                <input
                  value={q}
                  onChange={(event) => setQ(event.target.value)}
                  placeholder="Search by code, description, or pattern"
                  aria-label="Search by code, description, or job-title pattern"
                />
              </div>
            </Field>
            <button className="btn btn-navy" disabled={busy} type="submit">Search</button>
          </form>
        {!rows.length ? (
          <Empty title={q.trim() ? "No codes match this search" : "No occupational codes yet"}>
            {q.trim() ? "Try another code, description, category, or job-title pattern." : "Add an SOC code to start the catalog."}
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="data stack">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Job Title Patterns</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.soc_code}>
                    <td data-label="Code"><strong>{row.soc_code}</strong></td>
                    <td className="cell-title" data-label="Description">{row.description}</td>
                    <td data-label="Category">{row.category || "—"}</td>
                    <td data-label="Job Title Patterns"><TagList compact items={splitList(row.title_patterns)} empty="—" /></td>
                    <td className="cell-actions" data-label="Actions">
                      <button
                        className="btn btn-outline btn-sm"
                        type="button"
                        onClick={() => setEditor({ ...row, original_code: row.soc_code })}
                      >
                        <PencilIcon size={14} />
                        Edit
                      </button>
                    </td>
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
        <Dialog
          title="Add SOC Code"
          description="Use this when a new occupation should be available for alignment."
          hideActions
          wide
          onClose={() => { if (!saving) { setShowAdd(false); setForm(EMPTY_CODE); } }}
        >
        <form className="settings-form" id="add-soc" onSubmit={addSoc}>
          <fieldset className="setup-group">
            <legend>Occupation Details</legend>
            <Field label="PSOC/SOC Code" required>
              <input value={form.soc_code} onChange={(e) => setForm({ ...form, soc_code: e.target.value })} required />
            </Field>
            <Field label="Description" required>
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
            </Field>
            <div className="inline-fields">
              <Field label="Category">
                <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
              </Field>
              <Field label="Major Group">
                <input value={form.major_group} onChange={(e) => setForm({ ...form, major_group: e.target.value })} />
              </Field>
            </div>
          </fieldset>
          <fieldset className="setup-group">
            <legend>Job-Title Patterns</legend>
            <Field label="Comma-separated job titles" hint="Example: software engineer, developer, programmer">
              <textarea value={form.title_patterns} onChange={(e) => setForm({ ...form, title_patterns: e.target.value })} placeholder="software engineer, developer, programmer" />
            </Field>
          </fieldset>
          <fieldset className="setup-group">
            <legend>Degree Patterns</legend>
            <Field label="Comma-separated degree keywords" hint="Example: information technology, computer science">
              <textarea value={form.degree_patterns} onChange={(e) => setForm({ ...form, degree_patterns: e.target.value })} placeholder="information technology, computer science" />
            </Field>
          </fieldset>
          <div className="dialog-actions">
            <button className="btn btn-outline" type="button" onClick={() => { if (!saving) { setShowAdd(false); setForm(EMPTY_CODE); } }}>Cancel</button>
            <button className="btn btn-navy" disabled={saving}>{saving ? "Saving…" : "Save code"}</button>
          </div>
        </form>
        </Dialog>
      ) : null}

      {showMap ? (
        <Dialog
          title="Map a Raw Job Title"
          description="Map a resume or tracer job title to a code that already exists. Saving a title that is already mapped updates that mapping and marks it approved."
          hideActions
          wide
          onClose={() => { if (!saving) { setShowMap(false); setMap(EMPTY_MAP); } }}
        >
          <form className="settings-form" onSubmit={addMapping}>
            {error ? <Alert type="error">{error}</Alert> : null}
            <Field label="Raw Job Title" required>
              <input value={map.raw_title} onChange={(e) => setMap({ ...map, raw_title: e.target.value })} required />
            </Field>
            <CodeField value={map.soc_code} onChange={(soc_code) => setMap({ ...map, soc_code })} catalog={catalog} />
            <Field label="Optional Notes">
              <textarea value={map.admin_notes} onChange={(e) => setMap({ ...map, admin_notes: e.target.value })} />
            </Field>
            <div className="dialog-actions">
              <button className="btn btn-outline" type="button" onClick={() => { if (!saving) { setShowMap(false); setMap(EMPTY_MAP); } }}>Cancel</button>
              <button className="btn btn-navy" disabled={saving}>{saving ? "Saving…" : "Save Mapping"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}

      {showUpload ? (
        <Dialog
          title="Upload Excel"
          description="Add occupational codes from a workbook. The first row needs Code and Description. Category, job-title patterns, degree patterns, and major group are optional. Codes that already exist are left unchanged."
          hideActions
          onClose={closeUpload}
        >
          <form className="settings-form" onSubmit={uploadWorkbook}>
            {error ? <Alert type="error">{error}</Alert> : null}
            <FileDrop
              compact
              accept={WORKBOOK_ACCEPT}
              file={workbook}
              onChange={(file) => { setWorkbook(file); setUploadResult(null); }}
              validate={validateWorkbook}
              disabled={saving}
              formats="Excel .xlsx"
              maxSize="5 MB"
              label="Workbook"
              prompt="Drop an Excel file here, or browse to choose one."
            />
            {uploadResult ? (
              <Alert type={uploadResult.added ? "ok" : "error"}>{uploadResult.message}</Alert>
            ) : null}
            {uploadResult?.issues?.length ? (
              <ul className="soc-import-issues">
                {uploadResult.issues.map((issue) => <li key={issue}>{issue}</li>)}
              </ul>
            ) : null}
            <div className="dialog-actions">
              <button className="btn btn-outline" type="button" onClick={closeUpload}>Close</button>
              <button className="btn btn-navy" disabled={saving || !workbook}>{saving ? "Uploading…" : "Add codes"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}

      {editor ? (
        <Dialog title={`Edit ${editor.original_code}`} hideActions onClose={() => setEditor(null)}>
          <form onSubmit={requestSaveSoc} className="settings-form">
            <fieldset className="setup-group">
              <legend>Occupation Details</legend>
              <Field label="PSOC/SOC Code" required>
                <input value={editor.soc_code} onChange={(e) => setEditor({ ...editor, soc_code: e.target.value })} required />
              </Field>
              <Field label="Description" required>
                <input value={editor.description} onChange={(e) => setEditor({ ...editor, description: e.target.value })} required />
              </Field>
              <Field label="Category">
                <input value={editor.category || ""} onChange={(e) => setEditor({ ...editor, category: e.target.value })} />
              </Field>
              <Field label="Major Group">
                <input value={editor.major_group || ""} onChange={(e) => setEditor({ ...editor, major_group: e.target.value })} />
              </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Job-Title Patterns</legend>
              <Field label="Comma-separated job titles" hint="Example: software engineer, developer, programmer">
                <textarea value={editor.title_patterns || ""} onChange={(e) => setEditor({ ...editor, title_patterns: e.target.value })} placeholder="software engineer, developer, programmer" />
              </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Degree Patterns</legend>
              <Field label="Comma-separated degree keywords" hint="Example: information technology, computer science">
                <textarea value={editor.degree_patterns || ""} onChange={(e) => setEditor({ ...editor, degree_patterns: e.target.value })} placeholder="information technology, computer science" />
              </Field>
            </fieldset>
            <div className="dialog-actions">
              <button type="button" className="btn btn-outline" onClick={() => setEditor(null)}>Cancel</button>
              <button className="btn btn-navy" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}
      {confirmCode && editor ? (
        <Dialog
          title={`Change ${editor.original_code}?`}
          description={`Changing this code to ${editor.soc_code.trim()} updates job-title mappings and tracer submissions that stored ${editor.original_code}.`}
          confirmLabel={saving ? "Saving…" : "Update code"}
          busy={saving}
          onConfirm={saveSoc}
          onClose={() => { if (!saving) setConfirmCode(false); }}
        />
      ) : null}
      </div>
    </PortalShell>
  );
}
