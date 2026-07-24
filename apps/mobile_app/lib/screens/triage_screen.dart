import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/offline_triage_service.dart';
import '../services/profile_service.dart';
import '../services/sos_service.dart';
import '../services/sync_service.dart';
import '../theme/neumorphic_colors.dart';

/// AI Symptom Checker — voice-first per the planning doc ("ஆப் ஓபன் ஆனதும்
/// அவங்க ஒரு பெரிய மைக் ஐகானை பார்க்கணும்... தமிழ்லயோ லோக்கல்
/// லாங்குவேஜ்லயோ பிரச்சனையை சொல்லலாம்"), with the enriched result set
/// (causes, first aid, treatments, untreated outcome, specialist), voice
/// playback of the result, and an auto-SOS prompt on CRITICAL severity
/// (planning doc journey: "Critical Risk -> Emergency SOS activated").
class TriageScreen extends StatefulWidget {
  const TriageScreen({super.key});

  @override
  State<TriageScreen> createState() => _TriageScreenState();
}

class _TriageScreenState extends State<TriageScreen> {
  final TextEditingController _symptomsController = TextEditingController();
  final stt.SpeechToText _speech = stt.SpeechToText();
  final FlutterTts _tts = FlutterTts();

  bool _isLoading = false;
  bool _listening = false;
  Map<String, dynamic>? _result;
  String _error = '';
  // True when `_result` came from the offline keyword-matching fallback
  // (no network reached /triage/analyze) rather than the real AI.
  bool _isOfflineEstimate = false;
  // Optional photo of a visible symptom (planning doc: "இமேஜும் ஆட்
  // பண்ணலாம்") — distinct from the prescription scanner's OCR photo.
  XFile? _symptomImage;
  final ImagePicker _imagePicker = ImagePicker();

  // Module theme: teal (per-module color identity from the planning doc)
  static const _theme = Color(0xFF2DD4BF);

  @override
  void dispose() {
    _speech.stop();
    _tts.stop();
    super.dispose();
  }

  Future<void> _toggleListening() async {
    final s = context.read<LocaleService>();
    if (_listening) {
      await _speech.stop();
      setState(() => _listening = false);
      return;
    }
    final available = await _speech.initialize(
      onStatus: (status) {
        if (status == 'done' || status == 'notListening') {
          if (mounted) setState(() => _listening = false);
        }
      },
      onError: (_) {
        if (mounted) setState(() => _listening = false);
      },
    );
    if (!available) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Speech recognition unavailable on this device.')),
        );
      }
      return;
    }
    setState(() => _listening = true);
    await _speech.listen(
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        localeId: s.isTamil ? 'ta-IN' : 'en-IN',
      ),
      onResult: (result) {
        setState(() => _symptomsController.text = result.recognizedWords);
      },
    );
  }

  Future<void> _speakResult() async {
    if (_result == null) return;
    final s = context.read<LocaleService>();
    await _tts.setLanguage(s.isTamil ? 'ta-IN' : 'en-IN');
    await _tts.setSpeechRate(0.45);
    final text = [
      _result!['predicted_condition'],
      _result!['doctor_recommendation'],
      _result!['home_remedies'],
      _result!['first_aid'],
    ].whereType<String>().where((t) => t.isNotEmpty).join('. ');
    await _tts.speak(text);
  }

  Future<void> _maybePromptSos(int severityScore) async {
    if (severityScore < 75 || !mounted) return;
    final s = context.read<LocaleService>();
    final send = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.emergency, color: Colors.red, size: 40),
        title: Text(s.t('critical_prompt_title')),
        content: Text(s.t('critical_prompt_body')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(s.t('not_now'))),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.t('send_sos_now')),
          ),
        ],
      ),
    );
    if (send == true && mounted) {
      final active = context.read<ProfileService>().active;
      final res = await SosService().trigger(
        familyProfileId: active?.id,
        voiceNote: _symptomsController.text,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(res.sent ? s.t('sos_sent') : s.t('sos_failed')),
          backgroundColor: res.sent ? Colors.red : Colors.red.shade900,
        ));
      }
    }
  }

  Future<void> _pickSymptomImage(ImageSource source) async {
    try {
      final img = await _imagePicker.pickImage(source: source, maxWidth: 1280, imageQuality: 75);
      if (img != null) setState(() => _symptomImage = img);
    } catch (_) {
      // Camera/gallery unavailable — image stays optional, no error shown.
    }
  }

  Future<void> _analyze() async {
    if (_symptomsController.text.isEmpty) return;
    await _speech.stop();
    if (!mounted) return;

    setState(() {
      _isLoading = true;
      _listening = false;
      _error = '';
      _result = null;
      _isOfflineEstimate = false;
    });

    final active = context.read<ProfileService>().active;

    try {
      String? imageBase64;
      if (_symptomImage != null) {
        final bytes = await File(_symptomImage!.path).readAsBytes();
        imageBase64 = base64Encode(bytes);
      }
      final response = await ApiService().client.post(
        '/triage/analyze',
        data: {
          'symptoms_text': _symptomsController.text,
          'patient_id': 'self',
          'age': active?.age ?? 30,
          'family_profile_id': active?.id,
          'image_base64': imageBase64,
        },
      );

      final data = response.data as Map<String, dynamic>;
      setState(() => _result = data);

      final severityScore = (data['severity_score'] as num?)?.toInt() ?? 0;

      // Persist into the offline Health Wallet (idempotent sync queue).
      await SyncService().createRecord(
        patientName: active?.fullName ?? 'Myself',
        content:
            'Symptoms: ${_symptomsController.text}\nAI: ${data['predicted_condition']} (severity $severityScore/100)\nAdvice: ${data['doctor_recommendation']}',
        recordType: 'triage_log',
        title: data['predicted_condition'] as String?,
        familyProfileId: active?.id,
        doctorName: 'GramCare AI',
        severity: severityScore >= 75
            ? 'CRITICAL'
            : severityScore >= 50
                ? 'HIGH'
                : 'LOW',
      );

      // Planning doc: Critical Risk -> Emergency SOS activated.
      await _maybePromptSos(severityScore);
    } on DioException catch (e) {
      // Mirror the exact offline-detection already used by
      // sos_service.dart's SMS-fallback logic: connectionError /
      // connectionTimeout / receiveTimeout mean the request never reached
      // (or never heard back from) the server — i.e. no connectivity — as
      // opposed to a real server-side error, which should stay a real error.
      final offline = e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout;

      if (!offline) {
        setState(() => _error = context.read<LocaleService>().t('search_failed'));
      } else {
        final estimate = offlineTriageEstimate(_symptomsController.text);
        if (estimate == null) {
          // Never silently claim LOW severity for something the offline
          // table doesn't recognize — say so and point to real care.
          setState(() => _error = context.read<LocaleService>().t('offline_no_match'));
        } else {
          final severityScore = estimate.severity == OfflineSeverity.critical
              ? 90
              : estimate.severity == OfflineSeverity.high
                  ? 60
                  : estimate.severity == OfflineSeverity.moderate
                      ? 35
                      : 10;

          setState(() {
            _result = {
              'predicted_condition': estimate.department,
              'doctor_recommendation': estimate.recommendation,
              'severity_score': severityScore,
            };
            _isOfflineEstimate = true;
          });

          // Still persist into the offline Health Wallet, clearly flagged as
          // an offline estimate rather than a real AI read, so the record
          // trail doesn't misrepresent what actually assessed it.
          await SyncService().createRecord(
            patientName: active?.fullName ?? 'Myself',
            content:
                '[OFFLINE ESTIMATE — not full AI] Symptoms: ${_symptomsController.text}\n'
                'Offline triage: ${estimate.department} (${estimate.severity.label})\n'
                'Advice: ${estimate.recommendation}',
            recordType: 'triage_log',
            title: '${estimate.department} (offline estimate)',
            familyProfileId: active?.id,
            doctorName: 'GramCare AI (offline estimate)',
            severity: severityScore >= 75
                ? 'CRITICAL'
                : severityScore >= 50
                    ? 'HIGH'
                    : 'LOW',
          );

          // Same critical-risk -> Emergency SOS prompt as the online path.
          await _maybePromptSos(severityScore);
        }
      }
    } catch (e) {
      setState(() => _error = context.read<LocaleService>().t('search_failed'));
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Widget _resultRow(String label, String? value, {Color? color}) {
    if (value == null || value.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(height: 28),
        Text(label,
            style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.grey, fontSize: 13)),
        const SizedBox(height: 4),
        Text(value, style: TextStyle(fontSize: 15, color: color ?? const Color(0xFF2D3748))),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<LocaleService>();
    final neu = Theme.of(context).extension<NeumorphicColors>()!;

    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: neu.foreground),
          onPressed: () => context.pop(),
        ),
        title: Text(
          s.t('symptom_checker'),
          style: TextStyle(color: neu.foreground, fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // BIG mic — the voice-first entry point for low-literacy users
              Center(
                child: GestureDetector(
                  onTap: _toggleListening,
                  child: Container(
                    width: 110,
                    height: 110,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _listening ? Colors.red : _theme,
                      boxShadow: [
                        BoxShadow(
                          color: (_listening ? Colors.red : _theme).withValues(alpha: 0.4),
                          blurRadius: _listening ? 30 : 12,
                          spreadRadius: _listening ? 6 : 2,
                        ),
                      ],
                    ),
                    child: Icon(
                      _listening ? Icons.hearing : Icons.mic,
                      size: 52,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Center(
                child: Text(
                  _listening ? s.t('listening') : s.t('speak_symptoms'),
                  style: TextStyle(color: neu.foregroundMuted, fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(height: 24),

              Text(
                s.t('describe_symptoms'),
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: neu.foreground),
              ),
              const SizedBox(height: 12),

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
                  controller: _symptomsController,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    hintText: 'E.g., fever for 3 days with dry cough…',
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.all(20),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Optional symptom photo (planning doc: text/voice plus an
              // optional image — e.g. a rash or visible wound — that the AI
              // factors into the same severity assessment).
              if (_symptomImage == null)
                OutlinedButton.icon(
                  onPressed: () => _pickSymptomImage(ImageSource.camera),
                  icon: const Icon(Icons.add_a_photo_outlined, size: 18),
                  label: Text(s.t('add_symptom_photo')),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: _theme,
                    side: BorderSide(color: _theme),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    minimumSize: const Size.fromHeight(0),
                  ),
                )
              else
                Stack(
                  alignment: Alignment.topRight,
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: Image.file(File(_symptomImage!.path), height: 140, width: double.infinity, fit: BoxFit.cover),
                    ),
                    IconButton(
                      icon: const CircleAvatar(backgroundColor: Colors.black54, child: Icon(Icons.close, color: Colors.white, size: 18)),
                      onPressed: () => setState(() => _symptomImage = null),
                    ),
                  ],
                ),
              const SizedBox(height: 16),

              GestureDetector(
                onTap: _isLoading ? null : _analyze,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  decoration: BoxDecoration(
                    color: _theme,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                    ],
                  ),
                  child: Center(
                    child: _isLoading
                        ? const CircularProgressIndicator(color: Colors.white)
                        : Text(s.t('analyze_with_ai'),
                            style: const TextStyle(
                                color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                  ),
                ),
              ),

              if (_error.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(_error, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
              ],

              // Unmissable — this must never look like a real online result.
              // Bias here is deliberately toward over-caution: the offline
              // table is a small curated keyword-matching safety net, not
              // the real AI, and this banner exists so a user never mistakes
              // one for the other.
              if (_isOfflineEstimate && _result != null) ...[
                const SizedBox(height: 24),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.amber.shade50,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: Colors.amber.shade700, width: 2),
                    boxShadow: [
                      BoxShadow(color: neu.shadowDark, offset: const Offset(3, 3), blurRadius: 6),
                    ],
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.wifi_off_rounded, color: Colors.amber.shade900, size: 22),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          s.t('offline_estimate_banner'),
                          style: TextStyle(
                            color: Colors.amber.shade900,
                            fontWeight: FontWeight.bold,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              if (_result != null) ...[
                const SizedBox(height: 32),
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: _isOfflineEstimate ? Border.all(color: Colors.amber.shade400, width: 1.5) : null,
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
                          Text(s.t('severity_score'),
                              style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
                          Row(children: [
                            Text(
                              '${_result!['severity_score']}/100',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 18,
                                color: ((_result!['severity_score'] as num?) ?? 0) > 50
                                    ? Colors.red
                                    : Colors.green,
                              ),
                            ),
                            IconButton(
                              tooltip: s.t('tap_to_hear'),
                              icon: const Icon(Icons.volume_up, color: _theme),
                              onPressed: _speakResult,
                            ),
                          ]),
                        ],
                      ),
                      _resultRow(s.t('predicted_condition'), _result!['predicted_condition'] as String?),
                      _resultRow(s.t('possible_causes'), _result!['possible_causes'] as String?),
                      _resultRow(s.t('home_remedies'), _result!['home_remedies'] as String?),
                      _resultRow(s.t('first_aid'), _result!['first_aid'] as String?, color: Colors.deepOrange),
                      _resultRow(s.t('doctor_recommendation'), _result!['doctor_recommendation'] as String?),
                      _resultRow(s.t('treatment_options'), _result!['treatment_options'] as String?),
                      _resultRow(s.t('untreated_outcome'), _result!['untreated_outcome'] as String?),
                      _resultRow(s.t('specialist'), _result!['specialist_type'] as String?, color: const Color(0xFF4F46E5)),
                      _resultRow(s.t('recovery_time'), _result!['recovery_time'] as String?),
                      _resultRow(s.t('side_effects'), _result!['side_effects'] as String?, color: Colors.deepOrange),
                      // Explainable AI layer (planning doc): the reasoning
                      // behind the AI's conclusion must be visible, not just
                      // the conclusion — collapsed by default to keep the
                      // primary result scannable for rural/low-literacy users.
                      if ((_result!['explanation'] as String?)?.isNotEmpty == true) ...[
                        const Divider(height: 28),
                        Theme(
                          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                          child: ExpansionTile(
                            tilePadding: EdgeInsets.zero,
                            childrenPadding: const EdgeInsets.only(bottom: 8),
                            title: Row(
                              children: [
                                const Icon(Icons.psychology_alt_outlined, size: 18, color: _theme),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    s.t('why_ai_thinks_this'),
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                  ),
                                ),
                                if (_result!['confidence_score'] != null)
                                  Text(
                                    '${(((_result!['confidence_score'] as num).toDouble()) * 100).round()}%',
                                    style: const TextStyle(fontSize: 12, color: Colors.grey, fontWeight: FontWeight.w600),
                                  ),
                              ],
                            ),
                            children: [
                              Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  _result!['explanation'] as String,
                                  style: const TextStyle(fontSize: 14, color: Color(0xFF2D3748)),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                      if ((_result!['disclaimer'] as String?)?.isNotEmpty == true) ...[
                        const Divider(height: 28),
                        Text(
                          _result!['disclaimer'] as String,
                          style: const TextStyle(fontSize: 11, color: Colors.grey, fontStyle: FontStyle.italic),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
