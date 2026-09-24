# CareerSense Render deployment

This document prepares deployment. It does not create Render services or publish the app.

CareerSense is two services:

```text
frontend/   Vite + React (static site)
backend/    FastAPI (Docker web service; Tesseract is installed in the image)
```

There is no Supabase client in this repository. Data is SQLAlchemy: SQLite locally, PostgreSQL in production (`DATABASE_URL`).

## Frontend (Render Static Site)

| Setting | Value |
| --- | --- |
| Root directory | `frontend` |
| Build command | `npm install && npm run build` |
| Publish directory | `dist` |
| SPA rewrite | Source `/*`, destination `/index.html`, action **Rewrite** |

The app uses `BrowserRouter`. Without that rewrite, refreshing `/login`, `/alumni`, or `/admin` returns 404.

Environment variable (set before the production build):

| Name | Purpose | Secret |
| --- | --- | --- |
| `VITE_API_URL` | Public backend origin, no trailing slash, for example `https://<backend>.onrender.com` | No |

Leave `VITE_API_URL` empty only for local `npm run dev`, which proxies `/api` to `127.0.0.1:8000`. A production build with an empty value calls the static site host, which has no API.

Do not put `GEMINI_API_KEY`, `EMAIL_API_KEY`, `SECRET_KEY`, or database credentials in the frontend.

## Backend (Render Web Service, Docker)

| Setting | Value |
| --- | --- |
| Root directory | `backend` |
| Runtime | Docker |
| Dockerfile path | `backend/Dockerfile` (Dockerfile in the service root) |
| Health check path | `/health` |
| Start command | Defined by the image: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` |

Render injects `PORT`. Do not hardcode a host URL in the image.

Create a Render PostgreSQL database and set `DATABASE_URL` to its **external** or **internal** URL using the SQLAlchemy driver:

```text
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
```

Render’s default URL often starts with `postgresql://`. Change the scheme to `postgresql+psycopg://`. The API refuses to start in production when `DATABASE_URL` is SQLite.

`GET /health` returns `{"status":"ok"}` and does not call the database, Gemini, OCR, or email. `GET /api/health` remains for local diagnostics and is quieter in production.

### Backend environment variables

| Name | Purpose | Secret |
| --- | --- | --- |
| `ENVIRONMENT` | Set to `production` | No |
| `DATABASE_URL` | PostgreSQL URL (`postgresql+psycopg://...`) | Yes |
| `SECRET_KEY` | JWT signing key, at least 32 characters, unique | Yes |
| `CORS_ORIGINS` | Exact frontend origin, no wildcard | No |
| `FRONTEND_URL` | Same frontend origin; also used in email links if `EMAIL_BASE_URL` is empty | No |
| `PUBLIC_APP_URL` | Public frontend origin used in links when the two above are empty | No |
| `EMAIL_BASE_URL` | Public frontend origin written into email links | No |
| `EMAIL_ENABLED` | `true` in production (the API refuses `false`) | No |
| `EMAIL_PROVIDER` | `resend` | No |
| `EMAIL_API_KEY` | Resend API key (this is the Resend secret; the code does not read `RESEND_API_KEY`) | Yes |
| `EMAIL_FROM_ADDRESS` | Verified sender. The free `onboarding@resend.dev` address only delivers to the Resend account mailbox | No |
| `EMAIL_FROM_NAME` | Display name, default `CareerSense` | No |
| `EMAIL_REPLY_TO` | Optional | No |
| `GEMINI_API_KEY` | Optional. If empty, resume parsing uses the local parser | Yes |
| `GEMINI_MODEL` | Optional, default `gemini-2.0-flash` | No |
| `UPLOAD_DIR` | Resume/photo directory. Ephemeral on Render unless you attach a disk | No |
| `MAX_UPLOAD_MB` | Upload limit, default `10` | No |
| `TESSERACT_CMD` | Optional. Leave empty in the Docker image; Tesseract is on `PATH` | No |
| `TRUST_X_FORWARDED_FOR` | `true` only behind Render’s proxy | No |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional, default `720` | No |
| `ENABLE_DOCS` | Optional. Defaults off in production | No |
| `RATE_LIMIT_ENABLED` | Optional, default `true` | No |
| `EMAIL_RETRY_ATTEMPTS` | Optional | No |
| `EMAIL_RETRY_BACKOFF_MS` | Optional | No |
| `EMAIL_OUTBOX_MAX_ATTEMPTS` | Optional | No |
| `EMAIL_SCHEDULER_ENABLED` | Optional. Blank means on when email is enabled. Use one web instance so reminders are not sent twice | No |
| `EMAIL_SCHEDULER_INTERVAL_SECONDS` | Optional | No |
| `EMAIL_TIMEZONE` | Optional, default `Asia/Manila` | No |
| `OAAPS_EMAIL` | Optional contact on the rejected-account page | No |
| `OAAPS_PHONE` | Optional | No |
| `OAAPS_HOURS` | Optional | No |
| `OAAPS_LOCATION` | Optional | No |
| `OAAPS_OFFICE_NAME` | Optional | No |

Demo alumni and the demo admin are not seeded when `ENVIRONMENT=production`. PSOC/SOC reference rows are still loaded if the table is empty.

A fresh PostgreSQL database needs no manual migration step. On startup the API runs `create_all`, then `alembic upgrade head` to revision `0006_email_reminders`. That path was exercised against an empty PostgreSQL schema. Production still refuses a SQLite `DATABASE_URL`.

## Deployment order

1. Create Render PostgreSQL and copy its URL.
2. Deploy the backend Docker service with `ENVIRONMENT=production` and the variables above. Use a temporary `CORS_ORIGINS` / `FRONTEND_URL` if the frontend URL is not known yet (any `https://` placeholder will not match the real browser until step 6).
3. Copy the backend URL, for example `https://<backend>.onrender.com`.
4. Set the frontend `VITE_API_URL` to that origin and deploy the static site.
5. Copy the frontend URL.
6. Set backend `CORS_ORIGINS`, `FRONTEND_URL`, `EMAIL_BASE_URL`, and `PUBLIC_APP_URL` to that exact frontend origin (scheme + host, no path, no trailing slash).
7. Redeploy the backend so CORS and email links pick up the frontend origin.
8. Confirm Resend: a verified domain is required before mail can reach alumni addresses. The onboarding sender only reaches the Resend account mailbox.
9. Smoke-test health, sign-in, registration, resume upload, and one admin page.

## Persistent files

Resumes, profile photos, and perk images are stored on the container filesystem (`UPLOAD_DIR`). Render’s disk is wiped on each deploy unless a persistent disk is attached at the same path. PostgreSQL rows survive; the files they point at do not. Attach a Render disk mounted at `/app/uploads` and set `UPLOAD_DIR=/app/uploads`, or plan a later object-storage change. This repository does not switch storage automatically.
