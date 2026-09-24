import { useEffect, useRef, useState } from "react";
import { BellIcon } from "./icons";
import { notifyGroup } from "./AlumniChrome";
import { Dialog } from "./ui";
import { formatDateTime, fullName } from "../lib/format";
import { PerksDirectory } from "./PerksDirectory";
import { DigitalAlumniCard } from "./AngeleneanCard";

export function initials(profile) {
  const first = String(profile?.first_name || "").trim();
  const last = String(profile?.last_name || "").trim();
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase() || "A";
}

export function ProfilePhoto({ profile, src, size = "md" }) {
  const name = fullName(profile);
  const label = name && name !== "—" ? `${name} profile photo` : "Profile photo";
  return (
    <div className={`profile-photo ${size}`}>
      {src ? <img src={src} alt={label} /> : <span aria-hidden="true">{initials(profile)}</span>}
    </div>
  );
}

export function NotificationBell({ items = [], onRead, onReadAll, loading, error, onRetry }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const panelRef = useRef(null);
  const unread = items.filter((item) => !item.read).length;
  const grouped = items.reduce((acc, item) => {
    const group = notifyGroup(item);
    acc[group] = acc[group] || [];
    acc[group].push(item);
    return acc;
  }, {});

  useEffect(() => {
    function onDoc(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    function onKey(event) {
      if (event.key === "Escape") {
        setOpen(false);
        rootRef.current?.querySelector("button")?.focus();
        return;
      }
      if (!open || event.key !== "Tab") return;
      const itemsInPanel = panelRef.current
        ? [...panelRef.current.querySelectorAll("a, button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")].filter(
            (el) => !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true"
          )
        : [];
      if (!itemsInPanel.length) return;
      const first = itemsInPanel[0];
      const last = itemsInPanel[itemsInPanel.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const first = panelRef.current?.querySelector("button, [href]");
    first?.focus();
  }, [open]);

  return (
    <div className="notify-wrap" ref={rootRef}>
      <button
        type="button"
        className="btn btn-outline notify-bell"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={unread ? `${unread} unread notifications` : "Notifications"}
        onClick={() => setOpen((value) => !value)}
      >
        <BellIcon size={18} />
        {unread ? <span className="notify-dot">{unread > 9 ? "9+" : unread}</span> : null}
      </button>
      {open ? (
        <div className="notify-panel" role="dialog" aria-label="Notifications" ref={panelRef}>
          <div className="notify-panel-head">
            <strong>Notifications</strong>
            {unread ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={onReadAll}>
                Mark all as read
              </button>
            ) : null}
          </div>
          {loading ? (
            <p className="muted notify-empty">Loading notifications…</p>
          ) : error ? (
            <div className="notify-empty">
              <p className="muted">We couldn't load your notifications.</p>
              {onRetry ? (
                <button type="button" className="btn btn-outline btn-sm" onClick={onRetry}>Try again</button>
              ) : null}
            </div>
          ) : !items.length ? (
            <div className="notify-empty">
              <p className="notify-empty-title">You're all caught up</p>
              <p className="muted">There are no new notifications.</p>
            </div>
          ) : (
            <ul className="notify-list">
              {Object.entries(grouped).map(([group, rows]) => (
                <li key={group} className="notify-group">
                  <p className="notify-group-label">{group}</p>
                  <ul>
                    {rows.map((item) => (
                      <li key={item.id} className={item.read ? "" : "unread"}>
                        <button type="button" onClick={() => onRead(item)}>
                          {item.category === "profile_update" ? <span className="notify-flag">Action required</span> : null}
                          <strong>{item.title}</strong>
                          <span className="notify-body">{item.body}</span>
                          {item.category === "profile_update" && item.link ? <span className="notify-cta">Update My Profile</span> : null}
                          <small>{formatDateTime(item.created_at)}</small>
                        </button>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function AlumniCardPreview({ profile, user, card, photoSrc, open, onClose }) {
  if (!open) return null;
  const identity = {
    ...profile,
    student_id: profile?.student_id || user?.student_id || "",
    student_number: profile?.student_number || user?.student_id || "",
  };
  return (
    <Dialog title="Angelenean Alumni Card" wide confirmLabel="Close" onConfirm={onClose} onClose={onClose}>
      <DigitalAlumniCard identity={identity} card={card} photoSrc={photoSrc} />
    </Dialog>
  );
}

export function cardTone(status) {
  if (status === "Claimed" || status === "Active") return "active";
  if (status === "ReadyForPickup" || status === "Approved" || status === "Available") return "aligned";
  if (status === "ForVerification" || status === "Processing") return "unknown";
  if (status === "ForRenewal") return "pending";
  return "pending";
}

export function cardLabel(status) {
  return {
    NotYetApplied: "Not yet applied",
    ForVerification: "For verification",
    Approved: "Approved",
    ReadyForPickup: "Ready for pickup",
    Claimed: "Claimed",
    ForRenewal: "For renewal",
    ActionNeeded: "Not yet applied",
    Processing: "For verification",
    Active: "Claimed",
    Pending: "Not yet applied",
    Available: "Ready for pickup",
  }[status] || status;
}

export function AlumniPerks(props) {
  return <PerksDirectory {...props} />;
}
