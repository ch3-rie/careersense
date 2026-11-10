# Alumni QR and the Angelenean Alumni Card

Active alumni open **Services → Alumni QR** (`/alumni/qr`) to see both their QR code and their Angelenean Alumni Card. The QR code and the card stay separate. Displaying the QR code does not apply for a card, approve one, or mark one as claimed.

The same card workspace is also available at `/alumni/card`. Home, notifications, and perk messages still link there. That page does not show the QR code.

Only an **Active** alumni account can open either page. The API uses the signed-in account. There is no account id on these requests, so one alumnus cannot load another alumnus’s QR code or card. Pending and rejected accounts are refused.

## QR code

On Alumni QR, a confirmation asks the alumnus to show the code only when they are ready for a partner to see it. **Proceed** loads the code. **Cancel** leaves the code hidden and keeps the card on the page. **Show QR code** opens the confirmation again.

The code is loaded from the signed-in account:

| Request | What it returns |
| --- | --- |
| `GET /api/alumni/qr` | Student number, full name, course, college, and year graduated |
| `GET /api/alumni/qr/image` | An SVG QR image for that same account |

The image encodes a verification address, not the name, email, or student number. The address is the public site URL plus `/verify/qr/` and a signed token `v1.{account id}.{signature}`. The public site URL comes from `EMAIL_BASE_URL`, then `FRONTEND_URL`, then `PUBLIC_APP_URL`. The signature is an HMAC of the account id with the API secret. The same account always receives the same token while that secret stays the same.

University registry values are used for the five fields beside the code. Profile values fill a field only when the registry does not have it.

Opening `/verify/qr/{token}`, or `GET /api/public/alumni-qr/{token}`, checks the signature and returns those five fields for an Active alumni account. A bad signature, or an account that is not an active alumnus, is not verified. The public page does not show the card, contact details, or employment history.

A partner scan is recorded only when an administrator submits that code through Alumni QR Usage. Opening the Alumni QR tab, or loading the image, does not record a scan, a visit, or a perk redemption, and it does not change the card status.

There is no download, save, or print action for the QR image. It is shown on the page only.

## Alumni card on the same tab

The card block is directly under the QR block. It uses `GET /api/alumni/card` for the signed-in account and the existing Angelenean Alumni Card layout.

The card face shows:

- Angeles University Foundation and the title Angelenean Alumni Card
- Name, alumni ID (the linked student number), degree, and batch (year graduated), from the alumni profile and linked student number
- The profile photo, or initials when no photo is stored
- A barcode for the card number once the card is claimed; before that, the barcode uses the student number when one is on file

The card information beside it shows the status label, card holder, alumni ID, degree, and batch. A card number appears only after the card is **Claimed**. **Valid until** appears only when the card record has an expiry date.

The QR identity prefers the university registry. The card face prefers the alumni profile. For a linked graduate those values normally match. They are still two different reads.

## Status

The status on the card is the stored `alumni_cards.status` for that account. Labels:

| Status | What the alumnus sees |
| --- | --- |
| Not yet applied | No application is on file. **Get Alumni Card** is available after the Graduate Tracer Survey is submitted. |
| For verification | The application was submitted. AAPS is reviewing it. There is no second submit. |
| Approved | AAPS approved the application and is preparing the card. |
| Ready for pickup | The card can be claimed at Alumni Affairs and Placement Services (AAPS), AUF Main Campus, during the hours shown on the page. The page also shows what ID to bring. |
| Claimed | The alumnus has the card. **Card details** opens the same card in a dialog. Partner perks that require a card can use this status. |
| For renewal | The card is due for renewal. **Apply for Renewal** uses the same application form. |

An alumnus cannot set these statuses. AAPS changes them from **Admin → Alumni Card**. The usual path is For verification → Approved → Ready for pickup → Claimed. A renewal application can be recorded as For verification again.

If the survey is not on file, **Get Alumni Card** and **Apply for Renewal** stay unavailable and the page says to submit the Graduate Tracer Survey first. Employment status is not required.

## Applying

**Get Alumni Card** or **Apply for Renewal** opens the existing application on this tab. It posts to `POST /api/alumni/card/apply` for the signed-in account.

The form shows the record already on file. Registry identity is locked. The alumnus can edit date of birth, mobile number, and home address. They must choose an open OAAPS appointment date and time. A photo is not required to submit; the page notes that a photo on Home can be printed on the card.

The API rejects the application when:

- the Graduate Tracer Survey has not been submitted
- the card is not **Not yet applied** or **For renewal**
- the selected appointment is missing, full, or no longer open

A successful submit stores the application on that alumnus’s card, sets the status to **For verification**, and sends the usual card notification. It does not print the card, assign a card number, or mark it claimed.

There is no download, save, or print action for the card. **Card details**, shown only when the status is Claimed, opens the on-screen card again.
