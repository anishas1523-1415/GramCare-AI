import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/app_strings.dart';
import '../services/api_service.dart';

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

  const SosActiveScreen({
    super.key,
    required this.patientLat,
    required this.patientLng,
  });

  @override
  State<SosActiveScreen> createState() => _SosActiveScreenState();
}

class _SosActiveScreenState extends State<SosActiveScreen> {
  final Set<Marker> _markers = {};
  String? _status;
  int _escalationLevel = 0;
  bool _hasError = false;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _markers.add(Marker(
      markerId: const MarkerId('patient'),
      position: LatLng(widget.patientLat, widget.patientLng),
      infoWindow: const InfoWindow(title: 'You are here'),
      icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
    ));
    _fetchStatus();
    // The alert can transition ACTIVE -> RESPONDED (or escalate) at any
    // time on the hospital/doctor side — poll so this screen reflects that
    // without the patient needing to back out and re-enter.
    _poll = Timer.periodic(const Duration(seconds: 15), (_) => _fetchStatus());
  }

  @override
  void dispose() {
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
            child: GoogleMap(
              initialCameraPosition: CameraPosition(
                target: LatLng(widget.patientLat, widget.patientLng),
                zoom: 14,
              ),
              markers: _markers,
              myLocationEnabled: true,
            ),
          ),
        ],
      ),
    );
  }
}
