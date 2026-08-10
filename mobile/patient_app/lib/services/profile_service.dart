import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/family_profile.dart';
import 'api_service.dart';

/// App-wide family-profile state (planning doc: the user first selects WHICH
/// family member they act for; every feature is then scoped to that member).
///
/// Profiles are fetched from the API and cached in Hive so profile selection
/// still works offline. The active selection persists across app restarts.
class ProfileService extends ChangeNotifier {
  static const _cacheBox = 'family_profiles_cache';
  static const _activeKey = 'active_family_profile_id';

  List<FamilyProfile> _profiles = [];
  FamilyProfile? _active; // null = the account owner themself
  bool _loading = false;

  List<FamilyProfile> get profiles => _profiles;
  FamilyProfile? get active => _active;
  bool get loading => _loading;

  Future<void> load() async {
    _loading = true;
    notifyListeners();
    try {
      final res = await ApiService().client.get('/family');
      _profiles = (res.data as List)
          .map((j) => FamilyProfile.fromJson(j as Map<String, dynamic>))
          .toList();
      // Refresh the offline cache
      final box = await Hive.openBox(_cacheBox);
      await box.put('profiles', _profiles.map((p) => p.toJson()).toList());
    } catch (_) {
      // Offline: fall back to the cached list so selection keeps working
      final box = await Hive.openBox(_cacheBox);
      final cached = box.get('profiles');
      if (cached is List) {
        _profiles = cached
            .map((j) => FamilyProfile.fromJson(Map<String, dynamic>.from(j as Map)))
            .toList();
      }
    }
    await _restoreActive();
    _loading = false;
    notifyListeners();
  }

  Future<void> _restoreActive() async {
    final prefs = await SharedPreferences.getInstance();
    final savedId = prefs.getInt(_activeKey);
    if (savedId != null) {
      try {
        _active = _profiles.firstWhere((p) => p.id == savedId);
      } catch (_) {
        _active = null;
      }
    }
  }

  Future<void> setActive(FamilyProfile? profile) async {
    _active = profile;
    final prefs = await SharedPreferences.getInstance();
    if (profile == null) {
      await prefs.remove(_activeKey);
    } else {
      await prefs.setInt(_activeKey, profile.id);
    }
    notifyListeners();
  }

  Future<FamilyProfile?> create(Map<String, dynamic> body) async {
    final res = await ApiService().client.post('/family', data: body);
    await load();
    final created = FamilyProfile.fromJson(res.data as Map<String, dynamic>);
    return created;
  }

  Future<void> clearOnLogout() async {
    _profiles = [];
    _active = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_activeKey);
    notifyListeners();
  }
}
