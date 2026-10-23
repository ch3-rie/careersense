import { Link } from "react-router-dom";
import { directoryPath } from "./AdminOps";
import { ChevronRightIcon } from "./icons";

function fmtCount(row) {
  if (!row || row.available === false || row.count === null || row.count === undefined) return "—";
  return String(row.count);
}

function fmtPct(row) {
  if (!row || row.available === false || row.percentage === null || row.percentage === undefined) {
    return "Not Available";
  }
  return `${Number(row.percentage).toFixed(2)}%`;
}

function fmtRate(value) {
  if (value === null || value === undefined) return "Not Available";
  return `${Number(value).toFixed(2)}%`;
}

function cellLabel(cell) {
  if (typeof cell === "string" || typeof cell === "number") return String(cell);
  const nested = cell?.props?.children;
  if (typeof nested === "string" || typeof nested === "number") return String(nested);
  return "";
}

function ReportTable({ columns, rows, numericFrom = 1 }) {
  return (
    <div className="oaaps-table-wrap">
      <table className="oaaps-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const label = cellLabel(row[0]);
            return (
            <tr key={`${label}-${index}`} className={label.toUpperCase() === "TOTAL" ? "oaaps-total" : undefined}>
              {row.map((cell, cellIndex) => (
                <td key={`${columns[cellIndex]}-${cellIndex}`} className={cellIndex >= numericFrom ? "num" : undefined}>
                  {cell}
                </td>
              ))}
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function reportLink(report, indicator, scope) {
  const filters = report?.filters || {};
  const scoped = scope || {};
  return directoryPath("reports", {
    cohort: "productivity",
    indicator,
    college: scoped.college !== undefined ? scoped.college : filters.college,
    program: scoped.program !== undefined ? scoped.program : filters.program,
    year: scoped.year !== undefined ? scoped.year : filters.year,
    period_from: filters.period_from,
    period_to: filters.period_to,
    award: filters.award,
    further: filters.further,
  });
}

function FigureLink({ report, indicator, scope, children }) {
  const label = typeof children === "string" || typeof children === "number" ? String(children) : "";
  const unavailable = label === "—" || label === "Not Available";
  const accessible = unavailable
    ? `${indicator}, not available`
    : label === indicator
      ? `${indicator}. View students`
      : `${indicator}: ${label}. View students`;
  return (
    <Link
      className="oaaps-link"
      to={reportLink(report, indicator, scope)}
      aria-label={accessible}
    >
      {children}
      {unavailable ? null : <ChevronRightIcon className="oaaps-link-cue no-print" size={12} />}
    </Link>
  );
}

function metricRows(report, items) {
  return (items || []).map((row) => [
    <FigureLink report={report} indicator={row.indicator}>{row.indicator}</FigureLink>,
    <FigureLink report={report} indicator={row.indicator}>{row.available === false ? "—" : fmtCount(row)}</FigureLink>,
    <FigureLink report={report} indicator={row.indicator}>{fmtPct(row)}</FigureLink>,
  ]);
}

export default function OaapsReport({ report }) {
  if (!report) return null;
  const header = report.header || {};
  const profile = report.profile || {};
  const dist = report.distribution || {};
  const workforce = report.workforce || {};
  const professional = report.professional || {};
  const academic = report.academic || {};

  return (
    <article className="oaaps-document" id="oaaps-report">
      <header className="oaaps-masthead">
        <p className="oaaps-kicker">Angeles University Foundation</p>
        <h2>OVERALL GRADUATE PRODUCTIVITY REPORT</h2>
        <p className="oaaps-office">Office of Alumni Affairs and Placement Services (OAAPS)</p>
      </header>

      <div className="oaaps-table-wrap">
      <table className="oaaps-meta">
        <tbody>
          <tr>
            <th>Reporting Period</th>
            <td>{header.reporting_period}</td>
            <th>Graduating Batch/Cohort</th>
            <td>{header.batch_cohort}</td>
          </tr>
          <tr>
            <th>College/Program</th>
            <td colSpan={3}>{header.college_program}</td>
          </tr>
          <tr>
            <th>Awards Received</th>
            <td>{header.awards || "All"}</td>
            <th>Further Studies</th>
            <td>{header.further_studies || "All"}</td>
          </tr>
          <tr>
            <th>Total Graduates</th>
            <td><FigureLink report={report} indicator="Total Graduates">{header.total_graduates}</FigureLink></td>
            <th>Number of Graduates Traced</th>
            <td><FigureLink report={report} indicator="Graduates Traced">{header.graduates_traced}</FigureLink></td>
          </tr>
          <tr>
            <th>Tracer Study Response Rate</th>
            <td colSpan={3}><FigureLink report={report} indicator="Graduates Traced">{fmtPct(header.response_rate)}</FigureLink></td>
          </tr>
        </tbody>
      </table>
      </div>

      <section className="oaaps-section">
        <h3>I. OVERALL GRADUATE PRODUCTIVITY</h3>
        <h4>A. Executive Summary</h4>
        <ReportTable columns={["Key Indicator", "Total", "Percentage"]} rows={metricRows(report, report.executive_summary)} />
        <p className="oaaps-rate">Overall Graduate Productivity Rate: <FigureLink report={report} indicator="Overall Graduate Productivity Rate">{fmtRate(report.overall_productivity_rate)}</FigureLink></p>
        <p className="oaaps-formula">{report.formula}</p>

        <h4>B. Graduate Productivity Profile</h4>
        <p className="oaaps-profile">
          Total Graduates: <FigureLink report={report} indicator="Total Graduates">{profile.total_graduates}</FigureLink>
          <span>Traced Graduates: <FigureLink report={report} indicator="Traced Graduates">{profile.traced}</FigureLink></span>
          <span>Productive Graduates: <FigureLink report={report} indicator="Productive Graduates">{profile.productive}</FigureLink></span>
          <span>Not Yet Productively Engaged: <FigureLink report={report} indicator="Not Yet Productively Engaged">{profile.not_yet_engaged}</FigureLink></span>
        </p>
        <p className="oaaps-subhead">Productivity Distribution:</p>
        <ul className="oaaps-dist">
          <li><FigureLink report={report} indicator="Workforce Integration">Workforce Integration: {fmtRate(dist.workforce)}</FigureLink></li>
          <li><FigureLink report={report} indicator="Professional Advancement">Professional Advancement: {fmtRate(dist.professional)}</FigureLink></li>
          <li><FigureLink report={report} indicator="Academic Advancement">Academic Advancement: {fmtRate(dist.academic)}</FigureLink></li>
        </ul>
      </section>

      <section className="oaaps-section">
        <h3>II. WORKFORCE INTEGRATION</h3>
        <p className="oaaps-desc">{workforce.description}</p>
        <h4>A. Employment Status</h4>
        <ReportTable
          columns={["Employment Indicator", "No. of Graduates", "%"]}
          rows={metricRows(report, workforce.employment_status)}
        />
        <h4>B. Employment Relevance</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(report, workforce.employment_relevance)} />
        <h4>C. Employment Quality</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(report, workforce.employment_quality)} />
        <h4>D. Time-to-Employment</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(report, workforce.time_to_employment)} />
        <p className="oaaps-rate">Key Workforce Integration Rate: <FigureLink report={report} indicator="Workforce Integration">{fmtRate(workforce.key_rate)}</FigureLink></p>
      </section>

      <section className="oaaps-section">
        <h3>III. PROFESSIONAL ADVANCEMENT</h3>
        <p className="oaaps-desc">{professional.description}</p>
        <h4>A. Career Progression</h4>
        <ReportTable
          columns={["Indicator", "No. of Graduates", "%"]}
          rows={metricRows(report, professional.career_progression)}
        />
        <h4>B. Professional Credentials and Development</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(report, professional.credentials)} />
        <h4>C. Professional Recognition</h4>
        <p className="oaaps-subhead">Top Graduate Achievements:</p>
        <div className="oaaps-table-wrap">
          <table className="oaaps-table">
            <thead>
              <tr>
                <th>Graduate</th>
                <th>Program/Batch</th>
                <th>Organization</th>
                <th>Position/Achievement</th>
                <th>Year</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={5} className="oaaps-empty">
                  Not Available — CareerSense does not currently collect structured achievement records.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="oaaps-rate">Professional Advancement Rate: <FigureLink report={report} indicator="Professional Advancement">{fmtRate(professional.key_rate)}</FigureLink></p>
      </section>

      <section className="oaaps-section">
        <h3>IV. ACADEMIC ADVANCEMENT</h3>
        <p className="oaaps-desc">{academic.description}</p>
        <h4>A. Further Education</h4>
        <ReportTable
          columns={["Academic Outcome", "No. of Graduates", "%"]}
          rows={metricRows(report, academic.further_education)}
        />
        <h4>B. Academic and Research Achievements</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(report, academic.achievements)} />
        <p className="oaaps-rate">Academic Advancement Rate: <FigureLink report={report} indicator="Academic Advancement">{fmtRate(academic.key_rate)}</FigureLink></p>
      </section>

      <section className="oaaps-section">
        <h3>V. OVERALL GRADUATE PRODUCTIVITY SCORECARD</h3>
        <ReportTable
          columns={["Dimension", "Key Indicator", "Target", "Actual Rate", "Status"]}
          numericFrom={2}
          rows={(report.scorecard || []).map((row) => [
            row.dimension,
            <FigureLink report={report} indicator={row.key_indicator}>{row.key_indicator}</FigureLink>,
            row.target == null ? "Not Set" : row.target,
            <FigureLink report={report} indicator={row.key_indicator}>{fmtRate(row.actual_rate)}</FigureLink>,
            row.status == null ? "Not Set" : row.status,
          ])}
        />
        <p className="oaaps-subhead">Overall Productivity Formula</p>
        <p className="oaaps-formula oaaps-formula-block">
          Overall Graduate Productivity Rate =
          Number of graduates with at least one productivity outcome
          ÷ Number of graduates successfully traced
          × 100
        </p>
      </section>

      <section className="oaaps-section">
        <h3>VI. GRADUATE PRODUCTIVITY BY COLLEGE/PROGRAM/YEAR</h3>
        <ReportTable
          columns={[
            "College/Program",
            "Batch Year",
            "Graduates",
            "Traced",
            "Workforce",
            "Professional",
            "Academic",
            "Overall Productivity",
          ]}
          numericFrom={1}
          rows={(report.by_program || []).map((row) => {
            const scope = row.is_total ? undefined : { college: row.college, program: row.program, year: row.batch_year };
            return [
              <FigureLink report={report} indicator="Graduates Traced" scope={scope}>{row.college_program}</FigureLink>,
              row.batch_year,
              <FigureLink report={report} indicator="Total Graduates" scope={scope}>{row.graduates}</FigureLink>,
              <FigureLink report={report} indicator="Graduates Traced" scope={scope}>{row.traced}</FigureLink>,
              <FigureLink report={report} indicator="Workforce Integration" scope={scope}>{fmtPct(row.workforce)}</FigureLink>,
              <FigureLink report={report} indicator="Professional Advancement" scope={scope}>{fmtPct(row.professional)}</FigureLink>,
              <FigureLink report={report} indicator="Academic Advancement" scope={scope}>{fmtPct(row.academic)}</FigureLink>,
              <FigureLink report={report} indicator="Overall Graduate Productivity Rate" scope={scope}>{fmtPct(row.overall_productivity)}</FigureLink>,
            ];
          })}
        />
      </section>

      <p className="oaaps-footnote">
        Indicators shown as — or Not Available are not collected in the current Graduate Tracer Survey and were not inferred.
        Alignment remains a status (Aligned, Unknown, Misaligned) and is not converted into a percentage score.
      </p>
    </article>
  );
}
