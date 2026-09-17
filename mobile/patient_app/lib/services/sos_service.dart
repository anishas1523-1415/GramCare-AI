import 'package:dio/dio.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter/services.dart';
import 'package:geocoding/geocoding.dart';

import 'api_service.dart';

/// Emergency SOS pipeline (planning doc, Emergency SOS module):
/// 1. capture real GPS (best-effort, never blocks the alert),
/// 2. POST /sos/trigger with location + optional voice note + member,
/// 3. if the network path fails, fall back to an SMS intent that alerts the
///    user's stored emergency contacts ("இன்டர்நெட் இல்லைன்னா SMS மூலமாகவும்
///    வேலை செய்யும்").
class SosResult {
  final bool sent;            // true = server accepted the alert
  final bool smsFallbackUsed; // true = offline path opened the SMS composer
  final String? error;
  final Position? position;
  /// Server id of the accepted alert, so the SOS screen can attach the
  /// patient's voice recording to it afterwards. Null when nothing reached
  /// the server.
  final int? sosId;
  const SosResult({required this.sent, this.smsFallbackUsed = false, this.error,
      this.position, this.sosId});
}

class SosService {
  static const _smsChannel = MethodChannel('com.gramcare.mobile_app/sms');

  static final SosService _instance = SosService._internal();
  factory SosService() => _instance;
  SosService._internal();

  Future<Position?> _bestEffortPosition() async {
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return null;
      }
      // Emergency context: last-known first (instant), fresh fix with a
      // hard timeout second. Never let GPS delay a life-safety alert.
      final last = await Geolocator.getLastKnownPosition();
      try {
        return await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.high,
            timeLimit: Duration(seconds: 5),
          ),
        );
      } catch (_) {
        return last;
      }
    } catch (_) {
      return null;
    }
  }

  Future<SosResult> trigger({
    int? familyProfileId,
    String? voiceNote,
  }) async {
    final position = await _bestEffortPosition();
    String? locText;
    
    if (position != null) {
      try {
        List<Placemark> placemarks = await placemarkFromCoordinates(position.latitude, position.longitude);
        if (placemarks.isNotEmpty) {
          final p = placemarks.first;
          locText = [p.street, p.subLocality, p.locality, p.postalCode].where((e) => e != null && e.isNotEmpty).join(', ');
        }
      } catch (e) {
        locText = 'GPS available, address lookup failed';
      }
    } else {
      locText = 'GPS unavailable';
    }

    try {
      final res = await ApiService().client.post('/sos/trigger', data: {
        'location_lat': position?.latitude,
        'location_lng': position?.longitude,
        'location_text': locText,
        'voice_note': voiceNote,
        'severity': 'CRITICAL',
        'family_profile_id': familyProfileId,
      });
      // The server pages the hospital and SMSes the contacts, but both of
      // those depend on push and SMS credentials that may not be live.
      // Opening the composer here is the one channel that needs nothing
      // configured, so family are told even when everything else is down.
      final smsOpened = await _alertContacts(position);
      return SosResult(
        sent: true,
        smsFallbackUsed: smsOpened,
        position: position,
        sosId: (res.data is Map) ? res.data['id'] as int? : null,
      );
    } on DioException catch (e) {
      final offline = e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout;
      if (offline) {
        final smsOpened = await _alertContacts(position);
        return SosResult(sent: false, smsFallbackUsed: smsOpened,
            error: smsOpened ? null : 'Offline and SMS unavailable', position: position);
      }
      return SosResult(sent: false, error: e.response?.data?.toString() ?? e.message, position: position);
    } catch (e) {
      return SosResult(sent: false, error: e.toString(), position: position);
    }
  }

  /// Opens the SMS composer pre-addressed to the locally cached emergency
  /// contacts with a location link. Used both when the SOS reached the
  /// server and when it did not: a delivered SOS still only sits in a
  /// hospital queue, and family are usually far closer than an ambulance.
  /// (True background SMS needs carrier-level integration — an explicit
  /// user send keeps this reliable and store-policy-safe.)
  /// Opens the SMS composer pre-addressed to the locally cached emergency
  /// contacts with a location link. Used both when the SOS reached the
  /// server and when it did not: a delivered SOS still only sits in a
  /// hospital queue, and family are usually far closer than an ambulance.
  ///
  /// Routed through a platform channel rather than url_launcher because
  /// WhatsApp registers an ACTION_SENDTO filter for the smsto scheme, so
  /// letting Android choose could hand the emergency to WhatsApp — which
  /// then read the joined recipient list as one number and reported it was
  /// not on WhatsApp. The message simply never left. MainActivity names the
  /// default SMS package instead.
  Future<bool> _alertContacts(Position? position) async {
    final numbers = await cachedContactNumbers();
    if (numbers.isEmpty) return false;
    final loc = position != null
        ? 'https://maps.google.com/?q=${position.latitude},${position.longitude}'
        : 'location unknown';
    final body = 'EMERGENCY! I need help. My location: $loc — sent from GramCare AI';
    try {
      final opened = await _smsChannel.invokeMethod<bool>('openSmsComposer', {
        'recipients': numbers,
        'body': body,
      });
      return opened ?? false;
    } catch (_) {
      return false;
    }
  }

  /// Attaches the patient's recording to an alert already in flight.
  /// Returns false rather than throwing: losing the recording must never
  /// look like losing the emergency.
  Future<bool> uploadVoiceRecording(int sosId, String base64Audio) async {
    try {
      await ApiService().client.post(
        '/sos/$sosId/voice',
        data: {'voice_audio_base64': base64Audio},
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  // -------- contacts (server-backed, cached for offline SOS) --------------
  static List<String> _contactCache = [];

  Future<List<Map<String, dynamic>>> fetchContacts() async {
    final res = await ApiService().client.get('/sos/contacts');
    final contacts = List<Map<String, dynamic>>.from(res.data as List);
    _contactCache = contacts.map((c) => c['phone'] as String).toList();
    return contacts;
  }

  Future<List<String>> cachedContactNumbers() async {
    if (_contactCache.isNotEmpty) return _contactCache;
    try {
      await fetchContacts();
    } catch (_) {/* offline: whatever we have */}
    return _contactCache;
  }

  Future<void> addContact(String name, String phone, String relation) async {
    await ApiService().client.post('/sos/contacts', data: {
      'name': name, 'phone': phone, 'relation': relation,
    });
    await fetchContacts();
  }

  Future<void> deleteContact(int id) async {
    await ApiService().client.delete('/sos/contacts/$id');
    await fetchContacts();
  }
}
