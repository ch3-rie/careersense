import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ForgotStepper, PasswordHints, PasswordMatch, PinInput } from "./AuthFlow";
import { PortalShell } from "./Layout";
import { Panel } from "./RecordViews";
import { ChevronDownIcon } from "./icons";
import { Alert, Dialog, Field } from "./ui";
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
  const { login, logout, user, refreshUser, loading } = useAuth();
  const alumni = role === "Alumni";
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [fieldError, setFieldError] = useState("");
  const [office, setOffice] = useState(null);
  const [officeState, setOfficeState] = useState(alumni ? "loading" : "idle");
  const [helpTopic, setHelpTopic] = useState("");

  function loadOffice() {
    if (!alumni) return;
    setOfficeState("loading");
    api("/api/alumni/office")
      .then((payload) => {
        setOffice(payload);
        setOfficeState("ready");
      })
      .catch(() => {
        setOffice(null);
        setOfficeState("error");
      });
  }

  useEffect(() => {
    if (!alumni) return undefined;
    let cancelled = false;
    setOfficeState("loading");
    api("/api/alumni/office")
      .then((payload) => {
        if (cancelled) return;
        setOffice(payload);
        setOfficeState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setOffice(null);
        setOfficeState("error");
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

  if (alumni && loading && !user) {
    return (
      <PortalShell role={role}>
        <div className="account-page" aria-busy="true" aria-label="Loading account settings">
          <div className="card account-skel-card"><div className="skeleton account-skel-block" /></div>
          <div className="card account-skel-card"><div className="skeleton account-skel-block is-tall" /></div>
          <div className="account-grid">
            <div className="card account-skel-card"><div className="skeleton account-skel-block" /></div>
            <div className="card account-skel-card"><div className="skeleton account-skel-block" /></div>
          </div>
        </div>
      </PortalShell>
    );
  }

  const statusLabel = user?.status || "—";

  return (
    <PortalShell role={role}>
      {alumni ? (
        <div className="account-page">
          <Alert type="error">{error}</Alert>
          {user?.must_change_password ? (
            <Alert type="info" title="Complete Your Password Setup">
              A temporary password was issued for this account. Use the PIN sent to your registered email to verify your identity, then choose a new password.
            </Alert>
          ) : null}
          <Panel
            className="account-panel"
            title="Account information"
            description="Your sign-in email and student ID come from the graduate registry. These details are read-only and cannot be changed here."
          >
            <dl className="account-facts">
              <div>
                <dt>Email</dt>
                <dd>{user?.personal_email || "—"}</dd>
              </div>
              <div>
                <dt>Student ID</dt>
                <dd>{user?.linked_student_id || "—"}</dd>
              </div>
              <div>
                <dt>Account status</dt>
                <dd>
                  <span className={`account-status${String(statusLabel).toLowerCase() === "active" ? " is-active" : ""}`}>{statusLabel}</span>
                </dd>
              </div>
              <div>
                <dt>Role</dt>
                <dd>Alumni</dd>
              </div>
              <div>
                <dt>Member since</dt>
                <dd>{user?.created_at ? formatDate(user.created_at) : "—"}</dd>
              </div>
            </dl>
          </Panel>
          <Panel
            title="Password recovery"
            description="Reset your password with a verification PIN sent to your registered email. Your current password is not required."
          >
            <AlumniPasswordRecovery email={user?.personal_email || ""} onSignIn={() => {
              logout();
              navigate("/login", { replace: true, state: { notice: "Password updated successfully. Sign in with your new password." } });
            }} />
          </Panel>
          <section className="account-assist" aria-label="Account assistance">
            <div className="account-grid">
              <Panel
                className="account-help"
                title="Lost access to your email?"
                description="A lost sign-in email is restored by OAAPS."
              >
                <div className="account-help-body">
                  <p>The sign-in email cannot be changed in CareerSense. Contact the Alumni Office, and the office will confirm your university record before restoring access.</p>
                  <button type="button" className="btn btn-outline" onClick={() => setHelpTopic("email")}>Contact the Alumni Office</button>
                </div>
              </Panel>
              <Panel
                className="account-help"
                title="Account deletion assistance"
                description="Alumni accounts are not deleted from CareerSense."
              >
                <div className="account-help-body">
                  <p>Accounts are not deleted or deactivated on this page. Contact the Office of Alumni Affairs and Placement Services (OAAPS) to request help.</p>
                  <p className="muted">Opening the contact details does not delete or deactivate your account.</p>
                  <button type="button" className="btn btn-outline" onClick={() => setHelpTopic("delete")}>Contact the Alumni Office</button>
                </div>
              </Panel>
            </div>
          </section>
          {helpTopic ? (
            <Dialog
              title="Alumni Office"
              description={helpTopic === "delete" ? "Viewing these instructions does not delete or deactivate your account." : "The Alumni Office confirms your alumni record before restoring access to a sign-in email."}
              hideActions
              onClose={() => setHelpTopic("")}
              footer={(
                <button type="button" className="btn btn-outline" onClick={() => setHelpTopic("")}>Close</button>
              )}
            >
              <OfficeDetails office={office} state={officeState} onRetry={loadOffice} />
            </Dialog>
          ) : null}
        </div>
      ) : (
        <>
      <Alert type="error">{error}</Alert>
      {user?.must_change_password ? (
        <Alert type="info" title="Change your password">
          A temporary password was issued for this account. Set a new password before continuing.
        </Alert>
      ) : null}

      <Panel
        className="account-panel"
        title="Account information"
        description="This email is the sign-in for your administrator account and cannot be changed here."
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
        </>
      )}
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
  const resetLeft = useCountdown(step === "password" ? session.expiresAt : 0);
  const expired = step === "pin" && Boolean(session.expiresAt) && expiresLeft <= 0;
  const resetExpired = step === "password" && Boolean(session.expiresAt) && resetLeft <= 0;

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
    if (busy || resetExpired) return;
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
          <Field label="Registered email">
            <input value={registered || "—"} readOnly aria-readonly="true" />
          </Field>
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
          {resetExpired ? (
            <Alert type="warn">Your password reset session is no longer valid. Please start again.</Alert>
          ) : (
            <Alert type="info">{verified || "Email verified successfully. You can now create a new password."}</Alert>
          )}
          {!resetExpired ? (
            <p className="pin-countdown" role="status" aria-live="polite">Reset session expires in <span>{formatCountdown(resetLeft)}</span></p>
          ) : null}
          <Alert type="error" alertRef={errorRef}>{error}</Alert>
          <SecretField label="New password" autoComplete="new-password" value={password} onChange={setPassword} disabled={resetExpired || busy} />
          <PasswordHints value={password} />
          <SecretField label="Confirm new password" autoComplete="new-password" value={confirm} onChange={setConfirm} disabled={resetExpired || busy} />
          <PasswordMatch password={password} confirm={confirm} />
          <div className="account-recovery-actions">
            <button className="btn btn-navy" disabled={busy || resetExpired}>{busy ? "Updating…" : "Reset password"}</button>
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

function SecretField({ label, value, onChange, autoComplete, disabled }) {
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label} required>
      <div className="account-secret">
        <input
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          minLength={8}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required
          disabled={disabled}
        />
        <button
          type="button"
          className="account-secret-toggle"
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          onClick={() => setVisible((current) => !current)}
          disabled={disabled}
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
    </Field>
  );
}

const OFFICE_TIME_ZONE = "Asia/Manila";
const OFFICE_SCHEDULE = [
  { day: "Monday", opens: "08:00", closes: "17:00" },
  { day: "Tuesday", opens: "08:00", closes: "17:00" },
  { day: "Wednesday", opens: "08:00", closes: "17:00" },
  { day: "Thursday", opens: "08:00", closes: "17:00" },
  { day: "Friday", opens: "08:00", closes: "17:00" },
  { day: "Saturday", closed: true },
  { day: "Sunday", closed: true },
];

function officeSchedule(office) {
  const rows = Array.isArray(office?.schedule) ? office.schedule : [];
  const usable = rows.filter((row) => row && row.day);
  return usable.length ? usable : OFFICE_SCHEDULE;
}

function manilaClock(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: OFFICE_TIME_ZONE,
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const read = (type) => parts.find((part) => part.type === type)?.value || "";
  const hour = Number(read("hour"));
  const minute = Number(read("minute"));
  return {
    weekday: read("weekday"),
    minutes: (Number.isFinite(hour) ? hour : 0) * 60 + (Number.isFinite(minute) ? minute : 0),
  };
}

function minutesFromClock(value) {
  const match = String(value || "").match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function isOfficeOpen(schedule, date = new Date()) {
  const { weekday, minutes } = manilaClock(date);
  const today = schedule.find((row) => row.day === weekday);
  if (!today || today.closed) return false;
  const opens = minutesFromClock(today.opens);
  const closes = minutesFromClock(today.closes);
  if (opens == null || closes == null) return false;
  return minutes >= opens && minutes < closes;
}

function hoursLabel(row) {
  if (row?.closed || !row?.opens || !row?.closes) return "CLOSED";
  return `${row.opens} - ${row.closes}`;
}

function OfficeDetails({ office, state, onRetry }) {
  const schedule = officeSchedule(office);
  const location = String(office?.location || "Room 307, 3rd Floor, Angeles Hall, Angeles City, Philippines, 2009").trim();
  const phone = String(office?.phone || "(045) 625 2888").trim();
  const email = String(office?.email || "alumni@auf.edu.ph").trim();
  const [openNow, setOpenNow] = useState(() => isOfficeOpen(schedule));
  const [today, setToday] = useState(() => manilaClock().weekday);
  const [showSchedule, setShowSchedule] = useState(false);
  const todayRow = schedule.find((row) => row.day === today);
  const todayStatus = openNow ? "Open" : "Closed";

  useEffect(() => {
    const tick = () => {
      const rows = officeSchedule(office);
      setOpenNow(isOfficeOpen(rows));
      setToday(manilaClock().weekday);
    };
    tick();
    const timer = window.setInterval(tick, 30000);
    return () => window.clearInterval(timer);
  }, [office]);

  return (
    <div className="account-office">
      {state === "loading" ? <p>Loading office details…</p> : null}
      {state === "error" ? (
        <div className="account-office-missing">
          <p>Contact information is currently unavailable.</p>
          <button type="button" className="btn btn-outline btn-sm" onClick={onRetry}>Try again</button>
        </div>
      ) : null}
      {state === "ready" ? (
        <dl className="account-office-list">
          <div>
            <dt>Office hours</dt>
            <dd>
              <button
                type="button"
                className="account-office-today"
                aria-expanded={showSchedule}
                aria-label={`${today}, ${todayStatus}. ${showSchedule ? "Hide" : "Show"} the weekly schedule`}
                onClick={() => setShowSchedule((current) => !current)}
              >
                <span>{today}</span>
                <span className={`account-office-today-status${openNow ? " is-open" : " is-closed"}`}>
                  {openNow && todayRow ? hoursLabel(todayRow) : "Closed"}
                  <ChevronDownIcon size={16} className={showSchedule ? "is-open" : undefined} />
                </span>
              </button>
              {showSchedule ? (
                <ul className="account-office-hours">
                  {schedule.map((row) => (
                    <li key={row.day} className={row.day === today ? "is-today" : undefined}>
                      <span>{row.day}</span>
                      <span>{hoursLabel(row)}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </dd>
          </div>
          {location ? <div><dt>Office location</dt><dd>{location}</dd></div> : null}
          {phone ? <div><dt>Phone</dt><dd><a href={`tel:${phone}`}>{phone}</a></dd></div> : null}
          {email ? <div><dt>Email</dt><dd><a href={`mailto:${email}`}>{email}</a></dd></div> : null}
        </dl>
      ) : null}
    </div>
  );
}
