export function registrationHasProgress(step, form, { submitted = false } = {}) {
  if (submitted || Number(step) >= 3) return false;
  if (Number(step) >= 2) return true;
  const draft = form || {};
  return Boolean(
    String(draft.email || "").trim()
    || String(draft.password || "")
    || String(draft.confirm_password || "")
    || draft.resume
    || draft.privacy_consent
  );
}
