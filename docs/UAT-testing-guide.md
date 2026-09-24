# CareerSense testing pack

Use this pack for **user acceptance testing** (alumni testers) and **IT / OAAPS verification**. Demo data is seeded only in development. Do not use these passwords on a live campus system.

| Item | Value |
|------|--------|
| App | [http://localhost:5173](http://localhost:5173) |
| API | [http://127.0.0.1:8000](http://127.0.0.1:8000) |
| API docs (development) | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| Health | [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) |
| Sample files | [`backend/data/samples/`](../backend/data/samples/) |

---

## 1. Start the system (IT)

Requirements: Python 3.11+ and Node.js 20+.

```powershell
cd backend
py -3 -m pip install -r requirements.txt
copy ..\.env.example .env
py -3 -m uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

On first API start the database is created and demo graduates, PSOC codes, users, perks, and survey questions are seeded.

Confirm the API is up:

```powershell
curl http://127.0.0.1:8000/api/health
```

Expected JSON includes `"ok": true`. `gemini_configured` may be `false`; the local parser still extracts name, education, jobs, and skills.

Automated checks (from `backend/`):

```powershell
py -3 -m pytest
```

---

## 2. Demo accounts

Password rule: at least **8 characters**, with **letters and numbers**.

| Who | Email | Password | Status | What to test |
|-----|-------|----------|--------|--------------|
| OAAPS admin | `admin@auf.edu.ph` | `Admin@AUF2026` | Active | Approvals, registry, survey, perks, SOC, reports, users |
| Maria Reyes (BSIT, aligned) | `maria.reyes@gmail.com` | `Alumni@2026` | Active | Full alumni portal, claimed alumni card, perks, achievements |
| Liza Torres (BSA, misaligned) | `liza.torres@gmail.com` | `Alumni@2026` | Active | Misaligned occupation, no alumni card yet, further studies |
| Juan Dela Cruz | `juan.delacruz@gmail.com` | `Alumni@2026` | Pending | Pending page; cannot open `/alumni` |
| Ana Garcia | `ana.garcia@gmail.com` | `Alumni@2026` | Rejected | Rejected page with OAAPS reason |

**New registration (no account yet):** `carlos.mendoza@gmail.com` is in the graduate registry. Use resume [`carlos_mendoza.txt`](../backend/data/samples/carlos_mendoza.txt) and password `Alumni@2026`.

Other registry emails with **no account** (register the same way):

| Email | Student ID | Degree | Sample resume |
|-------|------------|--------|----------------|
| `paolo.navarro@gmail.com` | 2022-0112 | BS Civil Engineering | [`paolo_navarro.txt`](../backend/data/samples/paolo_navarro.txt) |
| `sofia.lim@gmail.com` | 2017-0201 | BEEd | [`sofia_lim.txt`](../backend/data/samples/sofia_lim.txt) |
| `miguel.santos@gmail.com` | 2020-0455 | BSBA | [`miguel_santos.txt`](../backend/data/samples/miguel_santos.txt) |

---

## 3. Seeded data testers will see

### Maria Reyes (aligned)

- Degree: BS Information Technology, Class of 2022
- Jobs: Junior Software Developer → Software Engineer
- Alignment: **Aligned**, PSOC **2512** Software Developers
- Alumni card: **Claimed** (`AUF-2022-0001`), pickup AUF Main Campus
- Phone / city: +63 917 555 0101, Angeles City
- Perk already claimed: Homecoming early-bird rate (code `AUF-HM-MARIA`)
- Library perk requires an issued card — Maria can claim it; Liza cannot until her card is issued

### Liza Torres (misaligned)

- Degree: BS Accountancy, Class of 2020
- Jobs: Associate Auditor → Restaurant Manager
- Alignment: **Misaligned**, PSOC **1412** Restaurant Managers
- Further studies: MBA at AUF (in progress)
- Alumni card: **Not yet applied**

### Juan Dela Cruz (pending)

- IT Support Specialist at Angeles Medical Center
- After login, the app stays on `/pending`

### Ana Garcia (rejected)

- Reason: submitted documents did not match the graduate record
- After login, the app stays on `/rejected`

### Demo perks

| Perk | Notes |
|------|--------|
| AUF Library alumni access | Requires claimed/ready alumni card |
| Partner cafe discount | Open to alumni; 15% off |
| Homecoming early-bird rate | Maria already claimed |
| 2025 Career Fair priority lane | **Expired** — should show as ended |

### Supplementary GTS questions (already on the form)

- How helpful was AUF internship or OJT support in your first job search? (scale 1–5)
- Which work arrangement best describes your current job? (On-site / Hybrid / Fully remote / Not applicable)

---

## 4. Alumni tester scripts

Use Chrome or Edge. Sign out between accounts (Manage Account → Sign out, or use a private window).

### A. Public site

1. Open `/`. Confirm Features and How it works.
2. Open Sign in and Upload resume.
3. Try **Forgot password** (needs email configured; see §7).

### B. Sign in as Maria (happy path)

1. Log in at `/login`.
2. **Home** `/alumni`: profile completion, achievements, work history, notifications.
3. **Alumni Card**: claimed card number and expiry (2028-03-31).
4. **Perks**: cafe discount is claimable; library perk is available because the card is claimed; Career Fair is expired; Homecoming is already used.
5. **Resume & Tracer**: review pre-filled GTS, save a small edit (for example skills), confirm alignment stays Aligned.
6. **Manage Account**: change password only if you will keep using this tester machine; otherwise skip so other testers can still use `Alumni@2026`.

Expected: Maria can open every `/alumni/*` page and is redirected away from `/admin`.

### C. Sign in as Liza (misalignment + card apply)

1. Home shows **Misaligned** and suggested paths such as accountant / auditor.
2. Open Alumni Card → apply with:

   | Field | Sample |
   |-------|--------|
   | Birthday | 1998-08-20 |
   | Phone | +63 918 555 0144 |
   | City | Mabalacat |
   | Country | Philippines |
   | Mailing address | 12 Rizal St., Mabalacat, Pampanga |
   | Company | Kapampangan Kitchen Group |
   | Position | Restaurant Manager |
   | Membership | New |

3. After submit, status should be **For verification**. Library perk stays locked until OAAPS marks the card ready/claimed.
4. Resume & Tracer: confirm MBA further-studies row is present.

### D. Pending and rejected

1. Juan → only `/pending`. Direct visit to `/alumni` must bounce back.
2. Ana → `/rejected` with the OAAPS reason. Direct visit to `/alumni` must bounce back.

### E. Full registration (Carlos)

1. Sign out. Open `/register`.
2. Email `carlos.mendoza@gmail.com`, password `Alumni@2026` (enter twice).
3. Upload [`carlos_mendoza.txt`](../backend/data/samples/carlos_mendoza.txt) (PDF/DOCX/TXT, max 10 MB).
4. Tick privacy consent.
5. Review extraction. Copy any missing answers from [`gts-sample-answers.md`](../backend/data/samples/gts-sample-answers.md) (Carlos column).
6. Submit. You should land on the success / pending step.
7. Switch to admin (next script) and approve Carlos.
8. Sign in as Carlos and confirm `/alumni` opens.

### F. Other registration samples

| Goal | Email | Resume | Expected alignment after GTS |
|------|-------|--------|------------------------------|
| Aligned engineering | `paolo.navarro@gmail.com` | `paolo_navarro.txt` | Civil Engineer → PSOC 2142 |
| Aligned education | `sofia.lim@gmail.com` | `sofia_lim.txt` | Primary teacher → PSOC 2341 |
| Aligned business | `miguel.santos@gmail.com` | `miguel_santos.txt` | Marketing → PSOC 2431 or 1221 |
| Never employed | Add Elena to Registry first | `elena_ramos.txt` | No occupation alignment |
| Unmatched name | `tester.unmatched@example.com` | `unmatched_applicant.txt` | Pending; admin verify finds no record |

### G. Negative checks (alumni)

| Action | Expected |
|--------|----------|
| Register with password `password` (letters only) | Blocked: letters **and** numbers required |
| Register without consent or without a resume | Blocked |
| Upload `.jpg` or empty file | Blocked |
| Register `maria.reyes@gmail.com` again | Account already exists |
| Alumni opens `/admin` | Redirected to alumni home |

---

## 5. OAAPS / admin tester scripts

Log in as `admin@auf.edu.ph`.

### A. Approval queue

1. Open **Approvals**. Juan should already be Pending.
2. Open Juan → **Verify** (should match student ID 2020-0002) → **Approve**.
3. Sign in as Juan in another window: `/alumni` should now open.
4. Optional: reject a throwaway registration with reason `QA reject — documents do not match the graduate record.` (min. 3 characters). Applicant then sees `/rejected`.

### B. Graduate registry

1. Search `2021-0088` or `Carlos`.
2. Add Elena before the unemployed registration test:

   | Field | Value |
   |-------|--------|
   | Student ID | 2023-0202 |
   | First / Middle / Last | Elena / Cruz / Ramos |
   | Email | `elena.ramos@gmail.com` |
   | Degree | Bachelor of Science in Nursing |
   | Year | 2023 |
   | Course code | BSN |
   | College | College of Nursing |

   Same rows are in [`registry-sample.csv`](../backend/data/samples/registry-sample.csv). Duplicate student ID or email must be rejected.

### C. Tracer records and reports

1. **Records**: open Maria (Aligned) and Liza (Misaligned).
2. **Reports**: totals, filters (year / college), CSV export, OAAPS document export/print.

### D. Survey manager

1. Confirm the four core sections (General, Employment, Further Studies, Feedback) are present.
2. Add a question, for example: *Would you recommend AUF to a family member?* (Yes/No, Feedback).
3. Publish if the UI requires it, then confirm the question appears on `/register` and on Maria’s Resume & Tracer form.

### E. Perks

Create a test perk:

| Field | Sample |
|-------|--------|
| Name | Partner bookstore 10% off |
| Partner | AUF Bookstore |
| Discount | 10% off |
| Category | Campus |
| How to claim | Show your alumni card at the cashier. |
| Valid from / to | 2026-01-01 / 2026-12-31 |
| Requires active card | No |

Toggle it off and confirm alumni no longer see it as available.

### F. SOC mapping

1. Search `2512` (Software Developers) and `1412` (Restaurant Managers).
2. Add a mapping if needed, e.g. raw title `fullstack engineer` → `2512`.
3. Re-save a GTS with that title and confirm alignment uses the mapping.

### G. Profile updates

1. Search Maria. Send a request for **Phone number** and **City**.
2. Sign in as Maria: notification appears; update contact on Home.
3. Admin request list should reflect the follow-up.

### H. Admin users

1. Create a second admin (copy the **one-time temporary password** immediately).
2. New admin must change password on first login (`/admin/account`).
3. Do not deactivate the last active admin.

### I. Authorization (IT)

| Caller | `/api/admin/dashboard` | `/api/alumni/dashboard` |
|--------|------------------------|-------------------------|
| Admin | 200 | 403 |
| Active alumni | 403 | 200 |
| Pending / rejected | 403 | 403 |
| Anonymous | 401 | 401 |

---

## 6. Sample files

All files live in [`backend/data/samples/`](../backend/data/samples/). TXT resumes are enough for parser tests; PDF and DOCX are also accepted.

| File | Purpose |
|------|---------|
| `carlos_mendoza.txt` | Happy-path registration (BSCS / software) |
| `paolo_navarro.txt` | Civil engineering alignment |
| `sofia_lim.txt` | Education alignment |
| `miguel_santos.txt` | Business / marketing alignment |
| `elena_ramos.txt` | Never employed (add registry row first) |
| `unmatched_applicant.txt` | No university record |
| `gts-sample-answers.md` | Copy-paste GTS values if extraction is incomplete |
| `registry-sample.csv` | Extra graduates to encode in Registry |
| `../sample_resume.txt` | Original Maria parser sample |

Resume layout the parser expects:

```text
Full Name
City, Province, Philippines
email@example.com

EDUCATION
Bachelor of ...
Angeles University Foundation
YYYY - YYYY

WORK EXPERIENCE
Job Title
Employer | Month YYYY - Present

SKILLS
Skill1, Skill2, Skill3
```

---

## 7. Email (optional IT check)

Local default is `EMAIL_ENABLED=false`. Forgot Password PINs and profile-update mail will not send until Resend is configured. Setup: [resend-email.md](resend-email.md).

With email on:

1. Forgot password for Maria → 6-digit PIN (10 minutes) → new password.
2. Admin → Profile Updates → send request → mailbox + in-app notice.
3. Approve/reject → account status mail.

If email is off, still test the on-screen Forgot Password errors and admin request history.

---

## 8. Limits and expected errors (IT)

| Rule | Value |
|------|--------|
| Resume types | `.pdf`, `.docx`, `.txt` only |
| Resume size | 10 MB (`MAX_UPLOAD_MB`) |
| Login attempts | 12 / 10 minutes / IP |
| Registration attempts | 6 / 10 minutes / IP |
| Password change / reset | 8 / 15 minutes |
| Forgot-password request | 8 / 10 minutes |
| PIN verify | 20 / 10 minutes |

Too many attempts return HTTP **429**: *Too many attempts. Please wait a few minutes and try again.*

Gemini is optional. Without `GEMINI_API_KEY`, extraction is heuristic; testers can still complete the GTS by hand.

---

## 9. Suggested test order (half day)

1. Health + pytest (IT).
2. Landing, login, Maria happy path, Liza card apply.
3. Juan pending / Ana rejected access checks.
4. Carlos registration + admin approve.
5. Registry add Elena → unemployed registration.
6. Unmatched applicant + reject.
7. Survey extra question, perk create, SOC search, reports export.
8. Optional: email PIN.

Record pass/fail on a copy of this list. Note browser, date, and whether Gemini was on.
