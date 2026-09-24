import { useEffect, useState } from "react";
import { StatusBadge } from "../../components/AdminOps";
import { alignmentLabel, openAdminTab, TracerDetailView } from "../../components/AdminReview";
import { ChevronRightIcon, SearchIcon } from "../../components/icons";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { Alert, Empty, Field, LoadError, Pager, PageSkeleton, ReviewSheet, SortButton, TableSkeleton, sortBy, toggleSort } from "../../components/ui";
import { coursesForCollege } from "../../lib/academicFilters";
import { api } from "../../lib/api";
import { formatDate, formatLongDate, questionLabelsFrom } from "../../lib/format";

export default function AdminRecords() {
  const [email, setEmail] = useState("");
  const [alignment, setAlignment] = useState("All");
  const [college, setCollege] = useState("");
  const [course, setCourse] = useState("");
  const [catalog, setCatalog] = useState({ colleges: [], courses: [], pairs: [] });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [error, setError] = useState("");
  const [labels, setLabels] = useState({});
  const [busy, setBusy] = useState(false);
  const [sort, setSort] = useState({ key: "submitted", dir: "desc" });

  async function load({
    nextEmail = email,
    nextAlignment = alignment,
    nextCollege = college,
    nextCourse = course,
    nextPage = 1,
  } = {}) {
    setBusy(true);
    setError("");
    try {
      const params = new URLSearchParams({
        email: nextEmail,
        alignment: nextAlignment,
        college: nextCollege,
        course: nextCourse,
        page: String(nextPage),
        page_size: "12",
      });
      setData(await api(`/api/admin/tracer?${params}`));
      setPage(nextPage);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api("/api/admin/academic-filters")
      .then((result) => setCatalog(result))
      .catch(() => {});
    load({ nextEmail: "", nextAlignment: "All", nextCollege: "", nextCourse: "", nextPage: 1 });
    api("/api/auth/options")
      .then((opts) => setLabels(questionLabelsFrom(opts.supplementary_questions)))
      .catch(() => {});
  }, []);

  const rows = sortBy(data?.items || [], sort, {
    email: (row) => String(row.email || "").toLowerCase(),
    job: (row) => String(row.job_title || "").toLowerCase(),
    alignment: (row) => String(row.alignment || "").toLowerCase(),
    submitted: (row) => String(row.submitted_at || ""),
  });
  const selected = rows.find((row) => row.id === openId) || data?.items?.find((row) => row.id === openId);
  const courseOptions = coursesForCollege(catalog, college);
  const filtersActive = Boolean(email.trim() || college || course || alignment !== "All");

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

  function chooseAlignment(value) {
    setAlignment(value);
    load({ nextAlignment: value, nextPage: 1 });
  }

  function clearFilters() {
    setEmail("");
    setAlignment("All");
    setCollege("");
    setCourse("");
    load({ nextEmail: "", nextAlignment: "All", nextCollege: "", nextCourse: "", nextPage: 1 });
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <Alert type="error">{error && data ? error : null}</Alert>
      <Panel title="Submitted records">
        <form
          className="filter-bar"
          onSubmit={(event) => {
            event.preventDefault();
            load({ nextPage: 1 });
          }}
        >
          <Field label="Search email">
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Search email" />
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
          <Field label="Alignment">
            <select aria-label="Filter records by alignment" value={alignment} onChange={(e) => chooseAlignment(e.target.value)}>
              <option>All</option>
              <option>Aligned</option>
              <option>Misaligned</option>
              <option>Unknown</option>
            </select>
          </Field>
          <button className="btn btn-navy" disabled={busy} type="submit">
            <SearchIcon size={16} />
            {busy ? "Searching…" : "Apply Filters"}
          </button>
          {filtersActive ? (
            <button className="btn btn-outline" type="button" onClick={clearFilters}>Clear Filters</button>
          ) : null}
        </form>
        {error && !data ? (
          <LoadError title="Unable to load records" onRetry={() => load({ nextPage: page })}>
            We couldn't retrieve the filtered records. Please try again.
          </LoadError>
        ) : busy ? (
          <TableSkeleton rows={6} cols={6} />
        ) : !data?.items?.length ? (
          <Empty
            title="No tracer records found"
            action={filtersActive ? <button className="btn btn-outline" type="button" onClick={clearFilters}>Clear Filters</button> : null}
          >
            {filtersActive ? "Try changing or clearing your filters." : "Submitted tracer records will appear here."}
          </Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data stack">
                <thead>
                  <tr>
                    <th><SortButton column="email" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Email</SortButton></th>
                    <th><SortButton column="job" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Job Title</SortButton></th>
                    <th>Employer</th>
                    <th><SortButton column="alignment" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Alignment</SortButton></th>
                    <th><SortButton column="submitted" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Submitted</SortButton></th>
                    <th>View</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className={openId === row.id ? "is-open" : ""}>
                      <td className="cell-email" data-label="Email">{row.email}</td>
                      <td className="cell-title" data-label="Job Title">{row.job_title || "—"}</td>
                      <td className="cell-title" data-label="Employer">{row.employer || "—"}</td>
                      <td data-label="Alignment"><StatusBadge kind="alignment" value={row.alignment} /></td>
                      <td data-label="Submitted">{formatDate(row.submitted_at)}</td>
                      <td className="cell-actions">
                        <button className="btn btn-outline btn-sm" type="button" onClick={() => setOpenId(row.id)}>
                          View
                          <ChevronRightIcon size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={(next) => load({ nextPage: next })} />
          </>
        )}
      </Panel>

      {selected ? (
        <ReviewSheet
          title="Tracer Record"
          subtitle={selected.email}
          meta={`Submitted: ${formatLongDate(selected.submitted_at)} · Alignment: ${alignmentLabel(selected.alignment)}`}
          onClose={() => setOpenId(null)}
          onOpenTab={() => openAdminTab(`/admin/records/${selected.id}`)}
          wide
        >
          <TracerDetailView record={selected} questionLabels={labels} compact hideEmail />
        </ReviewSheet>
      ) : null}
    </PortalShell>
  );
}
