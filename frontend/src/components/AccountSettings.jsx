import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ForgotStepper, PasswordHints, PasswordMatch, PinInput } from "./AuthFlow";
import { PortalShell } from "./Layout";
import { Panel } from "./RecordViews";
import { Alert, Field } from "./ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/format";
import {
  applyPinResponse,
  clearResetSession,
  formatCountdown,
  readResetSession,
  writeResetSession,
} from "../lib/passwordResetSession";
import { showToast } from "../lib/toasts";
import { friendlyError, passwordIsValid } from "../lib/userMessages";

export default function AccountSettings({ role }) {
  const navigate = useNavigate();
  const { login, logout, user, refreshUser } = useAuth();
  const alumni = role === "Alumni";
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [fieldError, setFieldError] = useState("");
  const [office, setOffice] = useState(null);
  const [helpTopic, setHelpTopic] = useState("");

  useEffect(() => {
    if (!alumni) return undefined;
    let cancelled = false;
    api("/api/alumni/office")
      .then((payload) => {
        if (!cancelled) setOffice(payload);
      })
      .catch(() => {
        if (!cancelled) setOffice(null);
      });
    return () => {
      cancelled = true;
    };
  }, [alumni]);

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
          {alumni
            ? "A temporary password was issued for this account. Use the PIN sent to your registered email, then choose a new password."
            : "A temporary password was issued for this account. Set a new password before continuing."}
        </Alert>
      ) : null}

      <Panel
        className="account-panel"
        title="Account information"
        description={alumni
          ? "Your sign-in email and student ID come from the graduate registry. Profile and career details stay on Home."
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
      </Panel>

      {alumni ? (
        <Panel
          title="Password recovery"
          description="Recover your password with a PIN sent to your registered email. Verify the PIN, then choose a new password. Your current password is not required."
        >
          <AlumniPasswordRecovery email={user?.personal_email || ""} onSignIn={() => {
            logout();
            navigate("/login", { replace: true, state: { notice: "Password updated successfully. Sign in with your new password." } });
          }} />
        </Panel>
      ) : (
        <Panel
          title="Security"
          description="Use a password with at least 8 characters, including letters and numbers."
        >
          <form className="account-security" id="change-password" onSubmit={changePassword}>
            <Field label="Current password" required>
              <input type="password" autoComplete="current-password" value={pw.current_password} onChange={(event) => setPw({ ...pw, current_password: event.target.value })} required />
            </Field>
            <Field label="New password" required error={fieldError}>
              <input type="password" autoComplete="new-password" minLength={8} value={pw.new_password} onChange={(event) => setPw({ ...pw, new_password: event.target.value })} required />
            </Field>
            <Field label="Confirm new password" required>
              <input type="password" autoComplete="new-password" value={pw.confirm} onChange={(event) => setPw({ ...pw, confirm: event.target.value })} required />
            </Field>
            <PasswordHints value={pw.new_password} />
            <PasswordMatch password={pw.new_password} confirm={pw.confirm} />
            <button className="btn btn-navy" disabled={busy}>{busy ? "Updating…" : "Update password"}</button>
            <p className="security-note">Changing your password will require other active sessions to sign in again.</p>
          </form>
        </Panel>
      )}

      {alumni ? (
        <div className="account-grid">
          <Panel
            className="account-help"
            title="Delete account"
            description="Alumni accounts are not deleted from CareerSense."
          >
            <div className="account-help-body">
              <p>To delete your account, contact the Office of Alumni Affairs and Placement Services (OAAPS). This page does not delete or deactivate your account.</p>
              <button type="button" className="btn btn-outline" onClick={() => setHelpTopic("delete")}>Contact OAAPS</button>
            </div>
            {helpTopic === "delete" ? <OfficeContact office={office} note="Viewing these instructions does not delete or deactivate your account." onClose={() => setHelpTopic("")} /> : null}
          </Panel>
          <Panel
            className="account-help"
            title="Email address recovery"
            description="A lost sign-in email is restored by OAAPS."
          >
            <div className="account-help-body">
              <p>If you cannot access the email address registered on your account, contact OAAPS. The office confirms your alumni record before any change. CareerSense does not offer a self-service email change or email recovery.</p>
              <button type="button" className="btn btn-outline" onClick={() => setHelpTopic("email")}>Contact OAAPS</button>
            </div>
            {helpTopic === "email" ? <OfficeContact office={office} onClose={() => setHelpTopic("")} /> : null}
          </Panel>
        </div>
      ) : null}

    </PortalShell>
  );
}

function useCountdown(target) {
  const [left, setLeft] = useState(() => Math.max(0, (target || 0) - Date.now()));
  useEffect(() => {
    setLeft(Math.max(0, (target || 0) - Date.now()));
    if (!target) return undefined;
    const id = window.setInterval(() => {
      setLeft(Math.max(0, target - Date.now()));
    }, 250);
    return () => window.clearInterval(id);
  }, [target]);
  return left;
}

function recoveryStep(email) {
  const session = readResetSession();
  if (!email || session.email !== email) return "send";
  if (session.resetToken) return "password";
  if (session.expiresAt && session.expiresAt > Date.now()) return "pin";
  return "send";
}

function AlumniPasswordRecovery({ email, onSignIn }) {
  const pinLabelId = useId();
  const registered = String(email || "").trim();
  const [step, setStep] = useState(() => recoveryStep(registered));
  const [session, setSession] = useState(() => readResetSession());
  const [pin, setPin] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [verified, setVerified] = useState("");
  const [busy, setBusy] = useState(false);
  const errorRef = useRef(null);
  const expiresLeft = useCountdown(step === "pin" ? session.expiresAt : 0);
  const resendLeft = useCountdown(step === "pin" ? session.resendAt : 0);
  const expired = step === "pin" && Boolean(session.expiresAt) && expiresLeft <= 0;

  useEffect(() => {
    if (error) errorRef.current?.scrollIntoView({ block: "nearest" });
  }, [error]);

  function restart() {
    clearResetSession();
    setSession({});
    setStep("send");
    setPin("");
    setPassword("");
    setConfirm("");
    setError("");
    setNotice("");
    setVerified("");
  }

  async function sendPin(event) {
    event?.preventDefault();
    if (busy || !registered) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await api("/api/auth/forgot-password", { method: "POST", body: { email: registered } });
      const next = applyPinResponse(registered, data);
      setSession(next);
      setPin("");
      setNotice(data.message || "If an account exists for this email address, a verification PIN has been sent.");
      setStep("pin");
    } catch (err) {
      setError(friendlyError(err, "We couldn't send a verification PIN. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  async function verifyPin(event) {
    event.preventDefault();
    if (busy || pin.length !== 6 || expired) return;
    setBusy(true);
    setError("");
    try {
      const data = await api("/api/auth/forgot-password/verify", {
        method: "POST",
        body: { email: registered, pin },
      });
      const next = writeResetSession({
        resetToken: data.reset_token,
        expiresAt: Date.now() + (Number(data.expires_in) || 600) * 1000,
      });
      setSession(next);
      setVerified(data.message || "Email verified successfully. You can now create a new password.");
      setStep("password");
    } catch (err) {
      setError(friendlyError(err, "The PIN is incorrect. Please try again."));
      setPin("");
    } finally {
      setBusy(false);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    if (busy) return;
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (!passwordIsValid(password)) {
      setError("Your password does not meet the required security requirements.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = await api("/api/auth/reset-password", {
        method: "POST",
        body: { reset_token: session.resetToken, new_password: password },
      });
      clearResetSession();
      setVerified(data.message || "Password updated successfully");
      setStep("done");
    } catch (err) {
      setError(friendlyError(err, "Your password reset session is no longer valid. Please start again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-recovery">
      <ForgotStepper step={step === "send" ? 1 : step === "pin" ? 2 : 3} />
      {step === "send" ? (
        <form onSubmit={sendPin} aria-busy={busy}>
          <p>A 6-digit PIN is sent to your registered email. Enter that PIN before it expires, then choose a new password.</p>
          <p className="muted pin-email">Registered email: {registered || "No email is stored on this account."}</p>
          <Alert type="error" alertRef={errorRef}>{error}</Alert>
          <button className="btn btn-navy" disabled={busy || !registered}>{busy ? "Sending PIN…" : "Send PIN"}</button>
        </form>
      ) : null}
      {step === "pin" ? (
        <form onSubmit={verifyPin} aria-busy={busy}>
          <Alert type="info">{notice || "If an account exists for this email address, a verification PIN has been sent."}</Alert>
          {session.maskedEmail ? <p className="muted pin-email">Sent to {session.maskedEmail}</p> : null}
          <p>Enter the 6-digit PIN from that email, then verify it.</p>
          {expired ? (
            <Alert type="warn">Your PIN has expired. Please request a new PIN.</Alert>
          ) : (
            <p className="pin-countdown" role="status" aria-live="polite">PIN expires in <span>{formatCountdown(expiresLeft)}</span></p>
          )}
          <Alert type="error" alertRef={errorRef}>{error}</Alert>
          <div className="field">
            <label id={pinLabelId}>Verification PIN</label>
            <PinInput value={pin} onChange={setPin} disabled={busy || expired} error={Boolean(error)} labelledBy={pinLabelId} />
          </div>
          <div className="account-recovery-actions">
            <button className="btn btn-navy" disabled={busy || expired || pin.length !== 6}>
              {busy ? "Verifying…" : "Verify PIN"}
            </button>
            {expired || resendLeft <= 0 ? (
              <button type="button" className="btn btn-outline" onClick={sendPin} disabled={busy}>
                {expired ? "Send new PIN" : "Resend PIN"}
              </button>
            ) : (
              <p className="muted pin-countdown" role="status">Resend PIN in {formatCountdown(resendLeft)}</p>
            )}
            <button type="button" className="btn btn-text" onClick={restart}>Start again</button>
          </div>
        </form>
      ) : null}
      {step === "password" ? (
        <form onSubmit={savePassword} aria-busy={busy}>
          <Alert type="info">{verified || "Email verified successfully. You can now create a new password."}</Alert>
          <Alert type="error" alertRef={errorRef}>{error}</Alert>
          <Field label="New password" required>
            <input type="password" autoComplete="new-password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
          </Field>
          <PasswordHints value={password} />
          <Field label="Confirm new password" required>
            <input type="password" autoComplete="new-password" minLength={8} value={confirm} onChange={(event) => setConfirm(event.target.value)} required />
          </Field>
          <PasswordMatch password={password} confirm={confirm} />
          <div className="account-recovery-actions">
            <button className="btn btn-navy" disabled={busy}>{busy ? "Updating…" : "Reset password"}</button>
            <button type="button" className="btn btn-text" onClick={restart}>Start again</button>
          </div>
        </form>
      ) : null}
      {step === "done" ? (
        <>
          <Alert type="success" title="Password updated successfully">
            Your password has been changed. Sign in again with the new password.
          </Alert>
          <button type="button" className="btn btn-navy" onClick={onSignIn}>Sign in</button>
        </>
      ) : null}
    </div>
  );
}

function OfficeContact({ office, note, onClose }) {
  return (
    <div className="account-office">
      <div className="account-office-head">
        <p><strong>{office?.name || "Office of Alumni Affairs and Placement Services (OAAPS)"}</strong></p>
        <button type="button" className="btn btn-outline btn-sm" onClick={onClose}>Close</button>
      </div>
      <dl>
        {office?.location ? <div><dt>Visit</dt><dd>{office.location}</dd></div> : null}
        {office?.hours ? <div><dt>Hours</dt><dd>{office.hours}</dd></div> : null}
        {office?.phone ? <div><dt>Phone</dt><dd>{office.phone}</dd></div> : null}
        {office?.email ? <div><dt>Email</dt><dd><a href={`mailto:${office.email}`}>{office.email}</a></dd></div> : null}
      </dl>
      {note ? <p className="muted">{note}</p> : null}
    </div>
  );
}
