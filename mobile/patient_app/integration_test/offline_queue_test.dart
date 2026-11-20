// On-device verification of Experiment A finding F-A1.
//
// The Python harness in research/experiments/exp_a/ exercises a
// reimplementation of SyncService. This test exercises the REAL Dart code on
// REAL hardware: the real encrypted Hive box, the real SyncService, the real
// Dio client and interceptors.
//
// What it proves:
//   * a 150-record offline backlog drains completely (before the chunking fix
//     the server rejected the whole queue 422 and it could never drain)
//   * the records actually reach the server, counted server-side
//   * re-pushing an already-synced queue is a no-op
//   * a 101-record single request is still refused by the server, so the fix
//     is the client's chunking and not a loosened cap
//
// Run against a backend on the developer's machine, never production:
//
//   adb reverse tcp:8000 tcp:8000
//   flutter test integration_test/offline_queue_test.dart -d <device-id> \
//     --dart-define=GRAMCARE_API_BASE=http://localhost:8000/api/v1 \
//     --dart-define=EXPA_USER=expa_device --dart-define=EXPA_PASS=strongpass123
//
// All data is synthetic.
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:integration_test/integration_test.dart';
import 'package:uuid/uuid.dart';

import 'package:mobile_app/models/health_record.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/services/encrypted_boxes.dart';
import 'package:mobile_app/services/secure_store.dart';
import 'package:mobile_app/services/sync_service.dart';

const _user = String.fromEnvironment('EXPA_USER', defaultValue: 'expa_device');
const _pass =
    String.fromEnvironment('EXPA_PASS', defaultValue: 'strongpass123');

/// How many records sit in the backlog. Deliberately above the server's
/// 100-record cap on POST /ehr/sync, which is what used to deadlock.
const _backlog = 150;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  late Box<HealthRecord> wallet;
  late String runTag;

  setUpAll(() async {
    // Mirror main.dart's Hive bootstrap exactly, including the cipher.
    await Hive.initFlutter();
    if (!Hive.isAdapterRegistered(0)) {
      Hive.registerAdapter(HealthRecordAdapter());
    }
    wallet = await EncryptedBoxes.open<HealthRecord>(
      SyncService.walletBoxName,
    );

    // A real session, obtained the way the app does, so the Dio interceptor
    // attaches a real Authorization header.
    final login = Dio(BaseOptions(baseUrl: ApiService.baseUrl));
    final res = await login.post(
      '/auth/login',
      data: FormData.fromMap({'username': _user, 'password': _pass}),
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    expect(res.statusCode, 200,
        reason: 'could not log in as $_user against ${ApiService.baseUrl}');
    await SecureStore().setToken(res.data['access_token'] as String);

    runTag = 'dev-${DateTime.now().millisecondsSinceEpoch}';
  });

  tearDownAll(() async {
    // Leave the handset's wallet as we found it.
    final mine = wallet.values
        .where((r) => (r.clientUuid ?? '').startsWith('dev-'))
        .toList();
    for (final r in mine) {
      await r.delete();
    }
  });

  testWidgets('a $_backlog-record offline backlog drains on the real device',
      (tester) async {
    // ---------------------------------------------------------------- given
    // The state an extended offline stretch leaves behind: records in the
    // encrypted box with synced=false and a client UUID. Written straight to
    // the box rather than through createRecord, because createRecord also
    // fires an opportunistic push, which would sync them one at a time and
    // never build the backlog this test is about.
    const uuid = Uuid();
    final queued = <String>[];
    for (var i = 0; i < _backlog; i++) {
      final cu = '$runTag-${uuid.v4()}';
      queued.add(cu);
      await wallet.add(HealthRecord(
        patientName: 'Device Test',
        symptoms: 'offline backlog record $i',
        aiSeverity: 'INFO',
        timestamp: DateTime.now().subtract(Duration(minutes: _backlog - i)),
        recordType: 'note',
        title: 'backlog $i',
        clientUuid: cu,
        synced: false,
      ));
    }

    final pendingBefore = wallet.values
        .where((r) => !r.synced && !r.syncRejected && r.clientUuid != null)
        .length;
    expect(pendingBefore, greaterThanOrEqualTo(_backlog),
        reason: 'the backlog was not written to the box');

    // ----------------------------------------------------------------- when
    final started = DateTime.now();
    await SyncService().pushUnsynced();
    final elapsed = DateTime.now().difference(started);

    // ----------------------------------------------------------------- then
    final stillQueued = wallet.values
        .where((r) =>
            (r.clientUuid ?? '').startsWith(runTag) &&
            !r.synced &&
            !r.syncRejected)
        .length;
    final markedSynced = wallet.values
        .where((r) => (r.clientUuid ?? '').startsWith(runTag) && r.synced)
        .length;

    // ignore: avoid_print
    print('[exp-a] backlog=$_backlog  still_queued=$stillQueued  '
        'marked_synced=$markedSynced  elapsed_ms=${elapsed.inMilliseconds}');

    expect(stillQueued, 0,
        reason: 'the queue did not drain: $stillQueued record(s) remain. '
            'Before the chunking fix this was all $_backlog, because '
            'pushUnsynced posted the whole queue in one request against a '
            'server that caps the list at 100.');
    expect(markedSynced, _backlog);

    // An HTTP 200 is not proof. Count them server-side.
    //
    // Read the patient's OWN wallet, not /ehr/records: that route is scoped
    // to approved doctors and admins (Experiment G, finding G-6), so a
    // patient token correctly gets a 403 there.
    final api = ApiService().client;
    final me = await api.get('/auth/me');
    final myId = (me.data as Map)['id'];
    // Page through. The route caps a page at 200 rows ordered by
    // record_date desc, so a single request cannot be trusted to contain
    // this run's records once the table holds more than that.
    var serverCount = 0;
    var skip = 0;
    const page = 200;
    while (true) {
      final res = await api.get('/ehr/patient/$myId', queryParameters: {
        'skip': skip,
        'limit': page,
      });
      final rows = res.data as List;
      serverCount += rows
          .where((e) =>
              ((e as Map)['client_uuid'] as String? ?? '').startsWith(runTag))
          .length;
      if (rows.length < page) break;
      skip += page;
    }
    // ignore: avoid_print
    print('[exp-a] server-side rows for this run: $serverCount');
    expect(serverCount, _backlog,
        reason: 'the server holds $serverCount of $_backlog records');
  }, timeout: const Timeout(Duration(minutes: 10)));

  testWidgets('re-pushing a drained queue is a no-op', (tester) async {
    final before = wallet.values
        .where((r) => !r.synced && !r.syncRejected && r.clientUuid != null)
        .length;
    await SyncService().pushUnsynced();
    final after = wallet.values
        .where((r) => !r.synced && !r.syncRejected && r.clientUuid != null)
        .length;
    expect(after, before);
  }, timeout: const Timeout(Duration(minutes: 5)));

  testWidgets('the server still refuses a single request over its 100 cap',
      (tester) async {
    // Proves the fix is the client chunking, not a relaxed server cap.
    const uuid = Uuid();
    final oversized = [
      for (var i = 0; i < 101; i++)
        {
          'client_uuid': 'cap-${uuid.v4()}',
          'record_type': 'note',
          'title': 'cap $i',
          'content': 'cap probe $i',
          'record_date': DateTime.now().toIso8601String(),
        }
    ];
    int? status;
    try {
      final res = await ApiService()
          .client
          .post('/ehr/sync', data: {'records': oversized});
      status = res.statusCode;
    } on DioException catch (e) {
      status = e.response?.statusCode;
    }
    // ignore: avoid_print
    print('[exp-a] 101-record single request -> HTTP $status');
    expect(status, 422);
  }, timeout: const Timeout(Duration(minutes: 5)));
}
