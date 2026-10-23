import { useEffect, useId, useRef, useState } from "react";
import { CheckIcon, FileIcon, UploadIcon } from "./icons";
import { fileKindLabel, formatFileSize } from "../lib/userMessages";

function assignFiles(input, file) {
  if (!input) return;
  const transfer = new DataTransfer();
  if (file) transfer.items.add(file);
  input.files = transfer.files;
}

export function FileDrop({
  name,
  accept,
  file,
  onChange,
  validate,
  currentName = "",
  status = "idle",
  error = "",
  disabled = false,
  required = false,
  handoff = false,
  compact = false,
  className = "",
  label = "",
  formats = "",
  maxSize = "",
  description = "",
  readyLabel = "Ready to upload",
  prompt = "",
  browseLabel = "",
  labelHidden = false,
  mark = "upload",
}) {
  const autoId = useId();
  const inputId = `${autoId}-file`;
  const hintId = `${autoId}-hint`;
  const errorId = `${autoId}-error`;
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [internal, setInternal] = useState(null);
  const [localError, setLocalError] = useState("");
  const controlled = file !== undefined;
  const selected = controlled ? file : internal;

  useEffect(() => {
    if (controlled && !file && inputRef.current) inputRef.current.value = "";
  }, [controlled, file]);
  const problem = error || localError;
  const showingCurrent = !selected && Boolean(currentName) && !handoff;
  const limits = [formats, maxSize].filter(Boolean).join(" · ");

  function emit(next, message) {
    if (!controlled) setInternal(next);
    setLocalError(message || "");
    onChange?.(next, message || "");
  }

  function take(next) {
    if (disabled) return;
    if (!next) {
      assignFiles(inputRef.current, null);
      emit(null, "");
      return;
    }
    const message = validate?.(next) || "";
    if (message) {
      assignFiles(inputRef.current, null);
      emit(null, message);
      return;
    }
    if (handoff) {
      assignFiles(inputRef.current, null);
      if (inputRef.current) inputRef.current.value = "";
      setLocalError("");
      onChange?.(next, "");
      return;
    }
    assignFiles(inputRef.current, next);
    emit(next, "");
  }

  function browse() {
    if (!disabled) inputRef.current?.click();
  }

  const statusText = status === "uploading"
    ? "Uploading…"
    : status === "success"
      ? "Uploaded"
      : status === "error"
        ? "Upload failed"
        : selected
          ? readyLabel
          : showingCurrent
            ? "Current file"
            : "";

  const describedBy = [hintId, problem ? errorId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className={`file-drop${compact ? " is-compact" : ""}${dragOver ? " is-over" : ""}${(status === "error" || (problem && !showingCurrent)) ? " has-error" : ""}${status === "success" ? " is-success" : ""}${status === "uploading" ? " is-uploading" : ""}${className ? ` ${className}` : ""}`}>
      {label ? <p className={`file-drop-label${labelHidden ? " sr-only" : ""}`} id={`${autoId}-label`}>{label}{required ? <span className="req" aria-hidden="true">*</span> : null}</p> : null}
      {selected || showingCurrent ? (
        <div
          className="file-drop-selected"
          role="status"
          aria-live="polite"
          onDragOver={(event) => {
            event.preventDefault();
            if (!disabled && status !== "uploading") setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            take(event.dataTransfer.files?.[0] || null);
          }}
        >
          <span className={`file-drop-mark${status === "success" ? " is-success" : ""}`} aria-hidden="true">
            {status === "uploading" ? <span className="btn-spinner" /> : status === "success" ? <CheckIcon size={18} /> : mark === "file" ? <FileIcon size={18} /> : <UploadIcon size={18} />}
          </span>
          <div className="file-drop-copy">
            <strong>{selected ? selected.name : currentName}</strong>
            <p className="muted">
              {selected
                ? `${fileKindLabel(selected.name)} · ${formatFileSize(selected.size)}`
                : `${fileKindLabel(currentName) === "File" ? "On file" : `${fileKindLabel(currentName)} · On file`}`}
            </p>
            {statusText ? <p className={`file-drop-status is-${status === "idle" ? "ready" : status}`}>{statusText}</p> : null}
          </div>
          <div className="file-drop-actions">
            <button type="button" className="btn btn-outline btn-sm" onClick={browse} disabled={disabled || status === "uploading"}>
              {selected || showingCurrent ? "Replace" : "Browse"}
            </button>
            {selected ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => take(null)} disabled={disabled || status === "uploading"}>
                Remove
              </button>
            ) : null}
          </div>
        </div>
      ) : browseLabel ? (
        <div
          className="file-drop-zone"
          onDragOver={(event) => {
            event.preventDefault();
            if (!disabled) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            take(event.dataTransfer.files?.[0] || null);
          }}
        >
          <span className="file-drop-icon" aria-hidden="true"><UploadIcon size={22} /></span>
          <strong>{prompt || "Drag and drop your file here"}</strong>
          <button type="button" className="btn btn-navy btn-sm" onClick={browse} disabled={disabled}>
            {browseLabel}
          </button>
          {limits ? <span className="muted">{limits}</span> : null}
          {description ? <p className="file-drop-note">{description}</p> : null}
        </div>
      ) : (
        <label
          htmlFor={inputId}
          className="file-drop-zone"
          onDragOver={(event) => {
            event.preventDefault();
            if (!disabled) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            take(event.dataTransfer.files?.[0] || null);
          }}
        >
          <span className="file-drop-icon" aria-hidden="true"><UploadIcon size={22} /></span>
          <strong>Drag and drop your file here or <span className="file-drop-browse">browse</span></strong>
          {limits ? <span className="muted">{limits}</span> : null}
          {description ? <p className="file-drop-note">{description}</p> : null}
        </label>
      )}
      <input
        ref={inputRef}
        id={inputId}
        className="sr-only"
        type="file"
        name={name || undefined}
        accept={accept}
        disabled={disabled || status === "uploading"}
        aria-label={label || "Upload file"}
        aria-required={required || undefined}
        aria-invalid={problem ? true : undefined}
        aria-describedby={describedBy}
        onChange={(event) => take(event.target.files?.[0] || null)}
      />
      <span className="sr-only" id={hintId}>{limits || "Choose a file"}</span>
      {problem ? <p className="field-error" id={errorId} role="alert">{problem}</p> : null}
    </div>
  );
}
