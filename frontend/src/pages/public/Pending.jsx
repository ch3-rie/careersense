import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthPageHeader, StatusTimeline } from "../../components/AuthFlow";
import { PublicFooter, PublicHeader } from "../../components/Layout";
import { Alert, Badge } from "../../components/ui";
import { useAuth } from "../../lib/auth";
import { clearJustRegistered } from "../../lib/registerSession";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

export default function PendingPage() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function checkStatus() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const data = await refreshUser();
      if (data?.user?.status === "Active") {
        clearJustRegistered();
        showToast("success", "Your account is active.");
        navigate("/alumni");
        return;
      }
      if (data?.user?.status === "Rejected") {
        clearJustRegistered();
        navigate("/rejected");
        return;
      }
      showToast("info", "Status refreshed. Your account is still awaiting approval.");
    } catch {
      navigate("/login", { replace: true, state: { notice: "Your session expired. Please sign in again." } });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PublicHeader />
      <main id="main" className="auth-shell">
        <div className="card auth-card panel">
          <AuthPageHeader
            kicker="CareerSense"
            title="Your account is under review"
            badge={<Badge tone="Pending">Pending approval</Badge>}
            lead="Your registration has been submitted successfully and is currently being reviewed by OAAPS."
          />
          <Alert type="error">{error ? friendlyError(error) : ""}</Alert>
          {user?.personal_email ? (
            <p className="status-email">
              Signed in as <strong>{user.personal_email}</strong>
            </p>
          ) : null}
          <StatusTimeline
            items={[
              { label: "Tracer information submitted", status: "done" },
              { label: "OAAPS review", status: "current" },
              { label: "Alumni portal access", status: "upcoming" },
            ]}
          />
          <p className="muted">This usually takes 1–3 working days. Your alumni dashboard is not available yet.</p>
          <div className="hero-actions">
            <button className="btn btn-navy" type="button" disabled={busy} onClick={checkStatus}>
              {busy ? "Checking…" : "Refresh status"}
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
              Sign out
            </button>
          </div>
        </div>
      </main>
      <PublicFooter />
    </>
  );
}
