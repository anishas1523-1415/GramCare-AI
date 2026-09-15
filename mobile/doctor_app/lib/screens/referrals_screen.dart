import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';

/// Referral network — referrals waiting on this doctor, and ones they have
/// sent out.
///
/// The web dashboard has had this panel since the referral module shipped;
/// the phone did not, which is the wrong way round. An incoming referral is
/// time-sensitive — a colleague has handed a patient over and is waiting on
/// an accept or decline — and that is exactly the decision a doctor is most
/// likely to be making away from a desk.
class ReferralsScreen extends StatefulWidget {
  const ReferralsScreen({super.key});

  @override
  State<ReferralsScreen> createState() => _ReferralsScreenState();
}

class _ReferralsScreenState extends State<ReferralsScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  List<Map<String, dynamic>> _incoming = [];
  List<Map<String, dynamic>> _sent = [];
  bool _loading = true;
  int? _busyId;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        ApiService().client.get('/referrals/incoming'),
        ApiService().client.get('/referrals/sent'),
      ]);
      if (!mounted) return;
      setState(() {
        _incoming = (results[0].data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _sent = (results[1].data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('referrals_load_failed');
        _loading = false;
      });
    }
  }

  Future<void> _act(int id, String action) async {
    setState(() {
      _busyId = id;
      _error = null;
    });
    try {
      await ApiService().client.put('/referrals/$id/$action');
      await _load();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('referral_action_failed');
      });
    } finally {
      if (mounted) setState(() => _busyId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();

    return Scaffold(
      appBar: AppBar(
        title: Text(locale.t('referrals')),
        bottom: TabBar(
          controller: _tabs,
          tabs: [
            Tab(text: _incoming.isEmpty
                ? locale.t('referrals_incoming')
                : '${locale.t('referrals_incoming')} (${_incoming.length})'),
            Tab(text: locale.t('referrals_sent')),
          ],
        ),
      ),
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
                        style: const TextStyle(color: AppTheme.criticalRed, fontWeight: FontWeight.w600)),
                  ),
                Expanded(
                  child: TabBarView(
                    controller: _tabs,
                    children: [
                      _buildList(locale, _incoming, incoming: true),
                      _buildList(locale, _sent, incoming: false),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Widget _buildList(LocaleService locale, List<Map<String, dynamic>> items, {required bool incoming}) {
    if (items.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(children: [
          const SizedBox(height: 140),
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                incoming ? locale.t('referrals_none_incoming') : locale.t('referrals_none_sent'),
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.black54),
              ),
            ),
          ),
        ]),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: items.length,
        itemBuilder: (context, i) {
          final r = items[i];
          final id = r['id'] as int;
          final status = (r['status'] as String? ?? '').toUpperCase();
          final isOpen = r['referred_to_doctor_id'] == null;
          final busy = _busyId == id;

          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(r['specialty'] as String? ?? '',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryBlue.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(locale.t('referral_status_${status.toLowerCase()}'),
                            style: const TextStyle(
                                fontSize: 11, color: AppTheme.primaryBlue, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text('${locale.t('patient')} #${r['patient_id']}',
                      style: const TextStyle(fontSize: 12, color: Colors.black54)),
                  const SizedBox(height: 6),
                  Text(r['reason'] as String? ?? '', style: const TextStyle(fontSize: 13)),
                  if ((r['notes'] as String?)?.isNotEmpty ?? false)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(r['notes'] as String,
                          style: const TextStyle(fontSize: 12, color: Colors.black54)),
                    ),
                  if (incoming && isOpen && status == 'PENDING')
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(locale.t('referral_open_note'),
                          style: const TextStyle(
                              fontSize: 12, color: AppTheme.primaryBlue, fontWeight: FontWeight.w600)),
                    ),
                  if (incoming && status == 'PENDING') ...[
                    const SizedBox(height: 10),
                    Row(children: [
                      Expanded(
                        child: ElevatedButton(
                          onPressed: busy ? null : () => _act(id, 'accept'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.primaryBlue,
                            foregroundColor: Colors.white,
                          ),
                          child: Text(locale.t('accept')),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton(
                          onPressed: busy ? null : () => _act(id, 'decline'),
                          style: OutlinedButton.styleFrom(foregroundColor: AppTheme.criticalRed),
                          child: Text(locale.t('decline')),
                        ),
                      ),
                    ]),
                  ],
                  if (incoming && status == 'ACCEPTED') ...[
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: busy ? null : () => _act(id, 'complete'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF10B981),
                          foregroundColor: Colors.white,
                        ),
                        child: Text(locale.t('mark_complete')),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
