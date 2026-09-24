import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AuthPageHeader,
  FileUploadField,
  FormBlock,
  ParseProgress,
  PasswordHints,
  PasswordMatch,
  RegisterStepper,
  RegistryMatch,
  StatusTimeline,
} from "../../components/AuthFlow";
import GtsForm from "../../components/GtsForm";
import RegistrationLeaveGuard from "../../components/RegistrationLeaveGuard";
import { PublicFooter, PublicHeader } from "../../components/Layout";
import { Alert, Badge, Field, Skeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { clearJustRegistered, markJustRegistered } from "../../lib/registerSession";
import { usePublishedSurvey } from "../../lib/surveyLive";
import { showToast } from "../../lib/toasts";
import { extractionState, friendlyError, passwordIsValid } from "../../lib/userMessages";
import { registrationHasProgress } from "../../lib/registrationProgress";

export default function RegisterPage() {
  const { login, user, logout } = useAuth();
  const navigate = useNavigate();
  const { options, reload: reloadSurvey } = usePublishedSurvey();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [parseStartedAt, setParseStartedAt] = useState(0);
  const headingRef = useRef(null);
  const [focusStep1, setFocusStep1] = useState(0);
  const [form, setForm] = useState({
    email: "",
    password: "",
    confirm_password: "",
    privacy_consent: false,
    resume: null,
  });
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (step === 2) reloadSurvey().catch(() => {});
  }, [step, reloadSurvey]);

  useEffect(() => {
    if (user?.status === "Pending" && step === 1 && !result) {
      navigate("/pending");
    }
  }, [user, step, result, navigate]);

  useEffect(() => {
    if (step === 1) return;
    headingRef.current?.focus();
  }, [step]);

  useEffect(() => {
    if (!focusStep1 || step !== 1) return;
    const node = document.querySelector(
      ".register-step .field.has-error input, .register-step .check.has-error input"
    );
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
    node.focus({ preventScroll: true });
  }, [focusStep1, step]);

  function applyServerError(err) {
    const msg = friendlyError(err);
    const lower = msg.toLowerCase();
    const next = {};
    if (lower.includes("password confirmation") || lower.includes("do not match")) next.confirm_password = msg;
    else if (lower.includes("password")) next.password = msg;
    else if (lower.includes("email") || lower.includes("account with this email") || lower.includes("already awaiting") || lower.includes("already exists")) {
      next.email = msg;
    } else if (lower.includes("consent")) next.privacy_consent = msg;
    else if (lower.includes("resume") || lower.includes("pdf") || lower.includes("docx") || lower.includes("upload") || lower.includes("file")) {
      next.resume = msg;
    }
    setFieldErrors(next);
    setError(Object.keys(next).length ? "Please correct the highlighted fields before continuing." : msg);
  }

  function validateStep1() {
    const next = {};
    if (!form.email.trim()) next.email = "Please enter your email.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = "Please enter a valid email address.";
    if (!form.password) next.password = "Please enter a password.";
    else if (!passwordIsValid(form.password)) {
      next.password = "Password must be at least 8 characters and include letters and numbers.";
    }
    if (!form.confirm_password) next.confirm_password = "Please confirm your password.";
    else if (form.password !== form.confirm_password) next.confirm_password = "Password confirmation does not match.";
    if (!form.resume) next.resume = "Please upload a PDF, DOCX, or TXT resume.";
    if (!form.privacy_consent) next.privacy_consent = "Privacy consent is required.";
    return next;
  }

  async function submitAccount(e) {
    e.preventDefault();
    if (busy) return;
    setError("");
    const next = validateStep1();
    setFieldErrors(next);
    if (Object.keys(next).length) {
      setError("Please correct the highlighted fields before continuing.");
      setFocusStep1((value) => value + 1);
      return;
    }
    setBusy(true);
    setParseStartedAt(Date.now());
    try {
      const payload = new FormData();
      payload.append("email", form.email);
      payload.append("password", form.password);
      payload.append("confirm_password", form.confirm_password);
      payload.append("privacy_consent", form.privacy_consent ? "true" : "false");
      payload.append("resume", form.resume);
      const data = await api("/api/auth/register", { method: "POST", form: payload });
      setResult(data);
      setStep(2);
      const state = extractionState(data);
      if (state === "failed") {
        showToast("warning", "We couldn't read this resume. You can still continue and enter your tracer information manually.");
      } else if (state === "empty") {
        showToast("info", "No information was extracted. You can enter your tracer information manually.");
      } else {
        showToast("success", "Resume uploaded. Review your tracer survey.");
      }
    } catch (err) {
      applyServerError(err);
    } finally {
      setBusy(false);
      setParseStartedAt(0);
    }
  }

  async function submitGts(payload) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const data = await api("/api/auth/register/complete", {
        method: "POST",
        body: { ...payload, registration_token: result.registration_token },
      });
      markJustRegistered();
      if (data.access_token && data.user) {
        login(data.access_token, data.user);
      }
      setStep(3);
      showToast("success", "Registration submitted successfully.");
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  const alignmentHint = result?.parsed_resume?.course_alignment || result?.gts_prefill?.course_alignment;
  const surveyClosed = options?.survey_open === false;
  const leaveArmed = registrationHasProgress(step, form, { submitted: step === 3 });

  return (
    <>
      <RegistrationLeaveGuard armed={leaveArmed} />
      <PublicHeader />
      <main id="main" className="auth-shell auth-wide">
        <div className="card auth-card">
          <AuthPageHeader
            title="Alumni Registration"
            badge={step === 3 ? <Badge tone="Pending">Pending approval</Badge> : result ? <Badge>Temporary draft</Badge> : null}
          />
          <RegisterStepper step={step} />

          {surveyClosed ? (
            <Alert type="info" title="Survey closed">
              The Graduate Tracer Survey is not currently accepting responses. You can save a resume draft, but you cannot submit registration until OAAPS reopens the survey.
            </Alert>
          ) : null}

          {error ? (
            <Alert type="error" title="We couldn't continue">
              {step === 1 && Object.keys(fieldErrors).length ? "Please correct the highlighted fields before continuing." : error}
            </Alert>
          ) : null}

          {step === 1 && (
            <form noValidate onSubmit={submitAccount} aria-busy={busy} className={`register-step${busy ? " is-busy" : ""}`}>
              <header className="register-step-head">
                <h2 className="auth-step-title" tabIndex={-1} ref={headingRef}>Create your alumni account</h2>
                <p className="lead">
                  Create your sign-in and upload a resume. CareerSense uses the resume to suggest Graduate Tracer Survey answers, which you review on the next step.
                </p>
              </header>

              {busy ? <ParseProgress startedAt={parseStartedAt} /> : null}

              <fieldset disabled={busy} className="auth-fieldset">
                <FormBlock title="Account information">
                  <Field label="Email" required error={fieldErrors.email}>
                    <input
                      type="email"
                      autoComplete="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      required
                    />
                  </Field>
                  <div className="inline-fields">
                    <div>
                      <Field label="Password" required error={fieldErrors.password}>
                        <input
                          type="password"
                          autoComplete="new-password"
                          value={form.password}
                          onChange={(e) => setForm({ ...form, password: e.target.value })}
                          required
                          minLength={8}
                        />
                      </Field>
                      <PasswordHints value={form.password} />
                    </div>
                    <div>
                      <Field label="Confirm password" required error={fieldErrors.confirm_password}>
                        <input
                          type="password"
                          autoComplete="new-password"
                          value={form.confirm_password}
                          onChange={(e) => setForm({ ...form, confirm_password: e.target.value })}
                          required
                        />
                      </Field>
                      <PasswordMatch password={form.password} confirm={form.confirm_password} />
                    </div>
                  </div>
                </FormBlock>

                <FormBlock title="Resume">
                  <FileUploadField
                    file={form.resume}
                    disabled={busy}
                    error={fieldErrors.resume}
                    onChange={(file, message) => {
                      setForm({ ...form, resume: file });
                      setFieldErrors((prev) => ({ ...prev, resume: message || "" }));
                      if (message) setError("Please correct the highlighted fields before continuing.");
                    }}
                  />
                </FormBlock>

                <FormBlock title="Privacy">
                  <label className={`check privacy-check ${fieldErrors.privacy_consent ? "has-error" : ""}`}>
                    <input
                      type="checkbox"
                      checked={form.privacy_consent}
                      aria-invalid={fieldErrors.privacy_consent ? true : undefined}
                      aria-describedby={fieldErrors.privacy_consent ? "privacy-consent-error" : undefined}
                      onChange={(e) => setForm({ ...form, privacy_consent: e.target.checked })}
                    />
                    <span>{options?.privacy_notice || "I consent to the processing of my personal data for graduate tracer purposes."}</span>
                  </label>
                  {fieldErrors.privacy_consent ? <span className="field-error" id="privacy-consent-error">{fieldErrors.privacy_consent}</span> : null}
                </FormBlock>
              </fieldset>

              <div className="register-step-actions">
                <button className="btn btn-navy btn-block" type="submit" disabled={busy}>
                  {busy ? "Reading resume…" : "Extract resume and continue"}
                </button>
                <p className="auth-foot-link">Already registered? <Link to="/login">Sign in</Link>.</p>
              </div>
            </form>
          )}

          {step === 2 && result && (
            <div className="register-step">
              <header className="register-step-head">
                <h2 className="auth-step-title" tabIndex={-1} ref={headingRef}>Review tracer survey</h2>
                <p className="lead">
                  Review each section. Correct any answer that is missing or wrong, then submit your tracer information.
                </p>
              </header>
              <RegistryMatch match={result.matched_record} />
              {!options ? (
                <div className="gts-loading" role="status">
                  <p className="muted">Loading the Graduate Tracer Survey…</p>
                  <Skeleton rows={6} />
                </div>
              ) : (
                <GtsForm
                  variant="review"
                  initial={result.gts_prefill}
                  options={options}
                  busy={busy}
                  submitLabel="Submit tracer information"
                  confirmSubmit
                  alignmentHint={alignmentHint}
                  resume={result.parsed_resume ? { ...result.parsed_resume, parser_source: result.parser_source } : null}
                  readOnly={surveyClosed}
                  closedMessage={surveyClosed ? "This survey is not currently accepting responses." : ""}
                  onSubmit={submitGts}
                />
              )}
            </div>
          )}

          {step === 3 && (
            <div className="register-step">
              <header className="register-step-head">
                <h2 className="auth-step-title" tabIndex={-1} ref={headingRef}>Registration submitted</h2>
                <p className="lead">Your registration is waiting for OAAPS to verify it.</p>
              </header>
              <StatusTimeline
                items={[
                  { label: "Tracer information submitted", status: "done" },
                  { label: "OAAPS review", status: "current" },
                  { label: "Alumni portal access", status: "upcoming" },
                ]}
              />
              <div className="register-step-copy">
                <p>OAAPS reviews your account, graduate record, resume, and tracer survey.</p>
                <p className="muted">This usually takes 1–3 working days. You can check your status while you wait.</p>
              </div>
              <div className="hero-actions">
                <button
                  className="btn btn-navy"
                  type="button"
                  onClick={() => {
                    clearJustRegistered();
                    navigate("/pending");
                  }}
                >
                  Check status
                </button>
                <button
                  className="btn btn-outline"
                  type="button"
                  onClick={() => {
                    clearJustRegistered();
                    logout();
                    navigate("/login");
                  }}
                >
                  Return to sign in
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
      <PublicFooter />
    </>
  );
}
