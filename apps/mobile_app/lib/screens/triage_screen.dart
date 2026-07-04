import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../services/sos_service.dart';
import '../services/sync_service.dart';

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
      localeId: s.isTamil ? 'ta-IN' : 'en-IN',
      listenOptions: stt.SpeechListenOptions(partialResults: true),
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

  Future<void> _analyze() async {
    if (_symptomsController.text.isEmpty) return;
    await _speech.stop();

    setState(() {
      _isLoading = true;
      _listening = false;
      _error = '';
      _result = null;
    });

    final active = context.read<ProfileService>().active;

    try {
      final response = await ApiService().client.post(
        '/triage/analyze',
        data: {
          'symptoms_text': _symptomsController.text,
          'patient_id': 'self',
          'age': active?.age ?? 30,
          'family_profile_id': active?.id,
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
          s.t('symptom_checker'),
          style: const TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.bold),
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
                          color: (_listening ? Colors.red : _theme).withOpacity(0.4),
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
                  style: const TextStyle(color: Color(0xFF718096), fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(height: 24),

              Text(
                s.t('describe_symptoms'),
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF2D3748)),
              ),
              const SizedBox(height: 12),

              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFE0E5EC),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: const [
                    BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
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
              const SizedBox(height: 24),

              GestureDetector(
                onTap: _isLoading ? null : _analyze,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  decoration: BoxDecoration(
                    color: _theme,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
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

              if (_result != null) ...[
                const SizedBox(height: 32),
                Container(
                  padding: const EdgeInsets.all(24),
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
