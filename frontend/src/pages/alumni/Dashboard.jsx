import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { CoverPhotoControl, PhotoCropDialog, ProfilePhotoControl } from "../../components/ProfilePhotoEditor";
import {
  MailIcon,
  MapPinIcon,
  PencilIcon,
  PhoneIcon,
} from "../../components/icons";
import { JobTimeline } from "../../components/JobTimeline";
import { StudyTimeline } from "../../components/StudyTimeline";
import { PortalShell } from "../../components/Layout";
import { ProfileProgress } from "../../components/ProfileProgress";
import { Alert, Dialog, Field, LoadError, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { isStaleDate, officialEmploymentFromGts } from "../../lib/employmentDisplay";
import { formatLongDate, fullName } from "../../lib/format";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

const BIO_MAX = 800;

function requestedFieldLines(body) {
  return String(body || "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("•"))
    .map((line) => line.replace(/^•\s*/, ""));
}

function homeActionForLink(dest) {
  const target = dest || "/alumni";
  if (target.startsWith("/alumni/resume")) return { kind: "link", to: target };
  if (target.startsWith("/alumni/card")) return { kind: "link", to: target };
  if (target.startsWith("/alumni/account")) return { kind: "link", to: target };
  if (target.includes("work-history")) return { kind: "jobs" };
  if (target.includes("further-studies")) return { kind: "studies" };
  if (target === "/alumni" || target.startsWith("/alumni#")) return { kind: "edit" };
  return { kind: "link", to: target };
}

function attentionItem(data) {
  const card = data?.card || {};
  const updateNote = (data?.notifications || []).find((item) => item.category === "profile_update" && !item.read);
  if (updateNote) {
    const dest = updateNote.link || "/alumni";
    return {
      title: "Information requested",
      lead: "OAAPS has requested that you review and update the following information.",
      fields: requestedFieldLines(updateNote.body),
      cta: "Edit profile",
      to: dest,
      action: homeActionForLink(dest),
    };
  }
  if (card.status === "ReadyForPickup") {
    return {
      title: "Action required",
      lead: "Your Alumni Card application is ready for pickup at AAPS, AUF Main Campus.",
      cta: "Review",
      to: "/alumni/card",
      action: { kind: "link", to: "/alumni/card" },
    };
  }
  if (card.status === "ForRenewal") {
    return {
      title: "Action required",
      lead: card.next_action || "Submit a renewal application to keep your AAC current.",
      cta: "Renew card",
      to: "/alumni/card",
      action: { kind: "link", to: "/alumni/card" },
    };
  }
  const submittedAt = data?.latest_submission?.submitted_at;
  if (submittedAt && isStaleDate(submittedAt)) {
    return {
      title: "Keep your alumni record current",
      lead: `Your employment information was last updated more than a year ago (${formatLongDate(submittedAt)}).`,
      cta: "Update tracer",
      to: "/alumni/resume",
      action: { kind: "link", to: "/alumni/resume" },
    };
  }
  return null;
}

function careerLine(employment, occupation) {
  if (employment.answered && !employment.currentlyEmployed) {
    return { text: "Not currently employed", empty: false };
  }
  if (occupation) return { text: occupation, empty: false };
  return { text: "Career information not yet provided", empty: true };
}

function locationLines(profile) {
  const address = String(profile.address || "").trim();
  const city = String(profile.city || "").trim();
  const country = String(profile.country_residence || "").trim();
  const locality = [city, country].filter(Boolean).join(", ");
  return [address, locality].filter(Boolean);
}

const EMPTY_FORM = {
  country_residence: "",
  phone: "",
  city: "",
  address: "",
  husband_surname: "",
  bio: "",
};

export default function AlumniDashboard() {
  const location = useLocation();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [photoSrc, setPhotoSrc] = useState("");
  const [coverSrc, setCoverSrc] = useState("");
  const [photoNonce, setPhotoNonce] = useState(0);
  const [coverNonce, setCoverNonce] = useState(0);
  const [editOpen, setEditOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [cropFile, setCropFile] = useState(null);
  const [coverFile, setCoverFile] = useState(null);

  function loadDashboard() {
    setError("");
    return api("/api/alumni/dashboard").then(setData);
  }

  useEffect(() => {
    loadDashboard().catch((err) => setError(friendlyError(err, "We couldn't load your alumni profile. Please try again.")));
  }, []);

  useEffect(() => {
    if (!location.hash || !data) return;
    const id = location.hash.slice(1);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior = reduceMotion ? "auto" : "smooth";
    if (id === "contact" || id === "profile" || id === "about") {
      document.getElementById("profile")?.scrollIntoView({ behavior, block: "start" });
      return;
    }
    document.getElementById(id)?.scrollIntoView({ behavior, block: "start" });
  }, [location.hash, data]);

  useEffect(() => {
    if (!data?.profile?.has_photo) {
      setPhotoSrc("");
      return undefined;
    }
    let url = "";
    let cancelled = false;
    api("/api/alumni/profile/photo", { blob: true })
      .then((blob) => {
        if (cancelled || !(blob instanceof Blob)) return;
        url = URL.createObjectURL(blob);
        setPhotoSrc(url);
      })
      .catch(() => {
        if (!cancelled) setPhotoSrc("");
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [data?.profile?.has_photo, photoNonce]);

  useEffect(() => {
    if (!data?.profile?.has_cover) {
      setCoverSrc("");
      return undefined;
    }
    let url = "";
    let cancelled = false;
    api("/api/alumni/profile/cover", { blob: true })
      .then((blob) => {
        if (cancelled || !(blob instanceof Blob)) return;
        url = URL.createObjectURL(blob);
        setCoverSrc(url);
      })
      .catch(() => {
        if (!cancelled) setCoverSrc("");
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [data?.profile?.has_cover, coverNonce]);

  function openEdit() {
    const profile = data?.profile || {};
    setForm({
      country_residence: profile.country_residence || "",
      phone: profile.phone || "",
      city: profile.city || "",
      address: profile.address || "",
      husband_surname: profile.husband_surname || "",
      bio: profile.bio || "",
    });
    setError("");
    setEditOpen(true);
  }

  function openPhotoEditor(file) {
    setError("");
    setCropFile(file);
  }

  function openCoverEditor(file) {
    setError("");
    setCoverFile(file);
  }

  function applyPhotoResult(payload, message) {
    setData(payload);
    setPhotoNonce((value) => value + 1);
    showToast("success", message);
  }

  function applyCoverResult(payload, message) {
    setData(payload);
    setCoverNonce((value) => value + 1);
    showToast("success", message);
  }

  function handleAttention(action) {
    if (action?.kind === "edit") {
      openEdit();
      return;
    }
    if (action?.kind === "jobs") {
      document.getElementById("work-history")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (action?.kind === "studies") {
      document.getElementById("further-studies")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  async function saveProfile() {
    setBusy(true);
    setError("");
    try {
      const next = await api("/api/alumni/profile", { method: "PUT", body: form });
      setData(next);
      setEditOpen(false);
      showToast("success", "Your profile has been updated.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't save your profile. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  function retryCompletion() {
    api("/api/alumni/profile-completion")
      .then((payload) => setData((current) => (current ? { ...current, completion: payload } : current)))
      .catch(() => {});
  }

  if (!data && !error) {
    return (
      <PortalShell role="Alumni">
        <PageSkeleton variant="alumni" />
      </PortalShell>
    );
  }

  const profile = data?.profile || {};
  const account = data?.user || {};
  const jobs = data?.jobs || [];
  const studies = (data?.further_studies || []).filter((row) => row && (row.course_degree || row.school || row.id));
  const name = fullName(profile);
  const displayName = name === "—" ? "Alumni" : name;
  const latest = data?.latest_submission;
  const employment = officialEmploymentFromGts(latest?.data || {});
  const occupation = latest?.job_title || employment.occupation;
  const completion = data?.completion || null;
  const attention = data ? attentionItem(data) : null;
  const career = careerLine(employment, occupation);
  const bio = String(profile.bio || "").trim();
  const phone = String(profile.phone || "").trim();
  const email = String(account.email || "").trim();
  const places = locationLines(profile);
  const degreeLine = [profile.degree, profile.year_graduated ? `Batch ${profile.year_graduated}` : ""]
    .filter(Boolean)
    .join(" · ");
  const coverAlt = `${displayName} cover photo`;

  return (
    <PortalShell role="Alumni">
      <Alert type="error">{error && !editOpen && !cropFile && !coverFile ? error : null}</Alert>
      {!data && error ? (
        <LoadError title="We couldn't load your alumni information." onRetry={() => loadDashboard().catch((err) => setError(friendlyError(err)))}>
          Please try again.
        </LoadError>
      ) : null}

      {data && (
        <article className="alumni-profile">
          <header className="alumni-profile-hero" id="profile">
            <div className={`alumni-cover${coverSrc ? " has-image" : ""}`}>
              {coverSrc ? (
                <img src={coverSrc} alt={coverAlt} />
              ) : (
                <div className="alumni-cover-fallback" aria-hidden="true" />
              )}
            </div>
            <div className="alumni-profile-head">
              <div className="alumni-profile-identity">
                <ProfilePhotoControl
                  quiet
                  profile={profile}
                  src={photoSrc}
                  size="xl"
                  onFile={openPhotoEditor}
                  onInvalid={setError}
                  onRemoved={(payload) => applyPhotoResult(payload, "Profile photo removed.")}
                />
                <div className="alumni-profile-copy-top">
                  <div className="alumni-profile-titles">
                    <div className="alumni-profile-lead">
                      <h1>{displayName}</h1>
                      <p className={`alumni-identity-role${career.empty ? " is-empty" : ""}`}>{career.text}</p>
                    </div>
                    {degreeLine ? <p className="alumni-profile-degree">{degreeLine}</p> : null}
                  </div>
                  <button type="button" className="btn btn-outline alumni-profile-edit" onClick={openEdit}>
                    <PencilIcon size={16} />
                    Edit profile
                  </button>
                </div>
              </div>
              {bio ? (
                <p className="alumni-bio">{bio}</p>
              ) : (
                <p className="alumni-bio is-empty">Add a short professional bio to introduce yourself.</p>
              )}
              <section className="alumni-contact" id="contact" aria-label="Email, phone, and location">
                <dl>
                  <div>
                    <dt>
                      <MailIcon size={16} />
                      Email
                    </dt>
                    <dd>
                      {email || "No email on file"}
                      <span className="fact-hint">Official account email</span>
                    </dd>
                  </div>
                  <div>
                    <dt>
                      <PhoneIcon size={16} />
                      Phone
                    </dt>
                    <dd>{phone || "No phone number added"}</dd>
                  </div>
                  <div>
                    <dt>
                      <MapPinIcon size={16} />
                      Location
                    </dt>
                    <dd>
                      {places.length ? places.map((line) => <span key={line}>{line}</span>) : "No location added"}
                    </dd>
                  </div>
                </dl>
              </section>
            </div>
          </header>

          {attention ? (
            <section className="alumni-attention" aria-label="Action needed">
              <div>
                <p className="eyebrow">{attention.title === "Information requested" ? "Information requested" : "Action required"}</p>
                <h2>{attention.title === "Information requested" ? "Please update your record" : attention.title}</h2>
                <p className="lead">{attention.lead}</p>
                {attention.fields?.length ? (
                  <div className="alumni-attention-fields">
                    <p>OAAPS has requested that you update:</p>
                    <ul>
                      {attention.fields.map((field) => (
                        <li key={field}>{field}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
              {attention.action?.kind === "link" ? (
                <Link className="btn btn-navy" to={attention.to}>{attention.cta}</Link>
              ) : (
                <button type="button" className="btn btn-navy" onClick={() => handleAttention(attention.action)}>
                  {attention.cta}
                </button>
              )}
            </section>
          ) : null}

          <JobTimeline
            jobs={jobs}
            onJobsChange={(next) => {
              setData((current) => ({ ...current, jobs: next }));
              loadDashboard().catch(() => {});
            }}
          />

          <StudyTimeline
            studies={studies}
            onStudiesChange={(next) => {
              setData((current) => ({ ...current, further_studies: next }));
              loadDashboard().catch(() => {});
            }}
          />

          <ProfileProgress
            variant="full"
            completion={completion}
            state={completion ? "ready" : "error"}
            onEdit={openEdit}
            onPhoto={() => document.getElementById("profile")?.scrollIntoView({ behavior: "smooth", block: "start" })}
            onRetry={retryCompletion}
          />
        </article>
      )}

      {editOpen ? (
        <Dialog
          title="Edit profile"
          description="These details appear on your professional alumni profile. Official AUF registry information stays read-only."
          confirmLabel={busy ? "Saving…" : "Save profile"}
          busy={busy}
          wide
          onConfirm={saveProfile}
          onClose={() => { if (!busy) setEditOpen(false); }}
        >
          <Alert type="error">{error}</Alert>

          <fieldset className="profile-edit-group">
            <legend>Profile presentation</legend>
            <ProfilePhotoControl
              compact
              profile={profile}
              src={photoSrc}
              size="md"
              disabled={busy}
              onFile={openPhotoEditor}
              onInvalid={setError}
              onRemoved={(payload) => applyPhotoResult(payload, "Profile photo removed.")}
            />
            <div className="cover-edit-row">
              <p className="cover-edit-label">Cover photo</p>
              <CoverPhotoControl
                hasCover={Boolean(profile.has_cover)}
                disabled={busy}
                onFile={openCoverEditor}
                onUploaded={applyCoverResult}
                onInvalid={setError}
              />
              <p className="muted photo-guidance">JPG, PNG, or WebP · Maximum 5 MB. Displayed across the profile header.</p>
            </div>
            <Field label="Professional bio" hint={`${form.bio.length}/${BIO_MAX}`}>
              <textarea
                rows={5}
                value={form.bio}
                onChange={(e) => setForm({ ...form, bio: e.target.value })}
                maxLength={BIO_MAX}
                placeholder="Introduce your professional background in a few sentences."
              />
            </Field>
          </fieldset>

          <fieldset className="profile-edit-group">
            <legend>Official AUF record</legend>
            <p className="muted profile-edit-note">Controlled by the graduate registry. Contact AAPS if a correction is needed.</p>
            <dl className="alumni-facts profile-readonly">
              <div>
                <dt>Full name</dt>
                <dd>{displayName}</dd>
              </div>
              <div>
                <dt>Student number</dt>
                <dd>{account.student_id || "—"}</dd>
              </div>
              <div>
                <dt>Degree</dt>
                <dd>{profile.degree || "—"}</dd>
              </div>
              <div>
                <dt>College</dt>
                <dd>{profile.college || "—"}</dd>
              </div>
              <div>
                <dt>Graduation year</dt>
                <dd>{profile.year_graduated || "—"}</dd>
              </div>
              <div>
                <dt>Approval status</dt>
                <dd>{account.status || "—"}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{email || "—"}</dd>
              </div>
            </dl>
          </fieldset>

          <fieldset className="profile-edit-group">
            <legend>Contact and location</legend>
            <Field label="Phone">
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} maxLength={40} />
            </Field>
            <Field label="Address">
              <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} maxLength={240} />
            </Field>
            <div className="inline-fields">
              <Field label="City">
                <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} maxLength={120} />
              </Field>
              <Field label="Country of residence">
                <input value={form.country_residence} onChange={(e) => setForm({ ...form, country_residence: e.target.value })} maxLength={80} />
              </Field>
            </div>
            <Field label="Husband’s surname" hint="Optional. Used for official records when applicable.">
              <input value={form.husband_surname} onChange={(e) => setForm({ ...form, husband_surname: e.target.value })} maxLength={80} />
            </Field>
          </fieldset>
        </Dialog>
      ) : null}

      {coverFile ? (
        <PhotoCropDialog
          kind="cover"
          file={coverFile}
          onReplace={setCoverFile}
          onClose={() => setCoverFile(null)}
          onUploaded={(payload) => {
            applyCoverResult(payload, profile.has_cover ? "Cover photo updated." : "Cover photo added.");
            setCoverFile(null);
          }}
        />
      ) : null}
      {cropFile ? (
        <PhotoCropDialog
          file={cropFile}
          onClose={() => setCropFile(null)}
          onUploaded={(payload) => {
            applyPhotoResult(payload, "Profile photo updated successfully.");
            setCropFile(null);
          }}
        />
      ) : null}
    </PortalShell>
  );
}
