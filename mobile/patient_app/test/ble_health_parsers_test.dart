import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/services/ble_health_parsers.dart';

/// Byte-level tests for the Bluetooth SIG health profiles, written against
/// the packet layouts in the SIG specifications rather than against any one
/// device. The "no finger"/"no skin contact" cases matter most: a device
/// reports a reserved NaN code or a zero until it has a real reading, and
/// those must decode to null so they are never stored as a vital sign.
void main() {
  group('Heart Rate Measurement (0x2A37)', () {
    test('reads an 8-bit value', () {
      expect(BleHealthParsers.heartRate([0x00, 72]), 72);
    });

    test('reads a 16-bit little-endian value when flag bit 0 is set', () {
      expect(BleHealthParsers.heartRate([0x01, 0x48, 0x00]), 72);
    });

    test('rejects a physiologically impossible rate', () {
      expect(BleHealthParsers.heartRate([0x01, 0x2C, 0x01]), isNull); // 300 bpm
    });

    test('rejects zero, which means no skin contact', () {
      expect(BleHealthParsers.heartRate([0x00, 0]), isNull);
    });

    test('rejects a packet truncated mid-value', () {
      expect(BleHealthParsers.heartRate([0x01, 0x48]), isNull);
    });
  });

  group('IEEE 11073-20601 SFLOAT', () {
    test('decodes a positive integer', () {
      expect(BleHealthParsers.sfloat(0x0062), 98.0);
    });

    test('decodes a negative exponent without float drift', () {
      expect(BleHealthParsers.sfloat(0xF170), 36.8);
    });

    test('decodes a negative mantissa', () {
      expect(BleHealthParsers.sfloat(0x0FFF), -1.0);
    });

    test('decodes the reserved NaN code to null', () {
      expect(BleHealthParsers.sfloat(0x07FF), isNull);
    });
  });

  group('Pulse Oximeter (0x2A5E / 0x2A5F)', () {
    test('reads SpO2 and pulse rate', () {
      final r = BleHealthParsers.pulseOximeter([0x00, 0x62, 0x00, 0x48, 0x00]);
      expect(r.spo2, 98);
      expect(r.pulse, 72);
    });

    test('drops both values while no finger is detected', () {
      final r = BleHealthParsers.pulseOximeter([0x00, 0xFF, 0x07, 0xFF, 0x07]);
      expect(r.spo2, isNull);
      expect(r.pulse, isNull);
    });

    test('drops a short packet', () {
      final r = BleHealthParsers.pulseOximeter([0x00, 0x62, 0x00]);
      expect(r.spo2, isNull);
      expect(r.pulse, isNull);
    });
  });

  group('Health Thermometer (0x2A1C / 0x2A1E)', () {
    test('decodes a 32-bit FLOAT', () {
      expect(BleHealthParsers.float32(0xFF000170), 36.8);
    });

    test('reads a Celsius measurement', () {
      expect(BleHealthParsers.temperatureCelsius([0x00, 0x70, 0x01, 0x00, 0xFF]), 36.8);
    });

    test('converts a Fahrenheit measurement', () {
      expect(BleHealthParsers.temperatureCelsius([0x01, 0xDA, 0x03, 0x00, 0xFF]), 37.0);
    });

    test('decodes the reserved NaN code to null', () {
      expect(BleHealthParsers.temperatureCelsius([0x00, 0xFF, 0xFF, 0x7F, 0x00]), isNull);
    });

    test('rejects a reading outside any human range', () {
      // 150 C — a sensor fault, not a patient.
      expect(BleHealthParsers.temperatureCelsius([0x00, 0x96, 0x00, 0x00, 0x00]), isNull);
    });
  });
}
