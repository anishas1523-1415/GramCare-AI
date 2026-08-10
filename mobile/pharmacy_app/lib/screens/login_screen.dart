import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/firebase_notification_service.dart';
import '../services/secure_store.dart';
import '../theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _isLoading = false;
  String _error = '';

  Future<void> _login(LocaleService locale) async {
    setState(() {
      _isLoading = true;
      _error = '';
    });

    try {
      final response = await ApiService().client.post(
        '/auth/login',
        data: {
          'username': _usernameController.text,
          'password': _passwordController.text,
        },
        options: Options(
          contentType: Headers.formUrlEncodedContentType,
        ),
      );

      final token = response.data['access_token'] as String?;
      final role = response.data['role'] as String?;
      if (token == null) {
        throw Exception('Login response did not include an access token.');
      }

      // Backend role string is exactly "PHARMACIST" (models.py / schemas.py
      // pattern "^(PATIENT|DOCTOR|PHARMACIST|HOSPITAL|ADMIN)$"). ADMIN is
      // also allowed through by require_role() server-side, so let it in too.
      if (role != 'PHARMACIST' && role != 'ADMIN') {
        setState(() {
          _error = locale.t('wrong_role');
          _isLoading = false;
        });
        return;
      }

      await SecureStore().setToken(token);
      await SecureStore().setRole(role ?? '');

      unawaited(FirebaseNotificationService().syncTokenWithBackend());

      if (mounted) context.go('/');
    } catch (e) {
      setState(() {
        _error = locale.t('invalid_credentials');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Align(
                  alignment: Alignment.topRight,
                  child: TextButton.icon(
                    onPressed: () => locale.setCode(locale.isTamil ? 'en' : 'ta'),
                    icon: const Icon(Icons.language, color: PharmacyTheme.primaryGreen),
                    label: Text(locale.isTamil ? 'English' : 'தமிழ்'),
                  ),
                ),
                const Icon(Icons.local_pharmacy, size: 88, color: PharmacyTheme.primaryGreen),
                const SizedBox(height: 16),
                Text(
                  locale.t('app_title'),
                  style: const TextStyle(fontSize: 30, fontWeight: FontWeight.bold, color: PharmacyTheme.darkGreen),
                ),
                Text(
                  locale.t('tagline'),
                  style: const TextStyle(fontSize: 15, color: Colors.black54),
                ),
                const SizedBox(height: 40),
                TextField(
                  controller: _usernameController,
                  decoration: InputDecoration(hintText: locale.t('username_hint')),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _passwordController,
                  obscureText: true,
                  decoration: InputDecoration(hintText: locale.t('password_hint')),
                ),
                if (_error.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  Text(_error, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                ],
                const SizedBox(height: 32),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _isLoading ? null : () => _login(locale),
                    child: _isLoading
                        ? const SizedBox(
                            height: 22,
                            width: 22,
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                          )
                        : Text(locale.t('login')),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
