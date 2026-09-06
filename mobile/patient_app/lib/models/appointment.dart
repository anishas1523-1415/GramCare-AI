/// Mirrors schemas.AppointmentResponse — GET /appointments/my (this app's
/// own bookings) and the response of POST /appointments/book.
class Appointment {
  final int id;
  final int patientId;
  final int? familyProfileId;
  final int doctorId;
  final DateTime scheduledAt;
  final String status; // PENDING | CONFIRMED | COMPLETED | CANCELLED
  final String? triageSummary;
  final int? triageSeverityScore;
  final String? consultationNotes;
  final int? paymentId;
  final DateTime createdAt;

  const Appointment({
    required this.id,
    required this.patientId,
    this.familyProfileId,
    required this.doctorId,
    required this.scheduledAt,
    required this.status,
    this.triageSummary,
    this.triageSeverityScore,
    this.consultationNotes,
    this.paymentId,
    required this.createdAt,
  });

  factory Appointment.fromJson(Map<String, dynamic> json) => Appointment(
        id: json['id'] as int,
        patientId: json['patient_id'] as int? ?? 0,
        familyProfileId: json['family_profile_id'] as int?,
        doctorId: json['doctor_id'] as int? ?? 0,
        scheduledAt: DateTime.parse(json['scheduled_at'] as String),
        status: json['status'] as String? ?? 'PENDING',
        triageSummary: json['triage_summary'] as String?,
        triageSeverityScore: json['triage_severity_score'] as int?,
        consultationNotes: json['consultation_notes'] as String?,
        paymentId: json['payment_id'] as int?,
        createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
      );
}
