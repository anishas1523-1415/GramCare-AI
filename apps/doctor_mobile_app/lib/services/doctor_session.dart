import 'package:flutter/foundation.dart';

import '../models/doctor_profile.dart';
import 'api_service.dart';
import 'secure_store.dart';

/// App-wide session state: the logged-in doctor's own profile (GET
/// /doctors/me), fetched right after login and cached in memory for the
/// dashboard/profile/schedule screens. Not persisted to disk — re-fetched
/// each cold start, same as apps/mobile_app's ProfileService pattern for
/// account-scoped (not offline-critical) data.
class DoctorSession extends ChangeNotifier {
  DoctorProfile? _profile;
  bool _loading = false;

  DoctorProfile? get profile => _profile;
  bool get loading => _loading;
  int? get doctorId => _profile?.id;

  /// Whether the queue/prescriptions/AI-summary/SOS endpoints will actually
  /// let this doctor through — mirrors require_approved_doctor() server
  /// side, so screens can show a clear reason instead of firing a request
  /// that's guaranteed to 403.
  bool get isApproved => _profile?.isApproved ?? false;

  Future<void> loadProfile() async {
    _loading = true;
    notifyListeners();
    try {
      final res = await ApiService().client.get('/doctors/me');
      _profile = DoctorProfile.fromJson(res.data as Map<String, dynamic>);
    } catch (e) {
      debugPrint('Failed to load doctor profile: $e');
    }
    _loading = false;
    notifyListeners();
  }

  Future<void> updateProfile(Map<String, dynamic> body) async {
    final res = await ApiService().client.put('/doctors/me', data: body);
    _profile = DoctorProfile.fromJson(res.data as Map<String, dynamic>);
    notifyListeners();
  }

  Future<void> uploadPhoto(String imageBase64) async {
    final res = await ApiService().client.post('/doctors/me/photo', data: {'image_base64': imageBase64});
    _profile = DoctorProfile.fromJson(res.data as Map<String, dynamic>);
    notifyListeners();
  }

  Future<void> uploadLicenseDocument(String imageBase64) async {
    final res = await ApiService().client.post('/doctors/me/license-document', data: {'image_base64': imageBase64});
    _profile = DoctorProfile.fromJson(res.data as Map<String, dynamic>);
    notifyListeners();
  }

  Future<void> clearOnLogout() async {
    _profile = null;
    await SecureStore().clearAll();
    notifyListeners();
  }
}
