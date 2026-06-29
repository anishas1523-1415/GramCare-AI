import 'package:hive/hive.dart';

part 'health_record.g.dart';

@HiveType(typeId: 0)
class HealthRecord extends HiveObject {
  @HiveField(0)
  late String patientName;

  @HiveField(1)
  late String symptoms;

  @HiveField(2)
  late String aiSeverity;

  @HiveField(3)
  late DateTime timestamp;

  HealthRecord({
    required this.patientName,
    required this.symptoms,
    required this.aiSeverity,
    required this.timestamp,
  });
}
