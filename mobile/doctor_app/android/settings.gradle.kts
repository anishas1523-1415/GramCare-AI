pluginManagement {
    val flutterSdkPath =
        run {
            val properties = java.util.Properties()
            file("local.properties").inputStream().use { properties.load(it) }
            val flutterSdkPath = properties.getProperty("flutter.sdk")
            require(flutterSdkPath != null) { "flutter.sdk not set in local.properties" }
            flutterSdkPath
        }

    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "8.11.1" apply false
    id("org.jetbrains.kotlin.android") version "2.2.20" apply false
    // Firebase integration (Crashlytics + FCM), mirroring apps/mobile_app's
    // setup: `apply false` here, actually applied per-module in
    // android/app/build.gradle.kts. NOT yet applied there — this app's
    // Android client (package com.gramcare.doctor_mobile_app) still needs
    // to be registered under the "gramcare-ai" Firebase project in the
    // Firebase console, and its generated google-services.json dropped
    // into android/app/, before these plugins can be turned on in
    // android/app/build.gradle.kts without breaking the Gradle build.
    id("com.google.gms.google-services") version "4.4.2" apply false
    id("com.google.firebase.crashlytics") version "3.0.2" apply false
}

include(":app")
