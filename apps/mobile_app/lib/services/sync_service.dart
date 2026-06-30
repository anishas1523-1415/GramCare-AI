import 'package:hive_flutter/hive_flutter.dart';
import 'package:dio/dio.dart';
import '../models/health_record.dart';
import 'api_service.dart';

class SyncService {
  static final SyncService _instance = SyncService._internal();

  factory SyncService() {
    return _instance;
  }

  SyncService._internal();

  /// Attempts to sync all offline records in the 'sync_queue' to the remote backend.
  Future<void> syncOfflineRecords() async {
    final box = await Hive.openBox<HealthRecord>('sync_queue');
    final healthWallet = await Hive.openBox<HealthRecord>('health_wallet');

    if (box.isEmpty) return;

    List<dynamic> keysToRemove = [];

    for (var key in box.keys) {
      HealthRecord? record = box.get(key);
      if (record != null) {
        try {
          // Attempt to push to backend
          await ApiService().client.post(
            '/ehr/sync',
            data: {
              'patient_name': record.patientName,
              'symptoms': record.symptoms,
              'ai_severity': record.aiSeverity,
              'timestamp': record.timestamp.toIso8601String(),
            },
          );

          // If successful, move to permanent health_wallet and queue for removal
          await healthWallet.add(record);
          keysToRemove.add(key);
          print('Successfully synced record for ${record.patientName}');
        } on DioException catch (e) {
          // If network error (offline), we leave it in the queue for next time
          if (e.type == DioExceptionType.connectionTimeout || 
              e.type == DioExceptionType.connectionError ||
              e.type == DioExceptionType.receiveTimeout) {
            print('Network unavailable, leaving in queue: ${record.patientName}');
          } else {
            // Other server error (e.g. 500, 400) - might need manual intervention, but we keep it
            print('Server error during sync: ${e.message}');
          }
        } catch (e) {
          print('Unknown error during sync: $e');
        }
      }
    }

    // Clean up successfully synced records
    for (var key in keysToRemove) {
      await box.delete(key);
    }
  }

  /// Adds a record to the sync queue. Use this when the app detects it's offline.
  Future<void> queueRecord(HealthRecord record) async {
    final box = await Hive.openBox<HealthRecord>('sync_queue');
    await box.add(record);
    
    // Attempt an immediate sync just in case we have a brief connection
    syncOfflineRecords();
  }
}
