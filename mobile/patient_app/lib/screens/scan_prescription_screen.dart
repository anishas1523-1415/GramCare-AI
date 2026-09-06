import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../services/sync_service.dart';
import '../theme/neumorphic_colors.dart';

/// OCR prescription/report scanner — the planning doc's second wallet entry
/// path: "வெளியில போய் வாங்குற பிரிஸ்கிரிப்ஷனை ஆப்ல போட்டோ எடுக்கலாம்.
/// AI படிச்சு, என்ன மருந்துகள் இருக்குன்னு தெளிவா பதிவு செஞ்சுக்கும்."
///
/// Flow: capture photo -> POST /triage/ocr (Gemini Vision) -> user CONFIRMS
/// the extracted text (AI never saves unreviewed clinical data) -> stored in
/// the offline wallet and queued for idempotent sync.
class ScanPrescriptionScreen extends StatefulWidget {
  const ScanPrescriptionScreen({super.key});

  @override
  State<ScanPrescriptionScreen> createState() => _ScanPrescriptionScreenState();
}

class _ScanPrescriptionScreenState extends State<ScanPrescriptionScreen> {
  final ImagePicker _picker = ImagePicker();
  XFile? _image;
  bool _processing = false;
  String _error = '';
  String? _extractedText;
  List<String> _medicines = [];
  double _confidence = 0;

  Future<void> _capture(ImageSource source) async {
    setState(() {
      _error = '';
      _extractedText = null;
      _medicines = [];
    });
    try {
      final img = await _picker.pickImage(
        source: source,
        maxWidth: 1600,
        imageQuality: 80,
      );
      if (img == null) return;
      setState(() => _image = img);
      await _runOcr(img);
    } catch (e) {
      setState(() => _error = context.read<LocaleService>().t('camera_open_failed'));
    }
  }

  Future<void> _runOcr(XFile img) async {
    setState(() => _processing = true);
    try {
      final bytes = await File(img.path).readAsBytes();
      final res = await ApiService().client.post('/triage/ocr', data: {
        'image_base64': base64Encode(bytes),
      });
      final data = res.data as Map<String, dynamic>;
      setState(() {
        _extractedText = data['extracted_text'] as String? ?? '';
        _medicines = List<String>.from(data['medicines_parsed'] as List? ?? const []);
        _confidence = (data['confidence'] as num?)?.toDouble() ?? 0;
      });
    } catch (e) {
      setState(() => _error = context.read<LocaleService>().t('ocr_read_failed'));
    } finally {
      setState(() => _processing = false);
    }
  }

  /// Medicine Information Assistant (planning doc): tapping a scanned
  /// medicine explains what it's for, dosage guidance, and side effects.
  Future<void> _showMedicineInfo(String medicineName) async {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _MedicineInfoSheet(medicineName: medicineName),
    );
  }

  Future<void> _saveToWallet() async {
    final active = context.read<ProfileService>().active;
    final medsSummary =
        _medicines.isEmpty ? _extractedText ?? '' : _medicines.join('; ');
    await SyncService().createRecord(
      patientName: active?.fullName ?? 'Myself',
      content: 'Medicines: $medsSummary\n\nFull text:\n${_extractedText ?? ''}',
      recordType: 'prescription',
      title: 'Scanned prescription',
      familyProfileId: active?.id,
      doctorName: 'Scanned (outside doctor)',
    );
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(context.read<LocaleService>().t('saved_to_wallet')),
          backgroundColor: const Color(0xFF10B981),
        ),
      );
      context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = context.watch<ProfileService>().active;
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    final locale = context.watch<LocaleService>();

    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: neu.foreground),
          tooltip: locale.t('back'),
          onPressed: () => context.pop(),
        ),
        title: Text(
          active == null ? locale.t('scan_prescription') : '${locale.t('scan_for')} ${active.fullName}',
          style: TextStyle(color: neu.foreground, fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: _bigButton(
                      icon: Icons.photo_camera,
                      label: locale.t('camera'),
                      color: const Color(0xFF8B5CF6),
                      onTap: _processing ? null : () => _capture(ImageSource.camera),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _bigButton(
                      icon: Icons.photo_library,
                      label: locale.t('gallery'),
                      color: const Color(0xFF3B82F6),
                      onTap: _processing ? null : () => _capture(ImageSource.gallery),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              if (_image != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: Image.file(File(_image!.path), height: 220, fit: BoxFit.cover),
                ),

              if (_processing) ...[
                const SizedBox(height: 32),
                const Center(child: CircularProgressIndicator()),
                const SizedBox(height: 12),
                Center(
                  child: Text(locale.t('ai_reading_prescription'),
                      style: TextStyle(color: neu.foregroundMuted)),
                ),
              ],

              if (_error.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(_error,
                    style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
              ],

              if (_extractedText != null && !_processing) ...[
                const SizedBox(height: 24),
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(locale.t('ai_found_medicines'),
                              style: const TextStyle(fontWeight: FontWeight.bold)),
                          Text('${(_confidence * 100).toStringAsFixed(0)}% ${locale.t('sure')}',
                              style: const TextStyle(fontSize: 12, color: Colors.grey)),
                        ],
                      ),
                      const SizedBox(height: 12),
                      if (_medicines.isEmpty)
                        Text(locale.t('no_medicines_recognized'))
                      else
                        ..._medicines.map((m) => InkWell(
                              onTap: () => _showMedicineInfo(m),
                              borderRadius: BorderRadius.circular(8),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(vertical: 6),
                                child: Row(
                                  children: [
                                    const Icon(Icons.medication,
                                        size: 18, color: Color(0xFF8B5CF6)),
                                    const SizedBox(width: 8),
                                    Expanded(child: Text(m)),
                                    const Icon(Icons.info_outline, size: 16, color: Color(0xFF718096)),
                                  ],
                                ),
                              ),
                            )),
                      const Divider(height: 24),
                      Text(locale.t('full_text'),
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, color: Colors.grey, fontSize: 12)),
                      const SizedBox(height: 4),
                      Text(_extractedText!,
                          style: const TextStyle(fontSize: 13, color: Color(0xFF4A5568))),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                // Human confirmation gate — AI output is never auto-saved.
                _bigButton(
                  icon: Icons.check_circle,
                  label: locale.t('save_to_wallet'),
                  color: const Color(0xFF10B981),
                  onTap: _saveToWallet,
                ),
                const SizedBox(height: 12),
                _bigButton(
                  icon: Icons.refresh,
                  label: locale.t('retake_photo'),
                  color: const Color(0xFF718096),
                  onTap: () => _capture(ImageSource.camera),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _bigButton({
    required IconData icon,
    required String label,
    required Color color,
    VoidCallback? onTap,
  }) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 18),
        decoration: BoxDecoration(
          color: onTap == null ? color.withValues(alpha: 0.4) : color,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: Colors.white),
            const SizedBox(width: 8),
            Flexible(
              child: Text(label,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }
}

/// Bottom sheet backing the Medicine Information Assistant
/// (GET /pharmacy/medicine-info) — purpose, dosage guidance, side effects,
/// and precautions for a tapped medicine name.
class _MedicineInfoSheet extends StatefulWidget {
  final String medicineName;
  const _MedicineInfoSheet({required this.medicineName});

  @override
  State<_MedicineInfoSheet> createState() => _MedicineInfoSheetState();
}

class _MedicineInfoSheetState extends State<_MedicineInfoSheet> {
  bool _loading = true;
  String _error = '';
  Map<String, dynamic>? _info;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    try {
      final res = await ApiService().client.get('/pharmacy/medicine-info',
          queryParameters: {'medicine': widget.medicineName});
      if (mounted) setState(() => _info = res.data as Map<String, dynamic>);
    } catch (_) {
      if (mounted) setState(() => _error = context.read<LocaleService>().t('medicine_info_failed'));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Widget _row(String label, String? value, IconData icon, Color color) {
    if (value == null || value.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: color)),
                const SizedBox(height: 4),
                Text(value, style: TextStyle(fontSize: 14, color: Theme.of(context).extension<NeumorphicColors>()!.foreground)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    final locale = context.watch<LocaleService>();
    return Container(
      padding: EdgeInsets.only(
        left: 24, right: 24, top: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 32,
      ),
      decoration: BoxDecoration(
        color: neu.background,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 40, height: 4,
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(color: Colors.grey.shade400, borderRadius: BorderRadius.circular(2)),
            ),
          ),
          Row(
            children: [
              const Icon(Icons.medication, color: Color(0xFF8B5CF6)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(widget.medicineName,
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: neu.foreground)),
              ),
            ],
          ),
          const SizedBox(height: 20),
          if (_loading)
            const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
          else if (_error.isNotEmpty)
            Text(_error, style: const TextStyle(color: Colors.red))
          else if (_info != null) ...[
            _row(locale.t('what_its_for'), _info!['purpose'] as String?, Icons.info, const Color(0xFF3B82F6)),
            _row(locale.t('dosage_guidance'), _info!['dosage_guidance'] as String?, Icons.schedule, const Color(0xFF10B981)),
            _row(locale.t('side_effects_watch'), _info!['side_effects'] as String?, Icons.warning_amber, Colors.deepOrange),
            _row(locale.t('precautions'), _info!['precautions'] as String?, Icons.shield_outlined, Colors.indigo),
          ],
        ],
      ),
    );
  }
}
