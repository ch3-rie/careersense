import { Link } from "react-router-dom";
import { CheckCircleIcon, InboxIcon } from "./icons";

export { FileCard, OfficialMark, StatusBadge, VerifyBanner } from "./AdminReview";

export function directoryPath(from, params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value) search.set(key, String(value));
  });
  if (from) search.set("from", from);
  return `/admin/directory?${search}`;
}

export function SnapshotBackLink({ from }) {
  if (from !== "dashboard" && from !== "reports") return null;
  const reports = from === "reports";
  return (
    <Link className="snapshot-back" to={reports ? "/admin/reports?restore=1" : "/admin"}>
      {reports ? "Back to Reports" : "Back to Dashboard"}
    </Link>
  );
}

export function MetricCard({ label, value, icon, hint, to, cta, title, describedBy, emphasis = false }) {
  const className = `card metric ops-metric${to ? " is-link" : ""}${emphasis ? " is-attention" : ""}`;
  const body = (
    <>
      <div className="ops-metric-top">
        {icon ? <span className="ops-metric-icon" aria-hidden="true">{icon}</span> : null}
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      {hint ? <p className="ops-metric-hint">{hint}</p> : null}
      {cta ? <span className="ops-metric-cta">{cta}</span> : null}
    </>
  );
  if (!to) return <article className={className} title={title}>{body}</article>;
  return (
    <Link
      className={className}
      to={to}
      title={title}
      aria-describedby={describedBy || undefined}
      aria-label={`${label}: ${value}. ${hint || ""} ${cta || ""}`.trim()}
    >
      {body}
    </Link>
  );
}

export function NextStepCard({ title, text, value, to, action, icon, emphasis = false }) {
  return (
    <Link
      className={`card next-card is-link${emphasis ? " is-emphasis" : ""}`}
      to={to}
      aria-label={`${title}. ${value ? `${value}. ` : ""}${text} ${action}`.replace(/\s+/g, " ").trim()}
    >
      <div className="next-card-main">
        {icon ? <span className="ops-metric-icon" aria-hidden="true">{icon}</span> : null}
        <div>
          <h3>{title}</h3>
          <p>{text}</p>
          {value ? <p className="next-value">{value}</p> : null}
        </div>
      </div>
      <span className="btn btn-outline">{action}</span>
    </Link>
  );
}

export function ShareStrip({ items, emptyTitle, emptyText }) {
  const total = items.reduce((sum, item) => sum + (Number(item.count) || 0), 0);
  if (!total) {
    return (
      <div className="empty compact">
        <h3>{emptyTitle}</h3>
        <p>{emptyText}</p>
      </div>
    );
  }
  return (
    <div className="share-strip-wrap">
      <div className="share-strip" role="img" aria-label={items.map((item) => `${item.label} ${item.count}`).join(", ")}>
        {items.map((item) => {
          const style = { flexGrow: item.count || 0, flexBasis: 0, display: item.count ? undefined : "none" };
          const className = `share-seg ${item.tone}${item.to ? " is-link" : ""}`;
          return item.to ? (
            <Link key={item.label} className={className} style={style} to={item.to} title={`${item.label}: ${item.count}`} aria-label={`${item.label}: ${item.count}`} />
          ) : (
            <span key={item.label} className={className} style={style} title={`${item.label}: ${item.count}`} />
          );
        })}
      </div>
      <ul className="share-legend">
        {items.map((item) => {
          const body = (
            <>
              <span className={`share-dot ${item.tone}`} aria-hidden="true" />
              <span>{item.label}</span>
              <strong>{item.count}</strong>
              <em>{Math.round(((item.count || 0) / total) * 100)}%</em>
            </>
          );
          return (
            <li key={item.label}>
              {item.to ? <Link className="share-legend-link" to={item.to}>{body}</Link> : body}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function EmptyState({ icon, title, text, action }) {
  return (
    <div className="empty ops-empty">
      {icon ? <div className="empty-icon">{icon}</div> : null}
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

export function QueueClear() {
  return (
    <EmptyState
      icon={<CheckCircleIcon size={40} />}
      title="Queue is clear"
      text="All registration requests have been reviewed."
    />
  );
}

export function ChartEmpty() {
  return (
    <EmptyState
      icon={<InboxIcon size={40} />}
      title="No submission data yet"
      text="Tracer submissions will appear here once records are available."
    />
  );
}
