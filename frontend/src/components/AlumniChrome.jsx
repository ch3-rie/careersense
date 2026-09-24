import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CheckIcon,
  ClockIcon,
  CreditCardIcon,
  InfoIcon,
} from "./icons";
import { api } from "../lib/api";

export function SourceBadge({ children }) {
  if (!children) return null;
  return <span className="source-badge">{children}</span>;
}

export function StatusMark({ tone = "pending", icon, children }) {
  return (
    <span className={`status-mark tone-${tone}`}>
      {icon ? <span className="status-mark-icon" aria-hidden="true">{icon}</span> : null}
      <span>{children}</span>
    </span>
  );
}

const RING_VIEWBOX = 100;

export function CompletionRing({ percent, loading = false, complete = false, size = 152, stroke = 8 }) {
  const known = !loading && percent != null && percent !== "";
  const value = known ? Math.max(0, Math.min(100, Number(percent) || 0)) : 0;
  const radius = (RING_VIEWBOX - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value / 100);
  return (
    <div
      className={`alumni-complete-ring${loading ? " is-loading" : ""}${complete ? " is-complete" : ""}`}
      style={{ width: size, height: size }}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={known ? value : undefined}
      aria-valuetext={known ? `${value} percent complete` : "Profile completion loading"}
      aria-label={known ? `Profile ${value} percent complete` : "Profile completion loading"}
      aria-busy={loading ? "true" : undefined}
    >
      <svg viewBox={`0 0 ${RING_VIEWBOX} ${RING_VIEWBOX}`} aria-hidden="true">
        <circle
          className="alumni-complete-ring-track"
          cx={RING_VIEWBOX / 2}
          cy={RING_VIEWBOX / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
        />
        <circle
          className="alumni-complete-ring-value"
          cx={RING_VIEWBOX / 2}
          cy={RING_VIEWBOX / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={known ? offset : circumference}
          strokeLinecap="round"
        />
      </svg>
      <span className="alumni-complete-ring-label" aria-hidden="true">
        {known ? (
          <>
            <strong>{value}</strong>
            <span>%</span>
          </>
        ) : (
          <strong className="alumni-complete-value-pending">—</strong>
        )}
      </span>
    </div>
  );
}

export function CompletionBar({ percent, message, compact = false, title, loading = false, hideTitle = false, hideValue = false }) {
  const known = !loading && percent != null && percent !== "";
  const value = known ? Math.max(0, Math.min(100, Number(percent) || 0)) : 0;
  const heading = title || "Profile completion";
  const showCopy = !hideTitle || (!hideValue && (known || loading)) || message;
  return (
    <>
      {showCopy ? (
        <div className="alumni-complete-copy">
          {hideTitle ? null : <p className="alumni-complete-title">{heading}</p>}
          {known && !hideValue ? <p className="alumni-complete-value">{value}%</p> : null}
          {loading && !hideValue ? <p className="alumni-complete-value alumni-complete-value-pending">—</p> : null}
          {message ? <p className="muted">{message}</p> : null}
        </div>
      ) : null}
      <div
        className={`alumni-complete-meter${loading ? " is-loading" : ""}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={known ? value : undefined}
        aria-valuetext={known ? `${value} percent complete` : "Profile completion loading"}
        aria-label={known ? `Profile ${value} percent complete` : "Profile completion loading"}
        aria-busy={loading ? "true" : undefined}
      >
        <span style={known ? { width: `${value}%` } : undefined} />
      </div>
    </>
  );
}

export function ServiceTile({ to, title, status, detail, icon, action }) {
  const body = (
    <>
      <span className="service-tile-icon" aria-hidden="true">{icon}</span>
      <span className="service-tile-copy">
        <strong>{title}</strong>
        {detail ? <span className="muted">{detail}</span> : null}
        {status ? <span className="service-tile-kicker">{status}</span> : null}
        {action ? <span className="service-tile-action">{action}</span> : null}
      </span>
    </>
  );
  if (to) {
    return <Link className="service-tile" to={to}>{body}</Link>;
  }
  return <div className="service-tile is-static">{body}</div>;
}

const AAC_ICONS = {
  NotYetApplied: InfoIcon,
  ForVerification: ClockIcon,
  Approved: CheckIcon,
  ReadyForPickup: CreditCardIcon,
  Claimed: CheckCircleIcon,
  ForRenewal: AlertTriangleIcon,
};

const AAC_TONES = {
  NotYetApplied: "pending",
  ForVerification: "info",
  Approved: "info",
  ReadyForPickup: "ok",
  Claimed: "ok",
  ForRenewal: "warn",
};

export function AacStatus({ card, compact = false, office }) {
  const status = card?.status || "NotYetApplied";
  const Icon = AAC_ICONS[status] || InfoIcon;
  const tone = AAC_TONES[status] || "pending";
  const label = card?.label || status.replace(/([a-z])([A-Z])/g, "$1 $2");
  const showPickup = Boolean(card?.show_pickup && office);
  return (
    <div className={`aac-status tone-${tone} ${compact ? "is-compact" : ""}`}>
      <StatusMark tone={tone} icon={<Icon size={compact ? 16 : 20} />}>
        {label}
      </StatusMark>
      {compact ? null : (
        <>
          <h2>{card?.headline || label}</h2>
          {card?.next_action ? <p className="lead">{card.next_action}</p> : null}
          {showPickup ? (
            <dl className="aac-pickup">
              <dt>Pickup location</dt>
              <dd>
                {office.name || "Alumni Affairs and Placement Services (AAPS)"}
                {office.location || card.pickup_location ? (
                  <>
                    <br />
                    {office.location || card.pickup_location}
                  </>
                ) : null}
              </dd>
              {office.hours ? (
                <>
                  <dt>Office hours</dt>
                  <dd>{office.hours}</dd>
                </>
              ) : null}
              {office.phone ? (
                <>
                  <dt>Phone</dt>
                  <dd>{office.phone}</dd>
                </>
              ) : null}
            </dl>
          ) : null}
        </>
      )}
    </div>
  );
}

export function AuthImage({ src, alt = "", className = "", loading }) {
  const [url, setUrl] = useState("");

  useEffect(() => {
    if (!src) {
      setUrl("");
      return undefined;
    }
    let objectUrl = "";
    let cancelled = false;
    api(src, { blob: true })
      .then((blob) => {
        if (cancelled || !(blob instanceof Blob)) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setUrl("");
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (!url) return null;
  return <img className={className} src={url} alt={alt} loading={loading} decoding="async" />;
}

export function notifyGroup(item) {
  const category = String(item?.category || "").toLowerCase();
  const title = String(item?.title || "").toLowerCase();
  if (category === "profile_update" || category === "action_required") return "Action required";
  if (category === "tracer") return "Tracer reminders";
  if (category === "announcement") return "Alumni announcements";
  if (category === "card" && /apply|pickup|renewal|ready/.test(title)) return "Action required";
  if (category === "card" || category === "perk") return "Application updates";
  return "Alumni announcements";
}
