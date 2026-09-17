import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'offline_cache.dart';

/// Platform-keystore-backed storage for secrets.
///
/// Same pattern as apps/mobile_app/lib/services/secure_store.dart (verbatim
/// JWT handling) minus the Hive health-wallet AES key, which has no
/// equivalent in this app — the pharmacist app has no offline encrypted
/// clinical-record box to protect.
class SecureStore {
  static final SecureStore _instance = SecureStore._internal();
  factory SecureStore() => _instance;
  SecureStore._internal();

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _tokenKey = 'gramcare_pharmacy_access_token';
  static const _roleKey = 'gramcare_pharmacy_role';
  static const _deviceIdKey = 'gramcare_pharmacy_device_id';
  static const _lastFcmTokenKey = 'gramcare_pharmacy_last_registered_fcm_token';

  Future<String?> getToken() => _storage.read(key: _tokenKey);

  Future<void> setToken(String token) => _storage.write(key: _tokenKey, value: token);

  Future<void> clearToken() => _storage.delete(key: _tokenKey);

  Future<String?> getRole() => _storage.read(key: _roleKey);

  Future<void> setRole(String role) => _storage.write(key: _roleKey, value: role);

  Future<void> clearAll() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _roleKey);
    // Cached API responses outlive the token otherwise, letting the next
    // account on this device read the previous pharmacist's stock offline.
    await OfflineCache().clear();
  }

  /// Stable per-install identifier sent to POST /api/v1/auth/fcm-token as
  /// `device_id` — same rationale as apps/mobile_app: without a stable id
  /// every app restart would look like a brand-new device to the backend.
  Future<String> getOrCreateDeviceId() async {
    final existing = await _storage.read(key: _deviceIdKey);
    if (existing != null) return existing;
    final id = const Uuid().v4();
    await _storage.write(key: _deviceIdKey, value: id);
    return id;
  }

  /// The last FCM token this install successfully registered with the
  /// backend, to avoid re-POSTing an unchanged token on every login/resume.
  Future<String?> getLastRegisteredFcmToken() => _storage.read(key: _lastFcmTokenKey);

  Future<void> setLastRegisteredFcmToken(String token) =>
      _storage.write(key: _lastFcmTokenKey, value: token);

  /// Forgets which token was last registered, so the next sync re-POSTs.
  /// Called when the session changes: the marker records "this token is
  /// registered", not "registered for this user", and on a shared phone
  /// those are very different claims.
  Future<void> clearLastRegisteredFcmToken() =>
      _storage.delete(key: _lastFcmTokenKey);
}
