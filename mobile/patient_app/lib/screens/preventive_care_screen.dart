import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/neumorphic_colors.dart';

/// Preventive care — rule-based screening and vaccination reminders, plus
/// the referrals a doctor has raised for this patient.
///
/// Both existed only on the web portal (/preventive-care and /referrals).
/// Neither is an AI prediction: the reminders come from deterministic rules
/// in core/preventive_rules.py, so each one carries its own plain-language
/// reason rather than a score the patient has to trust blindly.
class PreventiveCareScreen extends StatefulWidget {
  const PreventiveCareScreen({super.key});

  @override
  State<PreventiveCareScreen> createState() => _PreventiveCareScreenState();
}

class _PreventiveCareScreenState extends State<PreventiveCareScreen> with SingleTickerProviderStateMixin {
  // Module theme: preventive teal.
  static const _theme = Color(0xFF14B8A6);

  late final TabController _tabs;
  List<Map<String, dynamic>> _reminders = [];
  List<Map<String, dynamic>> _referrals = [];
  bool _loading = true;
  bool _loadingReferrals = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _tabs.addListener(() {
      if (_tabs.index == 1 && _referrals.isEmpty) _loadReferrals();
    });
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
      final res = await ApiService().client.get('/preventive/reminders');
      if (!mounted) return;
      setState(() {
        _reminders = (res.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('preventive_load_failed');
        _loading = false;
      });
    }
  }

  Future<void> _loadReferrals() async {
    setState(() => _loadingReferrals = true);
    try {
      final res = await ApiService().client.get('/referrals/mine');
      if (!mounted) return;
      setState(() {
        _referrals = (res.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loadingReferrals = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('referrals_load_failed');
        _loadingReferrals = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final neu = Theme.of(context).extension<NeumorphicColors>()!;

    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(
        title: Text(locale.t('preventive_care')),
        bottom: TabBar(
          controller: _tabs,
          labelColor: _theme,
          indicatorColor: _theme,
          tabs: [
            Tab(text: locale.t('preventive_due_tab')),
            Tab(text: locale.t('referrals_tab')),
          ],
        ),
      ),
      body: Column(
        children: [
          if (_error != null)
            Container(
              width: double.infinity,
              color: Colors.red.withValues(alpha: 0.1),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Text(_error!, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.w600)),
            ),
          Expanded(
            child: TabBarView(
              controller: _tabs,
              children: [_buildReminders(locale), _buildReferrals(locale)],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReminders(LocaleService locale) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    // Due items first — the whole point of the screen is what needs doing now.
    final due = _reminders.where((r) => r['due'] == true).toList();
    final upToDate = _reminders.where((r) => r['due'] != true).toList();

    if (_reminders.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(children: [
          const SizedBox(height: 120),
          Center(child: Text(locale.t('preventive_none'))),
        ]),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
        children: [
          if (due.isNotEmpty) ...[
            Text(locale.t('preventive_due_now'),
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 8),
            ...due.map((r) => _card(locale, r, isDue: true)),
            const SizedBox(height: 18),
          ],
          if (upToDate.isNotEmpty) ...[
            Text(locale.t('preventive_up_to_date'),
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 8),
            ...upToDate.map((r) => _card(locale, r, isDue: false)),
          ],
        ],
      ),
    );
  }

  Widget _card(LocaleService locale, Map<String, dynamic> r, {required bool isDue}) {
    final action = r['suggested_action'] as String?;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  (r['category'] == 'vaccination') ? Icons.vaccines : Icons.monitor_heart,
                  size: 18,
                  color: isDue ? _theme : Colors.black38,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(r['title'] as String? ?? '',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
                if (isDue)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: _theme.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(locale.t('preventive_due_badge'),
                        style: const TextStyle(fontSize: 11, color: _theme, fontWeight: FontWeight.bold)),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(r['reason'] as String? ?? '', style: const TextStyle(fontSize: 13, color: Colors.black54)),
            if (r['last_done_date'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('${locale.t('preventive_last_done')}: ${r['last_done_date']}',
                    style: const TextStyle(fontSize: 12, color: Colors.black45)),
              ),
            if (isDue && action != null) ...[
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => context.push(action == 'lab_test' ? '/lab-tests' : '/book'),
                  style: OutlinedButton.styleFrom(foregroundColor: _theme),
                  child: Text(action == 'lab_test'
                      ? locale.t('preventive_book_test')
                      : locale.t('preventive_book_consult')),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildReferrals(LocaleService locale) {
    if (_loadingReferrals) return const Center(child: CircularProgressIndicator());
    if (_referrals.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadReferrals,
        child: ListView(children: [
          const SizedBox(height: 120),
          Center(child: Text(locale.t('referrals_none'))),
        ]),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadReferrals,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
        itemCount: _referrals.length,
        itemBuilder: (context, i) {
          final r = _referrals[i];
          final status = (r['status'] as String? ?? '').toLowerCase();
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
                            style: const TextStyle(fontWeight: FontWeight.bold)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: _theme.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(locale.t('referral_status_$status'),
                            style: const TextStyle(fontSize: 11, color: _theme, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(r['reason'] as String? ?? '', style: const TextStyle(fontSize: 13)),
                  if ((r['notes'] as String?)?.isNotEmpty ?? false)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(r['notes'] as String,
                          style: const TextStyle(fontSize: 12, color: Colors.black54)),
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
