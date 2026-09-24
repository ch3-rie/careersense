# CareerSense

Graduate Tracer System for the **Angeles University Foundation Office of Alumni Affairs and Placement Services**.

Alumni upload a resume. CareerSense extracts education, work history, skills, and job titles, maps them into the Graduate Tracer Survey (GTS), and lets the graduate correct the record before OAAPS reviews it. Administrators approve accounts, classify occupations against PSOC/SOC codes, and report on career alignment.

This is a full-stack rebuild of the earlier Streamlit prototype (`Resume-NLP-Parser`). All original workflows are preserved. Session-based Streamlit routing, hardcoded demo admin bypasses, and in-memory “fake” survey/SOC writes are replaced with a real API, database, and role-based UI.

---

## What was retained vs replaced

| Area | Decision |
|------|----------|
| Resume → GTS extraction | **Retained and ported.** Gemini when `GEMINI_API_KEY` is set; otherwise the same local heuristic parser. |
| Identity matching against university records | **Retained** (email, then name). |
| Career alignment via PSOC/SOC | **Retained** and persisted (no longer a success toast without a write). |
| GTS four-tab instrument | **Retained** (general, employment, further studies, institutional feedback). |
| Alumni / Admin / Pending / Rejected flows | **Retained** as real URLs. |
| Streamlit UI and session routing | **Replaced.** Streamlit reruns were the main source of lag. |
| Supabase-only data layer | **Replaced** with SQLAlchemy. SQLite locally; PostgreSQL for deployment. |
| Supplementary GTS questions | **Upgraded** from session-only prototype to database CRUD that appears on the live form. |
| SOC “add code” | **Upgraded** from a fake success message to a real insert. |
| Password change | **Upgraded** from UI-only to a verified hash update. |

---

## Project structure

```text
CareerSense/
  backend/
    app/
      main.py              # FastAPI entry, CORS, table create + seed
      config.py            # Environment settings
      db.py                # SQLAlchemy engine / session
      models.py            # Database models
      schemas.py           # Request/response models
      security.py          # bcrypt + JWT
      deps.py              # Auth dependencies / RBAC
      seed.py              # Demo records, PSOC codes, users
      constants.py         # Locked GTS sections and option lists
      routers/             # HTTP API
      services/            # Parser, alignment, file storage, GTS persist
    data/                  # PSOC CSV + sample resume text
    uploads/               # Stored resumes (created at runtime)
    requirements.txt
  frontend/
    src/pages/             # Public, alumni, and admin screens
    src/components/        # Layout, GTS form, shared UI
    src/lib/               # API client + auth context
  .env.example
  README.md
```

---

## Database schema

Core tables (see `backend/app/models.py`):

- `university_records` — official graduate registry used for matching
- `accounts` — email, password hash, role (`Alumni` / `Admin`), status (`Pending` / `Active` / `Rejected`)
- `alumni_profiles` — name, degree, guardian fields
- `resumes` — uploaded file path, extracted text, parsed JSON, parser source
- `tracer_submissions` — each GTS snapshot, alignment, SOC code, extra answers
- `further_studies`, `alumni_skills`, `alignment_results`
- `soc_codes`, `job_title_mappings`
- `gts_questions` — supplementary (non-core) questions managed by admins
- `admin_logs` — approve/reject and configuration audit trail

---

## API

Base URL: `http://127.0.0.1:8000` (the Vite dev server also proxies `/api`).

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| GET | `/api/health` | Public | Liveness + whether Gemini is configured |
| GET | `/api/auth/options` | Public | GTS option lists + supplementary questions |
| POST | `/api/auth/register` | Public | Validate + parse resume into a **draft** (no account yet) |
| POST | `/api/auth/register/complete` | Public | Submit GTS; **then** create the alumni account |
| POST | `/api/auth/login` | Public | JWT login |
| GET | `/api/auth/me` | Auth | Current user |
| POST | `/api/auth/change-password` | Auth | Password update |
| POST | `/api/alumni/gts` | Alumni | Save tracer survey + run alignment |
| GET | `/api/alumni/dashboard` | Active alumni | Metrics |
| GET | `/api/alumni/analytics` | Active alumni | Scores and history |
| GET/POST | `/api/alumni/resumes` | Alumni | List / upload+parse |
| GET | `/api/admin/dashboard` | Admin | KPIs and charts |
| GET/POST | `/api/admin/approvals…` | Admin | Queue, verify, approve, reject |
| GET | `/api/admin/tracer` | Admin | Search tracer records |
| CRUD | `/api/admin/questions` | Admin | Supplementary GTS questions |
| GET/POST | `/api/admin/soc` | Admin | PSOC/SOC codes |
| POST | `/api/admin/job-mappings` | Admin | Raw title → SOC |
| GET | `/api/admin/reports` + `/export` | Admin | Totals and CSV |
| GET/POST | `/api/admin/university-records` | Admin | Graduate registry |
| GET/POST | `/api/admin/cards…` | Admin | AAC application queue and status changes |

---

## Authentication and authorization

1. Alumni register with email, password, privacy consent, and a resume.
2. The API hashes the password (bcrypt), stores the file, parses the resume, and tries to match `university_records`.
3. A JWT is returned. Status is `Pending` until an admin approves.
4. The graduate reviews the GTS and submits. Alignment is computed against SOC codes.
5. Admins verify the graduate record, then approve or reject (with a reason and an audit log).
6. Active alumni use `/alumni/*`. Admins use `/admin/*`. Pending and rejected users cannot open the alumni dashboard.

---

## Setup

### Requirements

- Python 3.11+ (tested with 3.13)
- Node.js 20+

### 1. Backend

```powershell
cd backend
py -3 -m pip install -r requirements.txt
copy ..\.env.example .env
py -3 -m uvicorn app.main:app --reload --port 8000
```

On first start the API creates `backend/careersense.db`, seeds PSOC codes, graduate records, and demo users.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Environment variables

See `.env.example`. Copy it to `backend/.env`.

| Variable | Required | Notes |
|----------|----------|--------|
| `ENVIRONMENT` | No | `development` (default) or `production`. Production refuses insecure `SECRET_KEY` values and disables `/docs` unless `ENABLE_DOCS=true`. |
| `DATABASE_URL` | No | Default SQLite file. Use PostgreSQL URL in production. |
| `SECRET_KEY` | **Yes in production** | JWT signing key. Must be unique and at least 32 characters when `ENVIRONMENT=production`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default 720 (12 hours). |
| `CORS_ORIGINS` | No | Comma-separated frontend origins. |
| `ENABLE_DOCS` | No | Override API docs. Default: on in development, off in production. |
| `RATE_LIMIT_ENABLED` | No | Default true. Limits login, registration, and password-change attempts per IP. |
| `GEMINI_API_KEY` | No | If empty, the local parser still extracts name/education/jobs/skills. |
| `GEMINI_MODEL` | No | Default `gemini-2.0-flash`. |
| `UPLOAD_DIR` | No | Resume storage directory. |
| `MAX_UPLOAD_MB` | No | Default 10. |
| `EMAIL_ENABLED` | No | `true` to send Resend mail. `false` for local work without a key. |
| `EMAIL_PROVIDER` | When sending | Must be `resend`. |
| `EMAIL_API_KEY` | When sending | Resend secret. Put it only in `backend/.env`. |
| `EMAIL_FROM_ADDRESS` | When sending | Verified sender address. |
| `EMAIL_BASE_URL` | When sending | Public frontend URL used in email links. |
| `EMAIL_SCHEDULER_ENABLED` | No | Blank follows `EMAIL_ENABLED`. Set on one API process only if you run multiple workers. |
| `VITE_API_URL` | No | Frontend only. Leave empty in dev (Vite proxies `/api`). Never put the Resend key here. |

---

## Demo accounts

Seeded on first API start:

| Role | Email | Password | Status |
|------|-------|----------|--------|
| Admin | `admin@auf.edu.ph` | `Admin@AUF2026` | Active |
| Alumni | `maria.reyes@gmail.com` | `Alumni@2026` | Active (aligned BSIT / software) |
| Alumni | `juan.delacruz@gmail.com` | `Alumni@2026` | Pending |
| Alumni | `liza.torres@gmail.com` | `Alumni@2026` | Active (misaligned BSA / restaurant manager) |
| Alumni | `ana.garcia@gmail.com` | `Alumni@2026` | Rejected |

A sample resume for parser tests is at `backend/data/sample_resume.txt`.  
`carlos.mendoza@gmail.com` exists in the graduate registry but has no account yet — use it to try a full registration.

**User and IT testing pack:** [docs/UAT-testing-guide.md](docs/UAT-testing-guide.md)  
Sample resumes, GTS answers, and extra registry rows: [backend/data/samples/](backend/data/samples/).

---

## External services and assumptions

- **Gemini** is optional. Without a key, extraction still runs locally. Connect later by setting `GEMINI_API_KEY`; no other architecture change is required.
- **Email** is sent from the API through Resend (`EMAIL_ENABLED`, `EMAIL_API_KEY` in `backend/.env`). The frontend never receives the key. Forgot Password PINs, profile update notices, automated profile reminders, and account approval mail all use this path. Full setup: [docs/resend-email.md](docs/resend-email.md).
- **Supabase** is no longer required. Data lives in SQLite or PostgreSQL.
- Resume files are stored on local disk (`backend/uploads`). For production, point this at a network volume or replace `app/services/files.py` with object storage.
- PSOC rows in `backend/data/psoc_seed.csv` are a starter set, not the full PSA publication.

---

## Deployment considerations

1. Set `ENVIRONMENT=production`, a strong unique `SECRET_KEY` (32+ characters), and switch `DATABASE_URL` to PostgreSQL.
2. Serve the API with Uvicorn/Gunicorn behind HTTPS (IIS, nginx, or a cloud load balancer). API docs are off in production unless `ENABLE_DOCS=true`.
3. Build the frontend with `npm run build` and host `frontend/dist` on the same domain or set `VITE_API_URL` to the API origin.
4. Restrict CORS to the real campus hostname.
5. Back up the database and `uploads/` — see [docs/backup-restore.md](docs/backup-restore.md).
6. Do not commit `.env`, the SQLite file, or uploaded resumes.
7. Demo accounts are seeded only in development. In production create the first admin with `backend/scripts/create_admin.py`.
8. Place the upload directory outside the web root and keep admin-only file download.
9. Schema changes are applied with Alembic (`backend/migrations`) on API startup. Production startup fails if migrations fail.
10. For campus email, set `EMAIL_ENABLED=true` with a real Resend key and verified from-address, then keep one API process running so the reminder scheduler can send. See [docs/resend-email.md](docs/resend-email.md).

Full deployment notes: [docs/deployment.md](docs/deployment.md).

Optional PostgreSQL:

```text
DATABASE_URL=postgresql+psycopg://careersense:careersense@localhost:5432/careersense
```

---

## Running tests of the original workflows

Step-by-step scripts, sample resumes, and GTS answers for alumni testers and IT/OAAPS staff: [docs/UAT-testing-guide.md](docs/UAT-testing-guide.md).

1. Sign in as admin and open **Approval queue**, **SOC mapping**, **Survey manager**, and **Reports**.
2. Sign in as `maria.reyes@gmail.com` and open dashboard, analytics, resume upload, and password change.
3. Register `carlos.mendoza@gmail.com` with `backend/data/samples/carlos_mendoza.txt` (or a PDF), review the pre-filled GTS, submit, then approve from the admin queue.
4. Add a supplementary question in Survey manager and confirm it appears on the GTS form.
5. Add a SOC code and confirm it is searchable and used in alignment.
6. With email configured, request a Forgot Password PIN and send a profile reminder from **Admin → Profile Updates**. See [docs/resend-email.md](docs/resend-email.md).

Automated tests (from `backend`):

```powershell
py -3 -m pytest
```
