const MAX_RESUME_MB = 10;
export const MAX_RESUME_BYTES = MAX_RESUME_MB * 1024 * 1024;
export const RESUME_ACCEPT = ".pdf,.docx,.txt";

export function formatFileSize(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(size < 10 * 1024 ? 1 : 0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function fileKindLabel(name = "") {
  const ext = String(name).split(".").pop()?.toLowerCase();
  const labels = {
    pdf: "PDF",
    docx: "DOCX",
    txt: "TXT",
    jpg: "JPG",
    jpeg: "JPG",
    png: "PNG",
    webp: "WebP",
    xlsx: "Excel",
    xlsm: "Excel",
  };
  return labels[ext] || "File";
}

export function resumeFileError(file) {
  if (!file) return "";
  const name = String(file.name || "").toLowerCase();
  if (!/\.(pdf|docx|txt)$/.test(name)) return "Please upload a PDF, DOCX, or TXT resume.";
  if (!file.size) return "The uploaded file is empty.";
  if (file.size > MAX_RESUME_BYTES) return "Resume must be 10 MB or smaller.";
  return "";
}

export const CERTIFICATE_ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp";
const CERTIFICATE_MAX_BYTES = MAX_RESUME_BYTES;

export function certificateFileError(file) {
  if (!file) return "";
  const name = String(file.name || "").toLowerCase();
  if (!/\.(pdf|png|jpe?g|webp)$/.test(name)) return "Upload a PDF, JPG, PNG, or WebP certificate or badge.";
  if (!file.size) return "The uploaded file is empty.";
  if (file.size > CERTIFICATE_MAX_BYTES) return "Certificate must be 10 MB or smaller.";
  return "";
}

export function passwordChecks(value) {
  const text = String(value || "");
  return {
    length: text.length >= 8,
    letter: /[A-Za-z]/.test(text),
    number: /\d/.test(text),
  };
}

export function passwordIsValid(value) {
  const checks = passwordChecks(value);
  return checks.length && checks.letter && checks.number;
}

export function friendlyError(error, fallback = "Something went wrong. Please try again.") {
  const raw = String(error?.message || error || "").trim();
  if (!raw) return fallback;
  if (/<\s*html|<!doctype/i.test(raw)) return fallback;
  const lower = raw.toLowerCase();
  if (/unprocessable entity|\b422\b|validationerror|valueerror/.test(lower)) {
    return "Please check the highlighted fields and try again.";
  }
  if (/\b(jwt|invalid token|not enough segments|token expired)\b/.test(lower)) {
    return "Your review session expired. Please upload your resume again.";
  }
  if (/parserexception|traceback|extract_resume/.test(lower)) {
    return "We couldn't read this resume. You can still continue and enter your tracer information manually.";
  }
  if (/internal server error|\b500\b/.test(lower)) {
    return "CareerSense ran into a problem. Please try again in a moment.";
  }
  if (raw === "Request failed." || raw === "Download failed.") return fallback;
  return raw;
}

export function extractionState(result) {
  const source = String(result?.parser_source || "");
  const parsed = result?.parsed_resume || {};
  if (source === "failed") return "failed";
  if (source === "empty") return "empty";
  const hasName = Boolean(parsed.first_name || parsed.last_name);
  const hasJobs = Array.isArray(parsed.experiences) && parsed.experiences.length > 0;
  const hasEdu = Boolean(parsed.degree || parsed.year_graduated);
  const hasSkills = Array.isArray(parsed.skills) && parsed.skills.length > 0;
  if (!hasName && !hasJobs && !hasEdu && !hasSkills) return "empty";
  return "ok";
}
