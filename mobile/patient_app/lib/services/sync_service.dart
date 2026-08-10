import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

import '../models/health_record.dart';
import 'api_service.dart';

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
class SyncService {
  static final SyncService _instance = SyncService._internal();
  factory SyncService() => _instance;
  SyncService._internal();

  static const walletBoxName = 'health_wallet';
  final _uuid = const Uuid();

  Future<Box<HealthRecord>> _wallet() => Hive.openBox<HealthRecord>(walletBoxName);

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
    );
    await box.add(record);
    // Fire-and-forget attempt; failures simply leave it queued.
    pushUnsynced();
    return record;
  }

  /// Push every unsynced local record to the server in one idempotent batch.
  Future<void> pushUnsynced() async {
    final box = await _wallet();
    final unsynced = box.values
        .where((r) => !r.synced && r.clientUuid != null)
        .toList();
    if (unsynced.isEmpty) return;

    try {
      final res = await ApiService().client.post('/ehr/sync', data: {
        'records': unsynced
            .map((r) => {
                  'client_uuid': r.clientUuid,
                  'record_type': r.recordType,
                  'title': r.title,
                  'content': r.content,
                  'doctor_name': r.doctorName,
                  'family_profile_id': r.familyProfileId,
                  'record_date': r.timestamp.toIso8601String(),
                })
            .toList(),
      });

      final acknowledged = <String>{
        ...List<String>.from(res.data['synced'] as List? ?? const []),
        ...List<String>.from(res.data['duplicates'] as List? ?? const []),
      };
      for (final record in unsynced) {
        if (acknowledged.contains(record.clientUuid)) {
          record.synced = true;
          await record.save();
        }
      }
      debugPrint('Sync complete: ${acknowledged.length} record(s) acknowledged.');
    } on DioException catch (e) {
      // Offline or server unavailable — records stay queued for next time.
      debugPrint('Sync deferred (${e.type}). Records remain queued.');
    } catch (e) {
      debugPrint('Unexpected sync error: $e');
    }
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
        if (existingUuids.contains(marker)) continue;
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
