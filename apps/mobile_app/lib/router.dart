import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'screens/dashboard_screen.dart';
import 'screens/login_screen.dart';
import 'screens/triage_screen.dart';
import 'screens/health_wallet_screen.dart';
import 'screens/vitals_screen.dart';
import 'screens/reminders_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  redirect: (context, state) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    
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
      path: '/triage',
      builder: (context, state) => const TriageScreen(),
    ),
    GoRoute(
      path: '/wallet',
      builder: (context, state) => const HealthWalletScreen(),
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
