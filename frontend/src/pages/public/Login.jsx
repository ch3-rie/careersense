import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthPageHeader } from "../../components/AuthFlow";
import { PublicFooter, PublicHeader } from "../../components/Layout";
import { Alert, Field } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { friendlyError } from "../../lib/userMessages";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const notice = location.state?.notice || "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const data = await api("/api/auth/login", { method: "POST", body: { email, password } });
      login(data.access_token, data.user);
      if (data.user.role === "Admin") navigate(data.user.must_change_password ? "/admin/account" : "/admin");
      else if (data.user.status === "Pending") navigate("/pending");
      else if (data.user.status === "Rejected") navigate("/rejected");
      else navigate("/alumni");
    } catch (err) {
      setError(friendlyError(err, "We couldn't sign you in. Check your email and password, then try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PublicHeader />
      <main id="main" className="auth-shell">
        <div className="card auth-card">
          <AuthPageHeader
            kicker="CareerSense"
            title="Sign in to CareerSense"
            lead="Use the email associated with your AUF graduate or administrator account."
          />
          <Alert type={error ? "error" : "info"}>{error || notice}</Alert>
          <form onSubmit={onSubmit} aria-busy={busy}>
            <Field label="Email" required>
              <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            <Field label="Password" required>
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </Field>
            <p className="auth-forgot">
              <Link to="/forgot-password">Forgot Password?</Link>
            </p>
            <button className="btn btn-navy btn-block" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="auth-foot-link">New graduate? <Link to="/register">Create an account and upload your resume</Link>.</p>
        </div>
      </main>
      <PublicFooter />
    </>
  );
}
