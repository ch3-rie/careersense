# CareerSense email setup

CareerSense sends transactional mail through **Resend** on the backend only. The React app never calls Resend and never receives the API key.

The API sends:

| Event | Email |
| --- | --- |
| Registration completed | Registration received |
| OAAPS approves the account | Account approved |
| OAAPS rejects the registration | Registration rejected |
| Forgot password | Password reset (6-digit PIN, 10-minute expiry) |
| Active alumni with no Graduate Tracer Survey | Graduate Tracer Survey reminder (sent once) |
| AAC application or status change | Alumni card application received / Alumni card status |
| Profile update request or automated reminder | Reminder to update profile (Admin → Profile Updates) |

Passwords, API keys, and reset tokens are never written into email bodies or application logs.

---

## Step 1 — Create a Resend account

1. Open [https://resend.com](https://resend.com) and create an account.
2. Confirm the Resend login email. That mailbox can receive Resend onboarding messages.
3. Sign in to the Resend dashboard.

---

## Step 2 — Create an API key

1. In the Resend dashboard, open **API Keys**.
2. Create a key with **Sending access** (permission to send email).
3. Copy the key once. It starts with `re_`.
4. Store it only in `backend/.env` as `EMAIL_API_KEY`.
5. Never put the key in frontend code, `VITE_*` variables, Git, screenshots, or logs.

`backend/.env` is already gitignored. `.env.example` must keep an empty `EMAIL_API_KEY=`.

---

## Step 3 — Choose a from address

### Local testing

Resend lets you send from the onboarding address:

```text
beth.t@example.com
```

Mail can be delivered to the email address on your Resend account. This is enough to prove CareerSense PIN and notice emails work before a campus domain is ready.

### Production

Do not send production alumni mail from a personal Gmail address.

Add and verify a domain you control, then send from an address on that domain, for example:

```text
noreply@auf.edu.ph
```

or a dedicated CareerSense host:

```text
noreply@careersense.auf.edu.ph
```

Set that address as `EMAIL_FROM_ADDRESS`.

---

## Step 4 — DNS authentication

In Resend, open **Domains**, add the sending domain, and create the DNS records Resend shows. Typical records:

| Type | Purpose |
|------|---------|
| **MX** or **TXT** as shown by Resend | Domain verification |
| **TXT SPF** | Authorizes Resend to send for the domain |
| **CNAME / TXT DKIM** | Signs messages so providers trust them |
| **TXT DMARC** (recommended) | Policy for spoofed mail using the domain |

Wait until Resend marks the domain **Verified**. Sending before verification fails or lands in spam.

You cannot complete DNS from this repository. The domain owner must add the records at the DNS host (campus IT, Cloudflare, registrar, and similar).

---

## Step 5 — CareerSense environment

Copy `/.env.example` values into `backend/.env` (real key only on the server):

```env
EMAIL_ENABLED=true
EMAIL_PROVIDER=resend
EMAIL_API_KEY=re_paste_the_real_key_here
EMAIL_FROM_ADDRESS=beth.t@example.com
EMAIL_FROM_NAME=CareerSense
EMAIL_REPLY_TO=
EMAIL_BASE_URL=http://localhost:5173
EMAIL_RETRY_ATTEMPTS=3
EMAIL_RETRY_BACKOFF_MS=400
EMAIL_OUTBOX_MAX_ATTEMPTS=5
EMAIL_SCHEDULER_ENABLED=
EMAIL_SCHEDULER_INTERVAL_SECONDS=60
EMAIL_TIMEZONE=Asia/Manila
```

| Variable | Where | Purpose |
|----------|--------|---------|
| `EMAIL_ENABLED` | `backend/.env` | `true` to send mail. `false` for local work without a key. |
| `EMAIL_PROVIDER` | `backend/.env` | Must be `resend` when sending is on. |
| `EMAIL_API_KEY` | `backend/.env` only | Resend secret. Never a `VITE_` variable. |
| `EMAIL_FROM_ADDRESS` | `backend/.env` | Verified sender (`beth.t@example.com` for tests). |
| `EMAIL_FROM_NAME` | `backend/.env` | Display name, default `CareerSense`. |
| `EMAIL_REPLY_TO` | `backend/.env` | Optional reply address. |
| `EMAIL_BASE_URL` | `backend/.env` | Public frontend origin used in email links. |
| `EMAIL_RETRY_ATTEMPTS` | `backend/.env` | Immediate retries for timeouts and 5xx errors. |
| `EMAIL_RETRY_BACKOFF_MS` | `backend/.env` | Delay between immediate retries. |
| `EMAIL_OUTBOX_MAX_ATTEMPTS` | `backend/.env` | Later retries for profile mail that still failed. |
| `EMAIL_SCHEDULER_ENABLED` | `backend/.env` | Blank = on when email is enabled. Set `true` or `false` to override. |
| `EMAIL_SCHEDULER_INTERVAL_SECONDS` | `backend/.env` | How often the API checks due reminders and the outbox. |
| `EMAIL_TIMEZONE` | `backend/.env` | Reminder clock. Default `Asia/Manila`. |
| `SECRET_KEY` | `backend/.env` | Used to hash password-reset PINs and tokens. Required in production. |
| `VITE_API_URL` | `frontend/.env` if used | Frontend API origin only. Do **not** put Resend credentials here. |

For campus deployment, set `EMAIL_FROM_ADDRESS` to the verified domain address and `EMAIL_BASE_URL` to the public CareerSense URL (the links inside emails).

Then **restart the API**. Changing `.env` is not applied until uvicorn restarts.

When `EMAIL_ENABLED=true`, CareerSense **refuses to start** if the key or from-address is missing or still a placeholder such as `re_your_key`.

When `EMAIL_ENABLED=false`, the API starts without credentials. Forgot-password still shows a warning that a PIN will not arrive. The UI does not claim that mail was delivered.

If you run several API worker processes, set `EMAIL_SCHEDULER_ENABLED=true` on **one** process only so scheduled reminders are not sent twice.

---

## Step 6 — Install dependencies and migrate

From the `backend` folder:

```powershell
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Alembic revision `0006_email_reminders` creates:

- `email_outbox` (retry queue for profile and reminder mail; PIN bodies are never stored)
- `profile_reminder_settings` (admin schedule and message)
- `profile_reminder_runs` / `profile_reminder_sends` (delivery history)

`ensure_runtime_schema()` also creates missing tables on API startup, so a fresh local SQLite database is enough.

Start the frontend as usual from `frontend` (`npm run dev`). Administrators use **Admin → Profile Updates**.

---

## Step 7 — Confirm the API is ready

1. Restart the API after saving `backend/.env`.
2. Open `http://127.0.0.1:8000/api/health`.
3. Confirm:
   - `email_configured` is `true`
   - `email_enabled` is `true`
   - `email_provider` is `resend`
   - `email_scheduler` is `true` when sending is on

If health is false, the from-address or API key is still a placeholder or the process was not restarted.

---

## Step 8 — Configure automated profile reminders (Admin Portal)

1. Sign in as an administrator.
2. Open **Admin → Profile Updates**.
3. Use **Automated profile reminders** (top of the page):
   - Turn **Enable automated reminder emails** on or off
   - Choose frequency: every day, every week, every month, or every N days
   - Choose send time in Asia/Manila
   - Choose the target alumni: all Active, incomplete profiles, filtered (year / program / completion), or selected people
   - Choose the profile fields to request
   - Edit the subject and message
   - Set **Minimum days between emails** so the same alumnus is not mailed too often
   - Optionally skip alumni who already completed those fields
4. Choose **Preview recipients**, then **Save reminder settings**.
5. Optional: **Send now** to run the reminder immediately (still skips recent duplicates unless you later use a forced resend from a new run with `force`).

The scheduler sends only to **Active** alumni with a valid registered `personal_email`. Pending, rejected, and admin accounts are never reminder targets. Duplicate suppression also counts a successful manual profile-update email inside the same window.

In-system alumni notifications still use the existing **Update My Profile** notice, so the alumni portal behavior does not change.

---

## How to test each email type

Use an account whose `personal_email` you can open. Seeded demo addresses such as `maria.reyes@gmail.com` will not arrive in your inbox.

### Forgot Password

1. Sign out. Open `/forgot-password`.
2. Enter the alumnus or admin registered email.
3. The page always says a PIN was sent if the request was accepted (it does not reveal whether the email exists).
4. Open the inbox. Subject: **CareerSense Password Reset Verification**.
5. The PIN is 6 digits, expires in 10 minutes, and is not the account password.
6. Enter the PIN at `/forgot-password/verify`, then set a new password.

### PIN / verification

This is the same Forgot Password message. After a correct PIN, CareerSense issues a short-lived reset token in the browser session only. The token is hashed in the database and expires in 10 minutes. Five wrong PINs lock the challenge. Resend is limited to once per minute and eight requests per hour.

If `/api/health` shows email is not configured, the verify page warns that no PIN will arrive.

### Profile reminder

1. Configure and save automated reminders as in Step 8.
2. Choose **Send now**, or wait until the next scheduled time while the API is running.
3. Confirm the inbox message and the alumni notification bell.
4. In Admin → Profile Updates, check **Recent reminder runs**.
5. In Resend, open **Emails** and confirm the message was accepted.

Manual one-off requests still use **New Update Request** on the same page.

### Account approval

Approve a pending registration in **Admin → Approvals**. The alumnus receives an approval email if sending is configured.

---

## Security rules

- Frontend JavaScript must never import the Resend SDK or the API key.
- Logs record mail kind and provider only. They do not record PINs, passwords, reset tokens, or API keys.
- Password-reset still uses a generic public response so attackers cannot probe which emails exist. Delivery still goes only to `accounts.personal_email`.
- Failed PIN emails are **not** written to `email_outbox` (the raw PIN must not be stored). Profile mail may be retried from the outbox.
- CareerSense never puts the current or new password in an email.

---

## Troubleshooting

### Emails are not delivered

1. `GET /api/health` → `email_configured` must be `true`.
2. Confirm `EMAIL_ENABLED=true` and that uvicorn was restarted.
3. Confirm `EMAIL_FROM_ADDRESS` is the Resend onboarding address or a **verified** domain address.
4. Open Resend → **Emails**. If the API rejected the message, the from-address or key is wrong.
5. Check spam. **Without a verified domain**, Resend’s free/testing mode only delivers to the email on your Resend account. Sends to any other address return HTTP 403. Alumni forgot-password and notice emails will not arrive until a domain is verified (or every recipient happens to be that Resend login mailbox).
6. Profile reminders only go to Active alumni. Preview recipients before sending.

### Invalid credentials (401 / 403 from Resend)

1. Recreate the API key in Resend and replace `EMAIL_API_KEY`.
2. Do not wrap the key in quotes that become part of the value.
3. Do not paste the key into `frontend/.env` or a `VITE_` variable.
4. Restart the API. CareerSense does not retry invalid credentials (that cannot succeed).

### Forgot Password PIN never arrives, is expired, or is locked

- PIN lifetime is **10 minutes**. Request a new PIN.
- Five incorrect attempts lock that PIN. Request a new PIN.
- Wait **60 seconds** between resends.
- The public message is always generic, even when no account exists or email sending failed.
- If email is disabled, the yellow warning on the Forgot Password page is expected.

### Failed API requests / 429

- Forgot Password is rate-limited per client IP.
- Wait a few minutes and try again.
- Application logs show `kind=` and `provider=` only.

### Scheduled reminders do not run

1. `email_scheduler` on `/api/health` must be `true`.
2. Reminders must be **enabled** and saved in the Admin Portal.
3. The API process must stay running. The scheduler is in-process (no extra worker).
4. Send time uses `EMAIL_TIMEZONE` (default Asia/Manila). A weekly reminder on Monday at 9:00 will not send on Tuesday.
5. After a successful scheduled run, the next run waits for the next slot.
6. `min_days_between` skips alumni who already received a reminder or matching profile-update email in that window.
7. If several uvicorn workers run, enable the scheduler on only one worker.
8. Use **Send now** to prove the template and Resend path independently of the clock.

### Reminder saved but status is Disabled

Email sending is off (`EMAIL_ENABLED=false` or missing key). In-system notifications can still be created; mail is not delivered until sending is configured.

### Alembic / missing tables

```powershell
cd backend
python -m alembic upgrade head
```

Restart the API. Startup also calls `ensure_runtime_schema()`.

### Frontend cannot reach the API

Set `VITE_API_URL` only if the UI is not served through the Vite proxy. This is not an email credential.
