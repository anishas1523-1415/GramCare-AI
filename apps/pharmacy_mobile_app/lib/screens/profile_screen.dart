import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../services/secure_store.dart';
import '../theme.dart';

/// GET /pharmacy/me -> schemas.PharmacyResponse (name, address, phone, lat/lng).
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _service = PharmacyService();
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _pharmacy;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final pharmacy = await _service.getMyPharmacy();
      setState(() {
        _pharmacy = pharmacy;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
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
      appBar: AppBar(title: Text(locale.t('profile'))),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              // Previously a dead end: no RefreshIndicator and no Retry
              // button here, unlike every other screen in this app — a
              // pharmacist who hit a transient failure had to navigate
              // away and back to try again.
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      Icon(Icons.error_outline, size: 48, color: Colors.grey.shade400),
                      const SizedBox(height: 12),
                      Center(child: Text(locale.t('no_profile'))),
                      const SizedBox(height: 12),
                      Center(
                        child: OutlinedButton(onPressed: _load, child: Text(locale.t('retry'))),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    Center(
                      child: CircleAvatar(
                        radius: 44,
                        backgroundColor: PharmacyTheme.lightGreen,
                        child: const Icon(Icons.storefront, size: 44, color: PharmacyTheme.primaryGreen),
                      ),
                    ),
                    const SizedBox(height: 20),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _profileRow(locale.t('pharmacy_name'), _pharmacy?['name'] as String? ?? '-'),
                            const Divider(),
                            _profileRow(locale.t('address'), _pharmacy?['address'] as String? ?? '-'),
                            const Divider(),
                            _profileRow(locale.t('phone'), _pharmacy?['phone'] as String? ?? '-'),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    ListTile(
                      leading: const Icon(Icons.language, color: PharmacyTheme.primaryGreen),
                      title: Text(locale.t('language')),
                      trailing: Switch(
                        value: locale.isTamil,
                        onChanged: (v) => locale.setCode(v ? 'ta' : 'en'),
                        activeThumbColor: PharmacyTheme.primaryGreen,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton.icon(
                      onPressed: _logout,
                      icon: const Icon(Icons.logout),
                      label: Text(locale.t('logout')),
                      style: ElevatedButton.styleFrom(backgroundColor: PharmacyTheme.statusOut),
                    ),
                  ],
                  ),
                ),
    );
  }

  Widget _profileRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label, style: const TextStyle(color: Colors.black54))),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w600), textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}
