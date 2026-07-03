import 'package:hive/hive.dart';

part 'health_record.g.dart';

/// A Family Health Wallet record, stored offline in an encrypted Hive box.
///
/// Extended from the original 4-field shape to carry the full server
/// contract: record type (color-coded in the wallet UI), family-member
/// scoping, and a client-generated UUID enabling idempotent sync
/// (POST /api/v1/ehr/sync). The adapter tolerates records written by the
/// old 4-field version so existing offline data keeps loading.
@HiveType(typeId: 0)
class HealthRecord extends HiveObject {
  @HiveField(0)
  late String patientName;

  @HiveField(1)
  late String symptoms; // legacy name; holds `content` for new records

  @HiveField(2)
  late String aiSeverity; // legacy; kept so old boxes still read

  @HiveField(3)
  late DateTime timestamp;

  @HiveField(4)
  String recordType; // prescription | lab_report | triage_log | vaccination | scan | note

  @HiveField(5)
  String? title;

  @HiveField(6)
  int? familyProfileId;

  @HiveField(7)
  String? doctorName;

  @HiveField(8)
  String? clientUuid;

  /// True once the record exists server-side (either it originated there or
  /// a sync succeeded). Unsynced records are what /ehr/sync uploads.
  @HiveField(9)
  bool synced;

  HealthRecord({
    required this.patientName,
    required this.symptoms,
    required this.aiSeverity,
    required this.timestamp,
    this.recordType = 'note',
    this.title,
    this.familyProfileId,
    this.doctorName,
    this.clientUuid,
    this.synced = false,
  });

  String get content => symptoms;
}
