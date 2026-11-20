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

  /// Structured data alongside the human-readable [content] - a scanned
  /// prescription's image URL, a parsed medicine list.
  ///
  /// The server has accepted and stored `payload` on both sync paths all
  /// along; this model had no field for it and the push body never sent one,
  /// so anything structured created offline was silently dropped
  /// (Experiment A, finding F-A6).
  @HiveField(10)
  Map<String, dynamic>? payload;

  /// True when the server has permanently refused this record - for example
  /// it is scoped to a family member deleted on another device. Such a
  /// record must stop being retried, and must NOT be reported as synced,
  /// because it never reached the server (Experiment A, finding F-A2).
  @HiveField(11)
  bool syncRejected;

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
    this.payload,
    this.syncRejected = false,
  });

  String get content => symptoms;
}
