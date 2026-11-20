# Debug-variant Android config

Everything here is merged into **debug** APKs only and never into a release
build.

| File | Why it exists |
|---|---|
| `AndroidManifest.xml` | permits cleartext HTTP, so an integration test can reach a backend on the developer's machine over `adb reverse`. A release build still refuses cleartext. |
| `google-services.json` | the same Firebase config as `android/app/google-services.json`, with a client entry added for the suffixed debug application id. |

## Why google-services.json is duplicated here

`buildTypes.debug` sets `applicationIdSuffix = ".debug"` so a debug build
installs as `com.gramcare.mobile_app.debug` and can never replace or uninstall
the release app on a real phone. (`flutter test integration_test/...` installs a
debug APK over whatever is there and then uninstalls it, which on Android
deletes the app's data. That is how a device test once wiped the installed
patient app and its encrypted health-wallet box.)

The Google Services Gradle plugin fails the build outright if no client in
`google-services.json` matches the application id:

```
No matching client found for package name 'com.gramcare.mobile_app.debug'
```

This file carries both package names, so either id builds. The credentials are
identical to the already-tracked original, so nothing additional is exposed.

## Known limitation

Firebase ties FCM registration to the package name, and
`com.gramcare.mobile_app.debug` is not a real app in the Firebase project, so
**a suffixed debug build cannot receive push notifications.** Everything else
works.

To test push on a debug build, opt out of the suffix for that build:

```powershell
$env:GRAMCARE_SAME_APP_ID = "1"
```

That build then uses the release application id and **will replace the
installed app**, so only do it deliberately.
