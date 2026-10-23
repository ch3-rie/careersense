import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { SnapshotBackLink, StatusBadge } from "../../components/AdminOps";
import { openAdminTab } from "../../components/AdminReview";
import { ChevronRightIcon, SearchIcon } from "../../components/icons";
import { recordName, recordStudentNumber, RecordDossier } from "../../components/OfficialTracerRecord";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { Alert, Empty, Field, LoadError, Pager, PageSkeleton, ReviewSheet, SortButton, TableSkeleton, sortBy, toggleSort } from "../../components/ui";
import { courseLabel, programChoices } from "../../lib/academicFilters";
import { api } from "../../lib/api";
import { formatDate, formatLongDate, formatTime, questionLabelsFrom } from "../../lib/format";

export default function AdminRecords() {
  const [params] = useSearchParams();
  const from = params.get("from") || "";
  const [email, setEmail] = useState("");
  const [submittedOn, setSubmittedOn] = useState(params.get("submitted_on") || "");
  const [alignment, setAlignment] = useState(() => {
    const value = params.get("alignment") || "All";
    return ["All", "Aligned", "Misaligned", "Unknown"].includes(value) ? value : "All";
  });
  const [college, setCollege] = useState("");
  const [course, setCourse] = useState("");
  const [catalog, setCatalog] = useState({ colleges: [], courses: [], pairs: [] });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [labels, setLabels] = useState({});
  const [survey, setSurvey] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sort, setSort] = useState({ key: "submitted", dir: "desc" });

  async function load({
    nextEmail = email,
    nextAlignment = alignment,
    nextCollege = college,
    nextCourse = course,
    nextSubmitted = submittedOn,
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
      if (nextSubmitted) params.set("submitted_on", nextSubmitted);
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
    load({ nextPage: 1 });
    api("/api/auth/options")
      .then((opts) => {
        setLabels(questionLabelsFrom(opts.supplementary_questions));
        setSurvey(opts.survey || null);
      })
      .catch(() => {});
  }, []);

  const rows = sortBy(data?.items || [], sort, {
    name: (row) => recordName(row).toLowerCase(),
    student: (row) => recordStudentNumber(row).toLowerCase(),
    alignment: (row) => String(row.alignment || "").toLowerCase(),
    submitted: (row) => String(row.submitted_at || ""),
  });
  useEffect(() => {
    if (!openId) {
      setDetail(null);
      return undefined;
    }
    let cancelled = false;
    api(`/api/admin/tracer/${openId}`)
      .then((row) => {
        if (!cancelled) setDetail(row);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [openId]);

  const listed = rows.find((row) => row.id === openId) || data?.items?.find((row) => row.id === openId);
  const selected = detail && detail.id === openId ? detail : listed;
  const courseChoices = programChoices(catalog, college);
  const filtersActive = Boolean(email.trim() || college || course || alignment !== "All" || submittedOn);

  function chooseCollege(value) {
    const allowed = programChoices(catalog, value).map((item) => item.course);
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
    setSubmittedOn("");
    load({ nextEmail: "", nextAlignment: "All", nextCollege: "", nextCourse: "", nextSubmitted: "", nextPage: 1 });
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <SnapshotBackLink from={from} />
      <Alert type="error">{error && data ? error : null}</Alert>
      <Panel className="submitted-records" title="Submitted records" description={submittedOn ? `Submissions from ${submittedOn}.` : ""}>
        <form
          className="filter-bar"
          onSubmit={(event) => {
            event.preventDefault();
            load({ nextPage: 1 });
          }}
        >
          <Field label="Search">
            <div className="search-field">
              <SearchIcon size={16} />
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Name, student number, or email"
                aria-label="Search by name, student number, or email"
              />
            </div>
          </Field>
          <Field label="College">
            <select aria-label="Filter records by college" value={college} onChange={(e) => chooseCollege(e.target.value)}>
              <option value="">All Colleges</option>
              {catalog.colleges.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </Field>
          <Field label="Course">
            <select aria-label="Filter records by course" value={courseChoices.some((item) => item.course === course) ? course : ""} onChange={(e) => chooseCourse(e.target.value)}>
              <option value="">All Courses</option>
              {courseChoices.map((item) => <option key={`${item.college}-${item.course}`} value={item.course}>{courseLabel(item)}</option>)}
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
          <button className="btn btn-navy" disabled={busy} type="submit">Search</button>
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
                    <th><SortButton column="name" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Alumnus</SortButton></th>
                    <th><SortButton column="student" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Student number</SortButton></th>
                    <th><SortButton column="submitted" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Submitted date</SortButton></th>
                    <th>Submitted time</th>
                    <th><SortButton column="alignment" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Alignment</SortButton></th>
                    <th>View</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className={openId === row.id ? "is-open" : ""}>
                      <td className="cell-person" data-label="Alumnus">
                        <div className="record-person">
                          <strong>{recordName(row) || "—"}</strong>
                          <span>{row.email || "—"}</span>
                        </div>
                      </td>
                      <td data-label="Student number">{recordStudentNumber(row) || "—"}</td>
                      <td data-label="Submitted date">{formatDate(row.submitted_at)}</td>
                      <td data-label="Submitted time">{formatTime(row.submitted_at)}</td>
                      <td data-label="Alignment"><StatusBadge kind="alignment" value={row.alignment} /></td>
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
          title={recordName(selected) || "Tracer Record"}
          subtitle={selected.email}
          meta={`${recordStudentNumber(selected) || "No student number"} · ${formatLongDate(selected.submitted_at)} · ${formatTime(selected.submitted_at)}`}
          onClose={() => setOpenId(null)}
          onOpenTab={() => openAdminTab(`/admin/records/${selected.id}`)}
          wide
        >
          <RecordDossier record={selected} schema={survey} questionLabels={labels} surveyLayout />
        </ReviewSheet>
      ) : null}
    </PortalShell>
  );
}
