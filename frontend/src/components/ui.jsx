import { Children, cloneElement, isValidElement, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { AlertTriangleIcon, CheckCircleIcon, CheckIcon, ExternalLinkIcon, InfoIcon, XIcon } from "./icons";
import { dismissToast, subscribeToasts, toastDuration } from "../lib/toasts";

const ALERT_ICONS = {
  error: AlertTriangleIcon,
  warn: AlertTriangleIcon,
  warning: AlertTriangleIcon,
  ok: CheckCircleIcon,
  success: CheckCircleIcon,
  info: InfoIcon,
};

export function Alert({ type = "info", children, alertRef, title }) {
  if (!children && !title) return null;
  const isError = type === "error";
  const Icon = ALERT_ICONS[type] || InfoIcon;
  return (
    <div
      className={`alert ${type} has-icon`}
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      tabIndex={isError ? -1 : undefined}
      ref={alertRef}
    >
      <span className="alert-icon" aria-hidden="true">
        <Icon size={18} />
      </span>
      <div className="alert-body">
        {title ? <strong>{title}</strong> : null}
        {children ? (title ? <p>{children}</p> : children) : null}
      </div>
    </div>
  );
}

export function Spinner() {
  return <div className="spinner" role="status" aria-label="Loading" />;
}

export function Empty({ title, children, icon, action, compact = false }) {
  return (
    <div className={`empty${compact ? " compact" : ""}`}>
      {icon ? <div className="empty-icon" aria-hidden="true">{icon}</div> : null}
      <h3>{title}</h3>
      {children ? <p>{children}</p> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}

export function SaveStatus({ state = "idle", savedLabel = "Saved just now", errorLabel = "Unable to save" }) {
  if (!state || state === "idle") return null;
  const labels = {
    saving: "Saving…",
    saved: savedLabel,
    error: errorLabel,
  };
  return (
    <p className={`save-status is-${state}`} role="status" aria-live="polite">
      {labels[state] || ""}
    </p>
  );
}

export function LoadError({ title = "Unable to load records", children, onRetry }) {
  return (
    <Empty
      title={title}
      action={
        onRetry ? (
          <button className="btn btn-navy" type="button" onClick={onRetry}>
            Try Again
          </button>
        ) : null
      }
    >
      {children || "Something went wrong while retrieving the data."}
    </Empty>
  );
}

export function Badge({ children, tone, title, icon }) {
  const raw = String(tone || children || "").toLowerCase().replace(/\s+/g, "-");
  return (
    <span className={`badge ${raw} ${icon ? "has-icon" : ""}`} title={title}>
      {icon ? <span className="badge-icon" aria-hidden="true">{icon}</span> : null}
      {children}
    </span>
  );
}

export function Breadcrumb({ items }) {
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      {items.map((item, index) => (
        <span key={item.label}>
          {index > 0 ? <span className="crumb-sep" aria-hidden="true">/</span> : null}
          {item.to ? <Link to={item.to}>{item.label}</Link> : <span aria-current="page">{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function PageHeader({ crumbs, actions }) {
  if (!crumbs?.length && !actions) return null;
  return (
    <header className="page-head">
      {crumbs?.length ? <Breadcrumb items={crumbs} /> : null}
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function GuideList({ title = "What you can do next", items }) {
  if (!items?.length) return null;
  return (
    <section className="guide-block">
      {title ? <h2 className="section-label">{title}</h2> : null}
      <div className="guide-grid">
        {items.map((item) => {
          const body = (
            <>
              <strong>{item.title}</strong>
              <p>{item.text}</p>
            </>
          );
          if (item.to) {
            return (
              <Link className="guide-card" to={item.to} key={item.title}>
                {body}
              </Link>
            );
          }
          return (
            <button type="button" className="guide-card" onClick={item.onClick} key={item.title}>
              {body}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function isControl(child) {
  return isValidElement(child) && (child.type === "input" || child.type === "select" || child.type === "textarea");
}

const SKIP_PLACEHOLDER = new Set(["checkbox", "radio", "file", "hidden", "date", "datetime-local", "month", "time"]);

function suggestPlaceholder(label, type = "text", tag = "input") {
  if (!label || tag === "select") return undefined;
  const name = String(label).replace(/\s+\*$/, "").replace(/\s*\([^)]*\)\s*$/, "").trim();
  if (!name) return undefined;
  const lower = name.charAt(0).toLowerCase() + name.slice(1);
  if (type === "password") {
    if (/confirm/i.test(name)) return "Re-enter your password";
    if (/current/i.test(name)) return "Enter your current password";
    if (/new/i.test(name)) return "Enter your new password";
    return "Enter your password";
  }
  if (type === "email" || /^e-?mail$/i.test(name) || /^personal email$/i.test(name)) return "Enter your email";
  if (/^please /i.test(name)) return name;
  if (/search/i.test(name)) {
    return `Enter ${lower.replace(/^search( by)?\s+/i, "")}`;
  }
  if (/^(include|develop|improve|increase|other)\b/i.test(name)) return "Enter your suggestion";
  if (name.length > 42) return "Enter your answer";
  return `Enter your ${lower}`;
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M10.6 10.7a3 3 0 0 0 4.2 4.2" />
      <path d="M9.9 5.1A11 11 0 0 1 12 5c6.4 0 10 7 10 7a19 19 0 0 1-3.3 3.9" />
      <path d="M6.1 6.1C3.8 7.8 2 12 2 12s3.6 7 10 7c1.5 0 2.9-.3 4.2-.8" />
    </svg>
  );
}

function PasswordToggle({ children }) {
  const [visible, setVisible] = useState(false);
  const input = Children.only(children);
  const label = visible ? "Hide password" : "Show password";
  return (
    <div className="password-field">
      {cloneElement(input, { type: visible ? "text" : "password" })}
      <button
        type="button"
        className="password-toggle"
        onClick={() => setVisible((on) => !on)}
        aria-label={label}
        aria-pressed={visible}
        title={label}
      >
        {visible ? <EyeIcon /> : <EyeOffIcon />}
      </button>
    </div>
  );
}

function plainLabel(label) {
  return String(label ?? "").replace(/\s*\*+\s*$/, "");
}

export function Field({ label, hint, note, children, required, error }) {
  const autoId = useId();
  const kids = Children.toArray(children);
  const control = kids.find(isControl);
  const id = control?.props?.id || autoId;
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null, note ? `${id}-note` : null].filter(Boolean).join(" ") || undefined;
  let assigned = false;
  return (
    <div className={`field ${error ? "has-error" : ""}`}>
      {label ? (
        <label htmlFor={id}>
          {required ? plainLabel(label) : label}
          {required ? <span className="req" aria-hidden="true">*</span> : null}
        </label>
      ) : null}
      {kids.map((child, index) => {
        if (!isControl(child) || assigned) return child;
        assigned = true;
        const type = child.props.type || "text";
        const extras = {
          key: child.key || index,
          id,
          "aria-required": required || child.props.required || undefined,
          "aria-invalid": error ? true : undefined,
          "aria-describedby": describedBy,
        };
        if (!child.props.placeholder && child.type !== "select" && !SKIP_PLACEHOLDER.has(type)) {
          extras.placeholder = suggestPlaceholder(plainLabel(label), type, child.type);
        }
        const cloned = cloneElement(child, extras);
        if (type === "password") {
          return <PasswordToggle key={child.key || index}>{cloned}</PasswordToggle>;
        }
        return cloned;
      })}
      {hint ? <span className="hint" id={`${id}-hint`}>{hint}</span> : null}
      {error ? <span className="field-error" id={`${id}-error`}>{error}</span> : null}
      {note ? <ResumeNote id={`${id}-note`}>{note}</ResumeNote> : null}
    </div>
  );
}

function ResumeNote({ id, children }) {
  if (!children) return null;
  return (
    <p className="resume-guidance" id={id} role="note">
      <InfoIcon size={16} />
      <span>{children}</span>
    </p>
  );
}

export function CheckGroup({ legend, required, error, note, children }) {
  const noteId = useId();
  return (
    <fieldset
      className={`field check-group ${error ? "has-error" : ""}`}
      aria-invalid={error ? true : undefined}
      aria-required={required || undefined}
      aria-describedby={note ? noteId : undefined}
    >
      {legend ? (
        <legend>
          {required ? plainLabel(legend) : legend}
          {required ? <span className="req" aria-hidden="true">*</span> : null}
        </legend>
      ) : null}
      {children}
      {error ? <span className="field-error">{error}</span> : null}
      {note ? <ResumeNote id={noteId}>{note}</ResumeNote> : null}
    </fieldset>
  );
}

const COMPACT_MAX_COUNT = 4;
const COMPACT_MAX_LENGTH = 22;

function isCompactChoiceList(labels) {
  if (labels.length < 2 || labels.length > COMPACT_MAX_COUNT) return false;
  return labels.every((label) => String(label || "").length <= COMPACT_MAX_LENGTH);
}

export function RadioOption({ name, value, checked, disabled, onChange, children, error }) {
  return (
    <label className={`choice-option ${checked ? "is-selected" : ""} ${error ? "is-error" : ""} ${disabled ? "is-disabled" : ""}`}>
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange(value)}
      />
      <span className="choice-option-text">{children}</span>
    </label>
  );
}

export function RadioChoiceList({ name, options, value, onChange, disabled, error }) {
  const compact = isCompactChoiceList(options.map((item) => item.label));
  return (
    <div className={`choice-list ${compact ? "is-compact" : ""}`} role="radiogroup">
      {options.map((item) => (
        <RadioOption
          key={item.value}
          name={name}
          value={item.value}
          checked={String(value || "") === String(item.value)}
          disabled={disabled}
          error={error}
          onChange={onChange}
        >
          {item.label}
        </RadioOption>
      ))}
    </div>
  );
}

export function RadioGroup({ legend, required, error, description, name, options, value, onChange, disabled }) {
  return (
    <CheckGroup legend={legend} required={required} error={error}>
      {description ? <p className="muted field-help">{description}</p> : null}
      <RadioChoiceList
        name={name}
        options={options}
        value={value}
        onChange={onChange}
        disabled={disabled}
        error={error}
      />
    </CheckGroup>
  );
}

export function TabList({ label, value, onChange, tabs, doneMap = {}, errorMap = {}, appearance = "primary" }) {
  const ids = tabs.map((item) => item[0]);
  const slug = String(label || "tabs").replace(/\s+/g, "-").toLowerCase();
  const isSteps = appearance === "steps";

  function move(delta) {
    const index = Math.max(0, ids.indexOf(value));
    onChange(ids[(index + delta + ids.length) % ids.length]);
  }

  return (
    <div
      className={`tabs ${appearance === "sub" ? "tabs-sub" : ""} ${isSteps ? "tabs-steps" : ""}`}
      role="tablist"
      aria-label={label}
      onKeyDown={(event) => {
        if (event.key === "ArrowRight") {
          event.preventDefault();
          move(1);
        } else if (event.key === "ArrowLeft") {
          event.preventDefault();
          move(-1);
        } else if (event.key === "Home") {
          event.preventDefault();
          onChange(ids[0]);
        } else if (event.key === "End") {
          event.preventDefault();
          onChange(ids[ids.length - 1]);
        }
      }}
    >
      {tabs.map(([id, text]) => {
        const selected = value === id;
        const done = Boolean(doneMap[id]);
        const hasError = Boolean(errorMap[id]);
        return (
          <button
            type="button"
            key={id}
            role="tab"
            id={`tab-${slug}-${id}`}
            aria-selected={selected}
            aria-controls={`panel-${slug}-${id}`}
            tabIndex={selected ? 0 : -1}
            className={`tab ${selected ? "on" : ""} ${done ? "done" : ""} ${hasError ? "has-error" : ""}`}
            onClick={() => onChange(id)}
          >
            {isSteps ? (
              <>
                <span className="tab-marker" aria-hidden="true">
                  {hasError ? "!" : done && !selected ? <CheckIcon size={14} /> : selected ? "●" : "○"}
                </span>
                <span className="tab-text">{text}</span>
              </>
            ) : (
              text
            )}
          </button>
        );
      })}
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pager">
      <span>
        Page {page} of {pages} · {total} records
      </span>
      <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </div>
  );
}

export function Skeleton({ rows = 4 }) {
  return (
    <div className="skeleton-stack" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div className="skeleton" key={index} />
      ))}
    </div>
  );
}

export function PageSkeleton({ variant = "default" }) {
  if (variant === "alumni") {
    return (
      <div className="alumni-skel" aria-hidden="true">
        <div className="alumni-skel-cover" />
        <div className="alumni-skel-hero">
          <div className="skeleton alumni-skel-photo" />
          <div>
            <div className="skeleton" style={{ width: 220, height: 26 }} />
            <div className="skeleton" style={{ width: 180, height: 14, marginTop: 10 }} />
            <div className="skeleton" style={{ width: 260, height: 12, marginTop: 8 }} />
          </div>
        </div>
        <div className="card"><Skeleton rows={3} /></div>
        <div className="card"><Skeleton rows={5} /></div>
        <div className="card"><Skeleton rows={4} /></div>
      </div>
    );
  }
  return (
    <>
      <div className="metrics">
        <div className="card metric"><Skeleton rows={2} /></div>
        <div className="card metric"><Skeleton rows={2} /></div>
        <div className="card metric"><Skeleton rows={2} /></div>
        <div className="card metric"><Skeleton rows={2} /></div>
      </div>
      <div className="card">
        <Skeleton rows={6} />
      </div>
    </>
  );
}

export function TableSkeleton({ rows = 8, cols = 5 }) {
  return (
    <div className="table-wrap" aria-hidden="true">
      <table className="data">
        <thead>
          <tr>
            {Array.from({ length: cols }).map((_, index) => (
              <th key={index}><div className="skeleton" style={{ width: index === 0 ? 90 : 70, height: 10 }} /></th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, row) => (
            <tr key={row}>
              {Array.from({ length: cols }).map((__, col) => (
                <td key={col}><div className="skeleton" style={{ width: col === 1 ? "70%" : "50%", height: 12 }} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ConfirmBar({ title, children, confirmLabel = "Confirm", danger, onConfirm, onCancel }) {
  return (
    <div className="confirm-bar">
      <div>
        <strong>{title}</strong>
        {children ? <p className="muted">{children}</p> : null}
      </div>
      <div className="hero-actions">
        <button type="button" className={danger ? "btn btn-danger" : "btn btn-navy"} onClick={onConfirm}>{confirmLabel}</button>
        <button type="button" className="btn btn-outline" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

export function Dialog({
  title,
  description,
  children,
  confirmLabel = "Confirm",
  danger,
  busy,
  onConfirm,
  onClose,
  wide,
  compact,
  hideActions,
  footer,
}) {
  const dialogRef = useRef(null);
  const previousFocus = useRef(null);
  const onCloseRef = useRef(onClose);
  const busyRef = useRef(busy);
  const titleId = useId();
  const descId = useId();
  onCloseRef.current = onClose;
  busyRef.current = busy;

  function requestClose() {
    if (busyRef.current) return;
    onCloseRef.current();
  }

  useEffect(() => {
    previousFocus.current = document.activeElement;
    const node = dialogRef.current;
    const body = node?.querySelector(".dialog-body");
    const firstField = focusablesIn(body)[0];
    (firstField || node)?.focus();
    const unlock = lockPageScroll();
    const entry = { node: dialogRef };

    function onKey(event) {
      const top = dialogStack[dialogStack.length - 1];
      if (top !== entry) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        requestClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusablesIn(node);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    dialogStack.push(entry);
    document.addEventListener("keydown", onKey, true);
    return () => {
      const index = dialogStack.indexOf(entry);
      if (index >= 0) dialogStack.splice(index, 1);
      document.removeEventListener("keydown", onKey, true);
      unlock();
      if (previousFocus.current?.focus) previousFocus.current.focus();
    };
  }, []);

  if (typeof document === "undefined") return null;

  const actions = hideActions
    ? footer
    : (
      <>
        <button type="button" className="btn btn-outline" onClick={requestClose} disabled={busy}>
          Cancel
        </button>
        {onConfirm ? (
          <button type="button" className={danger ? "btn btn-danger" : "btn btn-navy"} onClick={onConfirm} disabled={busy}>
            {busy ? "Working…" : confirmLabel}
          </button>
        ) : null}
      </>
    );

  return createPortal(
    <div className="dialog-backdrop offset-sidebar" onClick={requestClose}>
      <div
        className={`dialog ${wide ? "wide" : ""} ${compact ? "compact" : ""}`.trim()}
        role={danger ? "alertdialog" : "dialog"}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        ref={dialogRef}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialog-head">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="dialog-close" onClick={requestClose} disabled={busy} aria-label="Close">
            <XIcon size={18} />
          </button>
        </div>
        {description || children ? (
          <div className="dialog-body">
            {description ? <p className="dialog-lead" id={descId}>{description}</p> : null}
            {children}
          </div>
        ) : null}
        {actions ? <div className="dialog-actions">{actions}</div> : null}
      </div>
    </div>,
    document.body
  );
}

let scrollLockCount = 0;
let scrollLockState = null;
const dialogStack = [];

function lockPageScroll() {
  const html = document.documentElement;
  if (scrollLockCount === 0) {
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;
    function allowScroll(target) {
      return Boolean(target?.closest?.(".dialog, .review-sheet, .drawer"));
    }
    function onWheel(event) {
      if (allowScroll(event.target)) return;
      event.preventDefault();
    }
    function onTouchMove(event) {
      if (allowScroll(event.target)) return;
      event.preventDefault();
    }
    function onScroll() {
      if (window.scrollX !== scrollX || window.scrollY !== scrollY) {
        window.scrollTo(scrollX, scrollY);
      }
    }
    function onKey(event) {
      const keys = ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "];
      if (!keys.includes(event.key) || allowScroll(event.target)) return;
      event.preventDefault();
    }
    scrollLockState = { onWheel, onTouchMove, onScroll, onKey, scrollX, scrollY };
    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("scroll", onScroll);
    window.addEventListener("keydown", onKey, true);
    html.classList.add("modal-open");
  }
  scrollLockCount += 1;
  return () => {
    scrollLockCount = Math.max(0, scrollLockCount - 1);
    if (scrollLockCount > 0 || !scrollLockState) return;
    window.removeEventListener("wheel", scrollLockState.onWheel);
    window.removeEventListener("touchmove", scrollLockState.onTouchMove);
    window.removeEventListener("scroll", scrollLockState.onScroll);
    window.removeEventListener("keydown", scrollLockState.onKey, true);
    html.classList.remove("modal-open");
    window.scrollTo(scrollLockState.scrollX, scrollLockState.scrollY);
    scrollLockState = null;
  };
}

function focusablesIn(node) {
  if (!node) return [];
  return [...node.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")].filter(
    (el) => !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true"
  );
}

export function ReviewSheet({
  title,
  subtitle,
  meta,
  children,
  footer,
  onClose,
  onOpenTab,
  wide,
  offsetSidebar = true,
}) {
  const sheetRef = useRef(null);
  const previousFocus = useRef(null);
  const titleId = useId();

  useEffect(() => {
    previousFocus.current = document.activeElement;
    const node = sheetRef.current;
    const unlock = lockPageScroll();
    focusablesIn(node)[0]?.focus();

    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusablesIn(node);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      unlock();
      if (previousFocus.current?.focus) previousFocus.current.focus();
    };
  }, [onClose]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className={`review-sheet-backdrop ${offsetSidebar ? "offset-sidebar" : ""}`} onClick={onClose}>
      <div
        className={`review-sheet ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={sheetRef}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="review-sheet-head">
          <div className="review-sheet-copy">
            <h2 id={titleId}>{title}</h2>
            {subtitle ? <p className="review-sheet-subtitle">{subtitle}</p> : null}
            {meta ? <div className="review-sheet-meta">{meta}</div> : null}
          </div>
          <div className="review-sheet-head-actions">
            {onOpenTab ? (
              <button className="btn btn-outline" type="button" onClick={onOpenTab}>
                <span className="label-full">Open in New Tab</span>
                <span className="label-short">New Tab</span>
                <ExternalLinkIcon size={16} />
              </button>
            ) : null}
            <button className="btn btn-outline" type="button" onClick={onClose} aria-label="Close">
              Close
              <XIcon size={16} />
            </button>
          </div>
        </header>
        <div className="review-sheet-body">{children}</div>
        {footer ? <div className="review-sheet-foot">{footer}</div> : null}
      </div>
    </div>,
    document.body
  );
}

export function Drawer({ title, description, actions, children, onClose, labelledBy }) {
  const drawerRef = useRef(null);
  const previousFocus = useRef(null);
  const titleId = useId();

  useEffect(() => {
    previousFocus.current = document.activeElement;
    const node = drawerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    focusablesIn(node)[0]?.focus();

    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusablesIn(node);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      if (previousFocus.current?.focus) previousFocus.current.focus();
    };
  }, [onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy || titleId}
        ref={drawerRef}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-head">
          <div>
            <p className="drawer-kicker">Review</p>
            <h2 id={labelledBy || titleId}>{title}</h2>
            {description ? <p className="lead">{description}</p> : null}
          </div>
          {actions ? <div className="drawer-head-actions">{actions}</div> : (
            <button className="btn btn-outline btn-sm" type="button" onClick={onClose}>Close</button>
          )}
        </header>
        <div className="drawer-body">{children}</div>
      </div>
    </div>
  );
}

export function ExpandDetails({
  summary,
  hint,
  children,
  className = "",
  showLabel = "Show details",
  hideLabel = "Hide details",
  defaultOpen = false,
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details className={`expand-block ${className}`} open={open}>
      <summary
        onClick={(event) => {
          event.preventDefault();
          setOpen((value) => !value);
        }}
      >
        <span className="expand-summary">
          <span>{summary}</span>
          {hint ? <span className="expand-hint">{hint}</span> : null}
        </span>
        <span className="expand-action">{open ? hideLabel : showLabel}</span>
      </summary>
      {children}
    </details>
  );
}

export function SortButton({ column, sort, onSort, children }) {
  const active = sort.key === column;
  return (
    <button
      type="button"
      className={`th-sort ${active ? "on" : ""}`}
      onClick={() => onSort(column)}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
    >
      {children}
      <span aria-hidden="true">{active ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}</span>
    </button>
  );
}

export function sortBy(rows, sort, getters) {
  const getter = getters[sort.key];
  if (!getter) return rows;
  const copy = [...rows];
  copy.sort((a, b) => {
    const left = getter(a);
    const right = getter(b);
    if (left < right) return sort.dir === "asc" ? -1 : 1;
    if (left > right) return sort.dir === "asc" ? 1 : -1;
    return 0;
  });
  return copy;
}

export function toggleSort(sort, key) {
  if (sort.key === key) return { key, dir: sort.dir === "asc" ? "desc" : "asc" };
  return { key, dir: "asc" };
}

const TOAST_ICONS = {
  success: CheckCircleIcon,
  error: AlertTriangleIcon,
  warning: AlertTriangleIcon,
  info: InfoIcon,
};

export function ToastHost() {
  const [toasts, setToasts] = useState([]);
  const [leaving, setLeaving] = useState({});

  useEffect(() => subscribeToasts(setToasts), []);

  useEffect(() => {
    const timers = toasts.map((item) => {
      if (item.sticky || leaving[item.id]) return null;
      const wait = Math.max(600, toastDuration(item.type) - (Date.now() - item.createdAt));
      return window.setTimeout(() => beginLeave(item.id), wait);
    });
    return () => timers.forEach((timer) => timer && window.clearTimeout(timer));
  }, [toasts, leaving]);

  function beginLeave(id) {
    setLeaving((prev) => (prev[id] ? prev : { ...prev, [id]: true }));
    window.setTimeout(() => {
      dismissToast(id);
      setLeaving((prev) => {
        if (!prev[id]) return prev;
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }, 180);
  }

  return (
    <div className="toast-region cs-toast-region" aria-live="polite" aria-relevant="additions text">
      {toasts.map((item) => {
        const Icon = TOAST_ICONS[item.type] || InfoIcon;
        const urgent = item.type === "error" || item.type === "warning";
        return (
          <div
            key={item.id}
            className={`toast toast-${item.type} ${leaving[item.id] ? "is-leaving" : ""}`}
            role={urgent ? "alert" : "status"}
          >
            <span className="toast-icon" aria-hidden="true">
              <Icon size={18} />
            </span>
            <div className="toast-copy">
              {item.title ? <strong>{item.title}</strong> : null}
              <p>{item.message}</p>
            </div>
            <button type="button" className="toast-close" onClick={() => beginLeave(item.id)} aria-label="Dismiss notification">
              <XIcon size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
