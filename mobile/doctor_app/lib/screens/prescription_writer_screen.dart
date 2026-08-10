import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/appointment.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';

class _MedicineRow {
  final nameController = TextEditingController();
  final dosageController = TextEditingController();
  final frequencyController = TextEditingController();
  final durationController = TextEditingController();

  void dispose() {
    nameController.dispose();
    dosageController.dispose();
    frequencyController.dispose();
    durationController.dispose();
  }

  bool get isEmpty =>
      nameController.text.trim().isEmpty &&
      dosageController.text.trim().isEmpty &&
      frequencyController.text.trim().isEmpty &&
      durationController.text.trim().isEmpty;

  Map<String, String> toJson() => {
        'name': nameController.text.trim(),
        'dosage': dosageController.text.trim(),
        'frequency': frequencyController.text.trim(),
        'duration': durationController.text.trim(),
      };
}

/// Prescription Writer — POST /api/v1/ehr/issue_prescription. Auto-syncs to
/// the patient's Family Health Wallet and pharmacy queue server-side; this
/// screen only needs to submit the structured form and show confirmation.
class PrescriptionWriterScreen extends StatefulWidget {
  final int patientId;
  final Appointment? appointment;

  const PrescriptionWriterScreen({super.key, required this.patientId, this.appointment});

  @override
  State<PrescriptionWriterScreen> createState() => _PrescriptionWriterScreenState();
}

class _PrescriptionWriterScreenState extends State<PrescriptionWriterScreen> {
  final _diagnosisController = TextEditingController();
  final _dosageInstructionsController = TextEditingController();
  final _notesController = TextEditingController();
  final List<_MedicineRow> _medicines = [_MedicineRow()];

  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _diagnosisController.dispose();
    _dosageInstructionsController.dispose();
    _notesController.dispose();
    for (final m in _medicines) {
      m.dispose();
    }
    super.dispose();
  }

  void _addMedicineRow() {
    setState(() => _medicines.add(_MedicineRow()));
  }

  void _removeMedicineRow(int index) {
    setState(() {
      _medicines[index].dispose();
      _medicines.removeAt(index);
    });
  }

  Future<void> _submit(LocaleService locale) async {
    final validMedicines = _medicines.where((m) => !m.isEmpty).toList();
    if (validMedicines.isEmpty) {
      setState(() => _error = locale.t('at_least_one_medicine'));
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final res = await ApiService().client.post('/ehr/issue_prescription', data: {
        if (widget.appointment != null) 'appointment_id': widget.appointment!.id,
        'patient_id': widget.patientId,
        if (widget.appointment?.familyProfileId != null)
          'family_profile_id': widget.appointment!.familyProfileId,
        'medicines': validMedicines.map((m) => m.toJson()).toList(),
        if (_dosageInstructionsController.text.trim().isNotEmpty)
          'dosage_instructions': _dosageInstructionsController.text.trim(),
        if (_diagnosisController.text.trim().isNotEmpty) 'diagnosis': _diagnosisController.text.trim(),
        if (_notesController.text.trim().isNotEmpty) 'notes': _notesController.text.trim(),
      });

      if (!mounted) return;
      setState(() => _submitting = false);

      // Medicine Interaction Alerts (planning doc): checked server-side
      // against the patient's other currently-active medicines — surfaced
      // here so the doctor sees it before leaving the screen.
      final warnings = (res.data is Map ? (res.data as Map)['interaction_warnings'] as List? : null) ?? [];

      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          icon: Icon(
            warnings.isEmpty ? Icons.check_circle : Icons.warning_amber_rounded,
            color: warnings.isEmpty ? AppTheme.completedGreen : Colors.red,
            size: 48,
          ),
          title: Text(warnings.isEmpty ? locale.t('issue_prescription') : locale.t('interaction_warning_title')),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(locale.t('prescription_success')),
                if (warnings.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  ...warnings.map((w) {
                    final m = w as Map;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(
                        '${m['drug_a']} + ${m['drug_b']} (${m['severity']}): ${m['description']}',
                        style: const TextStyle(fontSize: 13),
                      ),
                    );
                  }),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text(locale.t('confirm')),
            ),
          ],
        ),
      );
      if (!mounted) return;
      context.pop();
    } catch (e) {
      setState(() {
        _submitting = false;
        _error = locale.t('prescription_failed');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();

    return Scaffold(
      appBar: AppBar(title: Text(locale.t('prescription_writer'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _diagnosisController,
            decoration: InputDecoration(labelText: locale.t('diagnosis')),
          ),
          const SizedBox(height: 20),
          Text(locale.t('active_medicines'), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 8),
          ..._medicines.asMap().entries.map((entry) {
            final index = entry.key;
            final row = entry.value;
            return Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            '#${index + 1}',
                            style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.deepBlue),
                          ),
                        ),
                        if (_medicines.length > 1)
                          IconButton(
                            icon: const Icon(Icons.delete_outline, color: AppTheme.cancelledRed),
                            tooltip: locale.t('remove'),
                            onPressed: () => _removeMedicineRow(index),
                          ),
                      ],
                    ),
                    TextField(
                      controller: row.nameController,
                      decoration: InputDecoration(labelText: locale.t('medicine_name')),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: row.dosageController,
                            decoration: InputDecoration(labelText: locale.t('dosage')),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextField(
                            controller: row.frequencyController,
                            decoration: InputDecoration(labelText: locale.t('frequency')),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: row.durationController,
                      decoration: InputDecoration(labelText: locale.t('duration')),
                    ),
                  ],
                ),
              ),
            );
          }),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: _addMedicineRow,
              icon: const Icon(Icons.add),
              label: Text(locale.t('add_medicine')),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _dosageInstructionsController,
            maxLines: 2,
            decoration: InputDecoration(labelText: locale.t('dosage_instructions')),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _notesController,
            maxLines: 3,
            decoration: InputDecoration(labelText: locale.t('notes')),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: AppTheme.cancelledRed)),
          ],
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _submitting ? null : () => _submit(locale),
            child: _submitting
                ? const SizedBox(
                    height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : Text(locale.t('issue_prescription')),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}
