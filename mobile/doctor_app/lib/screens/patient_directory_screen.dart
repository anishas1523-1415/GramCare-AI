import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';

/// Patient directory — every patient this doctor has records for, most
/// recently seen first.
///
/// Mirrors /doctor/directory on the web. The dashboard queue only shows
/// today's appointments, so without this there was no way on the phone to
/// reach a patient the doctor has treated before but who is not currently
/// booked in.
///
/// The backend has no "list my patients" endpoint; GET /ehr/records returns
/// the doctor-visible record feed, which is grouped by patient here — the
/// same approach the web page takes.
class PatientDirectoryScreen extends StatefulWidget {
  const PatientDirectoryScreen({super.key});

  @override
  State<PatientDirectoryScreen> createState() => _PatientDirectoryScreenState();
}

class _DirectoryEntry {
  final int patientId;
  final DateTime? lastVisit;
  final String lastTitle;
  final String lastType;
  int recordCount;

  _DirectoryEntry({
    required this.patientId,
    required this.lastVisit,
    required this.lastTitle,
    required this.lastType,
  }) : recordCount = 1;
}

class _PatientDirectoryScreenState extends State<PatientDirectoryScreen> {
  final _search = TextEditingController();
  List<_DirectoryEntry> _entries = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await ApiService().client.get('/ehr/records');
      final byPatient = <int, _DirectoryEntry>{};
      for (final raw in (res.data as List)) {
        final r = Map<String, dynamic>.from(raw as Map);
        final pid = r['patient_id'] as int;
        final existing = byPatient[pid];
        if (existing != null) {
          existing.recordCount += 1;
          continue;
        }
        final content = (r['content'] as String? ?? '');
        byPatient[pid] = _DirectoryEntry(
          patientId: pid,
          lastVisit: DateTime.tryParse(
              (r['record_date'] ?? r['created_at'] ?? '') as String),
          lastTitle: (r['title'] as String?)?.isNotEmpty == true
              ? r['title'] as String
              : (content.length > 80 ? content.substring(0, 80) : content),
          lastType: r['record_type'] as String? ?? '',
        );
      }
      final list = byPatient.values.toList()
        ..sort((a, b) => (b.lastVisit ?? DateTime(1970)).compareTo(a.lastVisit ?? DateTime(1970)));
      if (!mounted) return;
      setState(() {
        _entries = list;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('directory_load_failed');
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final q = _search.text.trim().toLowerCase();
    final filtered = q.isEmpty
        ? _entries
        : _entries
            .where((e) =>
                e.patientId.toString().contains(q) || e.lastTitle.toLowerCase().contains(q))
            .toList();
    final dateFmt = DateFormat('d MMM yyyy');

    return Scaffold(
      appBar: AppBar(title: Text(locale.t('patient_directory'))),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                if (_error != null)
                  Container(
                    width: double.infinity,
                    color: AppTheme.criticalRed.withValues(alpha: 0.1),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    child: Text(_error!,
                        style: const TextStyle(
                            color: AppTheme.criticalRed, fontWeight: FontWeight.w600)),
                  ),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: TextField(
                    controller: _search,
                    onChanged: (_) => setState(() {}),
                    decoration: InputDecoration(
                      hintText: locale.t('directory_search_hint'),
                      prefixIcon: const Icon(Icons.search),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
                Expanded(
                  child: filtered.isEmpty
                      ? RefreshIndicator(
                          onRefresh: _load,
                          child: ListView(children: [
                            const SizedBox(height: 120),
                            Center(child: Text(locale.t('directory_empty'))),
                          ]),
                        )
                      : RefreshIndicator(
                          onRefresh: _load,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(12, 0, 12, 24),
                            itemCount: filtered.length,
                            itemBuilder: (context, i) {
                              final e = filtered[i];
                              return Card(
                                margin: const EdgeInsets.only(bottom: 10),
                                child: ListTile(
                                  contentPadding: const EdgeInsets.symmetric(
                                      horizontal: 16, vertical: 8),
                                  leading: CircleAvatar(
                                    backgroundColor: AppTheme.primaryBlue,
                                    child: Text('#${e.patientId}',
                                        style: const TextStyle(
                                            color: Colors.white,
                                            fontSize: 12,
                                            fontWeight: FontWeight.bold)),
                                  ),
                                  title: Text(
                                    '${locale.t('patient')} #${e.patientId}',
                                    style: const TextStyle(fontWeight: FontWeight.w600),
                                  ),
                                  subtitle: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(e.lastTitle,
                                          maxLines: 2, overflow: TextOverflow.ellipsis),
                                      const SizedBox(height: 2),
                                      Text(
                                        [
                                          if (e.lastVisit != null) dateFmt.format(e.lastVisit!),
                                          '${e.recordCount} ${locale.t('directory_records')}',
                                        ].join(' · '),
                                        style: const TextStyle(
                                            fontSize: 11, color: Colors.black45),
                                      ),
                                    ],
                                  ),
                                  trailing: const Icon(Icons.chevron_right),
                                  onTap: () => context.push('/patient/${e.patientId}'),
                                ),
                              );
                            },
                          ),
                        ),
                ),
              ],
            ),
    );
  }
}
