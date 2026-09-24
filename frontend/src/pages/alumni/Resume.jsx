import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import GtsForm from "../../components/GtsForm";
import { DownloadIcon, UploadIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { SourceBadge } from "../../components/AlumniChrome";
import { ProfileProgress } from "../../components/ProfileProgress";
import { Panel, ResumeExtract } from "../../components/RecordViews";
import { Alert, Empty, ExpandDetails, PageSkeleton, SaveStatus } from "../../components/ui";
import { api, downloadAuthorized } from "../../lib/api";
import { officialEmploymentFromGts } from "../../lib/employmentDisplay";
import { formatDateTime, fullName, parserLabel } from "../../lib/format";
import { usePublishedSurvey } from "../../lib/surveyLive";
import { showToast } from "../../lib/toasts";
import { MAX_RESUME_BYTES, RESUME_ACCEPT, friendlyError } from "../../lib/userMessages";

function experiencesFromGts(gts = {}) {
  if (Array.isArray(gts.experiences) && gts.experiences.length) return gts.experiences;
  const firstTitle = String(gts.first_occ || "").trim();
  const firstEmployer = String(gts.first_emp || "").trim();
  const presentTitle = String(gts.pres_occ || gts.current_occupation || "").trim();
  const presentEmployer = String(gts.pres_emp || gts.current_employer || "").trim();
  const currentlyEmployed = String(gts.is_currently_employed || "") === "Yes";
  const presentIsFirst = String(gts.present_job_is_first || "") !== "No";
  const rows = [];
  if (firstTitle || firstEmployer) {
    rows.push({
      job_title: firstTitle,
      employer: firstEmployer,
      is_current: currentlyEmployed && presentIsFirst ? "Yes" : "No",
      employment_status: gts.first_stat || "",
    });
  }
  if (!presentIsFirst && (presentTitle || presentEmployer)) {
    rows.push({
      job_title: presentTitle,
      employer: presentEmployer,
      is_current: currentlyEmployed ? "Yes" : "No",
    });
  }
  return rows;
}

function resumeEvidence(preview, latest) {
  const parsed = preview?.parsed || latest?.parsed;
  const source = preview?.parser_source || latest?.parser_source || "";
  if (!parsed || source === "failed" || source === "empty") return null;
  return { ...parsed, parser_source: source };
}

function parsedFromGts(gts = {}) {
  return {
    first_name: gts.first_name,
    middle_name: gts.middle_name,
    last_name: gts.last_name,
    degree: gts.degree,
    year_graduated: gts.year_graduated,
    country: gts.country,
    current_occupation: gts.pres_occ || gts.first_occ || gts.current_occupation,
    current_employer: gts.pres_emp || gts.first_emp || gts.current_employer,
    is_currently_employed: gts.is_currently_employed,
    skills: gts.skills || [],
    experiences: experiencesFromGts(gts),
    further_studies: gts.further_studies || [],
  };
}

export default function AlumniResume() {
  const location = useLocation();
  const { options, error: surveyError } = usePublishedSurvey();
  const [resumes, setResumes] = useState([]);
  const [preview, setPreview] = useState(null);
  const [formSeed, setFormSeed] = useState(null);
  const [formKey, setFormKey] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [latestGts, setLatestGts] = useState(null);
  const [completion, setCompletion] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [saveState, setSaveState] = useState("idle");
  const [loaded, setLoaded] = useState(false);
  const fileRef = useRef(null);

  async function load(seedForm = true) {
    const [list, profile] = await Promise.all([
      api("/api/alumni/resumes"),
      api("/api/alumni/profile"),
    ]);
    setResumes(list);
    setLastUpdated(profile.latest_submitted_at || null);
    setLatestGts(profile.latest_gts || null);
    setCompletion(profile.completion || null);
    if (seedForm) {
      setFormSeed({
        ...(profile.latest_gts || {}),
        extra_answers: profile.extra_answers || {},
        resume_id: list[0]?.id,
      });
    }
  }

  useEffect(() => {
    load()
      .catch((err) => setError(friendlyError(err, "We couldn't load your tracer record. Please try again.")))
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    if (!location.hash || !loaded) return;
    const node = document.getElementById(location.hash.slice(1));
    node?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [location.hash, loaded]);

  useEffect(() => {
    if (saveState !== "saved") return undefined;
    const timer = window.setTimeout(() => setSaveState("idle"), 5000);
    return () => window.clearTimeout(timer);
  }, [saveState]);

  async function uploadFile(file) {
    if (!file) return;
    if (file.size > MAX_RESUME_BYTES) {
      setError("Please upload a PDF, DOCX, or TXT file of 10 MB or smaller.");
      return;
    }
    setBusy(true);
    setSaveState("saving");
    setError("");
    try {
      const form = new FormData();
      form.append("resume", file);
      const data = await api("/api/alumni/resumes", { method: "POST", form });
      setPreview(data);
      setFormSeed({
        ...data.gts_prefill,
        extra_answers: formSeed?.extra_answers || {},
        resume_id: data.resume_id,
      });
      setFormKey((value) => value + 1);
      await load(false);
      setSaveState("saved");
      showToast("success", "Resume uploaded. Review suggested information before saving.");
    } catch (err) {
      setSaveState("error");
      setError(friendlyError(err, "We couldn't read this resume. You can still update your tracer information manually."));
    } finally {
      setBusy(false);
    }
  }

  async function save(payload) {
    setBusy(true);
    setSaveState("saving");
    setError("");
    try {
      await api("/api/alumni/gts", {
        method: "POST",
        body: {
          ...payload,
          resume_id: preview?.resume_id || formSeed?.resume_id || payload.resume_id,
        },
      });
      setLastUpdated(new Date().toISOString());
      setLatestGts(payload);
      setPreview(null);
      setSaveState("saved");
      showToast("success", "Your responses are now the official tracer record.", { title: "Tracer survey saved" });
      await load(false);
    } catch (err) {
      setSaveState("error");
      setError(friendlyError(err, "We couldn't save your tracer information. Please review the highlighted fields and try again."));
    } finally {
      setBusy(false);
    }
  }

  if (!options || !loaded) return <PortalShell role="Alumni"><PageSkeleton variant="alumni" /></PortalShell>;

  const employment = officialEmploymentFromGts(latestGts || {});
  const occupation = employment.occupation;
  const employer = employment.employer;
  const hasTracer = Boolean(lastUpdated);
  const latestResume = resumes[0] || null;
  const extractParsed = preview?.parsed || latestResume?.parsed || parsedFromGts(latestGts || {});
  const extractGts = preview?.gts_prefill || latestGts || {};
  const extractSource = parserLabel(preview?.parser_source || latestResume?.parser_source);
  const hasExtract = Boolean(
    preview
    || latestResume?.parsed
    || fullName(extractParsed) !== "—"
    || (extractParsed.experiences || []).length
    || (extractParsed.skills || []).length
  );
  const formLocked = options.allow_alumni_edit === false || options.survey_open === false;

  let employmentTitle = "Not recorded";
  let employmentDetail = "Current occupation is not recorded on your submitted tracer.";
  if (!hasTracer) {
    employmentTitle = "Not yet saved";
    employmentDetail = "No official current occupation is on file until you save the tracer survey.";
  } else if (employment.answered && !employment.currentlyEmployed) {
    employmentTitle = "Not currently employed";
    employmentDetail = "";
  } else if (occupation) {
    employmentTitle = occupation;
    employmentDetail = employer || "";
  }

  return (
    <PortalShell role="Alumni">
      <Alert type="error">{error || surveyError}</Alert>

      <Panel
        className="tracer-snapshot"
        title="Employment status"
        actions={<SaveStatus state={busy ? "saving" : saveState} errorLabel="Unable to save. Your answers are still on this page." />}
      >
        <div className="tracer-snapshot-grid">
          <section aria-label="Last updated">
            <p className="eyebrow">Last updated</p>
            <strong>{hasTracer ? formatDateTime(lastUpdated) : "Not yet saved"}</strong>
          </section>
          <section aria-label="Current employment">
            <p className="eyebrow">Current employment</p>
            <strong>{employmentTitle}</strong>
            {employmentDetail ? <p>{employmentDetail}</p> : null}
            {hasTracer && employment.related ? <p className="muted">Related to degree: {employment.related}</p> : null}
            {hasTracer ? <SourceBadge>From submitted Graduate Tracer Survey</SourceBadge> : null}
          </section>
        </div>
      </Panel>

      {loaded ? (
        <Panel title="Alumni record" description="Completion is calculated from your submitted CareerSense record. Resume suggestions are not counted until you save the tracer.">
          <ProfileProgress
            compact
            completion={completion}
            state={completion ? "ready" : "error"}
            onRetry={() => load(false).catch(() => {})}
          />
        </Panel>
      ) : null}

      <Panel
        id="resume"
        className="resume-extract-panel"
        title={preview ? "Suggested from resume" : "Extracted from resume"}
        description={
          preview
            ? "Review these suggestions, then save the tracer survey if they should become your official record."
            : latestResume
              ? "Information read from your latest uploaded resume. This does not replace your official tracer until you save."
              : "Upload a resume to extract education, work history, and skills. Current details below come from your submitted tracer until then."
        }
      >
        <label
          className={`dropzone file-dropzone ${dragOver ? "is-over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            uploadFile(e.dataTransfer.files?.[0]);
          }}
        >
          <UploadIcon size={28} />
          <strong>Upload a resume</strong>
          <span className="muted">PDF, DOCX, or TXT · Maximum 10 MB</span>
          <p className="file-dropzone-copy">Drag and drop or choose a file. Review extracted information before saving the tracer.</p>
          <input
            ref={fileRef}
            type="file"
            accept={RESUME_ACCEPT}
            disabled={busy}
            onChange={(e) => {
              uploadFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </label>
        {busy ? <p className="muted" role="status">Reading resume…</p> : null}
        {hasExtract ? (
          <ResumeExtract
            parsed={extractParsed}
            gts={extractGts}
            alignment={preview?.alignment}
            parserSource={extractSource}
            suggestion={Boolean(preview)}
            embedded
          />
        ) : (
          <Empty compact title="No resume information yet" action={null}>
            Upload a resume to extract education, work history, and skills.
          </Empty>
        )}
      </Panel>

      <Panel
        id="tracer"
        className="tracer-official"
        title="Official tracer record"
        description="Save the Graduate Tracer Survey to update last updated date and current employment."
      >
        <ExpandDetails
          key={preview ? `preview-${preview.resume_id}` : "form"}
          summary="Review and save tracer survey"
          hint="Edit official Graduate Tracer Survey answers"
          defaultOpen={Boolean(preview) || location.hash === "#tracer"}
        >
          <GtsForm
            key={formKey}
            initial={formSeed || {}}
            options={options}
            onSubmit={save}
            busy={busy}
            submitLabel="Save tracer record"
            readOnly={formLocked}
            closedMessage={options.survey_open === false ? "This survey is not currently accepting responses." : ""}
            resume={resumeEvidence(preview, latestResume)}
          />
        </ExpandDetails>
      </Panel>

      <Panel title="Previous resumes" description="Files you have already submitted stay listed here.">
        {!resumes.length ? (
          <Empty compact title="No resumes stored" action={null}>
            Upload a file above. It will be listed here after the first successful upload.
          </Empty>
        ) : (
          <div>
            {resumes.map((row) => (
              <div className="file-row" key={row.id}>
                <div>
                  <strong>{row.original_filename}</strong>
                  <p className="muted" style={{ margin: "4px 0 0" }}>
                    {[parserLabel(row.parser_source), formatDateTime(row.created_at), fullName(row.parsed)].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <button
                  className="btn btn-outline btn-sm"
                  type="button"
                  onClick={() =>
                    downloadAuthorized(`/api/alumni/resumes/${row.id}/file`, row.original_filename).catch((err) =>
                      setError(friendlyError(err, "We couldn't download that file. Please try again."))
                    )
                  }
                >
                  <DownloadIcon size={14} />
                  Download
                </button>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </PortalShell>
  );
}
