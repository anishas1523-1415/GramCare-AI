import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/profile_service.dart';
import '../services/sync_service.dart';

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
      setState(() => _error = 'Could not open camera/gallery.');
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
      setState(() => _error =
          'Could not read the prescription. Check your connection and try again.');
    } finally {
      setState(() => _processing = false);
    }
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
        const SnackBar(
          content: Text('Saved to Health Wallet — will sync when online'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
      context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = context.watch<ProfileService>().active;

    return Scaffold(
      backgroundColor: const Color(0xFFE0E5EC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF2D3748)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          active == null ? 'Scan Prescription' : 'Scan for ${active.fullName}',
          style: const TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.bold),
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
                      label: 'Camera',
                      color: const Color(0xFF8B5CF6),
                      onTap: _processing ? null : () => _capture(ImageSource.camera),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _bigButton(
                      icon: Icons.photo_library,
                      label: 'Gallery',
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
                const Center(
                  child: Text('AI is reading the prescription…',
                      style: TextStyle(color: Color(0xFF718096))),
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
                          const Text('AI found these medicines:',
                              style: TextStyle(fontWeight: FontWeight.bold)),
                          Text('${(_confidence * 100).toStringAsFixed(0)}% sure',
                              style: const TextStyle(fontSize: 12, color: Colors.grey)),
                        ],
                      ),
                      const SizedBox(height: 12),
                      if (_medicines.isEmpty)
                        const Text('No medicines recognized — check the photo quality.')
                      else
                        ..._medicines.map((m) => Padding(
                              padding: const EdgeInsets.only(bottom: 6),
                              child: Row(
                                children: [
                                  const Icon(Icons.medication,
                                      size: 18, color: Color(0xFF8B5CF6)),
                                  const SizedBox(width: 8),
                                  Expanded(child: Text(m)),
                                ],
                              ),
                            )),
                      const Divider(height: 24),
                      const Text('Full text:',
                          style: TextStyle(
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
                  label: 'Looks right — Save to Wallet',
                  color: const Color(0xFF10B981),
                  onTap: _saveToWallet,
                ),
                const SizedBox(height: 12),
                _bigButton(
                  icon: Icons.refresh,
                  label: 'Retake photo',
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
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 18),
        decoration: BoxDecoration(
          color: onTap == null ? color.withOpacity(0.4) : color,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
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
