# CareerSense QA Inspection Report

**Product:** CareerSense (AUF OAAPS Graduate Tracer)  
**Build inspected:** local FastAPI (`http://127.0.0.1:8000`) + Vite (`http://localhost:5173`)  
**Date:** 13 September 2026 (second pass)  
**Role:** Quality control  
**Prior report:** same file, first pass earlier the same day  
**Scope:** Registration, resume parser / GTS prefill, official SOC alignment, alumni portal, admin approvals / perks / reports / survey, authorization, pytest harness, and the registration + GTS radio UI shipped after the first pass

---

## Remediation pass (13 September 2026, evening)

Code fixes from this report were implemented and re-verified the same day.

**Pytest:** 125 passed, 0 failed, 0 skipped  
**Isolation order:** approval then pending, and pending then approval — both pass; seed Juan stays Pending  
**Alembic (from `backend/`):** `from alembic import command` succeeds; `alembic current`, `heads`, and `upgrade head` all report `0001_integrity (head)`  
**Live after uvicorn reload:**

| Scenario | Result |
|---|---|
| Present = first, only `first_occ` = Software Engineer | `current_occupation` = Software Engineer, `current_employer` = ABC Corporation, SOC **Aligned** |
| Present ≠ first, first IT Support / present Systems Analyst, same employer | official occupation = Systems Analyst; first and present roles remain distinct |
| Rejected Ana `GET /profile`, `/resumes`, alignment preview | **403** (`/me` still 200) |
| Pending Juan dashboard | **403**, status still Pending |
| Frontend `/`, `/login`, `/register` | HTTP 200 |

### Status after remediation

| ID | Status |
|---|---|
| HIGH-01 | Fixed |
| HIGH-02 | Fixed |
| HIGH-03 | Fixed |
| HIGH-04 | Fixed |
| HIGH-05 | Fixed |
| HIGH-06 | Fixed (undated GTS stubs sync on later saves; dated manual jobs are left alone) |
| HIGH-07 | Fixed |
| HIGH-08 | Fixed |
| HIGH-09 | Fixed |
| MED-01 | Fixed |
| MED-03 | Fixed |
| MED-04 | Fixed |
| MED-05 | Fixed |
| MED-06 | Fixed |
| MED-07 | Fixed |
| MED-08 | Fixed |
| MED-09 | Fixed |
| MED-10 | Remaining — upload still returns parser `course_alignment` beside official SOC; persist uses SOC |
| MED-11 | Fixed |
| MED-12 | Fixed |
| MED-13 | Fixed |
| LOW-01 | Fixed |
| LOW-02 | Fixed |
| LOW-03 | Fixed |
| MED-02 | Already fixed before this pass |

The original second-pass findings below are retained as the inspection record. They describe the defects as they existed before this remediation.

---  

This report lists **confirmed defects**. Missing features are not filed. Severity:

| Severity | Meaning |
|---|---|
| High | Wrong official data, broken access policy, or false admin/alumni UI |
| Medium | Broken flow, inconsistent lockout, or misleading prefill |
| Low | Polish, sticky alerts, empty defaults |
| Residual | Mostly fixed; a narrow path still fails |
| Fixed | Re-verified as no longer occurring in current code |

---

## Executive summary

The registration contract is still sound: resume is required, `POST /api/auth/register` creates a **24-hour draft only** (`account_created: false`), and the alumni **Account** row is created only on `POST /api/auth/register/complete` as **Pending**. The parser remains prefill, not source of truth.

This second pass re-verified the first-pass register, ran the full backend suite, and probed the live API. It also inspected the registration wizard and GTS radio work.

**Open defects: 9 High, 11 Medium, 3 Low**, plus **1 residual Medium**. Three UI issues from the first pass / subsequent UI work are **fixed**.

The highest-risk cluster is still **current-job alignment**:

1. When the graduate says the present job is also the first job, the form hides `pres_occ` and persist **does not fall back to `first_occ`**. Official SOC alignment is stored as **Unknown** with an empty current occupation. **Confirmed on the live API in this pass.**
2. Prefill marks “present job is first” from **employer equality only**, so two different roles at the same company hide present-job fields.
3. Hidden `pres_occ` is still submitted. If the parser filled it, official alignment can use a title the graduate did not see.

Also confirmed at runtime:

- Local package `backend/alembic/` **shadows** the installed Alembic library, so startup migrations never run.
- Approving seed user Juan in `test_admin_ops` **pollutes** the session-scoped test database; later pending-alumni tests fail (`90 passed, 3 failed`).
- Rejected alumni can still call profile, resume list, and alignment-preview APIs.

**Recommendation:** Fix the present-job persist path (copy `first_occ` into the occupation used for SOC when present = first, and stop treating hidden `pres_occ` as authoritative). Rename the Alembic scripts package. Isolate pytest so CI cannot greenwash authorization.

---

## Method

| Check | Result |
|---|---|
| Static review of registration, GTS persist, parser mapping, alumni/admin routers, Register / GtsSchemaForm / Perks / Resume | Completed |
| `from alembic import command` from `backend/` | `ImportError` (HIGH-05) |
| Persist occupation when `present_job_is_first=Yes` and only `first_occ` is set | `job_title == ""` (HIGH-01) |
| Full pytest (`backend/tests`) | **90 passed, 3 failed** |
| Ordered isolation: `test_approve_and_reject` then pending tests | **1 passed, 3 failed** (HIGH-09) |
| Live `GET /api/health`, `/api/auth/options`, `/`, `/login`, `/register` | HTTP 200 |
| Live letters-only password on `/api/auth/register` | HTTP 400, server copy matches validation |
| Live login: admin, Maria (Active), Juan (Pending), Ana (Rejected) | Authz matrix below |
| Live `/register` + `/register/complete` with **only** `first_occ` | **Unknown** alignment stored |
| Live complete with **both** `first_occ` and `pres_occ` | **Aligned** (control) |
| Interactive click-through of every admin screen | **Not done** (HTTP + code only) |

Gemini is **not** configured in this environment (`gemini_configured: false`). Parser runs in heuristic mode.

Two throwaway Pending accounts were created on the local database to prove HIGH-01. OAAPS can reject them:

- `qa.high01.13092026c@gmail.com` — Unknown alignment (defect case)
- `qa.high01.both.13092026@gmail.com` — Aligned (control)

---

## Status versus first inspection

| ID | First pass | This pass |
|---|---|---|
| HIGH-01 | Open (code) | **Open — live API confirmed** |
| HIGH-02 | Open | Open (code) |
| HIGH-03 | Open | Open (code; survey currently open so closed path not hit live) |
| HIGH-04 | Open | Open (code) |
| HIGH-05 | Open (runtime) | Open (re-confirmed) |
| HIGH-06 | Open | Open (code) |
| HIGH-07 | Open | Open (code) |
| HIGH-08 | Open | Open (code) |
| HIGH-09 | Open (runtime) | Open (re-confirmed, 3/4 isolation fail) |
| MED-01 | Open (step 3 skipped) | **Residual** — `justRegistered()` keeps step 3 unless sessionStorage is unavailable |
| MED-02 | Open (length-only hint) | **Fixed** — `passwordIsValid` requires letters + numbers before upload |
| MED-03–12 | Open | Open |
| MED-13 | — | **New** — alignment hint status is frozen from resume parse |
| LOW-01, LOW-02 | Open | Open |
| LOW-03 | — | **New** — session-expired login notice uses error Alert |
| GTS `T()` collapsing labels | Not filed | **Fixed** — `T()` is identity |
| Radio/checkbox full-width chrome | Not filed | **Fixed** — `.field input` excludes radio/checkbox |

---

## Runtime evidence

### HIGH-01 — live persist

`POST /api/auth/register/complete` with:

- `is_currently_employed: Yes`
- `present_job_is_first: Yes`
- `first_occ: Software Engineer`
- `pres_occ: ""`

returned `alignment_status: "Unknown"`. Stored tracer JSON:

```text
first_occ: Software Engineer
pres_occ: ""
current_occupation: ""
alignment_status: Unknown
alignment_detail: No job title was provided for alignment.
soc_code: ""
```

The same flow with `pres_occ: "Software Engineer"` returned **Aligned / 100**. Validation accepts `first_occ`; persist ignores it.

### HIGH-05 — Alembic

Startup log:

```text
WARNING:careersense:Alembic upgrade did not run (cannot import name 'command' from 'alem
bic' (...\backend\alembic\__init__.py)). Applying runtime schema checks instead.
```

### HIGH-09 — pytest order

```text
pytest tests/test_admin_ops.py::test_approve_and_reject_update_queue_and_dashboard
       tests/test_registration.py::test_duplicate_email_pending_message
       tests/test_authorization.py::test_pending_alumni_blocked_from_dashboard
       tests/test_alumni_jobs.py::test_pending_alumni_blocked_from_jobs
→ 1 passed, 3 failed
```

Full suite: **90 passed, 3 failed** (same three).

### Authorization (live seed users)

| Actor | Dashboard | Jobs | Profile | GTS | Notes |
|---|---|---|---|---|---|
| Admin | 200 (admin) | — | — | — | OK |
| Maria (Active) | 200 | 200 | 200 | 400 if incomplete | OK |
| Juan (Pending) | 403 | 403 | 200 | 400 if incomplete (endpoint allowed) | Portal lockout OK; GTS still open to Pending |
| Ana (Rejected) | 403 | 403 | **200** | 403 | MED-04: profile, resumes, alignment preview still allowed |

---

## Findings

### HIGH-01 — Official alignment is Unknown when present job is first

**Area:** GTS persist / career alignment  
**Status:** Open — live confirmed  
**Where:**

- `backend/app/survey_default.py` — `pres_occ` visible only when `present_job_is_first == "No"`
- `frontend/src/components/GtsSchemaForm.jsx` — validates `first_occ` in that case; submit payload is `{ ...form }` with no copy into `pres_occ`
- `backend/app/services/validation.py` `validate_employed_job_title` — allows `pres_occ or first_occ`
- `backend/app/services/gts.py` — `job_title = survey_data.get("pres_occ") or survey_data.get("current_occupation") or ""`

**Two failure modes**

1. **Empty hidden field (live).** Graduate fills Occupation (first job) only. Persist sets `current_occupation=""`. `analyze_career_alignment` returns Unknown because no job title was provided.
2. **Stale hidden field.** Parser often prefills both `first_occ` (first experience) and `pres_occ` (current experience). The form hides `pres_occ` but still submits it. Official SOC uses the hidden current title even if the graduate edited the visible first-job title.

**Repro (mode 1)**

1. Register or call `/register/complete`.
2. Currently employed = Yes; present job is also first job = Yes.
3. Fill Occupation (first job) only; leave present occupation empty.
4. Submit.

**Expected:** Alignment uses the first-job title as the current occupation.  
**Actual:** Submit succeeds. Official occupation is empty. SOC alignment is Unknown.

Registration tests send **both** `first_occ` and `pres_occ`, so this path is untested in pytest.

**Suggested fix:** When `is_currently_employed == Yes` and `present_job_is_first != "No"`, persist `job_title` as `pres_occ or first_occ`. Optionally copy that value back into `pres_occ` / `current_occupation` before save so reports, hub, and timeline agree. Add a test that sends only `first_occ`.

---

### HIGH-02 — “Present job is first” inferred from employer only

**Area:** Resume parser → GTS prefill  
**Status:** Open  
**Where:** `backend/app/services/parser.py` `map_to_gts_fields` (~687–692)

Same employer (case-insensitive) → `present_job_is_first = "Yes"`. Titles are not compared.

**Repro:** Resume with Junior Developer at Acme (ended) then Software Engineer at Acme (Present).

**Expected:** Present job is first = No.  
**Actual:** Yes → present occupation fields hidden. Combined with HIGH-01, the current title can be dropped or silently used from the hidden field.

**Suggested fix:** Treat as the same job only when employer **and** normalized title match (or a single current role exists).

---

### HIGH-03 — Closed survey still accepts registration complete

**Area:** Registration / survey policy  
**Status:** Open  
**Where:**

- `backend/app/routers/auth.py` `complete_registration` — `survey_is_open` is imported for `/options` only; complete does not call it
- `backend/app/routers/alumni.py` `POST /gts` — open / read-only checks run only if status is **Active**
- `frontend/src/pages/public/Register.jsx` — `usePublishedSurvey` loads `survey_open` but does not pass `closedMessage` / `readOnly` (alumni Resume page does)

**Repro:** Admin sets the published GTS to not accepting responses. A new graduate can still upload a resume and submit the tracer. Pending alumni can `POST /api/alumni/gts` while Active alumni are blocked.

This pass: live `survey_open` was `true`, so the closed path was not exercised on the running server.

**Suggested fix:** Enforce `survey_is_open` (and optionally `allow_alumni_edit`) on `/register/complete` and on Pending `POST /gts`. Wire Register to the same closed/read-only UI as Resume.

---

### HIGH-04 — Matched university record silently unlinked at complete

**Area:** Registration  
**Status:** Open  
**Where:** `backend/app/routers/auth.py` (~249–253)

Step 1 can return `matched_record.student_id`. On complete, if that ID is already linked, `linked_id` is set to `None` with no error. Account is Pending, `is_verified=False`.

**Expected:** Block complete, or tell the graduate and OAAPS the ID is already linked.  
**Actual:** UI promised a match the stored account does not have.

---

### HIGH-05 — Alembic never runs (local package shadows the library)

**Area:** Schema / deployment  
**Status:** Open — runtime confirmed  
**Where:** `backend/alembic/__init__.py`, `backend/app/main.py` `_run_alembic`

From `backend/`, `from alembic import command` imports the empty **local** package. Startup warns and falls back to `ensure_runtime_schema()`. Versioned files under `backend/alembic/versions/` are skipped.

**Suggested fix:** Rename the scripts folder (for example `alembic_migrations`) and point `alembic.ini` `script_location` at it so `import alembic` resolves to the installed library.

---

### HIGH-06 — Job timeline never follows later GTS saves

**Area:** Alumni jobs vs tracer  
**Status:** Open  
**Where:** `backend/app/services/jobs.py` `ensure_job_timeline`; GTS persist does not write `AlumniJob`

Timeline is imported **once** (when `job_timeline_ready` is false) from resume experiences or latest GTS. Later tracer edits do not update jobs. Dashboard job history can disagree with the official tracer.

`_jobs_from_gts` also ignores present occupation when `present_job_is_first` is Yes, so HIGH-01 and HIGH-06 stack.

---

### HIGH-07 — New resume upload wipes custom GTS extras in the form

**Area:** Alumni Resume & Tracer  
**Status:** Open  
**Where:** `frontend/src/pages/alumni/Resume.jsx` (~57)

```js
setFormSeed({ ...data.gts_prefill, extra_answers: data.gts_prefill?.extra_answers || {} });
```

Parser prefill has no extras. Saving without re-entering Survey Manager extras overwrites `TracerSubmission.extra_answers`. Registration complete **does** persist extras if the client sends them.

---

### HIGH-08 — Admin Perks “Expired” filter is inverted

**Area:** Admin Perks  
**Status:** Open  
**Where:** `frontend/src/pages/admin/Perks.jsx` (~120)

```js
if (expiry === "expired" && row.valid_to && new Date(row.valid_to) < new Date()) return false;
```

That **excludes** expired rows. Filter “Expired” shows non-expired (and undated) perks instead.

**Suggested fix:** Return false when the row is **not** expired (or has no `valid_to`).

---

### HIGH-09 — Session-scoped tests approve Juan and break later pending checks

**Area:** Automated tests / CI  
**Status:** Open — runtime confirmed  
**Where:** `backend/tests/conftest.py` (session-scoped client/DB), `test_admin_ops.py` `test_approve_and_reject_update_queue_and_dashboard`

That test creates a throwaway pending user, then **approves another pending queue row** (seed Juan). After that:

- `test_duplicate_email_pending_message` expects “awaiting review”, gets “already exists”
- Pending dashboard/jobs tests expect **403**, get **200**

Authorization is not what the full suite claims.

**Suggested fix:** Function-scoped DB, or approve only the account created inside the test, or restore Juan to Pending in teardown.

---

### MED-01 — Registration step 3 can still be skipped (residual)

**Status:** Residual  
**Where:** `frontend/src/App.jsx` `RegisterGate`; `frontend/src/lib/registerSession.js`

`markJustRegistered()` is called before `login()`, so Pending users stay on `/register` step 3. If `sessionStorage` throws (private mode / quota), `justRegistered()` is false and the gate still sends them to `/pending`. Functionally they land in the correct pending state; the designed confirmation step is skipped.

---

### MED-02 — Password field does not match server rules

**Status:** Fixed  
Client `passwordIsValid` requires 8+ characters, a letter, and a number before upload (`userMessages.js`, `Register.jsx` `validateStep1`). Server `validate_password_strength` still enforces the same rule (live letters-only register returned 400). HTML `minLength={8}` remains; JS blocks the old “upload then 400” path.

---

### MED-03 — Compound given names break name-only university match

**Status:** Open  
**Where:** `parser_extract.py` `_split_name` (three-word name → `first_name` is two tokens); `auth.py` `match_university_record` (exact first + last)

Example: `Sean Gabriel Santos` → first_name `Sean Gabriel`. Registry `Sean` + `Santos` does not match. Email match still works.

---

### MED-04 — Rejected alumni can still call several alumni APIs

**Status:** Open — live confirmed (Ana)  
**Where:** `require_alumni` is role-only (`deps.py`).

| Endpoint | Rejected (live) |
|---|---|
| `GET /api/alumni/profile` | 200 |
| `GET /api/alumni/resumes` | 200 |
| `POST /api/alumni/alignment/preview` | 200 |
| `POST /api/alumni/gts` | 403 |
| Dashboard / jobs | 403 |

UI keeps them on `/rejected`. API lockout is incomplete.

---

### MED-05 — Rate limits trust `X-Forwarded-For`

**Status:** Open  
**Where:** `backend/app/rate_limit.py` `client_ip`

The first XFF hop is the limiter key. If the process sees raw client headers, login/register limits can be bypassed by rotating the header. Tests cover the limiter itself with a lowered cap; they do not cover XFF spoofing.

---

### MED-06 — Oversized resumes are fully buffered; failed parses can orphan files

**Status:** Open  
**Where:** `auth.py` / `alumni.py` `await resume.read()` then `write_bytes`; size check is after the body is in memory (`files.py`). Type is validated; size is not checked until `write_bytes`.

A later parse/DB failure can leave a file under `uploads/drafts/` with no draft row. The registration dropzone now rejects >10 MB in the browser; API clients and alumni re-upload still buffer first.

---

### MED-07 — Parallel register for the same email can 500

**Status:** Open  
**Where:** unique `RegistrationDraft.personal_email`; delete-then-insert with no `IntegrityError` handling on `db.commit()`.

Two simultaneous `/register` calls for a new email can hit the unique constraint.

---

### MED-08 — Reports “degree-related jobs” overcounts vs OAAPS logic

**Status:** Open  
**Where:** `backend/app/routers/admin.py` snapshot vs `reports.py` `_relatedness`

Dashboard snapshot increments when `present_related_degree` **or** `first_related` is Yes, including unemployed graduates. OAAPS export uses employment-aware relatedness.

---

### MED-09 — Parser always overwrites `related_to_degree`

**Status:** Open  
**Where:** `parser.py` normalize — every experience gets `_infer_related_to_degree`; current job is then overwritten from `course_alignment`.

Unknown course alignment can blank `present_related_degree` even if a job-level value existed.

---

### MED-10 — SOC badge and course alignment can disagree

**Status:** Open  
**Where:** alumni resume upload returns SOC `alignment` plus `parsed.course_alignment`

GTS persist uses the SOC path (course fallback only when SOC has no match). The UI can show two stories for the same upload. Registration `AlignmentHint` uses **course** alignment (see MED-13), not the official SOC result.

---

### MED-11 — Profile hub prefers first-job relatedness unless present is explicitly “No”

**Status:** Open  
**Where:** `backend/app/services/alumni_hub.py` (~509–513)

If `present_job_is_first` is Yes or blank, hub relatedness uses `first_related` first. Current-job relatedness can be ignored.

---

### MED-12 — Survey Manager extras are not synced into `GtsQuestion`

**Status:** Open  
**Where:** `surveySchema.js` extra keys like `q_<uuid>`; `survey.py` `_sync_extra_questions` only updates digit keys

Live alumni forms still use published JSON. Legacy `/api/admin/questions/{int}` cannot manage Survey Manager extras.

---

### MED-13 — Alignment hint status does not follow edited occupation (new)

**Area:** Registration GTS UI  
**Status:** Open  
**Where:** `Register.jsx` passes `result.parsed_resume.course_alignment`; `GtsSchemaForm` computes `currentOccupation` live but `AlignmentHint` still uses the resume status.

The occupation **label** updates as the graduate types. Aligned / Review recommended / Unable to determine does **not**. Copy says it is a resume suggestion, but the badge can contradict the title shown next to it. Official alignment is still SOC on persist (HIGH-01 / MED-10).

---

### LOW-01 — Further-studies default “No” cleared by empty prefill

**Status:** Open  
**Where:** `frontend/src/lib/surveySchema.js` `emptyFormFromSchema`

Parser sends `enroll_further_studies: ""`. Spread of `initial` overwrites schema default `"No"`. The select can be left blank.

---

### LOW-02 — Alumni success alerts do not auto-dismiss

**Status:** Open  

Admin pages clear flash in ~4.5s. Alumni Perks / Resume / Card / Account / Dashboard success alerts stay until the next action.

---

### LOW-03 — Session-expired notice on login is styled as an error (new)

**Status:** Open  
**Where:** `frontend/src/pages/public/Login.jsx` — `location.state.notice` seeds `error`; always rendered as `<Alert type="error">`

Pending “Refresh status” on an expired session navigates to login with “Your session expired. Please sign in again.” That is informational, not a failed sign-in.

---

## Scenario matrix

Legend: **Pass** = observed OK · **Fail** = defect · **Code** = not hit live this pass, confirmed in source · **N/R** = not run (would mutate survey policy or need browser)

### Registration and accounts

| Scenario | Result | ID |
|---|---|---|
| Step 1 creates draft only (`account_created: false`) | Pass (live) | — |
| Account created on complete as Pending + access JWT | Pass (live) | — |
| Registration JWT vs access JWT mix-up | Pass (pytest) | — |
| Invalid email rejected | Pass (pytest) | — |
| Letters-only password rejected by API | Pass (live) | MED-02 fixed |
| Client blocks letters-only password before upload | Pass (code) | MED-02 fixed |
| Duplicate Active email | Pass (pytest, isolation) | — |
| Duplicate Pending email | Fail after admin-ops (suite) / Pass if Juan still Pending | HIGH-09 |
| Access token cannot call complete | Pass (pytest) | — |
| Present = first, only `first_occ` | Fail (live Unknown) | HIGH-01 |
| Present = first, both titles filled | Pass (live Aligned) | HIGH-01 control |
| Closed survey blocks complete | Fail (code); N/R live (`survey_open` true) | HIGH-03 |
| Register UI read-only when closed | Fail (code) | HIGH-03 |
| Matched student ID already in use | Fail (code, silent unlink) | HIGH-04 |
| Wizard step 3 after complete | Residual (sessionStorage) | MED-01 |
| Compound given name vs registry | Fail (code) | MED-03 |
| Parallel same-email register | Fail (code) | MED-07 |
| Oversized resume API | Fail (code, buffered) | MED-06 |
| Client dropzone >10 MB | Pass (code) | MED-06 mitigated in UI |

### Authorization

| Scenario | Result | ID |
|---|---|---|
| Unauthenticated admin routes 401 | Pass (pytest) | — |
| Active alumni dashboard/jobs | Pass (live Maria) | — |
| Pending blocked from dashboard/jobs | Pass (live Juan); Fail after HIGH-09 in suite | HIGH-09 |
| Pending may GET profile | Pass (by design for status pages) | — |
| Pending may POST `/gts` even if survey closed | Fail (code) | HIGH-03 |
| Rejected blocked from dashboard/jobs/GTS | Pass (live Ana) | — |
| Rejected GET profile / resumes / alignment preview | Fail (live Ana) | MED-04 |
| Resume download IDOR (other id) | Pass (404, pytest + owned-file check) | — |
| Authz uses DB status, not JWT status | Pass (code; Refresh status) | — |
| CSV formula sanitization | Pass (pytest) | — |

### Parser, GTS, alignment

| Scenario | Result | ID |
|---|---|---|
| Parser isolation tests | Pass (in full suite except polluted authz tests) | — |
| Employer-only “present is first” | Fail (code) | HIGH-02 |
| Relatedness overwritten in normalize | Fail (code) | MED-09 |
| SOC vs course_alignment on upload | Fail (code) | MED-10 |
| Hub relatedness prefers first job | Fail (code) | MED-11 |
| Empty occupation → Unknown | Pass (by design; triggered wrongly by HIGH-01) | — |
| GTS section titles keep spaces | Pass (code: `T()` identity) | Fixed |
| Yes/No radios not merged visually | Pass (code: choice-option + input exclusion) | Fixed |
| Alignment hint follows edited title **status** | Fail (code) | MED-13 |
| Confirm-submit on register only | Pass (by design) | — |
| Resume re-upload clears extras | Fail (code) | HIGH-07 |
| Empty further-studies prefill clears default No | Fail (code) | LOW-01 |
| Core section keys still `general/employment/studies/feedback` | Pass | — |

### Alumni portal

| Scenario | Result | ID |
|---|---|---|
| Job timeline imported once | Fail (code) | HIGH-06 |
| Later GTS save updates jobs | Fail (code, never written) | HIGH-06 |
| Success alerts auto-dismiss | Fail (alumni pages) | LOW-02 |
| Password change hints letters+numbers | Pass (Account.jsx + server) | — |

### Admin

| Scenario | Result | ID |
|---|---|---|
| Dashboard / approvals / tracer detail | Pass (pytest + live admin dashboard) | — |
| Approve / reject / 422 short reason / 409 reject Active | Pass (pytest; pollutes Juan) | HIGH-09 |
| Perks Expired filter | Fail (code, inverted) | HIGH-08 |
| Reports degree-related snapshot | Fail (code, overcount) | MED-08 |
| Survey extras → GtsQuestion | Fail (code, digit keys only) | MED-12 |
| Alembic upgrade on startup | Fail (live warning) | HIGH-05 |

### Rate limit / security notes (not expanded into new Highs)

| Scenario | Result | ID |
|---|---|---|
| Login limiter trips when enabled | Pass (pytest) | — |
| Limiter key = first XFF hop | Fail (code) if proxy headers are untrusted | MED-05 |
| No `dangerouslySetInnerHTML` in app `src` | Pass | — |
| Resume type sniff (PDF/DOCX/TXT mismatch) | Pass (code `files.py`) | — |
| Dev `SECRET_KEY` warning | Expected in this environment | Ops, not filed |

---

## What was checked and is working as designed

| Topic | Result |
|---|---|
| Account created only after GTS submit | Draft first; live `account_created: false` |
| Registration token vs access JWT | Separate `typ`; tests cover mix-up |
| Authorization uses DB status | Approve updates DB; `/me` Refresh works |
| Pending cannot open alumni dashboard/jobs | Live Juan 403 (until HIGH-09 pollutes tests) |
| Rejected cannot submit GTS or open portal | Live Ana 403 on GTS / dashboard / jobs |
| CSV formula sanitization | `csv_safe` on export; covered by test |
| Skills on `GtsPayload` | Field exists; duplicates normalized |
| Extra answers on registration complete | Persist if the client sends them |
| Resume download scoped to owner | 404 for unknown / other account |
| Password letters + numbers | Server + new Register UI |
| GTS radio/checkbox layout after UI work | Labels no longer concatenated; radios not full-width |
| Frontend routes `/`, `/login`, `/register` | HTTP 200 |
| Health endpoint | `{ ok: true, service: CareerSense }` |

---

## Suggested test gaps (not defects by themselves)

- GTS submit with `present_job_is_first=Yes` and **only** `first_occ` (now proven live; still missing from pytest)
- Hidden `pres_occ` vs edited `first_occ` (HIGH-01 mode 2)
- Closed survey + `/register/complete` and Pending `POST /gts`
- Student ID already linked at complete
- Perks expiration filter
- Full pytest order (admin-ops before pending-alumni tests) as a **blocking** CI case
- Resume re-upload preserving `extra_answers`
- Parallel `/register` unique constraint
- XFF spoof vs rate limit
- Browser matrix: Register step 3, GTS radios at 375px / 768px / 1280px, Perks Expired filter click, closed-survey banner

---

## Priority order for fixes

1. **HIGH-01 + HIGH-02** — official current occupation / alignment (live production-data bug)
2. **HIGH-05** — Alembic package name (migrations will silently never apply)
3. **HIGH-03** — survey closed policy on registration and Pending GTS
4. **HIGH-08** — Perks expired filter (false admin UI)
5. **HIGH-09** — test isolation (CI currently cannot trust pending-authz tests)
6. **HIGH-06 / HIGH-07** — timeline + extras integrity
7. **HIGH-04** — honest registry matching
8. **MED-04 / MED-05** — Rejected API lockout and trusted-proxy rate limit
9. **MED-08–13** — reports, parser relatedness, dual alignment signals, hint freshness
10. **LOW-01–03** — defaults, alert dismiss, login notice tone

---

## Sign-off

This inspection combined static review, the full backend pytest suite, Alembic import, and targeted live HTTP probes (health, options, login, authorization, and two registration completes). It did **not** include a full interactive browser pass of every admin screen.

Do not treat tracer **alignment percentages** or **schema migrations** as reliable until HIGH-01 and HIGH-05 are fixed. Do not treat a green full pytest run as proof of pending-alumni lockout until HIGH-09 is fixed.

**Not started:** product code changes. This document is QA only.
