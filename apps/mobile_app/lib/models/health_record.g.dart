// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'health_record.dart';

// **************************************************************************
// TypeAdapterGenerator
// **************************************************************************

class HealthRecordAdapter extends TypeAdapter<HealthRecord> {
  @override
  final int typeId = 0;

  @override
  HealthRecord read(BinaryReader reader) {
    final numOfFields = reader.readByte();
    final fields = <int, dynamic>{
      for (int i = 0; i < numOfFields; i++) reader.readByte(): reader.read(),
    };
    return HealthRecord(
      patientName: fields[0] as String,
      symptoms: fields[1] as String,
      aiSeverity: fields[2] as String,
      timestamp: fields[3] as DateTime,
    );
  }

  @override
  void write(BinaryWriter writer, HealthRecord obj) {
    writer
      ..writeByte(4)
      ..writeByte(0)
      ..write(obj.patientName)
      ..writeByte(1)
      ..write(obj.symptoms)
      ..writeByte(2)
      ..write(obj.aiSeverity)
      ..writeByte(3)
      ..write(obj.timestamp);
  }

  @override
  int get hashCode => typeId.hashCode;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is HealthRecordAdapter &&
          runtimeType == other.runtimeType &&
          typeId == other.typeId;
}
