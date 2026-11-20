import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
    // Reads google-services.json (already present in this directory) and
    // generates the Firebase config the firebase_core plugin needs at runtime.
    id("com.google.gms.google-services")
    // Crashlytics native wiring — required for FirebaseCrashlytics to report
    // both Dart-side (via FlutterError.onError) and native crashes.
    id("com.google.firebase.crashlytics")
}

val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}


android {
    namespace = "com.gramcare.mobile_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    val localProperties = Properties()
    val localPropertiesFile = rootProject.file("local.properties")
    if (localPropertiesFile.exists()) {
        localProperties.load(FileInputStream(localPropertiesFile))
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.gramcare.mobile_app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // local.properties is gitignored, so a fresh clone or a CI runner has
        // no key at all and the SOS map silently ships as a blank grey tile.
        // Fall back to the environment so a build machine can supply it, and
        // say so out loud rather than producing a quietly broken APK.
        val mapsApiKey = localProperties.getProperty("MAPS_API_KEY")
            ?: System.getenv("MAPS_API_KEY")
            ?: ""
        if (mapsApiKey.isEmpty()) {
            logger.warn(
                "MAPS_API_KEY is not set (android/local.properties or the environment). " +
                "The SOS map will render blank; the screen falls back to an Open in Maps link."
            )
        }
        manifestPlaceholders["MAPS_API_KEY"] = mapsApiKey
    }

    signingConfigs {
        create("release") {
            keyAlias = keystoreProperties["keyAlias"] as String?
            keyPassword = keystoreProperties["keyPassword"] as String?
            storeFile = keystoreProperties["storeFile"]?.let { file(it as String) }
            storePassword = keystoreProperties["storePassword"] as String?
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            // A debug build installs under its OWN application id, so it can
            // never replace or uninstall the release app on a real phone.
            //
            // This exists because `flutter test integration_test/...` builds a
            // debug APK, installs it over whatever is already there, runs, and
            // then UNINSTALLS it — which on Android deletes the app's private
            // data. That is how a device test wiped the installed patient app
            // and its encrypted health-wallet box.
            //
            // Set GRAMCARE_SAME_APP_ID=1 to opt out, which you need only when
            // testing push on a debug build: Firebase registration is tied to
            // the package name, so a suffixed debug build cannot receive FCM.
            if (System.getenv("GRAMCARE_SAME_APP_ID") != "1") {
                applicationIdSuffix = ".debug"
                versionNameSuffix = "-debug"
            } else {
                logger.lifecycle(
                    "GRAMCARE_SAME_APP_ID=1: this debug build uses the RELEASE " +
                    "application id and will replace the installed app."
                )
            }
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")
}
