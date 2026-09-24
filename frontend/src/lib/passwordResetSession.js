const KEY = "cs_password_reset";

export function readResetSession() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || "null") || {};
  } catch {
    return {};
  }
}

export function writeResetSession(patch) {
  const next = { ...readResetSession(), ...patch };
  sessionStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export function clearResetSession() {
  sessionStorage.removeItem(KEY);
}

export function applyPinResponse(email, data) {
  const now = Date.now();
  const expiresIn = Number(data?.expires_in) || 600;
  const resendAfter = Number(data?.resend_after) || 0;
  return writeResetSession({
    email,
    maskedEmail: data?.masked_email || "",
    expiresAt: now + expiresIn * 1000,
    resendAt: now + Math.max(0, resendAfter) * 1000,
    resetToken: "",
  });
}

export function formatCountdown(ms) {
  const total = Math.max(0, Math.ceil(Number(ms) / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
