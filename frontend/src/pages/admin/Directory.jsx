import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { SnapshotBackLink } from "../../components/AdminOps";
import { ChevronRightIcon, DownloadIcon, SearchIcon } from "../../components/icons";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { Alert, Empty, Field, LoadError, Pager, PageSkeleton, SortButton, TableSkeleton } from "../../components/ui";
import { api, downloadAuthorized } from "../../lib/api";

export default function AdminDirectory() {
  const [params] = useSearchParams();
  const cohort = params.get("cohort") || "all";
  const status = params.get("status") || "";
  const alignment = params.get("alignment") || "";
  const year = params.get("year") || "";
  const answer = params.get("answer") || "";
  const reason = params.get("reason") || "";
  const college = params.get("college") || "";
  const program = params.get("program") || "";
  const indicator = params.get("indicator") || "";
  const periodFrom = params.get("period_from") || "";
  const periodTo = params.get("period_to") || "";
  const location = params.get("location") || "";
  const employment = params.get("employment") || "";
  const award = params.get("award") || "";
  const further = params.get("further") || "";
  const from = params.get("from") || "";
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({ key: "name", dir: "asc" });
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState("");
  const [retry, setRetry] = useState(0);

  const filterKey = [cohort, status, alignment, year, answer, reason, college, program, indicator, periodFrom, periodTo, location, employment, award, further].join("|");

  useEffect(() => {
    setPage(1);
    setQuery("");
    setAppliedQuery("");
    setSort({ key: "name", dir: "asc" });
  }, [filterKey]);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError("");
    const search = new URLSearchParams({
      cohort,
      status,
      alignment,
      year,
      answer,
      reason,
      college,
      program,
      indicator,
      period_from: periodFrom,
      period_to: periodTo,
      location,
      employment,
      award,
      further,
      page: String(page),
      page_size: "12",
      q: appliedQuery,
      sort_by: sort.key,
      sort_dir: sort.dir,
    });
    api(`/api/admin/directory?${search}`)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cohort, status, alignment, year, answer, reason, college, program, indicator, periodFrom, periodTo, location, employment, award, further, page, appliedQuery, sort, retry]);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function downloadList(format) {
    setError("");
    setDownloading(format);
    try {
      const search = new URLSearchParams({
        format,
        cohort,
        status,
        alignment,
        year,
        answer,
        reason,
        college,
        program,
        indicator,
        period_from: periodFrom,
        period_to: periodTo,
        location,
        employment,
        award,
        further,
        q: appliedQuery,
        sort_by: sort.key,
        sort_dir: sort.dir,
      });
      const extension = format === "xlsx" ? "xlsx" : "csv";
      await downloadAuthorized(`/api/admin/directory/export?${search}`, `careersense-alumni-list.${extension}`);
      setNotice(format === "xlsx" ? "Excel list downloaded." : "CSV list downloaded.");
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading("");
    }
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const rows = data?.items || [];
  const snapshotTotal = data?.snapshot_total ?? 0;
  const searched = Boolean(appliedQuery);
  const countNote = searched
    ? `${data?.total ?? 0} of ${snapshotTotal} match this search.`
    : `${snapshotTotal} record${snapshotTotal === 1 ? "" : "s"}, matching this snapshot.`;

  function changeSort(key) {
    setPage(1);
    setSort((prev) => (prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  }

  return (
    <PortalShell role="Admin">
      <SnapshotBackLink from={from} />
      <Alert type="error">{error && data ? error : ""}</Alert>
      <Alert type="ok" title={notice || undefined} />
      <Panel title={data?.title || "Alumni"} description={data?.description || ""}>
        <div className="directory-toolbar">
          <p className="directory-count">{countNote}</p>
          <div className="directory-exports">
            <button className="btn btn-outline btn-sm" type="button" disabled={Boolean(downloading)} onClick={() => downloadList("xlsx")}>
              <DownloadIcon size={16} />
              {downloading === "xlsx" ? "Downloading…" : "Download Excel"}
            </button>
            <button className="btn btn-outline btn-sm" type="button" disabled={Boolean(downloading)} onClick={() => downloadList("csv")}>
              <DownloadIcon size={16} />
              {downloading === "csv" ? "Downloading…" : "Download CSV"}
            </button>
          </div>
        </div>
        <form
          className="filter-bar"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedQuery(query.trim());
          }}
        >
          <Field label="Search">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Name, student ID, course, or email"
            />
          </Field>
          <button className="btn btn-navy" type="submit" disabled={busy}>
            <SearchIcon size={16} />
            {busy ? "Searching…" : "Search"}
          </button>
          {searched ? (
            <button
              className="btn btn-outline"
              type="button"
              onClick={() => {
                setQuery("");
                setAppliedQuery("");
                setPage(1);
              }}
            >
              Clear search
            </button>
          ) : null}
        </form>
        {error && !data ? (
          <LoadError onRetry={() => setRetry((current) => current + 1)}>{error}</LoadError>
        ) : busy && !rows.length ? (
          <TableSkeleton rows={6} cols={6} />
        ) : !rows.length ? (
          <Empty title={searched ? "No matching alumni" : "No records in this snapshot"}>
            {searched ? "Try a different name, student ID, course, or email." : (data?.description || "There are no alumni in this snapshot yet.")}
          </Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data stack">
                <thead>
                  <tr>
                    <th><SortButton column="name" sort={sort} onSort={changeSort}>Name</SortButton></th>
                    <th><SortButton column="student_id" sort={sort} onSort={changeSort}>Student ID</SortButton></th>
                    <th><SortButton column="course" sort={sort} onSort={changeSort}>Course</SortButton></th>
                    <th><SortButton column="year_graduated" sort={sort} onSort={changeSort}>Batch year</SortButton></th>
                    <th><SortButton column="status" sort={sort} onSort={changeSort}>Account status</SortButton></th>
                    <th><SortButton column="employment_status" sort={sort} onSort={changeSort}>Employment</SortButton></th>
                    <th>Record</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.student_id || `${row.id}-${row.submission_id || "account"}`}>
                      <td className="cell-title" data-label="Name">{row.name || "—"}</td>
                      <td data-label="Student ID">{row.student_id || "—"}</td>
                      <td className="cell-title" data-label="Course">{row.course || "—"}</td>
                      <td data-label="Batch year">{row.year_graduated || "—"}</td>
                      <td data-label="Account status">{row.status || "—"}</td>
                      <td data-label="Employment">{row.employment_status || "—"}</td>
                      <td className="cell-actions" data-label="Record">
                        {row.submission_id ? (
                          <Link className="btn btn-outline btn-sm" to={`/admin/records/${row.submission_id}`}>
                            View
                            <ChevronRightIcon size={16} />
                          </Link>
                        ) : row.status === "Pending" ? (
                          <Link className="btn btn-outline btn-sm" to={`/admin/approvals/${row.id}`}>
                            Review
                            <ChevronRightIcon size={16} />
                          </Link>
                        ) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Panel>
    </PortalShell>
  );
}
