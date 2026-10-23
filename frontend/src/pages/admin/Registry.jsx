import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileDrop } from "../../components/FileDrop";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { PlusIcon, SearchIcon, UploadIcon } from "../../components/icons";
import { Alert, Badge, Dialog, Empty, Field, LoadError, Pager, SortButton, TableSkeleton, sortBy, toggleSort } from "../../components/ui";
import { courseCodeFor, courseLabel, programChoices } from "../../lib/academicFilters";
import { api } from "../../lib/api";

const EMPTY_FORM = {
  student_id: "",
  first_name: "",
  middle_name: "",
  last_name: "",
  personal_email: "",
  degree: "",
  year_graduated: "",
  course_code: "",
  college: "",
};

const PREVIEW_PAGE_SIZE = 8;
const RECORD_PAGE_SIZE = 50;

const STEPS = [
  { title: "Upload Workbook", detail: "Select the RO Excel file." },
  { title: "Review Records", detail: "Validate the workbook and inspect the import preview." },
  { title: "Confirm Import", detail: "Confirm the number of eligible records before saving." },
  { title: "Import Results", detail: "Display the final outcome." },
];

const STATUS_TONE = {
  ready: "approved",
  imported: "approved",
  skipped: "pending",
  invalid: "rejected",
};

const STATUS_LABEL = {
  ready: "Ready",
  imported: "Imported",
  skipped: "Skipped",
  invalid: "Invalid",
};

function validateWorkbook(file) {
  const name = String(file?.name || "").toLowerCase();
  if (!name.endsWith(".xlsx") && !name.endsWith(".xlsm")) {
    return "Upload an Excel workbook (.xlsx or .xlsm) from the Registrar's Office.";
  }
  if (!file.size) return "The uploaded Excel file is empty.";
  if (file.size > 10 * 1024 * 1024) return "The Excel file is larger than 10 MB.";
  return "";
}

function formatManila(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-PH", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function graduateName(row) {
  return [row.first_name, row.middle_name, row.last_name].filter(Boolean).join(" ") || "—";
}

function countPhrase(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function introductionNote(row, catalog, catalogReady) {
  if (!catalogReady || row.status !== "ready") return "";
  const college = String(row.college || "");
  const course = String(row.course || "");
  if (!college || !course) return "";
  const collegeKnown = (catalog.colleges || []).some((name) => name.toLowerCase() === college.toLowerCase());
  const courseKnown = (catalog.programs || []).some(
    (item) => item.college.toLowerCase() === college.toLowerCase() && item.course.toLowerCase() === course.toLowerCase(),
  );
  if (!collegeKnown) {
    return "This record introduces a new college and course. They will be added to Colleges and Courses after a successful import. Existing graduate records stay unchanged.";
  }
  if (!courseKnown) {
    return "This record introduces a new course for an existing college. It will be added to Colleges and Courses after a successful import. Existing graduate records stay unchanged.";
  }
  return "";
}

function rowReason(row, catalog, catalogReady) {
  return row.message || introductionNote(row, catalog, catalogReady);
}

export default function AdminRegistry() {
  const [catalog, setCatalog] = useState({ colleges: [], courses: [], pairs: [], programs: [] });
  const [catalogReady, setCatalogReady] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [preview, setPreview] = useState(null);
  const [importError, setImportError] = useState("");
  const [importResult, setImportResult] = useState(null);
  const [lastImport, setLastImport] = useState(null);
  const [previewQuery, setPreviewQuery] = useState("");
  const [previewStatus, setPreviewStatus] = useState("all");
  const [previewPage, setPreviewPage] = useState(1);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reasonRow, setReasonRow] = useState(null);
  const [issuePage, setIssuePage] = useState(1);
  const [records, setRecords] = useState(null);
  const [recordsBusy, setRecordsBusy] = useState(true);
  const [recordsError, setRecordsError] = useState("");
  const [recordQuery, setRecordQuery] = useState("");
  const [recordCollege, setRecordCollege] = useState("");
  const [recordCourse, setRecordCourse] = useState("");
  const [recordSort, setRecordSort] = useState({ key: "last_name", dir: "asc" });

  async function loadRecords({ term = recordQuery, nextCollege = recordCollege, nextCourse = recordCourse, nextPage = 1 } = {}) {
    setRecordsError("");
    setRecordsBusy(true);
    try {
      const params = new URLSearchParams({
        q: term,
        college: nextCollege,
        course: nextCourse,
        page: String(nextPage),
        page_size: String(RECORD_PAGE_SIZE),
      });
      const result = await api(`/api/admin/university-records?${params}`);
      setRecords(result);
      setLastImport(result?.last_import || null);
      return result;
    } catch (err) {
      setRecordsError(err.message);
      return null;
    } finally {
      setRecordsBusy(false);
    }
  }

  useEffect(() => {
    api("/api/admin/academic-filters").then((result) => {
      setCatalog(result);
      setCatalogReady(true);
    }).catch(() => {});
    loadRecords({ term: "", nextCollege: "", nextCourse: "", nextPage: 1 });
  }, []);

  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  async function create(event) {
    event.preventDefault();
    setError("");
    setOk("");
    setSaving(true);
    try {
      await api("/api/admin/university-records", { method: "POST", body: form });
      setOk("Graduate record added successfully.");
      setForm(EMPTY_FORM);
      setShowAdd(false);
      const refreshed = await api("/api/admin/academic-filters");
      setCatalog(refreshed);
      setCatalogReady(true);
      setRecordQuery("");
      setRecordCollege("");
      setRecordCourse("");
      await loadRecords({ term: "", nextCollege: "", nextCourse: "", nextPage: 1 });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function takeFile(next) {
    setFile(next);
    setPreview(null);
    setImportError("");
    setImportResult(null);
    setConfirmOpen(false);
    setReasonRow(null);
    setPreviewQuery("");
    setPreviewStatus("all");
    setPreviewPage(1);
  }

  async function reviewFile() {
    if (!file || phase !== "idle") return;
    setImportError("");
    setImportResult(null);
    setConfirmOpen(false);
    setPhase("review");
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await api("/api/admin/university-records/import/preview", { method: "POST", form: body, toast: false });
      setPreview(result);
      setPreviewQuery("");
      setPreviewStatus("all");
      setPreviewPage(1);
    } catch (err) {
      setPreview(null);
      setImportError(err.message);
    } finally {
      setPhase("idle");
    }
  }

  async function confirmImport() {
    if (!file || !preview?.summary?.ready || phase === "commit") return;
    setImportError("");
    setPhase("commit");
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await api("/api/admin/university-records/import", { method: "POST", form: body, toast: false });
      setImportResult(result);
      setIssuePage(1);
      if ((result.summary?.imported || 0) > 0 && result.last_import) setLastImport(result.last_import);
      setPreview(null);
      setFile(null);
      setConfirmOpen(false);
      if (result.summary?.imported) {
        const refreshed = await api("/api/admin/academic-filters");
        setCatalog(refreshed);
        setCatalogReady(true);
        setRecordQuery("");
        setRecordCollege("");
        setRecordCourse("");
        await loadRecords({ term: "", nextCollege: "", nextCourse: "", nextPage: 1 });
      }
    } catch (err) {
      setImportError(err.message);
    } finally {
      setPhase("idle");
    }
  }

  function resetImport() {
    setFile(null);
    setPreview(null);
    setImportResult(null);
    setImportError("");
    setConfirmOpen(false);
    setReasonRow(null);
  }

  const working = phase !== "idle";
  const readyCount = preview?.summary?.ready || 0;
  const stepIndex = importResult ? 3 : confirmOpen || phase === "commit" ? 2 : preview ? 1 : 0;
  const previewRows = useMemo(() => {
    const term = previewQuery.trim().toLowerCase();
    return (preview?.rows || []).filter((row) => {
      if (previewStatus !== "all" && row.status !== previewStatus) return false;
      if (!term) return true;
      return [row.student_number, graduateName(row), row.college, row.course, row.course_code, row.message]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [preview, previewQuery, previewStatus]);
  const previewSlice = previewRows.slice((previewPage - 1) * PREVIEW_PAGE_SIZE, previewPage * PREVIEW_PAGE_SIZE);
  const newCatalogCount = useMemo(
    () => (preview?.rows || []).filter((row) => introductionNote(row, catalog, catalogReady)).length,
    [preview, catalog, catalogReady],
  );
  const recordRows = sortBy(records?.items || [], recordSort, {
    student_number: (row) => String(row.student_id || "").toLowerCase(),
    first_name: (row) => String(row.first_name || "").toLowerCase(),
    middle_name: (row) => String(row.middle_name || "").toLowerCase(),
    last_name: (row) => String(row.last_name || "").toLowerCase(),
    college: (row) => String(row.college || "").toLowerCase(),
    course: (row) => String(row.degree || "").toLowerCase(),
    course_code: (row) => String(row.course_code || "").toLowerCase(),
  });
  const recordCourseChoices = programChoices(catalog, recordCollege);
  const recordFilters = Boolean(recordQuery.trim() || recordCollege || recordCourse);
  const formPrograms = form.college ? programChoices(catalog, form.college) : [];
  const codeLocked = Boolean(courseCodeFor(catalog, form.college, form.degree));
  const filtersActive = Boolean(previewQuery.trim() || previewStatus !== "all");

  function chooseRecordCollege(value) {
    const allowed = programChoices(catalog, value).map((item) => item.course);
    const nextCourse = allowed.includes(recordCourse) ? recordCourse : "";
    setRecordCollege(value);
    setRecordCourse(nextCourse);
    loadRecords({ nextCollege: value, nextCourse, nextPage: 1 });
  }

  function chooseRecordCourse(value) {
    setRecordCourse(value);
    loadRecords({ nextCourse: value, nextPage: 1 });
  }

  function clearRecordFilters() {
    setRecordQuery("");
    setRecordCollege("");
    setRecordCourse("");
    loadRecords({ term: "", nextCollege: "", nextCourse: "", nextPage: 1 });
  }

  function openAdd() {
    setForm(EMPTY_FORM);
    setShowAdd(true);
    api("/api/admin/academic-filters").then((result) => {
      setCatalog(result);
      setCatalogReady(true);
    }).catch(() => {});
  }

  function closeAdd() {
    if (saving) return;
    setShowAdd(false);
    setForm(EMPTY_FORM);
  }

  function chooseFormCollege(value) {
    const match = programChoices(catalog, value).find((item) => item.course === form.degree);
    setForm({
      ...form,
      college: value,
      degree: match ? match.course : "",
      course_code: match?.course_code || "",
    });
  }

  function chooseFormCourse(value) {
    setForm({
      ...form,
      degree: value,
      course_code: courseCodeFor(catalog, form.college, value),
    });
  }

  return (
    <PortalShell role="Admin">
      <Alert type="error">{error}</Alert>
      <Alert type="ok" title={ok ? "Graduate record added" : undefined}>{ok}</Alert>

      <Panel
        className="import-flow registry-page"
        title="Import List"
        description="The official graduate registry used to verify alumni records."
        actions={(
          <>
            <button className="btn btn-outline" type="button" onClick={() => setShowImport(true)}>
              <UploadIcon size={16} />
              Import Excel
            </button>
            <button className="btn btn-navy" type="button" onClick={openAdd}>
              <PlusIcon size={16} />
              Add Graduate
            </button>
          </>
        )}
      >
        <form
          className="registry-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            loadRecords({ nextPage: 1 });
          }}
        >
          <Field label="Search">
            <input
              value={recordQuery}
              onChange={(event) => setRecordQuery(event.target.value)}
              placeholder="Search"
            />
          </Field>
          <Field label="College">
            <select aria-label="Filter graduates by college" value={recordCollege} onChange={(event) => chooseRecordCollege(event.target.value)}>
              <option value="">All colleges</option>
              {catalog.colleges.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </Field>
          <Field label="Course">
            <select
              aria-label="Filter graduates by course"
              value={recordCourseChoices.some((item) => item.course === recordCourse) ? recordCourse : ""}
              onChange={(event) => chooseRecordCourse(event.target.value)}
            >
              <option value="">All courses</option>
              {recordCourseChoices.map((item) => <option key={`${item.college}-${item.course}`} value={item.course}>{courseLabel(item)}</option>)}
            </select>
          </Field>
          <button className="btn btn-navy" disabled={recordsBusy} type="submit">
            <SearchIcon size={16} />
            {recordsBusy ? "Searching…" : "Search"}
          </button>
          {recordFilters ? (
            <button className="btn btn-outline" type="button" onClick={clearRecordFilters}>Clear filters</button>
          ) : null}
        </form>
        {recordsError && !records ? (
          <LoadError onRetry={() => loadRecords({ nextPage: records?.page || 1 })}>{recordsError}</LoadError>
        ) : recordsBusy && !records ? (
          <TableSkeleton rows={8} cols={7} />
        ) : !recordRows.length ? (
          <Empty
            title={recordFilters ? "No graduates found" : "No graduate records"}
            action={recordFilters ? (
              <button className="btn btn-outline" type="button" onClick={clearRecordFilters}>Clear filters</button>
            ) : (
              <button className="btn btn-outline" type="button" onClick={openAdd}>
                <PlusIcon size={16} />
                Add Graduate
              </button>
            )}
          >
            {recordFilters
              ? "No graduate records match this search."
              : "Import an Excel file from the Registrar's Office, or add one graduate at a time."}
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="data stack">
              <thead>
                <tr>
                  <th><SortButton column="student_number" sort={recordSort} onSort={(key) => setRecordSort((prev) => toggleSort(prev, key))}>Student Number</SortButton></th>
                  <th><SortButton column="first_name" sort={recordSort} onSort={(key) => setRecordSort((prev) => toggleSort(prev, key))}>First Name</SortButton></th>
                  <th><SortButton column="middle_name" sort={recordSort} onSort={(key) => setRecordSort((prev) => toggleSort(prev, key))}>Middle Name</SortButton></th>
                  <th><SortButton column="last_name" sort={recordSort} onSort={(key) => setRecordSort((prev) => toggleSort(prev, key))}>Last Name</SortButton></th>
                  <th><SortButton column="college" sort={recordSort} onSort={(key) => setRecordSort((prev) => toggleSort(prev, key))}>College</SortButton></th>
                  <th><SortButton column="course" sort={recordSort} onSort={(key) => setRecordSort((prev) => toggleSort(prev, key))}>Course</SortButton></th>
                  <th><SortButton column="course_code" sort={recordSort} onSort={(key) => setRecordSort((prev) => toggleSort(prev, key))}>Course Code</SortButton></th>
                </tr>
              </thead>
              <tbody>
                {recordRows.map((row) => (
                  <tr key={row.student_id}>
                    <td data-label="Student Number">{row.student_id}</td>
                    <td data-label="First Name">{row.first_name}</td>
                    <td data-label="Middle Name">{row.middle_name || "—"}</td>
                    <td data-label="Last Name">{row.last_name}</td>
                    <td data-label="College">{row.college || "—"}</td>
                    <td className="cell-title" data-label="Course">{row.degree || "—"}</td>
                    <td data-label="Course Code">{row.course_code || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {recordsError && records ? <Alert type="error">{recordsError}</Alert> : null}
        {!recordsBusy && records?.total ? (
          <Pager
            page={records.page}
            pageSize={records.page_size}
            total={records.total}
            onPage={(next) => loadRecords({ nextPage: next })}
          />
        ) : null}
      </Panel>

      {showImport ? (
        <Dialog
          title="Import Excel"
          description="No records are saved until you review the workbook and confirm the import."
          className="dialog-import"
          wide
          busy={working}
          onClose={() => { if (!working) setShowImport(false); }}
          hideActions
          footer={importResult ? (
            <>
              <button className="btn btn-outline" type="button" onClick={resetImport}>Import Another File</button>
              <button className="btn btn-navy" type="button" onClick={() => setShowImport(false)}>Close</button>
            </>
          ) : preview ? (
            <>
              <button className="btn btn-outline" type="button" onClick={() => { setPreview(null); setReasonRow(null); }} disabled={working}>Back</button>
              <button className="btn btn-navy" type="button" onClick={() => { setImportError(""); setConfirmOpen(true); }} disabled={working || !readyCount}>
                {`Import ${readyCount} Ready ${readyCount === 1 ? "Record" : "Records"}`}
              </button>
            </>
          ) : (
            <button className="btn btn-navy" type="button" onClick={reviewFile} disabled={working || !file}>
              {phase === "review" ? "Checking File…" : "Review File"}
            </button>
          )}
        >
          <div className="import-last" aria-live="polite">
            {lastImport?.imported_at ? (
              <>
                <div>
                  <span>Last successful import</span>
                  <strong>{lastImport.filename}</strong>
                </div>
                <time dateTime={lastImport.imported_at}>{formatManila(lastImport.imported_at)}</time>
              </>
            ) : (
              <p>No successful imports yet.</p>
            )}
          </div>
          <ol className="import-steps" aria-label="Import progress">
            {STEPS.map((step, index) => {
              const state = index === stepIndex ? "current" : index < stepIndex ? "completed" : "upcoming";
              return (
                <li key={step.title} className={index === stepIndex ? "is-current" : index < stepIndex ? "is-done" : ""} aria-current={index === stepIndex ? "step" : undefined}>
                  <span aria-hidden="true">{index < stepIndex ? "✓" : index + 1}</span>
                  {step.title}
                  <span className="sr-only">{state === "completed" ? ", completed" : state === "current" ? ", current step" : ", upcoming"}</span>
                </li>
              );
            })}
          </ol>

          {stepIndex === 3 && importResult ? (
            <section className="import-results" aria-live="polite">
              <h3>Import results</h3>
              <Alert type={importResult.summary?.imported ? "ok" : "warn"}>
                {importResult.summary?.imported
                  ? "Import completed. The eligible graduate records were added successfully. Existing graduate records were not changed."
                  : "No new graduate records were imported. Existing graduate records were not changed."}
              </Alert>
              <CountRow
                items={[
                  ["Imported", importResult.summary?.imported || 0],
                  ["Skipped", importResult.summary?.skipped || 0],
                  ["Invalid", importResult.summary?.invalid || 0],
                ]}
              />
              {importResult.issues?.length ? (
                <>
                  <PreviewTable
                    rows={importResult.issues.slice((issuePage - 1) * PREVIEW_PAGE_SIZE, issuePage * PREVIEW_PAGE_SIZE)}
                    catalog={catalog}
                    catalogReady={catalogReady}
                    onReason={setReasonRow}
                    caption="Rows that were skipped or invalid"
                  />
                  {importResult.issues.length > PREVIEW_PAGE_SIZE ? (
                    <Pager page={issuePage} pageSize={PREVIEW_PAGE_SIZE} total={importResult.issues.length} onPage={setIssuePage} />
                  ) : null}
                </>
              ) : (
                <p className="import-note">There are no skipped or invalid records to list.</p>
              )}
            </section>
          ) : null}

          {stepIndex < 3 && !preview ? (
            <section className="import-upload">
              <FileDrop
                compact
                className="import-file"
                mark="file"
                accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12"
                file={file}
                onChange={takeFile}
                validate={validateWorkbook}
                status="idle"
                disabled={working}
                label="Excel workbook"
                labelHidden
                prompt="Drag and drop your Excel workbook here, or browse your computer."
                browseLabel="Browse Files"
                readyLabel="Selected. Review the file before any records are imported."
              />
              <p className="import-limits">
                <span>Supported formats</span>
                <span>.xlsx</span>
                <span>.xlsm</span>
                <span>Maximum 10 MB</span>
              </p>
              {importError ? <Alert type="error">{importError}</Alert> : null}
              <details className="import-requirements">
                <summary>View Import Requirements</summary>
                <div className="import-requirement-grid">
                  <div>
                    <p>Required columns</p>
                    <ul className="import-cols">
                      <li>Student Number</li>
                      <li>First Name</li>
                      <li>Middle Name</li>
                      <li>Last Name</li>
                      <li>College</li>
                      <li>Course</li>
                      <li>Course Code</li>
                    </ul>
                  </div>
                  <div>
                    <p>Optional columns</p>
                    <ul className="import-cols">
                      <li>Email</li>
                      <li>Year Graduated</li>
                    </ul>
                  </div>
                </div>
                <ul className="import-requirement-notes">
                  <li>Header names may vary slightly. Supported aliases are recognized.</li>
                  <li>The system searches the first 20 rows of each worksheet for the header row.</li>
                  <li>Workbooks can contain up to 5,000 data rows.</li>
                  <li>Formula cells must be saved as values before uploading.</li>
                </ul>
              </details>
              {phase === "review" ? (
                <div className="import-progress" role="status" aria-live="polite">
                  <div className="import-progress-bar" aria-hidden="true"><span /></div>
                  <p>Checking the workbook. No records have been imported.</p>
                </div>
              ) : null}
            </section>
          ) : null}

          {preview && !importResult ? (
            <section className="import-preview">
              <h3>Import Preview</h3>
              <p className="lead">Review the validated records below. The college names, course names, and course codes shown are the values that will be saved. Nothing will be saved until you confirm the import.</p>
              <CountRow
                items={[
                  ["Ready", preview.summary?.ready || 0],
                  ["Skipped", preview.summary?.skipped || 0],
                  ["Invalid", preview.summary?.invalid || 0],
                ]}
              />
              {newCatalogCount ? (
                <p className="import-note">
                  {countPhrase(newCatalogCount, "ready record")} will add a college or course that is not in Colleges and Courses yet. Those entries are added only after a successful import.
                </p>
              ) : null}
              <form className="import-toolbar" onSubmit={(event) => event.preventDefault()}>
                <div className="search-field">
                  <SearchIcon size={16} />
                  <input
                    value={previewQuery}
                    onChange={(event) => {
                      setPreviewQuery(event.target.value);
                      setPreviewPage(1);
                    }}
                    placeholder="Search student number, name, college, or course"
                    aria-label="Search the import preview"
                  />
                </div>
                <select
                  aria-label="Filter preview by status"
                  value={previewStatus}
                  onChange={(event) => {
                    setPreviewStatus(event.target.value);
                    setPreviewPage(1);
                  }}
                >
                  <option value="all">All Statuses</option>
                  <option value="ready">Ready</option>
                  <option value="skipped">Skipped</option>
                  <option value="invalid">Invalid</option>
                </select>
              </form>
              {!previewSlice.length ? (
                <Empty
                  title="No preview rows"
                  action={filtersActive ? (
                    <button className="btn btn-outline" type="button" onClick={() => { setPreviewQuery(""); setPreviewStatus("all"); setPreviewPage(1); }}>
                      Clear filters
                    </button>
                  ) : null}
                >
                  No rows match this search or status. Validation results are unchanged.
                </Empty>
              ) : (
                <PreviewTable rows={previewSlice} catalog={catalog} catalogReady={catalogReady} onReason={setReasonRow} />
              )}
              {previewRows.length > PREVIEW_PAGE_SIZE ? (
                <Pager page={previewPage} pageSize={PREVIEW_PAGE_SIZE} total={previewRows.length} onPage={setPreviewPage} />
              ) : null}
              {!readyCount ? (
                <p className="lead">There are no ready records to import. Correct the invalid rows in the workbook, or upload a different file.</p>
              ) : null}
            </section>
          ) : null}
        </Dialog>
      ) : null}

      {confirmOpen && preview ? (
        <Dialog
          title="Confirm Import"
          description="Only Ready records will be imported. Existing graduate records will remain unchanged."
          confirmLabel="Confirm Import"
          busy={phase === "commit"}
          onConfirm={confirmImport}
          onClose={() => { if (phase !== "commit") setConfirmOpen(false); }}
        >
          <Alert type="error">{importError}</Alert>
          <p className="import-confirm-count"><strong>{readyCount}</strong> {readyCount === 1 ? "record will be added." : "records will be added."}</p>
          <ul className="import-confirm-list">
            <li>{countPhrase(preview.summary?.skipped || 0, "record")} will be skipped.</li>
            <li>{countPhrase(preview.summary?.invalid || 0, "record")} will be rejected.</li>
          </ul>
          {phase === "commit" ? <p className="import-note">Importing ready records. Existing graduate records stay unchanged.</p> : null}
        </Dialog>
      ) : null}

      {reasonRow ? (
        <Dialog
          title={reasonRow.status === "ready" ? "Catalog note" : `${STATUS_LABEL[reasonRow.status] || "Record"} reason`}
          description={reasonRow.student_number ? `Student number ${reasonRow.student_number}` : "This workbook row"}
          onClose={() => setReasonRow(null)}
          hideActions
          footer={<button className="btn btn-outline" type="button" onClick={() => setReasonRow(null)}>Close</button>}
        >
          <p>{rowReason(reasonRow, catalog, catalogReady) || "No additional detail is available for this row."}</p>
        </Dialog>
      ) : null}

      {showAdd ? (
        <Dialog title="Add Graduate" onClose={closeAdd} busy={saving} hideActions wide>
          <form className="graduate-form" onSubmit={create}>
            <p className="lead">Enter the official university record used to verify alumni registrations.</p>
            <h3>Graduate Information</h3>
            <div className="inline-fields">
              <Field label="Student ID" required>
                <input value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} required />
              </Field>
              <Field label="Year Graduated" required>
                <input value={form.year_graduated} onChange={(e) => setForm({ ...form, year_graduated: e.target.value })} required />
              </Field>
            </div>
            <div className="inline-fields">
              <Field label="Given Name" required>
                <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
              </Field>
              <Field label="Middle Name">
                <input value={form.middle_name} onChange={(e) => setForm({ ...form, middle_name: e.target.value })} />
              </Field>
            </div>
            <div className="inline-fields">
              <Field label="Last Name" required>
                <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
              </Field>
              <Field label="Personal Email" required>
                <input type="email" value={form.personal_email} onChange={(e) => setForm({ ...form, personal_email: e.target.value })} required />
              </Field>
            </div>
            <Field label="College" required>
              <select value={form.college} onChange={(e) => chooseFormCollege(e.target.value)} required>
                <option value="">Select a college</option>
                {catalog.colleges.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </Field>
            <Field label="Course" required>
              <select value={formPrograms.some((item) => item.course === form.degree) ? form.degree : ""} onChange={(e) => chooseFormCourse(e.target.value)} required disabled={!form.college}>
                <option value="">{form.college ? "Select a course" : "Select a college first"}</option>
                {formPrograms.map((item) => <option key={item.course} value={item.course}>{courseLabel(item)}</option>)}
              </select>
            </Field>
            <Field label="Course Code" hint={codeLocked ? <>Filled in from the selected course. Update the official code in <Link to="/admin/academics">Colleges and Courses</Link>.</> : "Filled in automatically when this course already has a code."}>
              <input
                value={form.course_code}
                onChange={(e) => setForm({ ...form, course_code: e.target.value })}
                readOnly={codeLocked}
                aria-readonly={codeLocked || undefined}
              />
            </Field>
            {!catalog.colleges.length ? (
              <p className="lead">Add colleges and courses in <Link to="/admin/academics">Colleges and Courses</Link>, or import a Registrar's Office list.</p>
            ) : null}
            <div className="dialog-actions">
              <button className="btn btn-outline" type="button" onClick={closeAdd} disabled={saving}>Cancel</button>
              <button className="btn btn-navy" disabled={saving}>{saving ? "Saving…" : "Save Graduate"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}

function CountRow({ items }) {
  return (
    <div className="import-counts">
      {items.map(([label, count]) => (
        <p key={label} className="import-count">
          <strong>{count}</strong>
          <span>{label}</span>
        </p>
      ))}
    </div>
  );
}

function PreviewTable({ rows, catalog, catalogReady, onReason, caption = "" }) {
  return (
    <div className="table-wrap">
      <table className="data stack">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr>
            <th>Student Number</th>
            <th>Graduate</th>
            <th>College</th>
            <th>Course</th>
            <th>Course Code</th>
            <th>Status</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const reason = rowReason(row, catalog, catalogReady);
            return (
              <tr key={`${row.row_number}-${row.student_number}-${row.status}`}>
                <td data-label="Student Number">{row.student_number || "—"}</td>
                <td data-label="Graduate">{graduateName(row)}</td>
                <td data-label="College">{row.college || "—"}</td>
                <td className="cell-title" data-label="Course">{row.course || "—"}</td>
                <td data-label="Course Code">{row.course_code || "—"}</td>
                <td data-label="Status">
                  <Badge tone={STATUS_TONE[row.status] || "info"}>{STATUS_LABEL[row.status] || row.status}</Badge>
                </td>
                <td data-label="Reason">
                  {reason ? (
                    <button
                      className="btn btn-outline btn-sm"
                      type="button"
                      onClick={() => onReason(row)}
                      aria-label={`View reason for ${row.student_number || "this row"}`}
                    >
                      View reason
                    </button>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
