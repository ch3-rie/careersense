import { messageForStatus, networkErrorNotice, usableDetail } from "./apiErrors";
import { showToast } from "./toasts";

const API_BASE = import.meta.env.VITE_API_URL || "";

const PUBLIC_AUTH_PATHS = [
  "/api/auth/login",
  "/api/auth/register",
  "/api/auth/forgot-password",
  "/api/auth/reset-password",
];

function getToken() {
  return localStorage.getItem("cs_token") || "";
}

export function setSession(token, user) {
  if (token) localStorage.setItem("cs_token", token);
  if (user) localStorage.setItem("cs_user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("cs_token");
  localStorage.removeItem("cs_user");
}

export function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("cs_user") || "null");
  } catch {
    return null;
  }
}

let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

function isPublicAuthPath(path) {
  const clean = String(path || "").split("?")[0];
  return (
    clean === "/api/auth/login" ||
    clean === "/api/auth/register" ||
    clean === "/api/auth/register/complete" ||
    clean.startsWith("/api/auth/forgot-password") ||
    clean === "/api/auth/reset-password"
  );
}

function friendlyMessage(data, fallback) {
  const detail = data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || item).join(" ");
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && detail.message) return detail.message;
  if (data?.message) return data.message;
  return fallback;
}

function handleUnauthorized(path) {
  if (isPublicAuthPath(path)) return;
  clearSession();
  if (typeof unauthorizedHandler === "function") unauthorizedHandler();
}

function shouldNotify(path, { method, blob, toast }) {
  if (toast != null) return Boolean(toast);
  if (isPublicAuthPath(path)) return false;
  return method !== "GET" || Boolean(blob);
}

function throwRequestError(path, status, detail, payload, options) {
  const publicAuth = isPublicAuthPath(path);
  const notice = status === 401 && publicAuth
    ? { type: "error", title: "", message: usableDetail(detail) || "We couldn't sign you in. Check your email and password, then try again." }
    : status
      ? messageForStatus(status, detail)
      : networkErrorNotice();
  if (shouldNotify(path, options)) showToast(notice.type, notice.message, { title: notice.title });
  const error = new Error(notice.message);
  error.status = status || 0;
  error.title = notice.title || "";
  error.payload = payload;
  throw error;
}

export async function api(path, { method = "GET", body, form, headers, blob, toast } = {}) {
  const opts = {
    method,
    headers: { ...(headers || {}) },
  };
  const token = getToken();
  if (token) opts.headers.Authorization = `Bearer ${token}`;
  if (form) {
    opts.body = form;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const notifyOptions = { method: method.toUpperCase(), blob, toast };
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, opts);
  } catch {
    throwRequestError(path, 0, "", null, notifyOptions);
  }
  const contentType = res.headers.get("content-type") || "";
  if (res.status === 401) {
    handleUnauthorized(path);
  }
  if (
    blob ||
    contentType.includes("text/csv") ||
    contentType.includes("octet-stream") ||
    contentType.includes("application/pdf") ||
    contentType.includes("wordprocessingml") ||
    contentType.includes("text/plain")
  ) {
    if (!res.ok) throwRequestError(path, res.status, "", null, notifyOptions);
    return res.blob();
  }
  const data = contentType.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const payload = typeof data === "object" ? data : { detail: data };
    throwRequestError(path, res.status, friendlyMessage(payload, ""), payload, notifyOptions);
  }
  return data;
}

export async function downloadAuthorized(path, filename) {
  const blob = await api(path, { blob: true });
  if (!(blob instanceof Blob)) {
    throw new Error("Download failed.");
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  link.click();
  URL.revokeObjectURL(url);
}
