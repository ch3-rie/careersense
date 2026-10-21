import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { PublicFooter, PublicHeader } from "../../components/Layout";
import { Alert } from "../../components/ui";
import { api } from "../../lib/api";
import { friendlyError } from "../../lib/userMessages";

const FIELDS = [
  ["student_number", "Student Number"],
  ["name", "Name"],
  ["course", "Course"],
  ["college", "College"],
  ["year_graduated", "Year Graduated"],
];

export default function VerifyQrPage() {
  const { token } = useParams();
  const [identity, setIdentity] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api(`/api/public/alumni-qr/${encodeURIComponent(token || "")}`, { toast: false })
      .then((payload) => {
        if (!cancelled) setIdentity(payload);
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err, "This QR code could not be verified."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <>
      <PublicHeader />
      <main id="main" className="auth-shell">
        <section className="card alumni-qr-verify" aria-label="Alumni QR verification">
          <p className="eyebrow">CareerSense</p>
          <h1>Alumni QR</h1>
          {loading ? <p className="muted">Checking this QR code…</p> : null}
          <Alert type="error">{error}</Alert>
          {identity ? (
            <dl className="alumni-qr-facts">
              {FIELDS.map(([key, label]) => (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>{String(identity[key] || "").trim() || "—"}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
