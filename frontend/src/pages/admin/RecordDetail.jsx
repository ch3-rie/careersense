import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { DetailHeader, TracerRecordLayout } from "../../components/AdminReview";
import GtsForm from "../../components/GtsForm";
import { PortalShell } from "../../components/Layout";
import { Alert, ExpandDetails, LoadError, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatLongDate, questionLabelsFrom } from "../../lib/format";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

export default function AdminRecordDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState(null);
  const [error, setError] = useState("");
  const [labels, setLabels] = useState({});
  const [survey, setSurvey] = useState(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setError("");
    api(`/api/admin/tracer/${id}`)
      .then(setRecord)
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
    api("/api/auth/options")
      .then((opts) => {
        setLabels(questionLabelsFrom(opts.supplementary_questions));
        setSurvey(opts.survey || null);
      })
      .catch(() => {});
  }, [id]);

  async function saveOfficial(payload) {
    setBusy(true);
    setError("");
    try {
      const saved = await api(`/api/admin/tracer/${id}`, { method: "POST", body: payload });
      showToast("success", "Official tracer record updated.");
      if (saved?.id && String(saved.id) !== String(id)) navigate(`/admin/records/${saved.id}`);
      else setRecord(saved);
    } catch (err) {
      setError(friendlyError(err, "We couldn't save this tracer record. Please review the answers and try again."));
    } finally {
      setBusy(false);
    }
  }

  if (!record && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  return (
    <PortalShell role="Admin">
      <DetailHeader
        backTo="/admin/records"
        backLabel="Back to Tracer Records"
        title="Tracer Record Details"
        name={
          record?.email ? (
            <a href={`mailto:${record.email}`}>{record.email}</a>
          ) : null
        }
        meta={record ? `Submitted ${formatLongDate(record.submitted_at)}` : null}
      />
      <Alert type="error">{error}</Alert>
      {error && !record ? (
        <LoadError onRetry={load}>{error}</LoadError>
      ) : record ? (
        <>
          <TracerRecordLayout record={record} questionLabels={labels} />
          <section className="detail-section official-tracer-manage">
            <h2>Official tracer record</h2>
            <p className="muted">OAAPS can review and update this graduate's saved tracer submission, including household background that is not shown to the alumnus.</p>
            {survey ? (
              <ExpandDetails summary="Manage official tracer record" hint="Edit and save the official survey answers">
                <GtsForm
                  schema={survey}
                  initial={{ ...(record.data || {}), extra_answers: record.extra_answers || {} }}
                  onSubmit={saveOfficial}
                  busy={busy}
                  submitLabel={busy ? "Saving…" : "Save official tracer record"}
                />
              </ExpandDetails>
            ) : null}
          </section>
        </>
      ) : null}
    </PortalShell>
  );
}
