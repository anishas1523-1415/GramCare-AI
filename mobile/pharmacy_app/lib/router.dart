import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'screens/dashboard_screen.dart';
import 'screens/expiry_alerts_screen.dart';
import 'screens/login_screen.dart';
import 'screens/order_queue_screen.dart';
import 'screens/profile_screen.dart';
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
  initialLocation: '/',
  redirect: (context, state) async {
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
      pageBuilder: (context, state) => _appPage(const LoginScreen(), state),
    ),
    GoRoute(
      path: '/',
      pageBuilder: (context, state) => _appPage(const DashboardScreen(), state),
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
