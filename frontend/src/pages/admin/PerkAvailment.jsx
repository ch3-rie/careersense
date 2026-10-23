import { useEffect, useState } from "react";
import { DateField } from "../../components/DateField";
import { Alert, Badge, Dialog, Empty, Field, Pager } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

const TYPES = [
  ["", "All activity"],
  ["qr_scan", "QR Scan"],
  ["partner_visit", "Partner Visit"],
  ["benefit_redemption", "Benefit Redemption"],
];

const STATUSES = [
  ["", "All statuses"],
  ["success", "Successful"],
  ["rejected", "Unsuccessful"],
  ["pending", "Pending"],
  ["confirmed", "Confirmed"],
  ["cancelled", "Cancelled"],
];

function completedAvailment(row) {
  return row.activity_type === "benefit_redemption" && row.status === "confirmed";
}

export default function PerkAvailment({ perks = [] }) {
  const [partners, setPartners] = useState([]);
  const [filters, setFilters] = useState({
    q: "",
    partner: "",
    perk_id: "",
    date_from: "",
    date_to: "",
    activity_type: "",
    status: "",
  });
  const [applied, setApplied] = useState(filters);
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/admin/partner-activity/partners")
      .then((result) => setPartners(result.items || []))
      .catch(() => setPartners([]));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", "12");
    if (applied.q) params.set("q", applied.q);
    if (applied.partner) params.set("partner", applied.partner);
    if (applied.perk_id) params.set("perk_id", applied.perk_id);
    if (applied.date_from) params.set("date_from", applied.date_from);
    if (applied.date_to) params.set("date_to", applied.date_to);
    if (applied.activity_type) params.set("activity_type", applied.activity_type);
    if (applied.status) params.set("status", applied.status);
    let cancelled = false;
    setBusy(true);
    setError("");
    api(`/api/admin/partner-activity?${params.toString()}`)
      .then((result) => {
        if (!cancelled) setData(result);
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
  }, [applied, page]);

  async function openDetail(row) {
    try {
      setDetail(await api(`/api/admin/partner-activity/${row.id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  const rows = data?.items || [];

  return (
    <section className="card panel admin-perk-panel">
      <p className="muted perk-avail-note">
        A completed availment is a Benefit Redemption with Confirmed status. QR scans stay labeled Not an availment.
      </p>
      <form
        className="filter-bar admin-perk-filters"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setApplied({ ...filters });
        }}
      >
        <Field label="Search">
          <input
            value={filters.q}
            onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            placeholder="Name, student number, email, or partner"
          />
        </Field>
        <Field label="Partner">
          <select value={filters.partner} onChange={(event) => setFilters({ ...filters, partner: event.target.value })}>
            <option value="">All partners</option>
            {partners.map((item) => (
              <option key={item.name} value={item.name}>{item.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Perk">
          <select value={filters.perk_id} onChange={(event) => setFilters({ ...filters, perk_id: event.target.value })}>
            <option value="">All perks</option>
            {perks.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </Field>
        <Field label="From">
          <DateField value={filters.date_from} onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} />
        </Field>
        <Field label="To">
          <DateField value={filters.date_to} onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} />
        </Field>
        <Field label="Activity">
          <select value={filters.activity_type} onChange={(event) => setFilters({ ...filters, activity_type: event.target.value })}>
            {TYPES.map(([value, label]) => <option key={value || "all"} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
            {STATUSES.map(([value, label]) => <option key={value || "all-status"} value={value}>{label}</option>)}
          </select>
        </Field>
        <button className="btn btn-navy" type="submit" disabled={busy}>{busy ? "Loading…" : "Apply"}</button>
      </form>
      <Alert type="error">{error}</Alert>
      {!rows.length ? (
        <Empty title={Object.values(applied).some(Boolean) ? "No records match these filters" : "No availment records"}>
          {Object.values(applied).some(Boolean)
            ? "Adjust the search, partner, perk, dates, activity, or status."
            : "Recorded visits and benefit redemptions appear here."}
        </Empty>
      ) : (
        <div className="table-wrap">
          <table className="data stack">
            <thead>
              <tr>
                <th>Alumni</th>
                <th>Student number</th>
                <th>Partner</th>
                <th>Perk or discount</th>
                <th>When</th>
                <th>Activity</th>
                <th>Status</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td data-label="Alumni">{row.alumni_name || "—"}</td>
                  <td data-label="Student number">{row.student_number || "—"}</td>
                  <td data-label="Partner">{row.partner}</td>
                  <td data-label="Perk or discount">{row.benefit_label || "—"}</td>
                  <td data-label="When">{formatDateTime(row.activity_at)}</td>
                  <td data-label="Activity">
                    <div className="perk-status-stack">
                      <span>{row.activity_type_label}</span>
                      {completedAvailment(row) ? <Badge tone="active">Completed availment</Badge> : null}
                      {row.activity_type === "qr_scan" ? <Badge tone="unknown">Not an availment</Badge> : null}
                    </div>
                  </td>
                  <td data-label="Status"><Badge tone={row.status === "confirmed" || row.status === "success" ? "active" : row.status === "pending" ? "pending" : "unknown"}>{row.status_label}</Badge></td>
                  <td data-label="Source">{row.recording_method_label}</td>
                  <td className="cell-actions">
                    <button className="btn btn-outline btn-sm" type="button" onClick={() => openDetail(row)}>View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data?.total ? (
        <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
      ) : null}
      {detail ? (
        <Dialog title="Availment details" confirmLabel="Close" wide onConfirm={() => setDetail(null)} onClose={() => setDetail(null)}>
          <div className="record-sections">
            <section>
              <h3>Activity</h3>
              <dl className="deflist">
                <div className="deflist-row"><dt>Activity</dt><dd>{detail.activity_type_label}</dd></div>
                <div className="deflist-row"><dt>Partner</dt><dd>{detail.partner || "—"}</dd></div>
                <div className="deflist-row"><dt>Perk or discount</dt><dd>{detail.benefit_label || "—"}</dd></div>
                <div className="deflist-row"><dt>When</dt><dd>{formatDateTime(detail.activity_at)}</dd></div>
                <div className="deflist-row"><dt>Status</dt><dd>{detail.status_label}</dd></div>
                <div className="deflist-row"><dt>Outcome</dt><dd>{detail.outcome_detail || "—"}</dd></div>
                <div className="deflist-row"><dt>Completed availment</dt><dd>{completedAvailment(detail) ? "Yes" : detail.activity_type === "qr_scan" ? "No. Not an availment." : "No"}</dd></div>
              </dl>
            </section>
            <section>
              <h3>Alumni and record</h3>
              <dl className="deflist">
                <div className="deflist-row"><dt>Alumni</dt><dd>{detail.alumni_name || (detail.alumni_account_id ? "—" : "Not linked to an alumnus")}</dd></div>
                <div className="deflist-row"><dt>Student number</dt><dd>{detail.student_number || "—"}</dd></div>
                <div className="deflist-row"><dt>Email</dt><dd>{detail.email || "—"}</dd></div>
                <div className="deflist-row"><dt>Source</dt><dd>{detail.recording_method_label}</dd></div>
                <div className="deflist-row"><dt>Recorded by</dt><dd>{detail.recorded_by || "—"}</dd></div>
                <div className="deflist-row"><dt>Notes</dt><dd>{detail.notes || "—"}</dd></div>
              </dl>
            </section>
          </div>
        </Dialog>
      ) : null}
    </section>
  );
}
