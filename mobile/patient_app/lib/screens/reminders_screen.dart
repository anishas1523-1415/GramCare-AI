import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../services/reminder_service.dart';
import '../theme/neumorphic_colors.dart';

/// Medicine Reminders — real implementation (previously a hardcoded static
/// list with no persistence and no notifications). Reminders are scoped to
/// the active family member, persist offline in Hive, fire daily local
/// notifications, and can be auto-imported from wallet prescriptions
/// ("பிரஸ்கிரிப்ஷன் அப்லோட் செஞ்சா, ஆப் ஆட்டோமேட்டிக்கா எல்லா
/// டீடைல்ஸையும் ஃபில் பண்ணிடும்" — planning doc).
class RemindersScreen extends StatefulWidget {
  const RemindersScreen({super.key});

  @override
  State<RemindersScreen> createState() => _RemindersScreenState();
}

class _RemindersScreenState extends State<RemindersScreen> {
  // Module theme: reminder red/amber (planning doc per-module identity)
  static const _theme = Color(0xFFEF4444);

  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  bool _importing = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final active = context.read<ProfileService>().active;
    final items = await ReminderService().reminders(familyProfileId: active?.id);
    if (mounted) {
      setState(() {
        _items = items;
        _loading = false;
      });
    }
  }

  Future<void> _importFromPrescriptions() async {
    setState(() => _importing = true);
    final active = context.read<ProfileService>().active;
    final added =
        await ReminderService().importFromPrescriptions(familyProfileId: active?.id);
    await _load();
    if (mounted) {
      setState(() => _importing = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(added > 0
            ? '$added reminder(s) created from prescriptions'
            : 'No new medicines found in prescriptions'),
        backgroundColor: added > 0 ? const Color(0xFF10B981) : Colors.grey,
      ));
    }
  }

  Future<void> _addManual() async {
    final s = context.read<LocaleService>();
    final medCtl = TextEditingController();
    final notesCtl = TextEditingController();
    TimeOfDay time = const TimeOfDay(hour: 8, minute: 0);

    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx2, setSt) => AlertDialog(
          title: Text(s.t('medicine_reminders')),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                  controller: medCtl,
                  decoration: const InputDecoration(labelText: 'Medicine')),
              TextField(
                  controller: notesCtl,
                  decoration: const InputDecoration(labelText: 'Instructions (optional)')),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                icon: const Icon(Icons.access_time),
                label: Text(time.format(ctx2)),
                onPressed: () async {
                  final picked =
                      await showTimePicker(context: ctx2, initialTime: time);
                  if (picked != null) setSt(() => time = picked);
                },
              ),
            ],
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: Text(s.t('cancel'))),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: Text(s.t('save'))),
          ],
        ),
      ),
    );

    if (saved == true && medCtl.text.trim().isNotEmpty && mounted) {
      final active = context.read<ProfileService>().active;
      await ReminderService().addReminder(
        medicine: medCtl.text.trim(),
        hour: time.hour,
        minute: time.minute,
        instructions: notesCtl.text.trim(),
        familyProfileId: active?.id,
      );
      await _load();
    }
  }

  String _fmt(int h, int m) {
    final period = h >= 12 ? 'PM' : 'AM';
    final hh = h % 12 == 0 ? 12 : h % 12;
    return '${hh.toString()}:${m.toString().padLeft(2, '0')} $period';
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<LocaleService>();
    final active = context.watch<ProfileService>().active;
    final neu = Theme.of(context).extension<NeumorphicColors>()!;

    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: neu.foreground),
          tooltip: s.t('back'),
          onPressed: () => context.pop(),
        ),
        title: Text(
          active == null
              ? s.t('medicine_reminders')
              : '${active.fullName} • ${s.t('medicine_reminders')}',
          style: TextStyle(
              color: neu.foreground, fontWeight: FontWeight.bold, fontSize: 17),
        ),
        actions: [
          IconButton(
            tooltip: 'Import from prescriptions',
            onPressed: _importing ? null : _importFromPrescriptions,
            icon: _importing
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.auto_awesome, color: _theme),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addManual,
        backgroundColor: _theme,
        child: const Icon(Icons.add_alarm, color: Colors.white),
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _items.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.notifications_none,
                              size: 56, color: neu.foregroundMuted),
                          const SizedBox(height: 12),
                          Text(
                            'No reminders yet.\nTap ✨ to create them from your prescriptions,\nor + to add one manually.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: neu.foregroundMuted, fontSize: 15),
                          ),
                        ],
                      ),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(24),
                    itemCount: _items.length,
                    itemBuilder: (context, i) {
                      final r = _items[i];
                      final taken = ReminderService().takenToday(r);
                      return Container(
                        margin: const EdgeInsets.only(bottom: 14),
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: neu.background,
                          borderRadius: BorderRadius.circular(16),
                          border: Border(
                            left: BorderSide(
                                color: taken ? const Color(0xFF10B981) : _theme,
                                width: 6),
                          ),
                          boxShadow: [
                            BoxShadow(
                                color: neu.shadowDark,
                                offset: const Offset(4, 4),
                                blurRadius: 8),
                            BoxShadow(
                                color: neu.shadowLight,
                                offset: const Offset(-4, -4),
                                blurRadius: 8),
                          ],
                        ),
                        child: Row(
                          children: [
                            // Tap-to-mark-taken (big touch target)
                            GestureDetector(
                              onTap: () async {
                                await ReminderService()
                                    .markTaken(r['id'] as int, taken: !taken);
                                await _load();
                              },
                              child: Icon(
                                taken
                                    ? Icons.check_circle
                                    : Icons.radio_button_unchecked,
                                size: 34,
                                color: taken
                                    ? const Color(0xFF10B981)
                                    : neu.foregroundMuted,
                              ),
                            ),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    r['medicine'] as String,
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 16,
                                      decoration: taken
                                          ? TextDecoration.lineThrough
                                          : null,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    '${_fmt(r['hour'] as int, r['minute'] as int)}'
                                    '${(r['instructions'] as String? ?? '').isNotEmpty ? ' • ${r['instructions']}' : ''}',
                                    style: TextStyle(
                                        fontSize: 13, color: neu.foregroundMuted),
                                  ),
                                ],
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.delete_outline,
                                  color: Colors.redAccent, size: 22),
                              tooltip: s.t('delete'),
                              onPressed: () async {
                                await ReminderService()
                                    .removeReminder(r['id'] as int);
                                await _load();
                              },
                            ),
                          ],
                        ),
                      );
                    },
                  ),
      ),
    );
  }
}
