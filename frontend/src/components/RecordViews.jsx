import { useState } from "react";
import { Badge, TabList } from "./ui";
import {
  displayValue,
  formatDate,
  formatDateTime,
  formatTime,
  fullName,
  ratingLabel,
  suggestionLabel,
} from "../lib/format";

function isEmpty(value) {
  if (value === true || value === false) return false;
  if (Array.isArray(value)) return !value.length;
  return value === null || value === undefined || value === "" || value === "—";
}

export function DefinitionList({ items, compact = false }) {
  const rows = (items || []).filter((item) => {
    if (!item?.label) return false;
    if (!compact) return true;
    return !isEmpty(item.value) && item.value !== "—";
  });
  if (!rows.length) return <p className="muted">No details recorded.</p>;
  return (
    <dl className="deflist">
      {rows.map((item, index) => (
        <div className="deflist-row" key={`${item.label}-${index}`}>
          <dt>{item.label}</dt>
          <dd>{item.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function TagList({ items, empty = "None listed", compact = false, maxVisible = 4 }) {
  const tags = (items || []).filter(Boolean);
  const [expanded, setExpanded] = useState(false);
  if (!tags.length) return <p className="muted">{empty}</p>;
  const hidden = compact && !expanded ? Math.max(0, tags.length - maxVisible) : 0;
  const shown = hidden ? tags.slice(0, maxVisible) : tags;
  return (
    <div className="tags">
      {shown.map((tag, index) => (
        <span className="tag" key={`${tag}-${index}`} title={String(tag)}>{tag}</span>
      ))}
      {hidden ? (
        <button type="button" className="tag-more" onClick={() => setExpanded(true)} title={tags.slice(maxVisible).join(", ")}>
          +{hidden} more
        </button>
      ) : null}
      {compact && expanded && tags.length > maxVisible ? (
        <button type="button" className="tag-more" onClick={() => setExpanded(false)}>Show less</button>
      ) : null}
    </div>
  );
}

export function Panel({ title, description, actions, children, id, className = "", panelRef }) {
  return (
    <section className={`card panel ${className}`.trim()} id={id} ref={panelRef}>
      {(title || actions) && (
        <header className="panel-head">
          <div>
            {title ? <h2 tabIndex={-1}>{title}</h2> : null}
            {description ? <p className="lead">{description}</p> : null}
          </div>
          {actions ? <div className="panel-actions">{actions}</div> : null}
        </header>
      )}
      {children}
    </section>
  );
}

export function ProgressBar({ value, label }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div>
      {label ? <div className="progress-label"><span>{label}</span><strong>{pct}%</strong></div> : null}
      <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function StudiesList({ studies }) {
  const rows = (studies || []).filter((row) => row && (row.course_degree || row.school || row["Course/Degree"]));
  if (!rows.length) return <p className="muted">No further studies recorded.</p>;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Program</th>
            <th>School</th>
            <th>Year enrolled</th>
            <th>Scholarship</th>
            <th>Graduated</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id || index}>
              <td>{row.course_degree || row["Course/Degree"] || "—"}</td>
              <td>{row.school || row.School || "—"}</td>
              <td>{row.year_enrolled || row["Year of First Enrollment"] || "—"}</td>
              <td>{row.scholarship || row.Scholarship || "—"}</td>
              <td>{displayValue(row.is_graduated ?? row.Graduated)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExperienceList({ experiences }) {
  const rows = experiences || [];
  if (!rows.length) return <p className="muted">No work history extracted.</p>;
  return (
    <ol className="timeline">
      {rows.map((job, index) => (
        <li key={`${job.job_title}-${index}`}>
          <div className="timeline-dot" />
          <div>
            <strong>{job.job_title || "Untitled role"}</strong>
            <p className="muted">{[job.employer, job.is_current === "Yes" ? "Current role" : null].filter(Boolean).join(" · ")}</p>
            <p className="muted">
              {[job.start_date, job.end_date || (job.is_current === "Yes" ? "Present" : "")].filter(Boolean).join(" – ")}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function extraLabel(key, labels = {}) {
  if (key === "_survey_version" || key === "_extra_labels") return "";
  return labels[key] || labels[String(key)] || String(key).replace(/_/g, " ");
}

export function ExtraAnswers({ answers, questionLabels }) {
  const storedLabels = answers?._extra_labels && typeof answers._extra_labels === "object" ? answers._extra_labels : {};
  const labels = { ...storedLabels, ...(questionLabels || {}) };
  const entries = Object.entries(answers || {}).filter(([key, value]) => key !== "_extra_labels" && key !== "_survey_version" && !isEmpty(value));
  if (!entries.length) return null;
  return (
    <section>
      <h3>Additional questions</h3>
      <DefinitionList
        items={entries.map(([key, value]) => ({
          label: extraLabel(key, labels),
          value: Array.isArray(value) ? value.join(", ") : displayValue(value),
        }))}
      />
    </section>
  );
}

export function TracerRecord({
  data = {},
  extra,
  alignment,
  submittedAt,
  compact = false,
  nested = false,
  stacked = false,
  questionLabels,
  soc,
}) {
  const [tab, setTab] = useState("overview");
  const suggestions = Object.entries(data.curriculum_suggestions || {}).filter(([, value]) => value);
  const studies = data.further_studies || [];
  const skills = data.skills || [];
  const extraAnswers = extra || data.extra_answers;
  const socCode = soc?.code || data.soc_code;
  const socDescription = soc?.description || data.soc_description;
  const socCategory = soc?.category || data.soc_category;

  const tabs = [
    ["overview", "Overview"],
    ["employment", "Employment"],
    ["studies", "Studies"],
    ["feedback", "Feedback"],
  ];

  const personal = (
    <section>
      <h3>Survey responses</h3>
      <DefinitionList
        compact={compact}
        items={[
          { label: "Given name", value: displayValue(data.first_name) },
          { label: "Middle name", value: displayValue(data.middle_name) },
          { label: "Last name", value: displayValue(data.last_name) },
          { label: "Country of residence", value: displayValue(data.country) },
          { label: "Degree", value: displayValue(data.degree) },
          { label: "Year graduated", value: displayValue(data.year_graduated) },
          { label: "Primary guardian", value: displayValue(data.primary_guardian) },
          { label: "Skills", value: skills.length ? skills.join(", ") : "—" },
        ]}
      />
    </section>
  );

  const employment = (
    <section>
      <h3>Employment</h3>
      <DefinitionList
        compact={compact}
        items={[
          { label: "Job title", value: displayValue(data.pres_occ || data.first_occ || data.current_occupation) },
          { label: "Employer", value: displayValue(data.pres_emp || data.first_emp || data.current_employer) },
          { label: "Employment status", value: displayValue(data.is_currently_employed || data.first_stat) },
          { label: "Ever employed after graduation", value: displayValue(data.ever_employed) },
          { label: "Time to first job", value: displayValue(data.time_to_first_job) },
          { label: "First job related to degree", value: displayValue(data.first_related) },
          { label: "How first job was found", value: displayValue(data.find_job || data.other_find_job) },
          { label: "First occupation", value: displayValue(data.first_occ) },
          { label: "First employer", value: displayValue(data.first_emp) },
          { label: "First salary range", value: displayValue(data.first_sal) },
          { label: "First employment status", value: displayValue(data.first_stat) },
          { label: "Currently employed", value: displayValue(data.is_currently_employed) },
          { label: "Present job is first job", value: displayValue(data.present_job_is_first) },
          { label: "Immediate head", value: displayValue(data.pres_head) },
          { label: "Length of stay", value: displayValue(data.pres_stay) },
          { label: "Present job related to degree", value: displayValue(data.present_related_degree) },
        ]}
      />
      {(data.reason_past || []).length ? (
        <div>
          <p className="field-caption">Reasons not employed after graduation</p>
          <TagList items={data.reason_past} />
          {data.reason_past_other ? <p>{data.reason_past_other}</p> : null}
        </div>
      ) : null}
      {(data.reason_current || []).length ? (
        <div>
          <p className="field-caption">Reasons not currently employed</p>
          <TagList items={data.reason_current} />
          {data.reason_current_other ? <p>{data.reason_current_other}</p> : null}
        </div>
      ) : null}
    </section>
  );

  const studiesBlock = (
    <section>
      <h3>Further studies</h3>
      <p className="muted">Enrolled after graduation: {displayValue(data.enroll_further_studies)}</p>
      <StudiesList studies={studies} />
    </section>
  );

  const extraBlock = extraAnswers && Object.keys(extraAnswers).length ? (
    <ExtraAnswers answers={extraAnswers} questionLabels={{ ...(data._extra_labels || {}), ...questionLabels }} />
  ) : null;

  const alignmentBlock = (
    <section>
      <h3>Alignment</h3>
      <DefinitionList
        items={[
          { label: "Classification", value: alignment ? <Badge tone={alignment}>{alignment}</Badge> : "—" },
          { label: "Matched occupation / SOC", value: [socCode, socDescription].filter(Boolean).join(" · ") || "—" },
          { label: "Category", value: displayValue(socCategory) },
        ]}
      />
    </section>
  );

  const submissionBlock = submittedAt ? (
    <section>
      <h3>Submission</h3>
      <DefinitionList
        items={[
          { label: "Submitted date", value: formatDate(submittedAt) },
          { label: "Submitted time", value: formatTime(submittedAt) },
        ]}
      />
    </section>
  ) : null;

  const feedbackBlock = (
    <section>
      <h3>Institutional feedback</h3>
      <DefinitionList
        compact={compact}
        items={[
          { label: "Participated in AUF career seminars", value: displayValue(data.participated_seminars) },
          { label: "Seminars were helpful", value: displayValue(data.seminars_helpful) },
          { label: "Inspired to mentor others", value: ratingLabel(data.mentoring_rating) },
          { label: "Inspired to join advocacy groups", value: ratingLabel(data.advocacy_rating) },
          { label: "Inspired to volunteer", value: ratingLabel(data.volunteering_rating) },
        ]}
      />
      {data.engagement_desc ? <blockquote className="quote">{data.engagement_desc}</blockquote> : null}
      {suggestions.length ? (
        <div>
          <p className="field-caption">Curriculum suggestions</p>
          <DefinitionList
            items={suggestions.map(([key, value]) => ({ label: suggestionLabel(key), value }))}
          />
        </div>
      ) : null}
    </section>
  );

  if (stacked) {
    return (
      <div className="record-view stacked-record">
        {employment}
        {personal}
        {studiesBlock}
        {feedbackBlock}
        {extraBlock}
        {alignmentBlock}
        {submissionBlock}
      </div>
    );
  }

  return (
    <div className="record-view">
      <div className="record-hero">
        <div>
          <p className="eyebrow">Tracer record</p>
          <h3>{fullName(data)}</h3>
          <p className="muted">
            {[data.degree, data.year_graduated && `Class of ${data.year_graduated}`, data.country].filter(Boolean).join(" · ") || "No education details yet"}
          </p>
        </div>
        <div className="record-meta">
          {alignment ? <Badge tone={alignment}>{alignment}</Badge> : null}
          {submittedAt ? <span className="muted">Submitted {formatDateTime(submittedAt)}</span> : null}
        </div>
      </div>

      {nested ? <p className="section-label">Sections in this tracer record</p> : null}
      <TabList
        label={nested ? "Tracer record sections" : "Tracer record"}
        value={tab}
        onChange={setTab}
        tabs={tabs}
        appearance={nested ? "sub" : "primary"}
      />

      {tab === "overview" && (
        <div className="record-grid">
          <section>
            <h3>Personal information</h3>
            <DefinitionList
              compact={compact}
              items={[
                { label: "Given name", value: displayValue(data.first_name) },
                { label: "Middle name", value: displayValue(data.middle_name) },
                { label: "Last name", value: displayValue(data.last_name) },
                { label: "Husband's surname", value: displayValue(data.husband_surname) },
                { label: "Country of residence", value: displayValue(data.country) },
                { label: "Primary guardian", value: displayValue(data.primary_guardian) },
                { label: "Guardian completed college", value: displayValue(data.guardian_degree_completed) },
              ]}
            />
          </section>
          <section>
            <h3>Skills</h3>
            <TagList items={skills} empty="No skills recorded." />
            {(socCode || socDescription) && (
              <>
                <h3 style={{ marginTop: 20 }}>Occupational classification</h3>
                <DefinitionList
                  compact={compact}
                  items={[
                    { label: "PSOC / SOC code", value: displayValue(socCode) },
                    { label: "Classification", value: displayValue(socDescription) },
                    { label: "Category", value: displayValue(socCategory) },
                  ]}
                />
              </>
            )}
          </section>
        </div>
      )}

      {tab === "employment" && employment}

      {tab === "studies" && studiesBlock}

      {tab === "feedback" && (
        <>
          {feedbackBlock}
          {extraBlock}
        </>
      )}
    </div>
  );
}

export function ResumeExtract({ parsed = {}, alignment, gts = {}, parserSource, suggestion = false, embedded = false }) {
  const studies = parsed.further_studies || gts.further_studies || [];
  const skills = parsed.skills || gts.skills || [];
  const name = fullName(parsed);
  const degree = parsed.degree || gts.degree;
  const year = parsed.year_graduated || gts.year_graduated;
  return (
    <div className={`record-view resume-extract${embedded ? " is-embedded" : ""}`}>
      {embedded ? null : (
        <div className="record-hero">
          <div>
            <p className="eyebrow">{suggestion ? "Suggested from resume" : "Extracted from resume"}</p>
            <h3>{name === "—" ? "Name not detected" : name}</h3>
            <p className="muted">{degree || "Degree not detected"}{year ? ` · Class of ${year}` : ""}</p>
          </div>
          <div className="record-meta">
            {suggestion ? <span className="source-badge">Suggested from uploaded resume</span> : null}
            {!suggestion && alignment?.status ? <Badge tone={alignment.status}>{alignment.status}</Badge> : null}
            {parserSource && parserSource !== "—" ? <span className="muted">{parserSource}</span> : null}
          </div>
        </div>
      )}
      {embedded ? (
        <div className="resume-extract-identity">
          <h3>{name === "—" ? "Name not detected" : name}</h3>
          <p className="muted">{degree || "Degree not detected"}{year ? ` · Class of ${year}` : ""}</p>
          {parserSource && parserSource !== "—" ? <p className="muted">{parserSource}</p> : null}
        </div>
      ) : null}
      {suggestion ? (
        <p className="muted">These values are suggestions only. They do not replace your submitted tracer record until you review and save the survey.</p>
      ) : alignment?.detail ? <p>{alignment.detail}</p> : null}
      <div className="record-grid">
        <section>
          <h3>Education</h3>
          <DefinitionList
            items={[
              { label: "Degree", value: displayValue(degree) },
              { label: "Year graduated", value: displayValue(year) },
              { label: "Country of residence", value: displayValue(parsed.country || gts.country) },
            ]}
          />
        </section>
        <section>
          <h3>Current occupation</h3>
          <DefinitionList
            items={[
              { label: "Occupation", value: displayValue(gts.pres_occ || gts.first_occ || parsed.current_occupation) },
              { label: "Employer", value: displayValue(gts.pres_emp || gts.first_emp || parsed.current_employer) },
              { label: "Currently employed", value: displayValue(parsed.is_currently_employed || gts.is_currently_employed) },
            ]}
          />
        </section>
      </div>
      <section>
        <h3>Skills</h3>
        <TagList items={skills} empty="No skills detected." />
      </section>
      <section>
        <h3>Work history</h3>
        <ExperienceList experiences={parsed.experiences} />
      </section>
      {Array.isArray(studies) && studies.length ? (
        <section>
          <h3>Further studies</h3>
          <StudiesList studies={studies} />
        </section>
      ) : null}
    </div>
  );
}

export function ProfileCard({ user = {}, profile = {} }) {
  return (
    <div className="record-view">
      <div className="record-hero">
        <div>
          <p className="eyebrow">{user.role === "Admin" ? "Administrator" : "Alumni account"}</p>
          <h3>{fullName(profile)}</h3>
          <p className="muted">{user.email}</p>
        </div>
        <Badge tone={user.status}>{user.status}</Badge>
      </div>
      <DefinitionList
        items={[
          { label: "Student ID", value: displayValue(user.student_id || "Not linked") },
          { label: "Degree", value: displayValue(profile.degree) },
          { label: "Year graduated", value: displayValue(profile.year_graduated) },
          { label: "Country", value: displayValue(profile.country_residence) },
          { label: "Primary guardian", value: displayValue(profile.guardian_type) },
          { label: "Guardian completed college", value: displayValue(profile.guardian_degree_completed) },
          { label: "Member since", value: formatDateTime(user.created_at) },
        ]}
      />
    </div>
  );
}
