import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { QueueClear, StatusBadge } from "../../components/AdminOps";
import {
  ApprovalReviewContent,
  DecisionActions,
  applicantName,
  isPendingRegistration,
  openAdminTab,
  registrationStatusLabel,
  useApprovalReview,
} from "../../components/AdminReview";
import { ChevronRightIcon, RefreshIcon, SearchIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import {
  Alert,
  Dialog,
  Field,
  LoadError,
  Pager,
  PageSkeleton,
  ReviewSheet,
  SortButton,
  TableSkeleton,
} from "../../components/ui";
import { formatLongDate } from "../../lib/format";
import { api } from "../../lib/api";

export default function AdminApprovals() {
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [openId, setOpenId] = useState(null);
  const [listError, setListError] = useState("");
  const [loadingList, setLoadingList] = useState(false);
  const [sort, setSort] = useState({ key: "name", dir: "asc" });
  const [flash, setFlash] = useState(location.state?.notice || "");
  const [flashTitle, setFlashTitle] = useState(location.state?.noticeTitle || "");
  const review = useApprovalReview(openId);

  async function load(nextPage = page, nextQuery = appliedQuery, nextSort = sort) {
    setLoadingList(true);
    setListError("");
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: "8",
        q: nextQuery,
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
    load(page, appliedQuery, sort);
  }, [page, appliedQuery, sort]);

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

  const waiting = data?.total || 0;
  const rows = data?.items || [];
  const name = applicantName(review.detail);
  const status = review.detail?.account?.status || "Pending";
  const pending = isPendingRegistration(review.detail);

  return (
    <PortalShell role="Admin">
      <Alert type="error" title={listError || review.error ? "Unable to complete that action" : undefined}>
        {listError || review.error}
      </Alert>
      <Alert type="ok" title={review.okTitle || flashTitle || undefined}>
        {review.ok || flash}
      </Alert>

      <section className="card panel">
        <div className="queue-bar">
          <div>
            <h2>{waiting} pending registration{waiting === 1 ? "" : "s"}</h2>
          </div>
          <form
            className="filter-bar"
            onSubmit={(event) => {
              event.preventDefault();
              setPage(1);
              setAppliedQuery(query.trim());
            }}
          >
            <FieldSearch value={query} onChange={setQuery} />
            <button className="btn btn-navy" type="submit">
              <SearchIcon size={16} />
              Search
            </button>
            <button className="btn btn-outline" type="button" onClick={() => load()}>
              <RefreshIcon size={16} />
              Refresh
            </button>
          </form>
        </div>

        {listError && !data ? (
          <LoadError onRetry={() => load()} />
        ) : loadingList && !rows.length ? (
          <TableSkeleton rows={8} cols={5} />
        ) : !rows.length ? (
          <QueueClear />
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
                    <th>Tracer</th>
                    <th>Review</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className={openId === row.id ? "is-open" : ""}>
                      <td data-label="Name">{row.name}</td>
                      <td className="cell-email" data-label="Email">{row.email}</td>
                      <td data-label="Student ID">{row.student_id || <strong>Unlinked</strong>}</td>
                      <td data-label="Tracer"><StatusBadge kind="tracer" value={row.has_submission} /></td>
                      <td className="cell-actions">
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
          title="Review Registration"
          subtitle={review.loading ? "Loading applicant…" : name}
          meta={
            review.detail
              ? `${registrationStatusLabel(status)} · Registered ${formatLongDate(review.detail.account.created_at)}`
              : null
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
          {review.loading ? (
            <TableSkeleton rows={6} cols={2} />
          ) : (
            <ApprovalReviewContent
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
        <Dialog
          title="Approve this registration?"
          confirmLabel="Approve"
          busy={review.busy}
          onConfirm={handleApprove}
          onClose={() => review.setConfirmApprove(false)}
        >
          <p>
            Approving this registration will activate the alumni account and mark the graduate as verified.
            They will be able to access the Alumni Portal.
          </p>
        </Dialog>
      ) : null}

      {review.confirmReject && review.detail ? (
        <Dialog
          title="Reject this registration?"
          confirmLabel="Reject"
          danger
          busy={review.busy}
          onConfirm={handleReject}
          onClose={() => review.setConfirmReject(false)}
        >
          <p>The applicant will remain unable to access the alumni portal and will see this reason.</p>
          <Field label="Reason for Rejection" required error={review.reasonError}>
            <textarea
              id="rejection-reason-dialog"
              value={review.reason}
              onChange={(e) => {
                review.setReason(e.target.value);
                if (e.target.value.trim().length >= 3) review.setReasonError("");
              }}
              placeholder="Explain why this registration cannot be approved."
            />
          </Field>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}

function FieldSearch({ value, onChange }) {
  return (
    <div className="field">
      <label htmlFor="approval-search">Search</label>
      <input
        id="approval-search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search by name, email, or student ID"
      />
    </div>
  );
}
