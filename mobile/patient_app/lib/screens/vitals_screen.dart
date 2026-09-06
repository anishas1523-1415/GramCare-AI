import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'dart:math';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../theme/neumorphic_colors.dart';

/// Health Vitals Tracker (planning doc): "Steps Tracker, Sleep Analysis
/// (deep sleep vs light sleep breakdown), Heart Rate & Oxygen level
/// monitoring ... presented as graphs ... colorful meters, personal health
/// goals." Real wearable pairing is deliberately on hold per the planning
/// discussion, so entry is manual/demo-filled, but the dashboard itself —
/// history, trend bars, and a step goal ring — is real and backed by
/// GET/POST /ehr/vitals.
class VitalsScreen extends StatefulWidget {
  const VitalsScreen({super.key});

  @override
  State<VitalsScreen> createState() => _VitalsScreenState();
}

class _VitalsScreenState extends State<VitalsScreen> {
  final TextEditingController _heartRateController = TextEditingController();
  final TextEditingController _spO2Controller = TextEditingController();
  final TextEditingController _stepsController = TextEditingController();
  final TextEditingController _deepSleepController = TextEditingController();
  final TextEditingController _lightSleepController = TextEditingController();

  static const int _stepGoal = 6000;

  bool _isStreaming = false;
  bool _saving = false;
  bool _loadingHistory = true;
  List<Map<String, dynamic>> _history = [];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _loadingHistory = true);
    final active = context.read<ProfileService>().active;
    try {
      final res = await ApiService().client.get('/ehr/vitals/history', queryParameters: {
        if (active?.id != null) 'family_profile_id': active!.id,
        'days': 14,
      });
      setState(() => _history = List<Map<String, dynamic>>.from(res.data as List));
    } catch (_) {
      // Offline/first-time — dashboard just shows empty state, not an error.
    } finally {
      if (mounted) setState(() => _loadingHistory = false);
    }
  }

  Map<String, dynamic>? get _latest => _history.isNotEmpty ? _history.first : null;

  int get _todaySteps {
    final now = DateTime.now();
    for (final entry in _history) {
      final ts = DateTime.tryParse(entry['timestamp'] as String? ?? '');
      if (ts != null && ts.year == now.year && ts.month == now.month && ts.day == now.day) {
        final steps = entry['steps'];
        if (steps is int) return steps;
      }
    }
    return 0;
  }

  void _simulateBLEConnection(LocaleService locale) {
    setState(() {
      _isStreaming = true;
      _heartRateController.text = (60 + Random().nextInt(40)).toString();
      _spO2Controller.text = (95 + Random().nextInt(5)).toString();
      _stepsController.text = (2000 + Random().nextInt(6000)).toString();
      _deepSleepController.text = (1.5 + Random().nextDouble() * 2).toStringAsFixed(1);
      _lightSleepController.text = (2.5 + Random().nextDouble() * 3).toStringAsFixed(1);
    });

    // Honest labelling: real wearable integration is deliberately on hold
    // per the planning discussion ("IoT டிவைஸ் ஃபியூச்சர்ல பார்த்துக்கலாம்").
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(locale.t('demo_values_filled')),
        backgroundColor: const Color(0xFF3B82F6),
      ),
    );
  }

  Future<void> _submitVitals(LocaleService locale) async {
    final hr = int.tryParse(_heartRateController.text);
    final spo2 = int.tryParse(_spO2Controller.text);
    if (hr == null || hr <= 0 || hr >= 300 || spo2 == null || spo2 < 0 || spo2 > 100) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(locale.t('invalid_vitals_range')),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    setState(() => _saving = true);
    final active = context.read<ProfileService>().active;
    try {
      await ApiService().client.post('/ehr/vitals', data: {
        'device_id': 'manual-entry',
        'family_profile_id': active?.id,
        'heart_rate': hr,
        'spo2': spo2,
        'temperature': 36.8, // manual UI captures HR/SpO2 primarily
        'steps': int.tryParse(_stepsController.text),
        'sleep_deep_hours': double.tryParse(_deepSleepController.text),
        'sleep_light_hours': double.tryParse(_lightSleepController.text),
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(locale.t('vitals_saved')),
            backgroundColor: const Color(0xFF10B981),
          ),
        );
        _heartRateController.clear();
        _spO2Controller.clear();
        _stepsController.clear();
        _deepSleepController.clear();
        _lightSleepController.clear();
        await _loadHistory();
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(locale.t('vitals_save_failed')),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _neuBox({required Widget child}) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    return Container(
      decoration: BoxDecoration(
        color: neu.background,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
          BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
        ],
      ),
      child: child,
    );
  }

  Widget _metricCard(String label, String value, IconData icon, Color color) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    return Expanded(
      child: _neuBox(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color, size: 22),
              const SizedBox(height: 8),
              Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: neu.foreground)),
              Text(label, style: TextStyle(fontSize: 11, color: neu.foregroundMuted)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _trendBars(String label, String field, Color color, {double max = 150}) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    final points = _history.take(7).toList().reversed.toList();
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontWeight: FontWeight.bold, color: neu.foreground, fontSize: 14)),
          const SizedBox(height: 10),
          SizedBox(
            height: 70,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: points.isEmpty
                  ? [Expanded(child: Center(child: Text(context.read<LocaleService>().t('no_data_yet'), style: TextStyle(color: neu.foregroundMuted, fontSize: 12))))]
                  : points.map((e) {
                      final raw = e[field];
                      final v = (raw is num) ? raw.toDouble() : 0.0;
                      final heightFraction = (v / max).clamp(0.05, 1.0);
                      return Expanded(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 3),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              Container(
                                height: 50 * heightFraction,
                                decoration: BoxDecoration(
                                  color: color,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final steps = _todaySteps;
    final goalFraction = (steps / _stepGoal).clamp(0.0, 1.0);
    final latest = _latest;
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
          locale.t('health_vitals_title'),
          style: TextStyle(color: neu.foreground, fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadHistory,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Colorful summary meters (planning doc: "attractive graphs
                // and colorful meters, presenting all vitals in one place").
                if (_loadingHistory)
                  const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                else ...[
                  Row(
                    children: [
                      _metricCard(locale.t('heart_rate'), latest?['heart_rate'] != null ? '${latest!['heart_rate']} bpm' : '—', Icons.favorite, Colors.red),
                      const SizedBox(width: 12),
                      _metricCard(locale.t('spo2'), latest?['spo2'] != null ? '${latest!['spo2']}%' : '—', Icons.air, Colors.blue),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _metricCard(locale.t('sleep_deep'), latest?['sleep_deep_hours'] != null ? '${latest!['sleep_deep_hours']}h' : '—', Icons.bedtime, Colors.indigo),
                      const SizedBox(width: 12),
                      _metricCard(locale.t('sleep_light'), latest?['sleep_light_hours'] != null ? '${latest!['sleep_light_hours']}h' : '—', Icons.nights_stay, Colors.purple),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // Personal step goal (planning doc: "personal health goals
                  // e.g. daily step targets").
                  _neuBox(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 64,
                            height: 64,
                            child: Stack(
                              alignment: Alignment.center,
                              children: [
                                CircularProgressIndicator(
                                  value: goalFraction,
                                  strokeWidth: 6,
                                  backgroundColor: neu.shadowDark.withValues(alpha: 0.3),
                                  color: const Color(0xFF10B981),
                                ),
                                Icon(Icons.directions_walk, color: Colors.green.shade700),
                              ],
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('$steps / $_stepGoal ${locale.t('steps_today')}',
                                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: neu.foreground)),
                                Text(locale.t('daily_step_goal'), style: TextStyle(fontSize: 12, color: neu.foregroundMuted)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Trend graphs — last 7 logged readings.
                  _trendBars(locale.t('heart_rate_trend'), 'heart_rate', Colors.red, max: 150),
                  _trendBars(locale.t('spo2_trend'), 'spo2', Colors.blue, max: 100),
                ],

                const Divider(height: 32),
                Text(
                  locale.t('sync_or_log_manually'),
                  style: TextStyle(fontSize: 16, color: neu.foregroundMuted),
                ),
                const SizedBox(height: 16),

                GestureDetector(
                  onTap: () => _simulateBLEConnection(locale),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    decoration: BoxDecoration(
                      color: const Color(0xFF3B82F6),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                      ],
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.bluetooth, color: Colors.white),
                        const SizedBox(width: 8),
                        Text(
                          _isStreaming ? locale.t('streaming_live') : locale.t('connect_smartwatch'),
                          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 32),

                _labeledField(locale.t('heart_rate_bpm'), _heartRateController, Icons.favorite, Colors.red),
                const SizedBox(height: 16),
                _labeledField(locale.t('spo2_percent'), _spO2Controller, Icons.air, Colors.blue),
                const SizedBox(height: 16),
                _labeledField(locale.t('steps_today_label'), _stepsController, Icons.directions_walk, Colors.green),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(child: _labeledField(locale.t('deep_sleep_hrs'), _deepSleepController, Icons.bedtime, Colors.indigo)),
                    const SizedBox(width: 12),
                    Expanded(child: _labeledField(locale.t('light_sleep_hrs'), _lightSleepController, Icons.nights_stay, Colors.purple)),
                  ],
                ),

                const SizedBox(height: 32),

                GestureDetector(
                  onTap: _saving ? null : () => _submitVitals(locale),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                      ],
                    ),
                    child: Center(
                      child: _saving
                          ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                          : Text(locale.t('save_vitals'), style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _labeledField(String label, TextEditingController controller, IconData icon, Color color) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(fontWeight: FontWeight.bold, color: neu.foreground, fontSize: 13)),
        const SizedBox(height: 8),
        _neuBox(
          child: TextField(
            controller: controller,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              border: InputBorder.none,
              contentPadding: const EdgeInsets.all(16),
              suffixIcon: Icon(icon, color: color),
            ),
          ),
        ),
      ],
    );
  }
}
