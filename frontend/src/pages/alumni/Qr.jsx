import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PortalShell } from "../../components/Layout";
import { Dialog } from "../../components/ui";
import { api } from "../../lib/api";

const FIELDS = [
  ["student_number", "Student Number", "is-student"],
  ["name", "Full Name", "is-name"],
  ["course", "Course", "is-course"],
  ["college", "College", "is-college"],
  ["year_graduated", "Year Graduated", "is-year"],
];

function shown(value) {
  const text = String(value ?? "").trim();
  return text || "—";
}

function AlumniQrSkeleton() {
  return (
    <div className="alumni-qr-sheet is-skeleton" aria-hidden="true">
      <div className="alumni-qr-code">
        <div className="alumni-qr-frame">
          <div className="skeleton alumni-qr-code-skel" />
        </div>
        <div className="skeleton alumni-qr-skel-line is-label" />
        <div className="skeleton alumni-qr-skel-line is-hint" />
      </div>
      <dl className="alumni-qr-facts">
        {FIELDS.map(([key, , placement]) => (
          <div key={key} className={placement}>
            <div className="skeleton alumni-qr-skel-line is-dt" />
            <div className="skeleton alumni-qr-skel-line is-dd" />
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function AlumniQrPage() {
  const navigate = useNavigate();
  const [identity, setIdentity] = useState(null);
  const [imageUrl, setImageUrl] = useState("");
  const [phase, setPhase] = useState("confirm");
  const [attempt, setAttempt] = useState(0);
  const imageUrlRef = useRef("");

  useEffect(() => {
    if (phase !== "loading") return undefined;
    let cancelled = false;
    setIdentity(null);
    setImageUrl("");

    Promise.all([
      api("/api/alumni/qr", { toast: false }),
      api("/api/alumni/qr/image", { blob: true, toast: false }),
    ])
      .then(([payload, blob]) => {
        if (cancelled) return;
        if (!payload || typeof payload !== "object" || !(blob instanceof Blob) || blob.size === 0) {
          setPhase("error");
          return;
        }
        if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
        const url = URL.createObjectURL(blob);
        imageUrlRef.current = url;
        setIdentity(payload);
        setImageUrl(url);
        setPhase("ready");
      })
      .catch(() => {
        if (!cancelled) setPhase("error");
      });

    return () => {
      cancelled = true;
    };
  }, [attempt, phase]);

  function proceed() {
    setPhase("loading");
  }

  function leave() {
    const index = window.history.state?.idx;
    if (typeof index === "number" && index > 0) {
      navigate(-1);
      return;
    }
    navigate("/alumni", { replace: true });
  }

  useEffect(() => () => {
    if (imageUrlRef.current) {
      URL.revokeObjectURL(imageUrlRef.current);
      imageUrlRef.current = "";
    }
  }, []);

  function retry() {
    setPhase("loading");
    setIdentity(null);
    setImageUrl("");
    setAttempt((value) => value + 1);
  }

  return (
    <PortalShell role="Alumni">
      {phase === "confirm" ? (
        <Dialog title="Confirm QR Code Display" confirmLabel="Proceed" onConfirm={proceed} onClose={leave}>
          <p>Show this code only when you are at an AUF partner and ready to record your visit.</p>
          <p>Before you continue, make sure no one else can see your screen. Do not display the code if someone could photograph it, or if you are sharing or recording your screen.</p>
        </Dialog>
      ) : null}
      {phase === "confirm" ? null : (
        <div className="alumni-qr">
        {phase === "loading" ? (
          <>
            <p className="sr-only" role="status">Loading your Alumni QR card.</p>
            <AlumniQrSkeleton />
          </>
        ) : null}

        {phase === "error" ? (
          <section className="alumni-qr-error" role="alert">
            <h2>Unable to load your Alumni QR card.</h2>
            <p>Please try again.</p>
            <button type="button" className="btn btn-navy" onClick={retry}>Retry</button>
          </section>
        ) : null}

        {phase === "ready" ? (
          <section className="alumni-qr-sheet" aria-label="Alumni QR">
            <div className="alumni-qr-code">
              <div className="alumni-qr-frame">
                <img src={imageUrl} alt="QR code for recording alumni card visits at AUF partners" />
              </div>
              <p className="alumni-qr-scan">Scan at Partners</p>
              <p className="alumni-qr-hint">Scan this code at AUF partner places and restaurants to record where your alumni card was used.</p>
            </div>
            <dl className="alumni-qr-facts">
              {FIELDS.map(([key, label, placement]) => (
                <div key={key} className={placement}>
                  <dt>{label}</dt>
                  <dd>{shown(identity?.[key])}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}
      </div>
      )}
    </PortalShell>
  );
}
