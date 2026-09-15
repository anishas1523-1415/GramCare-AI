import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../theme/neumorphic_colors.dart';

/// Lab test booking — search the catalog, pick a nearby centre, optionally
/// request home sample collection, and track the report.
///
/// The backend has supported this since the lab module shipped and the web
/// portal exposes it at /lab-tests, but the phone had no way in. Home
/// collection is the part that matters most here: the patients least able
/// to travel to a diagnostic centre are the ones using this app.
class LabTestsScreen extends StatefulWidget {
  const LabTestsScreen({super.key});

  @override
  State<LabTestsScreen> createState() => _LabTestsScreenState();
}

class _LabTestsScreenState extends State<LabTestsScreen> with SingleTickerProviderStateMixin {
  // Module theme: diagnostics violet, matching the web portal's lab page.
  static const _theme = Color(0xFF8B5CF6);

  late final TabController _tabs;

  final _search = TextEditingController();
  List<Map<String, dynamic>> _tests = [];
  List<Map<String, dynamic>> _centers = [];
  List<Map<String, dynamic>> _bookings = [];
  Map<int, String> _centerNames = {};

  bool _loadingTests = true;
  bool _loadingBookings = false;
  bool _booking = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _tabs.addListener(() {
      if (_tabs.index == 1 && _bookings.isEmpty) _loadBookings();
    });
    _loadTests();
  }

  @override
  void dispose() {
    _tabs.dispose();
    _search.dispose();
    super.dispose();
  }

  Future<void> _loadTests([String? query]) async {
    setState(() {
      _loadingTests = true;
      _error = null;
    });
    try {
      final res = await ApiService().client.get(
        '/lab/tests',
        queryParameters: (query != null && query.isNotEmpty) ? {'query': query} : null,
      );
      if (!mounted) return;
      setState(() {
        _tests = (res.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loadingTests = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('lab_tests_load_failed');
        _loadingTests = false;
      });
    }
  }

  Future<void> _loadCenters() async {
    if (_centers.isNotEmpty) return;
    final res = await ApiService().client.get('/lab/centers');
    _centers = (res.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    _centerNames = {for (final c in _centers) c['id'] as int: c['name'] as String};
  }

  Future<void> _loadBookings() async {
    setState(() => _loadingBookings = true);
    try {
      await _loadCenters();
      final res = await ApiService().client.get('/lab/bookings/mine');
      if (!mounted) return;
      setState(() {
        _bookings = (res.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loadingBookings = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('lab_bookings_load_failed');
        _loadingBookings = false;
      });
    }
  }

  Future<void> _openBookingSheet(Map<String, dynamic> test) async {
    final locale = context.read<LocaleService>();
    try {
      await _loadCenters();
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = locale.t('lab_centers_load_failed'));
      return;
    }
    if (!mounted) return;

    if (_centers.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(locale.t('lab_no_centers'))),
      );
      return;
    }

    Map<String, dynamic> center = _centers.first;
    bool homeCollection = false;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) => Padding(
          padding: EdgeInsets.only(
            left: 16, right: 16, top: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(test['name'] as String? ?? '',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              if ((test['prep_instructions'] as String?)?.isNotEmpty ?? false)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(test['prep_instructions'] as String,
                      style: const TextStyle(fontSize: 12, color: Colors.black54)),
                ),
              const SizedBox(height: 18),
              Text(locale.t('lab_choose_center'), style: const TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              DropdownButtonFormField<int>(
                initialValue: center['id'] as int,
                decoration: const InputDecoration(border: OutlineInputBorder()),
                items: _centers
                    .map((c) => DropdownMenuItem(
                          value: c['id'] as int,
                          child: Text(c['name'] as String, overflow: TextOverflow.ellipsis),
                        ))
                    .toList(),
                onChanged: (v) => setSheet(() {
                  center = _centers.firstWhere((c) => c['id'] == v);
                  if (center['offers_home_collection'] != true) homeCollection = false;
                }),
              ),
              if (center['offers_home_collection'] == true)
                CheckboxListTile(
                  value: homeCollection,
                  onChanged: (v) => setSheet(() => homeCollection = v ?? false),
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: Text(locale.t('lab_home_collection'), style: const TextStyle(fontSize: 14)),
                ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _booking
                      ? null
                      : () async {
                          Navigator.pop(ctx);
                          await _submitBooking(test, center, homeCollection);
                        },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _theme,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: Text(locale.t('lab_confirm_booking')),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _submitBooking(
    Map<String, dynamic> test,
    Map<String, dynamic> center,
    bool homeCollection,
  ) async {
    final locale = context.read<LocaleService>();
    final profile = context.read<ProfileService>().active;
    setState(() {
      _booking = true;
      _error = null;
    });
    try {
      await ApiService().client.post('/lab/bookings', data: {
        'lab_center_id': center['id'],
        'test_name': test['name'],
        'family_profile_id': profile?.id,
        'home_collection': homeCollection,
      });
      if (!mounted) return;
      setState(() => _booking = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(locale.t('lab_booked'))),
      );
      _bookings = [];
      _tabs.animateTo(1);
      _loadBookings();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _booking = false;
        _error = locale.t('lab_booking_failed');
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
        title: Text(locale.t('lab_tests')),
        bottom: TabBar(
          controller: _tabs,
          labelColor: _theme,
          indicatorColor: _theme,
          tabs: [
            Tab(text: locale.t('lab_book_tab')),
            Tab(text: locale.t('lab_my_bookings_tab')),
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
              children: [_buildCatalog(locale), _buildBookings(locale)],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCatalog(LocaleService locale) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _search,
            textInputAction: TextInputAction.search,
            onSubmitted: _loadTests,
            decoration: InputDecoration(
              hintText: locale.t('lab_search_hint'),
              prefixIcon: const Icon(Icons.search),
              filled: true,
              fillColor: Colors.white,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ),
        Expanded(
          child: _loadingTests
              ? const Center(child: CircularProgressIndicator())
              : _tests.isEmpty
                  ? Center(child: Text(locale.t('lab_no_tests')))
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(12, 0, 12, 24),
                      itemCount: _tests.length,
                      itemBuilder: (context, i) {
                        final t = _tests[i];
                        return Card(
                          margin: const EdgeInsets.only(bottom: 10),
                          child: ListTile(
                            title: Text(t['name'] as String? ?? '',
                                style: const TextStyle(fontWeight: FontWeight.w600)),
                            subtitle: Text(
                              [t['category'], t['sample_type']].where((e) => e != null).join(' · '),
                              style: const TextStyle(fontSize: 12),
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => _openBookingSheet(t),
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildBookings(LocaleService locale) {
    if (_loadingBookings) return const Center(child: CircularProgressIndicator());
    if (_bookings.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadBookings,
        child: ListView(children: [
          const SizedBox(height: 120),
          Center(child: Text(locale.t('lab_no_bookings'))),
        ]),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadBookings,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
        itemCount: _bookings.length,
        itemBuilder: (context, i) {
          final b = _bookings[i];
          final status = b['status'] as String? ?? '';
          final report = b['report_payload'] as Map?;
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
                        child: Text(b['test_name'] as String? ?? '',
                            style: const TextStyle(fontWeight: FontWeight.bold)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: _theme.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(locale.t('lab_status_${status.toLowerCase()}'),
                            style: const TextStyle(fontSize: 11, color: _theme, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _centerNames[b['lab_center_id']] ?? '',
                    style: const TextStyle(fontSize: 12, color: Colors.black54),
                  ),
                  if (b['home_collection'] == true)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Row(children: [
                        const Icon(Icons.home, size: 13, color: Colors.black45),
                        const SizedBox(width: 4),
                        Text(locale.t('lab_home_collection'),
                            style: const TextStyle(fontSize: 12, color: Colors.black54)),
                      ]),
                    ),
                  if (report != null && (report['summary'] as String?)?.isNotEmpty == true) ...[
                    const Divider(height: 18),
                    Text(locale.t('lab_report'), style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                    const SizedBox(height: 4),
                    Text(report['summary'] as String, style: const TextStyle(fontSize: 13)),
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
