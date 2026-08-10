import 'dart:async';

import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'router.dart';
import 'services/app_strings.dart';
import 'services/doctor_session.dart';
import 'services/firebase_notification_service.dart';
import 'theme/app_theme.dart';

void main() async {
  // runZonedGuarded, not a plain try/catch: also catches errors thrown by
  // code scheduled asynchronously outside the current call stack (timers,
  // unawaited Futures) that would otherwise crash silently without
  // Crashlytics ever seeing them — same rationale as apps/mobile_app.
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();

    // English-default, Tamil-togglable localization (planning doc: Tamil
    // support matters for rural Tamil Nadu doctors too).
    final locale = LocaleService();
    await locale.load();

    // Firebase Core + Messaging + Crashlytics + Analytics + local
    // notifications. FCM token registration with the backend happens later
    // (login screen / dashboard init) since it needs an authenticated JWT
    // this call doesn't have yet.
    await FirebaseNotificationService().initialize();

    runApp(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => DoctorSession()),
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const DoctorApp(),
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

class DoctorApp extends StatelessWidget {
  const DoctorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'GramCare Doctor',
      theme: AppTheme.theme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,
      routerConfig: appRouter,
    );
  }
}
