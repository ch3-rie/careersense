import { useEffect, useState } from "react";
import { Alert, SectionTitle } from "./ui";
import { api } from "../lib/api";
import { showToast } from "../lib/toasts";
import { friendlyError } from "../lib/userMessages";

const ROLES = [
  {
    id: "speaker",
    label: "Speaker",
    detail: "Interested in sharing professional knowledge, career experiences, or expertise.",
  },
  {
    id: "mentor",
    label: "Mentor",
    detail: "Interested in guiding students or fellow alumni through professional or career development.",
  },
  {
    id: "sponsor",
    label: "Sponsor",
    detail: "Interested in supporting university activities, programs, or initiatives.",
  },
];

function selectedRoles(participation) {
  return ROLES.map((role) => role.id).filter((id) => Boolean(participation?.[id]));
}

function sameRoles(left, right) {
  return left.length === right.length && left.every((role, index) => role === right[index]);
}

export function ParticipationInterest({ participation, onSaved }) {
  const saved = selectedRoles(participation);
  const [roles, setRoles] = useState(saved);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dirty = !sameRoles(roles, saved);

  useEffect(() => {
    setRoles(selectedRoles(participation));
  }, [participation]);

  function toggle(id) {
    setRoles((current) => (current.includes(id) ? current.filter((role) => role !== id) : [...current, id]));
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      const next = await api("/api/alumni/participation", {
        method: "PUT",
        body: { roles },
      });
      onSaved?.(next);
      showToast("success", roles.length ? "Participation interests saved." : "Participation interests cleared.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't save your participation interests. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="alumni-block" id="participation" aria-label="University participation">
      <header className="profile-section-head">
        <SectionTitle
          title="University participation"
          lead="Tell AUF if you are interested in taking part as a speaker, mentor, or sponsor. This does not sign you up for an activity."
        />
      </header>
      <Alert type="error">{error}</Alert>
      <div className="participation-choices">
        {ROLES.map((role) => {
          const checked = roles.includes(role.id);
          return (
            <label key={role.id} className={`participation-choice${checked ? " is-selected" : ""}`}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(role.id)}
                disabled={busy}
              />
              <span>
                <strong>{role.label}</strong>
                <span>{role.detail}</span>
              </span>
            </label>
          );
        })}
      </div>
      <div className="panel-actions">
        <button type="button" className="btn btn-navy btn-sm" onClick={save} disabled={busy || !dirty}>
          {busy ? "Saving…" : "Save interests"}
        </button>
      </div>
    </section>
  );
}
