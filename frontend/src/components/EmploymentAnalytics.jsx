import { useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { MetricCard } from "./AdminOps";
import { Panel } from "./RecordViews";
import { Field, LoadError } from "./ui";
import { api } from "../lib/api";

const STATUS_COLOR = {
  Employed: "#0B2E59",
  Unemployed: "#B58A3A",
  "Unknown / Not Reported": "#8A94A6",
};

function programsForCollege(options, college) {
  const selected = String(college || "");
  const pairs = options?.pairs || [];
  if (!selected || !pairs.length) return options?.programs || [];
  const names = pairs.filter((item) => item.college === selected && item.program).map((item) => item.program);
  return [...new Set(names)].sort((left, right) => left.localeCompare(right));
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0";
  const rounded = Math.round(number * 100) / 100;
  return String(rounded);
}

function statusSummary(analytics) {
  if (!analytics?.total) return "No tracer records are available for the selected filters.";
  return (analytics.status || [])
    .map((item) => `${item.label}: ${item.count} graduates, ${formatPercent(item.percent)} percent`)
    .join(". ");
}

export default function EmploymentAnalytics({ filters, options, onCollege, onCourse, onYear, onClear }) {
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [loadedKey, setLoadedKey] = useState("");
  const courses = programsForCollege(options, filters.college);
  const filtersActive = Boolean(filters.college || filters.program || filters.year);
  const requestKey = `${filters.college}|${filters.program}|${filters.year}|${reloadKey}`;
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
  }, [filters.college, filters.program, filters.year, reloadKey]);

  const reasons = analytics?.reasons || [];
  const maxReason = reasons.reduce((max, item) => Math.max(max, item.count), 0);
  const rateHint = analytics?.unknown
    ? `${analytics.unknown} without an employment answer are excluded from this rate.`
    : "Employed divided by employed plus unemployed.";

  return (
    <section className="admin-reports-block" aria-labelledby="employment-overview-heading">
      <header className="admin-reports-section-head">
        <h2 id="employment-overview-heading">Employment Overview</h2>
      </header>
      <form className="filter-bar" onSubmit={(event) => event.preventDefault()}>
        <Field label="College">
          <select aria-label="Filter employment analytics by college" value={filters.college} onChange={(event) => onCollege(event.target.value)}>
            <option value="">All Colleges</option>
            {(options.colleges || []).map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </Field>
        <Field label="Course">
          <select aria-label="Filter employment analytics by course" value={courses.includes(filters.program) ? filters.program : ""} onChange={(event) => onCourse(event.target.value)}>
            <option value="">All Courses</option>
            {courses.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </Field>
        <Field label="Graduation year">
          <select aria-label="Filter employment analytics by graduation year" value={filters.year} onChange={(event) => onYear(event.target.value)}>
            <option value="">All years</option>
            {(options.years || []).map((year) => <option key={year} value={year}>{year}</option>)}
          </select>
        </Field>
        {filtersActive ? (
          <button className="btn btn-outline" type="button" onClick={onClear}>Clear Filters</button>
        ) : null}
      </form>

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
            <MetricCard label="Tracer records" value={analytics.total} hint="Latest official submission in this filter" />
            <MetricCard label="Employed" value={analytics.employed} hint="Answered currently employed" />
            <MetricCard label="Unemployed" value={analytics.unemployed} hint="Answered not currently employed" />
            <MetricCard label="Employment rate" value={`${formatPercent(analytics.employment_rate)}%`} hint={rateHint} />
          </div>
          <div className="admin-reports-charts">
            <Panel title="Employment Status">
              <div className="employment-status" role="img" aria-label={statusSummary(analytics)}>
                <div className="employment-donut">
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={analytics.status.filter((item) => item.count > 0)}
                        dataKey="count"
                        nameKey="label"
                        innerRadius={58}
                        outerRadius={84}
                        paddingAngle={analytics.status.filter((item) => item.count > 0).length > 1 ? 2 : 0}
                        stroke="#fff"
                      >
                        {analytics.status.filter((item) => item.count > 0).map((item) => (
                          <Cell key={item.label} fill={STATUS_COLOR[item.label] || "#0B2E59"} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value, name, item) => [`${value} graduates (${formatPercent(item?.payload?.percent)}%)`, name]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <ul className="employment-legend">
                  {analytics.status.map((item) => (
                    <li key={item.label}>
                      <span className="employment-swatch" style={{ background: STATUS_COLOR[item.label] || "#0B2E59" }} aria-hidden="true" />
                      <span>{item.label}</span>
                      <strong>{item.count}</strong>
                      <span>{formatPercent(item.percent)}%</span>
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
                      <li className="reason-row" key={item.label}>
                        <span className="reason-label">{item.label}</span>
                        <span className="reason-track" aria-hidden="true">
                          <span className="reason-fill" style={{ width: `${Math.max(6, Math.round((item.count / maxReason) * 100))}%` }} />
                        </span>
                        <span className="reason-count">{item.count}</span>
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
    </section>
  );
}

export { programsForCollege };
