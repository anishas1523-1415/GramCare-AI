import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:doctor_mobile_app/services/offline_cache.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('read returns null when nothing was cached', () async {
    expect(await OfflineCache().read('queue'), isNull);
  });

  test('round-trips a cached list payload', () async {
    await OfflineCache().save('queue', [
      {'id': 1, 'patient_id': 7},
    ]);
    final entry = await OfflineCache().read('queue');
    expect(entry, isNotNull);
    expect((entry!.payload as List).first['patient_id'], 7);
    expect(entry.ageLabel, 'just now');
  });

  test('clear removes cached entries so the next account cannot read them', () async {
    await OfflineCache().save('queue', [1, 2, 3]);
    await OfflineCache().clear();
    expect(await OfflineCache().read('queue'), isNull);
  });

  test('unreadable stored value degrades to no cache instead of throwing', () async {
    SharedPreferences.setMockInitialValues({'offline_cache_queue': 'not-json'});
    expect(await OfflineCache().read('queue'), isNull);
  });
}
