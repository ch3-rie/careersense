# Pre-Render checklist

## A. Overall status

READY WITH WARNINGS

Nothing was deployed. Docker is not installed on this machine, so the production image and in-container Tesseract were not executed. PostgreSQL startup, schema creation, and the automated suite were executed.

## B. Tests performed

| Area | Status | Details |
| --- | --- | --- |
| Frontend build | PASS | `npm run build` succeeded earlier in this deployment pass (`frontend/dist`). Frontend source has no `localhost` or `:8000`. The dev proxy in `vite.config.js` is development-only. |
| Backend startup | PASS | Uvicorn bound `0.0.0.0:8011` using `PORT`. `GET /health` returned `{"status":"ok"}`. `GET /api/health` returned 200. |
| Docker build | FAIL | `docker` is not installed here. `backend/Dockerfile` was not built. |
| Docker startup | FAIL | No image to run. |
| PostgreSQL | PASS | Connected with `postgresql+psycopg` to a new schema `prerender_check` on the local Postgres server. No SQLite fallback. Schema dropped after the test. |
| Database initialization | PASS | Empty schema: `create_all`, then Alembic upgrades `0001` through `0006_email_reminders`. 31 tables including accounts, tracer submissions, survey definitions, perks, and `alembic_version`. |
| Authentication | PASS | 269 backend tests passed, including login, registration, pending/rejected/active rules, password hashing, and protected routes. Passwords stored as bcrypt (`$2`). |
| Resume PDF | PASS | Covered by `tests/test_parser.py` and `tests/test_parser_quality.py` in the 269 passing tests. |
| Resume DOCX | PASS | Same suite. |
| Resume TXT | PASS | Same suite. |
| Scanned PDF OCR | FAIL | Tesseract is not on this machine's PATH, and the Docker image was not built. With Tesseract missing, `get_ocr_engine()` returns `NullOcrEngine` and `image_to_text` returns `""` without crashing. OCR inside the image was not proven. |
| Gemini | SKIPPED | No Gemini call was made. If `GEMINI_API_KEY` is empty, parsing stays on the local heuristic. NOT TESTED — requires a valid development Gemini API key. |
| Resend configuration | PASS | Email config tests passed. No email was sent. Live Resend delivery was not attempted. |
| File uploads | PASS | Path checks and upload rejection are in the security tests. Files go under `UPLOAD_DIR` (`uploads/` locally, `/app/uploads` on Render). Directory is created on startup. |
| CORS | PASS | Production config rejects `CORS_ORIGINS=*`. `FRONTEND_URL` is appended to the explicit origin list. |
| Security | PASS | Production rejects short `SECRET_KEY`, SQLite, disabled email, and wildcard CORS. Docs default off in production. `.env` is gitignored. |
| Core CareerSense flow | PASS | Automated registration, approval, alumni, and admin API tests passed. A browser walkthrough was not repeated in this pass. |

Insert/update/delete on the fresh PostgreSQL schema succeeded for an account, a tracer row, a perk, and a survey definition. A foreign key exists. The account row was removed afterward.

## C. Critical issues

None found in the code that was executed.

The Docker image and Tesseract-in-image check could not be run on this machine. That is an environment limit, not a failing application test. Confirm `GET /health` and `tesseract --version` on the first Render deploy before relying on scanned-PDF OCR.

## D. Warnings

- Render Persistent Disk mounted at `/app/uploads` with `UPLOAD_DIR=/app/uploads` is required if resumes, photos, and perk images must survive deploys. The container filesystem is ephemeral.
- Resend's free onboarding sender only delivers to the Resend account mailbox. Alumni mail needs a verified domain and `EMAIL_FROM_ADDRESS` on that domain.
- `GEMINI_API_KEY` is optional. Without it, registration still parses locally.
- Leave `EMAIL_SCHEDULER_ENABLED` blank on one web instance only, or reminders can send twice.
- This folder is not a Git repository. `.gitignore` ignores `.env`, `.env.*` (except examples), `frontend/dist`, `backend/uploads`, local SQLite files, and virtualenvs. Do not commit `backend/.env`.
- Name parsing keeps compound given names in `first_name` (`Sean Gabriel Santos` → first `Sean Gabriel`, last `Santos`). That is heuristic, not a legal-name guarantee.

## E. Environment variables

### Backend

| Variable | Required | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | Required | `production` |
| `DATABASE_URL` | Required | `postgresql+psycopg://...` |
| `SECRET_KEY` | Required | JWT signing, 32+ characters |
| `CORS_ORIGINS` | Required | Exact frontend origin, no `*` |
| `FRONTEND_URL` | Required | Same origin; also used in email links |
| `PUBLIC_APP_URL` | Required | Frontend origin fallback for links |
| `EMAIL_BASE_URL` | Required | Links inside emails |
| `EMAIL_ENABLED` | Required | `true` |
| `EMAIL_PROVIDER` | Required | `resend` |
| `EMAIL_API_KEY` | Required | Resend secret |
| `EMAIL_FROM_ADDRESS` | Required | Verified sender |
| `EMAIL_FROM_NAME` | Optional | Display name |
| `GEMINI_API_KEY` | Optional | Server-side resume model |
| `UPLOAD_DIR` | Required on Render | `/app/uploads` when a disk is mounted |
| `TRUST_X_FORWARDED_FOR` | Required | `true` behind Render |
| `GEMINI_MODEL` | Optional | Default `gemini-2.0-flash` |
| `EMAIL_REPLY_TO` | Optional | Reply address |
| `TESSERACT_CMD` | Optional | Leave empty; image puts Tesseract on `PATH` |
| `MAX_UPLOAD_MB` | Optional | Default 10 |
| `ENABLE_DOCS` | Optional | Off in production unless set |
| `RATE_LIMIT_ENABLED` | Optional | Default true |
| Email retry/scheduler variables | Optional | See `RENDER_DEPLOYMENT.md` |
| `OAAPS_*` | Optional | Rejected-account contact text |

### Frontend

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | Required | Backend origin, no trailing slash, set before `npm run build` |

The code does not read `RESEND_API_KEY`, `JWT_SECRET`, or any Supabase variable.

## F. Render configuration

Do not create these services until you choose to. Values to enter later:

**Backend — Web Service, Docker**

- Root directory: `backend`
- Dockerfile path: `Dockerfile` (the file `backend/Dockerfile`)
- Start: image command `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Health check path: `/health`
- Persistent disk mount: `/app/uploads`
- `UPLOAD_DIR=/app/uploads`

**Frontend — Static Site**

- Root directory: `frontend`
- Build command: `npm install && npm run build`
- Publish directory: `dist`
- Rewrite: `/*` → `/index.html` (Rewrite)

**Database — Render PostgreSQL**

- Set `DATABASE_URL` to `postgresql+psycopg://...`
- Do not run a separate migration job. Startup applies Alembic through `0006_email_reminders`.

## G. Final manual tests after Render

1. `GET https://<backend>/health` returns `{"status":"ok"}`.
2. Open the frontend URL, sign in, and confirm API calls go to `<backend>` (not the static host).
3. Refresh `/login` and `/admin` directly. Both must load the app, not a 404.
4. Register with a TXT or PDF resume, submit the GTS, and confirm the account is Pending.
5. Approve that account as admin and sign in as the alumnus.
6. Upload a scanned PDF and confirm OCR text appears. If it does not, run `tesseract --version` in the service shell.
7. Trigger forgot-password only for a mailbox you control.
8. Redeploy once and confirm an uploaded resume file is still readable (persistent disk).
