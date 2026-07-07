import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

/// Platform-keystore-backed storage for secrets.
///
/// Mirrors apps/mobile_app's SecureStore verbatim (same clinical-app
/// compliance requirement: JWT must never sit in plain shared_preferences).
/// This app has no Hive health-wallet boxes of its own, so the Hive AES key
/// helper from the patient app is omitted — everything else carries over.
class SecureStore {
  static final SecureStore _instance = SecureStore._internal();
  factory SecureStore() => _instance;
  SecureStore._internal();

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _tokenKey = 'gramcare_doctor_access_token';
  static const _roleKey = 'gramcare_doctor_role';
  static const _deviceIdKey = 'gramcare_doctor_device_id';
  static const _lastFcmTokenKey = 'gramcare_doctor_last_registered_fcm_token';

  Future<String?> getToken() => _storage.read(key: _tokenKey);

  Future<void> setToken(String token) => _storage.write(key: _tokenKey, value: token);

  Future<void> clearToken() => _storage.delete(key: _tokenKey);

  Future<String?> getRole() => _storage.read(key: _roleKey);

  Future<void> setRole(String role) => _storage.write(key: _roleKey, value: role);

  Future<void> clearAll() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _roleKey);
  }

  /// Stable per-install identifier sent to POST /api/v1/auth/fcm-token as
  /// `device_id`. Mirrors the patient app's rationale: without a stable id
  /// every app restart would look like a brand-new device to the backend.
  Future<String> getOrCreateDeviceId() async {
    final existing = await _storage.read(key: _deviceIdKey);
    if (existing != null) return existing;
    final id = const Uuid().v4();
    await _storage.write(key: _deviceIdKey, value: id);
    return id;
  }

  /// The last FCM token this install successfully registered with the
  /// backend — avoids re-POSTing an unchanged token on every login/resume.
  Future<String?> getLastRegisteredFcmToken() => _storage.read(key: _lastFcmTokenKey);

  Future<void> setLastRegisteredFcmToken(String token) =>
      _storage.write(key: _lastFcmTokenKey, value: token);
}
