import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:go_router/go_router.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:provider/provider.dart';

import '../models/health_record.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../services/sync_service.dart';

/// Family Health Wallet — per-member, color-coded record list backed by the
/// encrypted offline box, refreshed from the server when online.
/// Record-type colors implement the planning doc's accessibility rule:
/// "பிரிஸ்கிரிப்ஷனுக்கு ஒரு நிறம், வேக்சினேஷனுக்கு ஒரு நிறம்".
class HealthWalletScreen extends StatefulWidget {
  const HealthWalletScreen({super.key});

  @override
  State<HealthWalletScreen> createState() => _HealthWalletScreenState();
}

const Map<String, (Color, IconData, String)> kRecordTypeStyle = {
  'prescription': (Color(0xFF4F46E5), Icons.receipt_long, 'Prescription'),
  'lab_report': (Color(0xFF0EA5E9), Icons.science, 'Lab Report'),
  'triage_log': (Color(0xFF2DD4BF), Icons.psychology, 'AI Check'),
  'vaccination': (Color(0xFF10B981), Icons.vaccines, 'Vaccination'),
  'scan': (Color(0xFF8B5CF6), Icons.document_scanner, 'Scanned'),
  'note': (Color(0xFF718096), Icons.notes, 'Note'),
};

class _HealthWalletScreenState extends State<HealthWalletScreen> {
  bool _syncing = false;
  final FlutterTts _tts = FlutterTts();

  @override
  void dispose() {
    _tts.stop();
    super.dispose();
  }

  /// "Tap to hear it read aloud" — the planning doc's accessibility feature
  /// for users who cannot read ("ஒவ்வொரு ரெக்கார்டையும் வாய்ஸ் கிளிக் பண்ணி
  /// கேட்டுக்கலாம்").
  Future<void> _speakRecord(HealthRecord record) async {
    final s = context.read<LocaleService>();
    await _tts.setLanguage(s.isTamil ? 'ta-IN' : 'en-IN');
    await _tts.setSpeechRate(0.45);
    await _tts.speak('${record.title ?? record.recordType}. ${record.content}');
  }

  Future<void> _refresh() async {
    setState(() => _syncing = true);
    try {
      final me = await ApiService().client.get('/auth/me');
      final myId = me.data['id'] as int?;
      if (myId != null) await SyncService().fullSync(myId);
    } catch (_) {
      // Offline: at least try to flush the queue.
      await SyncService().pushUnsynced();
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = context.watch<ProfileService>().active;

    return Scaffold(
      backgroundColor: const Color(0xFFE0E5EC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF2D3748)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          active == null ? 'My Health Wallet' : "${active.fullName}'s Wallet",
          style: const TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.bold),
        ),
        actions: [
          IconButton(
            tooltip: 'Sync now',
            icon: _syncing
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.sync, color: Color(0xFF2D3748)),
            onPressed: _syncing ? null : _refresh,
          ),
        ],
      ),
      body: SafeArea(
        child: ValueListenableBuilder(
          valueListenable: Hive.box<HealthRecord>('health_wallet').listenable(),
          builder: (context, Box<HealthRecord> box, _) {
            // Scope records to the selected family member (null = the
            // account owner's own records).
            final records = box.values
                .where((r) => r.familyProfileId == active?.id)
                .toList()
              ..sort((a, b) => b.timestamp.compareTo(a.timestamp));

            if (records.isEmpty) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.folder_open, size: 56, color: Color(0xFF718096)),
                      const SizedBox(height: 12),
                      Text(
                        active == null
                            ? 'No records yet. Run a symptom check or scan a prescription.'
                            : 'No records for ${active.fullName} yet.',
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Color(0xFF718096), fontSize: 16),
                      ),
                    ],
                  ),
                ),
              );
            }

            return ListView.builder(
              padding: const EdgeInsets.all(24),
              itemCount: records.length,
              itemBuilder: (context, index) {
                final record = records[index];
                final (color, icon, label) =
                    kRecordTypeStyle[record.recordType] ?? kRecordTypeStyle['note']!;
                return Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE0E5EC),
                    borderRadius: BorderRadius.circular(16),
                    border: Border(left: BorderSide(color: color, width: 6)),
                    boxShadow: const [
                      BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                      BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(icon, color: color, size: 22),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              label,
                              style: TextStyle(
                                  color: color, fontWeight: FontWeight.bold, fontSize: 12),
                            ),
                          ),
                          const Spacer(),
                          // Voice playback for low-literacy users
                          GestureDetector(
                            onTap: () => _speakRecord(record),
                            child: Icon(Icons.volume_up, size: 22, color: color),
                          ),
                          const SizedBox(width: 10),
                          Icon(
                            record.synced ? Icons.cloud_done : Icons.cloud_upload,
                            size: 18,
                            color: record.synced ? Colors.green : Colors.orange,
                          ),
                        ],
                      ),
                      if (record.title != null && record.title!.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Text(record.title!,
                            style: const TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 17)),
                      ],
                      const SizedBox(height: 8),
                      Text(record.content),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          if (record.doctorName != null) ...[
                            const Icon(Icons.badge, size: 14, color: Colors.grey),
                            const SizedBox(width: 4),
                            Flexible(
                              child: Text(record.doctorName!,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
                            ),
                            const SizedBox(width: 12),
                          ],
                          Text(
                            record.timestamp.toString().substring(0, 16),
                            style: const TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                        ],
                      )
                    ],
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
