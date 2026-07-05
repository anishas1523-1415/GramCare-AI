import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Platform-keystore-backed storage for secrets.
///
/// Replaces the previous plain shared_preferences storage of the JWT (a
/// compliance gap for a clinical app) and owns the AES key that encrypts the
/// Hive health-wallet boxes.
class SecureStore {
  static final SecureStore _instance = SecureStore._internal();
  factory SecureStore() => _instance;
  SecureStore._internal();

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _tokenKey = 'gramcare_access_token';
  static const _hiveKeyKey = 'gramcare_hive_aes_key';
  static const _legacyPrefsTokenKey = 'access_token';
  static const _deviceIdKey = 'gramcare_device_id';
  static const _lastFcmTokenKey = 'gramcare_last_registered_fcm_token';

  Future<String?> getToken() => _storage.read(key: _tokenKey);

  Future<void> setToken(String token) => _storage.write(key: _tokenKey, value: token);

  Future<void> clearToken() => _storage.delete(key: _tokenKey);

  /// One-time migration: lift a token previously stored in plain
  /// shared_preferences into secure storage, then remove the plain copy.
  Future<void> migrateLegacyToken() async {
    final prefs = await SharedPreferences.getInstance();
    final legacy = prefs.getString(_legacyPrefsTokenKey);
    if (legacy != null) {
      final existing = await getToken();
      if (existing == null) {
        await setToken(legacy);
      }
      await prefs.remove(_legacyPrefsTokenKey);
    }
  }

  /// 256-bit AES key for Hive box encryption; generated once per install
  /// and kept in the keystore.
  Future<List<int>> getOrCreateHiveKey() async {
    final existing = await _storage.read(key: _hiveKeyKey);
    if (existing != null) {
      return base64Url.decode(existing);
    }
    final rng = Random.secure();
    final key = List<int>.generate(32, (_) => rng.nextInt(256));
    await _storage.write(key: _hiveKeyKey, value: base64Url.encode(key));
    return key;
  }

  /// Stable per-install identifier sent to POST /api/v1/auth/fcm-token as
  /// `device_id`. The backend uses (user_id, device_id, platform) to decide
  /// whether an incoming token replaces an existing row for this device or
  /// creates a new one — without a stable id every app restart would look
  /// like a brand-new device to the backend.
  Future<String> getOrCreateDeviceId() async {
    final existing = await _storage.read(key: _deviceIdKey);
    if (existing != null) return existing;
    final id = const Uuid().v4();
    await _storage.write(key: _deviceIdKey, value: id);
    return id;
  }

  /// The last FCM token this install successfully registered with the
  /// backend. Used purely to avoid re-POSTing an unchanged token on every
  /// login/app-resume — FirebaseMessaging.onTokenRefresh only fires when the
  /// token actually rotates, but login/dashboard-resume can run with a token
  /// that hasn't changed since the last successful registration.
  Future<String?> getLastRegisteredFcmToken() => _storage.read(key: _lastFcmTokenKey);

  Future<void> setLastRegisteredFcmToken(String token) =>
      _storage.write(key: _lastFcmTokenKey, value: token);
}
