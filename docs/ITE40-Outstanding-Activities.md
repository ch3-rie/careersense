# ITE40 outstanding activities

Updated after the follow-up on 9 November 2026. Items that were completed in that follow-up are listed first so they are not repeated as open work.

## Completed in the follow-up

1. **TC-AUTH-003 passed.** `qa.super.95b332c6@example.com`, employee number 093, was created by Users as an add-users Admin. Its privileges were then cleared in the local database so the Users list showed Full access. The seeded Super Admin deactivated it. Sign-in stayed on `/login` and showed “This administrator account is inactive.” See `EV-AUTH-003-inactive.png`.
2. **Limited Admin navigation was captured.** `qa.admin.667341@example.com` completed the password change. The browser showed Users and Account only. Opening `/admin/approvals` returned to `/admin/users`. See `EV-AUTH-002-limited-nav.png`.
3. **Draft expiry was executed.** The draft clock was moved in the local database. Completion returned “Your resume review session expired. Please upload your resume again.” No account was created. A real 24-hour wait was not done.
4. **PIN expiry and a completed reset were executed.** The challenge clock was moved for the expiry message. The issued PIN was matched from the local hash, the new password signed in, and the previous password hash was restored. The PIN is not in the package.
5. **The last-administrator sentence was investigated.** It was not returned. Deactivating the other full administrator succeeded while two were active. Deactivating the signed-in Super Admin returned “You cannot deactivate your own account.” This is recorded in Section 9 and is not a confirmed defect.

## Still needs the group

1. Add the ITE40 group number and the names of the members.
2. Record who executed the cases and who reviewed the evidence. Section 13 does not invent that diary.
3. A second member should compare Section 8 with the files in `docs/qa-evidence/` before the defense.
4. Decide what to do with the local QA accounts listed below.

## Still not observed

1. **PIN email was not delivered.** `email_enabled` was false. The server log skipped the message, and the audit recorded `password_reset_email_failed`. The inbox was not checked.
2. **The clocks were moved.** Draft expiry and PIN expiry were not observed by waiting 24 hours or 10 minutes.
3. **The last-administrator sentence was not shown.** The outcome required by REQ-APR-02 was observed. The sentence itself was not.

## Local data the group should decide about

The local SQLite database now contains:

- University record `QA-6101f4` and Active account `qa.match.6101f451@example.com`
- Rejected account `qa.reject.6101f451@example.com`, with its previous password hash restored
- Active Admin `qa.admin.667341@example.com`, employee number 091, no longer required to change the password on sign-in
- Inactive Admin `qa.inactive.667341@example.com`, employee number 092
- Inactive Super Admin `qa.super.95b332c6@example.com`, employee number 093, full access after the local privilege change
- Registration drafts for the file-rule addresses
- No account for `qa.expire.95b332c6@example.com`

Maria’s job title was restored. Administrator rows that were already present were not modified. The hosted campus system was not changed.

## Evidence deliberately not stored

The Alumni QR image was displayed and then not saved, because the image is a signed verification value. Passwords, the issued PIN, the reset token, and the development `SECRET_KEY` used for the follow-up are not in the package tables. The execution scripts under `docs/qa-evidence/` contain local seeded passwords already printed in `docs/UAT-testing-guide.md`. Do not attach those scripts to a public copy.

## Not claimed

No product defect was confirmed. No fix was retested. The 13 September 2026 inspection and the automated suite were not used as results of these cases. A hosted build was not tested. The PIN email was not received.
