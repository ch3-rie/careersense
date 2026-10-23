import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { QueueClear, SnapshotBackLink, StatusBadge } from "../../components/AdminOps";
import {
  ApprovalReviewContent,
  ApproveConfirmDialog,
  DecisionActions,
  RejectConfirmDialog,
  applicantName,
  isPendingRegistration,
  openAdminTab,
  useApprovalReview,
} from "../../components/AdminReview";
import { ChevronRightIcon, RefreshIcon, SearchIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import {
  Alert,
  Empty,
  Field,
  LoadError,
  Pager,
  PageSkeleton,
  ReviewSheet,
  SortButton,
  TableSkeleton,
} from "../../components/ui";
import { programChoices } from "../../lib/academicFilters";
import { formatLongDate } from "../../lib/format";
import { api } from "../../lib/api";

const DEFAULT_FILTERS = { college: "", course: "", year: "", status: "Active" };

const STATUS_CARDS = [
  ["Active", "Approved", "approved"],
  ["Pending", "Pending", "pending"],
  ["Rejected", "Rejected", "rejected"],
];

export default function AdminApprovals() {
  const location = useLocation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const from = params.get("from") || "";
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [catalog, setCatalog] = useState({ colleges: [], courses: [], pairs: [], programs: [] });
  const [openId, setOpenId] = useState(null);
  const [listError, setListError] = useState("");
  const [loadingList, setLoadingList] = useState(false);
  const [sort, setSort] = useState({ key: "name", dir: "asc" });
  const [flash, setFlash] = useState(location.state?.notice || "");
  const [flashTitle, setFlashTitle] = useState(location.state?.noticeTitle || "");
  const review = useApprovalReview(openId);

  async function load(nextPage = page, nextQuery = appliedQuery, nextSort = sort, nextFilters = filters) {
    setLoadingList(true);
    setListError("");
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: "8",
        q: nextQuery,
        college: nextFilters.college,
        course: nextFilters.course,
        year: nextFilters.year,
        status: nextFilters.status,
        sort_by: nextSort.key,
        sort_dir: nextSort.dir,
      });
      setData(await api(`/api/admin/approvals?${params}`));
    } catch (err) {
      setListError(err.message);
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    load(page, appliedQuery, sort, filters);
  }, [page, appliedQuery, sort, filters]);

  useEffect(() => {
    api("/api/admin/academic-filters").then(setCatalog).catch(() => {});
  }, []);

  useEffect(() => {
    if (!location.state?.notice) return;
    navigate(location.pathname, { replace: true, state: {} });
  }, []);

  useEffect(() => {
    if (!flash) return undefined;
    const timer = window.setTimeout(() => {
      setFlash("");
      setFlashTitle("");
    }, 4500);
    return () => window.clearTimeout(timer);
  }, [flash]);

  function changeSort(key) {
    setPage(1);
    setSort((prev) => (prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  }

  function chooseStatus(status) {
    setPage(1);
    setFilters((current) => ({ ...current, status }));
  }

  function chooseCollege(value) {
    const allowed = programChoices(catalog, value).map((item) => item.course);
    setPage(1);
    setFilters((current) => ({
      ...current,
      college: value,
      course: allowed.includes(current.course) ? current.course : "",
    }));
  }

  function clearFilters() {
    setQuery("");
    setAppliedQuery("");
    setPage(1);
    setFilters(DEFAULT_FILTERS);
  }

  async function handleApprove() {
    const ok = await review.approve();
    if (ok) {
      setOpenId(null);
      await load();
    }
  }

  async function handleReject() {
    const ok = await review.reject();
    if (ok) {
      setOpenId(null);
      await load();
    }
  }

  if (!data && !listError) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const rows = data?.items || [];
  const courseChoices = programChoices(catalog, filters.college);
  const filtersActive = Boolean(appliedQuery || filters.college || filters.course || filters.year);
  const years = data?.years || [];
  const summary = data?.summary || {};
  const name = applicantName(review.detail);
  const status = review.detail?.account?.status || "Pending";
  const pending = isPendingRegistration(review.detail);

  return (
    <PortalShell role="Admin">
      <SnapshotBackLink from={from} />
      <Alert type="error" title={listError || review.error ? "Unable to complete that action" : undefined}>
        {listError || review.error}
      </Alert>
      <Alert type="ok" title={review.okTitle || flashTitle || undefined}>
        {review.ok || flash}
      </Alert>

      <section className="card panel approval-queue" aria-busy={loadingList || undefined}>
        <header className="approval-intro">
          <div>
            <h2>Approval Queue</h2>
            <p>Review approved, pending, and rejected alumni registrations.</p>
          </div>
        </header>
        <div className="renewal-summary" role="group" aria-label="Registration summaries">
          {STATUS_CARDS.map(([value, label, key]) => (
            <button
              key={value}
              type="button"
              className={filters.status === value ? "is-active" : ""}
              aria-pressed={filters.status === value}
              onClick={() => chooseStatus(value)}
            >
              <span>{label}</span>
              <strong>{summary[key] || 0}</strong>
            </button>
          ))}
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
            <div className="search-field">
              <SearchIcon size={16} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by name, email, or student ID"
                aria-label="Search by name, email, or student ID"
              />
            </div>
          </Field>
          <Field label="College">
            <select aria-label="Filter by college" value={filters.college} onChange={(event) => chooseCollege(event.target.value)}>
              <option value="">All colleges</option>
              {(catalog.colleges || []).map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </Field>
          <Field label="Course">
            <select aria-label="Filter by course" value={courseChoices.some((item) => item.course === filters.course) ? filters.course : ""} onChange={(event) => { setPage(1); setFilters((current) => ({ ...current, course: event.target.value })); }}>
              <option value="">All courses</option>
              {courseChoices.map((item) => <option key={`${item.college}-${item.course}`} value={item.course}>{item.course}</option>)}
            </select>
          </Field>
          <Field label="Batch year">
            <select aria-label="Filter by batch year" value={filters.year} onChange={(event) => { setPage(1); setFilters((current) => ({ ...current, year: event.target.value })); }}>
              <option value="">All batch years</option>
              {years.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </Field>
          <button className="btn btn-navy" type="submit">Search</button>
          {filtersActive ? (
            <button className="btn btn-outline" type="button" onClick={clearFilters}>Clear filters</button>
          ) : null}
          <button className="btn btn-outline" type="button" onClick={() => load()}>
            <RefreshIcon size={16} />
            Refresh
          </button>
        </form>

        {listError && !data ? (
          <LoadError onRetry={() => load()} />
        ) : loadingList && !rows.length ? (
          <TableSkeleton rows={8} cols={5} />
        ) : !rows.length ? (
          filtersActive ? (
            <Empty title="No matching applicants">
              Try another name, college, course, or batch year.
            </Empty>
          ) : filters.status === "Pending" ? (
            <QueueClear />
          ) : (
            <Empty title={filters.status === "Rejected" ? "No rejected registrations" : "No approved registrations"}>
              {filters.status === "Rejected"
                ? "Rejected alumni accounts will appear here."
                : "Approved alumni accounts will appear here."}
            </Empty>
          )
        ) : (
          <>
            <div className="table-wrap">
              <table className="data stack">
                <thead>
                  <tr>
                    <th>
                      <SortButton column="name" sort={sort} onSort={changeSort}>Name</SortButton>
                    </th>
                    <th>
                      <SortButton column="email" sort={sort} onSort={changeSort}>Email</SortButton>
                    </th>
                    <th>Student ID</th>
                    <th>College</th>
                    <th>Course</th>
                    <th>Batch year</th>
                    <th>Account status</th>
                    <th>Review</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className={openId === row.id ? "is-open" : ""}>
                      <td className="cell-name" data-label="Name"><strong>{row.name || "—"}</strong></td>
                      <td className="cell-email" data-label="Email"><span>{row.email || "—"}</span></td>
                      <td className="cell-group" data-label="Student ID">{row.student_id ? <span>{row.student_id}</span> : <span className="id-unlinked">Unlinked</span>}</td>
                      <td className="cell-college" data-label="College"><span>{row.college || "—"}</span></td>
                      <td className="cell-title" data-label="Course"><span>{row.degree || "—"}</span></td>
                      <td data-label="Batch year"><span>{row.year_graduated || "—"}</span></td>
                      <td className="cell-group" data-label="Account status"><StatusBadge value={row.status || "Pending"} /></td>
                      <td className="cell-actions" data-label="Review">
                        <button className="btn btn-navy btn-sm" type="button" onClick={() => setOpenId(row.id)}>
                          Review
                          <ChevronRightIcon size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </section>

      {openId ? (
        <ReviewSheet
          title="Registration Review"
          subtitle={review.loading ? "Loading applicant…" : name}
          meta={
            review.detail ? (
              <>
                <StatusBadge value={status} />
                <span>Registered {formatLongDate(review.detail.account.created_at)}</span>
              </>
            ) : null
          }
          onClose={() => {
            review.reset();
            setOpenId(null);
          }}
          onOpenTab={() => openAdminTab(`/admin/approvals/${openId}`)}
          wide
          footer={
            review.detail && !review.loading && pending ? (
              <DecisionActions
                busy={review.busy}
                onApprove={review.requestApprove}
                onReject={review.requestReject}
              />
            ) : null
          }
        >
          {review.loading || !review.detail ? (
            <TableSkeleton rows={6} cols={2} />
          ) : (
            <ApprovalReviewContent
              key={review.detail.account.id}
              detail={review.detail}
              verify={review.verify}
              labels={review.labels}
              reviewTab={review.reviewTab}
              setReviewTab={review.setReviewTab}
              reason={review.reason}
              setReason={review.setReason}
              reasonError={review.reasonError}
              setReasonError={review.setReasonError}
              busy={review.busy}
              onApprove={review.requestApprove}
              onReject={review.requestReject}
              onDownloadResume={review.downloadResume}
            />
          )}
        </ReviewSheet>
      ) : null}

      {review.confirmApprove && review.detail ? (
        <ApproveConfirmDialog
          busy={review.busy}
          onConfirm={handleApprove}
          onClose={() => review.setConfirmApprove(false)}
        />
      ) : null}

      {review.confirmReject && review.detail ? (
        <RejectConfirmDialog
          reason={review.reason}
          setReason={review.setReason}
          reasonError={review.reasonError}
          setReasonError={review.setReasonError}
          busy={review.busy}
          onConfirm={handleReject}
          onClose={() => review.setConfirmReject(false)}
        />
      ) : null}
    </PortalShell>
  );
}

