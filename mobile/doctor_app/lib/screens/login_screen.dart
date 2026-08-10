import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/doctor_session.dart';
import '../services/firebase_notification_service.dart';
import '../services/secure_store.dart';
import '../theme/app_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _loading = false;
  String? _error;
  bool _obscurePassword = true;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login(LocaleService locale) async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      // Backend expects OAuth2PasswordRequestForm — form-encoded fields, not JSON.
      final response = await ApiService().client.post(
        '/auth/login',
        data: FormData.fromMap({
          'username': _usernameController.text.trim(),
          'password': _passwordController.text,
        }),
      );

      final data = response.data as Map<String, dynamic>;
      final role = data['role'] as String?;
      final token = data['access_token'] as String;

      if (role != 'DOCTOR' && role != 'ADMIN') {
        setState(() {
          _error = locale.t('not_a_doctor_account');
          _loading = false;
        });
        return;
      }

      await SecureStore().setToken(token);
      await SecureStore().setRole(role!);

      if (!mounted) return;
      await context.read<DoctorSession>().loadProfile();

      // Best-effort; must never block navigation past login.
      unawaited(FirebaseNotificationService().syncTokenWithBackend());

      if (!mounted) return;
      context.go('/');
    } on DioException catch (e) {
      setState(() {
        _error = e.response?.statusCode == 401
            ? locale.t('invalid_credentials')
            : locale.t('login_failed');
        _loading = false;
      });
    } catch (_) {
      setState(() {
        _error = locale.t('login_failed');
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(
                      onPressed: () => locale.setCode(locale.isTamil ? 'en' : 'ta'),
                      icon: const Icon(Icons.language, size: 18),
                      label: Text(locale.isTamil ? 'English' : 'தமிழ்'),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    width: 88,
                    height: 88,
                    decoration: BoxDecoration(
                      color: AppTheme.primaryBlue,
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: const Icon(Icons.local_hospital_rounded, color: Colors.white, size: 46),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    locale.t('app_title'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: AppTheme.deepBlue),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    locale.t('tagline'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 14, color: Colors.black54),
                  ),
                  const SizedBox(height: 32),
                  TextField(
                    controller: _usernameController,
                    decoration: InputDecoration(
                      labelText: locale.t('username_hint'),
                      prefixIcon: const Icon(Icons.person_outline),
                    ),
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _passwordController,
                    obscureText: _obscurePassword,
                    decoration: InputDecoration(
                      labelText: locale.t('password_hint'),
                      prefixIcon: const Icon(Icons.lock_outline),
                      suffixIcon: IconButton(
                        icon: Icon(_obscurePassword ? Icons.visibility_off : Icons.visibility),
                        onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                      ),
                    ),
                    onSubmitted: (_) => _loading ? null : _login(locale),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: AppTheme.cancelledRed)),
                  ],
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: _loading ? null : () => _login(locale),
                    child: _loading
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : Text(locale.t('login')),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
