// Basic smoke test for the Doctor mobile app's root widget.
//
// Deliberately does not call main() (which performs Firebase init — not
// available in the widget-test environment). Instead it pumps DoctorApp
// directly, wrapped in the same Providers main() would supply, and checks
// that go_router lands on the login route since no JWT is present in
// FlutterSecureStorage during a test run.

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:doctor_mobile_app/main.dart';
import 'package:doctor_mobile_app/services/app_strings.dart';
import 'package:doctor_mobile_app/services/doctor_session.dart';

void main() {
  testWidgets('App boots to the login screen when logged out', (WidgetTester tester) async {
    // Without this, SecureStore().getToken() throws MissingPluginException
    // (no platform channel handler exists in the test environment) — the
    // router's redirect callback then fails silently and GoRouter renders
    // its error page instead of navigating, leaving zero TextFields on
    // screen. This mock is what makes the redirect actually resolve.
    FlutterSecureStorage.setMockInitialValues({});

    final locale = LocaleService();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => DoctorSession()),
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const DoctorApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(TextField), findsWidgets);
  });

  testWidgets(
      'Shows an error and re-enables the button when login fails',
      (WidgetTester tester) async {
    // No backend is reachable in the test environment, so submitting the
    // login form exercises the real network-failure path without mocking Dio.
    FlutterSecureStorage.setMockInitialValues({});

    final locale = LocaleService();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => DoctorSession()),
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const DoctorApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'doctor1');
    await tester.enterText(find.byType(TextField).last, 'testpass');
    await tester.tap(find.byType(ElevatedButton));
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    for (var i = 0; i < 30 && find.byType(CircularProgressIndicator).evaluate().isNotEmpty; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }

    expect(find.text(locale.t('login_failed')), findsOneWidget);
  }, timeout: const Timeout(Duration(seconds: 20)));
}
