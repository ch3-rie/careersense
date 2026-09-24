# CareerSense backup and restore

CareerSense stores alumni records in the database and resumes/photos/perk images on disk. Application code does not take backups by itself. Campus IT must schedule backups of both.

## What to back up

| Asset | Default local path | Production |
|---|---|---|
| Database | `backend/careersense.db` (SQLite) | PostgreSQL database named in `DATABASE_URL` |
| Uploaded files | `backend/uploads/` | The directory in `UPLOAD_DIR` (network volume or object storage) |
| Configuration | `backend/.env` | Secret store / protected host environment. Never store this in Git. |

Do not back up `__pycache__`, `frontend/node_modules`, or pytest temp databases.

## Frequency and retention

For a campus deployment:

- Database: at least daily, retain 30 days, keep one monthly copy for a year if policy requires it.
- `uploads/`: with the database, or continuously if the volume is replicated.
- Test a restore at least once before go-live and after any schema change.

## SQLite (development)

Stop the API, then copy the files:

```powershell
copy backend\careersense.db backups\careersense-yyyy-mm-dd.db
robocopy backend\uploads backups\uploads-yyyy-mm-dd /E
```

Restore by stopping the API, replacing those files, and starting the API again.

## PostgreSQL (production)

Example dump and restore (adjust names):

```powershell
pg_dump -Fc careersense > backups\careersense-yyyy-mm-dd.dump
pg_restore -d careersense --clean --if-exists backups\careersense-yyyy-mm-dd.dump
```

Restore `UPLOAD_DIR` to the same path the API expects. Resume rows store paths relative to that directory.

## After restore

1. Confirm `alembic current` matches the restored schema.
2. Start the API and call `GET /api/health`.
3. Sign in as an administrator and open Approvals, Alumni Cards, Records, and one resume download.
4. If JWT `SECRET_KEY` changed, every user must sign in again.

## Disaster recovery outline

1. Provision PostgreSQL and an empty `UPLOAD_DIR`.
2. Restore the latest database dump and upload tree.
3. Place `backend/.env` with the production `SECRET_KEY`, `CORS_ORIGINS`, Resend key, and `DATABASE_URL`.
4. Run `alembic upgrade head` if the restored dump is older than the release.
5. Start one API process so the email scheduler can run.
6. Verify login, a pending registration, and an AAC record.
