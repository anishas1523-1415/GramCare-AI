/// Mirrors backend schemas.EHRRecordResponse — read-only here (doctor mobile
/// app only reads patient wallet history; writes flow through
/// /ehr/issue_prescription instead).
class EHRRecord {
  final int id;
  final int patientId;
  final int? familyProfileId;
  final String recordType;
  final String? title;
  final String content;
  final Map<String, dynamic>? payload;
  final String? doctorName;
  final DateTime? recordDate;
  final DateTime createdAt;

  EHRRecord({
    required this.id,
    required this.patientId,
    this.familyProfileId,
    required this.recordType,
    this.title,
    required this.content,
    this.payload,
    this.doctorName,
    this.recordDate,
    required this.createdAt,
  });

  factory EHRRecord.fromJson(Map<String, dynamic> json) => EHRRecord(
        id: json['id'] as int,
        patientId: json['patient_id'] as int,
        familyProfileId: json['family_profile_id'] as int?,
        recordType: json['record_type'] as String,
        title: json['title'] as String?,
        content: json['content'] as String,
        payload: json['payload'] as Map<String, dynamic>?,
        doctorName: json['doctor_name'] as String?,
        recordDate: json['record_date'] != null ? DateTime.parse(json['record_date'] as String) : null,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
