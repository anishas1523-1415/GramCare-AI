import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme.dart';

/// Pharmacist self-registration. Previously this app had no registration
/// surface at all — only login — so a pharmacist's only path onto the
/// platform was the web portal (which itself has no pharmacist-facing
/// section either; see the login page's role list). Unlike DOCTOR/HOSPITAL,
/// the backend does NOT require phone-OTP proof for PHARMACIST
/// registration (modules/auth/router.py's register_user only gates
/// DOCTOR/HOSPITAL), so this form is a plain create-account flow.
///
/// PHARMACIST is still a non-PATIENT role, so POST /auth/register does not
/// return a token here either — the account needs the emailed verification
/// link clicked before POST /auth/login will succeed, same as every other
/// professional role.
class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _fullNameController = TextEditingController();
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _fullNameController.dispose();
    _usernameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

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
      _submitting = true;
      _error = null;
    });

    try {
      await ApiService().client.post('/auth/register', data: {
        'username': username,
        'password': password,
        'email': email,
        'full_name': fullName,
        'role': 'PHARMACIST',
        if (phone.isNotEmpty) 'phone': phone,
      });

      if (!mounted) return;
      context.go('/login');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(locale.t('registration_check_email')), duration: const Duration(seconds: 6)),
      );
    } on DioException catch (e) {
      setState(() => _error = _extractErrorDetail(e) ?? locale.t('registration_failed'));
    } catch (_) {
      setState(() => _error = locale.t('registration_failed'));
    } finally {
      if (mounted) setState(() => _submitting = false);
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
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Container(
                    width: 76,
                    height: 76,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: PharmacyTheme.primaryGreen,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Icon(Icons.person_add_alt_1, color: Colors.white, size: 40),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    locale.t('create_pharmacy_account'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: PharmacyTheme.darkGreen),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    locale.t('create_pharmacy_account_subtitle'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 13.5, color: Colors.black54),
                  ),
                  const SizedBox(height: 28),

                  TextField(
                    controller: _fullNameController,
                    decoration: InputDecoration(labelText: locale.t('full_name_hint'), prefixIcon: const Icon(Icons.badge_outlined)),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _usernameController,
                    decoration: InputDecoration(labelText: locale.t('username_hint'), prefixIcon: const Icon(Icons.person_outline)),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    decoration: InputDecoration(labelText: locale.t('email_hint'), prefixIcon: const Icon(Icons.email_outlined)),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _phoneController,
                    keyboardType: TextInputType.phone,
                    decoration: InputDecoration(labelText: locale.t('phone_hint_optional'), prefixIcon: const Icon(Icons.phone_outlined)),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: InputDecoration(labelText: locale.t('password_hint_min8'), prefixIcon: const Icon(Icons.lock_outline)),
                  ),

                  if (_error != null) ...[
                    const SizedBox(height: 18),
                    Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                  ],

                  const SizedBox(height: 26),
                  ElevatedButton(
                    onPressed: _submitting ? null : () => _register(locale),
                    child: _submitting
                        ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(locale.t('create_account')),
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: _submitting ? null : () => context.go('/login'),
                    child: Text(locale.t('already_have_account')),
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
