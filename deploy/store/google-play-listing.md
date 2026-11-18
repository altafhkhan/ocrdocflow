# OCRDocFlow — Google Play listing pack

Everything to copy into the Google Play Console when you create the app.
Prepared 2026-11-19 for version 1.0 (build 1). Nothing here has been
submitted; you paste it in yourself.

Files in this folder:

| File | Where it goes in the Play Console |
|---|---|
| `../../frontend/assets/play-store-icon-512.png` | Store listing → App icon |
| `feature-graphic-1024x500.png` | Store listing → Feature graphic |
| `screenshots/01` … `06` (1080 × 1920) | Store listing → Phone screenshots |
| `D:\Android\release\OCRDocFlow-1.0-build1.aab` | Testing / Production → Create release |

The screenshots show made-up invoices from fictional companies. They were
taken from the app's own screens running on a PC at phone size, not on a
handset, so there is no Android status bar in them. Google accepts that.

---

## Store listing

**App name** (30 characters max)

```
OCRDocFlow: Invoice Scanner
```

**Short description** (80 characters max)

```
Scan invoices, check the extracted data, and export to CSV or Excel.
```

**Full description** (4,000 characters max)

```
OCRDocFlow turns paper and PDF invoices into clean data you can use.

Take a photo of an invoice or choose a PDF or image from your phone.
OCRDocFlow reads it and fills in the invoice number, dates, customer or
supplier, currency, every line item, tax and totals. You check the
result against the original document on the same screen, correct
anything that is wrong, and save.

WHAT YOU CAN DO
• Photograph an invoice with your phone's camera, or upload a PDF, JPG
  or PNG (up to 10 MB and 10 pages).
• Read invoices in ten languages: English, Arabic, Urdu, French, German,
  Spanish, Dutch, Chinese, Japanese and Korean. Arabic and Urdu are shown
  right to left.
• See the original document next to the extracted fields, so checking is
  quick.
• Handle files that contain more than one invoice.
• Download your saved invoices as CSV or Excel, one row per line item,
  ready for your accounting or ERP software. Share the file by email or
  save it to your phone or cloud drive.
• Work as a team: invite colleagues to your organization so everyone
  sees the same invoices.
• Use the same account on your phone and at ocrdocflow.qumaxa.com.

HOW IT WORKS
1. Upload or photograph an invoice.
2. OCRDocFlow reads it — usually in under a minute.
3. Review the fields beside the original and press Save.
4. Export the saved invoices whenever you need them.

GOOD TO KNOW
• You stay in control: nothing is exported until you have reviewed and
  saved it. Automatic reading is not perfect, especially with
  handwriting or poor photos, so always check the result.
• You can try OCRDocFlow without an account, then create a free account
  to save and export your invoices.
• An internet connection is required. Documents are processed on our
  servers, not on the phone.

OCRDocFlow is made by Qumaxa IT Services.
Questions: contact@qumaxa.com
```

**Category:** Business  **Tags:** Business, Productivity, Finance

**Contact details**

| Field | Value |
|---|---|
| Email | contact@qumaxa.com |
| Website | https://ocrdocflow.qumaxa.com |
| Privacy policy URL | https://ocrdocflow.qumaxa.com/privacy |

The privacy page must be live (deployed) before you save the listing —
Google checks that the link opens.

---

## App content (the questionnaires)

### Privacy policy
`https://ocrdocflow.qumaxa.com/privacy`

### Ads
No, the app contains no ads.

### App access
Choose **"All or some functionality is restricted"** and give Google a
login it can use:

- Create a separate account for reviewers at ocrdocflow.qumaxa.com (for
  example `play-review@qumaxa.com`) and enter its email and password in
  this form. Do not give your own admin login.
- Instructions to add: *"Open the app, tap Log in, enter the details
  above. Tap 'Tap to choose a PDF or image invoice' or 'Take a photo of
  the invoice' to upload. Reading can take up to a minute. Then tap
  'Review & Save'."*

### Content rating
Category: **Utility, Productivity, Communication or Other**. Answer
**No** to every question (violence, sexual content, language, drugs,
gambling, user-to-user communication, sharing location, digital
purchases). Expected rating: Everyone / PEGI 3.

### Target audience
**18 and over** only. The app is not designed for children.

### News app / COVID-19 / Government / Financial features / Health
No to all. (It reads invoices; it does not provide banking, loans,
payments or financial advice.)

### Data safety

"Does your app collect or share any of the required user data types?" →
**Yes.**
"Is all of the user data collected by your app encrypted in transit?" →
**Yes.**
"Do you provide a way for users to request that their data is deleted?"
→ **Yes**, URL below.

| Data type | Collected | Shared | Why | Required? |
|---|---|---|---|---|
| Personal info → Email address | Yes | No | App functionality, Account management | Required |
| Personal info → Name | Yes | No | App functionality, Account management | Optional |
| Files and docs → Files and docs | Yes | **Yes** | App functionality | Required |
| Photos and videos → Photos | Yes | **Yes** | App functionality | Optional |
| Financial info → Other financial info | Yes | **Yes** | App functionality | Required |
| App activity → Other user-generated content | Yes | No | App functionality | Required |

Why "Shared = Yes" for documents, photos and invoice contents: the files
are sent to Google's Gemini API to be read, and on the **free** Gemini
tier in use today Google may use that content to improve its own
services. That is more than acting as a service provider, so it has to
be declared as sharing. Once OCRDocFlow moves to a paid Gemini key
(where Google only processes the data for you), these three can be
changed to "Shared = No".

Not collected by the app: location, contacts, phone number, device or
advertising IDs, messages, audio, health, browsing history, crash logs
or analytics. The IP address is recorded on the server with each upload;
Google's form has no separate entry for IP addresses used this way.

### Account deletion
"Does your app allow users to create an account?" → **Yes.**
Delete account URL: `https://ocrdocflow.qumaxa.com/privacy#delete`
"Can users request that some data is deleted without deleting the
account?" → **Yes**, same URL.

Deletion today is by email request to privacy@qumaxa.com, handled by
hand. Google accepts a web page that explains the steps, but that
mailbox must exist and be read.

---

## Release notes for version 1.0

```
First release of OCRDocFlow for Android.
• Upload or photograph invoices
• Review extracted data beside the original
• Export saved invoices to CSV or Excel
```

---

## Before you submit — open points

1. **Privacy notice wording needs your approval.** It was drafted from
   what the code does (`frontend/src/pages/PrivacyPage.tsx`) and has not
   been reviewed by you or a lawyer. It is not deployed yet.
2. **privacy@qumaxa.com must be a working mailbox.** The notice and the
   deletion link depend on it.
3. **Free Gemini tier.** The notice tells users plainly that, during the
   beta, Google may use uploaded content to improve its services. Moving
   to a paid Gemini key removes that sentence and the "Shared" answers
   above.
4. **Billing button in the app.** The app's Billing screen has a button
   that opens the website's billing page. Google Play's payments policy
   restricts apps from leading users to other ways of paying for digital
   services. Safest for review is to remove that button and keep only
   the sentence that plans are managed in the account on the website.
5. **Reviewer account.** Create it before filling in "App access".
6. **Personal vs company developer account.** A new personal account
   must run a closed test with 12 testers for 14 days before production.
7. **Listing claims.** "Usually in under a minute" matches local tests
   (5–40 seconds) but the live server on the free AI tier has taken up to
   three minutes. Remove that phrase if you publish before changing tier.
