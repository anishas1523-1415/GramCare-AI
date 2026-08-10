import 'dart:async';

import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:provider/provider.dart';
import 'package:workmanager/workmanager.dart';

import 'models/health_record.dart';
import 'router.dart';
import 'services/app_strings.dart';
import 'services/firebase_notification_service.dart';
import 'services/profile_service.dart';
import 'services/secure_store.dart';
import 'theme/neumorphic_colors.dart';
import 'services/sync_service.dart';

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    try {
      if (task == "syncHealthWallet") {
        await Hive.initFlutter();
        Hive.registerAdapter(HealthRecordAdapter());
        final hiveKey = await SecureStore().getOrCreateHiveKey();
        await Hive.openBox<HealthRecord>(
          'health_wallet',
          encryptionCipher: HiveAesCipher(hiveKey),
        );
        
        await SyncService().pushUnsynced();
        debugPrint("Background sync completed successfully.");
      }
    } catch (err) {
      debugPrint("Background sync error: $err");
      return Future.value(false);
    }
    return Future.value(true);
  });
}

void main() async {
  // runZonedGuarded, not a plain try/catch around main()'s body: this also
  // catches errors thrown by code scheduled asynchronously outside the
  // current call stack (timers, unawaited Futures) that would otherwise
  // crash silently without Crashlytics ever seeing them.
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();

    // Lift any legacy plain-text token into the platform keystore first.
    await SecureStore().migrateLegacyToken();

    // Initialize Hive Offline-First Database — the health wallet box is now
    // AES-encrypted with a key held in the platform keystore (clinical data
    // was previously stored in plaintext on disk).
    await Hive.initFlutter();
    Hive.registerAdapter(HealthRecordAdapter());
    final hiveKey = await SecureStore().getOrCreateHiveKey();
    await Hive.openBox<HealthRecord>(
      'health_wallet',
      encryptionCipher: HiveAesCipher(hiveKey),
    );

    // Tamil-first localization (planning doc) — persisted user choice.
    final locale = LocaleService();
    await locale.load();

    // Firebase Core + Messaging + Crashlytics + Analytics + local
    // notifications. This also wires FlutterError.onError and
    // PlatformDispatcher.instance.onError for Crashlytics — must happen
    // before runApp so no early widget-build error is missed. FCM token
    // registration with the backend happens later, from the login screen
    // and the dashboard (needs an authenticated JWT this call doesn't have).
    await FirebaseNotificationService().initialize();

    // Workmanager setup for robust background syncing
    await Workmanager().initialize(callbackDispatcher, isInDebugMode: false);
    // Periodically run the sync task every 1 hour (Android minimum is 15 minutes)
    await Workmanager().registerPeriodicTask(
      "syncHealthWalletTask",
      "syncHealthWallet",
      frequency: const Duration(hours: 1),
      constraints: Constraints(
        networkType: NetworkType.connected, // Only run when internet is available
      ),
    );

    runApp(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => ProfileService()),
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const GramCareApp(),
      ),
    );
  }, (error, stack) {
    // Guarded: an error thrown before FirebaseNotificationService().initialize()
    // finishes (e.g. during Hive setup) would mean Crashlytics itself isn't
    // ready yet — must not let recordError() throw a second, masking error.
    try {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    } catch (_) {
      debugPrint('Uncaught zone error (Crashlytics unavailable): $error');
    }
  });
}

class GramCareApp extends StatelessWidget {
  const GramCareApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'GramCare AI',
      theme: ThemeData(
        scaffoldBackgroundColor: const Color(0xFFE0E5EC),
        primaryColor: const Color(0xFF4F46E5),
        fontFamily: 'Inter',
        useMaterial3: true,
        extensions: const [NeumorphicColors.light],
      ),
      darkTheme: ThemeData(
        scaffoldBackgroundColor: NeumorphicColors.dark.background,
        primaryColor: const Color(0xFF4F46E5),
        fontFamily: 'Inter',
        useMaterial3: true,
        brightness: Brightness.dark,
        extensions: const [NeumorphicColors.dark],
      ),
      themeMode: ThemeMode.system,
      routerConfig: appRouter,
    );
  }
}
