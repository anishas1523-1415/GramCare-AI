import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';

/// Doctor self-registration. Previously this app had no registration
/// surface at all — a doctor's only path onto the platform was the web
/// portal, even though the APK is how most doctors actually receive the
/// app. The backend gates DOCTOR registration behind two server-side
/// checks, both mirrored here exactly as the web portal implements them:
///
/// 1. Phone OTP proof-of-ownership (POST /auth/phone/send-otp, then
///    POST /auth/phone/verify-otp) must complete within the 15 minutes
///    before POST /auth/register, or the server rejects the submission
///    with "Please verify this phone number with an OTP before
///    registering."
/// 2. Every non-PATIENT role needs to click an emailed verification link
///    before login succeeds, and a DOCTOR account additionally needs a
///    government reviewer's approval before appointments/patients unlock
///    (see ProfileScreen's "application under review" state) — so
///    registering here never auto-logs in; it lands back on Sign In with
///    a "check your email" message instead.
class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _fullNameController = TextEditingController();
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _phoneController = TextEditingController();
  final _otpController = TextEditingController();

  bool _otpSent = false;
  bool _phoneVerified = false;
  bool _sendingOtp = false;
  bool _verifyingOtp = false;
  bool _submitting = false;
  String? _error;
  String? _info;

  @override
  void dispose() {
    _fullNameController.dispose();
    _usernameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _phoneController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  /// Same shape-handling as the web portal / patient app: FastAPI's
  /// `detail` is a plain string for most errors but a list of
  /// validation-error objects for a 422 (e.g. a malformed email).
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

  Future<void> _sendOtp(LocaleService locale) async {
    final phone = _phoneController.text.trim();
    if (phone.length < 8) {
      setState(() => _error = locale.t('enter_valid_phone'));
      return;
    }
    setState(() {
      _sendingOtp = true;
      _error = null;
    });
    try {
      await ApiService().client.post('/auth/phone/send-otp', data: {'phone': phone});
      setState(() => _otpSent = true);
    } on DioException catch (e) {
      setState(() => _error = _extractErrorDetail(e) ?? locale.t('otp_send_failed'));
    } finally {
      if (mounted) setState(() => _sendingOtp = false);
    }
  }

  Future<void> _verifyOtp(LocaleService locale) async {
    final phone = _phoneController.text.trim();
    final otp = _otpController.text.trim();
    if (otp.isEmpty) return;
    setState(() {
      _verifyingOtp = true;
      _error = null;
    });
    try {
      await ApiService().client.post('/auth/phone/verify-otp', data: {'phone': phone, 'otp': otp});
      setState(() => _phoneVerified = true);
    } on DioException catch (e) {
      setState(() => _error = _extractErrorDetail(e) ?? locale.t('otp_incorrect'));
    } finally {
      if (mounted) setState(() => _verifyingOtp = false);
    }
  }

  Future<void> _register(LocaleService locale) async {
    final fullName = _fullNameController.text.trim();
    final username = _usernameController.text.trim();
    final email = _emailController.text.trim();
    final phone = _phoneController.text.trim();
    final password = _passwordController.text;

    if (fullName.isEmpty || username.isEmpty || email.isEmpty || password.isEmpty || phone.isEmpty) {
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
    if (!_phoneVerified) {
      setState(() => _error = locale.t('verify_phone_first'));
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
        'role': 'DOCTOR',
        'phone': phone,
      });

      if (!mounted) return;
      // DOCTOR must click the emailed verification link before login will
      // succeed — no point attempting an auto-login here.
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
                      color: AppTheme.primaryBlue,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Icon(Icons.person_add_alt_1, color: Colors.white, size: 40),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    locale.t('create_doctor_account'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: AppTheme.deepBlue),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    locale.t('create_doctor_account_subtitle'),
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
                    controller: _passwordController,
                    obscureText: true,
                    decoration: InputDecoration(labelText: locale.t('password_hint_min8'), prefixIcon: const Icon(Icons.lock_outline)),
                  ),
                  const SizedBox(height: 20),

                  // Phone OTP — required for DOCTOR before registration.
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.skyBlue,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.verified_user_outlined, size: 18, color: AppTheme.deepBlue),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                locale.t('verify_phone_note'),
                                style: const TextStyle(fontSize: 12.5, color: AppTheme.deepBlue, fontWeight: FontWeight.w600),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Expanded(
                              child: TextField(
                                controller: _phoneController,
                                enabled: !_phoneVerified,
                                keyboardType: TextInputType.phone,
                                decoration: InputDecoration(labelText: locale.t('phone_hint'), filled: true, fillColor: Colors.white),
                              ),
                            ),
                            const SizedBox(width: 10),
                            if (_phoneVerified)
                              const Icon(Icons.check_circle, color: AppTheme.completedGreen, size: 30)
                            else
                              ElevatedButton(
                                onPressed: _sendingOtp ? null : () => _sendOtp(locale),
                                child: _sendingOtp
                                    ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                    : Text(_otpSent ? locale.t('resend_otp') : locale.t('send_otp')),
                              ),
                          ],
                        ),
                        if (_otpSent && !_phoneVerified) ...[
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _otpController,
                                  keyboardType: TextInputType.number,
                                  decoration: InputDecoration(labelText: locale.t('otp_hint'), filled: true, fillColor: Colors.white),
                                ),
                              ),
                              const SizedBox(width: 10),
                              ElevatedButton(
                                onPressed: _verifyingOtp ? null : () => _verifyOtp(locale),
                                child: _verifyingOtp
                                    ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                    : Text(locale.t('verify_otp')),
                              ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),

                  if (_error != null) ...[
                    const SizedBox(height: 18),
                    Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.cancelledRed, fontWeight: FontWeight.bold)),
                  ],
                  if (_info != null) ...[
                    const SizedBox(height: 18),
                    Text(_info!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.completedGreen, fontWeight: FontWeight.w600)),
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
