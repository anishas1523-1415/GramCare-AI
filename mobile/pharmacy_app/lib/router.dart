import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'screens/brand_splash_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/expiry_alerts_screen.dart';
import 'screens/forgot_password_screen.dart';
import 'screens/login_screen.dart';
import 'screens/order_queue_screen.dart';
import 'screens/pharmacy_setup_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/register_screen.dart';
import 'screens/shortage_alerts_screen.dart';
import 'screens/stock_screen.dart';
import 'services/secure_store.dart';

/// Premium navigation (planning doc: never the default framework transition)
/// — the same fade+slide page transition used across every GramCare app, so
/// switching between the patient/doctor/pharmacy apps feels like one family.
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

    final token = await SecureStore().getToken();
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
      path: '/pharmacy-setup',
      pageBuilder: (context, state) => _appPage(const PharmacySetupScreen(), state),
    ),
    GoRoute(
      path: '/queue',
      pageBuilder: (context, state) => _appPage(const OrderQueueScreen(), state),
    ),
    GoRoute(
      path: '/stock',
      pageBuilder: (context, state) => _appPage(const StockScreen(), state),
    ),
    GoRoute(
      path: '/expiring',
      pageBuilder: (context, state) => _appPage(const ExpiryAlertsScreen(), state),
    ),
    GoRoute(
      path: '/shortages',
      pageBuilder: (context, state) => _appPage(const ShortageAlertsScreen(), state),
    ),
    GoRoute(
      path: '/profile',
      pageBuilder: (context, state) => _appPage(const ProfileScreen(), state),
    ),
  ],
);
