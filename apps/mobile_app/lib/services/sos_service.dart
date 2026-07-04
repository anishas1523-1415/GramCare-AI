import 'package:dio/dio.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';

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
  const SosResult({required this.sent, this.smsFallbackUsed = false, this.error});
}

class SosService {
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

    try {
      await ApiService().client.post('/sos/trigger', data: {
        'location_lat': position?.latitude,
        'location_lng': position?.longitude,
        'location_text': position == null ? 'GPS unavailable' : null,
        'voice_note': voiceNote,
        'severity': 'CRITICAL',
        'family_profile_id': familyProfileId,
      });
      return const SosResult(sent: true);
    } on DioException catch (e) {
      final offline = e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout;
      if (offline) {
        final smsOpened = await _smsFallback(position);
        return SosResult(sent: false, smsFallbackUsed: smsOpened,
            error: smsOpened ? null : 'Offline and SMS unavailable');
      }
      return SosResult(sent: false, error: e.response?.data?.toString() ?? e.message);
    } catch (e) {
      return SosResult(sent: false, error: e.toString());
    }
  }

  /// Offline path: open the SMS composer pre-addressed to the locally cached
  /// emergency contacts with a location link. (True background SMS requires
  /// carrier-level integration — an explicit user send keeps this reliable
  /// and store-policy-safe.)
  Future<bool> _smsFallback(Position? position) async {
    final numbers = await cachedContactNumbers();
    if (numbers.isEmpty) return false;
    final loc = position != null
        ? 'https://maps.google.com/?q=${position.latitude},${position.longitude}'
        : 'location unknown';
    final body = Uri.encodeComponent('EMERGENCY! I need help. My location: $loc — sent from GramCare AI');
    final uri = Uri.parse('smsto:${numbers.join(',')}?body=$body');
    try {
      return await launchUrl(uri);
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
