import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/neumorphic_colors.dart';

/// Digital Health Passport — blood group, allergies and chronic conditions,
/// plus the QR code that opens the public, no-login view of them.
///
/// The web portal has had this since the passport module shipped; the phone
/// did not, which is backwards: the QR exists precisely so a paramedic or
/// hospital desk can read a patient's critical details off the phone in
/// their hand, without a GramCare account. Mirrors /passport on the web —
/// same GET/PUT /passport/me and POST /passport/me/regenerate-token.
class HealthPassportScreen extends StatefulWidget {
  const HealthPassportScreen({super.key});

  @override
  State<HealthPassportScreen> createState() => _HealthPassportScreenState();
}

class _HealthPassportScreenState extends State<HealthPassportScreen> {
  // Module theme: emergency red, matching the web passport page.
  static const _theme = Color(0xFFEF4444);

  final _bloodGroup = TextEditingController();
  final _allergies = TextEditingController();
  final _conditions = TextEditingController();

  bool _loading = true;
  bool _saving = false;
  bool _regenerating = false;
  String? _error;
  String? _success;
  String? _token;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _bloodGroup.dispose();
    _allergies.dispose();
    _conditions.dispose();
    super.dispose();
  }

  void _apply(Map<String, dynamic> data) {
    _bloodGroup.text = (data['blood_group'] ?? '') as String;
    _allergies.text = (data['allergies'] ?? '') as String;
    _conditions.text = (data['chronic_conditions'] ?? '') as String;
    _token = data['passport_token'] as String?;
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await ApiService().client.get('/passport/me');
      if (!mounted) return;
      setState(() {
        _apply(Map<String, dynamic>.from(res.data as Map));
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('passport_load_failed');
        _loading = false;
      });
    }
  }

  Future<void> _save() async {
    final locale = context.read<LocaleService>();
    setState(() {
      _saving = true;
      _error = null;
      _success = null;
    });
    try {
      final res = await ApiService().client.put('/passport/me', data: {
        'blood_group': _bloodGroup.text.trim().isEmpty ? null : _bloodGroup.text.trim(),
        'allergies': _allergies.text.trim().isEmpty ? null : _allergies.text.trim(),
        'chronic_conditions': _conditions.text.trim().isEmpty ? null : _conditions.text.trim(),
      });
      if (!mounted) return;
      setState(() {
        _apply(Map<String, dynamic>.from(res.data as Map));
        _success = locale.t('passport_saved');
        _saving = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = locale.t('passport_save_failed');
        _saving = false;
      });
    }
  }

  Future<void> _regenerate() async {
    final locale = context.read<LocaleService>();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(locale.t('passport_new_code')),
        content: Text(locale.t('passport_regenerate_confirm')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(locale.t('cancel'))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: Text(locale.t('passport_new_code'))),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() {
      _regenerating = true;
      _error = null;
      _success = null;
    });
    try {
      final res = await ApiService().client.post('/passport/me/regenerate-token');
      if (!mounted) return;
      setState(() {
        _apply(Map<String, dynamic>.from(res.data as Map));
        _success = locale.t('passport_new_code_done');
        _regenerating = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = locale.t('passport_regenerate_failed');
        _regenerating = false;
      });
    }
  }

  /// Must match the web portal's public route, since that is what the QR
  /// resolves to for whoever scans it.
  String get _publicUrl => 'https://gram-care-ai.vercel.app/passport/view/$_token';

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final neu = Theme.of(context).extension<NeumorphicColors>()!;

    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(title: Text(locale.t('health_passport'))),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  locale.t('passport_subtitle'),
                  style: const TextStyle(fontSize: 14, color: Colors.black54),
                ),
                const SizedBox(height: 16),

                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(_error!, style: const TextStyle(color: _theme, fontWeight: FontWeight.bold)),
                  ),
                if (_success != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(_success!, style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold)),
                  ),

                _field(locale.t('blood_group'), _bloodGroup, hint: 'O+'),
                _field(locale.t('allergies'), _allergies, hint: locale.t('allergies_hint'), lines: 2),
                _field(locale.t('chronic_conditions'), _conditions, hint: locale.t('chronic_conditions_hint'), lines: 2),

                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _saving ? null : _save,
                    icon: const Icon(Icons.save),
                    label: Text(_saving ? locale.t('saving') : locale.t('save')),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _theme,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),

                const SizedBox(height: 28),
                if (_token != null && _token!.isNotEmpty) ...[
                  Center(
                    child: Column(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: QrImageView(
                            data: _publicUrl,
                            size: 200,
                            backgroundColor: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 8),
                          child: Text(
                            locale.t('passport_qr_note'),
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 12, color: Colors.black54),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          alignment: WrapAlignment.center,
                          children: [
                            OutlinedButton.icon(
                              onPressed: () async {
                                await Clipboard.setData(ClipboardData(text: _publicUrl));
                                if (!context.mounted) return;
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text(locale.t('passport_link_copied'))),
                                );
                              },
                              icon: const Icon(Icons.copy, size: 16),
                              label: Text(locale.t('passport_copy_link')),
                            ),
                            OutlinedButton.icon(
                              onPressed: _regenerating ? null : _regenerate,
                              icon: const Icon(Icons.refresh, size: 16),
                              label: Text(_regenerating ? locale.t('saving') : locale.t('passport_new_code')),
                              style: OutlinedButton.styleFrom(foregroundColor: _theme),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ] else
                  Center(
                    child: Text(
                      locale.t('passport_save_for_qr'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 13, color: Colors.black54),
                    ),
                  ),
                const SizedBox(height: 32),
              ],
            ),
    );
  }

  Widget _field(String label, TextEditingController controller, {String? hint, int lines = 1}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          TextField(
            controller: controller,
            maxLines: lines,
            decoration: InputDecoration(
              hintText: hint,
              filled: true,
              fillColor: Colors.white,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ],
      ),
    );
  }
}
