const TECHNICAL = /traceback|exception|axioserror|sqlalchemy|syntaxerror|typeerror|referenceerror|<!doctype|<\s*html|\bstack trace\b|internal server error/i;

export function usableDetail(detail) {
  const raw = String(detail || "").replace(/\s+/g, " ").trim();
  if (!raw || raw === "Request failed." || raw === "Download failed.") return "";
  if (raw.length > 280 || TECHNICAL.test(raw)) return "";
  return raw;
}

export function networkErrorNotice() {
  return {
    type: "error",
    title: "Connection problem",
    message: "Could not reach CareerSense. Check your connection and try again.",
  };
}

export function messageForStatus(status, detail) {
  const clean = usableDetail(detail);
  if (status === 400) {
    return {
      type: "error",
      title: "Please review your information",
      message: clean || "Please review your information and try again.",
    };
  }
  if (status === 401) {
    return {
      type: "error",
      title: "Session expired",
      message: "Your session has expired. Please sign in again.",
    };
  }
  if (status === 403) {
    return {
      type: "error",
      title: "Not allowed",
      message: clean || "You don't have permission to perform this action.",
    };
  }
  if (status === 404) {
    return {
      type: "error",
      title: "Not found",
      message: clean || "The requested information could not be found.",
    };
  }
  if (status === 409) {
    return {
      type: "warning",
      title: "Please review your details",
      message: clean || "This information conflicts with an existing record. Please review your details.",
    };
  }
  if (status === 422) {
    return {
      type: "warning",
      title: "Please review your information",
      message: clean || "Please correct the highlighted fields before continuing.",
    };
  }
  if (status === 429) {
    return {
      type: "warning",
      title: "Please wait",
      message: "Too many attempts. Please wait a moment and try again.",
    };
  }
  if (status >= 500) {
    return {
      type: "error",
      title: "Something went wrong",
      message: "Something went wrong on our side. Please try again.",
    };
  }
  return {
    type: "error",
    title: "Something went wrong",
    message: clean || "We couldn't complete that request. Please try again.",
  };
}
