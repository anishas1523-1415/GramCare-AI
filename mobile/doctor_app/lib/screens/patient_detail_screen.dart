import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/appointment.dart';
import '../models/ehr_record.dart';
import '../models/patient_summary.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';
import '../widgets/status_badge.dart';

class PatientDetailScreen extends StatefulWidget {
  final int patientId;
  final Appointment? appointment;

  const PatientDetailScreen({super.key, required this.patientId, this.appointment});

  @override
  State<PatientDetailScreen> createState() => _PatientDetailScreenState();
}

class _PatientDetailScreenState extends State<PatientDetailScreen> {
  PatientSummary? _summary;
  List<EHRRecord> _history = [];
  bool _loadingSummary = true;
  bool _loadingHistory = true;
  String? _summaryError;
  String? _historyError;
  Appointment? _appointment;
  bool _updatingStatus = false;

  final _notesController = TextEditingController();
  bool _savingNotes = false;

  @override
  void initState() {
    super.initState();
    _appointment = widget.appointment;
    _notesController.text = _appointment?.consultationNotes ?? '';
    _loadSummary();
    _loadHistory();
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _loadSummary() async {
    setState(() {
      _loadingSummary = true;
      _summaryError = null;
    });
    try {
      final query = _appointment?.familyProfileId != null
          ? '?family_profile_id=${_appointment!.familyProfileId}'
          : '';
      final res = await ApiService()
          .client
          .get('/assist/patient-summary/${widget.patientId}$query');
      setState(() {
        _summary = PatientSummary.fromJson(res.data as Map<String, dynamic>);
        _loadingSummary = false;
      });
    } catch (e) {
      setState(() {
        _loadingSummary = false;
        _summaryError = context.mounted ? context.read<LocaleService>().t('error_generic') : null;
      });
    }
  }

  Future<void> _loadHistory() async {
    setState(() {
      _loadingHistory = true;
      _historyError = null;
    });
    try {
      final res = await ApiService().client.get('/ehr/patient/${widget.patientId}');
      final list = (res.data as List)
          .map((j) => EHRRecord.fromJson(j as Map<String, dynamic>))
          .toList();
      setState(() {
        _history = list;
        _loadingHistory = false;
      });
    } catch (e) {
      setState(() {
        _loadingHistory = false;
        _historyError = context.mounted ? context.read<LocaleService>().t('error_generic') : null;
      });
    }
  }

  Future<void> _updateStatus(String status) async {
    final appt = _appointment;
    if (appt == null) return;
    setState(() => _updatingStatus = true);
    try {
      final res = await ApiService().client.put(
            '/appointments/${appt.id}',
            data: {'status': status},
          );
      setState(() {
        _appointment = Appointment.fromJson(res.data as Map<String, dynamic>);
        _updatingStatus = false;
      });
    } catch (e) {
      setState(() => _updatingStatus = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.read<LocaleService>().t('error_generic'))),
      );
    }
  }

  Future<void> _saveNotes() async {
    final appt = _appointment;
    if (appt == null || _notesController.text.trim().isEmpty) return;
    setState(() => _savingNotes = true);
    try {
      final res = await ApiService().client.put(
            '/appointments/${appt.id}',
            data: {'consultation_notes': _notesController.text.trim()},
          );
      setState(() {
        _appointment = Appointment.fromJson(res.data as Map<String, dynamic>);
        _savingNotes = false;
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.read<LocaleService>().t('notes_saved'))),
      );
    } catch (e) {
      setState(() => _savingNotes = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.read<LocaleService>().t('error_generic'))),
      );
    }
  }

  Color _riskColor(String risk) {
    switch (risk) {
      case 'HIGH':
        return AppTheme.criticalRed;
      case 'MODERATE':
        return AppTheme.pendingAmber;
      default:
        return AppTheme.completedGreen;
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();

    return Scaffold(
      appBar: AppBar(title: Text(locale.t('patient_detail'))),
      body: RefreshIndicator(
        onRefresh: () async {
          await Future.wait([_loadSummary(), _loadHistory()]);
        },
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            if (_appointment != null) _buildAppointmentHeader(locale),
            const SizedBox(height: 8),
            _buildSummaryCard(locale),
            const SizedBox(height: 8),
            _buildHistoryCard(locale),
            const SizedBox(height: 8),
            if (_appointment != null) _buildActionsCard(locale),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildAppointmentHeader(LocaleService locale) {
    final appt = _appointment!;
    final dateFmt = DateFormat('EEE, MMM d, yyyy  •  hh:mm a');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  dateFmt.format(appt.scheduledAt.toLocal()),
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                StatusBadge(status: appt.status, locale: locale),
              ],
            ),
            if (appt.triageSummary != null && appt.triageSummary!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(locale.t('triage_summary'), style: const TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              Text(appt.triageSummary!),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryCard(LocaleService locale) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.auto_awesome, color: AppTheme.primaryBlue, size: 20),
                const SizedBox(width: 8),
                Text(locale.t('ai_pre_consult_summary'), style: const TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 10),
            if (_loadingSummary)
              const Center(child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator()))
            else if (_summaryError != null)
              Row(
                children: [
                  Expanded(child: Text(_summaryError!)),
                  TextButton(onPressed: _loadSummary, child: Text(locale.t('retry'))),
                ],
              )
            else if (_summary != null)
              _buildSummaryContent(locale, _summary!),
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryContent(LocaleService locale, PatientSummary s) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(s.patientName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: _riskColor(s.riskFlag).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                '${locale.t('risk_flag')}: ${s.riskFlag}',
                style: TextStyle(color: _riskColor(s.riskFlag), fontWeight: FontWeight.bold, fontSize: 12),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(s.summaryText, style: const TextStyle(color: Colors.black87)),
        if (s.activeMedicines.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(locale.t('active_medicines'), style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          ...s.activeMedicines.map(
            (m) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text('• ${m.name} ${m.dosage} (${m.frequency}) — ${m.daysRemaining}d remaining'),
            ),
          ),
        ],
        if (s.recentConditions.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(locale.t('recent_conditions'), style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          Text(s.recentConditions.join(', ')),
        ],
        if (s.latestVitals != null) ...[
          const SizedBox(height: 12),
          Text(locale.t('latest_vitals'), style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          Text(
            'HR ${s.latestVitals!['heart_rate']} bpm • SpO2 ${s.latestVitals!['spo2']}% • ${s.latestVitals!['temperature']}°C',
          ),
        ],
      ],
    );
  }

  Widget _buildHistoryCard(LocaleService locale) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.history, color: AppTheme.primaryBlue, size: 20),
                const SizedBox(width: 8),
                Text(locale.t('medical_history'), style: const TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 10),
            if (_loadingHistory)
              const Center(child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator()))
            else if (_historyError != null)
              Row(
                children: [
                  Expanded(child: Text(_historyError!)),
                  TextButton(onPressed: _loadHistory, child: Text(locale.t('retry'))),
                ],
              )
            else if (_history.isEmpty)
              Text(locale.t('no_history'), style: const TextStyle(color: Colors.black54))
            else
              ..._history.take(10).map((r) => _historyTile(r)),
          ],
        ),
      ),
    );
  }

  Widget _historyTile(EHRRecord r) {
    final dateFmt = DateFormat('MMM d, yyyy');
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(_iconForRecordType(r.recordType), size: 18, color: AppTheme.deepBlue),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  r.title ?? r.recordType,
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                ),
                Text(
                  r.content,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: Colors.black54),
                ),
                Text(
                  dateFmt.format((r.recordDate ?? r.createdAt).toLocal()),
                  style: const TextStyle(fontSize: 11, color: Colors.black38),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  IconData _iconForRecordType(String type) {
    switch (type) {
      case 'prescription':
        return Icons.medication_outlined;
      case 'lab_report':
        return Icons.biotech_outlined;
      case 'vaccination':
        return Icons.vaccines_outlined;
      case 'scan':
        return Icons.document_scanner_outlined;
      case 'triage_log':
        return Icons.monitor_heart_outlined;
      default:
        return Icons.note_outlined;
    }
  }

  Widget _buildActionsCard(LocaleService locale) {
    final appt = _appointment!;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (appt.status == 'PENDING')
                  ElevatedButton.icon(
                    onPressed: _updatingStatus ? null : () => _updateStatus('CONFIRMED'),
                    icon: const Icon(Icons.check_circle_outline, size: 18),
                    label: Text(locale.t('mark_confirmed')),
                  ),
                if (appt.status == 'CONFIRMED')
                  ElevatedButton.icon(
                    onPressed: _updatingStatus ? null : () => _updateStatus('COMPLETED'),
                    icon: const Icon(Icons.task_alt, size: 18),
                    label: Text(locale.t('mark_completed')),
                  ),
                if (appt.status == 'PENDING' || appt.status == 'CONFIRMED')
                  OutlinedButton.icon(
                    onPressed: _updatingStatus ? null : () => _updateStatus('CANCELLED'),
                    icon: const Icon(Icons.cancel_outlined, size: 18, color: AppTheme.cancelledRed),
                    label: Text(locale.t('cancel_appointment'), style: const TextStyle(color: AppTheme.cancelledRed)),
                  ),
                OutlinedButton.icon(
                  onPressed: () => context.push('/prescribe/${widget.patientId}', extra: appt),
                  icon: const Icon(Icons.receipt_long_outlined, size: 18),
                  label: Text(locale.t('write_prescription')),
                ),
                if (appt.mode == 'teleconsultation' && appt.status == 'CONFIRMED')
                  ElevatedButton.icon(
                    onPressed: () => context.push('/video-call/${appt.id}'),
                    icon: const Icon(Icons.videocam, size: 18),
                    label: const Text('Start Video Call'),
                    style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryBlue),
                  ),
              ],
            ),
            const Divider(height: 28),
            Text(locale.t('consultation_notes'), style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            TextField(
              controller: _notesController,
              maxLines: 4,
              decoration: InputDecoration(hintText: locale.t('add_notes')),
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: ElevatedButton(
                onPressed: _savingNotes ? null : _saveNotes,
                child: _savingNotes
                    ? const SizedBox(
                        height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : Text(locale.t('save_notes')),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
