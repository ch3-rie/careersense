import { useEffect, useId, useRef, useState } from "react";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CheckIcon,
  FileTextIcon,
  InfoIcon,
  UploadIcon,
} from "./icons";
import {
  MAX_RESUME_BYTES,
  RESUME_ACCEPT,
  fileKindLabel,
  formatFileSize,
  passwordChecks,
} from "../lib/userMessages";

export function AuthPageHeader({ kicker = "CareerSense", title, lead, badge }) {
  return (
    <header className="auth-card-head">
      {kicker ? <p className="kicker">{kicker}</p> : null}
      <div className="auth-card-title-row">
        <h1 className="serif">{title}</h1>
        {badge ? <div className="auth-card-badge">{badge}</div> : null}
      </div>
      {lead ? <p className="lead">{lead}</p> : null}
    </header>
  );
}

const REGISTER_STEPS = [
  { n: 1, label: "Account & resume", short: "Account" },
  { n: 2, label: "Review tracer survey", short: "Review" },
  { n: 3, label: "Pending approval", short: "Pending" },
];

const FORGOT_STEPS = [
  { n: 1, label: "Email", short: "Email" },
  { n: 2, label: "Verify PIN", short: "PIN" },
  { n: 3, label: "New password", short: "Password" },
];

export function AuthStepper({ step, steps, label }) {
  return (
    <ol className="reg-steps" aria-label={label}>
      {steps.map((item) => {
        const status = step === item.n ? "current" : step > item.n ? "done" : "upcoming";
        return (
          <li key={item.n} className={`reg-step ${status}`} aria-current={status === "current" ? "step" : undefined}>
            <span className="reg-step-marker" aria-hidden="true">
              {status === "done" ? <CheckIcon size={14} /> : item.n}
            </span>
            <span className="reg-step-label">
              <span className="label-full">{item.label}</span>
              <span className="label-short">{item.short}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function RegisterStepper({ step }) {
  return <AuthStepper step={step} steps={REGISTER_STEPS} label="Registration progress" />;
}

export function ForgotStepper({ step }) {
  return <AuthStepper step={step} steps={FORGOT_STEPS} label="Password reset progress" />;
}

export function FormBlock({ title, children }) {
  return (
    <section className="form-block">
      {title ? <h2 className="form-block-title">{title}</h2> : null}
      {children}
    </section>
  );
}

export function PasswordHints({ value }) {
  const checks = passwordChecks(value);
  const items = [
    ["length", "At least 8 characters", checks.length],
    ["letter", "Contains a letter", checks.letter],
    ["number", "Contains a number", checks.number],
  ];
  return (
    <ul className="pw-hints" aria-live="polite">
      {items.map(([id, label, ok]) => (
        <li key={id} className={ok ? "ok" : ""}>
          <span aria-hidden="true">{ok ? "✓" : "○"}</span>
          {label}
        </li>
      ))}
    </ul>
  );
}

export function PasswordMatch({ password, confirm }) {
  if (!confirm) return null;
  const ok = password === confirm;
  return (
    <p className={`pw-match ${ok ? "ok" : "bad"}`} role="status">
      {ok ? "Passwords match." : "Passwords do not match yet."}
    </p>
  );
}

export function PinInput({ value, onChange, disabled, error, labelledBy }) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 6).split("");
  while (digits.length < 6) digits.push("");
  const refs = useRef([]);

  function focusAt(index) {
    refs.current[Math.max(0, Math.min(5, index))]?.focus();
  }

  function emit(nextDigits) {
    onChange(nextDigits.join("").slice(0, 6));
  }

  function onKeyDown(index, event) {
    if (event.key === "Backspace") {
      event.preventDefault();
      const next = [...digits];
      if (next[index]) {
        next[index] = "";
        emit(next);
      } else {
        next[Math.max(0, index - 1)] = "";
        emit(next);
        focusAt(index - 1);
      }
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusAt(index - 1);
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      focusAt(index + 1);
    }
  }

  function onPaste(event) {
    event.preventDefault();
    const pasted = String(event.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;
    const next = pasted.split("");
    while (next.length < 6) next.push("");
    emit(next);
    focusAt(Math.min(5, pasted.length));
  }

  function onInput(index, event) {
    const raw = event.target.value.replace(/\D/g, "");
    if (!raw) {
      const next = [...digits];
      next[index] = "";
      emit(next);
      return;
    }
    const next = [...digits];
    if (raw.length > 1) {
      raw.slice(0, 6).split("").forEach((digit, offset) => {
        next[offset] = digit;
      });
      emit(next);
      focusAt(Math.min(5, raw.length));
      return;
    }
    next[index] = raw.slice(-1);
    emit(next);
    if (index < 5) focusAt(index + 1);
  }

  return (
    <div className={`pin-inputs${error ? " has-error" : ""}`} role="group" aria-labelledby={labelledBy} onPaste={onPaste}>
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(node) => { refs.current[index] = node; }}
          className="pin-digit"
          type="text"
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          pattern="[0-9]*"
          maxLength={1}
          value={digit}
          disabled={disabled}
          aria-label={`Digit ${index + 1} of 6`}
          aria-invalid={error ? true : undefined}
          onChange={(event) => onInput(index, event)}
          onKeyDown={(event) => onKeyDown(index, event)}
          onFocus={(event) => event.target.select()}
          autoFocus={index === 0}
        />
      ))}
    </div>
  );
}

export function FileUploadField({
  file,
  onChange,
  error,
  disabled,
  label = "Upload your resume",
  hint = "PDF, DOCX, or TXT · Maximum 10 MB",
  description = "This file only suggests survey answers. You can correct them before you submit.",
}) {
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  function applyFile(next, { allowEmpty = false } = {}) {
    if (!next) {
      if (allowEmpty) onChange(null);
      return;
    }
    const name = String(next.name || "").toLowerCase();
    if (!/\.(pdf|docx|txt)$/.test(name)) {
      onChange(null, "Please upload a PDF, DOCX, or TXT resume.");
      return;
    }
    if (next.size > MAX_RESUME_BYTES) {
      onChange(null, "Resume must be 10 MB or smaller.");
      return;
    }
    onChange(next, "");
  }

  function clearFile(event) {
    event.preventDefault();
    event.stopPropagation();
    if (inputRef.current) inputRef.current.value = "";
    onChange(null, "");
  }

  if (file) {
    return (
      <div className={`file-selected ${error ? "has-error" : ""}`}>
        <span className="file-selected-icon" aria-hidden="true">
          <CheckIcon size={18} />
        </span>
        <div className="file-selected-copy">
          <strong id={inputId}>{file.name}</strong>
          <p className="muted" id={hintId}>
            {fileKindLabel(file.name)} · {formatFileSize(file.size)}
          </p>
        </div>
        <div className="file-selected-actions">
          <button type="button" className="btn btn-outline btn-sm" disabled={disabled} onClick={() => inputRef.current?.click()}>
            Change file
          </button>
          <button type="button" className="btn btn-outline btn-sm" disabled={disabled} onClick={clearFile}>
            Remove
          </button>
        </div>
        <input
          ref={inputRef}
          id={`${inputId}-input`}
          className="sr-only"
          type="file"
          accept={RESUME_ACCEPT}
          aria-label="Replace resume file"
          disabled={disabled}
          onChange={(event) => {
            const next = event.target.files?.[0];
            if (next) applyFile(next);
          }}
        />
        {error ? <span className="field-error" id={errorId}>{error}</span> : null}
      </div>
    );
  }

  return (
    <div className={`field file-upload-field ${error ? "has-error" : ""}`}>
      <label
        htmlFor={inputId}
        className={`dropzone file-dropzone ${dragOver ? "is-over" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          applyFile(event.dataTransfer.files?.[0] || null, { allowEmpty: true });
        }}
      >
        <UploadIcon size={28} />
        <strong>{label}</strong>
        <span className="muted" id={hintId}>{hint}</span>
        <p className="file-dropzone-copy">{description}</p>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={RESUME_ACCEPT}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={[hintId, error ? errorId : null].filter(Boolean).join(" ") || undefined}
          onChange={(event) => applyFile(event.target.files?.[0] || null, { allowEmpty: true })}
        />
      </label>
      {error ? <span className="field-error" id={errorId}>{error}</span> : null}
    </div>
  );
}

const PARSE_STAGES = [
  "Reading your resume",
  "Extracting education, work history, and skills",
  "Preparing your tracer survey",
];

export function ParseProgress({ startedAt }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 800);
    return () => window.clearInterval(timer);
  }, []);

  const elapsed = Math.max(0, now - (startedAt || now));
  const stage = Math.min(PARSE_STAGES.length - 1, Math.floor(elapsed / 2400));
  const slow = elapsed > 8000;

  return (
    <div className="parse-progress" role="status" aria-live="polite">
      <div className="parse-progress-head">
        <span className="btn-spinner" aria-hidden="true" />
        <div>
          <strong>Reading resume…</strong>
          <p className="muted">Please wait. This can take a few seconds.</p>
        </div>
      </div>
      <ol className="parse-stages">
        {PARSE_STAGES.map((label, index) => (
          <li key={label} className={index === stage ? "on" : index < stage ? "seen" : ""}>
            {label}
          </li>
        ))}
      </ol>
      {slow ? <p className="muted">This is taking a little longer than usual. Please keep this page open.</p> : null}
    </div>
  );
}

export function RegistryMatch({ match }) {
  if (match?.matched) {
    return (
      <div className="status-callout ok" role="status">
        <span className="status-callout-icon" aria-hidden="true">
          <CheckCircleIcon size={20} />
        </span>
        <div>
          <strong>AUF graduate record matched</strong>
          <p>
            {[
              match.student_id && `Student ID: ${match.student_id}`,
              match.degree,
              match.year_graduated,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="status-callout warn" role="status">
      <span className="status-callout-icon" aria-hidden="true">
        <AlertTriangleIcon size={20} />
      </span>
      <div>
        <strong>No AUF record matched yet</strong>
        <p>You can still continue. OAAPS may verify your identity using your name or student ID.</p>
      </div>
    </div>
  );
}

export function StatusTimeline({ items }) {
  return (
    <ol className="status-timeline">
      {items.map((item) => (
        <li key={item.label} className={item.status}>
          <span className="status-marker" aria-hidden="true">
            {item.status === "done" ? <CheckIcon size={14} /> : <span className="status-dot" />}
          </span>
          <span>{item.label}</span>
        </li>
      ))}
    </ol>
  );
}

export function AlignmentHint({ alignment, occupation }) {
  const hintJob = String(alignment?.job_title || "").trim().toLowerCase();
  const liveJob = String(occupation || "").trim().toLowerCase();
  const stale = Boolean(hintJob && liveJob && hintJob !== liveJob);
  const status = stale ? "" : String(alignment?.status || "").toLowerCase();
  let title = "Unable to determine";
  let tone = "unknown";
  let Icon = InfoIcon;
  if (status === "aligned") {
    title = "Aligned with your degree";
    tone = "ok";
    Icon = CheckCircleIcon;
  } else if (status === "misaligned") {
    title = "Review recommended";
    tone = "warn";
    Icon = AlertTriangleIcon;
  }
  return (
    <aside className={`align-hint ${tone}`}>
      <p className="align-hint-kicker">Career alignment</p>
      <p className="align-hint-title">
        <Icon size={16} />
        <span>{title}</span>
      </p>
      <p>
        Based on your current occupation{occupation ? ` (${occupation})` : ""}. Confirm whether this work relates to your bachelor's degree.
      </p>
    </aside>
  );
}

export function SubmitConfirm({
  title = "Ready to submit?",
  children = "Please make sure your information is correct. The tracer information you submit will become your official tracer record and will be reviewed by OAAPS.",
  confirmLabel = "Submit tracer information",
  cancelLabel = "Continue reviewing",
  busy,
  onCancel,
}) {
  return (
    <div className="submit-confirm" role="region" aria-labelledby="submit-confirm-title">
      <h3 id="submit-confirm-title">{title}</h3>
      <p className="muted">{children}</p>
      <div className="submit-confirm-actions">
        <button type="button" className="btn btn-outline" disabled={busy} onClick={onCancel}>
          {cancelLabel}
        </button>
        <button type="submit" className="btn btn-navy" disabled={busy}>
          {busy ? "Submitting…" : confirmLabel}
        </button>
      </div>
    </div>
  );
}

export function ExtractionEmpty({ failed }) {
  if (failed) {
    return (
      <div className="extract-empty">
        <FileTextIcon size={22} />
        <div>
          <strong>We couldn't read this resume</strong>
          <p>Your registration can continue. Please review and complete the survey manually.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="extract-empty">
      <InfoIcon size={22} />
      <div>
        <strong>No information was extracted</strong>
        <p>You can enter your tracer information manually.</p>
      </div>
    </div>
  );
}
