import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/doctor_session.dart';
import '../theme/app_theme.dart';

class _Slot {
  final int id;
  final DateTime start;
  final DateTime end;
  final bool isBooked;

  _Slot({required this.id, required this.start, required this.end, required this.isBooked});

  factory _Slot.fromJson(Map<String, dynamic> json) => _Slot(
        id: json['id'] as int,
        start: DateTime.parse(json['start_time'] as String),
        end: DateTime.parse(json['end_time'] as String),
        isBooked: json['is_booked'] as bool? ?? false,
      );
}

/// My Schedule / Slots — GET /doctors/{id}/slots?include_booked=true,
/// POST /doctors/me/slots, DELETE /doctors/me/slots/{id}, plus toggling
/// is_available via PUT /doctors/me.
class ScheduleScreen extends StatefulWidget {
  const ScheduleScreen({super.key});

  @override
  State<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends State<ScheduleScreen> {
  List<_Slot> _slots = [];
  bool _loading = true;
  String? _error;
  bool _togglingAvailability = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadSlots());
  }

  Future<void> _loadSlots() async {
    final doctorId = context.read<DoctorSession>().doctorId;
    if (doctorId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await ApiService()
          .client
          .get('/doctors/$doctorId/slots', queryParameters: {'include_booked': true});
      final list = (res.data as List).map((j) => _Slot.fromJson(j as Map<String, dynamic>)).toList()
        ..sort((a, b) => a.start.compareTo(b.start));
      setState(() {
        _slots = list;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = context.mounted ? context.read<LocaleService>().t('error_generic') : null;
      });
    }
  }

  Future<void> _addSlot() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 90)),
    );
    if (date == null || !mounted) return;

    final startTime = await showTimePicker(context: context, initialTime: TimeOfDay.now());
    if (startTime == null || !mounted) return;

    final start = DateTime(date.year, date.month, date.day, startTime.hour, startTime.minute);
    final end = start.add(const Duration(minutes: 30));

    try {
      await ApiService().client.post('/doctors/me/slots', data: [
        {
          'start_time': start.toUtc().toIso8601String(),
          'end_time': end.toUtc().toIso8601String(),
        }
      ]);
      await _loadSlots();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.read<LocaleService>().t('error_generic'))),
      );
    }
  }

  Future<void> _deleteSlot(_Slot slot, LocaleService locale) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(locale.t('delete_slot_confirm')),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(locale.t('cancel'))),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: Text(locale.t('delete'))),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await ApiService().client.delete('/doctors/me/slots/${slot.id}');
      await _loadSlots();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(locale.t('error_generic'))),
      );
    }
  }

  Future<void> _toggleAvailability(bool value) async {
    setState(() => _togglingAvailability = true);
    try {
      await context.read<DoctorSession>().updateProfile({'is_available': value});
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.read<LocaleService>().t('error_generic'))),
      );
    }
    setState(() => _togglingAvailability = false);
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final session = context.watch<DoctorSession>();
    final profile = session.profile;

    return Scaffold(
      appBar: AppBar(title: Text(locale.t('my_schedule'))),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addSlot,
        icon: const Icon(Icons.add),
        label: Text(locale.t('add_slot')),
      ),
      body: RefreshIndicator(
        onRefresh: _loadSlots,
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            if (profile != null)
              Card(
                child: SwitchListTile(
                  title: Text(locale.t('available_for_consultation')),
                  value: profile.isAvailable,
                  activeThumbColor: AppTheme.primaryBlue,
                  onChanged: _togglingAvailability ? null : _toggleAvailability,
                ),
              ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Text(locale.t('availability_slots'), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            ),
            const SizedBox(height: 8),
            if (_loading)
              const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator()))
            else if (_error != null)
              Center(
                child: Column(
                  children: [
                    Padding(padding: const EdgeInsets.all(16), child: Text(_error!)),
                    OutlinedButton(onPressed: _loadSlots, child: Text(locale.t('retry'))),
                  ],
                ),
              )
            else if (_slots.isEmpty)
              Padding(
                padding: const EdgeInsets.all(32),
                child: Center(child: Text(locale.t('no_slots'), style: const TextStyle(color: Colors.black54))),
              )
            else
              ..._slots.map((slot) => _slotTile(slot, locale)),
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }

  Widget _slotTile(_Slot slot, LocaleService locale) {
    final dateFmt = DateFormat('EEE, MMM d');
    final timeFmt = DateFormat('hh:mm a');
    return Card(
      child: ListTile(
        leading: Icon(
          slot.isBooked ? Icons.event_busy : Icons.event_available,
          color: slot.isBooked ? AppTheme.confirmedBlue : AppTheme.completedGreen,
        ),
        title: Text('${dateFmt.format(slot.start.toLocal())}  ${timeFmt.format(slot.start.toLocal())} - ${timeFmt.format(slot.end.toLocal())}'),
        subtitle: Text(slot.isBooked ? locale.t('slot_booked') : locale.t('slot_open')),
        trailing: slot.isBooked
            ? null
            : IconButton(
                icon: const Icon(Icons.delete_outline, color: AppTheme.cancelledRed),
                tooltip: locale.t('remove'),
                onPressed: () => _deleteSlot(slot, locale),
              ),
      ),
    );
  }
}
