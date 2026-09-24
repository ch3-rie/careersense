import { useEffect, useRef, useState } from "react";
import { MonthCalendar, dateFromIso, formatCalendarDate, isoFromDate } from "../../components/AacCalendar";
import { CreditCardIcon, RefreshIcon, SearchIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import {
  Alert,
  Badge,
  Dialog,
  Field,
  LoadError,
  Pager,
  PageSkeleton,
} from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

const FILTERS = [
  { id: "", label: "All" },
  { id: "ForVerification", label: "For verification" },
  { id: "Approved", label: "Approved" },
  { id: "ReadyForPickup", label: "Ready for pickup" },
  { id: "Claimed", label: "Claimed" },
  { id: "ForRenewal", label: "For renewal" },
];

const ACTION_LABELS = {
  Approved: "Approve application",
  ReadyForPickup: "Mark ready for pickup",
  Claimed: "Mark claimed",
  ForRenewal: "Mark for renewal",
  NotYetApplied: "Return application",
};

export default function AdminCards() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [status, setStatus] = useState("ForVerification");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [slots, setSlots] = useState([]);
  const [calMonth, setCalMonth] = useState(() => new Date());
  const [selectedDate, setSelectedDate] = useState("");
  const [slotTime, setSlotTime] = useState("09:00");
  const [slotCapacity, setSlotCapacity] = useState("8");
  const scheduleReady = useRef(false);

  async function loadSlots() {
    const body = await api("/api/admin/cards/slots");
    const next = body.slots || [];
    setSlots(next);
    if (!scheduleReady.current) {
      scheduleReady.current = true;
      const first = next[0]?.date || isoFromDate(new Date());
      setSelectedDate(first);
      const parsed = dateFromIso(first);
      if (parsed) setCalMonth(parsed);
    }
  }

  async function load(nextPage = page, nextQuery = appliedQuery, nextStatus = status) {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: "8",
        q: nextQuery,
        status: nextStatus,
        sort_by: "submitted",
        sort_dir: "desc",
      });
      setData(await api(`/api/admin/cards?${params}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(page, appliedQuery, status);
  }, [page, appliedQuery, status]);

  useEffect(() => {
    loadSlots().catch(() => setSlots([]));
  }, []);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function openDetail(id) {
    setError("");
    try {
      setSelected(await api(`/api/admin/cards/${id}`));
      setNote("");
    } catch (err) {
      setError(err.message);
    }
  }

  async function applyStatus() {
    if (!pending || !selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await api(`/api/admin/cards/${selected.account.id}/status`, {
        method: "POST",
        body: { status: pending, note },
      });
      setNotice(result.already_processed ? "This card is already in that status." : "Alumni card status updated.");
      setPending(null);
      setSelected(null);
      await load(page, appliedQuery, status);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const items = data?.items || [];
  const counts = data?.counts || {};
  const todayIso = isoFromDate(new Date());
  const slotMarks = slots.reduce((marks, slot) => {
    const current = marks[slot.date] || { count: 0 };
    const count = current.count + 1;
    marks[slot.date] = {
      count,
      text: String(count),
      label: `${count} time${count === 1 ? "" : "s"}`,
    };
    return marks;
  }, {});
  const daySlots = slots.filter((slot) => slot.date === selectedDate);

  return (
    <PortalShell role="Admin">
      <Alert type="success" title={notice ? "Updated" : ""}>{notice}</Alert>
      {error ? <LoadError onRetry={() => load()}>{error}</LoadError> : null}

      <section className="card panel" aria-label="AAC appointment schedule">
        <h2>Appointment schedule</h2>
        <p className="muted">Choose a date on the calendar, then add or remove the times alumni can book. A full slot disappears from the application.</p>
        <div className="aac-cal-layout">
          <MonthCalendar
            month={calMonth}
            onMonth={setCalMonth}
            selected={selectedDate}
            onSelect={setSelectedDate}
            marks={slotMarks}
            isSelectable={(iso) => iso >= todayIso}
            ariaLabel="AAC appointment schedule"
          />
          <div className="aac-day-panel">
            <h3>{selectedDate ? formatCalendarDate(selectedDate) : "Select a date"}</h3>
            {daySlots.length ? (
              <ul className="aac-slot-list">
                {daySlots.map((slot) => (
                  <li key={slot.id}>
                    <span>{slot.time} · {slot.booked}/{slot.capacity} booked</span>
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={async () => {
                        await api(`/api/admin/cards/slots/${slot.id}`, { method: "DELETE" });
                        await loadSlots();
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted aac-day-placeholder">No times on this date yet.</p>
            )}
            <form
              className="aac-slot-form"
              onSubmit={async (event) => {
                event.preventDefault();
                if (!selectedDate) return;
                setError("");
                try {
                  await api("/api/admin/cards/slots", {
                    method: "POST",
                    body: { slot_date: selectedDate, slot_time: slotTime, capacity: Number(slotCapacity) || 8 },
                  });
                  await loadSlots();
                  setNotice("Appointment slot saved.");
                } catch (err) {
                  setError(err.message);
                }
              }}
            >
              <Field label="Time">
                <input type="time" value={slotTime} onChange={(event) => setSlotTime(event.target.value)} required />
              </Field>
              <Field label="Capacity">
                <input type="number" min="1" max="100" value={slotCapacity} onChange={(event) => setSlotCapacity(event.target.value)} />
              </Field>
              <button className="btn btn-navy" type="submit" disabled={!selectedDate || selectedDate < todayIso}>
                Add slot
              </button>
            </form>
          </div>
        </div>
      </section>

      <section className="card panel">
        <form
          className="toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedQuery(query);
          }}
        >
          <Field label="Search">
            <div className="search-field">
              <SearchIcon size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, email, or student ID" />
            </div>
          </Field>
          <Field label="Status">
            <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
              {FILTERS.map((item) => (
                <option key={item.id || "all"} value={item.id}>
                  {item.label}{item.id && counts[item.id] ? ` (${counts[item.id]})` : ""}
                </option>
              ))}
            </select>
          </Field>
          <button className="btn btn-navy" type="submit">Search</button>
          <button className="btn btn-outline" type="button" onClick={() => load()} disabled={loading}>
            <RefreshIcon size={16} /> Refresh
          </button>
        </form>

        {loading && !items.length ? (
          <PageSkeleton />
        ) : !items.length ? (
          <p className="muted">No alumni card records match this filter.</p>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Alumni</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th>Membership</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.name}</strong>
                      <div className="muted">{row.email}</div>
                    </td>
                    <td><Badge tone={row.status}>{row.label}</Badge></td>
                    <td>{row.submitted_at ? formatDateTime(row.submitted_at) : "—"}</td>
                    <td>{row.membership_type || "—"}</td>
                    <td className="cell-actions">
                      <button className="btn btn-navy btn-sm" type="button" onClick={() => openDetail(row.id)}>
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data ? <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} /> : null}
      </section>

      {selected ? (
        <Dialog
          title="Alumni card application"
          wide
          confirmLabel="Close"
          onConfirm={() => setSelected(null)}
          onClose={() => setSelected(null)}
        >
          <dl className="deflist">
            <div className="deflist-row"><dt>Alumni</dt><dd>{selected.account.name}</dd></div>
            <div className="deflist-row"><dt>Email</dt><dd>{selected.account.email}</dd></div>
            <div className="deflist-row"><dt>Student ID</dt><dd>{selected.account.student_id || "—"}</dd></div>
            <div className="deflist-row"><dt>Degree</dt><dd>{selected.account.degree || "—"}</dd></div>
            <div className="deflist-row"><dt>Status</dt><dd><Badge tone={selected.card.status}>{selected.card.label}</Badge></dd></div>
            <div className="deflist-row"><dt>Phone</dt><dd>{selected.card.application?.phone || selected.account.phone || "—"}</dd></div>
            <div className="deflist-row"><dt>Mailing address</dt><dd>{selected.card.application?.mailing_address || "—"}</dd></div>
            <div className="deflist-row"><dt>Membership</dt><dd>{selected.card.application?.membership_type || "—"}</dd></div>
            <div className="deflist-row"><dt>Birthday</dt><dd>{selected.card.application?.birthday || "—"}</dd></div>
            <div className="deflist-row"><dt>Appointment</dt><dd>{selected.card.application?.appointment_date ? `${selected.card.application.appointment_date} ${selected.card.application.appointment_time || ""}` : "—"}</dd></div>
          </dl>
          <Field label="Optional note for the alumnus">
            <textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={400} rows={3} />
          </Field>
          <div className="primary-actions">
            {(selected.next_statuses || []).map((next) => (
              <button
                key={next}
                className={next === "NotYetApplied" ? "btn btn-outline" : "btn btn-navy"}
                type="button"
                onClick={() => setPending(next)}
              >
                <CreditCardIcon size={16} />
                {ACTION_LABELS[next] || next}
              </button>
            ))}
          </div>
        </Dialog>
      ) : null}

      {pending ? (
        <Dialog
          title={`${ACTION_LABELS[pending] || pending}?`}
          confirmLabel={ACTION_LABELS[pending] || "Update"}
          busy={busy}
          danger={pending === "NotYetApplied"}
          onConfirm={applyStatus}
          onClose={() => setPending(null)}
        >
          <p>
            This updates the official Angelenean Alumni Card status. The alumnus cannot change this status from the alumni portal.
          </p>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
