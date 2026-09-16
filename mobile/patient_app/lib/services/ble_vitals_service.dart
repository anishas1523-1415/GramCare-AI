import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import 'ble_health_parsers.dart';

/// The newest value a connected device has reported for each measurement.
/// A heart-rate strap never reports SpO2 and an oximeter never reports
/// temperature, so each field stays null until its own device sends it.
class BleVitalsReading {
  final int? heartRate;
  final int? spo2;
  final double? temperatureC;

  const BleVitalsReading({this.heartRate, this.spo2, this.temperatureC});

  BleVitalsReading merge({int? heartRate, int? spo2, double? temperatureC}) => BleVitalsReading(
        heartRate: heartRate ?? this.heartRate,
        spo2: spo2 ?? this.spo2,
        temperatureC: temperatureC ?? this.temperatureC,
      );
}

enum BleReadiness { ready, unsupported, bluetoothOff }

/// Live vitals from any device that implements the Bluetooth SIG health
/// profiles (Heart Rate, Pulse Oximeter, Health Thermometer) rather than one
/// vendor's private protocol.
class BleVitalsService {
  static final Guid heartRateService = Guid('180D');
  static final Guid pulseOximeterService = Guid('1822');
  static final Guid thermometerService = Guid('1809');
  static final List<Guid> healthServices = [heartRateService, pulseOximeterService, thermometerService];

  static final Guid _heartRate = Guid('2A37');
  static final Guid _plxSpotCheck = Guid('2A5E');
  static final Guid _plxContinuous = Guid('2A5F');
  static final Guid _temperature = Guid('2A1C');
  static final Guid _intermediateTemperature = Guid('2A1E');
  static final Set<Guid> _measurements = {
    _heartRate,
    _plxSpotCheck,
    _plxContinuous,
    _temperature,
    _intermediateTemperature,
  };

  final _readings = StreamController<BleVitalsReading>.broadcast();
  final List<StreamSubscription<List<int>>> _subscriptions = [];
  BluetoothDevice? _device;
  BleVitalsReading _latest = const BleVitalsReading();

  Stream<BleVitalsReading> get readings => _readings.stream;

  Stream<BluetoothConnectionState> get connectionState =>
      _device?.connectionState ?? const Stream<BluetoothConnectionState>.empty();

  Stream<List<ScanResult>> get scanResults => FlutterBluePlus.scanResults;

  Stream<bool> get isScanning => FlutterBluePlus.isScanning;

  static String? nameOf(BluetoothDevice device) {
    if (device.advName.isNotEmpty) return device.advName;
    if (device.platformName.isNotEmpty) return device.platformName;
    return null;
  }

  /// Checks Bluetooth LE support and that the adapter is on. Android can
  /// switch it on after asking the user; iOS cannot.
  Future<BleReadiness> prepare() async {
    if (!await FlutterBluePlus.isSupported) return BleReadiness.unsupported;
    if (await _waitForAdapterOn(const Duration(seconds: 2))) return BleReadiness.ready;
    if (Platform.isAndroid) {
      try {
        await FlutterBluePlus.turnOn();
      } catch (_) {
        // The user declined the system prompt.
      }
      if (await _waitForAdapterOn(const Duration(seconds: 8))) return BleReadiness.ready;
    }
    return BleReadiness.bluetoothOff;
  }

  /// Scans only for devices advertising a health profile. Results arrive on
  /// [scanResults]; the scan stops on its own after [timeout].
  Future<void> startScan({Duration timeout = const Duration(seconds: 12)}) =>
      FlutterBluePlus.startScan(withServices: healthServices, timeout: timeout);

  Future<void> stopScan() => FlutterBluePlus.stopScan();

  /// Connects and subscribes to every standard health measurement the
  /// device exposes. Returns false, after disconnecting, if it exposes none.
  Future<bool> connect(BluetoothDevice device) async {
    await stopScan();
    // FlutterBluePlus is licensed free for personal, educational and
    // nonprofit use. A for-profit deployment must change this to
    // License.commercial and buy a licence (see the package's LICENSE).
    await device.connect(license: License.nonprofit, timeout: const Duration(seconds: 20));
    _device = device;
    _latest = const BleVitalsReading();

    try {
      var subscribed = 0;
      for (final service in await device.discoverServices()) {
        for (final c in service.characteristics) {
          if (!_measurements.contains(c.uuid)) continue;
          if (!c.properties.notify && !c.properties.indicate) continue;
          final sub = c.onValueReceived.listen((bytes) => _onValue(c.uuid, bytes));
          device.cancelWhenDisconnected(sub);
          _subscriptions.add(sub);
          await c.setNotifyValue(true);
          subscribed++;
        }
      }
      if (subscribed == 0) {
        await disconnect();
        return false;
      }
      return true;
    } catch (_) {
      await disconnect();
      rethrow;
    }
  }

  Future<void> disconnect() async {
    for (final sub in _subscriptions) {
      await sub.cancel();
    }
    _subscriptions.clear();
    final device = _device;
    _device = null;
    if (device != null) {
      try {
        await device.disconnect();
      } catch (_) {
        // Already gone: out of range or switched off.
      }
    }
  }

  Future<void> dispose() async {
    try {
      await stopScan();
    } catch (_) {
      // Nothing to stop.
    }
    await disconnect();
    await _readings.close();
  }

  void _onValue(Guid uuid, List<int> bytes) {
    int? heartRate;
    int? spo2;
    double? temperatureC;
    if (uuid == _heartRate) {
      heartRate = BleHealthParsers.heartRate(bytes);
    } else if (uuid == _plxSpotCheck || uuid == _plxContinuous) {
      final plx = BleHealthParsers.pulseOximeter(bytes);
      spo2 = plx.spo2;
      heartRate = plx.pulse;
    } else if (uuid == _temperature || uuid == _intermediateTemperature) {
      temperatureC = BleHealthParsers.temperatureCelsius(bytes);
    }
    if (heartRate == null && spo2 == null && temperatureC == null) return;
    _latest = _latest.merge(heartRate: heartRate, spo2: spo2, temperatureC: temperatureC);
    if (!_readings.isClosed) _readings.add(_latest);
  }

  Future<bool> _waitForAdapterOn(Duration timeout) async {
    final done = Completer<bool>();
    final sub = FlutterBluePlus.adapterState.listen((state) {
      if (state == BluetoothAdapterState.on && !done.isCompleted) done.complete(true);
    });
    final timer = Timer(timeout, () {
      if (!done.isCompleted) done.complete(false);
    });
    final on = await done.future;
    timer.cancel();
    await sub.cancel();
    return on;
  }
}
