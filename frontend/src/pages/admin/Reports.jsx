import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard, ShareStrip } from "../../components/AdminOps";
import {
  CheckCircleIcon,
  ClipboardListIcon,
  DownloadIcon,
  FileTextIcon,
  PrinterIcon,
  RefreshIcon,
  UsersIcon,
  XIcon,
} from "../../components/icons";
import OaapsReport from "../../components/OaapsReport";
import EmploymentAnalytics, { programsForCollege } from "../../components/EmploymentAnalytics";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { Alert, Field, LoadError, PageSkeleton } from "../../components/ui";
import { api, downloadAuthorized } from "../../lib/api";

const EMPTY_FILTERS = {
  period_from: "",
  period_to: "",
  year: "",
  college: "",
  program: "",
};

function queryFrom(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

function ChartUnavailable() {
  return (
    <div className="empty compact admin-reports-empty">
      <h3>No data available for this report yet.</h3>
      <p>Totals will appear here once matching records are on file.</p>
    </div>
  );
}

export default function AdminReports() {
  const [data, setData] = useState(null);
  const [report, setReport] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [exporting, setExporting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);

  function load() {
    setError("");
    api("/api/admin/reports").then(setData).catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  async function generateReport(event) {
    event.preventDefault();
    setError("");
    setLoadingReport(true);
    try {
      setReport(await api(`/api/admin/reports/oaaps${queryFrom(filters)}`));
      setOk("Report generated successfully.");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingReport(false);
    }
  }

  async function downloadCsv() {
    setError("");
    setExporting(true);
    try {
      await downloadAuthorized("/api/admin/reports/export", "careersense-tracer.csv");
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  }

  async function downloadWord() {
    setError("");
    setDownloading(true);
    try {
      await downloadAuthorized(
        `/api/admin/reports/oaaps/export${queryFrom(filters)}`,
        "AUF-OAAPS-Graduate-Productivity-Report.docx"
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS);
    setReport(null);
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const options = data?.options || report?.options || { colleges: [], programs: [], years: [] };
  const courseOptions = programsForCollege(options, filters.college);
  const yearData = data?.by_graduation_year || [];
  const hasEmployment = Boolean(
    data?.currently_employed_submissions || data?.degree_related_submissions || data?.total_submissions
  );

  function chooseCollege(value) {
    const allowed = programsForCollege(options, value);
    setFilters((prev) => ({
      ...prev,
      college: value,
      program: allowed.includes(prev.program) ? prev.program : "",
    }));
    setReport(null);
  }

  function chooseCourse(value) {
    setFilters((prev) => ({ ...prev, program: value }));
    setReport(null);
  }

  function chooseYear(value) {
    setFilters((prev) => ({ ...prev, year: value }));
    setReport(null);
  }

  function clearAcademicFilters() {
    setFilters((prev) => ({ ...prev, college: "", program: "", year: "" }));
    setReport(null);
  }

  return (
    <PortalShell role="Admin">
      <div className="admin-reports">
        <Alert type="error">{error}</Alert>
        <Alert type="ok" title={ok || undefined} />
        {error && !data ? (
          <LoadError onRetry={load}>{error}</LoadError>
        ) : null}

        {data ? (
          <div className="reports-dashboard">
            <section className="admin-reports-block" aria-labelledby="reports-overview-heading">
              <header className="admin-reports-section-head">
                <h2 id="reports-overview-heading">Overview</h2>
              </header>
              <div className="admin-reports-metrics">
                <MetricCard label="Registered Alumni" value={data.registered} icon={<UsersIcon size={18} />} hint="All alumni accounts on file" />
                <MetricCard label="Approved" value={data.approved} icon={<CheckCircleIcon size={18} />} hint="Active alumni accounts" />
                <MetricCard label="Pending" value={data.pending} icon={<ClipboardListIcon size={18} />} hint="Awaiting verification" />
                <MetricCard label="Rejected" value={data.rejected} icon={<XIcon size={18} />} hint="Denied registrations" />
              </div>
            </section>

            <section className="admin-reports-block" aria-labelledby="reports-analytics-heading">
              <header className="admin-reports-section-head">
                <h2 id="reports-analytics-heading">Analytics Overview</h2>
              </header>
              <div className="admin-reports-charts">
                <Panel title="Alumni by Status">
                  <ShareStrip
                    emptyTitle="No data available for this report yet."
                    emptyText="Status totals will appear after alumni register."
                    items={[
                      { label: "Approved", count: data.approved, tone: "active" },
                      { label: "Pending", count: data.pending, tone: "pending" },
                      { label: "Rejected", count: data.rejected, tone: "rejected" },
                    ]}
                  />
                </Panel>
                <Panel title="Employment Snapshot" description="Unfiltered counts from each alumnus’s latest tracer record. College and course charts are in Employment Overview.">
                  {hasEmployment ? (
                    <dl className="admin-reports-snapshot">
                      <div>
                        <dt>Currently employed</dt>
                        <dd>{data.currently_employed_submissions}</dd>
                      </div>
                      <div>
                        <dt>Degree-related jobs</dt>
                        <dd>{data.degree_related_submissions}</dd>
                      </div>
                      <div>
                        <dt>Tracer submissions</dt>
                        <dd>{data.total_submissions}</dd>
                      </div>
                    </dl>
                  ) : (
                    <ChartUnavailable />
                  )}
                </Panel>
              </div>
              <Panel className="admin-reports-chart-wide" title="Alumni by Graduation Year">
                {yearData.length ? (
                  <div className="admin-reports-chart" role="img" aria-label="Alumni counts by graduation year">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={yearData} margin={{ top: 12, right: 12, left: 4, bottom: 8 }}>
                        <XAxis dataKey="year" tick={{ fontSize: 14, fill: "#5b6777" }} axisLine={false} tickLine={false} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 14, fill: "#5b6777" }} axisLine={false} tickLine={false} width={36} />
                        <Tooltip cursor={{ fill: "rgba(11,46,89,0.06)" }} />
                        <Bar dataKey="count" fill="#0B2E59" radius={[4, 4, 0, 0]} maxBarSize={42} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <ChartUnavailable />
                )}
              </Panel>
            </section>

            <EmploymentAnalytics
              filters={filters}
              options={options}
              onCollege={chooseCollege}
              onCourse={chooseCourse}
              onYear={chooseYear}
              onClear={clearAcademicFilters}
            />
          </div>
        ) : null}

        <section className="admin-reports-csv no-print">
          <div>
            <h2>Data export</h2>
          </div>
          <button className="btn btn-outline" type="button" disabled={exporting} onClick={downloadCsv}>
            <DownloadIcon size={16} />
            {exporting ? "Exporting…" : "Download CSV"}
          </button>
        </section>

        <Panel
          className="admin-reports-builder no-print"
          title="Overall Graduate Productivity Report"
        >
          <form className="admin-reports-filters" onSubmit={generateReport}>
            <div className="admin-reports-filter-grid">
              <Field label="Reporting Period: From">
                <input type="date" value={filters.period_from} onChange={(e) => setFilters({ ...filters, period_from: e.target.value })} />
              </Field>
              <Field label="Reporting Period: To">
                <input type="date" value={filters.period_to} onChange={(e) => setFilters({ ...filters, period_to: e.target.value })} />
              </Field>
              <Field label="Graduating Batch / Year">
                <select aria-label="Filter the productivity report by graduating batch" value={filters.year} onChange={(e) => chooseYear(e.target.value)}>
                  <option value="">All batches</option>
                  {(options.years || []).map((year) => <option key={year} value={year}>{year}</option>)}
                </select>
              </Field>
              <Field label="College">
                <select aria-label="Filter the productivity report by college" value={filters.college} onChange={(e) => chooseCollege(e.target.value)}>
                  <option value="">All colleges</option>
                  {(options.colleges || []).map((college) => <option key={college} value={college}>{college}</option>)}
                </select>
              </Field>
              <Field label="Program">
                <select aria-label="Filter the productivity report by program" value={courseOptions.includes(filters.program) ? filters.program : ""} onChange={(e) => chooseCourse(e.target.value)}>
                  <option value="">All programs</option>
                  {courseOptions.map((program) => <option key={program} value={program}>{program}</option>)}
                </select>
              </Field>
            </div>
            <div className="admin-reports-filter-actions">
              <button className="btn btn-navy" type="submit" disabled={loadingReport}>
                <FileTextIcon size={16} />
                {loadingReport ? "Generating…" : "Generate Report"}
              </button>
              <button className="btn btn-outline" type="button" onClick={resetFilters}>
                <RefreshIcon size={16} />
                Reset
              </button>
            </div>
          </form>
          {report ? null : (
            <p className="muted admin-reports-await">Generate a report to preview it below. Choose a period or cohort, then select Generate Report.</p>
          )}
        </Panel>

        {report ? (
          <section className="admin-reports-result" aria-labelledby="reports-generated-heading">
            <div className="report-preview-head no-print">
              <div>
                <h2 id="reports-generated-heading">Graduate Productivity Report</h2>
              </div>
              <div className="admin-reports-export-actions">
                <button className="btn btn-navy" type="button" disabled={downloading} onClick={downloadWord}>
                  <DownloadIcon size={16} />
                  {downloading ? "Downloading…" : "Download Word"}
                </button>
                <button className="btn btn-outline" type="button" onClick={() => window.print()}>
                  <PrinterIcon size={16} />
                  Print / Save as PDF
                </button>
              </div>
            </div>
            <div className="admin-reports-document">
              <OaapsReport report={report} />
            </div>
          </section>
        ) : null}
      </div>
    </PortalShell>
  );
}
