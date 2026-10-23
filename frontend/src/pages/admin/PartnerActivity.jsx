import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { DateField } from "../../components/DateField";
import { QrCodeIcon, SearchIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { InfoGrid } from "../../components/AdminReview";
import { Panel } from "../../components/RecordViews";
import {
  Alert,
  Badge,
  Dialog,
  Empty,
  Field,
  LoadError,
  Pager,
  PageSkeleton,
  ReviewSheet,
  SortButton,
} from "../../components/ui";
import { api, downloadAuthorized } from "../../lib/api";
import { formatDate, formatLongDate, formatTime } from "../../lib/format";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

const STATUS_OPTIONS = [
  ["", "All statuses"],
  ["success", "Successful"],
  ["rejected", "Unsuccessful"],
  ["pending", "Pending"],
  ["confirmed", "Confirmed"],
  ["cancelled", "Cancelled"],
];

function localDateTimeValue(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function localInputToIso(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(value || ""));
  if (!match) return "";
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5]));
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString();
}

function statusTone(status) {
  if (status === "success" || status === "confirmed") return "active";
  if (status === "rejected" || status === "cancelled") return "rejected";
  if (status === "pending") return "pending";
  return "unknown";
}

function blankForm() {
  return {
    alumniId: "",
    alumniLabel: "",
    partner: "",
    activityType: "partner_visit",
    activityAt: localDateTimeValue(),
    perkId: "",
    status: "pending",
    notes: "",
    reference: "",
    relatedId: "",
  };
}

export default function AdminPartnerActivity() {
  const [params, setParams] = useSearchParams();
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState(null);
  const [partners, setPartners] = useState([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState(params.get("q") || "");
  const [sort, setSort] = useState({ key: params.get("sort") || "activity_at", dir: params.get("dir") || "desc" });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [recordOpen, setRecordOpen] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(blankForm);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [alumniQuery, setAlumniQuery] = useState("");
  const [alumniHits, setAlumniHits] = useState([]);
  const [scanPartner, setScanPartner] = useState("");
  const [scanPayload, setScanPayload] = useState("");
  const [scanNotes, setScanNotes] = useState("");
  const [scanError, setScanError] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState("");

  const dateFrom = params.get("from") || "";
  const dateTo = params.get("to") || "";
  const partner = params.get("partner") || "";
  const status = params.get("status") || "";
  const match = params.get("match") || "";
  const page = Number(params.get("page") || "1");
  const search = params.get("q") || "";

  function replaceParams(next, { resetPage = true } = {}) {
    const copy = new URLSearchParams(params);
    Object.entries(next).forEach(([key, value]) => {
      if (value) copy.set(key, value);
      else copy.delete(key);
    });
    if (resetPage) copy.delete("page");
    setParams(copy);
  }

  function scopeParams() {
    const queryParams = new URLSearchParams();
    if (dateFrom) queryParams.set("date_from", dateFrom);
    if (dateTo) queryParams.set("date_to", dateTo);
    if (partner) queryParams.set("partner", partner);
    if (search) queryParams.set("q", search);
    return queryParams;
  }

  function listParams() {
    const queryParams = scopeParams();
    if (match) queryParams.set("match", match);
    else if (status) queryParams.set("status", status);
    queryParams.set("page", String(page));
    queryParams.set("page_size", "12");
    queryParams.set("sort_by", sort.key);
    queryParams.set("sort_dir", sort.dir);
    return queryParams;
  }

  function cardTarget(nextMatch) {
    const copy = new URLSearchParams(params);
    ["type", "method", "status", "page"].forEach((key) => copy.delete(key));
    if (match === nextMatch) copy.delete("match");
    else copy.set("match", nextMatch);
    return `/admin/partner-activity?${copy.toString()}`;
  }

  async function load() {
    setError("");
    try {
      const [summaryBody, listBody] = await Promise.all([
        api(`/api/admin/partner-activity/summary?${scopeParams().toString()}`, { toast: false }),
        api(`/api/admin/partner-activity?${listParams().toString()}`, { toast: false }),
      ]);
      setSummary(summaryBody);
      setRows(listBody);
    } catch (err) {
      setError(friendlyError(err, "We couldn't load partner activity."));
    }
  }

  useEffect(() => {
    api("/api/admin/partner-activity/partners", { toast: false })
      .then((body) => setPartners(body.items || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [dateFrom, dateTo, partner, search, status, match, page, sort.key, sort.dir]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return undefined;
    }
    let cancelled = false;
    api(`/api/admin/partner-activity/${selected}`, { toast: false })
      .then((body) => {
        if (!cancelled) {
          setDetail(body);
          setNoteDraft(body.notes || "");
        }
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err, "We couldn't open this activity."));
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  useEffect(() => {
    if (!recordOpen || alumniQuery.trim().length < 2) {
      setAlumniHits([]);
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      api(`/api/admin/partner-activity/alumni?q=${encodeURIComponent(alumniQuery.trim())}`, { toast: false })
        .then((body) => {
          if (!cancelled) setAlumniHits(body.items || []);
        })
        .catch(() => {
          if (!cancelled) setAlumniHits([]);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [alumniQuery, recordOpen]);

  const activePartners = partners.filter((item) => item.active);
  const selectedPartner = activePartners.find((item) => item.name === form.partner);
  const usablePerks = (selectedPartner?.perks || []).filter((perk) => perk.usable);
  const filtersActive = Boolean(dateFrom || dateTo || partner || search || status || match);

  const scanHint = useMemo(() => {
    if (!summary) return "";
    return `${summary.qr_scans_successful} successful · ${summary.qr_scans_unsuccessful} unsuccessful`;
  }, [summary]);

  function openRecord() {
    setForm(blankForm());
    setFormError("");
    setFieldErrors({});
    setAlumniQuery("");
    setAlumniHits([]);
    setIdempotencyKey(crypto.randomUUID());
    setRecordOpen(true);
  }

  function openScan() {
    setScanPartner(activePartners[0]?.name || "");
    setScanPayload("");
    setScanNotes("");
    setScanError("");
    setIdempotencyKey(crypto.randomUUID());
    setScanOpen(true);
  }

  function validateForm() {
    const next = {};
    if (!form.alumniId) next.alumni = "Select an alumnus.";
    if (!form.partner) next.partner = "Select a partner establishment.";
    if (!form.activityAt) next.activityAt = "Enter the activity date and time.";
    else if (!localInputToIso(form.activityAt)) next.activityAt = "Enter the activity date and time.";
    else if (new Date(localInputToIso(form.activityAt)).getTime() > Date.now() + 2 * 60 * 1000) next.activityAt = "The activity date cannot be in the future.";
    if (form.activityType === "benefit_redemption" && !form.perkId) next.perk = "Select the benefit or discount.";
    if (!["pending", "confirmed"].includes(form.status)) next.status = "Choose Pending or Confirmed.";
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  }

  async function saveManual() {
    setFormError("");
    if (!validateForm()) {
      setFormError("Complete the required fields before saving.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/admin/partner-activity", {
        method: "POST",
        body: {
          alumni_account_id: Number(form.alumniId),
          partner: form.partner,
          activity_type: form.activityType,
          activity_at: localInputToIso(form.activityAt),
          status: form.status,
          perk_id: form.perkId ? Number(form.perkId) : null,
          notes: form.notes,
          reference_code: form.reference,
          idempotency_key: idempotencyKey,
          related_activity_id: form.relatedId ? Number(form.relatedId) : null,
        },
      });
      showToast("success", form.activityType === "benefit_redemption" ? "Benefit redemption recorded." : "Partner visit recorded.");
      setRecordOpen(false);
      await load();
    } catch (err) {
      setFormError(friendlyError(err, "We couldn't save this activity."));
    } finally {
      setBusy(false);
    }
  }

  async function saveScan() {
    setScanError("");
    if (!scanPartner) {
      setScanError("Select a partner establishment.");
      return;
    }
    if (!scanPayload.trim()) {
      setScanError("Paste the alumni QR code or its verification link.");
      return;
    }
    setBusy(true);
    try {
      const saved = await api("/api/admin/partner-activity/scans", {
        method: "POST",
        body: {
          partner: scanPartner,
          payload: scanPayload.trim(),
          notes: scanNotes,
          idempotency_key: idempotencyKey,
        },
      });
      showToast("success", saved.status === "success" ? "QR scan recorded." : "Unsuccessful scan recorded.");
      setScanOpen(false);
      await load();
      setSelected(saved.id);
    } catch (err) {
      setScanError(friendlyError(err, "We couldn't record this scan."));
    } finally {
      setBusy(false);
    }
  }

  async function updateDetail(changes) {
    if (!detail) return;
    setBusy(true);
    try {
      const saved = await api(`/api/admin/partner-activity/${detail.id}`, { method: "PATCH", body: changes });
      setDetail(saved);
      setNoteDraft(saved.notes || "");
      showToast("success", "Activity updated.");
      await load();
    } catch (err) {
      setError(friendlyError(err, "We couldn't update this activity."));
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    try {
      const queryParams = listParams();
      queryParams.delete("page");
      queryParams.delete("page_size");
      await downloadAuthorized(`/api/admin/partner-activity/export?${queryParams.toString()}`, "partner-activity.csv");
    } catch (err) {
      setError(friendlyError(err, "We couldn't export these activities."));
    }
  }

  function clearFilters() {
    setQuery("");
    setParams(new URLSearchParams());
  }

  if (!summary && !rows && !error) {
    return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;
  }

  return (
    <PortalShell role="Admin">
      <div className="setup-page">
      <section className="card panel qr-usage-intro" aria-label="Alumni QR Usage">
        <header className="panel-head">
          <div>
            <h2>Alumni QR Usage</h2>
            <p className="lead">
              Record and monitor QR scans, partner visits, and benefit redemptions at partner establishments. Opening an alumni QR code does not create a visit or a redemption.
            </p>
          </div>
          <div className="panel-actions">
            <button className="btn btn-outline" type="button" onClick={openScan}>Record QR Scan</button>
            <button className="btn btn-navy" type="button" onClick={openRecord}>Record Activity</button>
          </div>
        </header>
      </section>

      <Alert type="error">{error && rows ? error : null}</Alert>
      {error && !rows ? <LoadError onRetry={load}>{error}</LoadError> : null}

      <div className="metrics partner-metrics">
        <MetricLink
          label="Unique Alumni"
          value={summary?.unique_alumni ?? 0}
          hint="Distinct alumni with a successful scan, recorded visit, or redemption in this range."
          to={cardTarget("alumni")}
          current={match === "alumni"}
        />
        <MetricLink
          label="QR Scans"
          value={summary?.qr_scans ?? 0}
          hint={scanHint || "Recorded scan attempts."}
          to={cardTarget("scans")}
          current={match === "scans"}
        />
        <MetricLink
          label="Partner Visits"
          value={summary?.partner_visits ?? 0}
          hint="Visits recorded by an authorized person. Cancelled visits are excluded."
          to={cardTarget("visits")}
          current={match === "visits"}
        />
        <MetricLink
          label="Confirmed Redemptions"
          value={summary?.confirmed_redemptions ?? 0}
          hint="Benefits marked confirmed. A scan or visit is not counted here."
          to={cardTarget("redemptions")}
          current={match === "redemptions"}
        />
      </div>

      <Panel
        className="qr-usage"
        title="Activity log"
        description="Search by alumni name, student number, email, or partner. Summary cards follow the date range, partner, and search. Export uses the table filters."
        actions={<button className="btn btn-outline btn-sm" type="button" onClick={exportCsv}>Download CSV</button>}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            replaceParams({ q: query.trim(), match: "" });
          }}
        >
          <div className="qr-search-row">
            <Field label="Search">
              <div className="search-field">
                <SearchIcon size={16} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Name, student number, email, or partner"
                  aria-label="Search by alumni name, student number, email, or partner"
                />
              </div>
            </Field>
            <button className="btn btn-navy" type="submit">Search</button>
            {filtersActive ? <button className="btn btn-outline" type="button" onClick={clearFilters}>Clear filters</button> : null}
          </div>
          <div className="partner-activity-filters">
          <Field label="From">
            <DateField
              value={dateFrom}
              max={dateTo || undefined}
              aria-label="Activity from date"
              onChange={(event) => replaceParams({ from: event.target.value })}
            />
          </Field>
          <Field label="To">
            <DateField
              value={dateTo}
              min={dateFrom || undefined}
              aria-label="Activity to date"
              onChange={(event) => replaceParams({ to: event.target.value })}
            />
          </Field>
          <Field label="Partner">
            <select value={partner} onChange={(event) => replaceParams({ partner: event.target.value })}>
              <option value="">All partners</option>
              {partners.map((item) => <option key={item.name} value={item.name}>{item.name}{item.active ? "" : " (inactive)"}</option>)}
            </select>
          </Field>
          <Field label="Status">
            <select value={status} onChange={(event) => replaceParams({ status: event.target.value, match: "" })}>
              {STATUS_OPTIONS.map(([value, label]) => <option key={value || "all"} value={value}>{label}</option>)}
            </select>
          </Field>
          </div>
        </form>

        {!rows?.items?.length ? (
          <Empty title={filtersActive ? "No records match these filters" : "No activity recorded yet"}>{filtersActive ? "Change the date, partner, search, or status, or clear the filters." : "QR scans, partner visits, and benefit redemptions will appear here."}</Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data stack">
                <thead>
                  <tr>
                    <th>Alumnus</th>
                    <th>Student number</th>
                    <th><SortButton column="partner" sort={sort} onSort={(key) => setSort((prev) => ({ key, dir: prev.key === key && prev.dir === "asc" ? "desc" : "asc" }))}>Partner</SortButton></th>
                    <th><SortButton column="activity_at" sort={sort} onSort={(key) => setSort((prev) => ({ key, dir: prev.key === key && prev.dir === "asc" ? "desc" : "asc" }))}>Date and time</SortButton></th>
                    <th><SortButton column="status" sort={sort} onSort={(key) => setSort((prev) => ({ key, dir: prev.key === key && prev.dir === "asc" ? "desc" : "asc" }))}>Status</SortButton></th>
                    <th>View</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.items.map((row) => (
                    <tr key={row.id}>
                      <td className="cell-person" data-label="Alumnus">
                        <div className="record-person">
                          <strong>{row.alumni_name || "Unknown alumnus"}</strong>
                          <span>{row.email || "—"}</span>
                        </div>
                      </td>
                      <td data-label="Student number">{row.student_number || "—"}</td>
                      <td data-label="Partner">{row.partner || "—"}</td>
                      <td data-label="Date and time">{formatDate(row.activity_at)} · {formatTime(row.activity_at)}</td>
                      <td data-label="Status"><Badge tone={statusTone(row.status)}>{row.status_label}</Badge></td>
                      <td className="cell-actions" data-label="View">
                        <button className="btn btn-outline btn-sm" type="button" onClick={() => setSelected(row.id)}>View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={rows.page} pageSize={rows.page_size} total={rows.total} onPage={(next) => replaceParams({ page: String(next) }, { resetPage: false })} />
          </>
        )}
      </Panel>
      </div>

      {recordOpen ? (
        <Dialog title="Record Activity" description="Manual entries stay labeled as manual. They are not recorded as QR scans." confirmLabel={busy ? "Saving…" : "Save activity"} busy={busy} onConfirm={saveManual} onClose={() => { if (!busy) setRecordOpen(false); }}>
          <Alert type="error">{formError}</Alert>
          <div className="partner-activity-form">
            <fieldset className="setup-group">
              <legend>Alumni</legend>
            <Field label="Alumni" required error={fieldErrors.alumni}>
              <input value={alumniQuery} onChange={(event) => { setAlumniQuery(event.target.value); setForm((current) => ({ ...current, alumniId: "", alumniLabel: "" })); }} placeholder="Search by name or student number" />
              {form.alumniLabel ? <p className="field-help">Selected: {form.alumniLabel}</p> : null}
              {alumniHits.length ? (
                <ul className="partner-alumni-hits">
                  {alumniHits.map((hit) => (
                    <li key={hit.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setForm((current) => ({ ...current, alumniId: String(hit.id), alumniLabel: `${hit.name} · ${hit.student_number || hit.email}` }));
                          setAlumniQuery(hit.name);
                          setAlumniHits([]);
                        }}
                      >
                        <strong>{hit.name}</strong>
                        <span>{hit.student_number || "No student number"} · {hit.email}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Partner and activity</legend>
            <Field label="Partner establishment" required error={fieldErrors.partner}>
              <select value={form.partner} onChange={(event) => setForm((current) => ({ ...current, partner: event.target.value, perkId: "" }))}>
                <option value="">Select a partner</option>
                {activePartners.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
              </select>
            </Field>
            <Field label="Activity type" required>
              <select value={form.activityType} onChange={(event) => setForm((current) => ({ ...current, activityType: event.target.value }))}>
                <option value="partner_visit">Partner Visit</option>
                <option value="benefit_redemption">Benefit Redemption</option>
              </select>
            </Field>
            </fieldset>
            <fieldset className="setup-group">
              <legend>Benefit, time, and status</legend>
            <Field label="Activity date and time" required error={fieldErrors.activityAt}>
              <input type="datetime-local" value={form.activityAt} onChange={(event) => setForm((current) => ({ ...current, activityAt: event.target.value }))} />
            </Field>
            <Field label="Benefit or discount" required={form.activityType === "benefit_redemption"} error={fieldErrors.perk} hint={form.activityType === "partner_visit" ? "Optional for a visit. Choosing a benefit does not record a redemption." : "Required for a redemption."}>
              <select value={form.perkId} onChange={(event) => setForm((current) => ({ ...current, perkId: event.target.value }))}>
                <option value="">{form.activityType === "benefit_redemption" ? "Select a benefit" : "No benefit"}</option>
                {usablePerks.map((perk) => <option key={perk.id} value={perk.id}>{perk.name}{perk.discount ? ` — ${perk.discount}` : ""}</option>)}
              </select>
            </Field>
            <Field label="Verification status" required error={fieldErrors.status}>
              <select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}>
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
              </select>
            </Field>
            <Field label="Notes or reference" hint="Optional. Use this for a transaction or reference number.">
              <textarea value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} />
              <input value={form.reference} onChange={(event) => setForm((current) => ({ ...current, reference: event.target.value }))} maxLength={80} placeholder="Reference number" />
            </Field>
            </fieldset>
          </div>
        </Dialog>
      ) : null}

      {scanOpen ? (
        <Dialog title="Record QR Scan" description="Submit the code an authorized partner scanned. This records a scan attempt only." confirmLabel={busy ? "Recording…" : "Record scan"} busy={busy} onConfirm={saveScan} onClose={() => { if (!busy) setScanOpen(false); }}>
          <Alert type="error">{scanError}</Alert>
          <div className="partner-activity-form">
            <p className="setup-help">Paste the signed QR value, or a link that contains /verify/qr/. The scan time is the time you submit this form. A scan cannot be changed into a partner visit or a benefit redemption.</p>
            <Field label="Partner establishment" required>
              <select value={scanPartner} onChange={(event) => setScanPartner(event.target.value)}>
                <option value="">Select a partner</option>
                {activePartners.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
              </select>
            </Field>
            <Field label="QR code or verification link" required hint="Paste the signed QR value or the /verify/qr link. Displaying the code on the alumni page is not a scan.">
              <textarea value={scanPayload} onChange={(event) => setScanPayload(event.target.value)} placeholder="v1.… or https://…/verify/qr/…" />
            </Field>
            <Field label="Notes">
              <textarea value={scanNotes} onChange={(event) => setScanNotes(event.target.value)} />
            </Field>
          </div>
        </Dialog>
      ) : null}

      {detail ? (
        <ReviewSheet title={detail.alumni_name || "Unknown alumnus"} subtitle={detail.email || "No email address"} meta={`${detail.activity_type_label} · ${detail.recording_method_label}`} onClose={() => setSelected(null)} wide>
          <div className="record-sections">
            <section className="detail-section">
              <h2>Activity Summary</h2>
              <InfoGrid
                items={[
                  { label: "Activity type", value: detail.activity_type_label },
                  { label: "Partner establishment", value: detail.partner },
                  { label: "Benefit or discount", value: detail.benefit_label || "—" },
                  { label: "Activity date", value: formatLongDate(detail.activity_at) },
                  { label: "Activity time", value: formatTime(detail.activity_at) },
                  { label: "Status", value: detail.status_label },
                  { label: "Outcome", value: detail.outcome_detail || "—" },
                ]}
              />
            </section>
            <section className="detail-section">
              <h2>Alumni Information</h2>
              {!detail.alumni_account_id ? <p className="setup-help">This scan is not linked to an alumnus.</p> : null}
              <InfoGrid
                items={[
                  { label: "Alumnus", value: detail.alumni_name || "—" },
                  { label: "Student number", value: detail.student_number || "—" },
                  { label: "Email address", value: detail.email || "—" },
                ]}
              />
            </section>
            <section className="detail-section">
              <h2>Record Information</h2>
              <InfoGrid
                items={[
                  { label: "Recording method", value: detail.recording_method_label },
                  { label: "Reference", value: detail.reference_code || "—" },
                  { label: "Recorded by", value: detail.recorded_by || "—" },
                  { label: "Activity timestamp", value: `${formatLongDate(detail.activity_at)} · ${formatTime(detail.activity_at)}` },
                  { label: "Recorded at", value: `${formatLongDate(detail.created_at)} · ${formatTime(detail.created_at)}` },
                ]}
              />
            </section>
            <section className="detail-section">
              <h2>Related Activity</h2>
              <p className="setup-help">Scans, visits, and redemptions stay separate records.</p>
              <InfoGrid
                items={[
                  { label: "Related record", value: detail.related_activity ? `${detail.related_activity.activity_type_label} · ${detail.related_activity.status_label}` : "None" },
                ]}
              />
            </section>
            <section className="detail-section">
              <h2>Notes</h2>
              <Field label="Notes">
                <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} />
              </Field>
              <div className="partner-activity-actions">
                <button className="btn btn-outline btn-sm" type="button" disabled={busy} onClick={() => updateDetail({ notes: noteDraft })}>Save notes</button>
                {detail.recording_method === "manual" && detail.status !== "confirmed" && detail.status !== "cancelled" ? (
                  <button className="btn btn-navy btn-sm" type="button" disabled={busy} onClick={() => updateDetail({ status: "confirmed" })}>Confirm</button>
                ) : null}
                {detail.recording_method === "manual" && detail.status !== "cancelled" ? (
                  <button className="btn btn-outline btn-sm" type="button" disabled={busy} onClick={() => updateDetail({ status: "cancelled" })}>Cancel activity</button>
                ) : null}
              </div>
            </section>
            {detail.audit?.length ? (
              <section className="detail-section">
                <h2>Audit History</h2>
                <ul className="partner-audit">
                  {detail.audit.map((entry) => (
                    <li key={entry.id}>
                      <strong>{entry.action === "partner_activity.create" ? "Created" : "Updated"}</strong>
                      <span>{formatLongDate(entry.created_at)} · {formatTime(entry.created_at)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        </ReviewSheet>
      ) : null}
    </PortalShell>
  );
}

function MetricLink({ label, value, hint, to, current }) {
  return (
    <Link className={`card metric ops-metric is-link ${current ? "is-current" : ""}`} to={to} aria-label={`${label}: ${value}. ${hint}`}>
      <div className="ops-metric-top">
        <span className="ops-metric-icon" aria-hidden="true"><QrCodeIcon size={18} /></span>
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      {hint ? <p className="ops-metric-hint">{hint}</p> : null}
      <span className="ops-metric-cta">{current ? "Showing these records" : "View records →"}</span>
    </Link>
  );
}
