/// Mirrors backend schemas.DoctorPublic (GET/PUT /api/v1/doctors/me).
class DoctorProfile {
  final int id;
  final String fullName;
  final String specialty;
  final String? qualifications;
  final int experienceYears;
  final double consultationFee;
  final String? languages;
  final bool isAvailable;

  DoctorProfile({
    required this.id,
    required this.fullName,
    required this.specialty,
    this.qualifications,
    required this.experienceYears,
    required this.consultationFee,
    this.languages,
    required this.isAvailable,
  });

  factory DoctorProfile.fromJson(Map<String, dynamic> json) => DoctorProfile(
        id: json['id'] as int,
        fullName: json['full_name'] as String,
        specialty: json['specialty'] as String,
        qualifications: json['qualifications'] as String?,
        experienceYears: json['experience_years'] as int? ?? 0,
        consultationFee: (json['consultation_fee'] as num?)?.toDouble() ?? 0,
        languages: json['languages'] as String?,
        isAvailable: json['is_available'] as bool? ?? false,
      );
}
