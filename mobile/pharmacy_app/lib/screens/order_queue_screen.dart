import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/prescription.dart';
import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../theme.dart';

/// "New order notifications" feed (planning doc) — unfulfilled digital
/// prescriptions awaiting pickup, from GET /pharmacy/queue. There is no
/// push-triggered new-order notification wired server-side yet (see the
/// scoping note in firebase_notification_service.dart), so this screen
/// polls on open + pull-to-refresh, which is the reliable path today.
class OrderQueueScreen extends StatefulWidget {
  const OrderQueueScreen({super.key});

  @override
  State<OrderQueueScreen> createState() => _OrderQueueScreenState();
}

class _OrderQueueScreenState extends State<OrderQueueScreen> {
  final _service = PharmacyService();
  bool _loading = true;
  String? _error;
  List<PrescriptionQueueItem> _queue = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final queue = await _service.getQueue();
      setState(() {
        _queue = queue;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _fulfill(PrescriptionQueueItem item, LocaleService locale) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(locale.t('fulfill')),
        content: Text(locale.t('confirm_fulfill')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(locale.t('cancel'))),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: Text(locale.t('confirm'))),
        ],
      ),
    );
    if (confirmed != true) return;

    // Optimistic removal from the list, restored if the call fails.
    setState(() => _queue.removeWhere((q) => q.id == item.id));
    try {
      final result = await _service.fulfillPrescription(item.id);
      if (mounted) {
        final missing = (result['not_in_your_stock'] as List?) ?? [];
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(missing.isEmpty
              ? locale.t('fulfilled')
              : '${locale.t('fulfilled')} (${locale.t('not_in_stock_warning')}: ${missing.join(', ')})'),
        ));

        // Medicine Interaction Alerts (planning doc): shown after the fact
        // since fulfillment already completed — this is the pharmacist's
        // cue to counsel the patient, not a blocking gate.
        final warnings = (result['interaction_warnings'] as List?) ?? [];
        if (warnings.isNotEmpty && mounted) {
          await showDialog<void>(
            context: context,
            builder: (ctx) => AlertDialog(
              icon: const Icon(Icons.warning_amber_rounded, color: Colors.red, size: 36),
              title: Text(locale.t('interaction_warning_title')),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: warnings.map((w) {
                    final m = w as Map;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Text(
                        '${m['drug_a']} + ${m['drug_b']} (${m['severity']}): ${m['description']}',
                      ),
                    );
                  }).toList(),
                ),
              ),
              actions: [
                FilledButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: Text(locale.t('interaction_warning_ack')),
                ),
              ],
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _queue.insert(0, item));
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('error_generic'))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      appBar: AppBar(title: Text(locale.t('order_queue'))),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? ListView(children: [
                    const SizedBox(height: 100),
                    Center(child: Text(locale.t('offline_note'))),
                  ])
                : _queue.isEmpty
                    ? ListView(children: [
                        const SizedBox(height: 100),
                        Center(child: Text(locale.t('no_orders'))),
                      ])
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: _queue.length,
                        itemBuilder: (context, i) => _QueueCard(
                          item: _queue[i],
                          onFulfill: () => _fulfill(_queue[i], locale),
                          locale: locale,
                        ),
                      ),
      ),
    );
  }
}

class _QueueCard extends StatefulWidget {
  final PrescriptionQueueItem item;
  final VoidCallback onFulfill;
  final LocaleService locale;

  const _QueueCard({required this.item, required this.onFulfill, required this.locale});

  @override
  State<_QueueCard> createState() => _QueueCardState();
}

class _QueueCardState extends State<_QueueCard> {
  final _service = PharmacyService();
  final Map<String, List<Map<String, dynamic>>> _substitutes = {};

  @override
  void initState() {
    super.initState();
    _loadSubstitutes();
  }

  Future<void> _loadSubstitutes() async {
    for (final med in widget.item.medicines) {
      if (med.name.isEmpty) continue;
      final subs = await _service.getSubstitutes(med.name);
      if (subs.isNotEmpty && mounted) {
        setState(() => _substitutes[med.name] = subs);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = widget.locale;
    final item = widget.item;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.receipt_long, color: PharmacyTheme.primaryGreen),
                const SizedBox(width: 8),
                Text('#${item.id}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                const Spacer(),
                if (item.diagnosis != null && item.diagnosis!.isNotEmpty)
                  Chip(label: Text(item.diagnosis!), backgroundColor: PharmacyTheme.lightGreen),
              ],
            ),
            const SizedBox(height: 10),
            Text(locale.t('medicines_needed'), style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            ...item.medicines.map((m) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('• ${m.name} — ${m.dosage} (${m.frequency}, ${m.duration})'),
                      if (_substitutes[m.name]?.isNotEmpty == true)
                        Padding(
                          padding: const EdgeInsets.only(left: 12, top: 2),
                          child: Row(
                            children: [
                              const Icon(Icons.eco, size: 16, color: PharmacyTheme.accentMint),
                              const SizedBox(width: 4),
                              Expanded(
                                child: Text(
                                  '${locale.t('substitute_suggestion')}: '
                                  '${_substitutes[m.name]!.map((s) => "${s['name']} (₹${s['price']})").join(', ')}',
                                  style: const TextStyle(color: PharmacyTheme.accentMint, fontSize: 12),
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                )),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: widget.onFulfill,
                icon: const Icon(Icons.check_circle),
                label: Text(locale.t('fulfill')),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
