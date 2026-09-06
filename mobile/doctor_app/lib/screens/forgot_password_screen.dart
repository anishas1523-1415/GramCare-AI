import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';

/// Self-service password reset. The web portal has had /forgot-password and
/// /reset-password since the backend's POST /auth/forgot-password and
/// POST /auth/reset-password were built — this app just never grew a
/// matching screen, so a doctor who forgot their password had no in-app
/// recovery path at all.
///
/// The reset link itself still opens in a browser (it points at the web
/// portal's /reset-password?token=... page) rather than deep-linking back
/// into this app — same approach the patient app now uses, and simplest
/// given the backend already emails a web URL. This screen's job is just
/// the "request a reset link" half of the flow.
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _emailController = TextEditingController();
  bool _submitting = false;
  bool _sent = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _submit(LocaleService locale) async {
    final email = _emailController.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = locale.t('enter_valid_email'));
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      // The endpoint always returns a generic success message regardless of
      // whether the email exists, to avoid leaking which emails are
      // registered — so there is no error branch to distinguish here beyond
      // a network/server failure.
      await ApiService().client.post('/auth/forgot-password', data: {'email': email});
      if (mounted) setState(() => _sent = true);
    } on DioException catch (_) {
      setState(() => _error = locale.t('reset_request_failed'));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      appBar: AppBar(title: Text(locale.t('reset_password_title')), backgroundColor: Colors.transparent, foregroundColor: AppTheme.deepBlue, elevation: 0),
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
                  Icon(_sent ? Icons.mark_email_read_outlined : Icons.lock_reset, size: 64, color: AppTheme.primaryBlue),
                  const SizedBox(height: 18),
                  if (_sent) ...[
                    Text(
                      locale.t('reset_link_sent'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 15.5, color: Colors.black87),
                    ),
                    const SizedBox(height: 26),
                    ElevatedButton(onPressed: () => context.go('/login'), child: Text(locale.t('back_to_login'))),
                  ] else ...[
                    Text(
                      locale.t('reset_password_tagline'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 14, color: Colors.black54),
                    ),
                    const SizedBox(height: 26),
                    TextField(
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      decoration: InputDecoration(labelText: locale.t('email_hint'), prefixIcon: const Icon(Icons.email_outlined)),
                      onSubmitted: (_) => _submitting ? null : _submit(locale),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 16),
                      Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.cancelledRed, fontWeight: FontWeight.bold)),
                    ],
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: _submitting ? null : () => _submit(locale),
                      child: _submitting
                          ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : Text(locale.t('send_reset_link')),
                    ),
                    const SizedBox(height: 12),
                    TextButton(onPressed: () => context.go('/login'), child: Text(locale.t('back_to_login'))),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
