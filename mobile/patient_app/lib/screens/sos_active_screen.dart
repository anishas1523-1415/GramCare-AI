import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/app_strings.dart';
import '../services/api_service.dart';
import '../services/sos_service.dart';

/// Previously this screen called GET /sos/active — the HOSPITAL/DOCTOR-
/// facing "every active alert" endpoint, not scoped to this patient at all
/// — and used nothing from the response except whether the call succeeded,
/// showing a static "Help is on the way" message forever regardless of what
/// actually happened to the alert. GET /sos/mine is the patient-scoped
/// endpoint and actually carries status (ACTIVE/RESPONDED/RESOLVED) and
/// escalation info; this now polls it and reflects the real state.
class SosActiveScreen extends StatefulWidget {
  final double patientLat;
  final double patientLng;
  /// Null when the alert never reached the server (offline SMS path), in
  /// which case there is nothing to attach a recording to.
  final int? sosId;

  const SosActiveScreen({
    super.key,
    required this.patientLat,
    required this.patientLng,
    this.sosId,
  });

  @override
  State<SosActiveScreen> createState() => _SosActiveScreenState();
}

class _SosActiveScreenState extends State<SosActiveScreen> {
  String? _status;
  int _escalationLevel = 0;
  bool _hasError = false;
  Timer? _poll;

  // Voice recording. The alert has already gone; this lets the patient say
  // what is wrong in their own voice while help is on the way, which a
  // speech-to-text transcript cannot carry — distress, breathlessness, or
  // somebody else in the room speaking.
  final AudioRecorder _recorder = AudioRecorder();
  bool _recording = false;
  bool _uploadingVoice = false;
  bool _voiceSent = false;
  Timer? _recordTimer;
  int _recordSeconds = 0;
  static const int _maxRecordSeconds = 30;

  @override
  void initState() {
    super.initState();
    _fetchStatus();
    // The alert can transition ACTIVE -> RESPONDED (or escalate) at any
    // time on the hospital/doctor side — poll so this screen reflects that
    // without the patient needing to back out and re-enter.
    _poll = Timer.periodic(const Duration(seconds: 15), (_) => _fetchStatus());
  }

  @override
  void dispose() {
    _recordTimer?.cancel();
    _recorder.dispose();
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _fetchStatus() async {
    try {
      final res = await ApiService().client.get('/sos/mine');
      final list = res.data as List;
      if (list.isEmpty) return;
      final latest = list.first as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _status = latest['status'] as String?;
        _escalationLevel = (latest['escalation_level'] as num?)?.toInt() ?? 0;
        _hasError = false;
      });
      if (_status == 'RESOLVED') {
        _poll?.cancel();
      }
    } catch (e) {
      if (mounted) setState(() => _hasError = true);
    }
  }

  String _statusMessage(LocaleService s) {
    if (_hasError) return s.t('sos_status_error');
    switch (_status) {
      case 'RESPONDED':
        return s.t('sos_status_responded');
      case 'RESOLVED':
        return s.t('sos_status_resolved');
      case 'ACTIVE':
        return _escalationLevel > 0 ? s.t('sos_escalated') : s.t('sos_status_active');
      default:
        return s.t('sos_status_active');
    }
  }

  Color _statusColor() {
    if (_hasError) return Colors.grey;
    switch (_status) {
      case 'RESPONDED':
        return Colors.green.shade100;
      case 'RESOLVED':
        return Colors.blue.shade100;
      default:
        return Colors.red.shade100;
    }
  }

  Color _statusTextColor() {
    if (_hasError) return Colors.black54;
    switch (_status) {
      case 'RESPONDED':
        return Colors.green.shade800;
      case 'RESOLVED':
        return Colors.blue.shade800;
      default:
        return Colors.red;
    }
  }

  /// Hands the alert's coordinates to whatever map app the phone has. geo:
  /// is the Android intent every map app registers; the https URL is the
  /// fallback for a phone with none.
  Future<void> _toggleRecording() async {
    if (_recording) {
      await _stopAndUpload();
      return;
    }
    if (!await _recorder.hasPermission()) return;

    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/sos_${widget.sosId}.m4a';
    // AAC in an MP4 container: what Android records natively, small enough
    // to upload on a rural connection, and playable everywhere.
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.aacLc, bitRate: 32000, sampleRate: 22050),
      path: path,
    );
    if (!mounted) return;
    setState(() {
      _recording = true;
      _recordSeconds = 0;
    });
    _recordTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _recordSeconds++);
      // Hard cap so a phone left running in a pocket cannot produce a clip
      // too large to reach a responder over 2G.
      if (_recordSeconds >= _maxRecordSeconds) _stopAndUpload();
    });
  }

  Future<void> _stopAndUpload() async {
    _recordTimer?.cancel();
    final path = await _recorder.stop();
    if (!mounted) return;
    setState(() {
      _recording = false;
      _uploadingVoice = true;
    });

    var ok = false;
    final sosId = widget.sosId;
    if (path != null && sosId != null) {
      try {
        final bytes = await File(path).readAsBytes();
        ok = await SosService().uploadVoiceRecording(sosId, base64Encode(bytes));
      } catch (_) {
        ok = false;
      }
    }
    if (!mounted) return;
    setState(() {
      _uploadingVoice = false;
      _voiceSent = ok;
    });
    final s = context.read<LocaleService>();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(s.t(ok ? 'sos_voice_sent' : 'sos_voice_failed')),
      backgroundColor: ok ? Colors.green.shade800 : Colors.red.shade900,
    ));
  }

  Widget _buildVoiceRecorder(LocaleService s) {
    if (widget.sosId == null) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Expanded(
            child: Text(
              _voiceSent
                  ? s.t('sos_voice_sent')
                  : _recording
                      ? '${s.t('sos_voice_recording')}  $_recordSeconds/$_maxRecordSeconds s'
                      : s.t('sos_voice_prompt'),
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: _recording ? Colors.red : Colors.black87,
              ),
            ),
          ),
          const SizedBox(width: 10),
          if (_uploadingVoice)
            const SizedBox(height: 22, width: 22, child: CircularProgressIndicator(strokeWidth: 2))
          else
            FilledButton.icon(
              onPressed: _toggleRecording,
              style: FilledButton.styleFrom(
                backgroundColor: _recording ? Colors.red.shade700 : Colors.red.shade400,
              ),
              icon: Icon(_recording ? Icons.stop : Icons.mic, size: 18),
              label: Text(s.t(_recording ? 'sos_voice_stop' : 'sos_voice_record')),
            ),
        ],
      ),
    );
  }

  Future<void> _openInMaps() async {
    final lat = widget.patientLat;
    final lng = widget.patientLng;
    final geo = Uri.parse('geo:$lat,$lng?q=$lat,$lng');
    if (await canLaunchUrl(geo)) {
      await launchUrl(geo);
      return;
    }
    await launchUrl(
      Uri.parse('https://maps.google.com/?q=$lat,$lng'),
      mode: LaunchMode.externalApplication,
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<LocaleService>();

    return Scaffold(
      appBar: AppBar(
        title: Text(s.t('emergency_sos')),
        backgroundColor: Colors.red,
        foregroundColor: Colors.white,
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            color: _statusColor(),
            width: double.infinity,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (_status != 'RESOLVED' && !_hasError)
                  const Padding(
                    padding: EdgeInsets.only(right: 10),
                    child: SizedBox(
                      height: 16, width: 16,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.red),
                    ),
                  ),
                Flexible(
                  child: Text(
                    _statusMessage(s),
                    style: TextStyle(
                      color: _statusTextColor(),
                      fontWeight: FontWeight.bold,
                      fontSize: 18,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
          ),
          _buildVoiceRecorder(s),
          // The embedded map needs a billed Google Maps key, which a build
          // without MAPS_API_KEY does not have — it renders as a blank grey
          // tile. During an emergency that is worse than useless, so the
          // coordinates and a handoff to the phone's own Maps app sit above
          // the map and work whether or not the tile ever loads.
          InkWell(
            onTap: _openInMaps,
            child: Container(
              width: double.infinity,
              color: Colors.red.shade50,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  const Icon(Icons.place, size: 18, color: Colors.red),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${widget.patientLat.toStringAsFixed(5)}, ${widget.patientLng.toStringAsFixed(5)}',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontFeatures: [FontFeature.tabularFigures()],
                      ),
                    ),
                  ),
                  Text(
                    s.t('open_in_maps'),
                    style: const TextStyle(
                      color: Colors.red,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Icon(Icons.open_in_new, size: 16, color: Colors.red),
                ],
              ),
            ),
          ),
          Expanded(
            child: FlutterMap(
              options: MapOptions(
                initialCenter: LatLng(widget.patientLat, widget.patientLng),
                // Close enough to read the street the patient is on, which
                // is the whole point of showing responders a map.
                initialZoom: 16,
                minZoom: 3,
                maxZoom: 19,
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  // OSM's tile usage policy requires an identifying agent.
                  userAgentPackageName: 'com.gramcare.mobile_app',
                  maxNativeZoom: 19,
                ),
                MarkerLayer(
                  markers: [
                    Marker(
                      point: LatLng(widget.patientLat, widget.patientLng),
                      width: 46,
                      height: 46,
                      alignment: Alignment.topCenter,
                      child: const _PatientPin(),
                    ),
                  ],
                ),
                const RichAttributionWidget(
                  attributions: [
                    TextSourceAttribution('OpenStreetMap contributors'),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A pulsing pin so the patient's position is unmistakable on a small
/// screen an ambulance crew is reading in a hurry.
class _PatientPin extends StatelessWidget {
  const _PatientPin();

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        Container(
          width: 46,
          height: 46,
          decoration: BoxDecoration(
            color: Colors.red.withValues(alpha: 0.22),
            shape: BoxShape.circle,
          ),
        ),
        const Icon(Icons.person_pin_circle, color: Colors.red, size: 34),
      ],
    );
  }
}
