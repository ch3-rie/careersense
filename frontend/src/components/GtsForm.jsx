import GtsSchemaForm from "./GtsSchemaForm";
import { Skeleton } from "./ui";

export default function GtsForm({
  initial,
  options,
  onSubmit,
  submitLabel,
  busy,
  extraNotice,
  schema,
  preview,
  readOnly,
  closedMessage,
  confirmSubmit,
  alignmentHint,
  variant,
  resume,
}) {
  const liveSchema = schema || options?.survey;
  if (liveSchema?.sections?.length) {
    return (
      <GtsSchemaForm
        schema={liveSchema}
        initial={initial}
        onSubmit={onSubmit}
        submitLabel={submitLabel}
        busy={busy}
        extraNotice={extraNotice}
        preview={preview}
        readOnly={readOnly}
        closedMessage={closedMessage}
        confirmSubmit={confirmSubmit}
        alignmentHint={alignmentHint}
        variant={variant}
        resume={resume}
      />
    );
  }
  if (options == null && schema == null) {
    return (
      <div className="gts-loading" role="status">
        <p className="muted">Loading the Graduate Tracer Survey…</p>
        <Skeleton rows={5} />
      </div>
    );
  }
  return <p className="muted">The Graduate Tracer Survey is not available yet. Please try again shortly.</p>;
}
