import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
}
