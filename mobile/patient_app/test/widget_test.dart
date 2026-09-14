// Basic smoke test for the real GramCare AI app.
//
// Pumps the real app and verifies it renders the login screen when no
// access token is stored — the initial redirect behavior in lib/router.dart.
// The token now lives in flutter_secure_storage (keystore), so the secure
// storage platform channel is mocked instead of shared_preferences.

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mobile_app/main.dart';
import 'package:mobile_app/services/app_strings.dart';
import 'package:mobile_app/services/profile_service.dart';

/// The app boots at /splash, which holds before routing on to /login (see
/// BrandSplashScreen._navigateNext). A bare pumpAndSettle() returns while
/// that gate is still pending, leaving the test looking at the splash
/// screen — so advance past it explicitly first.
Future<void> _settleThroughSplash(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(seconds: 2));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('Shows the login screen on first launch (no stored session)',
      (WidgetTester tester) async {
    // Mock both storage channels used during startup/redirect.
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});

    final locale = LocaleService();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => ProfileService()),
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const GramCareApp(),
      ),
    );
    // Allow the async GoRouter redirect (which awaits SecureStore) to
    // resolve before asserting on the resulting screen.
    await _settleThroughSplash(tester);

    // Asserted through LocaleService rather than as literal English: the
    // app is Tamil-first, so hardcoded English strings only pass on a
    // device that happens to have English selected.
    expect(find.text(locale.t('app_title')), findsOneWidget);
    // Username/password fields identify this as the login screen rather
    // than the dashboard.
    expect(find.byType(TextField), findsNWidgets(2));
  });

  testWidgets(
      'Shows an error and re-enables the button when login fails',
      (WidgetTester tester) async {
    // No backend is reachable in the test environment, so submitting the
    // login form exercises the real failure path (connection error ->
    // catch block -> error message + spinner reset) without needing to
    // mock Dio.
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});

    final locale = LocaleService();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => ProfileService()),
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const GramCareApp(),
      ),
    );
    await _settleThroughSplash(tester);

    await tester.enterText(find.byType(TextField).first, 'testuser');
    await tester.enterText(find.byType(TextField).last, 'testpass');
    await tester.tap(find.text(locale.t('login')));

    // The button swaps to a spinner immediately (isLoading = true).
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    // Let the failed network call resolve — bounded pumps rather than
    // pumpAndSettle, since Dio's own connection-timeout backoff can keep
    // scheduling frames past pumpAndSettle's patience in a sandboxed
    // network-less test runner.
    for (var i = 0; i < 30 && find.text(locale.t('login')).evaluate().isEmpty; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }

    expect(find.text(locale.t('invalid_credentials')), findsOneWidget);
    expect(find.text(locale.t('login')), findsOneWidget);
  }, timeout: const Timeout(Duration(seconds: 20)));
}
