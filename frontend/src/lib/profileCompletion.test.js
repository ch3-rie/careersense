import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  achievementList,
  completionPercent,
  hasCompletionPayload,
  isProfileComplete,
  missingSections,
  nextAchievement,
  profileCompleteBadge,
} from "./profileCompletion.js";

describe("profileCompletion display helpers", () => {
  it("does not treat a missing payload as 0%", () => {
    assert.equal(hasCompletionPayload(null), false);
    assert.equal(completionPercent(null), null);
    assert.equal(isProfileComplete(null), false);
  });

  it("reads backend percent and complete flag without recalculating", () => {
    const payload = {
      percent: 90,
      percentage: 90,
      is_complete: false,
      missing_sections: [{ key: "photo", label: "Profile photo", route: "/alumni" }],
      badge: { key: "profile_complete", name: "Profile Complete", earned: false, awarded_at: null },
      achievements: [
        { key: "profile_complete", name: "Profile Complete", earned: false, awarded_at: null, route: "/alumni" },
        { key: "resume_ready", name: "Resume Ready", earned: false, awarded_at: null, route: "/alumni/resume" },
      ],
      earned_count: 0,
    };
    assert.equal(completionPercent(payload), 90);
    assert.equal(isProfileComplete(payload), false);
    assert.equal(missingSections(payload)[0].key, "photo");
    assert.equal(profileCompleteBadge(payload).earned, false);
    assert.equal(achievementList(payload).length, 2);
    assert.equal(nextAchievement(payload).route, "/alumni");
  });

  it("keeps an earned badge earned even if completion later drops", () => {
    const payload = {
      percent: 90,
      is_complete: false,
      missing_sections: [{ key: "photo", label: "Profile photo", route: "/alumni" }],
      achievements: [
        {
          key: "profile_complete",
          name: "Profile Complete",
          earned: true,
          awarded_at: "2026-09-15T00:00:00Z",
        },
      ],
      badge: {
        key: "profile_complete",
        name: "Profile Complete",
        earned: true,
        awarded_at: "2026-09-15T00:00:00Z",
      },
    };
    assert.equal(isProfileComplete(payload), false);
    assert.equal(profileCompleteBadge(payload).earned, true);
    assert.equal(achievementList(payload)[0].earned, true);
  });

  it("uses is_complete from the backend rather than inventing 100%", () => {
    const payload = { percent: 100, is_complete: false, missing_sections: [{ key: "employment" }] };
    assert.equal(isProfileComplete(payload), false);
  });
});
