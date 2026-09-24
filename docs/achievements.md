# CareerSense alumni achievements

Achievements recognize meaningful CareerSense milestones. They are **not** a game: there are no points, XP, levels, leaderboards, streaks, coins, or rewards.

Profile completion still answers “how complete is my record?” Achievements answer “which official milestones have I already earned?”

## Catalog

Definitions live in `backend/app/services/achievements.py`.

| Key | Name | Requirement |
| --- | --- | --- |
| `profile_complete` | Profile Complete | Authoritative completion is exactly 100% (`is_complete`) |
| `resume_ready` | Resume Ready | Owned resume with usable extraction is attached to a successfully submitted GTS (`resume_id` + `tracer_required_ok`). Upload or parser output alone is not enough. |
| `tracer_completed` | Tracer Completed | Current published GTS submitted with all applicable required fields (`required_answer_gaps`) |
| `career_updated` | Career Updated | Currently employed, with occupation, employer, and relatedness from `resolve_current_employment()`. Unemployed or old jobs only do not qualify. |
| `alumni_card_holder` | Alumni Card Holder | Canonical AAC status is `Claimed` only |
| `careersense_alumni` | CareerSense Alumni | The five core achievements above are earned |

Optional later keys (`lifelong_learner`, `perks_explorer`, `tracer_updated`) can be added to the catalog without changing persistence.

## Persistence

Table: `alumni_badges`

- Unique `(account_id, badge_key)`
- Optional `award_metadata` (tracer cycle label/version)
- Earned badges are never revoked if the record later becomes incomplete

## Evaluation

`AchievementService.evaluate_all()` reads one field snapshot plus the completion result. It is called from `refresh_alumni_progress()`.

Triggers (notify on first award):

- `PUT /api/alumni/profile`
- `POST /api/alumni/profile/photo`
- `POST /api/alumni/gts` (Active alumni)
- job timeline create/update/delete
- AAC application (`ForVerification` does not award Card Holder)
- `set_alumni_card_status(..., Claimed)` (OAAPS hook)

`GET /api/alumni/dashboard`, `/profile-completion`, `/achievements`, and `/card` backfill missing badges **without** creating notifications.

Achievement failures are logged and do not roll back the alumni save.

## API

`GET /api/alumni/achievements` — Active alumni only. Returns the caller’s catalog with earned/locked state. There is no POST; alumni cannot award badges.

The same `achievements` list is included on dashboard and profile-completion payloads.

## Notifications

One in-app `alumni_notifications` row per achievement:

- Title: `Achievement unlocked`
- Body: `You earned the {name} badge.` plus the catalog description
- Category: `achievement`
- Link: `/alumni#achievement-{key}`

## Frontend

Alumni Home (`/alumni`) shows the completion card and a six-badge grid with an accessible detail dialog. Resume & Tracer keeps the compact completion bar only.
