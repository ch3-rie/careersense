import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthPageHeader } from "../../components/AuthFlow";
import { PublicFooter, PublicHeader } from "../../components/Layout";
import { Badge } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { clearJustRegistered } from "../../lib/registerSession";

export default function RejectedPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [contact, setContact] = useState(null);

  useEffect(() => {
    api("/api/auth/options")
      .then((opts) => setContact(opts.office_contact || null))
      .catch(() => setContact(null));
  }, []);

  const office = contact?.name || "Office of Alumni Affairs and Placement Services";

  return (
    <>
      <PublicHeader />
      <main id="main" className="auth-shell">
        <div className="card auth-card panel">
          <AuthPageHeader
            kicker="CareerSense"
            title="Registration requires attention"
            badge={<Badge tone="Rejected">Registration not approved</Badge>}
            lead="Your registration was not approved."
          />
          {user?.rejection_reason ? (
            <blockquote className="quote">{user.rejection_reason}</blockquote>
          ) : (
            <p className="muted">No additional reason was recorded. OAAPS can provide details in person or by email.</p>
          )}
          <p>This email cannot be used to start a new registration. Please contact the Alumni Office if you need help.</p>
          <div className="form-section" style={{ marginTop: 16 }}>
            <h3>{office}</h3>
            {contact?.location ? <p>{contact.location}</p> : <p>Angeles University Foundation</p>}
            {contact?.email ? (
              <p><a href={`mailto:${contact.email}`}>{contact.email}</a></p>
            ) : (
              <p className="muted">Visit the office on campus for assistance.</p>
            )}
            {contact?.phone ? <p>{contact.phone}</p> : null}
            {contact?.hours ? <p className="muted">{contact.hours}</p> : null}
          </div>
          <div className="hero-actions">
            <button
              className="btn btn-navy"
              type="button"
              onClick={() => {
                clearJustRegistered();
                logout();
                navigate("/login");
              }}
            >
              Sign in
            </button>
          </div>
        </div>
      </main>
      <PublicFooter />
    </>
  );
}
