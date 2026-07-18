/// Mirrors backend schemas.DoctorSelfResponse (GET/PUT /api/v1/doctors/me)
/// — previously only mirrored the public-facing subset (DoctorPublic), so
/// verification_status/license fields the backend already returned were
/// silently dropped and no screen could show a doctor their own approval
/// state.
class DoctorProfile {
  final int id;
  final String fullName;
  final String specialty;
  final String? qualifications;
  final int experienceYears;
  final double consultationFee;
  final String? languages;
  final bool isAvailable;
  final String? photoUrl;
  final String? licenseNumber;
  final String? licenseDocumentUrl;
  final String? serviceHours;
  final String verificationStatus;
  final String? rejectionReason;

  bool get isApproved => verificationStatus == 'APPROVED';
  bool get isPending => verificationStatus == 'PENDING';
  bool get isRejected => verificationStatus == 'REJECTED';

  DoctorProfile({
    required this.id,
    required this.fullName,
    required this.specialty,
    this.qualifications,
    required this.experienceYears,
    required this.consultationFee,
    this.languages,
    required this.isAvailable,
    this.photoUrl,
    this.licenseNumber,
    this.licenseDocumentUrl,
    this.serviceHours,
    required this.verificationStatus,
    this.rejectionReason,
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
        photoUrl: json['photo_url'] as String?,
        licenseNumber: json['license_number'] as String?,
        licenseDocumentUrl: json['license_document_url'] as String?,
        serviceHours: json['service_hours'] as String?,
        // Accounts registered before the verification workflow existed
        // have no status of their own opinion server-side beyond the
        // backfilled default, but a missing/unrecognized value here should
        // never read as "approved" — default defensively to PENDING.
        verificationStatus: json['verification_status'] as String? ?? 'PENDING',
        rejectionReason: json['rejection_reason'] as String?,
      );
}
