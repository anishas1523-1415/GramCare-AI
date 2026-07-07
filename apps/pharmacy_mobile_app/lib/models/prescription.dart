/// Mirrors schemas.PrescriptionResponse (apps/backend_service/schemas.py:153-166)
/// as returned by GET /pharmacy/queue.
///
/// SCOPING NOTE: models.Prescription (apps/backend_service/models.py:190-207)
/// has no delivery-tracking status field — only `is_fulfilled` (bool) and
/// `fulfilled_by_pharmacy_id`. There is no PENDING/PACKED/OUT_FOR_DELIVERY/
/// DELIVERED lifecycle in the backend today, so this app treats "fulfilled"
/// as the terminal state and does not attempt to surface delivery-tracking
/// stages that don't exist server-side.
class MedicineNeeded {
  final String name;
  final String dosage;
  final String frequency;
  final String duration;

  MedicineNeeded({
    required this.name,
    required this.dosage,
    required this.frequency,
    required this.duration,
  });

  factory MedicineNeeded.fromJson(Map<String, dynamic> json) {
    return MedicineNeeded(
      name: (json['name'] as String?) ?? '',
      dosage: (json['dosage'] as String?) ?? '',
      frequency: (json['frequency'] as String?) ?? '',
      duration: (json['duration'] as String?) ?? '',
    );
  }
}

class PrescriptionQueueItem {
  final int id;
  final int? appointmentId;
  final int patientId;
  final int doctorId;
  final List<MedicineNeeded> medicines;
  final String? dosageInstructions;
  final String? diagnosis;
  final String? notes;
  final bool isFulfilled;
  final String createdAt;

  PrescriptionQueueItem({
    required this.id,
    this.appointmentId,
    required this.patientId,
    required this.doctorId,
    required this.medicines,
    this.dosageInstructions,
    this.diagnosis,
    this.notes,
    required this.isFulfilled,
    required this.createdAt,
  });

  factory PrescriptionQueueItem.fromJson(Map<String, dynamic> json) {
    final meds = (json['medicines'] as List<dynamic>? ?? [])
        .map((m) => MedicineNeeded.fromJson(Map<String, dynamic>.from(m as Map)))
        .toList();
    return PrescriptionQueueItem(
      id: json['id'] as int,
      appointmentId: json['appointment_id'] as int?,
      patientId: json['patient_id'] as int? ?? 0,
      doctorId: json['doctor_id'] as int? ?? 0,
      medicines: meds,
      dosageInstructions: json['dosage_instructions'] as String?,
      diagnosis: json['diagnosis'] as String?,
      notes: json['notes'] as String?,
      isFulfilled: json['is_fulfilled'] as bool? ?? false,
      createdAt: json['created_at'] as String? ?? '',
    );
  }
}
