import { Link } from "react-router-dom";
import { CheckCircleIcon, InboxIcon } from "./icons";

export { FileCard, OfficialMark, StatusBadge, VerifyBanner } from "./AdminReview";

export function MetricCard({ label, value, icon, hint, to, cta }) {
  return (
    <article className="card metric ops-metric">
      <div className="ops-metric-top">
        {icon ? <span className="ops-metric-icon" aria-hidden="true">{icon}</span> : null}
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      {hint ? <p className="ops-metric-hint">{hint}</p> : null}
      {to && cta ? (
        <Link className="ops-metric-cta" to={to}>{cta}</Link>
      ) : null}
    </article>
  );
}

export function NextStepCard({ title, text, value, to, action }) {
  return (
    <article className="card next-card">
      <div>
        <h3>{title}</h3>
        <p>{text}</p>
        {value ? <p className="next-value">{value}</p> : null}
      </div>
      <Link className="btn btn-outline" to={to}>{action}</Link>
    </article>
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
        {items.map((item) => (
          <span
            key={item.label}
            className={`share-seg ${item.tone}`}
            style={{ flexGrow: item.count || 0, flexBasis: 0, display: item.count ? undefined : "none" }}
            title={`${item.label}: ${item.count}`}
          />
        ))}
      </div>
      <ul className="share-legend">
        {items.map((item) => (
          <li key={item.label}>
            <span className={`share-dot ${item.tone}`} aria-hidden="true" />
            <span>{item.label}</span>
            <strong>{item.count}</strong>
            <em>{Math.round(((item.count || 0) / total) * 100)}%</em>
          </li>
        ))}
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
