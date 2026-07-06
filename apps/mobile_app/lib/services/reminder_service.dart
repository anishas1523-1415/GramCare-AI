import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../models/health_record.dart';
import 'firebase_notification_service.dart';
import 'sync_service.dart';

/// Medicine reminders — the planning doc's Medication Management module
/// ("குறிப்பிட்ட நேரம் வந்ததும், ஆப் அவங்களுக்கு அலர்ட் நோட்டிபிகேஷன்
/// காட்டும்"), previously a hardcoded static list.
///
/// - Reminders derive automatically from prescription records in the Health
///   Wallet: "Paracetamol 500mg (1-0-1)" → morning + night doses. Users can
///   also add/remove reminders manually and tick doses as taken.
/// - Persisted in Hive (offline-first, like everything else).
/// - Daily local notifications via the SAME FlutterLocalNotificationsPlugin
///   instance FCM uses (no duplicate plugin/channels). Inexact scheduling —
///   avoids Android 12+'s SCHEDULE_EXACT_ALARM permission wall; ±minutes is
///   fine for medication reminders.
///
/// Timezone note: repeats are anchored with tz.TZDateTime built via
/// duration arithmetic from "now", then matched on time-of-day. India (the
/// launch region) has no DST, so the wall-clock anchor stays correct
/// year-round without needing a native-timezone lookup plugin.
class ReminderService extends ChangeNotifier {
  static final ReminderService _instance = ReminderService._internal();
  factory ReminderService() => _instance;
  ReminderService._internal();

  static const _boxName = 'medicine_reminders';
  bool _tzReady = false;

  // Dose-slot times for the Indian "1-0-1" style frequency notation:
  // morning-noon-night.
  static const _slotTimes = [(8, 0), (14, 0), (20, 0)];
  static const _slotNames = ['Morning', 'Afternoon', 'Night'];

  Future<Box> _box() => Hive.openBox(_boxName);

  void _ensureTz() {
    if (_tzReady) return;
    tzdata.initializeTimeZones();
    _tzReady = true;
  }

  // ---------------------------------------------------------------- read --

  Future<List<Map<String, dynamic>>> reminders({int? familyProfileId}) async {
    final box = await _box();
    return box.values
        .map((e) => Map<String, dynamic>.from(e as Map))
        .where((r) => r['family_profile_id'] == familyProfileId)
        .toList()
      ..sort((a, b) => ((a['hour'] as int) * 60 + (a['minute'] as int))
          .compareTo((b['hour'] as int) * 60 + (b['minute'] as int)));
  }

  String _todayKey() {
    final now = DateTime.now();
    return '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
  }

  bool takenToday(Map<String, dynamic> reminder) =>
      List<String>.from(reminder['taken_dates'] as List? ?? const [])
          .contains(_todayKey());

  // --------------------------------------------------------------- write --

  Future<void> addReminder({
    required String medicine,
    required int hour,
    required int minute,
    String? instructions,
    int? familyProfileId,
  }) async {
    final box = await _box();
    final id = DateTime.now().millisecondsSinceEpoch % 0x7FFFFFFF;
    await box.put(id.toString(), {
      'id': id,
      'medicine': medicine,
      'hour': hour,
      'minute': minute,
      'instructions': instructions ?? '',
      'family_profile_id': familyProfileId,
      'taken_dates': <String>[],
    });
    await _schedule(id, medicine, hour, minute, instructions);
    notifyListeners();
  }

  Future<void> removeReminder(int id) async {
    final box = await _box();
    await box.delete(id.toString());
    await FirebaseNotificationService().localNotifications.cancel(id);
    notifyListeners();
  }

  Future<void> markTaken(int id, {bool taken = true}) async {
    final box = await _box();
    final r = Map<String, dynamic>.from(box.get(id.toString()) as Map);
    final dates = List<String>.from(r['taken_dates'] as List? ?? const []);
    final today = _todayKey();
    taken ? (dates.contains(today) ? null : dates.add(today)) : dates.remove(today);
    r['taken_dates'] = dates;
    await box.put(id.toString(), r);
    notifyListeners();
  }

  // ------------------------------------------------- prescription import --

  /// Scan wallet prescription records and create reminders for medicines
  /// that don't have one yet. Returns how many were added.
  /// Parses the Indian "1-0-1" dose notation from record content; medicines
  /// without a recognizable pattern default to a single morning dose.
  Future<int> importFromPrescriptions({int? familyProfileId}) async {
    final wallet = await Hive.openBox<HealthRecord>(SyncService.walletBoxName);
    final box = await _box();
    final existing = box.values
        .map((e) => (Map<String, dynamic>.from(e as Map))['medicine'] as String)
        .map((m) => m.toLowerCase())
        .toSet();

    int added = 0;
    for (final record in wallet.values) {
      if (record.recordType != 'prescription') continue;
      if (record.familyProfileId != familyProfileId) continue;

      for (final med in _parseMedicines(record.content)) {
        if (existing.contains(med.name.toLowerCase())) continue;
        existing.add(med.name.toLowerCase());
        for (var slot = 0; slot < 3; slot++) {
          if (!med.slots[slot]) continue;
          final (h, m) = _slotTimes[slot];
          await addReminder(
            medicine: med.name,
            hour: h,
            minute: m,
            instructions: '${_slotNames[slot]} dose',
            familyProfileId: familyProfileId,
          );
          added++;
        }
      }
    }
    return added;
  }

  static final _medLineRe = RegExp(
      r'([A-Za-z][A-Za-z0-9 .+%-]{2,40}?)\s*\((\d)\s*-\s*(\d)\s*-\s*(\d)\)');

  List<_ParsedMedicine> _parseMedicines(String content) {
    final results = <_ParsedMedicine>[];
    for (final m in _medLineRe.allMatches(content)) {
      results.add(_ParsedMedicine(
        m.group(1)!.trim(),
        [m.group(2) != '0', m.group(3) != '0', m.group(4) != '0'],
      ));
    }
    if (results.isEmpty && content.contains('Medicines:')) {
      // No dose pattern — take names from the "Medicines:" segment, default
      // to a single morning dose.
      final segment = content.split('Medicines:')[1].split('\n').first;
      for (final raw in segment.split(RegExp('[;,]'))) {
        final name = raw.replaceAll(RegExp(r'\|.*$'), '').trim();
        if (name.length >= 3 && name.length <= 60) {
          results.add(_ParsedMedicine(name, [true, false, false]));
        }
      }
    }
    return results;
  }

  // ------------------------------------------------------------ schedule --

  Future<void> _schedule(
      int id, String medicine, int hour, int minute, String? instructions) async {
    try {
      _ensureTz();
      final now = DateTime.now();
      var first = DateTime(now.year, now.month, now.day, hour, minute);
      if (!first.isAfter(now)) first = first.add(const Duration(days: 1));
      // Anchor as a TZDateTime offset from the current instant (see class
      // docs for why this is DST-safe for the IST launch region).
      final anchor = tz.TZDateTime.now(tz.local).add(first.difference(now));

      await FirebaseNotificationService().localNotifications.zonedSchedule(
        id,
        'மருந்து நேரம் • Medicine time',
        '$medicine${(instructions?.isNotEmpty ?? false) ? ' — $instructions' : ''}',
        anchor,
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'gramcare_appointments_channel',
            'GramCare Appointments',
            channelDescription: 'Appointment reminders and confirmations.',
            icon: '@mipmap/ic_launcher',
            importance: Importance.defaultImportance,
          ),
          iOS: DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        matchDateTimeComponents: DateTimeComponents.time, // repeat daily
        payload: '{"type":"appointment_reminder"}',
      );
    } catch (e) {
      // Scheduling failure must never break reminder CRUD (e.g. running on
      // a platform without notification support in tests).
      debugPrint('Reminder scheduling failed (non-fatal): $e');
    }
  }
}

class _ParsedMedicine {
  final String name;
  final List<bool> slots; // [morning, afternoon, night]
  const _ParsedMedicine(this.name, this.slots);
}
