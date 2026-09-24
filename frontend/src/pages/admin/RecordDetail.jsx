import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { DetailHeader, TracerRecordLayout } from "../../components/AdminReview";
import { PortalShell } from "../../components/Layout";
import { Alert, LoadError, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatLongDate, questionLabelsFrom } from "../../lib/format";

export default function AdminRecordDetail() {
  const { id } = useParams();
  const [record, setRecord] = useState(null);
  const [error, setError] = useState("");
  const [labels, setLabels] = useState({});

  function load() {
    setError("");
    api(`/api/admin/tracer/${id}`)
      .then(setRecord)
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
    api("/api/auth/options")
      .then((opts) => setLabels(questionLabelsFrom(opts.supplementary_questions)))
      .catch(() => {});
  }, [id]);

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
        <TracerRecordLayout record={record} questionLabels={labels} />
      ) : null}
    </PortalShell>
  );
}
