# OCRDocFlow mobile apps (Android and iOS) — setup guide

The Android and iOS apps are the **same web app** (`frontend/`) packaged
inside an app shell with [Capacitor](https://capacitorjs.com). There is
one codebase: a change to the web app reaches the apps the next time you
rebuild them.

| Where | What |
|---|---|
| `frontend/capacitor.config.ts` | App name and ID (`com.qumaxa.ocrdocflow`) |
| `frontend/android/` | The Android project (open it in Android Studio) |
| `frontend/ios/` | The iOS project (open it in Xcode, on a Mac) |
| `frontend/src/native.ts` | The few places where the app behaves differently from the website |

## Status — what has and has not been checked

- The web app still builds and type-checks with the mobile changes in it.
- The Android and iOS projects were **generated** on a Windows PC.
- **The Android app has not been built or run yet.** The PC it was made on
  had no Java and no Android SDK. Follow "Android" below on a PC that has
  Android Studio.
- **The iOS app has not been built or run.** That can only be done on a
  Mac. Follow "iOS" below.
- The in-app PDF preview was tested in a desktop browser only. The camera
  button, the share sheet for downloads and the "open website" button need
  a real phone or an emulator to test — see the checklist at the end.

## One server step before the apps can log in

The apps call the live API at `https://ocrdocflow.qumaxa.com`. The API
only answers pages it knows, so `backend/app/main.py` now also allows the
two addresses the apps use (`https://localhost` for Android,
`capacitor://localhost` for iOS).

**That change must be deployed once** (`deploy/redeploy.sh`) before any
app can log in or upload. Until then the app opens but every request
fails. Nothing else on the server changes.

## How the app differs from the website

| Thing | Website | App |
|---|---|---|
| Server address | Same site (`/api/...`) | Always `https://ocrdocflow.qumaxa.com` |
| Upload | Choose or drag a file | Choose a file, or **Take a photo of the invoice** (large photos are shrunk before sending) |
| Download CSV / Excel | Normal browser download | The phone's share sheet opens: save to Files/Drive, email it, or open in Excel |
| Original document in the review screen | PDF shown in a frame | PDF pages drawn as pictures (a phone app cannot show a PDF in a frame) |
| Billing | Plans + Stripe checkout | Shows current plan and usage only; a button opens the website in the phone's browser |
| Login | Stays logged in in the browser | Stays logged in on the phone (stored inside the app) |

**Subscriptions.** The app sells nothing, so there is no Apple or Google
in-app purchase and no store commission. People buy a plan on the website
and simply sign in to the app. Do not add prices or a "Subscribe" button
to the app screens: Apple can reject an app that sells a digital
subscription outside its own payment system.

Long uploads (a minute or more) are fine: the app waits as long as the
website does.

---

## What you need installed

For both apps, on the computer that builds them:

- **Node.js 22 or newer** and this repository.
- Run once: `npm --prefix frontend install`

### Android (Windows, Mac or Linux)

- **Android Studio** (free): https://developer.android.com/studio
  Its installer also installs Java and the Android SDK. Accept the
  licences when it asks, and let it download "Android SDK Platform 36".
- The app works on Android 7.0 and newer.

### iOS (Mac only)

- A **Mac** with **Xcode** (free, from the Mac App Store). Apple does not
  allow building iPhone apps on Windows.
- An **Apple Developer account** (US$99 per year) to put the app on a
  real iPhone for more than a few days and to publish it.
- The app works on iOS 15 and newer.

---

## Android

### Run it (test build)

```bash
npm --prefix frontend run mobile:android
```

This builds the web app, copies it into the Android project and opens
Android Studio. In Android Studio wait for "Gradle sync" to finish, pick
a phone (an emulator, or a real phone connected by USB with "USB
debugging" switched on) and press the green **Run** button.

To only produce a test APK file without opening Android Studio:

```bash
npm --prefix frontend run mobile:sync
```

```bash
cd frontend/android && ./gradlew assembleDebug
```

The file appears at
`frontend/android/app/build/outputs/apk/debug/app-debug.apk`. You can
copy that to an Android phone and install it for testing. It cannot go on
Google Play.

### Signed release (for Google Play)

You do these steps yourself — they involve passwords only you should know.

1. **Create your upload key (once).** In a terminal, inside
   `frontend/android`:

   ```bash
   keytool -genkeypair -v -keystore ocrdocflow-upload.jks -alias ocrdocflow -keyalg RSA -keysize 2048 -validity 10000
   ```

   It asks for a password and your name/company. (`keytool` comes with
   Android Studio's Java.)
2. **Tell the build about it.** Copy
   `frontend/android/keystore.properties.example` to
   `frontend/android/keystore.properties` and put your passwords in it.
3. **Keep both files safe and backed up**, outside the repository too.
   They are ignored by git on purpose. If you lose the key you must ask
   Google to reset it before you can publish updates.
4. **Raise the version** for every new upload: in
   `frontend/android/app/build.gradle`, add 1 to `versionCode` and set
   `versionName` (for example `1.1`).
5. **Build the release:**

   ```bash
   npm --prefix frontend run mobile:sync
   ```

   ```bash
   cd frontend/android && ./gradlew bundleRelease
   ```

   The file for Google Play is
   `frontend/android/app/build/outputs/bundle/release/app-release.aab`.
   (For a signed APK to hand to someone directly, use
   `./gradlew assembleRelease` instead.)

### In the Google Play Console (you do this)

1. Create a developer account at https://play.google.com/console —
   **US$25, paid once**. For a company account Google asks for a D-U-N-S
   number and verifies the business; allow some days.
2. **Create app** → name "OCRDocFlow", type App, Free.
3. Fill in the required forms: privacy policy link, "Data safety" (the
   app collects email/name for the account and the documents users
   upload), content rating, target audience, and login details for a
   **test account** so Google's reviewers can sign in.
4. Store listing: short and full description, app icon (512×512),
   feature graphic (1024×500), at least two phone screenshots.
5. Upload `app-release.aab` under **Testing → Internal testing** first,
   install it from the test link and try it. Then promote it to
   Production and send it for review.
6. Note: a brand-new *personal* developer account must run a closed test
   with at least 12 testers for 14 days before Google allows a production
   release. Company accounts do not have this rule.

---

## iOS (on a Mac)

The iOS project in `frontend/ios` was generated on Windows and has never
been opened in Xcode. The first build on a Mac is where any problem will
show up.

### Run it

1. Get the repository onto the Mac, then:

   ```bash
   npm --prefix frontend install
   ```

   ```bash
   npm --prefix frontend run mobile:ios
   ```

   This builds the web app, copies it into the iOS project and opens
   Xcode. Xcode downloads the Capacitor packages by itself the first time
   (no CocoaPods needed).
2. In Xcode click **App** in the left panel → **Signing & Capabilities**
   → tick "Automatically manage signing" and choose your **Team** (your
   Apple Developer account).
3. Pick an iPhone simulator, or your own iPhone connected by cable, at
   the top and press **Run** (▶).

### Build for the App Store

1. In Xcode, under **App → General**, set **Version** (for example `1.0`)
   and **Build** (`1`, then add 1 for every upload).
2. At the top choose the device **Any iOS Device (arm64)**.
3. Menu **Product → Archive**. When it finishes the Organizer window
   opens: **Distribute App → App Store Connect → Upload**.

### In your Apple Developer account (you do this)

1. Enrol at https://developer.apple.com/programs/ — **US$99 per year**.
   A company enrolment needs a D-U-N-S number; allow some days.
2. At https://appstoreconnect.apple.com → **Apps → +** → New App: name
   "OCRDocFlow", bundle ID `com.qumaxa.ocrdocflow` (register it under
   Certificates, Identifiers & Profiles if it is not in the list).
3. After the upload from Xcode, the build appears under **TestFlight**.
   Install the TestFlight app on an iPhone and test there first.
4. Fill in the listing: description, keywords, support and privacy
   policy links, screenshots (6.9" iPhone at least; iPad too unless you
   switch iPad off in Xcode), "App Privacy" answers (account email/name
   and uploaded documents), and a **test account** for Apple's reviewer.
5. In the review notes, say plainly: "This is a companion app for an
   existing business service. Accounts and plans are managed on our
   website; the app offers no purchases." Then submit for review.

---

## Things you will want to do before publishing

- **App icon and splash screen.** Both projects still have Capacitor's
  default icon. Put a 1024×1024 `icon.png` (and optionally a 2732×2732
  `splash.png`) in `frontend/assets/`, then run
  `npx @capacitor/assets generate` inside `frontend/` and rebuild.
- **Privacy policy page** on the website — both stores require a link.
- **How long a login lasts.** The server setting
  `ACCESS_TOKEN_EXPIRE_MINUTES` decides when a user is asked to log in
  again. The example file shows 15 minutes, which is short for a phone
  app; check the live value in `backend/.env` on the server.

## After you change the web app

The apps do not update by themselves. For each new version: raise the
version number, build again (`mobile:sync`, then the release steps above)
and upload to both stores. Server-only changes (the API) reach the apps
immediately, with no new app version.

## First-test checklist (on a real phone or emulator)

- [ ] Log in, close the app completely, open it again — still logged in.
- [ ] Upload a PDF from the phone's files; wait through a slow upload.
- [ ] "Take a photo of the invoice" opens the camera and uploads the photo.
- [ ] Review screen: original document shows (PDF and photo), fields edit and save.
- [ ] Arabic or Urdu document: review screen reads right-to-left.
- [ ] Download CSV and Excel: share sheet opens, file opens in Excel/Sheets.
- [ ] Billing: shows plan and usage; the button opens the website in the browser.
- [ ] Team and Admin pages (including "Usage & costs") open and scroll sideways where tables are wide.
- [ ] Nothing is hidden behind the notch, status bar or home bar.
