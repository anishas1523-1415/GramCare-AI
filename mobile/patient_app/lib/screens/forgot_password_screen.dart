import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../services/api_service.dart';
import '../theme/neumorphic_colors.dart';

/// Self-service password reset. The backend's POST /auth/forgot-password
/// has been live since the web portal's own /forgot-password page was
/// built, but this app never grew a matching screen — a patient who forgot
/// their password had no in-app recovery path, only "contact support" or
/// finding the web portal.
///
/// The emailed reset link opens the web portal's /reset-password page
/// rather than deep-linking back into this app — this screen only covers
/// the "request a reset link" half of the flow.
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final TextEditingController _emailController = TextEditingController();
  bool _isLoading = false;
  bool _sent = false;
  String _error = '';

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _emailController.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = 'Enter a valid email address.');
      return;
    }
    setState(() {
      _isLoading = true;
      _error = '';
    });
    try {
      // Always returns a generic success message regardless of whether the
      // email is registered, to avoid leaking which emails exist.
      await ApiService().client.post('/auth/forgot-password', data: {'email': email});
      if (mounted) setState(() => _sent = true);
    } on DioException catch (_) {
      setState(() => _error = 'Could not send the reset link. Please check your connection and try again.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    return Scaffold(
      backgroundColor: neu.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  _sent ? Icons.mark_email_read_outlined : Icons.lock_reset,
                  size: 72,
                  color: const Color(0xFF4F46E5),
                ),
                const SizedBox(height: 20),
                if (_sent) ...[
                  Text(
                    "If that email is registered, we've sent a reset link to it. Check your inbox.",
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 15.5, color: neu.foreground),
                  ),
                  const SizedBox(height: 32),
                  GestureDetector(
                    onTap: () => context.go('/login'),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 20),
                      decoration: BoxDecoration(
                        color: const Color(0xFF4F46E5),
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8)],
                      ),
                      child: const Center(
                        child: Text('Back to Sign In', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                      ),
                    ),
                  ),
                ] else ...[
                  Text(
                    'Reset your password',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: neu.foreground),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    "Enter your account email and we'll send you a reset link.",
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 14, color: neu.foreground.withValues(alpha: 0.6)),
                  ),
                  const SizedBox(height: 32),
                  Container(
                    decoration: BoxDecoration(
                      color: neu.background,
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                        BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
                      ],
                    ),
                    child: TextField(
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(
                        hintText: 'Email',
                        border: InputBorder.none,
                        contentPadding: EdgeInsets.all(20),
                      ),
                      onSubmitted: (_) => _isLoading ? null : _submit(),
                    ),
                  ),
                  if (_error.isNotEmpty) ...[
                    const SizedBox(height: 20),
                    Text(_error, textAlign: TextAlign.center, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                  ],
                  const SizedBox(height: 32),
                  GestureDetector(
                    onTap: _isLoading ? null : _submit,
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 20),
                      decoration: BoxDecoration(
                        color: const Color(0xFF4F46E5),
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8)],
                      ),
                      child: Center(
                        child: _isLoading
                            ? const CircularProgressIndicator(color: Colors.white)
                            : const Text('Send Reset Link', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: _isLoading ? null : () => context.go('/login'),
                    child: const Text('Back to Sign In'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
