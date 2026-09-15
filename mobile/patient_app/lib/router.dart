import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'screens/book_consultation_screen.dart';
import 'screens/brand_splash_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/emergency_contacts_screen.dart';
import 'screens/forgot_password_screen.dart';
import 'screens/login_screen.dart';
import 'screens/my_appointments_screen.dart';
import 'screens/register_screen.dart';
import 'screens/profile_selection_screen.dart';
import 'screens/pharmacy_search_screen.dart';
import 'screens/scan_prescription_screen.dart';
import 'screens/triage_screen.dart';
import 'screens/health_passport_screen.dart';
import 'screens/health_wallet_screen.dart';
import 'screens/video_consultation_screen.dart';
import 'screens/vitals_screen.dart';
import 'screens/reminders_screen.dart';
import 'screens/sos_active_screen.dart';
import 'services/secure_store.dart';

/// Premium navigation (planning doc: "ஃப்ளூயிட் ட்ரான்சிஷன்ஸ்" — smooth,
/// consistent transitions app-wide). A single shared fade+slide transition
/// applied to every route beats one-off per-screen animation code, and
/// keeps the feel cohesive across all modules.
CustomTransitionPage _appPage(Widget child, GoRouterState state) {
  return CustomTransitionPage(
    key: state.pageKey,
    child: child,
    transitionDuration: const Duration(milliseconds: 320),
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(begin: const Offset(0, 0.04), end: Offset.zero).animate(curved),
          child: child,
        ),
      );
    },
  );
}

final GoRouter appRouter = GoRouter(
  initialLocation: '/splash',
  redirect: (context, state) async {
    // The animated brand intro (BrandSplashScreen) does its own token check
    // and self-navigates once ready — it must never be redirected away
    // before that finishes, or the animation gets cut off.
    if (state.matchedLocation == '/splash') return null;

    // Token now lives in the platform keystore, not shared_preferences.
    final token = await SecureStore().getToken();

    // All three auth surfaces are reachable without a token; everything
    // else redirects to login.
    final isAuthRoute = state.matchedLocation == '/login' ||
        state.matchedLocation == '/register' ||
        state.matchedLocation == '/forgot-password';

    if (token == null && !isAuthRoute) {
      return '/login';
    }

    if (token != null && isAuthRoute) {
      return '/';
    }

    return null;
  },
  routes: [
    GoRoute(
      path: '/splash',
      pageBuilder: (context, state) => _appPage(const BrandSplashScreen(), state),
    ),
    GoRoute(
      path: '/login',
      pageBuilder: (context, state) => _appPage(const LoginScreen(), state),
    ),
    GoRoute(
      path: '/register',
      pageBuilder: (context, state) => _appPage(const RegisterScreen(), state),
    ),
    GoRoute(
      path: '/forgot-password',
      pageBuilder: (context, state) => _appPage(const ForgotPasswordScreen(), state),
    ),
    GoRoute(
      path: '/',
      pageBuilder: (context, state) => _appPage(const DashboardScreen(), state),
    ),
    GoRoute(
      path: '/profiles',
      pageBuilder: (context, state) => _appPage(const ProfileSelectionScreen(), state),
    ),
    GoRoute(
      path: '/triage',
      pageBuilder: (context, state) => _appPage(const TriageScreen(), state),
    ),
    GoRoute(
      path: '/wallet',
      pageBuilder: (context, state) => _appPage(const HealthWalletScreen(), state),
    ),
    GoRoute(
      path: '/scan',
      pageBuilder: (context, state) => _appPage(const ScanPrescriptionScreen(), state),
    ),
    GoRoute(
      path: '/pharmacy',
      pageBuilder: (context, state) => _appPage(const PharmacySearchScreen(), state),
    ),
    GoRoute(
      path: '/emergency-contacts',
      pageBuilder: (context, state) => _appPage(const EmergencyContactsScreen(), state),
    ),
    GoRoute(
      path: '/vitals',
      pageBuilder: (context, state) => _appPage(const VitalsScreen(), state),
    ),
    GoRoute(
      path: '/passport',
      pageBuilder: (context, state) => _appPage(const HealthPassportScreen(), state),
    ),
    GoRoute(
      path: '/reminders',
      pageBuilder: (context, state) => _appPage(const RemindersScreen(), state),
    ),
    GoRoute(
      path: '/sos-active',
      pageBuilder: (context, state) {
        final lat = double.tryParse(state.uri.queryParameters['lat'] ?? '0') ?? 0;
        final lng = double.tryParse(state.uri.queryParameters['lng'] ?? '0') ?? 0;
        return _appPage(SosActiveScreen(patientLat: lat, patientLng: lng), state);
      },
    ),
    GoRoute(
      path: '/book',
      pageBuilder: (context, state) => _appPage(const BookConsultationScreen(), state),
    ),
    GoRoute(
      path: '/appointments',
      pageBuilder: (context, state) => _appPage(const MyAppointmentsScreen(), state),
    ),
    GoRoute(
      path: '/video-call/:appointmentId',
      pageBuilder: (context, state) {
        final appointmentId = int.parse(state.pathParameters['appointmentId']!);
        return _appPage(VideoConsultationScreen(appointmentId: appointmentId), state);
      },
    ),
  ],
);
