/// Mirrors backend schemas.EmergencySOSResponse (GET /api/v1/sos/active).
class SosAlert {
  final int id;
  final int patientId;
  final double? locationLat;
  final double? locationLng;
  final String? locationText;
  final String? voiceNote;
  final String severity;
  final String status; // ACTIVE | RESPONDED | RESOLVED
  final int? respondedBy;
  final int escalationLevel;
  final int? assignedHospitalId;
  final DateTime createdAt;
  final DateTime? resolvedAt;

  SosAlert({
    required this.id,
    required this.patientId,
    this.locationLat,
    this.locationLng,
    this.locationText,
    this.voiceNote,
    required this.severity,
    required this.status,
    this.respondedBy,
    required this.escalationLevel,
    this.assignedHospitalId,
    required this.createdAt,
    this.resolvedAt,
  });

  factory SosAlert.fromJson(Map<String, dynamic> json) => SosAlert(
        id: json['id'] as int,
        patientId: json['patient_id'] as int,
        locationLat: (json['location_lat'] as num?)?.toDouble(),
        locationLng: (json['location_lng'] as num?)?.toDouble(),
        locationText: json['location_text'] as String?,
        voiceNote: json['voice_note'] as String?,
        severity: json['severity'] as String? ?? 'CRITICAL',
        status: json['status'] as String,
        respondedBy: json['responded_by'] as int?,
        escalationLevel: json['escalation_level'] as int? ?? 0,
        assignedHospitalId: json['assigned_hospital_id'] as int?,
        createdAt: DateTime.parse(json['created_at'] as String),
        resolvedAt: json['resolved_at'] != null ? DateTime.parse(json['resolved_at'] as String) : null,
      );
}
