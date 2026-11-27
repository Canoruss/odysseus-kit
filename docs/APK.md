# Android App

The app is a [Capacitor](https://capacitorjs.com) wrapper around your Odysseus, with native features: widgets (chat, translation, notes, task, expenses), reminders with "Done" and "Snooze", morning summary, camera-based translator, two-way calendar sync, fingerprint lock, and reading of SMS queries from SNS 24 (Portugal only, optional).

No-compile alternative: open the Odysseus address in Chrome and choose **Install app** (PWA).

## Ready-made APK

The signed APK for each version is in the repository's **Releases**, including the `SHA-256` of the file and the certificate. You only need to compile if you want to modify the app.

## First app screen

The server address **is no longer embedded in the APK**: when you open the app for the first time, the configuration screen appears (language and Odysseus address, with a connection test). After logging in, the Tools → Setup assistant opens for keys and services. You can change the address by repeating the startup process (clearing the app's data).

## Building

Source version: **1.58** (versionCode 63). Requirements: JDK 21, Android SDK (platform 35 and build-tools), Node 20+, and Rust with the Android NDK 27 (for the voice/policy library in `voice-core/`).

0a. `bash scripts/build-voice.sh` builds `voice-core/` and copies the `.so` files into `android/app/src/main/jniLibs/`.

0. `cd android && npm install && npx cap sync android` (downloads Capacitor and generates `capacitor-cordova-android-plugins`; the `package.json` is in `android/`).
1. (Optional, only for the sample texts) the `YOUR-SERVER...` addresses in the files below are no longer used at startup; you can ignore them:
   - `android/app/src/main/assets/capacitor.config.json` (`server.url` field);
   - `android/app/src/main/java/com/canorus/odysseus/Updater.java` (`BASE`) and `NoteSync.java` (`SITE`);
   - `android/www/error.html`.
   Search for `YOUR-SERVER.YOUR-TAILNET.ts.net` and replace it in all locations.
2. Create your signing key (keep it safe; without it, you cannot update the app):
   ```bash
   keytool -genkey -v -keystore ~/odysseus-kit.keystore -alias kit -keyalg RSA -keysize 2048 -validity 10000
   ```
   and create `android/keystore.properties` (not committed to Git) with `storeFile`, `storePassword`, `keyAlias`, `keyPassword`.
3. Build: `cd android && ./gradlew assembleRelease`.
4. Install the APK on your phone (enable "install from unknown sources").

## In-app updates

`android/tools/publish.sh` compiles, signs, and publishes the APK to a folder served at `/odysseus-app/` (with `version.json`). The app checks this list in Settings. Serve the folder using the same proxy as in step 3 of the installation.

## Notes

- The package identifier is `com.canorus.odysseus`. If you publish your variant, change it.
- Permissions used: notifications, exact alarms, calendar, camera, microphone, read SMS (only for SNS 24 queries), and read notifications. You can remove them from `AndroidManifest.xml` if you do not use the feature.
