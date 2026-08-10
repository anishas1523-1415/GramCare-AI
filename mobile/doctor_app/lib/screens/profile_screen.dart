import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/doctor_profile.dart';
import '../services/app_strings.dart';
import '../services/doctor_session.dart';
import '../theme/app_theme.dart';

/// Doctor's own profile — GET/PUT /doctors/me, plus the government
/// verification fields (license number, license document, status) that
/// previously had a backend but no screen: a doctor had photo/qualification
/// fields to edit but no way to actually apply for approval or see where
/// their application stood, and the dashboard just 403'd silently instead
/// of pointing here. Mirrors apps/web_portal's /doctor/profile page.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _editing = false;
  bool _saving = false;
  bool _uploadingPhoto = false;
  bool _uploadingDoc = false;

  final _specialtyController = TextEditingController();
  final _qualificationsController = TextEditingController();
  final _experienceController = TextEditingController();
  final _feeController = TextEditingController();
  final _languagesController = TextEditingController();
  final _licenseNumberController = TextEditingController();
  final _serviceHoursController = TextEditingController();

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
    _licenseNumberController.text = profile.licenseNumber ?? '';
    _serviceHoursController.text = profile.serviceHours ?? '';
  }

  @override
  void dispose() {
    _specialtyController.dispose();
    _qualificationsController.dispose();
    _experienceController.dispose();
    _feeController.dispose();
    _languagesController.dispose();
    _licenseNumberController.dispose();
    _serviceHoursController.dispose();
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
        'license_number': _licenseNumberController.text.trim(),
        'service_hours': _serviceHoursController.text.trim(),
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

  Future<void> _uploadPhoto(LocaleService locale) async {
    final session = context.read<DoctorSession>();
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 80);
    if (photo == null) return;
    setState(() => _uploadingPhoto = true);
    try {
      final bytes = await File(photo.path).readAsBytes();
      await session.uploadPhoto(base64Encode(bytes));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('photo_upload_failed'))));
    } finally {
      if (mounted) setState(() => _uploadingPhoto = false);
    }
  }

  Future<void> _uploadLicenseDocument(LocaleService locale) async {
    final session = context.read<DoctorSession>();
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 85);
    if (photo == null) return;
    setState(() => _uploadingDoc = true);
    try {
      final bytes = await File(photo.path).readAsBytes();
      await session.uploadLicenseDocument(base64Encode(bytes));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('document_uploaded'))));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('document_upload_failed'))));
    } finally {
      if (mounted) setState(() => _uploadingDoc = false);
    }
  }

  Future<void> _logout() async {
    await context.read<DoctorSession>().clearOnLogout();
    if (!mounted) return;
    context.go('/login');
  }

  ({Color color, IconData icon, String label}) _statusStyle(DoctorProfile profile, LocaleService locale) {
    if (profile.isApproved) {
      return (color: AppTheme.completedGreen, icon: Icons.verified_outlined, label: locale.t('status_approved'));
    }
    if (profile.isRejected) {
      return (color: AppTheme.cancelledRed, icon: Icons.error_outline, label: locale.t('status_not_approved'));
    }
    return (color: AppTheme.pendingAmber, icon: Icons.hourglass_top_outlined, label: locale.t('status_pending_review'));
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
                  child: Stack(
                    children: [
                      CircleAvatar(
                        radius: 44,
                        backgroundColor: AppTheme.skyBlue,
                        backgroundImage: profile.photoUrl != null ? NetworkImage(profile.photoUrl!) : null,
                        child: profile.photoUrl == null
                            ? Text(
                                profile.fullName.isNotEmpty ? profile.fullName[0].toUpperCase() : '?',
                                style: const TextStyle(fontSize: 32, color: AppTheme.deepBlue, fontWeight: FontWeight.bold),
                              )
                            : null,
                      ),
                      Positioned(
                        right: 0,
                        bottom: 0,
                        child: InkWell(
                          onTap: _uploadingPhoto ? null : () => _uploadPhoto(locale),
                          child: CircleAvatar(
                            radius: 15,
                            backgroundColor: AppTheme.primaryBlue,
                            child: _uploadingPhoto
                                ? const SizedBox(
                                    height: 14, width: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                : const Icon(Icons.camera_alt, size: 15, color: Colors.white),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                Center(
                  child: Text(profile.fullName, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 10),
                Center(child: _statusChip(profile, locale)),
                if (profile.isRejected && profile.rejectionReason != null) ...[
                  const SizedBox(height: 14),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.cancelledRed.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppTheme.cancelledRed.withValues(alpha: 0.3)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(locale.t('rejection_reason'), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                        const SizedBox(height: 4),
                        Text(profile.rejectionReason!),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 20),
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
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(locale.t('license_document'), style: const TextStyle(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 4),
                        Text(locale.t('license_document_note'),
                            style: const TextStyle(fontSize: 12, color: Colors.black54)),
                        if (profile.licenseDocumentUrl != null) ...[
                          const SizedBox(height: 8),
                          Text(locale.t('view_document'),
                              style: const TextStyle(fontSize: 12, color: AppTheme.primaryBlue, decoration: TextDecoration.underline)),
                        ],
                        const SizedBox(height: 12),
                        OutlinedButton.icon(
                          onPressed: _uploadingDoc ? null : () => _uploadLicenseDocument(locale),
                          icon: const Icon(Icons.upload_file_outlined, size: 18),
                          label: Text(_uploadingDoc
                              ? locale.t('uploading')
                              : profile.licenseDocumentUrl != null
                                  ? locale.t('replace_document')
                                  : locale.t('upload_document')),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
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

  Widget _statusChip(DoctorProfile profile, LocaleService locale) {
    final style = _statusStyle(profile, locale);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      decoration: BoxDecoration(
        color: style.color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: style.color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(style.icon, size: 15, color: style.color),
          const SizedBox(width: 6),
          Text(style.label, style: TextStyle(color: style.color, fontWeight: FontWeight.bold, fontSize: 12)),
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
        _infoTile(locale.t('license_number'), profile.licenseNumber ?? '-'),
        _infoTile(locale.t('service_hours'), profile.serviceHours ?? '-'),
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
        const SizedBox(height: 12),
        TextField(
          controller: _licenseNumberController,
          decoration: InputDecoration(labelText: locale.t('license_number'), hintText: locale.t('license_number_hint')),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _serviceHoursController,
          decoration: InputDecoration(labelText: locale.t('service_hours'), hintText: locale.t('service_hours_hint')),
        ),
      ];
}
