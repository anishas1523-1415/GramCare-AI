import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/ble_vitals_service.dart';
import '../services/profile_service.dart';
import '../theme/neumorphic_colors.dart';

/// Health Vitals Tracker (planning doc): "Steps Tracker, Sleep Analysis
/// (deep sleep vs light sleep breakdown), Heart Rate & Oxygen level
/// monitoring ... presented as graphs ... colorful meters, personal health
/// goals."
///
/// Readings come from a standard Bluetooth health device (heart-rate strap,
/// pulse oximeter, thermometer) streamed live, or are typed in from any
/// device the family already owns. Only what was actually measured is saved,
/// tagged with where it came from; nothing is filled in on the patient's
/// behalf.
class VitalsScreen extends StatefulWidget {
  const VitalsScreen({super.key});

  @override
  State<VitalsScreen> createState() => _VitalsScreenState();
}

class _VitalsScreenState extends State<VitalsScreen> {
  final _heartRateController = TextEditingController();
  final _spO2Controller = TextEditingController();
  final _temperatureController = TextEditingController();
  final _stepsController = TextEditingController();
  final _deepSleepController = TextEditingController();
  final _lightSleepController = TextEditingController();

  static const int _stepGoal = 6000;

  // Same bounds the API enforces (VitalsPayload in modules/ehr_sync/router.py).
  static const _bounds = <String, (num, num)>{
    'heart_rate': (1, 299),
    'spo2': (0, 100),
    'temperature': (25.1, 44.9),
    'steps': (0, 200000),
    'sleep_deep_hours': (0, 24),
    'sleep_light_hours': (0, 24),
  };
  static const _integerFields = {'heart_rate', 'spo2', 'steps'};

  final _ble = BleVitalsService();
  StreamSubscription<BleVitalsReading>? _readingSub;
  StreamSubscription<BluetoothConnectionState>? _connectionSub;
  String? _connectedName;
  String? _readingSourceName;
  bool _connecting = false;
  bool _hasLiveReading = false;

  bool _saving = false;
  bool _loadingHistory = true;
  List<Map<String, dynamic>> _history = [];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  @override
  void dispose() {
    _readingSub?.cancel();
    _connectionSub?.cancel();
    unawaited(_ble.dispose());
    for (final c in [
      _heartRateController,
      _spO2Controller,
      _temperatureController,
      _stepsController,
      _deepSleepController,
      _lightSleepController,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _loadHistory() async {
    setState(() => _loadingHistory = true);
    final active = context.read<ProfileService>().active;
    try {
      final res = await ApiService().client.get('/ehr/vitals/history', queryParameters: {
        if (active?.id != null) 'family_profile_id': active!.id,
        'days': 14,
      });
      if (mounted) setState(() => _history = List<Map<String, dynamic>>.from(res.data as List));
    } catch (_) {
      // Offline or first visit: the dashboard shows its empty state.
    } finally {
      if (mounted) setState(() => _loadingHistory = false);
    }
  }

  /// Newest recorded value for [field]. Each reading carries only what was
  /// measured, so the newest row may not include this field at all.
  Object? _latestOf(String field) {
    for (final entry in _history) {
      final v = entry[field];
      if (v != null) return v;
    }
    return null;
  }

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

  void _snack(String message, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message), backgroundColor: color));
  }

  Future<void> _connectDevice(LocaleService locale) async {
    final readiness = await _ble.prepare();
    if (!mounted) return;
    if (readiness != BleReadiness.ready) {
      _snack(
        locale.t(readiness == BleReadiness.unsupported ? 'ble_not_supported' : 'ble_turn_on'),
        Colors.orange,
      );
      return;
    }

    final device = await showModalBottomSheet<BluetoothDevice>(
      context: context,
      showDragHandle: true,
      builder: (_) => _DevicePickerSheet(ble: _ble, locale: locale),
    );
    if (device == null || !mounted) return;

    setState(() => _connecting = true);
    try {
      final ok = await _ble.connect(device);
      if (!mounted) return;
      if (!ok) {
        _snack(locale.t('ble_no_health_data'), Colors.orange);
        return;
      }
      setState(() {
        _connectedName = BleVitalsService.nameOf(device) ?? locale.t('ble_unnamed_device');
        _hasLiveReading = false;
      });
      _readingSub = _ble.readings.listen(_applyReading);
      _connectionSub = _ble.connectionState.listen((state) {
        if (state == BluetoothConnectionState.disconnected && _connectedName != null) {
          _onDeviceLost(locale);
        }
      });
    } catch (_) {
      if (mounted) _snack(locale.t('ble_connect_failed'), Colors.red);
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  void _applyReading(BleVitalsReading r) {
    if (!mounted) return;
    setState(() {
      _hasLiveReading = true;
      _readingSourceName = _connectedName;
      if (r.heartRate != null) _heartRateController.text = '${r.heartRate}';
      if (r.spo2 != null) _spO2Controller.text = '${r.spo2}';
      if (r.temperatureC != null) _temperatureController.text = r.temperatureC!.toStringAsFixed(1);
    });
  }

  Future<void> _stopListening() async {
    await _readingSub?.cancel();
    _readingSub = null;
    await _connectionSub?.cancel();
    _connectionSub = null;
  }

  Future<void> _disconnectDevice() async {
    // Cleared first so the disconnect event below isn't reported as a loss.
    setState(() {
      _connectedName = null;
      _hasLiveReading = false;
    });
    await _stopListening();
    await _ble.disconnect();
  }

  Future<void> _onDeviceLost(LocaleService locale) async {
    await _stopListening();
    await _ble.disconnect();
    if (!mounted) return;
    setState(() {
      _connectedName = null;
      _hasLiveReading = false;
    });
    _snack(locale.t('ble_disconnected'), Colors.orange);
  }

  Future<void> _submitVitals(LocaleService locale) async {
    final fields = <String, TextEditingController>{
      'heart_rate': _heartRateController,
      'spo2': _spO2Controller,
      'temperature': _temperatureController,
      'steps': _stepsController,
      'sleep_deep_hours': _deepSleepController,
      'sleep_light_hours': _lightSleepController,
    };
    final values = <String, num>{};
    for (final entry in fields.entries) {
      final text = entry.value.text.trim();
      if (text.isEmpty) continue;
      final num? value = _integerFields.contains(entry.key) ? int.tryParse(text) : double.tryParse(text);
      final (low, high) = _bounds[entry.key]!;
      if (value == null || value < low || value > high) {
        _snack(locale.t('invalid_vitals_range'), Colors.red);
        return;
      }
      values[entry.key] = value;
    }
    if (values.isEmpty) {
      _snack(locale.t('vitals_need_one_value'), Colors.red);
      return;
    }

    setState(() => _saving = true);
    final active = context.read<ProfileService>().active;
    final source = _readingSourceName;
    try {
      await ApiService().client.post('/ehr/vitals', data: {
        'device_id': source != null ? 'ble:${source.length > 100 ? source.substring(0, 100) : source}' : 'manual-entry',
        'family_profile_id': active?.id,
        ...values,
      });
      if (!mounted) return;
      _snack(locale.t('vitals_saved'), const Color(0xFF10B981));
      for (final c in fields.values) {
        c.clear();
      }
      _readingSourceName = null;
      await _loadHistory();
    } catch (_) {
      if (mounted) _snack(locale.t('vitals_save_failed'), Colors.red);
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
    // Only readings that actually include this measurement.
    final points = _history.where((e) => e[field] is num).take(7).toList().reversed.toList();
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
                  ? [
                      Expanded(
                        child: Center(
                          child: Text(context.read<LocaleService>().t('no_data_yet'),
                              style: TextStyle(color: neu.foregroundMuted, fontSize: 12)),
                        ),
                      ),
                    ]
                  : points.map((e) {
                      final v = (e[field] as num).toDouble();
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

  Widget _buildDeviceCard(LocaleService locale, NeumorphicColors neu) {
    final name = _connectedName;
    if (name != null) {
      return _neuBox(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              const Icon(Icons.bluetooth_connected, color: Color(0xFF3B82F6)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${locale.t('ble_live_from')} $name',
                        style: TextStyle(fontWeight: FontWeight.bold, color: neu.foreground)),
                    if (!_hasLiveReading)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(locale.t('ble_waiting_reading'),
                            style: TextStyle(fontSize: 12, color: neu.foregroundMuted)),
                      ),
                  ],
                ),
              ),
              TextButton(onPressed: _disconnectDevice, child: Text(locale.t('ble_disconnect'))),
            ],
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GestureDetector(
          onTap: _connecting ? null : () => _connectDevice(locale),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 16),
            decoration: BoxDecoration(
              color: const Color(0xFF3B82F6),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8)],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (_connecting)
                  const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                  )
                else
                  const Icon(Icons.bluetooth, color: Colors.white),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(
                    _connecting ? locale.t('ble_connecting') : locale.t('connect_ble_device'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(locale.t('ble_profiles_note'), style: TextStyle(fontSize: 12, color: neu.foregroundMuted)),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final steps = _todaySteps;
    final goalFraction = (steps / _stepGoal).clamp(0.0, 1.0);
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    final locale = context.watch<LocaleService>();

    final hr = _latestOf('heart_rate');
    final spo2 = _latestOf('spo2');
    final temperature = _latestOf('temperature');
    final deepSleep = _latestOf('sleep_deep_hours');
    final lightSleep = _latestOf('sleep_light_hours');

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
                if (_loadingHistory)
                  const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                else ...[
                  Row(
                    children: [
                      _metricCard(locale.t('heart_rate'), hr != null ? '$hr bpm' : '—', Icons.favorite, Colors.red),
                      const SizedBox(width: 12),
                      _metricCard(locale.t('spo2'), spo2 != null ? '$spo2%' : '—', Icons.air, Colors.blue),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _metricCard(
                        locale.t('temperature'),
                        temperature is num ? '${temperature.toStringAsFixed(1)} °C' : '—',
                        Icons.thermostat,
                        Colors.orange,
                      ),
                      const SizedBox(width: 12),
                      _metricCard(
                        locale.t('sleep_deep_light'),
                        (deepSleep != null || lightSleep != null)
                            ? '${deepSleep ?? '—'}h / ${lightSleep ?? '—'}h'
                            : '—',
                        Icons.bedtime,
                        Colors.indigo,
                      ),
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
                                Text(locale.t('daily_step_goal'),
                                    style: TextStyle(fontSize: 12, color: neu.foregroundMuted)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  _trendBars(locale.t('heart_rate_trend'), 'heart_rate', Colors.red, max: 150),
                  _trendBars(locale.t('spo2_trend'), 'spo2', Colors.blue, max: 100),
                ],

                const Divider(height: 32),
                Text(
                  locale.t('sync_or_log_manually'),
                  style: TextStyle(fontSize: 16, color: neu.foregroundMuted),
                ),
                const SizedBox(height: 16),

                _buildDeviceCard(locale, neu),

                const SizedBox(height: 32),

                _labeledField(locale.t('heart_rate_bpm'), _heartRateController, Icons.favorite, Colors.red),
                const SizedBox(height: 16),
                _labeledField(locale.t('spo2_percent'), _spO2Controller, Icons.air, Colors.blue),
                const SizedBox(height: 16),
                _labeledField(locale.t('temperature_c'), _temperatureController, Icons.thermostat, Colors.orange),
                const SizedBox(height: 16),
                _labeledField(locale.t('steps_today_label'), _stepsController, Icons.directions_walk, Colors.green),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                        child: _labeledField(
                            locale.t('deep_sleep_hrs'), _deepSleepController, Icons.bedtime, Colors.indigo)),
                    const SizedBox(width: 12),
                    Expanded(
                        child: _labeledField(
                            locale.t('light_sleep_hrs'), _lightSleepController, Icons.nights_stay, Colors.purple)),
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
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                            )
                          : Text(locale.t('save_vitals'),
                              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
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

/// Lists nearby devices advertising a standard health profile, strongest
/// signal first, and returns the one the user taps.
class _DevicePickerSheet extends StatefulWidget {
  final BleVitalsService ble;
  final LocaleService locale;

  const _DevicePickerSheet({required this.ble, required this.locale});

  @override
  State<_DevicePickerSheet> createState() => _DevicePickerSheetState();
}

class _DevicePickerSheetState extends State<_DevicePickerSheet> {
  List<ScanResult> _results = const [];
  bool _scanning = true;
  bool _failed = false;
  StreamSubscription<List<ScanResult>>? _resultsSub;
  StreamSubscription<bool>? _scanningSub;

  @override
  void initState() {
    super.initState();
    _scan();
  }

  @override
  void dispose() {
    _resultsSub?.cancel();
    _scanningSub?.cancel();
    unawaited(widget.ble.stopScan().catchError((_) {}));
    super.dispose();
  }

  Future<void> _scan() async {
    if (mounted) {
      setState(() {
        _results = const [];
        _scanning = true;
        _failed = false;
      });
    }
    await _resultsSub?.cancel();
    await _scanningSub?.cancel();
    try {
      await widget.ble.startScan();
    } catch (_) {
      if (mounted) {
        setState(() {
          _scanning = false;
          _failed = true;
        });
      }
      return;
    }
    // Subscribed after the scan has started, so the stream's initial
    // "not scanning" value can't flash "no devices found" first.
    _resultsSub = widget.ble.scanResults.listen((results) {
      if (mounted) setState(() => _results = results);
    });
    _scanningSub = widget.ble.isScanning.listen((scanning) {
      if (mounted) setState(() => _scanning = scanning);
    });
  }

  List<IconData> _profileIcons(ScanResult r) {
    final uuids = r.advertisementData.serviceUuids;
    return [
      if (uuids.contains(BleVitalsService.heartRateService)) Icons.favorite,
      if (uuids.contains(BleVitalsService.pulseOximeterService)) Icons.air,
      if (uuids.contains(BleVitalsService.thermometerService)) Icons.thermostat,
    ];
  }

  @override
  Widget build(BuildContext context) {
    final t = widget.locale.t;
    final sorted = [..._results]..sort((a, b) => b.rssi.compareTo(a.rssi));
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(t('ble_choose_device'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(t('ble_profiles_note'), style: const TextStyle(fontSize: 12, color: Colors.black54)),
            const SizedBox(height: 12),
            if (_scanning)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                    const SizedBox(width: 12),
                    Expanded(child: Text(t('ble_searching'))),
                  ],
                ),
              )
            else if (sorted.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(_failed ? t('ble_scan_failed') : t('ble_none_found')),
              ),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                children: [
                  for (final r in sorted)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.bluetooth, color: Color(0xFF3B82F6)),
                      title: Text(BleVitalsService.nameOf(r.device) ?? t('ble_unnamed_device')),
                      subtitle: Row(
                        children: [
                          for (final icon in _profileIcons(r))
                            Padding(padding: const EdgeInsets.only(right: 6), child: Icon(icon, size: 16)),
                        ],
                      ),
                      trailing: Text('${r.rssi} dBm', style: const TextStyle(fontSize: 12, color: Colors.black54)),
                      onTap: () => Navigator.of(context).pop(r.device),
                    ),
                ],
              ),
            ),
            if (!_scanning)
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: _scan,
                  icon: const Icon(Icons.refresh),
                  label: Text(t('ble_search_again')),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
