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
import 'package:mobile_app/services/profile_service.dart';

void main() {
  testWidgets('Shows the login screen on first launch (no stored session)',
      (WidgetTester tester) async {
    // Mock both storage channels used during startup/redirect.
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => ProfileService()),
        ],
        child: const GramCareApp(),
      ),
    );
    // Allow the async GoRouter redirect (which awaits SecureStore) to
    // resolve before asserting on the resulting screen.
    await tester.pumpAndSettle();

    expect(find.text('GramCare AI'), findsOneWidget);
    // Username/password fields identify this as the login screen rather
    // than the dashboard.
    expect(find.byType(TextField), findsNWidgets(2));
  });
}
