plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
    // NOTE: Firebase Gradle plugins are intentionally NOT applied here yet.
    // firebase_core/messaging/crashlytics/analytics are wired on the Dart
    // side (see lib/services/firebase_notification_service.dart) exactly
    // like apps/mobile_app, but this app has no android/app/google-services.json
    // of its own — a new Firebase Android app ("com.gramcare.pharmacy_mobile_app")
    // must be registered in the Firebase console and its google-services.json
    // dropped into android/app/ before these two lines (and the matching
    // plugin versions in settings.gradle.kts) can be uncommented and the app
    // will actually build/run with push notifications.
    // id("com.google.gms.google-services")
    // id("com.google.firebase.crashlytics")
}

android {
    namespace = "com.gramcare.pharmacy_mobile_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.gramcare.pharmacy_mobile_app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")
}
