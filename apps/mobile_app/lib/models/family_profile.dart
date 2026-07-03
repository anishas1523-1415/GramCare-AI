/// Family member profile — mirrors backend FamilyProfileResponse.
class FamilyProfile {
  final int id;
  final String fullName;
  final String relation;
  final int age;
  final String gender;
  final String? bloodGroup;
  final String? allergies;
  final String? chronicConditions;
  final String? photoUrl;
  final String? colorTag;

  const FamilyProfile({
    required this.id,
    required this.fullName,
    required this.relation,
    required this.age,
    required this.gender,
    this.bloodGroup,
    this.allergies,
    this.chronicConditions,
    this.photoUrl,
    this.colorTag,
  });

  factory FamilyProfile.fromJson(Map<String, dynamic> json) => FamilyProfile(
        id: json['id'] as int,
        fullName: json['full_name'] as String? ?? '',
        relation: json['relation'] as String? ?? '',
        age: json['age'] as int? ?? 0,
        gender: json['gender'] as String? ?? '',
        bloodGroup: json['blood_group'] as String?,
        allergies: json['allergies'] as String?,
        chronicConditions: json['chronic_conditions'] as String?,
        photoUrl: json['photo_url'] as String?,
        colorTag: json['color_tag'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'full_name': fullName,
        'relation': relation,
        'age': age,
        'gender': gender,
        'blood_group': bloodGroup,
        'allergies': allergies,
        'chronic_conditions': chronicConditions,
        'photo_url': photoUrl,
        'color_tag': colorTag,
      };

  /// Initials used for the big avatar button (photo-as-button planned;
  /// initials are the fallback until a photo is set).
  String get initials {
    final parts = fullName.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts.first.substring(0, 1) + parts.last.substring(0, 1)).toUpperCase();
  }
}
