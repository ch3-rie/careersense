import { useEffect, useState } from "react";
import { PortalShell } from "../../components/Layout";
import { PageSkeleton, Alert } from "../../components/ui";
import { api } from "../../lib/api";
import { friendlyError } from "../../lib/userMessages";

const FIELDS = [
  ["student_number", "Student Number"],
  ["name", "Name"],
  ["course", "Course"],
  ["college", "College"],
  ["year_graduated", "Year Graduated"],
];

export default function AlumniQrPage() {
  const [identity, setIdentity] = useState(null);
  const [imageUrl, setImageUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/alumni/qr")
      .then((payload) => {
        if (!cancelled) setIdentity(payload);
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err, "We couldn't open your Alumni QR. Please try again."));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let url = "";
    let cancelled = false;
    api("/api/alumni/qr/image", { blob: true })
      .then((blob) => {
        if (cancelled || !(blob instanceof Blob)) return;
        url = URL.createObjectURL(blob);
        setImageUrl(url);
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err, "We couldn't prepare your QR code. Please try again."));
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, []);

  if (!identity && !error) {
    return <PortalShell role="Alumni"><PageSkeleton variant="alumni" /></PortalShell>;
  }

  return (
    <PortalShell role="Alumni">
      <div className="alumni-qr">
        <Alert type="error">{error}</Alert>
        <section className="alumni-qr-sheet" aria-label="Alumni QR">
          <div className="alumni-qr-code">
            {imageUrl ? <img src={imageUrl} alt="Your Alumni QR code" /> : <p className="muted">Preparing your QR code…</p>}
          </div>
          <dl className="alumni-qr-facts">
            {FIELDS.map(([key, label]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{String(identity?.[key] || "").trim() || "—"}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </PortalShell>
  );
}
