import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../services/secure_store.dart';
import '../theme.dart';

/// One-time pharmacy onboarding. Every backend endpoint this app depends on
/// (GET /pharmacy/me, /stock, /queue, /expiring, ...) looks up a Pharmacy
/// row by the account's owner_user_id and returns 409 "No pharmacy
/// registered for this account yet" if one doesn't exist — but nothing in
/// this app previously ever called POST /pharmacy/register to create that
/// row. A brand-new pharmacist account (including one created through the
/// registration screen this app now has) hit that 409 on the very first
/// dashboard load and had no way past it: every screen showed a bare
/// "no profile" error forever.
///
/// This screen is shown in place of that dead end — DashboardScreen routes
/// here on a 409 instead of surfacing the generic error state.
class PharmacySetupScreen extends StatefulWidget {
  const PharmacySetupScreen({super.key});

  @override
  State<PharmacySetupScreen> createState() => _PharmacySetupScreenState();
}

class _PharmacySetupScreenState extends State<PharmacySetupScreen> {
  final _service = PharmacyService();
  final _nameController = TextEditingController();
  final _addressController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _nameController.dispose();
    _addressController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _submit(LocaleService locale) async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _error = locale.t('pharmacy_name_required'));
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await _service.registerPharmacy(
        name: name,
        address: _addressController.text.trim(),
        phone: _phoneController.text.trim(),
      );
      if (mounted) context.go('/');
    } on DioException catch (_) {
      setState(() => _error = locale.t('error_generic'));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _logout() async {
    await SecureStore().clearAll();
    if (mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      appBar: AppBar(
        title: Text(locale.t('setup_pharmacy_title')),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(icon: const Icon(Icons.logout), tooltip: locale.t('logout'), onPressed: _logout),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(Icons.storefront, size: 64, color: PharmacyTheme.primaryGreen),
                  const SizedBox(height: 16),
                  Text(
                    locale.t('setup_pharmacy_title'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: PharmacyTheme.darkGreen),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    locale.t('setup_pharmacy_subtitle'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 14, color: Colors.black54),
                  ),
                  const SizedBox(height: 28),
                  TextField(
                    controller: _nameController,
                    decoration: InputDecoration(labelText: locale.t('pharmacy_name'), prefixIcon: const Icon(Icons.storefront_outlined)),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _addressController,
                    decoration: InputDecoration(labelText: locale.t('address'), prefixIcon: const Icon(Icons.location_on_outlined)),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _phoneController,
                    keyboardType: TextInputType.phone,
                    decoration: InputDecoration(labelText: locale.t('phone'), prefixIcon: const Icon(Icons.phone_outlined)),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                  ],
                  const SizedBox(height: 26),
                  ElevatedButton(
                    onPressed: _submitting ? null : () => _submit(locale),
                    child: _submitting
                        ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(locale.t('save')),
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
