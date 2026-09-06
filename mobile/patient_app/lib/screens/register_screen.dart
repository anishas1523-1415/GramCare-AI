import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/firebase_notification_service.dart';
import '../services/secure_store.dart';
import '../theme/neumorphic_colors.dart';
import 'dart:async';

/// Patient self-registration. Previously this app had NO registration
/// surface at all — only a login screen — so a rural patient whose first
/// contact with GramCare is the APK (the primary distribution channel per
/// the planning doc) had no way to create an account without finding the
/// web portal. That gap read as "registration failed" to real users.
///
/// PATIENT-only on purpose: doctors/hospitals register on the web portal,
/// where the OTP + email-verification flow lives. Patients stay
/// low-friction — register then immediately log in (POST /auth/register
/// doesn't return a token, same two-step the web portal does).
class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final TextEditingController _fullNameController = TextEditingController();
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _isLoading = false;
  String _error = '';

  @override
  void dispose() {
    _fullNameController.dispose();
    _usernameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  /// FastAPI's `detail` field is a plain string for most errors (e.g.
  /// "Username already registered") but a LIST of validation-error objects
  /// for a 422 (e.g. an invalid email: [{"msg": "value is not a valid email
  /// address: ...", "loc": [...], ...}]). The previous version of this
  /// screen only ever checked for a string, so a 422 — the single most
  /// likely error a real user hits (a typo'd email) — silently fell through
  /// to a generic "check your details" with no actual detail. Confirmed
  /// live against the backend: POST /auth/register with a malformed email
  /// returns exactly this list shape.
  String? _extractErrorDetail(DioException e) {
    final data = e.response?.data;
    if (data is! Map) return null;
    final detail = data['detail'];
    if (detail is String) return detail;
    if (detail is List && detail.isNotEmpty) {
      final first = detail.first;
      if (first is Map && first['msg'] is String) return first['msg'] as String;
    }
    return null;
  }

  Future<void> _register(LocaleService locale) async {
    final fullName = _fullNameController.text.trim();
    final username = _usernameController.text.trim();
    final email = _emailController.text.trim();
    final phone = _phoneController.text.trim();
    final password = _passwordController.text;

    if (fullName.isEmpty || username.isEmpty || email.isEmpty || password.isEmpty) {
      setState(() => _error = locale.t('fill_required_fields'));
      return;
    }
    if (username.length < 3) {
      setState(() => _error = locale.t('username_too_short'));
      return;
    }
    if (password.length < 8) {
      setState(() => _error = locale.t('password_too_short'));
      return;
    }

    setState(() {
      _isLoading = true;
      _error = '';
    });

    try {
      await ApiService().client.post('/auth/register', data: {
        'username': username,
        'password': password,
        'email': email,
        'full_name': fullName,
        'role': 'PATIENT',
        // Optional — powers SMS appointment reminders. Skippable, same as
        // the web portal's registration form.
        if (phone.isNotEmpty) 'phone': phone,
      });

      // Register doesn't return a token; log in with the new credentials.
      final response = await ApiService().client.post(
        '/auth/login',
        data: {'username': username, 'password': password},
        options: Options(contentType: Headers.formUrlEncodedContentType),
      );

      final token = response.data['access_token'];
      if (token == null) {
        throw Exception('Login after registration did not return a token.');
      }
      await SecureStore().setToken(token as String);
      unawaited(FirebaseNotificationService().syncTokenWithBackend());

      if (mounted) context.go('/');
    } on DioException catch (e) {
      setState(() {
        // Surface the backend's real message (duplicate username/email,
        // invalid email) instead of a generic failure — "Registration
        // failed" with no reason is exactly the complaint this screen
        // exists to eliminate.
        _error = _extractErrorDetail(e) ?? locale.t('registration_failed');
      });
    } catch (e) {
      setState(() {
        _error = locale.t('registration_failed');
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Widget _neuField({
    required TextEditingController controller,
    required String hint,
    required NeumorphicColors neu,
    TextInputType keyboardType = TextInputType.text,
    bool obscure = false,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: neu.background,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
          BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
        ],
      ),
      child: TextField(
        controller: controller,
        keyboardType: keyboardType,
        obscureText: obscure,
        decoration: InputDecoration(
          hintText: hint,
          border: InputBorder.none,
          contentPadding: const EdgeInsets.all(20),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    final locale = context.watch<LocaleService>();
    return Scaffold(
      backgroundColor: neu.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.person_add_alt_1, size: 72, color: Color(0xFF4F46E5)),
                const SizedBox(height: 16),
                Text(
                  locale.t('create_account_title'),
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: neu.foreground),
                ),
                const SizedBox(height: 8),
                Text(
                  locale.t('create_account_subtitle'),
                  style: TextStyle(fontSize: 14, color: neu.foreground.withValues(alpha: 0.6)),
                ),
                const SizedBox(height: 32),

                _neuField(controller: _fullNameController, hint: locale.t('full_name_hint'), neu: neu),
                const SizedBox(height: 18),
                _neuField(controller: _usernameController, hint: locale.t('username_hint'), neu: neu),
                const SizedBox(height: 18),
                _neuField(
                  controller: _emailController,
                  hint: locale.t('email_hint'),
                  neu: neu,
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 18),
                _neuField(
                  controller: _phoneController,
                  hint: locale.t('phone_hint_optional'),
                  neu: neu,
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 18),
                _neuField(
                  controller: _passwordController,
                  hint: locale.t('password_hint_min8'),
                  neu: neu,
                  obscure: true,
                ),

                if (_error.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  Text(
                    _error,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold),
                  ),
                ],

                const SizedBox(height: 32),

                GestureDetector(
                  onTap: _isLoading ? null : () => _register(locale),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    decoration: BoxDecoration(
                      color: const Color(0xFF4F46E5),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                      ],
                    ),
                    child: Center(
                      child: _isLoading
                          ? const CircularProgressIndicator(color: Colors.white)
                          : Text(locale.t('create_account'),
                              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ),

                const SizedBox(height: 20),
                TextButton(
                  onPressed: _isLoading ? null : () => context.go('/login'),
                  child: Text(locale.t('already_have_account')),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
