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

Last updated 2026-11-18.

**Android — built and run on a virtual phone (emulator, Android 15).**
- The test APK builds on the Windows PC (tools in `D:\Android`, see
  "Android tools already on this PC").
- Tested in the app against the **live** server, without logging in:
  choosing a PDF from the phone's files, upload and reading ("done"),
  the result screen, CSV download through the share sheet, and the
  "Take a photo of the invoice" button opening the camera.
- Tested in the app against the **local test** server, logged in with a
  test account: dashboard, upload, the Review & Save screen with the
  original PDF drawn beside the fields, and saving.
- **Not tested yet:** the in-app Billing screen and its "open website"
  button, the Excel download while logged in, Team/Admin pages, an
  Arabic/Urdu document, and anything on a **real** phone.
- Seen during testing: a photo with no invoice in it (the emulator's
  empty room) kept the live server busy for over 3 minutes until it
  timed out. The app now shows a clear message when that happens. A real
  invoice photo has not been tried.
- A signed release (version 1.0, build 1) was built and its signature
  verified on 2026-11-19: `D:/Android/release/OCRDocFlow-1.0-build1.aab`
  (for Google Play) and the matching `.apk`. The signed build has not
  been run on a phone. Nothing has been uploaded to Google Play.

**iOS — generated only.** The project in `frontend/ios` was created on
Windows and has never been opened in Xcode, built or run. That can only
be done on a Mac. Follow "iOS" below.

## The server already allows the apps

The apps call the live API at `https://ocrdocflow.qumaxa.com`. The API
only answers pages it knows, so `backend/app/main.py` also allows the
two addresses the apps use (`https://localhost` for Android,
`capacitor://localhost` for iOS). This was deployed on 2026-11-18, and
the Android app was seen uploading to the live server afterwards.

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

### Android tools already on this PC

Drive C: on the development PC is almost full, so Android Studio was not
installed. The same tools were put on drive D: instead (2026-11-18):

| What | Where |
|---|---|
| Java 21 (Microsoft OpenJDK) | `D:\Android\jdk-21` |
| Android SDK: platform 36, build tools, emulator, one Android 15 phone image | `D:\Android\Sdk` |
| Gradle and build libraries | `D:\Android\gradle-home` |
| Virtual phone `ocrdocflow_test` | `D:\Android\user-home` |

Four settings on the Windows user account point at them: `JAVA_HOME`,
`ANDROID_HOME`, `GRADLE_USER_HOME`, `ANDROID_USER_HOME`. Open a **new**
terminal for them to take effect. With these, the `gradlew` commands
below work without Android Studio. To remove everything, delete
`D:\Android` and those four settings.

**The virtual phone is heavy for this PC** (11 GB memory, shared with
Docker). While it ran, Windows' swap file grew and drive C: dropped to
about 250 MB free. Close other programs first, run it for short
sessions, and prefer a real Android phone on a USB cable. To start it:

```bash
D:/Android/Sdk/emulator/emulator.exe -avd ocrdocflow_test -memory 2048 -no-snapshot
```

Then install the test APK on it (or on a connected phone):

```bash
D:/Android/Sdk/platform-tools/adb.exe install -r frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

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

### Testing against the local server (developers)

A normal build always talks to the live server. To try logged-in screens
without touching live data, the app can load its pages from the dev
server on the PC and use the local API:

1. Start the local API (root `docker-compose.yml`) and the web dev server
   so that it listens on 127.0.0.1:
   `npm --prefix frontend run dev -- --host 127.0.0.1`
2. `frontend/.env.development.local` (not in git) must contain
   `VITE_MOBILE_API_BASE_URL=http://localhost:8000`.
3. Let the phone reach the PC's ports:
   `adb reverse tcp:5173 tcp:5173` and `adb reverse tcp:8000 tcp:8000`.
4. In `frontend/`: `CAP_DEV_SERVER=http://localhost:5173 npx cap sync android`,
   then build and install the test APK as above.
5. **Afterwards run `npx cap sync android` again without `CAP_DEV_SERVER`**
   and rebuild, so the app goes back to its normal, self-contained form.
   Never build a release with `CAP_DEV_SERVER` set.

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

- **App icon and splash screen** use the Qumaxa logo
  (`frontend/assets/logo.png`). To change it, replace that file and run
  `python frontend/assets/make_icons.py`, then rebuild. The same script
  writes `play-store-icon-512.png` and `app-store-icon-1024.png` for the
  store listings.
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
