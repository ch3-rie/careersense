# Alumni profile completion and Profile Complete badge

CareerSense treats profile completeness as an **alumni-records** concern, not a game. The backend is the only source of:

- completion percentage
- incomplete sections
- whether the profile is 100% complete
- Profile Complete badge status

The alumni portal displays those results. It does not recalculate percent in the browser.

The six-achievement catalog (Resume Ready, Tracer Completed, Career Updated, Alumni Card Holder, CareerSense Alumni, and Profile Complete) is documented in [achievements.md](achievements.md). Completion percent remains the input to `profile_complete`; it is not replaced by the badge grid.

## Where it lives

| Layer | Location |
| --- | --- |
| Calculation | `backend/app/services/profile_completion.py` |
| Achievement catalog and award | `backend/app/services/achievements.py` |
| Persistence | `alumni_badges` (`account_id` + `badge_key` unique) |
| Alumni APIs | `GET /api/alumni/dashboard`, `GET /api/alumni/profile`, `GET /api/alumni/profile-completion` (`GET /api/alumni/completion` is an alias), `GET /api/alumni/achievements` |
| UI | Alumni Home completion card + Achievements; Resume & Tracer compact status |

Admin profile-update search uses the same `profile_completion_percent()` helper.

## Weights (always 100%)

| Category | Weight | What counts as complete |
| --- | ---: | --- |
| Basic information | 10% | Given name and last name (registry values count when present) |
| Education | 15% | Bachelor’s degree and graduation year (registry values count when present) |
| Contact information | 20% | Phone, city, and country |
| Profile photo | 10% | A stored profile photo |
| Employment | 20% | Conditional official GTS employment answers |
| Further studies | 10% | Conditional official GTS further-studies answers |
| Graduate Tracer Survey | 15% | A submitted current GTS whose visible required questions are answered |

Resume parser output does **not** count. Information must be saved on the official GTS / alumni profile.

A resume file is optional and is not part of the score.

`is_complete` is true only when every applicable section is complete. If rounding would hit 100 while a section is still open, the percent is capped at 99.

## Conditional rules

### Employment

- No tracer yet → incomplete.
- `ever_employed = No` → complete. First-job and current-job fields are not required.
- `is_currently_employed = No` → current occupation and employer are not required.
- `is_currently_employed = Yes` → current occupation, employer, and degree-relatedness from `resolve_current_employment()`.

### Further studies

- `enroll_further_studies = No` → complete.
- `Yes` → at least one program with institution and course/degree.

### Tracer survey

Uses published-schema visibility and required-field rules (`required_answer_gaps`).

## Profile Complete badge

| Field | Value |
| --- | --- |
| Key | `profile_complete` |
| Name | Profile Complete |
| Requirement | `is_complete` (100% of applicable official information) |
| Persistence | Kept after the profile later drops below 100% |
| Notification | One in-app `achievement` notice on first award after a save. Opening Home does not re-notify. |

No points, XP, levels, leaderboards, streaks, or section badges.

Badge evaluation runs after profile, photo, GTS, and job saves. A badge failure is logged and does not roll back the alumni save.

## Security

- `require_active_alumni` on completion endpoints.
- Pending, rejected, admin, and anonymous callers receive 401/403.
- Alumni cannot award or edit the badge. Unique `(account_id, badge_key)` prevents duplicates.

## Frontend

Alumni Home shows a completion card, missing-section actions that reuse Update Information / Resume & Tracer, and a six-achievement grid with an accessible badge dialog. Do not add a second percent formula in React.
