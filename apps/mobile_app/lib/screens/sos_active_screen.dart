import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';
import '../services/app_strings.dart';
import '../services/api_service.dart';

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
  final Set<Polyline> _polylines = {};
  String _statusMessage = "Locating nearest hospital...";

  @override
  void initState() {
    super.initState();
    _markers.add(Marker(
      markerId: const MarkerId('patient'),
      position: LatLng(widget.patientLat, widget.patientLng),
      infoWindow: const InfoWindow(title: 'You are here'),
      icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
    ));
    _fetchHospitalRoute();
  }

  Future<void> _fetchHospitalRoute() async {
    try {
      await ApiService().client.get('/sos/active');
      if (mounted) {
        setState(() {
          _statusMessage = "Help is on the way.";
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _statusMessage = "Error fetching route.";
        });
      }
    }
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
            color: Colors.red.shade100,
            width: double.infinity,
            child: Text(
              _statusMessage,
              style: const TextStyle(
                color: Colors.red,
                fontWeight: FontWeight.bold,
                fontSize: 18,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          Expanded(
            child: GoogleMap(
              initialCameraPosition: CameraPosition(
                target: LatLng(widget.patientLat, widget.patientLng),
                zoom: 14,
              ),
              markers: _markers,
              polylines: _polylines,
              myLocationEnabled: true,
            ),
          ),
        ],
      ),
    );
  }
}
