import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

import '../models/health_record.dart';
import 'api_service.dart';
import 'encrypted_boxes.dart';

/// Offline-first Health Wallet engine.
///
/// Write path: records created on-device go into the encrypted
/// 'health_wallet' box with synced=false and a client UUID, then
/// [pushUnsynced] batches them to POST /ehr/sync. The endpoint is idempotent
/// on client_uuid, so retries/double-sends can never duplicate data.
/// (Previously this service posted single records to a nonexistent route,
/// so offline data never reached the server at all.)
///
/// Read path: [pullRemote] refreshes the local box with the caller's
/// server-side records (doctor-issued prescriptions etc.), keyed by server
/// id so re-pulls update rather than duplicate.
///
/// Three corrections from Experiment A
/// (docs/research/experiments/exp_a/results.md):
///
///  * [pushUnsynced] sends the queue in slices of [syncBatchLimit]. It used
///    to post every unsynced record in ONE request while the server caps the
///    list at 100, so a queue over 100 was rejected 422 on every attempt and
///    could never drain. Measured: 100 records synced; 101 persisted nothing
///    and stayed queued forever (finding F-A1).
///  * The server now reports permanently refused records in `rejected`.
///    Those stop being retried and are NOT marked synced (finding F-A2).
///  * [pullRemote] updates a cached server record instead of skipping it, so
///    a server-side correction reaches the device (finding F-A5).
class SyncService {
  static final SyncService _instance = SyncService._internal();
  factory SyncService() => _instance;
  SyncService._internal();

  static const walletBoxName = 'health_wallet';

  /// Must not exceed the server's cap on `POST /ehr/sync` (the `records`
  /// list is validated with max_length=100). Sending more is rejected 422
  /// with nothing persisted, and the whole queue stalls behind it.
  static const syncBatchLimit = 100;

  final _uuid = const Uuid();

  Future<Box<HealthRecord>> _wallet() =>
      EncryptedBoxes.open<HealthRecord>(walletBoxName);

  /// Create a record locally (works fully offline) and opportunistically try
  /// to sync it immediately.
  Future<HealthRecord> createRecord({
    required String patientName,
    required String content,
    required String recordType,
    String? title,
    int? familyProfileId,
    String? doctorName,
    String severity = 'INFO',
    Map<String, dynamic>? payload,
  }) async {
    final box = await _wallet();
    final record = HealthRecord(
      patientName: patientName,
      symptoms: content,
      aiSeverity: severity,
      timestamp: DateTime.now(),
      recordType: recordType,
      title: title,
      familyProfileId: familyProfileId,
      doctorName: doctorName,
      clientUuid: _uuid.v4(),
      synced: false,
      payload: payload,
    );
    await box.add(record);
    // Fire-and-forget attempt; failures simply leave it queued.
    pushUnsynced();
    return record;
  }

  /// Push every unsynced local record to the server in idempotent batches.
  ///
  /// Slices the queue into [syncBatchLimit]-record requests. Each slice is
  /// acknowledged on its own, so a long offline stretch drains steadily
  /// instead of failing as one oversized request.
  Future<void> pushUnsynced() async {
    final box = await _wallet();
    final unsynced = box.values
        .where((r) => !r.synced && !r.syncRejected && r.clientUuid != null)
        .toList();
    if (unsynced.isEmpty) return;

    var acknowledgedTotal = 0;
    var rejectedTotal = 0;

    for (var start = 0; start < unsynced.length; start += syncBatchLimit) {
      final end = (start + syncBatchLimit) > unsynced.length
          ? unsynced.length
          : start + syncBatchLimit;
      final slice = unsynced.sublist(start, end);

      try {
        final res = await ApiService().client.post('/ehr/sync', data: {
          'records': slice
              .map((r) => {
                    'client_uuid': r.clientUuid,
                    'record_type': r.recordType,
                    'title': r.title,
                    'content': r.content,
                    'doctor_name': r.doctorName,
                    'family_profile_id': r.familyProfileId,
                    'record_date': r.timestamp.toIso8601String(),
                    if (r.payload != null) 'payload': r.payload,
                  })
              .toList(),
        });

        final acknowledged = <String>{
          ...List<String>.from(res.data['synced'] as List? ?? const []),
          ...List<String>.from(res.data['duplicates'] as List? ?? const []),
        };
        // Permanently refused: stop retrying, but never claim it synced.
        final refused = <String>{
          for (final entry in (res.data['rejected'] as List? ?? const []))
            (entry as Map)['client_uuid'] as String,
        };

        for (final record in slice) {
          if (acknowledged.contains(record.clientUuid)) {
            record.synced = true;
            await record.save();
          } else if (refused.contains(record.clientUuid)) {
            record.syncRejected = true;
            await record.save();
          }
        }
        acknowledgedTotal += acknowledged.length;
        rejectedTotal += refused.length;
      } on DioException catch (e) {
        // Offline or server unavailable. This slice and everything after it
        // stay queued; stop rather than hammering the rest against a
        // connection that has just failed.
        debugPrint('Sync deferred (${e.type}) after $acknowledgedTotal '
            'record(s). Remaining records stay queued.');
        return;
      } catch (e) {
        debugPrint('Unexpected sync error: $e');
        return;
      }
    }

    debugPrint('Sync complete: $acknowledgedTotal acknowledged, '
        '$rejectedTotal permanently rejected.');
  }

  /// Pull the caller's server-side records into the local wallet cache so
  /// the wallet is complete offline. Server-origin records are stored with
  /// clientUuid `srv-<id>` — the same idempotency trick, locally.
  Future<void> pullRemote(int myUserId, {String patientName = 'Me'}) async {
    try {
      final res = await ApiService().client.get('/ehr/patient/$myUserId');
      final box = await _wallet();
      final existingUuids = box.values.map((r) => r.clientUuid).toSet();

      for (final j in (res.data as List)) {
        final m = j as Map<String, dynamic>;
        final marker = 'srv-${m['id']}';
        if (existingUuids.contains(marker)) {
          // Update in place rather than skipping. Skipping meant a
          // server-side correction to an already-cached record never reached
          // the device, leaving the local copy permanently stale
          // (Experiment A, finding F-A5).
          final cached = box.values.firstWhere((r) => r.clientUuid == marker);
          cached.symptoms = m['content'] as String? ?? cached.symptoms;
          cached.title = m['title'] as String? ?? cached.title;
          cached.recordType = m['record_type'] as String? ?? cached.recordType;
          cached.doctorName = m['doctor_name'] as String? ?? cached.doctorName;
          cached.familyProfileId =
              m['family_profile_id'] as int? ?? cached.familyProfileId;
          if (m['payload'] is Map) {
            cached.payload = Map<String, dynamic>.from(m['payload'] as Map);
          }
          final when = DateTime.tryParse(m['record_date'] as String? ?? '');
          if (when != null) cached.timestamp = when;
          await cached.save();
          continue;
        }
        await box.add(HealthRecord(
          patientName: patientName,
          symptoms: m['content'] as String? ?? '',
          aiSeverity: 'INFO',
          timestamp: DateTime.tryParse(m['record_date'] as String? ?? '') ??
              DateTime.tryParse(m['created_at'] as String? ?? '') ??
              DateTime.now(),
          recordType: m['record_type'] as String? ?? 'note',
          title: m['title'] as String?,
          familyProfileId: m['family_profile_id'] as int?,
          doctorName: m['doctor_name'] as String?,
          clientUuid: marker,
          synced: true,
          payload: m['payload'] is Map
              ? Map<String, dynamic>.from(m['payload'] as Map)
              : null,
        ));
      }
    } on DioException catch (e) {
      debugPrint('Wallet pull skipped (offline?): ${e.type}');
    }
  }

  /// Full sync cycle: push queued local records, then refresh from server.
  Future<void> fullSync(int myUserId) async {
    await pushUnsynced();
    await pullRemote(myUserId);
  }
}
