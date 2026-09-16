import 'dart:math' as math;

/// Decoders for the Bluetooth SIG standard health profiles the app reads:
/// Heart Rate (0x180D), Pulse Oximeter (0x1822) and Health Thermometer
/// (0x1809). Free of any Bluetooth plugin types so they can be tested with
/// plain byte lists.
///
/// Out-of-range results decode to null rather than a number: oximeters and
/// straps emit placeholder values (0, or the reserved NaN codes) until a
/// finger or skin contact is detected, and those must never be saved as a
/// measurement.
class BleHealthParsers {
  BleHealthParsers._();

  /// Heart Rate Measurement (0x2A37). Bit 0 of the flags byte selects an
  /// 8-bit or 16-bit little-endian value.
  static int? heartRate(List<int> data) {
    if (data.length < 2) return null;
    final is16Bit = (data[0] & 0x01) == 1;
    if (is16Bit && data.length < 3) return null;
    final bpm = is16Bit ? data[1] | (data[2] << 8) : data[1];
    return _inRange(bpm.toDouble(), 20, 250)?.round();
  }

  /// PLX Spot-check (0x2A5E) and Continuous (0x2A5F) measurements both open
  /// with a flags byte followed by SpO2 then pulse rate, each an SFLOAT.
  static ({int? spo2, int? pulse}) pulseOximeter(List<int> data) {
    if (data.length < 5) return (spo2: null, pulse: null);
    final spo2 = sfloat(data[1] | (data[2] << 8));
    final pulse = sfloat(data[3] | (data[4] << 8));
    return (
      spo2: _inRange(spo2, 50, 100)?.round(),
      pulse: _inRange(pulse, 20, 250)?.round(),
    );
  }

  /// Temperature Measurement (0x2A1C) and Intermediate Temperature
  /// (0x2A1E): flags (bit 0 set = Fahrenheit) then a 32-bit FLOAT.
  /// Always returns Celsius.
  static double? temperatureCelsius(List<int> data) {
    if (data.length < 5) return null;
    final fahrenheit = (data[0] & 0x01) == 1;
    final raw = data[1] | (data[2] << 8) | (data[3] << 16) | (data[4] << 24);
    final value = float32(raw);
    if (value == null) return null;
    final celsius = fahrenheit ? (value - 32) * 5 / 9 : value;
    return _inRange(celsius, 30, 44);
  }

  /// IEEE 11073-20601 16-bit SFLOAT: 4-bit signed exponent, 12-bit signed
  /// mantissa. The reserved codes (NaN, NRes, +INF, -INF, reserved) decode
  /// to null.
  static double? sfloat(int raw) {
    raw &= 0xFFFF;
    const reserved = {0x07FF, 0x0800, 0x07FE, 0x0802, 0x0801};
    if (reserved.contains(raw)) return null;
    var mantissa = raw & 0x0FFF;
    var exponent = raw >> 12;
    if (mantissa >= 0x0800) mantissa -= 0x1000;
    if (exponent >= 0x8) exponent -= 0x10;
    return _scale(mantissa, exponent);
  }

  /// IEEE 11073-20601 32-bit FLOAT: 8-bit signed exponent, 24-bit signed
  /// mantissa. The reserved mantissa codes decode to null.
  static double? float32(int raw) {
    raw &= 0xFFFFFFFF;
    var mantissa = raw & 0x00FFFFFF;
    const reserved = {0x7FFFFF, 0x800000, 0x7FFFFE, 0x800002, 0x800001};
    if (reserved.contains(mantissa)) return null;
    var exponent = (raw >> 24) & 0xFF;
    if (mantissa >= 0x800000) mantissa -= 0x1000000;
    if (exponent >= 0x80) exponent -= 0x100;
    return _scale(mantissa, exponent);
  }

  // Dividing for negative exponents keeps results like 36.8 exact, where
  // multiplying by 0.1 would give 36.800000000000004.
  static double _scale(int mantissa, int exponent) => exponent >= 0
      ? (mantissa * math.pow(10, exponent)).toDouble()
      : mantissa / math.pow(10, -exponent);

  static double? _inRange(double? v, double min, double max) =>
      (v == null || v.isNaN || v < min || v > max) ? null : v;
}
