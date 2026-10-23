import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { SnapshotBackLink } from "../../components/AdminOps";
import { DateField } from "../../components/DateField";
import { SearchIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import {
  Alert,
  Badge,
  Dialog,
  Empty,
  Field,
  LoadError,
  Pager,
  PageSkeleton,
} from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate, formatDateTime } from "../../lib/format";

const STATUS_VIEW = {
  ForVerification: { label: "Renewal Requested", tone: "for-verification" },
  Approved: { label: "Approved for printing", tone: "info" },
  ReadyForPickup: { label: "Printed", tone: "info" },
  Claimed: { label: "Claimed", tone: "claimed" },
  ForRenewal: { label: "For renewal", tone: "for-renewal" },
  NotYetApplied: { label: "Not yet applied", tone: "pending" },
  Undefined: { label: "Undefined", tone: "undefined" },
};

const ACTION_LABELS = {
  Approved: "Approve for printing",
  ReadyForPickup: "Mark as Printed",
  Claimed: "Mark as Claimed",
  ForRenewal: "Mark for renewal",
  ForVerification: "Mark as Requesting",
  NotYetApplied: "Return application",
};

const ACTION_COPY = {
  Approved: "This approves the renewal so the card can be printed. It does not mark the card as printed or claimed, and it does not start the four-year countdown.",
  ReadyForPickup: "This records that OAAPS has printed the card. Printing does not mark the card as claimed and does not start the four-year countdown.",
  Claimed: "This records that the alumnus received the card. The claiming date below starts the next four-year renewal cycle. The printing date and today’s entry date are not used.",
  ForRenewal: "This marks the card as due for renewal. It does not create a new renewal request, mark the card as printed, or change the claiming date.",
  ForVerification: "This records that the alumnus requested a renewal. It does not approve the card for printing or mark it as printed or claimed.",
  NotYetApplied: "This returns the application to the alumnus. It does not mark the card as printed or claimed.",
};

function todayIso() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function statusView(status) {
  return STATUS_VIEW[status] || { label: status || "Undefined", tone: "unknown" };
}

function idTone(status) {
  return status === "Defined" ? "defined" : "undefined";
}

function eligibilityTone(code) {
  if (code === "due") return "due";
  if (code === "not_yet") return "not-yet";
  return "undefined";
}

function showDate(value, dateOnly = false) {
  if (!value) return "—";
  return dateOnly ? formatDate(value) : formatDateTime(value);
}

export default function AdminCards() {
  const [params] = useSearchParams();
  const from = params.get("from") || "";
  const [data, setData] = useState(null);
  const [colleges, setColleges] = useState([]);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [college, setCollege] = useState("");
  const [year, setYear] = useState("");
  const [queue, setQueue] = useState("claimed");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [pending, setPending] = useState(null);
  const [claimedOn, setClaimedOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const extraFilters = Boolean(appliedQuery || college || year);
  const showReset = extraFilters;

  async function load(nextPage = page, next = {}) {
    const nextQuery = next.query ?? appliedQuery;
    const nextCollege = next.college ?? college;
    const nextYear = next.year ?? year;
    const nextQueue = next.queue ?? queue;
    setLoading(true);
    setError("");
    try {
      const search = new URLSearchParams({
        page: String(nextPage),
        page_size: "8",
        q: nextQuery,
        sort_by: "submitted",
        sort_dir: "desc",
        scope: "renewal",
        college: nextCollege,
        year: nextYear,
        queue: nextQueue,
      });
      setData(await api(`/api/admin/cards?${search}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(page);
  }, [page, appliedQuery, college, year, queue]);

  useEffect(() => {
    api("/api/admin/academic-filters")
      .then((result) => setColleges(result.colleges || []))
      .catch(() => setColleges([]));
  }, []);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function resetFilters() {
    setQuery("");
    setAppliedQuery("");
    setCollege("");
    setYear("");
    setQueue("claimed");
    setPage(1);
  }

  function chooseSummary(nextQueue) {
    setPage(1);
    setQueue(nextQueue);
  }

  async function openDetail(id) {
    setError("");
    try {
      setSelected(await api(`/api/admin/cards/${id}`));
      setNote("");
    } catch (err) {
      setError(err.message);
    }
  }

  function askStatus(id, status) {
    setError("");
    setClaimedOn(status === "Claimed" ? todayIso() : "");
    setPending({ id, status });
  }

  async function applyStatus() {
    if (!pending) return;
    if (pending.status === "Claimed" && !claimedOn) {
      setError("Enter the date the alumnus actually claimed the card.");
      return;
    }
    if (pending.status === "Claimed" && claimedOn > todayIso()) {
      setError("The claiming date cannot be in the future.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api(`/api/admin/cards/${pending.id}/status`, {
        method: "POST",
        body: {
          status: pending.status,
          note,
          ...(pending.status === "Claimed" ? { claimed_on: claimedOn } : {}),
        },
      });
      setNotice(result.already_processed ? "This card is already in that status." : "Alumni card status updated.");
      setPending(null);
      setSelected(null);
      await load(page);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const items = data?.items || [];
  const summary = data?.summary || { claimed: 0, renewal: 0, requesting: 0, printing: 0, printed: 0, undefined: 0 };
  const years = data?.years || [];
  const renewal = selected?.renewal || {};
  const account = selected?.account || {};
  const card = selected?.card || {};
  const currentView = statusView(renewal.display_status || card.status);
  const statusKnown = currentView.label !== "Undefined";

  return (
    <PortalShell role="Admin">
      <SnapshotBackLink from={from} />
      <Alert type="success" title={notice ? "Updated" : ""}>{notice}</Alert>
      {error && !selected ? <LoadError onRetry={() => load()}>{error}</LoadError> : null}

      <section className="card panel renewal-page" aria-label="Alumni card renewals">
        <header className="panel-head">
          <div>
            <h2>Alumni Card</h2>
            <p className="lead">Manage alumni card renewal requests, printing, and claiming.</p>
          </div>
        </header>
        <p className="renewal-notice">This page is for alumni card renewals only. New alumni card issuance is handled separately.</p>

        <div className="renewal-summary" role="group" aria-label="Renewal summaries">
          <button type="button" className={queue === "claimed" ? "is-active" : ""} aria-pressed={queue === "claimed"} onClick={() => chooseSummary("claimed")}>
            <span>Claimed</span>
            <strong>{summary.claimed || 0}</strong>
          </button>
          <button type="button" className={queue === "renewal" ? "is-active" : ""} aria-pressed={queue === "renewal"} onClick={() => chooseSummary("renewal")}>
            <span>For Renewal</span>
            <strong>{summary.renewal || 0}</strong>
          </button>
          <button type="button" className={queue === "requesting" ? "is-active" : ""} aria-pressed={queue === "requesting"} onClick={() => chooseSummary("requesting")}>
            <span>Requesting</span>
            <strong>{summary.requesting || 0}</strong>
          </button>
          <button type="button" className={queue === "printing" ? "is-active" : ""} aria-pressed={queue === "printing"} onClick={() => chooseSummary("printing")}>
            <span>For Printing</span>
            <strong>{summary.printing || 0}</strong>
          </button>
          <button type="button" className={queue === "printed" ? "is-active" : ""} aria-pressed={queue === "printed"} onClick={() => chooseSummary("printed")}>
            <span>Printed</span>
            <strong>{summary.printed || 0}</strong>
          </button>
          <button type="button" className={queue === "undefined" ? "is-active" : ""} aria-pressed={queue === "undefined"} onClick={() => chooseSummary("undefined")}>
            <span>Undefined</span>
            <strong>{summary.undefined || 0}</strong>
          </button>
        </div>

        <form
          className="renewal-toolbar"
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
                placeholder="Search by alumni name or student number…"
                aria-label="Search by alumni name or student number"
              />
            </div>
          </Field>
          <Field label="College">
            <select aria-label="College" value={college} onChange={(event) => { setCollege(event.target.value); setPage(1); }}>
              <option value="">All Colleges</option>
              {colleges.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </Field>
          <Field label="Batch Year">
            <select aria-label="Batch Year" value={year} onChange={(event) => { setYear(event.target.value); setPage(1); }}>
              <option value="">All years</option>
              {years.map((item) => <option key={item} value={item}>{item}</option>)}
              {year && !years.includes(year) ? <option value={year}>{year}</option> : null}
            </select>
          </Field>
          <button className="btn btn-navy" type="submit">Search</button>
          {showReset ? <button className="btn btn-outline" type="button" onClick={resetFilters}>Reset</button> : null}
        </form>

        {loading && !items.length ? <PageSkeleton /> : null}
        {!loading && !items.length ? (
          <Empty
            title="No renewal requests found."
            action={showReset ? <button className="btn btn-outline" type="button" onClick={resetFilters}>Clear Filters</button> : null}
          >
            {extraFilters || queue !== "claimed"
              ? "No renewal requests match the current search and filters."
              : "Claimed cards will appear here after an alumnus receives a renewed card."}
          </Empty>
        ) : null}
        {items.length ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Alumni</th>
                  <th>College / Course</th>
                  <th>Card Status</th>
                  <th>Batch Year</th>
                  <th>Next Renewal</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const view = statusView(row.display_status || row.status);
                  return (
                    <tr key={row.id}>
                      <td data-label="Alumni">
                        <strong>{row.name}</strong>
                        <div className="muted">{row.student_id || "No student number"}</div>
                      </td>
                      <td data-label="College / Course">
                        <div>{row.college || "—"}</div>
                        <div className="muted">{row.course || "—"}</div>
                      </td>
                      <td data-label="Card Status">
                        <Badge tone={view.tone}>{view.label}</Badge>
                      </td>
                      <td data-label="Batch Year">{row.year_graduated || "—"}</td>
                      <td data-label="Next Renewal">{row.next_renewal_on ? formatDate(row.next_renewal_on) : "—"}</td>
                      <td className="cell-actions" data-label="Action">
                        <button className="btn btn-outline btn-sm" type="button" onClick={() => openDetail(row.id)}>View details</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
        {data?.total ? <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} /> : null}
      </section>

      {selected ? (
        <Dialog
          title="Renewal details"
          wide
          onClose={() => { if (!busy) setSelected(null); }}
          hideActions
          footer={(
            <>
              {(selected.actions || []).map((next) => (
                <button
                  key={next}
                  className="btn btn-navy"
                  type="button"
                  disabled={busy}
                  onClick={() => askStatus(account.id, next)}
                >
                  {ACTION_LABELS[next] || next}
                </button>
              ))}
              <button className="btn btn-outline" type="button" onClick={() => setSelected(null)} disabled={busy}>Close</button>
            </>
          )}
        >
          {error ? <Alert type="error">{error}</Alert> : null}
          <section className="renewal-detail">
            <h3>Alumni</h3>
            <dl className="deflist">
              <div className="deflist-row"><dt>Name</dt><dd>{account.name}</dd></div>
              <div className="deflist-row"><dt>Student number</dt><dd>{account.student_id || "—"}</dd></div>
              <div className="deflist-row"><dt>College</dt><dd>{account.college || "—"}</dd></div>
              <div className="deflist-row"><dt>Course</dt><dd>{account.course || account.degree || "—"}</dd></div>
              <div className="deflist-row"><dt>Batch year</dt><dd>{account.year_graduated || "—"}</dd></div>
              <div className="deflist-row"><dt>ID status</dt><dd><Badge tone={idTone(renewal.id_status)}>{renewal.id_status || "Undefined"}</Badge></dd></div>
            </dl>
          </section>
          <section className="renewal-detail">
            <h3>Renewal eligibility</h3>
            <dl className="deflist">
              <div className="deflist-row"><dt>Eligibility</dt><dd><Badge tone={eligibilityTone(renewal.eligibility)}>{renewal.eligibility_label || "Not determined"}</Badge></dd></div>
              <div className="deflist-row"><dt>Next renewal date</dt><dd>{renewal.next_renewal_on ? formatDate(renewal.next_renewal_on) : "Not calculated"}</dd></div>
            </dl>
            <p className="renewal-note">{renewal.eligibility_note || renewal.id_note}</p>
          </section>
          <section className="renewal-detail">
            <h3>Card renewal</h3>
            <dl className="deflist">
              <div className="deflist-row"><dt>Renewal status</dt><dd><Badge tone={currentView.tone}>{currentView.label}</Badge></dd></div>
              {statusKnown && renewal.requested_at ? <div className="deflist-row"><dt>Request date</dt><dd>{showDate(renewal.requested_at)}</dd></div> : null}
              {statusKnown && renewal.printed_at ? <div className="deflist-row"><dt>Printing date</dt><dd>{showDate(renewal.printed_at)}</dd></div> : null}
              {statusKnown && (renewal.claimed_at || renewal.claiming_date) ? (
                <div className="deflist-row"><dt>Claiming date</dt><dd>{renewal.claimed_at ? showDate(renewal.claimed_at) : formatDate(renewal.claiming_date)}</dd></div>
              ) : null}
            </dl>
            {statusKnown ? null : (
              <p className="renewal-note">No card update is on file for this previous batch, so the status stays undefined. Choose the step the office has verified.</p>
            )}
          </section>
          <Field label="Optional note for the alumnus">
            <textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={400} rows={3} />
          </Field>
        </Dialog>
      ) : null}

      {pending ? (
        <Dialog
          title={`${ACTION_LABELS[pending.status] || "Update status"}?`}
          confirmLabel={busy ? "Saving…" : (ACTION_LABELS[pending.status] || "Update")}
          busy={busy}
          danger={pending.status === "NotYetApplied"}
          onConfirm={applyStatus}
          onClose={() => { if (!busy) setPending(null); }}
        >
          {error ? <Alert type="error">{error}</Alert> : null}
          <p>{ACTION_COPY[pending.status] || "This updates the stored alumni card status."}</p>
          {pending.status === "Claimed" ? (
            <Field label="Claiming date" required>
              <DateField
                value={claimedOn}
                max={todayIso()}
                onChange={(event) => setClaimedOn(event.target.value)}
                aria-label="Claiming date"
              />
            </Field>
          ) : null}
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
