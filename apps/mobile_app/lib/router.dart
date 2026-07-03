import 'package:go_router/go_router.dart';

import 'screens/dashboard_screen.dart';
import 'screens/login_screen.dart';
import 'screens/profile_selection_screen.dart';
import 'screens/pharmacy_search_screen.dart';
import 'screens/scan_prescription_screen.dart';
import 'screens/triage_screen.dart';
import 'screens/health_wallet_screen.dart';
import 'screens/vitals_screen.dart';
import 'screens/reminders_screen.dart';
import 'services/secure_store.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  redirect: (context, state) async {
    // Token now lives in the platform keystore, not shared_preferences.
    final token = await SecureStore().getToken();

    final isLoggingIn = state.matchedLocation == '/login';

    if (token == null && !isLoggingIn) {
      return '/login';
    }

    if (token != null && isLoggingIn) {
      return '/';
    }

    return null;
  },
  routes: [
    GoRoute(
      path: '/login',
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: '/',
      builder: (context, state) => const DashboardScreen(),
    ),
    GoRoute(
      path: '/profiles',
      builder: (context, state) => const ProfileSelectionScreen(),
    ),
    GoRoute(
      path: '/triage',
      builder: (context, state) => const TriageScreen(),
    ),
    GoRoute(
      path: '/wallet',
      builder: (context, state) => const HealthWalletScreen(),
    ),
    GoRoute(
      path: '/scan',
      builder: (context, state) => const ScanPrescriptionScreen(),
    ),
    GoRoute(
      path: '/pharmacy',
      builder: (context, state) => const PharmacySearchScreen(),
    ),
    GoRoute(
      path: '/vitals',
      builder: (context, state) => const VitalsScreen(),
    ),
    GoRoute(
      path: '/reminders',
      builder: (context, state) => const RemindersScreen(),
    ),
  ],
);
