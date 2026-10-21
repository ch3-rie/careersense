import { useState } from "react";
import { Link } from "react-router-dom";
import { CompletionRing } from "./AlumniChrome";
import {
  BriefcaseIcon,
  CheckIcon,
  ClipboardListIcon,
  CreditCardIcon,
  FileTextIcon,
  LockIcon,
  StarIcon,
} from "./icons";
import { Dialog, SectionTitle } from "./ui";
import { formatLongDate } from "../lib/format";
import {
  achievementList,
  completionPercent,
  earnedAchievementCount,
  hasCompletionPayload,
  isProfileComplete,
  missingSections,
  nextAchievement,
  profileCompleteBadge,
} from "../lib/profileCompletion";

function badgeRequirement(item) {
  if (!item) return "";
  if (item.earned) return item.description || "";
  if (item.key === "profile_complete") return "Complete the remaining profile sections.";
  return item.locked_description || item.description || "";
}

function AchievementIcon({ name, size = 22 }) {
  if (name === "file") return <FileTextIcon size={size} />;
  if (name === "clipboard") return <ClipboardListIcon size={size} />;
  if (name === "briefcase") return <BriefcaseIcon size={size} />;
  if (name === "id-card") return <CreditCardIcon size={size} />;
  if (name === "star") return <StarIcon size={size} />;
  return <CheckIcon size={size} />;
}

function actionControl(section, onEdit, onPhoto, label, buttonClass) {
  if (!section) return null;
  const classes = buttonClass || ((section.key === "photo" || section.cta_photo) ? "btn btn-outline btn-sm" : "btn btn-navy btn-sm");
  if (section.key === "photo" || section.cta_photo) {
    return (
      <button type="button" className={classes} onClick={onPhoto}>
        {label || "Add profile photo"}
      </button>
    );
  }
  if ((section.key === "contact" || section.cta_edit || section.route === "/alumni") && onEdit) {
    return (
      <button type="button" className={buttonClass || "btn btn-navy btn-sm"} onClick={onEdit}>
        {label || "Edit profile"}
      </button>
    );
  }
  const text =
    label ||
    (section.key === "employment"
      ? "Update employment"
      : section.key === "tracer"
        ? "Update tracer survey"
        : section.key === "further_studies"
          ? "Update further studies"
          : section.key === "alumni_card_holder"
            ? "Open Alumni Card"
            : section.cta || `Update ${String(section.label || "profile").toLowerCase()}`);
  if (section.route?.includes("#")) {
    return (
      <Link className={buttonClass || "btn btn-navy btn-sm"} to={section.route}>
        {text}
      </Link>
    );
  }
  if (section.route && !section.route.startsWith("/alumni#") && section.route !== "/alumni") {
    return (
      <Link className={buttonClass || "btn btn-navy btn-sm"} to={section.route}>
        {text}
      </Link>
    );
  }
  if (onEdit) {
    return (
      <button type="button" className={buttonClass || "btn btn-navy btn-sm"} onClick={onEdit}>
        {text}
      </button>
    );
  }
  return (
    <Link className={buttonClass || "btn btn-navy btn-sm"} to={section.route || "/alumni"}>
      {text}
    </Link>
  );
}

function BadgeHubShell({ count, busy, children }) {
  return (
    <section
      className="alumni-block badge-hub"
      id="alumni-badges"
      aria-label="Alumni Badge Achievements"
      aria-busy={busy ? "true" : undefined}
    >
      <header className="profile-section-head">
        <SectionTitle
          title="Alumni Badge Achievements"
          lead="Official milestones from your alumni record. Earned badges stay earned."
        />
        {count ? <p className="alumni-section-meta">{count}</p> : null}
      </header>
      {children}
    </section>
  );
}

function recordGridClass(compact, showCompletion, showBadges) {
  return [
    "alumni-record-grid",
    compact ? "is-compact" : "",
    showCompletion && showBadges ? "is-split" : "",
    showBadges && !showCompletion ? "has-achievements" : "",
  ].filter(Boolean).join(" ");
}

function modalAction(item, firstMissing, onEdit, onPhoto, onClose) {
  if (item.earned) return null;
  if (item.key === "profile_complete") {
    return actionControl(firstMissing || { key: "contact", cta_edit: true, route: "/alumni" }, () => {
      onClose();
      onEdit?.();
    }, () => {
      onClose();
      onPhoto?.();
    }, item.cta || "Complete Profile");
  }
  if (item.cta_edit || item.route === "/alumni") {
    return actionControl({ ...item, cta_edit: true }, () => {
      onClose();
      onEdit?.();
    }, () => {
      onClose();
      onPhoto?.();
    }, item.cta);
  }
  return (
    <Link className="btn btn-navy" to={item.route || "/alumni"} onClick={onClose}>
      {item.cta || "Continue"}
    </Link>
  );
}

export function ProfileProgress({
  completion,
  state = "ready",
  compact = false,
  showAchievements = false,
  variant = "auto",
  onEdit,
  onRetry,
  onPhoto,
}) {
  const [openKey, setOpenKey] = useState(null);
  const loading = state === "loading";
  const failed = state === "error" || (state === "ready" && !hasCompletionPayload(completion));
  const mode = variant === "auto" ? (showAchievements ? "full" : "completion") : variant;
  const showCompletion = mode === "full" || mode === "completion";
  const showBadges = mode === "full" || mode === "achievements";

  if (failed) {
    if (!showCompletion && !showBadges) return null;
    if (!compact && showBadges) {
      return (
        <BadgeHubShell>
          <p className="muted">Alumni badge achievements are temporarily unavailable.</p>
          {onRetry ? (
            <button type="button" className="btn btn-navy btn-sm" onClick={onRetry}>
              Try Again
            </button>
          ) : null}
        </BadgeHubShell>
      );
    }
    return (
      <section className="alumni-complete alumni-progress-error" aria-label="Profile Completion">
        {compact ? (
          <p className="alumni-complete-title">Profile completion</p>
        ) : (
          <header className="profile-section-head">
            <div>
              <h2>Profile Completion</h2>
            </div>
          </header>
        )}
        <p className="muted">Profile completion is temporarily unavailable.</p>
        {onRetry ? (
          <button type="button" className="btn btn-navy btn-sm" onClick={onRetry}>
            Try Again
          </button>
        ) : null}
      </section>
    );
  }

  if (loading) {
    if (!compact && showBadges) {
      return (
        <BadgeHubShell busy>
          <p className="muted">Loading alumni badge achievements…</p>
          <div className="badge-hub-grid" aria-hidden="true">
            {Array.from({ length: 6 }, (_, index) => (
              <div key={index} className="badge-hub-card is-locked">
                <span className="badge-hub-card-top">
                  <span className="achievement-seal" />
                  <span className="badge-hub-status">Not earned</span>
                </span>
                <strong>Loading</strong>
                <span>Please wait</span>
              </div>
            ))}
          </div>
        </BadgeHubShell>
      );
    }
    return (
      <div className={recordGridClass(compact, showCompletion, showBadges)}>
        {showCompletion ? (
          <section className={`alumni-complete${compact ? " is-compact" : " is-ring"}`} aria-label="Profile Completion">
            {compact ? null : (
              <header className="profile-section-head">
                <div>
                  <h2>Profile Completion</h2>
                </div>
              </header>
            )}
            <div className={`alumni-complete-ring-layout${compact ? " is-compact" : ""}`}>
              <CompletionRing loading size={compact ? 88 : 152} />
              <div className="alumni-complete-ring-copy">
                {compact ? <p className="alumni-complete-title">Profile completion</p> : null}
                <p className="muted">Loading your record status…</p>
              </div>
            </div>
          </section>
        ) : null}
        {showBadges ? (
          <section className="alumni-achievement-card" aria-label="Alumni Badge Achievements">
            {compact ? (
              <p className="eyebrow">Alumni Badge Achievements</p>
            ) : (
              <header className="profile-section-head">
                <div>
                  <h2>Alumni Badge Achievements</h2>
                </div>
              </header>
            )}
            <p className="muted">Loading alumni badge achievements…</p>
            <div className="alumni-achievement-grid" aria-hidden="true">
              {Array.from({ length: compact ? 6 : 4 }, (_, index) => (
                <div key={index} className={`alumni-achievement is-loading${compact ? "" : " is-row"}`}>
                  <span className="achievement-seal" />
                  <span className="alumni-achievement-copy">
                    <strong>Loading</strong>
                    <span className="muted">Please wait</span>
                  </span>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    );
  }

  const percent = completionPercent(completion);
  const complete = isProfileComplete(completion);
  const missing = missingSections(completion);
  const badge = profileCompleteBadge(completion);
  const achievements = achievementList(completion);
  const earnedCount = earnedAchievementCount(completion);
  const next = nextAchievement(completion);
  const openItem = achievements.find((row) => row.key === openKey) || (openKey === badge.key ? badge : null);
  const message = complete
    ? completion.message || "All applicable alumni information has been completed."
    : percent >= 70
      ? "You're almost there. Complete the remaining information to keep your alumni record accurate and up to date."
      : completion.message || "Complete the remaining information to keep your alumni record accurate and up to date.";
  const firstMissing = missing[0];
  const statusLabel = complete ? "Profile complete" : percent >= 70 ? "Almost complete" : "In progress";
  const summary = complete
    ? completion.message || "All applicable alumni information has been completed."
    : missing.length
      ? "Finish the sections below to keep your alumni record current."
      : completion.message || "Complete the remaining information to keep your alumni record current.";
  const dialog = openItem ? (
    <Dialog
      title={openItem.name}
      compact
      hideActions
      footer={
        openItem.earned ? (
          <button type="button" className="btn btn-navy" onClick={() => setOpenKey(null)}>
            Close
          </button>
        ) : (
          <>
            {modalAction(openItem, firstMissing, onEdit, onPhoto, () => setOpenKey(null))}
            <button type="button" className="btn btn-outline" onClick={() => setOpenKey(null)}>
              Close
            </button>
          </>
        )
      }
      onClose={() => setOpenKey(null)}
    >
      <div className="alumni-badge-dialog">
        <span className={`achievement-seal achievement-seal-lg${openItem.earned ? " is-earned" : ""}`} aria-hidden="true">
          {openItem.earned ? <AchievementIcon name={openItem.icon} size={28} /> : <LockIcon size={24} />}
        </span>
        <p className="eyebrow">{openItem.earned ? "Earned" : "To earn this badge"}</p>
        <p>{openItem.earned ? openItem.description : badgeRequirement(openItem)}</p>
        {openItem.earned && openItem.awarded_at ? <p className="muted">{formatLongDate(openItem.awarded_at)}</p> : null}
        {openItem.earned && openItem.detail ? <p className="muted">{openItem.detail}</p> : null}
      </div>
    </Dialog>
  ) : null;

  if (!compact) {
    const countLabel = achievements.length
      ? `${earnedCount} of ${achievements.length} earned`
      : "Temporarily unavailable";
    return (
      <>
        <BadgeHubShell count={countLabel}>
          <div className="badge-hub-progress">
            <CompletionRing percent={percent} complete={complete} size={96} />
            <div className="badge-hub-progress-copy">
              <p className="badge-hub-status-line">
                <strong>{statusLabel}</strong>
              </p>
              <p className="muted">{summary}</p>
            </div>
          </div>

          {!complete && missing.length ? (
            <div className="badge-hub-needed">
              <p id="badge-still-needed">Still needed</p>
              <ul aria-labelledby="badge-still-needed">
                {missing.map((section) => (
                  <li key={section.key || section.label}>
                    <span>
                      <strong>{section.label || "Additional information"}</strong>
                      {section.detail && section.detail !== section.label ? <span>{section.detail}</span> : null}
                    </span>
                    {actionControl(section, onEdit, onPhoto, undefined, "btn btn-outline btn-sm")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {achievements.length ? (
            <div className="badge-hub-grid">
              {achievements.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`badge-hub-card${item.earned ? " is-earned" : " is-locked"}`}
                  onClick={() => setOpenKey(item.key)}
                  aria-label={
                    item.earned
                      ? `${item.name}, earned ${item.awarded_at ? formatLongDate(item.awarded_at) : ""}`.trim()
                      : `${item.name}, not earned. ${badgeRequirement(item)}`
                  }
                >
                  <span className="badge-hub-card-top">
                    <span className={`achievement-seal${item.earned ? " is-earned" : ""}`} aria-hidden="true">
                      <AchievementIcon name={item.icon} size={18} />
                      {item.earned ? null : <span className="achievement-lock"><LockIcon size={12} /></span>}
                    </span>
                    <span className="badge-hub-status">{item.earned ? "Earned" : "Not earned"}</span>
                  </span>
                  <strong>{item.name}</strong>
                  <span className="badge-hub-req">{badgeRequirement(item)}</span>
                  {item.earned && item.awarded_at ? <span className="badge-hub-date">{formatLongDate(item.awarded_at)}</span> : null}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">Alumni badge achievements could not be loaded.</p>
          )}
        </BadgeHubShell>
        {dialog}
      </>
    );
  }

  return (
    <div className={recordGridClass(compact, showCompletion, showBadges)}>
      {showCompletion ? (
        <section className={`alumni-complete${compact ? " is-compact" : " is-ring"}`} aria-label="Profile Completion" id={compact ? undefined : "profile-completion"}>
          {compact ? null : (
            <header className="profile-section-head">
              <div>
                <h2>Profile Completion</h2>
              </div>
            </header>
          )}
          <div className={`alumni-complete-ring-layout${compact ? " is-compact" : ""}`}>
            <CompletionRing percent={percent} complete={complete} size={compact ? 88 : 152} />
            <div className="alumni-complete-ring-copy">
              {compact ? (
                <p className="alumni-complete-title">{complete ? "Profile complete" : "Profile completion"}</p>
              ) : null}
              {message ? <p className={compact ? "muted" : "alumni-section-lead"}>{message}</p> : null}
              {!compact && !complete && missing.length ? (
                <ul className="alumni-complete-gaps">
                  {missing.map((section) => (
                    <li key={section.key || section.label}>{section.label || "Additional information"}</li>
                  ))}
                </ul>
              ) : null}
              {!compact && complete ? (
                <p className="alumni-complete-done-row">
                  <span className="job-now">Complete</span>
                  <span className="muted">
                    {badge.earned
                      ? `Earned ${formatLongDate(badge.awarded_at)}`
                      : "All applicable alumni information has been completed."}
                  </span>
                </p>
              ) : null}
              {compact ? (
                <div className="alumni-progress-actions">
                  {complete ? (
                    showBadges && mode === "full" ? (
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpenKey(badge.key)}>
                        View badge
                      </button>
                    ) : null
                  ) : (
                    actionControl(firstMissing, onEdit, onPhoto, "Complete Profile")
                  )}
                </div>
              ) : (
                <div className="alumni-progress-actions">
                  {complete ? (
                    showBadges && mode === "full" ? (
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpenKey(badge.key)}>
                        View badge
                      </button>
                    ) : null
                  ) : (
                    actionControl(firstMissing, onEdit, onPhoto, "Complete profile", "btn btn-navy btn-sm")
                  )}
                </div>
              )}
            </div>
          </div>
        </section>
      ) : null}

      {showBadges ? (
        <section className="alumni-achievement-card" aria-label="Alumni Badge Achievements" id="alumni-badges">
          {compact ? (
            <div className="alumni-achievement-head">
              <h2 className="alumni-subhead">Alumni Badge Achievements</h2>
              <p className="alumni-achievement-count">
                {achievements.length
                  ? `${earnedCount} of ${achievements.length} earned`
                  : "Alumni badge achievements are temporarily unavailable."}
              </p>
            </div>
          ) : (
            <header className="profile-section-head">
              <div>
                <h2>Alumni Badge Achievements</h2>
              </div>
              <p className="alumni-section-meta">
                {achievements.length
                  ? `${earnedCount} of ${achievements.length} earned`
                  : "Temporarily unavailable"}
              </p>
            </header>
          )}
          {compact ? null : (
            <p className="alumni-section-lead">
              These badges are earned from your profile completion. Finish the remaining sections in the completion panel to unlock a locked badge. Each locked badge lists what is still required.
            </p>
          )}
          {next && !complete ? (
            <p className="alumni-section-lead">
              {next.headline}
              {next.detail ? ` ${next.detail}` : ""}
            </p>
          ) : null}
          {achievements.length ? (
            <div className="alumni-achievement-grid">
              {achievements.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`alumni-achievement${item.earned ? " is-earned" : " is-locked"}${compact ? "" : " is-row"}`}
                  onClick={() => setOpenKey(item.key)}
                  aria-label={
                    item.earned
                      ? `${item.name}, earned ${item.awarded_at ? formatLongDate(item.awarded_at) : ""}`.trim()
                      : `${item.name}, locked. ${item.locked_description || item.description}`
                  }
                >
                  <span className={`achievement-seal${item.earned ? " is-earned" : ""}`} aria-hidden="true">
                    <AchievementIcon name={item.icon} size={compact ? 22 : 18} />
                    {item.earned ? null : <span className="achievement-lock"><LockIcon size={12} /></span>}
                  </span>
                  <span className="alumni-achievement-copy">
                    <strong>{item.name}</strong>
                    <span className="muted">
                      {item.earned
                        ? `Earned ${formatLongDate(item.awarded_at)}`
                        : item.locked_description || "Locked"}
                    </span>
                  </span>
                  {compact ? null : item.earned ? <span className="job-now">Earned</span> : null}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">Alumni badge achievements could not be loaded.</p>
          )}
        </section>
      ) : null}

      {dialog}
    </div>
  );
}
