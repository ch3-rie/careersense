import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ShareStrip, directoryPath } from "../../components/AdminOps";
import {
  DownloadIcon,
  FileTextIcon,
  PrinterIcon,
  RefreshIcon,
} from "../../components/icons";
import OaapsReport from "../../components/OaapsReport";
import EmploymentAnalytics, { programsForCollege } from "../../components/EmploymentAnalytics";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { Alert, Field, LoadError, PageSkeleton } from "../../components/ui";
import { courseLabel } from "../../lib/academicFilters";
import { api, downloadAuthorized } from "../../lib/api";

const EMPTY_EMPLOYMENT = {
  college: "",
  program: "",
  year: "",
  location: "",
  employment: "",
};

const EMPTY_OAAPS = {
  year: "",
  college: "",
  program: "",
  award: "",
  further: "",
};

const OAAPS_KEYS = ["year", "college", "program", "award", "further"];
const EMPLOYMENT_KEYS = ["college", "program", "year", "location", "employment"];

const REPORTS_CONTEXT_KEY = "cs-admin-reports-context";

function readFilters(source, empty) {
  const filters = { ...empty };
  Object.keys(empty).forEach((key) => {
    filters[key] = typeof source?.[key] === "string" ? source[key] : "";
  });
  return filters;
}

function sameFilters(left, right, keys) {
  return keys.every((key) => String(left?.[key] || "") === String(right?.[key] || ""));
}

function savedReportContext(search) {
  if (new URLSearchParams(search).get("restore") !== "1") return null;
  try {
    const parsed = JSON.parse(sessionStorage.getItem(REPORTS_CONTEXT_KEY) || "null");
    if (!parsed || typeof parsed !== "object") return null;
    const legacy = parsed.filters && typeof parsed.filters === "object" ? parsed.filters : {};
    const employment = readFilters(parsed.employment || legacy, EMPTY_EMPLOYMENT);
    const oaaps = readFilters(parsed.oaaps || legacy, EMPTY_OAAPS);
    const generated = Boolean(parsed.generated);
    return { employment, oaaps, generated };
  } catch {
    return null;
  }
}

function queryFrom(filters, keys) {
  const params = new URLSearchParams();
  keys.forEach((key) => {
    if (filters[key]) params.set(key, filters[key]);
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
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const saved = useState(() => savedReportContext(params.toString() ? `?${params.toString()}` : ""))[0];
  const restoreToken = useRef(0);
  const [data, setData] = useState(null);
  const [report, setReport] = useState(null);
  const [generatedOaaps, setGeneratedOaaps] = useState(null);
  const [employment, setEmployment] = useState(() => saved?.employment || EMPTY_EMPLOYMENT);
  const [oaaps, setOaaps] = useState(() => saved?.oaaps || EMPTY_OAAPS);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [exporting, setExporting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [loadingReport, setLoadingReport] = useState(() => Boolean(saved?.generated));

  const reportMatches = Boolean(report && generatedOaaps && sameFilters(oaaps, generatedOaaps, OAAPS_KEYS));
  const reportStale = Boolean(generatedOaaps) && !sameFilters(oaaps, generatedOaaps, OAAPS_KEYS);

  function load() {
    setError("");
    api("/api/admin/reports").then(setData).catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!saved?.generated) return undefined;
    const token = ++restoreToken.current;
    let cancelled = false;
    const restored = saved.oaaps;
    setLoadingReport(true);
    api(`/api/admin/reports/oaaps${queryFrom(restored, OAAPS_KEYS)}`)
      .then((payload) => {
        if (!cancelled && token === restoreToken.current) {
          setReport(payload);
          setGeneratedOaaps(restored);
        }
      })
      .catch((err) => {
        if (!cancelled && token === restoreToken.current) setError(err.message);
      })
      .finally(() => {
        if (!cancelled && token === restoreToken.current) setLoadingReport(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (loadingReport) return undefined;
    sessionStorage.setItem(
      REPORTS_CONTEXT_KEY,
      JSON.stringify({ employment, oaaps, generated: reportMatches }),
    );
    return undefined;
  }, [employment, oaaps, reportMatches, loadingReport]);

  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  async function generateReport(event) {
    event.preventDefault();
    setError("");
    const token = ++restoreToken.current;
    const requested = { ...oaaps };
    setLoadingReport(true);
    try {
      const payload = await api(`/api/admin/reports/oaaps${queryFrom(requested, OAAPS_KEYS)}`);
      if (token !== restoreToken.current) return;
      setReport(payload);
      setGeneratedOaaps(requested);
      setOk("Report generated successfully.");
    } catch (err) {
      if (token === restoreToken.current) setError(err.message);
    } finally {
      if (token === restoreToken.current) setLoadingReport(false);
    }
  }

  async function downloadCsv() {
    setError("");
    setExporting(true);
    try {
      await downloadAuthorized(
        `/api/admin/reports/export${queryFrom(employment, EMPLOYMENT_KEYS)}`,
        "careersense-tracer.csv",
      );
      setOk("Employment overview CSV downloaded.");
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
        `/api/admin/reports/oaaps/export${queryFrom(oaaps, OAAPS_KEYS)}`,
        "AUF-OAAPS-Graduate-Productivity-Report.docx",
      );
      setOk("Word report downloaded.");
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  function resetReport() {
    restoreToken.current += 1;
    setLoadingReport(false);
    setReport(null);
    setGeneratedOaaps(null);
    setOaaps(EMPTY_OAAPS);
  }

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const options = data?.options || report?.options || { colleges: [], programs: [], years: [] };
  const courseOptions = programsForCollege(options, oaaps.college);
  const yearData = data?.by_graduation_year || [];
  const hasEmployment = Boolean(
    data?.currently_employed_submissions || data?.degree_related_submissions || data?.total_submissions,
  );

  function setEmploymentField(key, value) {
    setEmployment((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "college") {
        const allowed = programsForCollege(options, value);
        if (!allowed.some((item) => item.program === prev.program)) next.program = "";
      }
      return next;
    });
  }

  function setOaapsField(key, value) {
    restoreToken.current += 1;
    setLoadingReport(false);
    setOaaps((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "college") {
        const allowed = programsForCollege(options, value);
        if (!allowed.some((item) => item.program === prev.program)) next.program = "";
      }
      return next;
    });
  }

  function clearEmploymentFilters() {
    setEmployment(EMPTY_EMPLOYMENT);
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
            <section className="admin-reports-block" aria-labelledby="reports-analytics-heading">
              <header className="admin-reports-section-head">
                <div>
                  <p className="admin-reports-kicker">All records</p>
                  <h2 id="reports-analytics-heading">Institutional Snapshot</h2>
                  <p>Institution-wide totals. Filters in the sections below do not change these figures.</p>
                </div>
              </header>
              <div className="admin-reports-charts">
                <Panel title="Alumni by Status">
                  <ShareStrip
                    emptyTitle="No data available for this report yet."
                    emptyText="Status totals will appear after alumni register."
                    items={[
                      { label: "Active / Approved", count: data.approved, tone: "active", to: directoryPath("reports", { cohort: "status", status: "Active" }) },
                      { label: "Pending", count: data.pending, tone: "pending", to: "/admin/approvals?from=reports" },
                      { label: "Rejected", count: data.rejected, tone: "rejected", to: directoryPath("reports", { cohort: "status", status: "Rejected" }) },
                    ]}
                  />
                </Panel>
                <Panel
                  title="Employment Snapshot"
                  description="Employed and degree-related counts use each alumnus’s latest tracer record. Tracer submissions counts every submission on file, including earlier ones from the same alumnus."
                >
                  {hasEmployment ? (
                    <dl className="admin-reports-snapshot">
                      <Link to={directoryPath("reports", { cohort: "employed_overview" })}>
                        <dt>Currently employed</dt>
                        <dd>{data.currently_employed_submissions}</dd>
                        <span className="snapshot-note">Latest tracer record</span>
                      </Link>
                      <Link to={directoryPath("reports", { cohort: "related" })}>
                        <dt>Degree-related jobs</dt>
                        <dd>{data.degree_related_submissions}</dd>
                        <span className="snapshot-note">Latest tracer record</span>
                      </Link>
                      <Link to="/admin/records?from=reports">
                        <dt>Tracer submissions</dt>
                        <dd>{data.total_submissions}</dd>
                        <span className="snapshot-note">Every submission on file</span>
                      </Link>
                    </dl>
                  ) : (
                    <ChartUnavailable />
                  )}
                </Panel>
              </div>
              <Panel className="admin-reports-chart-wide" title="Alumni by Graduation Year">
                {yearData.length ? (
                  <div className="admin-reports-chart is-clickable" role="img" aria-label="Alumni counts by graduation year. Choose a bar to open that batch.">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={yearData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                          <XAxis dataKey="year" tick={{ fontSize: 13, fill: "#5b6777" }} axisLine={false} tickLine={false} />
                          <YAxis allowDecimals={false} tick={{ fontSize: 13, fill: "#5b6777" }} axisLine={false} tickLine={false} width={32} />
                          <Tooltip cursor={{ fill: "rgba(11,46,89,0.06)" }} />
                          <Bar
                            dataKey="count"
                            fill="#0B2E59"
                            radius={[4, 4, 0, 0]}
                            maxBarSize={36}
                            cursor="pointer"
                            onClick={(bar) => {
                              const batch = bar?.year || bar?.payload?.year;
                              if (batch) navigate(directoryPath("reports", { cohort: "year", year: batch }));
                            }}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                  </div>
                ) : (
                  <ChartUnavailable />
                )}
              </Panel>
            </section>

            <EmploymentAnalytics
              filters={employment}
              options={options}
              onCollege={(value) => setEmploymentField("college", value)}
              onCourse={(value) => setEmploymentField("program", value)}
              onYear={(value) => setEmploymentField("year", value)}
              onLocation={(value) => setEmploymentField("location", value)}
              onEmployment={(value) => setEmploymentField("employment", value)}
              onClear={clearEmploymentFilters}
              onDownload={downloadCsv}
              downloading={exporting}
            />
          </div>
        ) : null}

        <section className="admin-reports-block admin-reports-config no-print" aria-labelledby="oaaps-config-heading">
          <header className="admin-reports-section-head">
            <div>
              <p className="admin-reports-kicker">Report configuration</p>
              <h2 id="oaaps-config-heading">Overall Graduate Productivity Report</h2>
              <p>Official OAAPS document. These filters are separate from Employment Overview.</p>
            </div>
          </header>
          <form className="admin-reports-filters" onSubmit={generateReport}>
            <div className="admin-reports-filter-grid">
              <Field label="Batch Year">
                <select aria-label="Filter the productivity report by batch year" value={oaaps.year} onChange={(e) => setOaapsField("year", e.target.value)}>
                  <option value="">All batches</option>
                  {(options.years || []).map((year) => <option key={year} value={year}>{year}</option>)}
                </select>
              </Field>
              <Field label="College">
                <select aria-label="Filter the productivity report by college" value={oaaps.college} onChange={(e) => setOaapsField("college", e.target.value)}>
                  <option value="">All colleges</option>
                  {(options.colleges || []).map((college) => <option key={college} value={college}>{college}</option>)}
                </select>
              </Field>
              <Field label="Program">
                <select aria-label="Filter the productivity report by program" value={courseOptions.some((item) => item.program === oaaps.program) ? oaaps.program : ""} onChange={(e) => setOaapsField("program", e.target.value)}>
                  <option value="">All programs</option>
                  {courseOptions.map((item) => <option key={item.program} value={item.program}>{courseLabel(item)}</option>)}
                </select>
              </Field>
              <Field label="Awards Received">
                <select aria-label="Filter the productivity report by awards received" value={oaaps.award} onChange={(e) => setOaapsField("award", e.target.value)}>
                  <option value="">All awards</option>
                  <option value="__recorded__">Has recorded awards</option>
                  <option value="__none__">No recorded awards</option>
                  {(options.awards || []).map((title) => <option key={title} value={title}>{title}</option>)}
                </select>
              </Field>
              <Field label="Further Studies">
                <select aria-label="Filter the productivity report by further studies" value={oaaps.further} onChange={(e) => setOaapsField("further", e.target.value)}>
                  <option value="">All further studies</option>
                  <option value="__recorded__">Has recorded further studies</option>
                  <option value="__none__">No recorded further studies</option>
                  {(options.further_studies || []).map((course) => <option key={course} value={course}>{course}</option>)}
                </select>
              </Field>
            </div>
            <div className="admin-reports-filter-actions">
              <button className="btn btn-navy" type="submit" disabled={loadingReport}>
                <FileTextIcon size={16} />
                {loadingReport ? "Generating…" : "Generate Report"}
              </button>
              <button className="btn btn-outline" type="button" onClick={resetReport}>
                <RefreshIcon size={16} />
                Reset Report
              </button>
            </div>
          </form>
          {loadingReport ? (
            <p className="muted admin-reports-await" role="status">Loading the report…</p>
          ) : reportStale ? (
            <p className="report-stale" role="status">
              These filters differ from the generated report. Select Generate Report to refresh the preview.
            </p>
          ) : null}
        </section>

        {reportMatches ? (
          <section className="admin-reports-result" aria-labelledby="reports-generated-heading">
            <div className="report-preview-head no-print">
              <div>
                <p className="admin-reports-kicker">Generated OAAPS report</p>
                <h2 id="reports-generated-heading">Graduate Productivity Report</h2>
                <p>Counts and percentages open the matching student list. That list can be downloaded as Excel or CSV.</p>
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
