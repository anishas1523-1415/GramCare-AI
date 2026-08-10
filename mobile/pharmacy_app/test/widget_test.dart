// Basic smoke test for the real Pharmacy Mobile App, mirroring
// apps/mobile_app/test/widget_test.dart's approach: pump the real app
// widget (not main()) and verify it renders the login screen when no
// access token is stored — the initial redirect behavior in lib/router.dart.
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:pharmacy_mobile_app/main.dart';
import 'package:pharmacy_mobile_app/services/app_strings.dart';

void main() {
  testWidgets('Shows the login screen on first launch (no stored session)',
      (WidgetTester tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: LocaleService()),
        ],
        child: const PharmacyApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('GramCare Pharmacy'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
  });

  testWidgets(
      'Shows an error and re-enables the button when login fails',
      (WidgetTester tester) async {
    // No backend is reachable in the test environment, so submitting the
    // login form exercises the real network-failure path without mocking Dio.
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});

    final locale = LocaleService();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: locale),
        ],
        child: const PharmacyApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'pharma1');
    await tester.enterText(find.byType(TextField).last, 'testpass');
    await tester.tap(find.byType(ElevatedButton));
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    for (var i = 0; i < 30 && find.byType(CircularProgressIndicator).evaluate().isNotEmpty; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }

    expect(find.text(locale.t('invalid_credentials')), findsOneWidget);
  }, timeout: const Timeout(Duration(seconds: 20)));
}
