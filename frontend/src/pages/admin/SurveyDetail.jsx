import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DetailHeader } from "../../components/AdminReview";
import GtsForm from "../../components/GtsForm";
import { PortalShell } from "../../components/Layout";
import { Alert, Badge, Empty, LoadError, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime, questionTypeLabel } from "../../lib/format";
import {
  ALIGNMENT_FIELD_KEYS,
  CORE_SECTION_KEYS,
  flattenQuestions,
  findQuestionLocation,
  findSectionLocation,
  optionLabel,
  optionValue,
  questionIndex,
  SYSTEM_FIELD_KEYS,
  visibilitySummary,
} from "../../lib/surveySchema";

const PREVIEW_SEED = {};

function locateQuestion(schema, questionId) {
  if (!schema || !questionId) return null;
  const direct = findQuestionLocation(schema, questionId);
  if (direct) return direct;
  return flattenQuestions(schema).find(({ question }) => (
    question.field_key === questionId || question.extra_key === questionId
  )) || null;
}

function questionSchemaPreview(section, question) {
  return {
    title: question.label || "Question preview",
    intro: "",
    sections: [
      {
        id: section?.id || "section",
        key: section?.key || "preview",
        name: section?.name || "Question",
        subsections: [
          {
            id: "preview",
            name: "",
            questions: [question],
          },
        ],
      },
    ],
  };
}

function isSystemQuestion(question) {
  const key = question?.field_key || question?.id;
  return Boolean(question?.system || SYSTEM_FIELD_KEYS.has(key) || ALIGNMENT_FIELD_KEYS.has(key) || question?.type === "repeatable_group");
}

export function AdminSurveyQuestionDetail() {
  const { questionId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setError("");
    setBusy(true);
    api("/api/admin/survey")
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false));
  }

  useEffect(() => { load(); }, [questionId]);

  const draftHit = locateQuestion(data?.draft, questionId);
  const publishedHit = locateQuestion(data?.published, questionId);
  const hit = draftHit || publishedHit;
  const question = hit?.question;
  const section = hit?.section;
  const inDraft = Boolean(draftHit);
  const inPublished = Boolean(publishedHit);
  const byId = useMemo(() => questionIndex(inDraft ? data?.draft : data?.published), [data, inDraft]);

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <div className="review-detail-shell survey-detail-page">
        <DetailHeader
          backTo="/admin/survey"
          backLabel="Back to Survey Manager"
          title={question?.label || "Survey question"}
          meta={section ? `${section.name}${hit?.subsection?.name ? ` · ${hit.subsection.name}` : ""}` : "Graduate Tracer Survey"}
          actions={
            question ? (
              <Link className="btn btn-navy" to={`/admin/survey?question=${encodeURIComponent(question.id)}`}>
                Edit in Survey Manager
              </Link>
            ) : null
          }
        />
        <Alert type="error">{error && data ? error : null}</Alert>
        {error && !data ? <LoadError onRetry={load}>{error}</LoadError> : null}
        {!question && !error ? (
          <Empty title="Question not found">
            This question is not in the current draft or published survey. It may have been removed from the Survey Manager.
          </Empty>
        ) : null}
        {question ? (
          <>
            <section className="detail-section">
              <h2>Record information</h2>
              <div className="survey-detail-meta">
                <Badge tone={inPublished ? "active" : "pending"}>{inPublished ? "On live GTS" : "Draft only"}</Badge>
                {inDraft && !inPublished ? <Badge tone="pending">Not yet published</Badge> : null}
                {isSystemQuestion(question) ? <Badge tone="pending">System field</Badge> : <Badge>Custom question</Badge>}
                {question.required ? <Badge tone="info">Required</Badge> : null}
              </div>
              <dl className="survey-detail-dl">
                <div>
                  <dt>Question title</dt>
                  <dd>{question.label || "Untitled question"}{question.required ? <span className="req"> *</span> : null}</dd>
                </div>
                <div>
                  <dt>Description</dt>
                  <dd>{question.description || "No description"}</dd>
                </div>
                <div>
                  <dt>Question type</dt>
                  <dd>{questionTypeLabel(question.type)}</dd>
                </div>
                <div>
                  <dt>Section</dt>
                  <dd>
                    {section ? (
                      <Link to={`/admin/survey/sections/${encodeURIComponent(section.id)}`}>{section.name}</Link>
                    ) : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Question ID</dt>
                  <dd>{question.id}</dd>
                </div>
                <div>
                  <dt>System field key</dt>
                  <dd>{question.field_key || question.extra_key || "—"}</dd>
                </div>
                <div>
                  <dt>Storage</dt>
                  <dd>{question.storage === "extra" ? "Supplementary (extra_answers)" : "Core tracer field"}</dd>
                </div>
                <div>
                  <dt>Conditional visibility</dt>
                  <dd>{visibilitySummary(question, byId) || "Always visible"}</dd>
                </div>
              </dl>
            </section>

            {(question.options || []).length ? (
              <section className="detail-section">
                <h2>Choices</h2>
                <ol className="survey-detail-list">
                  {(question.options || []).map((opt, index) => (
                    <li key={`${optionValue(opt)}-${index}`}>{optionLabel(opt) || optionValue(opt) || "Untitled option"}</li>
                  ))}
                </ol>
              </section>
            ) : null}

            <section className="detail-section">
              <h2>How this question appears</h2>
              <p className="muted">This preview uses the same Graduate Tracer Survey renderer as registration and the Alumni Portal.</p>
              <GtsForm schema={questionSchemaPreview(section, question)} initial={PREVIEW_SEED} preview submitLabel="Preview only" />
            </section>

            <section className="detail-section">
              <h2>Available actions</h2>
              <div className="page-actions">
                <Link className="btn btn-navy" to={`/admin/survey?question=${encodeURIComponent(question.id)}`}>
                  Edit in Survey Manager
                </Link>
                <Link className="btn btn-outline" to="/admin/survey">Return to Survey Manager</Link>
              </div>
              {busy ? <p className="muted">Refreshing…</p> : null}
            </section>
          </>
        ) : null}
      </div>
    </PortalShell>
  );
}

export function AdminSurveySectionDetail() {
  const { sectionId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  function load() {
    setError("");
    api("/api/admin/survey")
      .then(setData)
      .catch((err) => setError(err.message));
  }

  useEffect(() => { load(); }, [sectionId]);

  const draftHit = findSectionLocation(data?.draft, sectionId);
  const publishedHit = findSectionLocation(data?.published, sectionId);
  const hit = draftHit || publishedHit;
  const section = hit?.section;
  const core = CORE_SECTION_KEYS.includes(section?.key);
  const questions = (section?.subsections || []).flatMap((sub) => sub.questions || []);

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <div className="review-detail-shell survey-detail-page">
        <DetailHeader
          backTo="/admin/survey"
          backLabel="Back to Survey Manager"
          title={section?.name || "Survey section"}
          meta={core ? "Core Graduate Tracer Survey section" : "Custom section"}
          actions={
            section ? (
              <Link className="btn btn-navy" to={`/admin/survey?section=${encodeURIComponent(section.id)}`}>
                Edit in Survey Manager
              </Link>
            ) : null
          }
        />
        <Alert type="error">{error && data ? error : null}</Alert>
        {error && !data ? <LoadError onRetry={load}>{error}</LoadError> : null}
        {!section && !error ? (
          <Empty title="Section not found">This section is not in the current draft or published survey.</Empty>
        ) : null}
        {section ? (
          <>
            <section className="detail-section">
              <h2>Record information</h2>
              <div className="survey-detail-meta">
                <Badge tone={publishedHit ? "active" : "pending"}>{publishedHit ? "On live GTS" : "Draft only"}</Badge>
                {core ? <Badge tone="pending">Core section</Badge> : <Badge>Custom section</Badge>}
              </div>
              <dl className="survey-detail-dl">
                <div>
                  <dt>Section title</dt>
                  <dd>{section.name}</dd>
                </div>
                <div>
                  <dt>Description</dt>
                  <dd>{section.description || "No description"}</dd>
                </div>
                <div>
                  <dt>Section ID</dt>
                  <dd>{section.id}</dd>
                </div>
                <div>
                  <dt>Questions</dt>
                  <dd>{questions.length}</dd>
                </div>
              </dl>
            </section>
            <section className="detail-section">
              <h2>Questions in this section</h2>
              {questions.length ? (
                <ol className="survey-detail-list">
                  {questions.map((question) => (
                    <li key={question.id}>
                      <Link to={`/admin/survey/questions/${encodeURIComponent(question.id)}`}>
                        {question.label || "Untitled question"}
                      </Link>
                      {question.required ? <span className="req"> *</span> : null}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="muted">This section has no questions yet.</p>
              )}
            </section>
            <section className="detail-section">
              <h2>Available actions</h2>
              <div className="page-actions">
                <Link className="btn btn-navy" to={`/admin/survey?section=${encodeURIComponent(section.id)}`}>
                  Edit in Survey Manager
                </Link>
                <Link className="btn btn-outline" to="/admin/survey">Return to Survey Manager</Link>
              </div>
            </section>
          </>
        ) : null}
      </div>
    </PortalShell>
  );
}

export function AdminSurveyVersionDetail() {
  const { versionNumber } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setError("");
    api(`/api/admin/survey/versions/${versionNumber}`)
      .then(setDetail)
      .catch((err) => setError(err.message));
  }

  useEffect(() => { load(); }, [versionNumber]);

  async function restore() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/admin/survey/versions/${versionNumber}/restore`, { method: "POST" });
      navigate("/admin/survey");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!detail && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <div className="review-detail-shell survey-detail-page">
        <DetailHeader
          backTo="/admin/survey"
          backLabel="Back to Survey Manager"
          title={detail ? `Survey version ${detail.version}` : "Survey version"}
          meta={detail ? `${detail.status} · ${detail.question_count || 0} questions` : null}
          actions={
            detail ? (
              <button className="btn btn-outline" type="button" onClick={restore} disabled={busy}>
                {busy ? "Restoring..." : "Restore to draft"}
              </button>
            ) : null
          }
        />
        <Alert type="error">{error}</Alert>
        {error && !detail ? <LoadError onRetry={load}>{error}</LoadError> : null}
        {detail ? (
          <>
            <section className="detail-section">
              <h2>Record information</h2>
              <div className="survey-detail-meta">
                <Badge tone={detail.status === "Published" ? "active" : "unknown"}>{detail.status}</Badge>
              </div>
              <dl className="survey-detail-dl">
                <div>
                  <dt>Version</dt>
                  <dd>{detail.version}</dd>
                </div>
                <div>
                  <dt>Published</dt>
                  <dd>{formatDateTime(detail.published_at)}</dd>
                </div>
                <div>
                  <dt>Published by</dt>
                  <dd>{detail.published_by || "—"}</dd>
                </div>
                <div>
                  <dt>Questions</dt>
                  <dd>{detail.question_count}</dd>
                </div>
                <div>
                  <dt>Survey title</dt>
                  <dd>{detail.schema?.title || "Graduate Tracer Survey"}</dd>
                </div>
              </dl>
            </section>
            <section className="detail-section">
              <h2>Version preview</h2>
              <p className="muted">This is the survey configuration stored for this version. Historical responses are not changed by viewing or restoring it.</p>
              {detail.schema?.sections?.length ? (
                <GtsForm schema={detail.schema} initial={PREVIEW_SEED} preview submitLabel="Preview only" />
              ) : (
                <Empty title="No questions in this version" />
              )}
            </section>
            <section className="detail-section">
              <h2>Available actions</h2>
              <div className="page-actions">
                <button className="btn btn-navy" type="button" onClick={restore} disabled={busy}>
                  {busy ? "Restoring..." : "Restore to draft"}
                </button>
                <Link className="btn btn-outline" to="/admin/survey">Return to Survey Manager</Link>
              </div>
            </section>
          </>
        ) : null}
      </div>
    </PortalShell>
  );
}
