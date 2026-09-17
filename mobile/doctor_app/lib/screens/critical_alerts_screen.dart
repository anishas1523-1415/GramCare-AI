import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/sos_alert.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';

/// Read-only feed of active SOS emergencies (GET /sos/active), for doctors
/// to "review critical updates on the move" per the planning doc. The
/// primary responder surface is the web Hospital Emergency Desk; this
/// screen just needs to surface the same active list and auto-refresh.
class CriticalAlertsScreen extends StatefulWidget {
  const CriticalAlertsScreen({super.key});

  @override
  State<CriticalAlertsScreen> createState() => _CriticalAlertsScreenState();
}

class _CriticalAlertsScreenState extends State<CriticalAlertsScreen> {
  List<SosAlert> _alerts = [];
  // One player for the screen: starting a second recording must stop the
  // first, not talk over it.
  final AudioPlayer _player = AudioPlayer();
  int? _playingAlertId;
  bool _loading = true;
  String? _error;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadAlerts();
    // Periodic refresh — SOS alerts are time-critical; a doctor glancing at
    // this screen should see new alerts without manually pulling to refresh.
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) => _loadAlerts(silent: true));
  }

  Future<void> _toggleVoice(SosAlert alert) async {
    if (_playingAlertId == alert.id) {
      await _player.stop();
      if (mounted) setState(() => _playingAlertId = null);
      return;
    }
    await _player.stop();
    try {
      await _player.play(UrlSource(alert.voiceAudioUrl!));
      if (!mounted) return;
      setState(() => _playingAlertId = alert.id);
      _player.onPlayerComplete.first.then((_) {
        if (mounted) setState(() => _playingAlertId = null);
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _playingAlertId = null);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(context.read<LocaleService>().t('sos_voice_play_failed')),
      ));
    }
  }

  /// Hands the patient's coordinates to whatever navigation app the phone
  /// has. geo: is the intent every Android map app registers; the https URL
  /// covers a phone with none.
  Future<void> _navigateTo(double lat, double lng) async {
    final geo = Uri.parse('geo:$lat,$lng?q=$lat,$lng');
    if (await canLaunchUrl(geo)) {
      await launchUrl(geo);
      return;
    }
    await launchUrl(
      Uri.parse('https://www.openstreetmap.org/?mlat=$lat&mlon=$lng#map=17/$lat/$lng'),
      mode: LaunchMode.externalApplication,
    );
  }

  @override
  void dispose() {
    _player.dispose();
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadAlerts({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final res = await ApiService().client.get('/sos/active');
      final list = (res.data as List).map((j) => SosAlert.fromJson(j as Map<String, dynamic>)).toList();
      if (!mounted) return;
      setState(() {
        _alerts = list;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        if (!silent) _error = context.read<LocaleService>().t('error_generic');
      });
    }
  }

  /// All located active alerts on one OpenStreetMap. No API key, no billing
  /// account — the Google key this project had was empty in every build and
  /// billing-disabled in production, so it drew nothing at all.
  Widget _buildAlertMap(LocaleService locale, List<SosAlert> located) {
    final points = located
        .map((a) => LatLng(a.locationLat!, a.locationLng!))
        .toList();

    return Container(
      height: 220,
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.criticalRed.withValues(alpha: 0.35)),
      ),
      child: FlutterMap(
        options: MapOptions(
          initialCenter: points.first,
          initialZoom: points.length == 1 ? 15 : 11,
          minZoom: 3,
          maxZoom: 19,
          initialCameraFit: points.length > 1
              ? CameraFit.coordinates(
                  coordinates: points,
                  padding: const EdgeInsets.all(40),
                  maxZoom: 16,
                )
              : null,
        ),
        children: [
          TileLayer(
            urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            userAgentPackageName: 'com.gramcare.doctor_mobile_app',
            maxNativeZoom: 19,
          ),
          MarkerLayer(
            markers: [
              for (final a in located)
                Marker(
                  point: LatLng(a.locationLat!, a.locationLng!),
                  width: 40,
                  height: 40,
                  alignment: Alignment.topCenter,
                  child: GestureDetector(
                    onTap: () => _navigateTo(a.locationLat!, a.locationLng!),
                    child: Icon(
                      Icons.person_pin_circle,
                      size: 36,
                      color: _severityColor(a.severity),
                    ),
                  ),
                ),
            ],
          ),
          const RichAttributionWidget(
            attributions: [TextSourceAttribution('OpenStreetMap contributors')],
          ),
        ],
      ),
    );
  }

  Color _severityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return AppTheme.criticalRed;
      case 'HIGH':
        return AppTheme.pendingAmber;
      default:
        return AppTheme.confirmedBlue;
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();

    return Scaffold(
      appBar: AppBar(title: Text(locale.t('critical_alerts'))),
      body: RefreshIndicator(
        onRefresh: () => _loadAlerts(),
        child: _buildBody(locale),
      ),
    );
  }

  Widget _buildBody(LocaleService locale) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return ListView(
        children: [
          const SizedBox(height: 100),
          Center(child: Text(_error!)),
          const SizedBox(height: 12),
          Center(child: OutlinedButton(onPressed: () => _loadAlerts(), child: Text(locale.t('retry')))),
        ],
      );
    }
    if (_alerts.isEmpty) {
      return ListView(
        children: [
          const SizedBox(height: 100),
          Icon(Icons.check_circle_outline, size: 56, color: Colors.grey.shade400),
          const SizedBox(height: 16),
          Center(child: Text(locale.t('no_active_alerts'), style: const TextStyle(color: Colors.black54))),
        ],
      );
    }

    final dateFmt = DateFormat('MMM d, hh:mm a');
    // Every alert that actually carries coordinates. A doctor triaging
    // several emergencies at once needs to see how they sit relative to
    // each other and to themselves, which a list of addresses cannot show.
    final located = _alerts
        .where((a) => a.locationLat != null && a.locationLng != null)
        .toList();

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _alerts.length + (located.isEmpty ? 0 : 1),
      itemBuilder: (context, rawIndex) {
        if (located.isNotEmpty && rawIndex == 0) {
          return _buildAlertMap(locale, located);
        }
        final index = located.isEmpty ? rawIndex : rawIndex - 1;
        final alert = _alerts[index];
        final color = _severityColor(alert.severity);
        return Card(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: BorderSide(color: color.withValues(alpha: 0.4)),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: color),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${locale.t('sos_severity')}: ${alert.severity}',
                        style: TextStyle(fontWeight: FontWeight.bold, color: color),
                      ),
                    ),
                    Text(dateFmt.format(alert.createdAt.toLocal()), style: const TextStyle(fontSize: 12, color: Colors.black54)),
                  ],
                ),
                const SizedBox(height: 8),
                Text('Patient ID: ${alert.patientId}'),
                if (alert.locationText != null && alert.locationText!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.location_on_outlined, size: 16, color: Colors.black54),
                      const SizedBox(width: 4),
                      Expanded(child: Text(alert.locationText!, style: const TextStyle(fontSize: 13))),
                    ],
                  ),
                ],
                if (alert.voiceNote != null && alert.voiceNote!.trim().isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.04),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.record_voice_over, size: 16, color: Colors.black54),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            alert.voiceNote!,
                            style: const TextStyle(fontSize: 13, fontStyle: FontStyle.italic),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 4),
                Text('${locale.t('sos_status')}: ${alert.status}', style: const TextStyle(fontSize: 13)),
                if (alert.voiceAudioUrl != null && alert.voiceAudioUrl!.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () => _toggleVoice(alert),
                      icon: Icon(
                        _playingAlertId == alert.id ? Icons.stop_circle : Icons.play_circle,
                        size: 20,
                      ),
                      label: Text(locale.t(
                        _playingAlertId == alert.id ? 'sos_voice_stop' : 'sos_voice_play',
                      )),
                    ),
                  ),
                ],
                if (alert.locationLat != null && alert.locationLng != null) ...[
                  const SizedBox(height: 10),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: () => _navigateTo(alert.locationLat!, alert.locationLng!),
                      icon: const Icon(Icons.directions, size: 18),
                      style: FilledButton.styleFrom(backgroundColor: color),
                      label: Text(locale.t('navigate_to_patient')),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}
