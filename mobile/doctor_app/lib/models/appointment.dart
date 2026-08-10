/// Mirrors backend schemas.AppointmentResponse.
class Appointment {
  final int id;
  final int patientId;
  final int? familyProfileId;
  final int doctorId;
  final DateTime scheduledAt;
  final String status; // PENDING | CONFIRMED | COMPLETED | CANCELLED
  final String? triageSummary;
  final String? consultationNotes;
  final int? paymentId;
  final DateTime createdAt;

  Appointment({
    required this.id,
    required this.patientId,
    this.familyProfileId,
    required this.doctorId,
    required this.scheduledAt,
    required this.status,
    this.triageSummary,
    this.consultationNotes,
    this.paymentId,
    required this.createdAt,
  });

  factory Appointment.fromJson(Map<String, dynamic> json) => Appointment(
        id: json['id'] as int,
        patientId: json['patient_id'] as int,
        familyProfileId: json['family_profile_id'] as int?,
        doctorId: json['doctor_id'] as int,
        scheduledAt: DateTime.parse(json['scheduled_at'] as String),
        status: json['status'] as String,
        triageSummary: json['triage_summary'] as String?,
        consultationNotes: json['consultation_notes'] as String?,
        paymentId: json['payment_id'] as int?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
