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
          {rows.map((row, index) => (
            <tr key={`${row[0]}-${index}`} className={String(row[0]).toUpperCase() === "TOTAL" ? "oaaps-total" : undefined}>
              {row.map((cell, cellIndex) => (
                <td key={`${columns[cellIndex]}-${cellIndex}`} className={cellIndex >= numericFrom ? "num" : undefined}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function metricRows(items) {
  return (items || []).map((row) => [row.indicator, fmtCount(row), fmtPct(row)]);
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
            <th>Total Graduates</th>
            <td>{header.total_graduates}</td>
            <th>Number of Graduates Traced</th>
            <td>{header.graduates_traced}</td>
          </tr>
          <tr>
            <th>Tracer Study Response Rate</th>
            <td colSpan={3}>{fmtPct(header.response_rate)}</td>
          </tr>
        </tbody>
      </table>

      <section className="oaaps-section">
        <h3>I. OVERALL GRADUATE PRODUCTIVITY</h3>
        <h4>A. Executive Summary</h4>
        <ReportTable columns={["Key Indicator", "Total", "Percentage"]} rows={metricRows(report.executive_summary)} />
        <p className="oaaps-rate">Overall Graduate Productivity Rate: {fmtRate(report.overall_productivity_rate)}</p>
        <p className="oaaps-formula">{report.formula}</p>

        <h4>B. Graduate Productivity Profile</h4>
        <p className="oaaps-profile">
          Total Graduates: <strong>{profile.total_graduates}</strong>
          <span>Traced Graduates: <strong>{profile.traced}</strong></span>
          <span>Productive Graduates: <strong>{profile.productive}</strong></span>
          <span>Not Yet Productively Engaged: <strong>{profile.not_yet_engaged}</strong></span>
        </p>
        <p className="oaaps-subhead">Productivity Distribution:</p>
        <ul className="oaaps-dist">
          <li>Workforce Integration: {fmtRate(dist.workforce)}</li>
          <li>Professional Advancement: {fmtRate(dist.professional)}</li>
          <li>Academic Advancement: {fmtRate(dist.academic)}</li>
        </ul>
      </section>

      <section className="oaaps-section">
        <h3>II. WORKFORCE INTEGRATION</h3>
        <p className="oaaps-desc">{workforce.description}</p>
        <h4>A. Employment Status</h4>
        <ReportTable
          columns={["Employment Indicator", "No. of Graduates", "%"]}
          rows={metricRows(workforce.employment_status)}
        />
        <h4>B. Employment Relevance</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(workforce.employment_relevance)} />
        <h4>C. Employment Quality</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(workforce.employment_quality)} />
        <h4>D. Time-to-Employment</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(workforce.time_to_employment)} />
        <p className="oaaps-rate">Key Workforce Integration Rate: {fmtRate(workforce.key_rate)}</p>
      </section>

      <section className="oaaps-section">
        <h3>III. PROFESSIONAL ADVANCEMENT</h3>
        <p className="oaaps-desc">{professional.description}</p>
        <h4>A. Career Progression</h4>
        <ReportTable
          columns={["Indicator", "No. of Graduates", "%"]}
          rows={metricRows(professional.career_progression)}
        />
        <h4>B. Professional Credentials and Development</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(professional.credentials)} />
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
        <p className="oaaps-rate">Professional Advancement Rate: {fmtRate(professional.key_rate)}</p>
      </section>

      <section className="oaaps-section">
        <h3>IV. ACADEMIC ADVANCEMENT</h3>
        <p className="oaaps-desc">{academic.description}</p>
        <h4>A. Further Education</h4>
        <ReportTable
          columns={["Academic Outcome", "No. of Graduates", "%"]}
          rows={metricRows(academic.further_education)}
        />
        <h4>B. Academic and Research Achievements</h4>
        <ReportTable columns={["Indicator", "No.", "%"]} rows={metricRows(academic.achievements)} />
        <p className="oaaps-rate">Academic Advancement Rate: {fmtRate(academic.key_rate)}</p>
      </section>

      <section className="oaaps-section">
        <h3>V. OVERALL GRADUATE PRODUCTIVITY SCORECARD</h3>
        <ReportTable
          columns={["Dimension", "Key Indicator", "Target", "Actual Rate", "Status"]}
          numericFrom={2}
          rows={(report.scorecard || []).map((row) => [
            row.dimension,
            row.key_indicator,
            row.target == null ? "Not Set" : row.target,
            fmtRate(row.actual_rate),
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
          rows={(report.by_program || []).map((row) => [
            row.college_program,
            row.batch_year,
            row.graduates,
            row.traced,
            fmtPct(row.workforce),
            fmtPct(row.professional),
            fmtPct(row.academic),
            fmtPct(row.overall_productivity),
          ])}
        />
      </section>

      <p className="oaaps-footnote">
        Indicators shown as — or Not Available are not collected in the current Graduate Tracer Survey and were not inferred.
        Alignment remains a status (Aligned, Unknown, Misaligned) and is not converted into a percentage score.
      </p>
    </article>
  );
}
