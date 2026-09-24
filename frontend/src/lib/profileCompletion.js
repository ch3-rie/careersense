export function hasCompletionPayload(payload) {
  return Boolean(payload) && (payload.percent != null || payload.percentage != null);
}

export function completionPercent(payload) {
  if (!hasCompletionPayload(payload)) return null;
  const value = Number(payload.percent ?? payload.percentage);
  if (!Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function isProfileComplete(payload) {
  if (!hasCompletionPayload(payload)) return false;
  if (payload.is_complete === true) return true;
  if (payload.is_complete === false) return false;
  return completionPercent(payload) === 100 && !(payload.missing_sections || []).length;
}

export function missingSections(payload) {
  const listed = payload?.missing_sections;
  if (Array.isArray(listed) && listed.length) {
    return listed.map((row) => ({
      key: row.key || row.id,
      label: row.label,
      route: row.route || "/alumni",
      detail: row.detail || row.hint || "",
    }));
  }
  return (payload?.next_actions || []).map((row) => ({
    key: row.id || row.key,
    label: row.label,
    route: row.route || "/alumni",
    detail: row.detail || row.hint || "",
  }));
}

export function normalizeAchievement(row) {
  if (!row || !row.key) return null;
  const earned = row.earned === true || row.awarded === true;
  return {
    key: row.key,
    name: row.name || row.title || row.key,
    description: row.description || "",
    locked_description: row.locked_description || row.description || "",
    icon: row.icon || "check",
    category: row.category || "core",
    earned,
    awarded_at: row.awarded_at || null,
    route: row.route || "/alumni",
    cta: row.cta || "Continue",
    cta_edit: Boolean(row.cta_edit),
    metadata: row.metadata || null,
    detail: row.detail || row.metadata?.survey_label || "",
  };
}

export function achievementList(payload) {
  const listed = payload?.achievements;
  if (!Array.isArray(listed) || !listed.length) return [];
  return listed.map(normalizeAchievement).filter(Boolean);
}

export function earnedAchievementCount(payload) {
  if (payload?.earned_count != null && Number.isFinite(Number(payload.earned_count))) {
    return Number(payload.earned_count);
  }
  return achievementList(payload).filter((row) => row.earned).length;
}

export function profileCompleteBadge(payload) {
  const fromList = achievementList(payload).find((row) => row.key === "profile_complete" || row.key === "record_complete");
  if (fromList) return fromList;
  const badge = payload?.badge || (payload?.badges || []).find((row) => row.key === "profile_complete" || row.key === "record_complete");
  if (!badge) {
    return {
      key: "profile_complete",
      name: "Profile Complete",
      description: "All applicable alumni information has been completed.",
      locked_description: "Complete all applicable alumni information to earn this achievement.",
      icon: "check",
      category: "core",
      earned: false,
      awarded_at: null,
      route: "/alumni",
      cta: "Complete Profile",
      cta_edit: true,
      metadata: null,
      detail: "",
    };
  }
  return normalizeAchievement({
    ...badge,
    key: "profile_complete",
    name: badge.name || badge.title || "Profile Complete",
    description: badge.description || "All applicable alumni information has been completed.",
    locked_description: badge.locked_description || "Complete all applicable alumni information to earn this achievement.",
    icon: badge.icon || "check",
    route: badge.route || "/alumni",
    cta: badge.cta || "Complete Profile",
    cta_edit: true,
  });
}

export function nextAchievement(payload) {
  if (payload?.next_achievement) return payload.next_achievement;
  const locked = achievementList(payload).find((row) => !row.earned);
  if (!locked) {
    return {
      key: null,
      headline: "You're all set.",
      detail: "Your CareerSense alumni profile is complete.",
      route: "/alumni",
      cta: null,
    };
  }
  return {
    key: locked.key,
    headline: "You're almost there.",
    detail: locked.locked_description || locked.description,
    route: locked.route,
    cta: locked.cta,
    cta_edit: locked.cta_edit,
  };
}
