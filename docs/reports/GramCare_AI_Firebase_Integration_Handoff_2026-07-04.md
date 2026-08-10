# GramCare AI — Flutter Firebase Integration Handoff
**Date:** 2026-07-04 | **Scope:** apps/mobile_app

## What was built

| File | Change |
|---|---|
| `pubspec.yaml` | added `firebase_core`, `firebase_messaging`, `firebase_crashlytics`, `firebase_analytics`, `flutter_local_notifications` |
| `android/settings.gradle.kts` | added `com.google.gms.google-services` + `com.google.firebase.crashlytics` plugin declarations |
| `android/app/build.gradle.kts` | applied both plugins (reads the `google-services.json` already present in `android/app/`) |
| `android/app/src/main/AndroidManifest.xml` | added `POST_NOTIFICATIONS` + `WAKE_LOCK` permissions, default notification channel + icon meta-data |
| `lib/services/firebase_notification_service.dart` | **new** — the whole FCM lifecycle (see below) |
| `lib/services/secure_store.dart` | added `getOrCreateDeviceId()` and last-registered-token cache (for duplicate-avoidance) |
| `lib/main.dart` | `Firebase`/Crashlytics/service init before `runApp`, wrapped in `runZonedGuarded` |
| `lib/screens/login_screen.dart` | registers the FCM token right after a successful login |
| `lib/screens/dashboard_screen.dart` | re-syncs the token on every app open (covers "already logged in" case) |

## How each requirement was satisfied

1–4. **Init Firebase / Messaging / Crashlytics / Analytics** — all in `FirebaseNotificationService.initialize()`, called once from `main.dart` before `runApp`.
5–6. **Permission + token** — `syncTokenWithBackend()`, called from `login_screen.dart` (after login) and `dashboard_screen.dart` (on every app open).
7. **POST to `/api/v1/auth/fcm-token`** — `_registerTokenWithBackend()`, using the existing `ApiService` (which already attaches the JWT via its Dio interceptor). Backend endpoint was already implemented and unchanged.
8. **Token refresh** — `FirebaseMessaging.instance.onTokenRefresh.listen(...)` re-POSTs automatically.
9. **Foreground / background / terminated** — `onMessage` (foreground, rendered manually via `flutter_local_notifications`), `onMessageOpenedApp` (background tap), `getInitialMessage()` (terminated-launch tap), plus a top-level `firebaseMessagingBackgroundHandler` registered via `onBackgroundMessage`.
10. **Android notification channel** — one channel, `gramcare_high_importance_channel`, created in `initialize()` and referenced in the manifest as the default channel for terminated-state auto-display.
11. **Foreground display via flutter_local_notifications** — `_showForegroundNotification()`.
12. **Tap navigation** — `_navigateForNotification()`, driven by the `type` field in the FCM data payload.

## Navigation mapping — please double-check this

The mobile app is patient-only and has **no** literal "SOS screen" or "Doctor dashboard" (those are `web_portal`/`react_dashboard` concepts). I mapped notification types to the closest existing screen:

| `data.type` | Routes to |
|---|---|
| `sos_alert` | `/emergency-contacts` |
| `appointment_reminder` | `/reminders` |
| `doctor_message`, `prescription_issued` | `/wallet` (Health Wallet) |
| `pharmacy_ready`, `pharmacy_update` | `/pharmacy` (Pharmacy Search) |
| anything else | `/` (Dashboard) |

The backend's `core/notifications.py` currently only ever sends `sos_alert` and `appointment_reminder` — the doctor/pharmacy types are forward-compatible placeholders for when that's wired up, not currently emitted by any backend code path I found. If your intent was different screens, the mapping lives in one place (`_navigateForNotification` in `firebase_notification_service.dart`) and is a one-line-per-case change.

## Duplicate handling

Two layers, matching what you asked to verify:
- **Client-side:** `SecureStore` caches the last token this install successfully registered; `_registerTokenWithBackend()` skips the POST entirely if the token hasn't changed. A stable per-install `device_id` (UUID, generated once, kept in secure storage) is sent so the backend can tell "same device, new token" from "new device."
- **Server-side (unchanged, already existed):** the endpoint deactivates any other user's row with the same token (anti-stealing), and updates-in-place if this exact `(user_id, device_id, platform)` already has a row.

## What is verified vs. not — please read before trusting this

**Not verified — this sandbox cannot run the Flutter/Dart toolchain at all.** Confirmed directly (not assumed): `storage.googleapis.com`, `dl.google.com`, `pub.dev`, and `pub.dartlang.org` all return `403 blocked-by-allowlist` from this environment's network proxy, and a fresh `git clone` of the Flutter SDK itself still fails at the Dart SDK bootstrap step for the same reason. That means none of the following happened here:
- `flutter pub get` (pubspec.lock still needs regeneration — it doesn't yet have entries for the 5 new packages)
- `flutter analyze`
- `flutter test`
- `flutter build apk`

**What I did instead:** every new/changed file was hand-reviewed against the FlutterFire APIs I have high confidence in (constructor signatures, callback types, class names — e.g. confirmed `AndroidNotificationChannel`, `NotificationDetails(android:, iOS:)`, `FirebaseCrashlytics.instance.recordFlutterFatalError`, `FirebaseMessaging.onBackgroundMessage` requiring a top-level `@pragma('vm:entry-point')` function). Every file was also mechanically checked: XML well-formedness (`AndroidManifest.xml`), brace/paren balance (all `.dart` and `.gradle.kts` files), and YAML validity (`pubspec.yaml`). None of that is a substitute for the real compiler.

## Commands to run yourself, in order, on a machine with real network access

```bash
cd apps/mobile_app
flutter pub get                 # regenerates pubspec.lock for the 5 new packages
flutter analyze                 # will catch anything my manual review missed
flutter test
flutter build apk --debug       # or --release, once you've confirmed analyze/test pass
```

## Verification checklist (requirement #13) — run manually on a device/emulator with a real backend reachable

- [ ] **Token registration:** log in, check backend logs / `user_push_tokens` table for a new row.
- [ ] **Token refresh:** clear app data or reinstall, log in again, confirm the row's `fcm_token` updates (not a duplicate row) for the same `device_id`.
- [ ] **Duplicate handling:** log in twice in a row without a token change — confirm only one network call fires the first time (check `_registerTokenWithBackend` debug log: "FCM token unchanged... skipping POST" on the second).
- [ ] **Foreground notification:** send a test push while the app is open — a system-tray notification should appear (not silently swallowed).
- [ ] **Background notification:** send a push while the app is backgrounded (not killed) — should appear, and tapping it should open the app to the mapped screen.
- [ ] **Terminated notification:** force-stop the app, send a push, tap it — app should cold-start and land on the mapped screen (there's a 700ms delay built in before this redirect fires, to let the login-redirect settle first — adjust `firebase_notification_service.dart`'s `Duration(milliseconds: 700)` if this races on a slower device).
- [ ] **Analytics events:** check Firebase console (DebugView) for `notification_permission_requested`, `fcm_token_obtained`, `fcm_token_registered_backend`, `fcm_token_refreshed`, `notification_received_foreground`, `notification_received_background`, `notification_tapped`.
- [ ] **Crash reporting:** trigger a test exception (e.g. `throw Exception('test crash')` temporarily somewhere) and confirm it appears in Firebase Crashlytics console within a few minutes.

## iOS — out of scope here

No `GoogleService-Info.plist` exists in `ios/Runner/`, and this sandbox has no macOS/Xcode toolchain to build iOS regardless. The Dart code is cross-platform, but iOS needs its own Firebase config file and a CocoaPods install on a Mac before it will build.
