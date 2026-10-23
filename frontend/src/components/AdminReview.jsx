import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CheckIcon,
  ChevronLeftIcon,
  DownloadIcon,
  FileIcon,
  LockIcon,
  XIcon,
} from "./icons";
import { Alert, Badge, Dialog, ExpandDetails, Field } from "./ui";
import { api, downloadAuthorized } from "../lib/api";
import { safeHttpUrl } from "../lib/safeUrl";
import { friendlyError } from "../lib/userMessages";
import {
  displayValue,
  formatLongDate,
  formatTime,
  fullName,
  questionLabelsFrom,
  ratingLabel,
  suggestionLabel,
} from "../lib/format";

export function openAdminTab(path) {
  const url = path.startsWith("http") ? path : `${window.location.origin}${path}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

export function registrationStatusLabel(status) {
  if (status === "Active") return "Approved";
  return status || "Pending";
}

export function isPendingRegistration(detail) {
  return (detail?.account?.status || "Pending") === "Pending";
}

export function applicantName(detail) {
  if (!detail) return "";
  const name = fullName(detail.profile || {});
  return name !== "—" ? name : detail.account?.email || "";
}

export function verifyType(verify) {
  return verify?.match_type || (verify?.matched ? "student_id" : "none");
}

export function verifyShortLabel(verify) {
  return (
    {
      student_id: "Matched by Student ID",
      email_name: "Matched by Email or Name",
      already_linked: "Already Linked",
      none: "No Match Found",
    }[verifyType(verify)] || "No Match Found"
  );
}

export function verifySummaryValue(verify) {
  return verifyShortLabel(verify);
}

export function alignmentLabel(value) {
  const tone = String(value || "Unknown").trim().toLowerCase() || "unknown";
  if (tone === "aligned") return "✓ Aligned";
  if (tone === "misaligned") return "× Misaligned";
  return "! Unknown";
}

function alignmentTone(value) {
  const tone = String(value || "Unknown").trim().toLowerCase();
  if (tone === "aligned" || tone === "misaligned") return tone;
  return "unknown";
}

function relatednessLabel(value) {
  if (value === "Yes") return "Related";
  if (value === "No") return "Not related";
  return displayValue(value);
}

function isFilled(value) {
  if (value === true || value === false) return true;
  if (Array.isArray(value)) return value.length > 0;
  return value !== null && value !== undefined && value !== "" && value !== "—";
}

function studyRows(studies) {
  return (studies || []).filter((row) => row && (row.course_degree || row.school || row["Course/Degree"]));
}

export function tracerFromApproval(detail) {
  const sub = detail?.submission;
  if (!sub) return null;
  const data = sub.data || {};
  return {
    ...sub,
    email: detail.account?.email,
    alignment: sub.alignment || sub.alignment_status,
    job_title: sub.job_title || data.pres_occ || data.first_occ || data.current_occupation || "",
    employer: sub.employer || data.pres_emp || data.first_emp || data.current_employer || "",
    employment_status: sub.employment_status || data.is_currently_employed || data.first_stat || "",
    soc_code: sub.soc_code || data.soc_code || "",
    soc_description: sub.soc_description || data.soc_description || "",
    soc_category: sub.soc_category || data.soc_category || "",
    extra_answers: sub.extra_answers || data.extra_answers || {},
    submitted_at: sub.submitted_at,
    data,
  };
}

export function StatusBadge({ kind = "account", value }) {
  const text = String(value || "").trim() || "Unknown";
  if (kind === "alignment") {
    const tone = alignmentTone(text);
    const icon =
      tone === "aligned" ? <CheckIcon size={14} /> : tone === "misaligned" ? <XIcon size={14} /> : <AlertTriangleIcon size={14} />;
    return (
      <Badge tone={text} icon={icon}>
        {text}
      </Badge>
    );
  }
  if (kind === "tracer") {
    const yes = Boolean(value);
    return <Badge tone={yes ? "defined" : "not-yet"}>{yes ? "Yes" : "No"}</Badge>;
  }
  return <Badge tone={text}>{text}</Badge>;
}

export function VerifyBanner({ verify, compact = false }) {
  const map = {
    student_id: {
      tone: "ok",
      icon: <CheckCircleIcon size={compact ? 18 : 20} />,
      title: "Matched by Student ID",
      text: "This student ID matches a graduate registry record.",
    },
    email_name: {
      tone: "info",
      icon: <AlertTriangleIcon size={compact ? 18 : 20} />,
      title: "Matched by Email or Name",
      text: "A registry record was matched through email or name. Confirm the details before deciding.",
    },
    already_linked: {
      tone: "warn",
      icon: <AlertTriangleIcon size={compact ? 18 : 20} />,
      title: "Already Linked",
      text: "This registry record is linked to another account and must not be attached to this applicant.",
    },
    none: {
      tone: "error",
      icon: <AlertTriangleIcon size={compact ? 18 : 20} />,
      title: "No Match Found",
      text: "No matching graduate registry record was found.",
    },
  };
  const state = map[verifyType(verify)] || map.none;
  return (
    <div className={`verify-banner ${state.tone} ${compact ? "compact" : ""}`} role="status">
      <span className="verify-icon" aria-hidden="true">{state.icon}</span>
      <div>
        <strong>{state.title}</strong>
        <p>{state.text}</p>
      </div>
    </div>
  );
}

export function ApplicantSummary({ detail }) {
  if (!detail) return null;
  const account = detail.account || {};
  const linked = String(account.student_id || "").trim();
  return (
    <section className="applicant-summary" aria-label="Applicant summary">
      <div className="applicant-summary-id">
        <h3>{applicantName(detail) || "Applicant"}</h3>
        <p>{account.email || "—"}</p>
      </div>
      <dl>
        <div>
          <dt>Student ID</dt>
          <dd>{linked ? linked : <span className="id-unlinked">Unlinked</span>}</dd>
        </div>
        <div>
          <dt>Account status</dt>
          <dd><StatusBadge value={account.status || "Pending"} /></dd>
        </div>
        <div>
          <dt>Registered</dt>
          <dd>{formatLongDate(account.created_at)}</dd>
        </div>
      </dl>
    </section>
  );
}

export function OfficialMark() {
  return (
    <span className="official-mark">
      <LockIcon size={14} />
      Official AUF Record
    </span>
  );
}

export function FileCard({ filename, uploadedAt, onDownload }) {
  const ext = String(filename || "").split(".").pop()?.toUpperCase() || "FILE";
  return (
    <article className="file-card">
      <span className="file-card-icon" aria-hidden="true"><FileIcon size={18} /></span>
      <div className="file-card-copy">
        <strong>{filename || "Resume"}</strong>
        <p>{ext} · Uploaded {formatLongDate(uploadedAt)}</p>
      </div>
      <button className="btn btn-outline btn-sm" type="button" onClick={onDownload}>
        <DownloadIcon size={16} />
        Download
      </button>
    </article>
  );
}

export function InfoGrid({ items }) {
  const rows = (items || []).filter((item) => item?.label);
  if (!rows.length) return <p className="muted">No details recorded.</p>;
  return (
    <dl className="info-grid">
      {rows.map((item, index) => (
        <div className="info-row" key={`${item.label}-${index}`}>
          <dt>{item.label}</dt>
          <dd>{isFilled(item.value) ? item.value : "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ReviewSummary({ items }) {
  const rows = (items || []).filter((item) => item?.label);
  if (!rows.length) return null;
  return (
    <div className="summary-strip">
      {rows.map((item) => (
        <div className="summary-block" key={item.label}>
          <span>{item.label}</span>
          <strong>{isFilled(item.value) ? item.value : "—"}</strong>
        </div>
      ))}
    </div>
  );
}

function ExpandableAnswer({ children }) {
  const [open, setOpen] = useState(false);
  const text = children == null || children === "—" ? "" : String(children);
  if (text.length < 220) return <div className="qa-a">{isFilled(children) ? children : "—"}</div>;
  return (
    <div className="qa-a">
      <div className={open ? "" : "qa-clamp"}>{children}</div>
      <button className="qa-more" type="button" onClick={() => setOpen((value) => !value)}>
        {open ? "Show less" : "Show more"}
      </button>
    </div>
  );
}

function QaList({ items, compact = false }) {
  const rows = (items || []).filter((item) => {
    if (!item?.label) return false;
    if (!compact) return true;
    return isFilled(item.value);
  });
  if (!rows.length) return <p className="muted">No details recorded.</p>;
  return (
    <div className="qa-list">
      {rows.map((item, index) => (
        <div className="qa-item" key={`${item.label}-${index}`}>
          <p className="qa-q">{item.label}</p>
          <ExpandableAnswer>{item.value}</ExpandableAnswer>
        </div>
      ))}
    </div>
  );
}

function extraLabel(key, labels = {}) {
  return labels[key] || labels[String(key)] || String(key).replace(/_/g, " ");
}

export function AlignmentHero({ record }) {
  const data = record?.data || {};
  const status = record?.alignment || "Unknown";
  const tone = alignmentTone(status);
  const job = record?.job_title || data.pres_occ || data.first_occ || "";
  const occupation = record?.soc_description || "";
  const supporting = job && occupation ? `${job} → ${occupation}` : occupation;
  const classification = [record?.soc_code, record?.soc_category].filter(Boolean).join(" · ");
  const icon =
    tone === "aligned" ? <CheckCircleIcon size={22} /> : tone === "misaligned" ? <XIcon size={22} /> : <AlertTriangleIcon size={22} />;

  return (
    <section className="review-block">
      <h3>Employment Alignment</h3>
      <div className={`alignment-hero ${tone}`}>
        <span className="alignment-hero-icon" aria-hidden="true">{icon}</span>
        <div>
          <p className="alignment-status">{alignmentLabel(status)}</p>
          {supporting ? <p className="alignment-support">{supporting}</p> : null}
          {classification ? <p className="alignment-class">{classification}</p> : null}
        </div>
      </div>
    </section>
  );
}

function StudiesSection({ studies, defaultOpen = false, plain = false, openIfPresent = false }) {
  const rows = studyRows(studies);
  const countLabel = rows.length ? `${rows.length} record${rows.length === 1 ? "" : "s"}` : "None";
  const startOpen = openIfPresent ? rows.length > 0 : defaultOpen;
  const body = rows.length ? (
    <div className="study-stack">
      {rows.map((row, index) => (
        <article className="study-mini" key={row.id || index}>
          <strong>{row.course_degree || row["Course/Degree"] || "Untitled program"}</strong>
          <InfoGrid
            items={[
              { label: "School", value: displayValue(row.school || row.School) },
              { label: "Address of Institution", value: displayValue(row.institution_address || row["Address of Institution"]) },
              { label: "Year enrolled", value: displayValue(row.year_enrolled || row["Year of First Enrollment"]) },
              { label: "Scholarship", value: displayValue(row.scholarship || row.Scholarship) },
              { label: "Graduated", value: displayValue(row.is_graduated ?? row.Graduated) },
            ]}
          />
        </article>
      ))}
    </div>
  ) : (
    <p className="muted">No further studies recorded.</p>
  );
  if (plain) return body;
  return (
    <ExpandDetails
      summary="Further Studies / Degrees Earned"
      hint={countLabel}
      showLabel="Show"
      hideLabel="Hide"
      defaultOpen={startOpen}
    >
      {body}
    </ExpandDetails>
  );
}

function ActivityCards({ rows, empty, render }) {
  if (!rows.length) return <p className="muted">{empty}</p>;
  return <div className="activity-stack">{rows.map(render)}</div>;
}

function MaybeCollapse({ title, hint, collapsible, open, children }) {
  if (!collapsible) {
    return (
      <section className="review-block">
        <h3>{title}</h3>
        {children}
      </section>
    );
  }
  return (
    <ExpandDetails summary={title} hint={hint} defaultOpen={open} showLabel="Show" hideLabel="Hide">
      {children}
    </ExpandDetails>
  );
}

export function ProfileActivityReview({ activity, collapsible = false }) {
  const [error, setError] = useState("");
  if (!activity) return null;
  const jobs = activity.jobs || [];
  const seminars = activity.seminars || [];
  const certifications = activity.certifications || [];
  const awards = activity.awards || [];
  const unemployed = Boolean(activity.currently_unemployed);
  const reasonLabel = String(activity.unemployment_reason_label || "").trim();
  const reasonDetails = String(activity.unemployment_details || "").trim();
  const reason = String(activity.no_employment_reason || "").trim();

  async function viewCertificate(row) {
    setError("");
    try {
      const blob = await api(`/api/admin/certifications/${row.id}/file`, { blob: true, toast: false });
      const url = URL.createObjectURL(blob);
      const opened = window.open(url, "_blank", "noopener,noreferrer");
      if (!opened) downloadAuthorized(`/api/admin/certifications/${row.id}/file`, row.certificate_filename || "certificate");
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setError(friendlyError(err, "We couldn't open this certificate."));
    }
  }

  return (
    <div className="activity-review">
      <Alert type="error">{error}</Alert>
      <MaybeCollapse
        title="Employment History"
        hint={jobs.length ? `${jobs.length} record${jobs.length === 1 ? "" : "s"}` : unemployed ? "Unemployed" : "None"}
        collapsible={collapsible}
        open={Boolean(jobs.length || unemployed)}
      >
        {unemployed || jobs.length ? (
          <div className="activity-stack">
            {unemployed ? (
              <article className="study-mini">
                <strong>Unemployed</strong>
                <InfoGrid
                  items={[
                    { label: "Reason", value: displayValue(reasonLabel || "Not recorded") },
                    { label: "Details", value: displayValue(reasonDetails) },
                  ]}
                />
              </article>
            ) : null}
            {jobs.map((row) => (
              <article className="study-mini" key={row.id}>
                <strong>{row.job_title}</strong>
                <InfoGrid
                  items={[
                    { label: "Company", value: displayValue(row.company) },
                    { label: "Location", value: displayValue(row.location) },
                    { label: "Industry", value: displayValue(row.industry) },
                    { label: "Current", value: unemployed ? (row.is_current ? "Kept on file, not counted while unemployed" : "No") : (row.is_current ? "Yes" : "No") },
                    { label: "Salary range", value: displayValue(row.salary_range) },
                  ]}
                />
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">{reason || "No employment history recorded."}</p>
        )}
      </MaybeCollapse>
      <MaybeCollapse
        title="Seminars Attended"
        hint={seminars.length ? `${seminars.length}` : "None"}
        collapsible={collapsible}
        open={seminars.length > 0}
      >
        <ActivityCards
          rows={seminars}
          empty="No seminars recorded."
          render={(row) => (
            <article className="study-mini" key={row.id}>
              <strong>{row.title}</strong>
              <InfoGrid
                items={[
                  { label: "Location of Seminar", value: displayValue(row.location) },
                  { label: "Date or year", value: displayValue(row.held_on) },
                  { label: "Organizer", value: displayValue(row.organizer) },
                ]}
              />
            </article>
          )}
        />
      </MaybeCollapse>
      <MaybeCollapse
        title="Certifications"
        hint={certifications.length ? `${certifications.length}` : "None"}
        collapsible={collapsible}
        open={certifications.length > 0}
      >
        <ActivityCards
          rows={certifications}
          empty="No certifications recorded."
          render={(row) => {
            const verify = safeHttpUrl(row.verification_url);
            return (
              <article className="study-mini" key={row.id}>
                <strong>{row.name}</strong>
                <InfoGrid
                  items={[
                    { label: "Awarding body", value: displayValue(row.awarding_body) },
                    { label: "Date or year awarded", value: displayValue(row.awarded_on) },
                    {
                      label: "Verification",
                      value: verify ? <a href={verify} target="_blank" rel="noopener noreferrer">Open verification link</a> : "—",
                    },
                  ]}
                />
                {row.has_certificate ? (
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => viewCertificate(row)}>
                    View certificate
                  </button>
                ) : null}
              </article>
            );
          }}
        />
      </MaybeCollapse>
      <MaybeCollapse
        title="Awards / Achievements"
        hint={awards.length ? `${awards.length}` : "None"}
        collapsible={collapsible}
        open={awards.length > 0}
      >
        <ActivityCards
          rows={awards}
          empty="No awards or achievements recorded."
          render={(row) => (
            <article className="study-mini" key={row.id}>
              <strong>{row.title}</strong>
              <InfoGrid
                items={[
                  { label: "Awarded by", value: displayValue(row.issuer) },
                  { label: "Date or year", value: displayValue(row.awarded_on) },
                  { label: "Description", value: displayValue(row.description) },
                ]}
              />
            </article>
          )}
        />
      </MaybeCollapse>
    </div>
  );
}

function ResumeStack({ resumes, onDownload, heading = "Uploaded Resumes", collapsible = false }) {
  const files = resumes || [];
  const body = files.length ? (
    <div className="file-stack">
      {files.map((row) => (
        <FileCard
          key={row.id}
          filename={row.filename}
          uploadedAt={row.created_at}
          onDownload={() => onDownload(row.id, row.filename)}
        />
      ))}
    </div>
  ) : (
    <p className="muted">No resume files on file.</p>
  );
  if (collapsible) {
    return (
      <MaybeCollapse
        title={heading || "Uploaded Resumes"}
        hint={files.length ? `${files.length}` : "None"}
        collapsible
        open={files.length > 0}
      >
        {body}
      </MaybeCollapse>
    );
  }
  return (
    <section className="review-block">
      {heading ? <h3>{heading}</h3> : null}
      {body}
    </section>
  );
}

function comparable(value) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!text || text === "—" || text === "Unlinked") return "";
  return text.toLowerCase();
}

function CompareCell({ side, label, value, unlinked = false, differs = false, official = false }) {
  const missing = !isFilled(value) || value === "—";
  return (
    <div className={`compare-cell${official ? " official" : ""}${differs ? " is-diff" : ""}`}>
      <span className="compare-side">{side}</span>
      <span>{label}</span>
      <strong>
        {unlinked ? <span className="id-unlinked">Unlinked</span> : missing ? "—" : value}
        {differs ? <span className="compare-note">Differs</span> : null}
      </strong>
    </div>
  );
}

function IdentitySections({ detail, verify }) {
  const profile = detail.profile || {};
  const account = detail.account || {};
  const registry = verify?.record;
  const rows = [
    { label: "Full name", submitted: fullName(profile), registry: registry ? fullName(registry) : "", compare: true },
    {
      label: "Student ID",
      submitted: account.student_id,
      registry: registry?.student_id || "",
      compare: true,
      unlinked: !String(account.student_id || "").trim(),
    },
    { label: "Degree or course", submitted: profile.degree, registry: registry?.degree || "", compare: true },
    { label: "Graduation year", submitted: profile.year_graduated, registry: registry?.year_graduated || "", compare: true },
    { label: "Country", submitted: profile.country_residence, registry: "", compare: false },
    { label: "Registration date", submitted: formatLongDate(account.created_at), registry: "", compare: false },
    { label: "College", submitted: "", registry: registry?.college || "", compare: false },
    { label: "Email", submitted: account.email, registry: registry?.email || "", compare: true },
  ];
  return (
    <div className="compare-board">
      <div className="compare-board-head">Submitted Information</div>
      <div className="compare-board-head official">
        <span>Official Graduate Registry Record</span>
        <OfficialMark />
      </div>
      {registry ? null : (
        <p className="compare-missing">No matching registry record was found. Registry values are unavailable.</p>
      )}
      {rows.map((row) => {
        const differs = Boolean(
          row.compare
          && registry
          && comparable(row.submitted)
          && comparable(row.registry)
          && comparable(row.submitted) !== comparable(row.registry)
        );
        return (
          <div className="compare-pair" key={row.label}>
            <CompareCell side="Submitted" label={row.label} value={row.submitted} unlinked={row.unlinked} differs={differs} />
            <CompareCell side="Registry" label={row.label} value={row.registry} official />
          </div>
        );
      })}
    </div>
  );
}

function employmentItems(record) {
  const data = record.data || {};
  return [
    { label: "Job Title", value: displayValue(record.job_title || data.pres_occ || data.first_occ) },
    { label: "Employer", value: displayValue(record.employer || data.pres_emp || data.first_emp) },
    { label: "Employment Status", value: displayValue(record.employment_status || data.is_currently_employed || data.first_stat) },
    { label: "How relevant is your current employment to your degree?", value: relatednessLabel(data.present_related_degree) },
    { label: "Ever employed after graduation", value: displayValue(data.ever_employed) },
    { label: "Time to first job", value: displayValue(data.time_to_first_job) },
    { label: "First job related to degree", value: relatednessLabel(data.first_related) },
    { label: "How first job was found", value: displayValue(data.find_job || data.other_find_job) },
    { label: "Length of stay", value: displayValue(data.pres_stay) },
  ];
}

function surveyItems(record, { hideIdentity = false } = {}) {
  const data = record.data || {};
  const suggestions = Object.entries(data.curriculum_suggestions || {}).filter(([, value]) => value);
  const identity = hideIdentity
    ? []
    : [
        { label: "Given name", value: displayValue(data.first_name) },
        { label: "Middle name", value: displayValue(data.middle_name) },
        { label: "Last name", value: displayValue(data.last_name) },
        { label: "Country of residence", value: displayValue(data.country) },
        { label: "Degree", value: displayValue(data.degree) },
        { label: "Year graduated", value: displayValue(data.year_graduated) },
        { label: "Primary guardian", value: displayValue(data.primary_guardian) },
        { label: "Guardian completed college", value: displayValue(data.guardian_degree_completed) },
      ];
  return [
    ...identity,
    { label: "Enrolled in further studies", value: displayValue(data.enroll_further_studies) },
    { label: "Participated in AUF career seminars", value: displayValue(data.participated_seminars) },
    { label: "Seminars were helpful", value: displayValue(data.seminars_helpful) },
    { label: "Inspired to mentor others", value: ratingLabel(data.mentoring_rating) },
    { label: "Inspired to join advocacy groups", value: ratingLabel(data.advocacy_rating) },
    { label: "Inspired to volunteer", value: ratingLabel(data.volunteering_rating) },
    ...suggestions.map(([key, value]) => ({ label: suggestionLabel(key), value })),
  ];
}

function extraItems(record, questionLabels) {
  const data = record.data || {};
  const extra = record.extra_answers || data.extra_answers || {};
  const labels = { ...(data._extra_labels || {}), ...(questionLabels || {}) };
  return Object.entries(extra)
    .filter(([key, value]) => key !== "_extra_labels" && key !== "_survey_version" && isFilled(value))
    .map(([key, value]) => ({
      label: extraLabel(key, labels),
      value: Array.isArray(value) ? value.join(", ") : displayValue(value),
    }));
}

export function TracerDetailView({
  record,
  questionLabels,
  compact = false,
  hideIdentity = false,
  hideEmail = false,
  showAlignment = true,
  groupEmployment = false,
}) {
  if (!record) return null;
  const extras = extraItems(record, questionLabels);
  const employment = employmentItems(record);
  const relevanceLabels = new Set([
    "How relevant is your current employment to your degree?",
    "First job related to degree",
  ]);
  const relevance = employment.filter((item) => relevanceLabels.has(item.label));
  const employmentCore = employment.filter((item) => !relevanceLabels.has(item.label));
  const submissionItems = [
    { label: "Submitted date", value: formatLongDate(record.submitted_at) },
    { label: "Submitted time", value: formatTime(record.submitted_at) },
    hideEmail ? null : { label: "Graduate email", value: record.email || "—" },
  ].filter(Boolean);
  const submission = <QaList items={submissionItems} />;

  return (
    <div className={`tracer-detail ${compact ? "is-compact" : "is-page"}`}>
      {groupEmployment ? (
        <>
          <section className="review-block">
            <h3>Employment</h3>
            <QaList compact items={employmentCore} />
          </section>
          <section className="review-block">
            <h3>Degree relevance</h3>
            <QaList compact items={relevance} />
          </section>
        </>
      ) : (
        <section className="review-block">
          <h3>Employment Information</h3>
          <QaList compact items={employment} />
        </section>
      )}
      {showAlignment ? <AlignmentHero record={record} /> : null}
      {Array.isArray(record.further_studies) ? (
        <section className="review-block">
          <h3>Further Studies / Degrees Earned</h3>
          <StudiesSection studies={record.further_studies} plain />
        </section>
      ) : null}
      <section className="review-block">
        <h3>Graduate Tracer Survey</h3>
        <QaList compact items={surveyItems(record, { hideIdentity })} />
      </section>
      {extras.length ? (
        <section className="review-block">
          <h3>Supplementary Questions</h3>
          <QaList compact items={extras} />
        </section>
      ) : null}
      {compact ? (
        <ExpandDetails summary="Submission Information">{submission}</ExpandDetails>
      ) : (
        <section className="review-block">
          <h3>Submission Information</h3>
          {submission}
        </section>
      )}
      {record.profile_activity ? <ProfileActivityReview activity={record.profile_activity} /> : null}
    </div>
  );
}

export function DecisionPanel({
  reason,
  setReason,
  reasonError,
  setReasonError,
  busy,
  onApprove,
  onReject,
  showButtons = true,
  hideTitle = false,
  canDecide = true,
  statusLabel = "Pending",
}) {
  return (
    <div className="decision-panel">
      {hideTitle ? null : <h3>Registration Decision</h3>}
      {canDecide ? (
        <>
          <p className="decision-lead">
            Choose one option after you have checked the registry match and the submitted information. Opening this tab does not approve or reject the account.
          </p>
          <div className="decision-grid">
            <article className="decision-card">
              <h4>Approve Registration</h4>
              <p>Approval activates the alumni account and marks it as verified.</p>
              {showButtons ? (
                <button className="btn btn-navy" type="button" disabled={busy} onClick={onApprove}>
                  <CheckIcon size={16} />
                  Approve Registration
                </button>
              ) : null}
            </article>
            <article className="decision-card reject">
              <h4>Reject Registration</h4>
              <p>Rejection prevents the applicant from accessing the alumni portal. The applicant will be informed of the rejection reason.</p>
              <Field label="Reason for Rejection" required error={reasonError}>
                <textarea
                  id="rejection-reason"
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value);
                    if (e.target.value.trim().length >= 3) setReasonError("");
                  }}
                  placeholder="Explain why this registration cannot be approved."
                />
              </Field>
              {showButtons ? (
                <button className="btn btn-danger" type="button" disabled={busy} onClick={onReject}>
                  <XIcon size={16} />
                  Reject Registration
                </button>
              ) : null}
            </article>
          </div>
        </>
      ) : (
        <p className="decision-closed">
          This request is no longer available for a decision. The account status is <strong>{statusLabel}</strong>.
        </p>
      )}
    </div>
  );
}

export function DecisionActions({ busy, onApprove, onReject, compact = false, disabled = false }) {
  const locked = busy || disabled;
  return (
    <div className={`decision-actions ${compact ? "is-compact" : ""}`}>
      <button className="btn btn-navy" type="button" disabled={locked} onClick={onApprove}>
        <CheckIcon size={16} />
        {busy ? "Working…" : "Approve Registration"}
      </button>
      <button className="btn btn-danger" type="button" disabled={locked} onClick={onReject}>
        <XIcon size={16} />
        {busy ? "Working…" : "Reject Registration"}
      </button>
    </div>
  );
}

export function ApprovalReviewContent({ detail, verify }) {
  if (!detail) return null;
  const pending = isPendingRegistration(detail);

  return (
    <div className="review-flow">
      <ApplicantSummary detail={detail} />
      <section className="registry-status" aria-label="Registry verification">
        <h3>Registry verification</h3>
        <VerifyBanner verify={verify} compact />
        {pending ? (
          <p className="registry-note">
            This result is separate from the account status. The account remains Pending until you approve or reject the registration.
          </p>
        ) : (
          <p className="decision-closed">
            This request is no longer available for a decision. The account status is <strong>{registrationStatusLabel(detail.account?.status)}</strong>.
          </p>
        )}
      </section>
      <IdentitySections detail={detail} verify={verify} />
    </div>
  );
}

export function ApproveConfirmDialog({ busy, onConfirm, onClose }) {
  return (
    <Dialog
      title="Approve this registration?"
      confirmLabel="Approve Registration"
      busy={busy}
      onConfirm={onConfirm}
      onClose={onClose}
    >
      <p>Approval activates the alumni account and marks it as verified. The graduate will be able to access the Alumni Portal.</p>
    </Dialog>
  );
}

export function RejectConfirmDialog({ reason, setReason, reasonError, setReasonError, busy, onConfirm, onClose }) {
  return (
    <Dialog
      title="Reject this registration?"
      confirmLabel="Reject Registration"
      danger
      busy={busy}
      onConfirm={onConfirm}
      onClose={onClose}
    >
      <p>Rejection prevents the applicant from accessing the alumni portal. The applicant will be informed of this reason.</p>
      <Field label="Reason for Rejection" required error={reasonError}>
        <textarea
          id="rejection-reason-dialog"
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
            if (e.target.value.trim().length >= 3) setReasonError("");
          }}
          placeholder="Explain why this registration cannot be approved."
        />
      </Field>
    </Dialog>
  );
}

export function DetailHeader({ backTo, backLabel, title, name, meta, actions }) {
  return (
    <header className="detail-header">
      <Link className="back-link" to={backTo}>
        <ChevronLeftIcon size={16} />
        {backLabel}
      </Link>
      <div className="detail-header-row">
        <div className="detail-header-copy">
          {name || title ? <h1>{name || title}</h1> : null}
          {meta ? <p className="detail-meta">{meta}</p> : null}
        </div>
        {actions ? <div className="page-actions">{actions}</div> : null}
      </div>
    </header>
  );
}

export function ApprovalDetailView({
  detail,
  verify,
  labels,
  reviewTab,
  setReviewTab,
  reason,
  setReason,
  reasonError,
  setReasonError,
  busy,
  onApprove,
  onReject,
  onDownloadResume,
}) {
  const [localTab, setLocalTab] = useState("identity");
  if (!detail) return null;
  return (
    <ApprovalReviewContent
      detail={detail}
      verify={verify}
      labels={labels}
      reviewTab={reviewTab || localTab}
      setReviewTab={setReviewTab || setLocalTab}
      reason={reason}
      setReason={setReason}
      reasonError={reasonError}
      setReasonError={setReasonError}
      busy={busy}
      onApprove={onApprove}
      onReject={onReject}
      onDownloadResume={onDownloadResume}
    />
  );
}

export function TracerRecordLayout({ record, questionLabels, compact = false }) {
  if (!record) return null;
  if (compact) {
    return <TracerDetailView record={record} questionLabels={questionLabels} compact hideEmail />;
  }
  const extras = extraItems(record, questionLabels);
  return (
    <div className="detail-page">
      <div className="detail-layout tracer-layout">
        <div className="detail-main">
          <section className="detail-section">
            <h2>Employment Information</h2>
            <QaList compact items={employmentItems(record)} />
          </section>
          <section className="detail-section">
            <h2>Graduate Tracer Survey</h2>
            <QaList compact items={surveyItems(record)} />
          </section>
          {extras.length ? (
            <section className="detail-section">
              <h2>Supplementary Questions</h2>
              <QaList compact items={extras} />
            </section>
          ) : null}
          {Array.isArray(record.further_studies) ? (
            <section className="detail-section">
              <h2>Further Studies / Degrees Earned</h2>
              <StudiesSection studies={record.further_studies} plain />
            </section>
          ) : null}
          {record.profile_activity ? (
            <section className="detail-section">
              <h2>Alumni Profile Records</h2>
              <ProfileActivityReview activity={record.profile_activity} />
            </section>
          ) : null}
          <section className="detail-section">
            <h2>Submission Information</h2>
            <QaList
              items={[
                { label: "Submitted date", value: formatLongDate(record.submitted_at) },
                { label: "Submitted time", value: formatTime(record.submitted_at) },
              ]}
            />
          </section>
        </div>
        <aside className="detail-aside">
          <section className="detail-section">
            <AlignmentHero record={record} />
          </section>
        </aside>
      </div>
    </div>
  );
}

export function useApprovalReview(accountId) {
  const [detail, setDetail] = useState(null);
  const [verify, setVerify] = useState(null);
  const [labels, setLabels] = useState({});
  const [reviewTab, setReviewTab] = useState("identity");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [okTitle, setOkTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [confirmReject, setConfirmReject] = useState(false);
  const [confirmApprove, setConfirmApprove] = useState(false);

  useEffect(() => {
    api("/api/auth/options")
      .then((opts) => setLabels(questionLabelsFrom(opts.supplementary_questions)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => {
      setOk("");
      setOkTitle("");
    }, 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  async function load() {
    if (!accountId) {
      setDetail(null);
      setVerify(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    setReasonError("");
    setConfirmReject(false);
    setConfirmApprove(false);
    setReviewTab("identity");
    try {
      const [info, check] = await Promise.all([
        api(`/api/admin/approvals/${accountId}`),
        api(`/api/admin/approvals/${accountId}/verify`, { method: "POST" }),
      ]);
      setDetail(info);
      setVerify(check);
    } catch (err) {
      setError(err.message);
      setDetail(null);
      setVerify(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [accountId]);

  function reset() {
    setDetail(null);
    setVerify(null);
    setReason("");
    setReasonError("");
    setConfirmReject(false);
    setConfirmApprove(false);
    setReviewTab("identity");
  }

  function requestApprove() {
    if (!detail || busy) return;
    if (!isPendingRegistration(detail)) {
      setError("This request is no longer available for a decision.");
      return;
    }
    setConfirmApprove(true);
  }

  async function approve() {
    if (!detail || busy) return false;
    if (!isPendingRegistration(detail)) {
      setError("This request is no longer available for a decision.");
      setConfirmApprove(false);
      return false;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/api/admin/approvals/${detail.account.id}/approve`, { method: "POST" });
      setOkTitle("Registration approved successfully.");
      setOk("The alumni account is now active and verified.");
      setConfirmApprove(false);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  function requestReject() {
    if (!detail || busy) return;
    if (!isPendingRegistration(detail)) {
      setError("This request is no longer available for a decision.");
      return;
    }
    if (reason.trim().length < 3) {
      setReasonError("Enter a rejection reason with at least 3 characters.");
      setConfirmReject(true);
      requestAnimationFrame(() => document.getElementById("rejection-reason-dialog")?.focus());
      return;
    }
    setConfirmReject(true);
  }

  async function reject() {
    if (!detail) return false;
    if (!isPendingRegistration(detail)) {
      setError("This request is no longer available for a decision.");
      setConfirmReject(false);
      return false;
    }
    if (reason.trim().length < 3) {
      setReasonError("Enter a rejection reason with at least 3 characters.");
      requestAnimationFrame(() => document.getElementById("rejection-reason-dialog")?.focus());
      return false;
    }
    if (busy) return false;
    setBusy(true);
    setError("");
    try {
      await api(`/api/admin/approvals/${detail.account.id}/reject`, { method: "POST", body: { reason } });
      setOkTitle("Registration rejected successfully.");
      setOk("The applicant cannot access the alumni portal and will see this reason.");
      setConfirmReject(false);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function downloadResume(resumeId, filename) {
    setError("");
    try {
      await downloadAuthorized(`/api/admin/resumes/${resumeId}/file`, filename || "resume");
    } catch (err) {
      setError(err.message);
    }
  }

  return {
    detail,
    verify,
    labels,
    reviewTab,
    setReviewTab,
    reason,
    setReason,
    reasonError,
    setReasonError,
    error,
    ok,
    okTitle,
    busy,
    loading,
    confirmReject,
    setConfirmReject,
    confirmApprove,
    setConfirmApprove,
    approve,
    reject,
    requestApprove,
    requestReject,
    downloadResume,
    reset,
    reload: load,
  };
}
