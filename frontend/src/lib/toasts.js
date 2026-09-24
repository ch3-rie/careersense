const MAX_TOASTS = 4;
const DURATIONS = {
  success: 4500,
  info: 5500,
  warning: 8000,
  error: 10000,
};

let toasts = [];
let seq = 0;
const listeners = new Set();

function emit() {
  const snapshot = toasts.slice();
  listeners.forEach((listener) => listener(snapshot));
}

export function showToast(type, message, options = {}) {
  const text = String(message || "").trim();
  if (!text) return "";
  const kind = ["success", "error", "warning", "info"].includes(type) ? type : "info";
  const title = String(options.title || "").trim();
  const existing = toasts.find((item) => item.type === kind && item.message === text && item.title === title);
  if (existing) {
    existing.createdAt = Date.now();
    existing.sticky = Boolean(options.sticky);
    emit();
    return existing.id;
  }
  const toast = {
    id: `toast-${++seq}`,
    type: kind,
    title,
    message: text,
    sticky: Boolean(options.sticky),
    createdAt: Date.now(),
  };
  toasts = [...toasts, toast].slice(-MAX_TOASTS);
  emit();
  return toast.id;
}

export function dismissToast(id) {
  const next = toasts.filter((item) => item.id !== id);
  if (next.length === toasts.length) return;
  toasts = next;
  emit();
}

export function toastDuration(type) {
  return DURATIONS[type] || DURATIONS.info;
}

export function subscribeToasts(listener) {
  listeners.add(listener);
  listener(toasts.slice());
  return () => listeners.delete(listener);
}
