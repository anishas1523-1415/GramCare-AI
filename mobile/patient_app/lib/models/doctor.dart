/// Public doctor directory entry — mirrors schemas.DoctorPublic
/// (GET /doctors), the same shape the web portal's booking flow uses.
class DoctorPublic {
  final int id;
  final String fullName;
  final String specialty;
  final String? qualifications;
  final int experienceYears;
  final double consultationFee;
  final String? languages;
  final bool isAvailable;

  const DoctorPublic({
    required this.id,
    required this.fullName,
    required this.specialty,
    this.qualifications,
    required this.experienceYears,
    required this.consultationFee,
    this.languages,
    required this.isAvailable,
  });

  factory DoctorPublic.fromJson(Map<String, dynamic> json) => DoctorPublic(
        id: json['id'] as int,
        fullName: json['full_name'] as String? ?? '',
        specialty: json['specialty'] as String? ?? '',
        qualifications: json['qualifications'] as String?,
        experienceYears: json['experience_years'] as int? ?? 0,
        consultationFee: (json['consultation_fee'] as num?)?.toDouble() ?? 0.0,
        languages: json['languages'] as String?,
        isAvailable: json['is_available'] as bool? ?? false,
      );
}

/// Published availability slot — mirrors schemas.SlotResponse
/// (GET /doctors/{id}/slots).
class DoctorSlot {
  final int id;
  final DateTime startTime;
  final DateTime endTime;
  final bool isBooked;

  const DoctorSlot({
    required this.id,
    required this.startTime,
    required this.endTime,
    required this.isBooked,
  });

  factory DoctorSlot.fromJson(Map<String, dynamic> json) => DoctorSlot(
        id: json['id'] as int,
        startTime: DateTime.parse(json['start_time'] as String),
        endTime: DateTime.parse(json['end_time'] as String),
        isBooked: json['is_booked'] as bool? ?? false,
      );
}
