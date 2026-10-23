import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { MetricCard, directoryPath } from "./AdminOps";
import { ChevronDownIcon, DownloadIcon } from "./icons";
import { Panel } from "./RecordViews";
import { Field, LoadError } from "./ui";
import { courseLabel } from "../lib/academicFilters";
import { api } from "../lib/api";

const STATUS_COLOR = {
  Employed: "#0B2E59",
  Unemployed: "#B58A3A",
  "Unknown / Not Reported": "#8A94A6",
};

const RATE_NOTE_ID = "employment-rate-note";

function programsForCollege(options, college) {
  const selected = String(college || "");
  const pairs = options?.pairs || [];
  const rows = selected ? pairs.filter((item) => item.college === selected) : pairs;
  const source = rows.length
    ? rows.filter((item) => item.program).map((item) => ({ program: item.program, kind: item.kind || "" }))
    : (options?.programs || []).map((name) => ({ program: name, kind: "" }));
  const seen = new Set();
  return source.filter((item) => {
    if (!item.program || seen.has(item.program)) return false;
    seen.add(item.program);
    return true;
  }).sort((left, right) => left.program.localeCompare(right.program));
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0";
  return String(Math.round(number * 100) / 100);
}

function formatRate(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0.00";
  return (Math.round(number * 100) / 100).toFixed(2);
}

function analyticsPath(filters, extra) {
  return directoryPath("reports", {
    cohort: "analytics",
    college: filters.college,
    program: filters.program,
    year: filters.year,
    location: filters.location,
    employment: filters.employment,
    ...extra,
  });
}

function statusAnswer(label) {
  if (label === "Employed") return "employed";
  if (label === "Unemployed") return "unemployed";
  return "unknown";
}

function statusSummary(analytics) {
  if (!analytics?.total) return "No tracer records are available for the selected filters.";
  return (analytics.status || [])
    .map((item) => `${item.label}: ${item.count} graduates, ${formatPercent(item.percent)} percent of the filtered total`)
    .join(". ");
}

function selectedChips(filters, courses) {
  const chips = [];
  if (filters.college) chips.push(["College", filters.college]);
  if (filters.program) {
    const match = courses.find((item) => item.program === filters.program);
    chips.push(["Course", match ? courseLabel(match) : filters.program]);
  }
  if (filters.year) chips.push(["Graduation year", filters.year]);
  if (filters.location) {
    chips.push(["Location", filters.location === "__none__" ? "No recorded location" : filters.location]);
  }
  if (filters.employment) {
    chips.push(["Status", filters.employment === "employed" ? "Employed" : "Unemployed"]);
  }
  return chips;
}

export default function EmploymentAnalytics({
  filters,
  options,
  onCollege,
  onCourse,
  onYear,
  onLocation,
  onEmployment,
  onClear,
  onDownload,
  downloading,
}) {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [loadedKey, setLoadedKey] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const courses = programsForCollege(options, filters.college);
  const filtersActive = Boolean(filters.college || filters.program || filters.year || filters.location || filters.employment);
  const chips = selectedChips(filters, courses);
  const requestKey = `${filters.college}|${filters.program}|${filters.year}|${filters.location}|${filters.employment}|${reloadKey}`;
  const ready = !busy && !error && loadedKey === requestKey;

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError("");
    setAnalytics(null);
    const params = new URLSearchParams();
    if (filters.college) params.set("college", filters.college);
    if (filters.program) params.set("course", filters.program);
    if (filters.year) params.set("year", filters.year);
    if (filters.location) params.set("location", filters.location);
    if (filters.employment) params.set("employment", filters.employment);
    const query = params.toString();
    api(`/api/admin/reports/employment${query ? `?${query}` : ""}`)
      .then((result) => {
        if (!cancelled) {
          setAnalytics(result);
          setLoadedKey(requestKey);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAnalytics(null);
          setLoadedKey(requestKey);
          setError("Unable to load employment analytics");
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters.college, filters.program, filters.year, filters.location, filters.employment, reloadKey]);

  const reasons = analytics?.reasons || [];
  const maxReason = reasons.reduce((max, item) => Math.max(max, item.count), 0);
  const rateHint = "Employed ÷ (employed + unemployed).";
  const rateTitle = analytics?.unknown
    ? `${analytics.unknown} without a Yes or No answer are in the total and the chart, and are left out of this rate.`
    : "Chart percentages use the filtered total. This rate uses employed and unemployed answers only.";

  return (
    <section className="admin-reports-block" aria-labelledby="employment-overview-heading">
      <header className="admin-reports-section-head">
        <div>
          <p className="admin-reports-kicker">Filtered tracer records</p>
          <h2 id="employment-overview-heading">Employment Overview</h2>
          <p>Latest tracer record for each alumnus. These filters stay separate from the OAAPS report.</p>
        </div>
      </header>

      <div className={`employment-filter-panel ${filtersOpen ? "is-open" : ""}`}>
        <div className="employment-filter-tools">
          <button
            className="btn btn-outline btn-sm employment-filter-toggle"
            type="button"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((open) => !open)}
          >
            <ChevronDownIcon size={16} />
            {filtersOpen ? "Hide filters" : "Show filters"}
          </button>
          {chips.length ? (
            <ul className="report-filter-chips" aria-label="Selected employment filters">
              {chips.map(([label, value]) => (
                <li className="report-filter-chip" key={label}>{label}: {value}</li>
              ))}
            </ul>
          ) : (
            <p className="employment-filter-all">All colleges, courses, years, locations, and employment statuses.</p>
          )}
          <button className="btn btn-outline btn-sm" type="button" onClick={onClear} disabled={!filtersActive}>
            Clear Employment Filters
          </button>
        </div>
        <form className="filter-bar" onSubmit={(event) => event.preventDefault()}>
          <Field label="College">
            <select aria-label="Filter employment analytics by college" value={filters.college} onChange={(event) => onCollege(event.target.value)}>
              <option value="">All Colleges</option>
              {(options.colleges || []).map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </Field>
          <Field label="Course">
            <select aria-label="Filter employment analytics by course" value={courses.some((item) => item.program === filters.program) ? filters.program : ""} onChange={(event) => onCourse(event.target.value)}>
              <option value="">All Courses</option>
              {courses.map((item) => <option key={item.program} value={item.program}>{courseLabel(item)}</option>)}
            </select>
          </Field>
          <Field label="Graduation year">
            <select aria-label="Filter employment analytics by graduation year" value={filters.year} onChange={(event) => onYear(event.target.value)}>
              <option value="">All years</option>
              {(options.years || []).map((year) => <option key={year} value={year}>{year}</option>)}
            </select>
          </Field>
          <Field label="Location">
            <select aria-label="Filter employment analytics by location" value={filters.location || ""} onChange={(event) => onLocation(event.target.value)}>
              <option value="">All locations</option>
              <option value="__none__">No recorded location</option>
              {(options.locations || []).map((city) => <option key={city} value={city}>{city}</option>)}
            </select>
          </Field>
          <Field label="Status of Employment">
            <select aria-label="Filter employment analytics by employment status" value={filters.employment || ""} onChange={(event) => onEmployment(event.target.value)}>
              <option value="">All statuses</option>
              <option value="employed">Employed</option>
              <option value="unemployed">Unemployed</option>
            </select>
          </Field>
        </form>
      </div>

      {busy || !ready && !error ? (
        <p className="employment-loading" role="status">Loading employment analytics…</p>
      ) : error ? (
        <LoadError title="Unable to load employment analytics" onRetry={() => setReloadKey((value) => value + 1)}>
          Please try again.
        </LoadError>
      ) : !analytics?.total ? (
        <div className="empty compact admin-reports-empty">
          <h3>Employment Status</h3>
          <p>No tracer records are available for the selected filters.</p>
        </div>
      ) : (
        <>
          <div className="admin-reports-metrics" aria-live="polite">
            <MetricCard label="Tracer records" value={analytics.total} hint="Latest official submission in this filter" cta="View students" to={analyticsPath(filters, { answer: "all" })} />
            <MetricCard label="Employed" value={analytics.employed} hint="Answered currently employed" cta="View students" to={analyticsPath(filters, { answer: "employed" })} />
            <MetricCard label="Unemployed" value={analytics.unemployed} hint="Answered not currently employed" cta="View students" to={analyticsPath(filters, { answer: "unemployed" })} />
            <MetricCard
              label="Employment rate"
              value={`${formatRate(analytics.employment_rate)}%`}
              hint={rateHint}
              title={rateTitle}
              describedBy={RATE_NOTE_ID}
              cta="View students"
              to={analyticsPath(filters, { answer: "known" })}
            />
          </div>
          <p className="notice-note" id={RATE_NOTE_ID}>
            Employment rate is employed divided by employed plus unemployed, to two decimal places.
            {analytics.unknown
              ? ` ${analytics.unknown} without a Yes or No answer stay in the tracer-record total and in the chart, and are left out of this rate.`
              : " Chart percentages are each category’s share of the filtered total, so they can differ from this rate when an answer is missing."}
          </p>
          <div className="admin-reports-charts">
            <Panel title="Employment Status">
              <div className="employment-status" role="img" aria-label={statusSummary(analytics)}>
                <div className="employment-donut">
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={analytics.status.filter((item) => item.count > 0)}
                        dataKey="count"
                        cursor="pointer"
                        onClick={(sector) => {
                          const label = sector?.label || sector?.payload?.label;
                          if (label) navigate(analyticsPath(filters, { answer: statusAnswer(label) }));
                        }}
                        nameKey="label"
                        innerRadius={54}
                        outerRadius={78}
                        paddingAngle={analytics.status.filter((item) => item.count > 0).length > 1 ? 2 : 0}
                        stroke="#fff"
                      >
                        {analytics.status.filter((item) => item.count > 0).map((item) => (
                          <Cell key={item.label} fill={STATUS_COLOR[item.label] || "#0B2E59"} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value, name, item) => [`${value} graduates (${formatPercent(item?.payload?.percent)}% of filtered total)`, name]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <ul className="employment-legend">
                  {analytics.status.map((item) => (
                    <li key={item.label}>
                      <Link className="employment-legend-link" to={analyticsPath(filters, { answer: statusAnswer(item.label) })}>
                        <span className="employment-swatch" style={{ background: STATUS_COLOR[item.label] || "#0B2E59" }} aria-hidden="true" />
                        <span>{item.label}</span>
                        <strong>{item.count}</strong>
                        <span>{formatPercent(item.percent)}%</span>
                        <span className="sr-only">View students</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </Panel>
            <Panel title="Reasons for Unemployment">
              {analytics.unemployed && reasons.length ? (
                <>
                  <ul className="reason-chart" aria-label="Reasons for unemployment">
                    {reasons.map((item) => (
                      <li key={item.label}>
                        <Link className="reason-row is-link" to={analyticsPath(filters, { answer: "unemployed", reason: item.label })}>
                          <span className="reason-label">{item.label}</span>
                          <span className="reason-track" aria-hidden="true">
                            <span className="reason-fill" style={{ width: `${Math.max(6, Math.round((item.count / maxReason) * 100))}%` }} />
                          </span>
                          <span className="reason-count">{item.count}</span>
                          <span className="sr-only">View students</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <p className="notice-note">A graduate who selected more than one reason is counted in each reason.</p>
                </>
              ) : (
                <div className="empty compact admin-reports-empty">
                  <h3>Reasons for Unemployment</h3>
                  <p>No unemployed graduate records are available for the selected filters.</p>
                </div>
              )}
            </Panel>
          </div>
        </>
      )}

      {ready ? (
        <div className="admin-reports-csv">
          <button className="btn btn-outline" type="button" disabled={downloading} onClick={onDownload}>
            <DownloadIcon size={16} />
            {downloading ? "Downloading…" : "Download CSV"}
          </button>
        </div>
      ) : null}
    </section>
  );
}

export { programsForCollege };
