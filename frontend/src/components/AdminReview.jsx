import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CheckIcon,
  ChevronLeftIcon,
  DownloadIcon,
  FileIcon,
  InboxIcon,
  LockIcon,
  XIcon,
} from "./icons";
import { Badge, Empty, ExpandDetails, Field, TabList } from "./ui";
import { api, downloadAuthorized } from "../lib/api";
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
      email_name: "Possible match",
      already_linked: "Already linked",
      none: "No match found",
    }[verifyType(verify)] || "No match found"
  );
}

export function verifySummaryValue(verify) {
  return (
    {
      student_id: "✓ Matched by Student ID",
      email_name: "! Possible match",
      already_linked: "! Already linked",
      none: "! No match found",
    }[verifyType(verify)] || "! No match found"
  );
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
    return <Badge tone={value ? "Active" : "Pending"}>{value ? "Yes" : "No"}</Badge>;
  }
  return <Badge tone={text}>{text}</Badge>;
}

export function VerifyBanner({ verify, compact = false }) {
  const map = {
    student_id: {
      tone: "ok",
      icon: <CheckCircleIcon size={compact ? 18 : 20} />,
      title: "✓ Graduate Record Matched",
      text: "Matched using Student ID.",
    },
    email_name: {
      tone: "info",
      icon: <AlertTriangleIcon size={compact ? 18 : 20} />,
      title: "! Possible Graduate Record",
      text: "Matched using email/name. Review the registry information before approving.",
    },
    already_linked: {
      tone: "warn",
      icon: <AlertTriangleIcon size={compact ? 18 : 20} />,
      title: "! Graduate Record Already Linked",
      text: "This official graduate record is already connected to another account.",
    },
    none: {
      tone: "error",
      icon: <AlertTriangleIcon size={compact ? 18 : 20} />,
      title: "! No Graduate Record Found",
      text: "Review the submitted information or search the Graduate Registry.",
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

function StudiesSection({ studies, defaultOpen = false, plain = false }) {
  const rows = studyRows(studies);
  const countLabel = `${rows.length} record${rows.length === 1 ? "" : "s"}`;
  const body = rows.length ? (
    <div className="study-stack">
      {rows.map((row, index) => (
        <article className="study-mini" key={row.id || index}>
          <strong>{row.course_degree || row["Course/Degree"] || "Untitled program"}</strong>
          <InfoGrid
            items={[
              { label: "School", value: displayValue(row.school || row.School) },
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
      summary="Further Studies"
      hint={countLabel}
      showLabel="Show"
      hideLabel="Hide"
      defaultOpen={defaultOpen}
    >
      {body}
    </ExpandDetails>
  );
}

function ResumeStack({ resumes, onDownload, heading = "Uploaded Resumes" }) {
  const files = resumes || [];
  return (
    <section className="review-block">
      {heading ? <h3>{heading}</h3> : null}
      {files.length ? (
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
      )}
    </section>
  );
}

function IdentitySections({ detail, verify, stacked = false }) {
  const profile = detail.profile || {};
  const registry = verify?.record;
  return (
    <div className={stacked ? "identity-stack" : "compare-grid"}>
      <article className="compare-card">
        <div className="compare-kicker">Submitted information</div>
        <h3>Submitted Profile</h3>
        <InfoGrid
          items={[
            { label: "Full Name", value: fullName(profile) },
            { label: "Student ID", value: displayValue(detail.account.student_id || "Unlinked") },
            { label: "Degree", value: displayValue(profile.degree) },
            { label: "Year Graduated", value: displayValue(profile.year_graduated) },
            { label: "Country", value: displayValue(profile.country_residence) },
            { label: "Registered", value: formatLongDate(detail.account.created_at) },
          ]}
        />
      </article>
      <article className="compare-card official">
        <div className="compare-kicker">
          Official university record
          <OfficialMark />
        </div>
        <h3>University Registry Match</h3>
        {registry ? (
          <InfoGrid
            items={[
              { label: "Student ID", value: displayValue(registry.student_id) },
              { label: "Name", value: fullName(registry) },
              { label: "Email", value: displayValue(registry.email) },
              { label: "Degree", value: displayValue(registry.degree) },
              { label: "Year", value: displayValue(registry.year_graduated) },
              { label: "College", value: displayValue(registry.college) },
            ]}
          />
        ) : (
          <Empty title="No official match">Search the Graduate Registry if the submitted details look correct.</Empty>
        )}
      </article>
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
}) {
  if (!record) return null;
  const extras = extraItems(record, questionLabels);
  const submissionItems = [
    { label: "Submitted date", value: formatLongDate(record.submitted_at) },
    { label: "Submitted time", value: formatTime(record.submitted_at) },
    hideEmail ? null : { label: "Graduate email", value: record.email || "—" },
  ].filter(Boolean);
  const submission = <QaList items={submissionItems} />;

  return (
    <div className={`tracer-detail ${compact ? "is-compact" : "is-page"}`}>
      <section className="review-block">
        <h3>Employment Information</h3>
        <QaList compact items={employmentItems(record)} />
      </section>
      {showAlignment ? <AlignmentHero record={record} /> : null}
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
            Review the verification and submitted information before deciding whether to activate this account.
          </p>
          <div className="decision-grid">
            <article className="decision-card">
              <h4>Approve</h4>
              <p>Activates the alumni account and marks the graduate as verified.</p>
              {showButtons ? (
                <button className="btn btn-navy" type="button" disabled={busy} onClick={onApprove}>
                  <CheckIcon size={16} />
                  Approve Registration
                </button>
              ) : null}
            </article>
            <article className="decision-card reject">
              <h4>Reject</h4>
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
              <p className="field-help">The applicant will see this reason and remain unable to access the alumni portal.</p>
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
        <p className="decision-lead">
          This registration is already <strong>{statusLabel}</strong>. Approve and Reject are no longer available.
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
        {busy ? "Working…" : compact ? "Approve" : "Approve Registration"}
      </button>
      <button className="btn btn-danger" type="button" disabled={locked} onClick={onReject}>
        <XIcon size={16} />
        {busy ? "Working…" : compact ? "Reject" : "Reject Registration"}
      </button>
    </div>
  );
}

export function ApprovalReviewContent({
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
  if (!detail) return null;
  const profile = detail.profile || {};
  const submission = tracerFromApproval(detail);

  return (
    <div className="review-flow">
      <ReviewSummary
        items={[
          { label: "Applicant", value: applicantName(detail) },
          { label: "Student ID", value: displayValue(detail.account.student_id || "Unlinked") },
          { label: "Degree", value: displayValue(profile.degree) },
          { label: "Verification", value: verifySummaryValue(verify) },
        ]}
      />
      <VerifyBanner verify={verify} compact />
      <TabList
        label="Review"
        value={reviewTab}
        onChange={setReviewTab}
        tabs={[
          ["identity", "Identity"],
          ["tracer", "Tracer"],
          ["decision", "Decision"],
        ]}
      />

      {reviewTab === "identity" && (
        <div role="tabpanel" id="panel-review-identity" className="review-tab-panel">
          <IdentitySections detail={detail} verify={verify} />
          <StudiesSection studies={detail.further_studies} />
          <ResumeStack resumes={detail.resumes} onDownload={onDownloadResume} />
        </div>
      )}

      {reviewTab === "tracer" && (
        <div role="tabpanel" id="panel-review-tracer" className="review-tab-panel">
          {submission ? (
            <TracerDetailView record={submission} questionLabels={labels} compact hideIdentity hideEmail />
          ) : (
            <Empty icon={<InboxIcon size={36} />} title="No tracer submission">
              The applicant has not submitted a Graduate Tracer Survey yet.
            </Empty>
          )}
        </div>
      )}

      {reviewTab === "decision" && (
        <div role="tabpanel" id="panel-review-decision" className="review-tab-panel">
          <DecisionPanel
            reason={reason}
            setReason={setReason}
            reasonError={reasonError}
            setReasonError={setReasonError}
            busy={busy}
            onApprove={onApprove}
            onReject={onReject}
            showButtons={false}
            canDecide={isPendingRegistration(detail)}
            statusLabel={registrationStatusLabel(detail.account.status)}
          />
        </div>
      )}
    </div>
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
  reason,
  setReason,
  reasonError,
  setReasonError,
  busy,
  onApprove,
  onReject,
  onDownloadResume,
}) {
  if (!detail) return null;
  const profile = detail.profile || {};
  const submission = tracerFromApproval(detail);
  const status = detail.account.status || "Pending";
  const pending = isPendingRegistration(detail);

  return (
    <div className="detail-page">
      <ReviewSummary
        items={[
          { label: "Applicant", value: applicantName(detail) },
          { label: "Student ID", value: displayValue(detail.account.student_id || "Unlinked") },
          { label: "Degree", value: displayValue(profile.degree) },
          { label: "Status", value: registrationStatusLabel(status) },
        ]}
      />
      <div className="detail-layout">
        <div className="detail-main">
          <section className="detail-section">
            <h2>Identity Information</h2>
            <h3 className="section-subhead">Submitted Profile</h3>
            <InfoGrid
              items={[
                { label: "Full Name", value: fullName(profile) },
                { label: "Student ID", value: displayValue(detail.account.student_id || "Unlinked") },
                { label: "Degree", value: displayValue(profile.degree) },
                { label: "Year Graduated", value: displayValue(profile.year_graduated) },
                { label: "Country", value: displayValue(profile.country_residence) },
                { label: "Registered", value: formatLongDate(detail.account.created_at) },
              ]}
            />
          </section>
          <section className="detail-section official">
            <div className="section-kicker">
              <h2>University Registry</h2>
              <OfficialMark />
            </div>
            {verify?.record ? (
              <InfoGrid
                items={[
                  { label: "Student ID", value: displayValue(verify.record.student_id) },
                  { label: "Name", value: fullName(verify.record) },
                  { label: "Email", value: displayValue(verify.record.email) },
                  { label: "Degree", value: displayValue(verify.record.degree) },
                  { label: "Year", value: displayValue(verify.record.year_graduated) },
                  { label: "College", value: displayValue(verify.record.college) },
                ]}
              />
            ) : (
              <Empty title="No official match">Search the Graduate Registry if the submitted details look correct.</Empty>
            )}
          </section>
          <section className="detail-section">
            <h2>Further Studies</h2>
            <StudiesSection studies={detail.further_studies} plain />
          </section>
          <section className="detail-section">
            {submission ? (
              <TracerDetailView
                record={submission}
                questionLabels={labels}
                hideIdentity
                hideEmail
                showAlignment={false}
              />
            ) : (
              <>
                <h2>Graduate Tracer Survey</h2>
                <Empty icon={<InboxIcon size={36} />} title="No tracer submission">
                  The applicant has not submitted a Graduate Tracer Survey yet.
                </Empty>
              </>
            )}
          </section>
          <section className="detail-section">
            <h2>Uploaded Documents</h2>
            <ResumeStack resumes={detail.resumes} onDownload={onDownloadResume} heading={null} />
          </section>
        </div>
        <aside className="detail-aside">
          <section className="detail-section">
            <h2>Verification</h2>
            <VerifyBanner verify={verify} compact />
          </section>
          <section className="detail-section">
            <h2>Status</h2>
            <InfoGrid
              items={[
                { label: "Account", value: registrationStatusLabel(status) },
                { label: "Verification", value: verifyShortLabel(verify) },
              ]}
            />
          </section>
          {submission ? (
            <section className="detail-section">
              <AlignmentHero record={submission} />
            </section>
          ) : null}
          <section className="detail-section">
            <h2>Actions</h2>
            <DecisionPanel
              reason={reason}
              setReason={setReason}
              reasonError={reasonError}
              setReasonError={setReasonError}
              busy={busy}
              onApprove={onApprove}
              onReject={onReject}
              hideTitle
              canDecide={pending}
              statusLabel={registrationStatusLabel(status)}
            />
          </section>
        </aside>
      </div>
    </div>
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
      setError("This registration is no longer pending.");
      return;
    }
    setConfirmApprove(true);
  }

  async function approve() {
    if (!detail || busy) return false;
    if (!isPendingRegistration(detail)) {
      setError("This registration is no longer pending.");
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
      setError("This registration is no longer pending.");
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
      setError("This registration is no longer pending.");
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
