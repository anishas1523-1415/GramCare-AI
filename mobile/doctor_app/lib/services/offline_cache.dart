import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Read-through cache for GET responses, so a doctor with no signal
/// still sees their patient queue and schedule instead of an error screen.
///
/// Rural connectivity is the whole premise of this platform, but this app
/// previously had no offline story at all: every screen called the API
/// directly and rendered a failure when it could not be reached.
///
/// Deliberately read-only. Queuing offline *writes* (issuing a prescription)
/// needs server-side idempotency keys per action so a retry cannot
/// duplicate a prescription — that is a backend change, not something to fake
/// on-device. Until then, writes still require connectivity and say so.
class OfflineCache {
  static final OfflineCache _instance = OfflineCache._internal();
  factory OfflineCache() => _instance;
  OfflineCache._internal();

  static const _prefix = 'offline_cache_';

  Future<void> save(String key, Object? payload) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      '$_prefix$key',
      jsonEncode({
        'at': DateTime.now().toIso8601String(),
        'payload': payload,
      }),
    );
  }

  /// Returns the cached entry, or null when nothing was ever cached for
  /// this key (or the stored value is unreadable — a format change from an
  /// older build should degrade to "no cache", never crash the screen).
  Future<CachedEntry?> read(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_prefix$key');
    if (raw == null) return null;
    try {
      final decoded = Map<String, dynamic>.from(jsonDecode(raw) as Map);
      final at = DateTime.tryParse(decoded['at'] as String? ?? '');
      if (at == null) return null;
      return CachedEntry(payload: decoded['payload'], cachedAt: at);
    } catch (_) {
      return null;
    }
  }

  /// Clears every cached response. Called on logout so the next account to
  /// use this device cannot read the previous doctor's patient data offline.
  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys().where((k) => k.startsWith(_prefix)).toList();
    for (final k in keys) {
      await prefs.remove(k);
    }
  }
}

class CachedEntry {
  final Object? payload;
  final DateTime cachedAt;

  const CachedEntry({required this.payload, required this.cachedAt});

  /// Short human-readable age, e.g. "2h ago" — shown in the offline banner
  /// so a doctor can judge whether the data is still trustworthy.
  String get ageLabel {
    final diff = DateTime.now().difference(cachedAt);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}
