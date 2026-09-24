import { useEffect, useId, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  AuthPageHeader,
  ForgotStepper,
  PasswordHints,
  PasswordMatch,
  PinInput,
} from "../../components/AuthFlow";
import { PublicFooter, PublicHeader } from "../../components/Layout";
import { Alert, Field } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import {
  applyPinResponse,
  clearResetSession,
  formatCountdown,
  readResetSession,
  writeResetSession,
} from "../../lib/passwordResetSession";
import { friendlyError, passwordIsValid } from "../../lib/userMessages";

function AuthLayout({ children }) {
  return (
    <>
      <PublicHeader />
      <main id="main" className="auth-shell">
        <div className="card auth-card">{children}</div>
      </main>
      <PublicFooter />
    </>
  );
}

function EmailDeliveryNotice() {
  const [configured, setConfigured] = useState(true);
  useEffect(() => {
    api("/api/health")
      .then((data) => setConfigured(Boolean(data.email_configured)))
      .catch(() => {});
  }, []);
  if (configured) return null;
  return (
    <Alert type="warn">
      This CareerSense server cannot send email, so a PIN will not arrive in your inbox.
      An administrator must set a real Resend API key and verified from address
      (EMAIL_API_KEY, EMAIL_FROM_ADDRESS, EMAIL_ENABLED=true), then restart the API.
    </Alert>
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

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState(readResetSession().email || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const data = await api("/api/auth/forgot-password", { method: "POST", body: { email } });
      applyPinResponse(email, data);
      navigate("/forgot-password/verify");
    } catch (err) {
      setError(friendlyError(err, "We couldn't send a verification PIN. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <AuthPageHeader
        title="Forgot your password?"
        lead="Enter the email address associated with your CareerSense account. We'll send a verification PIN to your email."
      />
      <ForgotStepper step={1} />
      <EmailDeliveryNotice />
      <Alert type="error">{error}</Alert>
      <form onSubmit={onSubmit} aria-busy={busy}>
        <Field label="Email Address" required>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </Field>
        <button className="btn btn-navy btn-block" disabled={busy}>
          {busy ? "Sending PIN…" : "Send PIN"}
        </button>
      </form>
      <p className="auth-foot-link"><Link to="/login">Back to Sign In</Link></p>
    </AuthLayout>
  );
}

export function VerifyResetPinPage() {
  const navigate = useNavigate();
  const session = readResetSession();
  const pinLabelId = useId();
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const expiresLeft = useCountdown(session.expiresAt);
  const resendLeft = useCountdown(session.resendAt);
  const expired = Boolean(session.expiresAt) && expiresLeft <= 0;

  if (!session.email) {
    return <Navigate to="/forgot-password" replace />;
  }

  async function verify(event) {
    event.preventDefault();
    if (busy || pin.length !== 6) return;
    setBusy(true);
    setError("");
    try {
      const data = await api("/api/auth/forgot-password/verify", {
        method: "POST",
        body: { email: session.email, pin },
      });
      writeResetSession({ resetToken: data.reset_token, expiresAt: Date.now() + (Number(data.expires_in) || 600) * 1000 });
      navigate("/reset-password");
    } catch (err) {
      setError(friendlyError(err, "The PIN is incorrect. Please try again."));
      setPin("");
    } finally {
      setBusy(false);
    }
  }

  async function sendAgain() {
    if (busy || resendLeft > 0) return;
    setBusy(true);
    setError("");
    try {
      const data = await api("/api/auth/forgot-password/resend", { method: "POST", body: { email: session.email } });
      applyPinResponse(session.email, data);
      setPin("");
    } catch (err) {
      setError(friendlyError(err, "We couldn't send a new PIN. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <AuthPageHeader
        title="Enter Verification PIN"
        lead="We sent a 6-digit PIN to your registered email address."
      />
      <ForgotStepper step={2} />
      <EmailDeliveryNotice />
      {session.maskedEmail ? <p className="muted pin-email">Sent to {session.maskedEmail}</p> : null}
      <Alert type="error">{error}</Alert>
      {expired ? (
        <Alert type="warn">Your PIN has expired. Please request a new PIN.</Alert>
      ) : (
        <p className="pin-countdown" role="status" aria-live="polite">
          PIN expires in <span>{formatCountdown(expiresLeft)}</span>
        </p>
      )}
      <form onSubmit={verify} aria-busy={busy}>
        <div className="field">
          <label id={pinLabelId}>Verification PIN</label>
          <PinInput value={pin} onChange={setPin} disabled={busy || expired} error={Boolean(error)} labelledBy={pinLabelId} />
        </div>
        <button className="btn btn-navy btn-block" disabled={busy || expired || pin.length !== 6}>
          {busy ? "Verifying…" : "Verify PIN"}
        </button>
      </form>
      <div className="auth-reset-actions">
        {expired || resendLeft <= 0 ? (
          <button type="button" className="btn btn-outline btn-block" onClick={sendAgain} disabled={busy}>
            {expired ? "Send New PIN" : "Resend PIN"}
          </button>
        ) : (
          <p className="muted pin-countdown" role="status">Resend PIN in {formatCountdown(resendLeft)}</p>
        )}
        <p className="auth-foot-link"><Link to="/forgot-password">Back to Email</Link></p>
      </div>
    </AuthLayout>
  );
}

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const session = readResetSession();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  if (!session.resetToken && !done) {
    return <Navigate to="/forgot-password" replace />;
  }

  async function onSubmit(event) {
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
      await api("/api/auth/reset-password", {
        method: "POST",
        body: { reset_token: session.resetToken, new_password: password },
      });
      clearResetSession();
      logout();
      setDone(true);
    } catch (err) {
      setError(friendlyError(err, "Your password reset session is no longer valid. Please start again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      {done ? (
        <>
          <AuthPageHeader
            title="Password updated successfully"
            lead="Your password has been changed. You can now sign in using your new password."
          />
          <ForgotStepper step={3} />
          <button className="btn btn-navy btn-block" type="button" onClick={() => navigate("/login")}>
            Return to Sign In
          </button>
        </>
      ) : (
        <>
          <AuthPageHeader
            title="Create a new password"
            lead="Choose a password you have not used on CareerSense before."
          />
          <ForgotStepper step={3} />
          <Alert type="info">Email verified successfully. You can now create a new password.</Alert>
          <Alert type="error">{error}</Alert>
          <form onSubmit={onSubmit} aria-busy={busy}>
            <Field label="New Password" required>
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={8}
              />
            </Field>
            <PasswordHints value={password} />
            <Field label="Confirm New Password" required>
              <input
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                required
                minLength={8}
              />
            </Field>
            <PasswordMatch password={password} confirm={confirm} />
            <button className="btn btn-navy btn-block" disabled={busy}>
              {busy ? "Updating…" : "Reset Password"}
            </button>
          </form>
          <p className="auth-foot-link"><Link to="/forgot-password">Start again</Link></p>
        </>
      )}
    </AuthLayout>
  );
}
