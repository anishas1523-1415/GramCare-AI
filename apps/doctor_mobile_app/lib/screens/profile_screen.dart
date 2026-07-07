import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/doctor_profile.dart';
import '../services/app_strings.dart';
import '../services/doctor_session.dart';
import '../theme/app_theme.dart';

/// Doctor's own profile — GET/PUT /doctors/me. Also hosts logout and the
/// language toggle for parity with the patient app's profile screen.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _editing = false;
  bool _saving = false;

  final _specialtyController = TextEditingController();
  final _qualificationsController = TextEditingController();
  final _experienceController = TextEditingController();
  final _feeController = TextEditingController();
  final _languagesController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final session = context.read<DoctorSession>();
      if (session.profile == null) {
        await session.loadProfile();
      }
      _resetFields();
    });
  }

  void _resetFields() {
    final profile = context.read<DoctorSession>().profile;
    if (profile == null) return;
    _specialtyController.text = profile.specialty;
    _qualificationsController.text = profile.qualifications ?? '';
    _experienceController.text = profile.experienceYears.toString();
    _feeController.text = profile.consultationFee.toStringAsFixed(0);
    _languagesController.text = profile.languages ?? '';
  }

  @override
  void dispose() {
    _specialtyController.dispose();
    _qualificationsController.dispose();
    _experienceController.dispose();
    _feeController.dispose();
    _languagesController.dispose();
    super.dispose();
  }

  Future<void> _save(LocaleService locale) async {
    setState(() => _saving = true);
    try {
      await context.read<DoctorSession>().updateProfile({
        'specialty': _specialtyController.text.trim(),
        'qualifications': _qualificationsController.text.trim(),
        'experience_years': int.tryParse(_experienceController.text.trim()) ?? 0,
        'consultation_fee': double.tryParse(_feeController.text.trim()) ?? 0.0,
        'languages': _languagesController.text.trim(),
      });
      if (!mounted) return;
      setState(() {
        _saving = false;
        _editing = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(locale.t('profile_updated'))),
      );
    } catch (e) {
      setState(() => _saving = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(locale.t('error_generic'))),
      );
    }
  }

  Future<void> _logout() async {
    await context.read<DoctorSession>().clearOnLogout();
    if (!mounted) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final session = context.watch<DoctorSession>();
    final profile = session.profile;

    return Scaffold(
      appBar: AppBar(
        title: Text(locale.t('profile')),
        actions: [
          if (!_editing && profile != null)
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              tooltip: locale.t('edit_profile'),
              onPressed: () => setState(() => _editing = true),
            ),
        ],
      ),
      body: profile == null
          ? (session.loading
              ? const Center(child: CircularProgressIndicator())
              : Center(child: Text(locale.t('error_generic'))))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Center(
                  child: CircleAvatar(
                    radius: 44,
                    backgroundColor: AppTheme.skyBlue,
                    child: Text(
                      profile.fullName.isNotEmpty ? profile.fullName[0].toUpperCase() : '?',
                      style: const TextStyle(fontSize: 32, color: AppTheme.deepBlue, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Center(
                  child: Text(profile.fullName, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 24),
                if (_editing) ..._editFields(locale) else ..._viewFields(locale, profile),
                const SizedBox(height: 24),
                if (_editing)
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: _saving
                              ? null
                              : () {
                                  setState(() => _editing = false);
                                  _resetFields();
                                },
                          child: Text(locale.t('cancel')),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton(
                          onPressed: _saving ? null : () => _save(locale),
                          child: _saving
                              ? const SizedBox(
                                  height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : Text(locale.t('save')),
                        ),
                      ),
                    ],
                  ),
                const SizedBox(height: 24),
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.language),
                    title: Text(locale.t('language')),
                    trailing: Switch(
                      value: locale.isTamil,
                      activeThumbColor: AppTheme.primaryBlue,
                      onChanged: (v) => locale.setCode(v ? 'ta' : 'en'),
                    ),
                    subtitle: Text(locale.isTamil ? 'தமிழ்' : 'English'),
                  ),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: _logout,
                  icon: const Icon(Icons.logout, color: AppTheme.cancelledRed),
                  label: Text(locale.t('logout'), style: const TextStyle(color: AppTheme.cancelledRed)),
                  style: OutlinedButton.styleFrom(side: const BorderSide(color: AppTheme.cancelledRed)),
                ),
              ],
            ),
    );
  }

  List<Widget> _viewFields(LocaleService locale, DoctorProfile profile) => [
        _infoTile(locale.t('specialty'), profile.specialty),
        _infoTile(locale.t('qualifications'), profile.qualifications ?? '-'),
        _infoTile(locale.t('experience_years'), profile.experienceYears.toString()),
        _infoTile(locale.t('consultation_fee'), 'INR ${profile.consultationFee.toStringAsFixed(0)}'),
        _infoTile(locale.t('languages'), profile.languages ?? '-'),
      ];

  Widget _infoTile(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 12, color: Colors.black54)),
            Text(value, style: const TextStyle(fontSize: 16)),
          ],
        ),
      );

  List<Widget> _editFields(LocaleService locale) => [
        TextField(
          controller: _specialtyController,
          decoration: InputDecoration(labelText: locale.t('specialty')),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _qualificationsController,
          decoration: InputDecoration(labelText: locale.t('qualifications')),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _experienceController,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(labelText: locale.t('experience_years')),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _feeController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: InputDecoration(labelText: locale.t('consultation_fee')),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _languagesController,
          decoration: InputDecoration(labelText: locale.t('languages')),
        ),
      ];
}
