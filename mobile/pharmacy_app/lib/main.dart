import 'dart:async';

import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'router.dart';
import 'services/app_strings.dart';
import 'services/firebase_notification_service.dart';
import 'theme.dart';

void main() async {
  // runZonedGuarded, not a plain try/catch — also catches errors thrown by
  // code scheduled asynchronously outside the current call stack (timers,
  // unawaited Futures), matching apps/mobile_app's main.dart.
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();

    final locale = LocaleService();
    await locale.load();

    // Firebase Core + Messaging + Crashlytics + Analytics + local
    // notifications. FCM token registration with the backend happens later,
    // from the login screen and the dashboard (needs an authenticated JWT
    // this call doesn't have).
    await FirebaseNotificationService().initialize();

    runApp(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const PharmacyApp(),
      ),
    );
  }, (error, stack) {
    try {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    } catch (_) {
      debugPrint('Uncaught zone error (Crashlytics unavailable): $error');
    }
  });
}

class PharmacyApp extends StatelessWidget {
  const PharmacyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'GramCare Pharmacy',
      theme: PharmacyTheme.themeData,
      darkTheme: PharmacyTheme.darkThemeData,
      themeMode: ThemeMode.system,
      routerConfig: appRouter,
    );
  }
}
