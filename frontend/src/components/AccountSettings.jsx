import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PasswordHints, PasswordMatch } from "./AuthFlow";
import { SourceBadge } from "./AlumniChrome";
import { PortalShell } from "./Layout";
import { Panel } from "./RecordViews";
import { Alert, Dialog, Field } from "./ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/format";
import { applyPinResponse } from "../lib/passwordResetSession";
import { showToast } from "../lib/toasts";
import { friendlyError, passwordIsValid } from "../lib/userMessages";

export default function AccountSettings({ role }) {
  const navigate = useNavigate();
  const { login, user, refreshUser } = useAuth();
  const alumni = role === "Alumni";
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [fieldError, setFieldError] = useState("");
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotBusy, setForgotBusy] = useState(false);
  const [forgotError, setForgotError] = useState("");

  async function changePassword(event) {
    event.preventDefault();
    if (busy) return;
    setError("");
    setFieldError("");
    if (pw.new_password !== pw.confirm) {
      setFieldError("New password confirmation does not match.");
      return;
    }
    if (!passwordIsValid(pw.new_password)) {
      setFieldError("Minimum 8 characters, including letters and numbers.");
      return;
    }
    setBusy(true);
    try {
      const data = await api("/api/auth/change-password", {
        method: "POST",
        body: { current_password: pw.current_password, new_password: pw.new_password },
      });
      if (data.access_token) {
        login(data.access_token, { ...user, must_change_password: false });
      }
      try {
        await refreshUser?.();
      } catch {
        /* session already updated */
      }
      setPw({ current_password: "", new_password: "", confirm: "" });
      showToast("success", data.message || "Password updated.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't update your password. Please check your current password and try again."));
    } finally {
      setBusy(false);
    }
  }

  async function sendResetPin() {
    const email = String(user?.personal_email || "").trim();
    if (!email || forgotBusy) return;
    setForgotBusy(true);
    setForgotError("");
    try {
      const data = await api("/api/auth/forgot-password", { method: "POST", body: { email } });
      applyPinResponse(email, data);
      setForgotOpen(false);
      navigate("/forgot-password/verify");
    } catch (err) {
      setForgotError(friendlyError(err, "We couldn't send a verification PIN. Please try again."));
      setForgotBusy(false);
    }
  }

  const facts = [
    ["Email", user?.personal_email || "—"],
    alumni ? ["Student ID", user?.linked_student_id || "—"] : null,
    ["Status", user?.status || "—"],
    ["Role", alumni ? "Alumni" : "Administrator"],
    user?.created_at ? ["Member since", formatDate(user.created_at)] : null,
  ].filter(Boolean);

  return (
    <PortalShell role={role}>
      <Alert type="error">{error}</Alert>
      {user?.must_change_password ? (
        <Alert type="info" title="Change your password">
          A temporary password was issued for this account. Set a new password before continuing.
        </Alert>
      ) : null}

      <Panel
        className="account-panel"
        title="Account information"
        description={alumni
          ? "Email and student ID come from the graduate registry and cannot be changed here. Profile and career details stay on Home."
          : "This email is the sign-in for your administrator account and cannot be changed here."}
      >
        <dl className="aac-facts">
          {facts.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        {alumni ? <SourceBadge>From AUF Graduate Registry</SourceBadge> : null}
      </Panel>

      <Panel
        title="Security"
        description="Use a password with at least 8 characters, including letters and numbers."
      >
        <form className="account-security" id="change-password" onSubmit={changePassword}>
          <Field label="Current password" required>
            <input type="password" autoComplete="current-password" value={pw.current_password} onChange={(event) => setPw({ ...pw, current_password: event.target.value })} required />
          </Field>
          <p className="account-forgot">
            <button
              type="button"
              onClick={() => {
                setForgotError("");
                setForgotOpen(true);
              }}
            >
              Forgot password?
            </button>
          </p>
          <Field label="New password" required error={fieldError}>
            <input type="password" autoComplete="new-password" minLength={8} value={pw.new_password} onChange={(event) => setPw({ ...pw, new_password: event.target.value })} required />
          </Field>
          <PasswordHints value={pw.new_password} />
          <Field label="Confirm new password" required>
            <input type="password" autoComplete="new-password" value={pw.confirm} onChange={(event) => setPw({ ...pw, confirm: event.target.value })} required />
          </Field>
          <PasswordMatch password={pw.new_password} confirm={pw.confirm} />
          <button className="btn btn-navy" disabled={busy}>{busy ? "Updating…" : "Update password"}</button>
          <p className="security-note">Changing your password will require other active sessions to sign in again.</p>
        </form>
      </Panel>

      {forgotOpen ? (
        <Dialog
          title="Forgot your password?"
          description={`We'll send a verification PIN to ${user?.personal_email || "your account email"}. You can enter that PIN to choose a new password.`}
          confirmLabel={forgotBusy ? "Sending PIN…" : "Send PIN"}
          busy={forgotBusy}
          onConfirm={sendResetPin}
          onClose={() => { if (!forgotBusy) setForgotOpen(false); }}
        >
          <Alert type="error">{forgotError}</Alert>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
