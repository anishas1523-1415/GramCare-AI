import 'package:flutter/foundation.dart';

import 'secure_store.dart';

/// The user's own AI provider key, when they have chosen to supply one.
///
/// GramCare runs on free AI tiers with a daily cap. When that cap is spent,
/// every AI feature falls back to a placeholder answer for the rest of the
/// day. Rather than show a rural patient a dead assistant, the apps offer to
/// use a key of their own — and someone who has one is then never blocked by
/// a shared quota again.
///
/// The key is a credential, so it lives in the platform keystore beside the
/// session token, never in shared_preferences and never on our server: it is
/// attached to the requests the user makes and nowhere else.
class AiKeyService extends ChangeNotifier {
  static final AiKeyService _instance = AiKeyService._internal();
  factory AiKeyService() => _instance;
  AiKeyService._internal();

  static const _storageKey = 'gramcare_user_ai_key';

  String? _key;
  bool _loaded = false;

  /// Null when the user has not supplied a key. Read this straight into a
  /// request body — the backend treats it as optional.
  String? get key => _key;

  bool get hasKey => (_key ?? '').isNotEmpty;

  /// Set once the server has told us its own quota is spent, so the prompt
  /// only ever appears in that situation and not as general clutter.
  bool quotaExhausted = false;

  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    _key = await SecureStore.readRaw(_storageKey);
    if (_key != null) notifyListeners();
  }

  Future<void> save(String value) async {
    final trimmed = value.trim();
    if (trimmed.isEmpty) return;
    _key = trimmed;
    await SecureStore.writeRaw(_storageKey, trimmed);
    // A key the user just gave us is assumed good until a request says
    // otherwise; clearing this hides the prompt immediately.
    quotaExhausted = false;
    notifyListeners();
  }

  Future<void> clear() async {
    _key = null;
    await SecureStore.deleteRaw(_storageKey);
    notifyListeners();
  }

  /// Records what the last AI response said about the shared quota.
  void noteQuotaExhausted(bool exhausted) {
    if (quotaExhausted == exhausted) return;
    quotaExhausted = exhausted;
    notifyListeners();
  }
}
