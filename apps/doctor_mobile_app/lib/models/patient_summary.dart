/// Mirrors backend modules/ai_assist/router.py's ActiveMedicine + PatientSummary.
class ActiveMedicine {
  final String name;
  final String dosage;
  final String frequency;
  final String started;
  final int daysRemaining;

  ActiveMedicine({
    required this.name,
    required this.dosage,
    required this.frequency,
    required this.started,
    required this.daysRemaining,
  });

  factory ActiveMedicine.fromJson(Map<String, dynamic> json) => ActiveMedicine(
        name: json['name'] as String,
        dosage: json['dosage'] as String,
        frequency: json['frequency'] as String,
        started: json['started'] as String,
        daysRemaining: json['days_remaining'] as int,
      );
}

class PatientSummary {
  final int patientId;
  final String patientName;
  final int? ageHint;
  final String riskFlag; // LOW | MODERATE | HIGH
  final String summaryText;
  final List<ActiveMedicine> activeMedicines;
  final List<String> recentConditions;
  final Map<String, dynamic>? latestVitals;
  final String? chronicConditions;
  final String? allergies;
  final String generatedBy;

  PatientSummary({
    required this.patientId,
    required this.patientName,
    this.ageHint,
    required this.riskFlag,
    required this.summaryText,
    required this.activeMedicines,
    required this.recentConditions,
    this.latestVitals,
    this.chronicConditions,
    this.allergies,
    required this.generatedBy,
  });

  factory PatientSummary.fromJson(Map<String, dynamic> json) => PatientSummary(
        patientId: json['patient_id'] as int,
        patientName: json['patient_name'] as String,
        ageHint: json['age_hint'] as int?,
        riskFlag: json['risk_flag'] as String,
        summaryText: json['summary_text'] as String,
        activeMedicines: (json['active_medicines'] as List<dynamic>? ?? [])
            .map((e) => ActiveMedicine.fromJson(e as Map<String, dynamic>))
            .toList(),
        recentConditions: (json['recent_conditions'] as List<dynamic>? ?? [])
            .map((e) => e as String)
            .toList(),
        latestVitals: json['latest_vitals'] as Map<String, dynamic>?,
        chronicConditions: json['chronic_conditions'] as String?,
        allergies: json['allergies'] as String?,
        generatedBy: json['generated_by'] as String,
      );
}
