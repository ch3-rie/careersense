# CareerSense production deployment

This is the operational checklist for a campus deployment. The application can run without Docker; HTTPS, backups, and DNS are the host's responsibility.

## Implemented in the application

- FastAPI API with JWT auth, RBAC, and account status gates
- Alembic migrations on startup (fails closed when `ENVIRONMENT=production`)
- Security headers on API responses
- Local or PostgreSQL database
- Disk file storage under `UPLOAD_DIR`
- Resend transactional email and an outbox/scheduler
- Optional Gemini resume extraction with a local heuristic fallback
- `GET /api/health` liveness probe
- First-admin helper: `backend/scripts/create_admin.py`

## Must be configured for live use

1. `ENVIRONMENT=production`
2. Unique `SECRET_KEY` of at least 32 characters
3. PostgreSQL `DATABASE_URL`
4. Explicit `CORS_ORIGINS` for the campus frontend origin (not `*`)
5. `EMAIL_ENABLED=true` with a real Resend API key and verified from-address — see [resend-email.md](resend-email.md)
6. HTTPS terminator (IIS, nginx, or a load balancer)
7. Restricted `UPLOAD_DIR` outside the web root
8. Backups of the database and `uploads/` — see [backup-restore.md](backup-restore.md)

## Suggested reverse proxy headers

Forward the real client IP only when the proxy is trusted:

```text
TRUST_X_FORWARDED_FOR=true
```

The proxy should strip incoming `X-Forwarded-For` from clients and set it itself. Also send:

- `X-Forwarded-Proto: https`
- HSTS on the HTML origin
- A Content-Security-Policy on the frontend origin (the API already sends a restrictive API CSP)

## Process model

- Serve the API with Uvicorn or Gunicorn behind the proxy.
- Keep **one** API process with `EMAIL_SCHEDULER_ENABLED` following email (the default) so reminder mail is not duplicated.
- Rate limits are in-process. Multiple workers weaken those limits; put login/forgot-password limits on the proxy as well if you run more than one worker.

## Frontend

```powershell
cd frontend
npm ci
npm run build
```

Host `frontend/dist` on the same campus hostname, or set `VITE_API_URL` at build time to the API origin.

## First administrator

Demo users are **not** seeded in production. After the empty database is migrated:

```powershell
cd backend
py -3 scripts/create_admin.py --email oaaps.admin@auf.edu.ph --first-name OAAPS --last-name Admin
```

Sign in and change the temporary password immediately. Additional admins are created from Admin → Users.

## Health check

`GET /api/health` returns `{ "ok": true }` when the process is up. In production it does not advertise Gemini, docs, or provider details.

## Optional services

| Service | Required to go live? | If missing |
|---|---|---|
| Resend | Yes in production | API refuses to start |
| Gemini | No | Heuristic parser still extracts name, jobs, education, skills |
| Object storage | No for a single-server campus | Replace `app/services/files.py` when you outgrow local disk |
| Redis rate limits | No for a single process | Add when you scale to multiple API workers |
