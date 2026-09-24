import { useEffect, useState } from "react";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { PlusIcon, SearchIcon } from "../../components/icons";
import { Alert, Dialog, Empty, Field, LoadError, Pager, SortButton, TableSkeleton, sortBy, toggleSort } from "../../components/ui";
import { coursesForCollege } from "../../lib/academicFilters";
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

export default function AdminRegistry() {
  const [q, setQ] = useState("");
  const [college, setCollege] = useState("");
  const [course, setCourse] = useState("");
  const [catalog, setCatalog] = useState({ colleges: [], courses: [], pairs: [] });
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sort, setSort] = useState({ key: "name", dir: "asc" });
  const [form, setForm] = useState(EMPTY_FORM);

  async function load({ term = q, nextCollege = college, nextCourse = course, nextPage = 1 } = {}) {
    setError("");
    setBusy(true);
    try {
      const params = new URLSearchParams({
        q: term,
        college: nextCollege,
        course: nextCourse,
        page: String(nextPage),
        page_size: "25",
      });
      const result = await api(`/api/admin/university-records?${params}`);
      setData(result);
      setPage(nextPage);
      return result;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api("/api/admin/academic-filters")
      .then((result) => setCatalog(result))
      .catch(() => {});
    load({ term: "", nextCollege: "", nextCourse: "", nextPage: 1 }).then((result) => {
      if (result && !result.items?.length) setShowAdd(true);
    });
  }, []);

  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  async function create(e) {
    e.preventDefault();
    setError("");
    setOk("");
    setSaving(true);
    try {
      await api("/api/admin/university-records", { method: "POST", body: form });
      setOk("Graduate record added successfully.");
      setForm(EMPTY_FORM);
      setShowAdd(false);
      setCollege("");
      setCourse("");
      setQ("");
      await load({ term: "", nextCollege: "", nextCourse: "", nextPage: 1 });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const rows = sortBy(data?.items || [], sort, {
    id: (row) => String(row.student_id || "").toLowerCase(),
    name: (row) => [row.last_name, row.first_name].filter(Boolean).join(" ").toLowerCase(),
    email: (row) => String(row.personal_email || "").toLowerCase(),
    year: (row) => String(row.year_graduated || ""),
  });
  const courseOptions = coursesForCollege(catalog, college);
  const filtersActive = Boolean(q.trim() || college || course);

  function chooseCollege(value) {
    const allowed = coursesForCollege(catalog, value);
    const nextCourse = allowed.includes(course) ? course : "";
    setCollege(value);
    setCourse(nextCourse);
    load({ nextCollege: value, nextCourse, nextPage: 1 });
  }

  function chooseCourse(value) {
    setCourse(value);
    load({ nextCourse: value, nextPage: 1 });
  }

  function clearFilters() {
    setQ("");
    setCollege("");
    setCourse("");
    load({ term: "", nextCollege: "", nextCourse: "", nextPage: 1 });
  }

  return (
    <PortalShell role="Admin">
      <Alert type="error">{error && !data ? null : error}</Alert>
      <Alert type="ok" title={ok ? "Graduate record added" : undefined}>{ok}</Alert>

      <Panel
        title="Official records"
        actions={
          <button className="btn btn-navy" type="button" onClick={() => setShowAdd(true)}>
            <PlusIcon size={16} />
            Add Graduate
          </button>
        }
      >
        <form
          className="filter-bar"
          onSubmit={(event) => {
            event.preventDefault();
            load({ nextPage: 1 });
          }}
        >
          <Field label="Search by student ID, name, or email">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by student ID, name, or email" />
          </Field>
          <Field label="College">
            <select aria-label="Filter records by college" value={college} onChange={(e) => chooseCollege(e.target.value)}>
              <option value="">All Colleges</option>
              {catalog.colleges.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </Field>
          <Field label="Course">
            <select aria-label="Filter records by course" value={courseOptions.includes(course) ? course : ""} onChange={(e) => chooseCourse(e.target.value)}>
              <option value="">All Courses</option>
              {courseOptions.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </Field>
          <button className="btn btn-navy" disabled={busy} type="submit">
            <SearchIcon size={16} />
            {busy ? "Searching…" : "Search"}
          </button>
          {filtersActive ? (
            <button className="btn btn-outline" type="button" onClick={clearFilters}>Clear Filters</button>
          ) : null}
        </form>
        {error && !data ? (
          <LoadError onRetry={() => load({ nextPage: page })}>{error}</LoadError>
        ) : busy ? (
          <TableSkeleton rows={8} cols={5} />
        ) : !rows.length ? (
          <Empty
            title={filtersActive ? "No records found" : "No records"}
            action={filtersActive ? <button className="btn btn-outline" type="button" onClick={clearFilters}>Clear Filters</button> : null}
          >
            {filtersActive
              ? "No university records match the selected college and course."
              : "Add a graduate so registrations can be matched to an official university record."}
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="data stack">
              <thead>
                <tr>
                  <th><SortButton column="id" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Student ID</SortButton></th>
                  <th><SortButton column="name" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Name</SortButton></th>
                  <th><SortButton column="email" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Email</SortButton></th>
                  <th>Degree</th>
                  <th><SortButton column="year" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Year</SortButton></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.student_id}>
                    <td data-label="Student ID">{row.student_id}</td>
                    <td data-label="Name">{[row.first_name, row.middle_name, row.last_name].filter(Boolean).join(" ")}</td>
                    <td className="cell-email" data-label="Email">{row.personal_email}</td>
                    <td className="cell-title" data-label="Degree">{row.degree}</td>
                    <td data-label="Year">{row.year_graduated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!busy && data?.total ? (
          <Pager
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPage={(next) => load({ nextPage: next })}
          />
        ) : null}
      </Panel>

      {showAdd ? (
        <Dialog title="Add Graduate" onClose={() => setShowAdd(false)} hideActions wide>
          <form onSubmit={create}>
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
            <Field label="Degree" required>
              <input value={form.degree} onChange={(e) => setForm({ ...form, degree: e.target.value })} required />
            </Field>
            <div className="inline-fields">
              <Field label="Course Code">
                <input value={form.course_code} onChange={(e) => setForm({ ...form, course_code: e.target.value })} />
              </Field>
              <Field label="College">
                <input value={form.college} onChange={(e) => setForm({ ...form, college: e.target.value })} />
              </Field>
            </div>
            <div className="dialog-actions">
              <button className="btn btn-outline" type="button" onClick={() => setShowAdd(false)}>Cancel</button>
              <button className="btn btn-navy" disabled={saving}>{saving ? "Saving…" : "Save Graduate"}</button>
            </div>
          </form>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
