import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/neumorphic_colors.dart';

/// My Care — the AI Care Navigator's prioritised "what to do next" list.
///
/// Mirrors /my-care on the web portal (GET /navigator/next-steps). Each item
/// carries its own `reason`, so the patient is told *why* something is being
/// suggested rather than being handed a bare instruction — and a `cta_route`
/// the app turns into a button that goes straight there.
class MyCareScreen extends StatefulWidget {
  const MyCareScreen({super.key});

  @override
  State<MyCareScreen> createState() => _MyCareScreenState();
}

class _MyCareScreenState extends State<MyCareScreen> {
  // Module theme: navigator indigo.
  static const _theme = Color(0xFF6366F1);

  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;

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
      final res = await ApiService().client.get('/navigator/next-steps');
      if (!mounted) return;
      setState(() {
        _items = (res.data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.read<LocaleService>().t('my_care_load_failed');
        _loading = false;
      });
    }
  }

  static const _priorityColors = {
    'CRITICAL': Color(0xFFEF4444),
    'HIGH': Color(0xFFF97316),
    'MEDIUM': Color(0xFF6366F1),
    'LOW': Color(0xFF64748B),
  };

  static const _categoryIcons = {
    'sos': Icons.emergency,
    'lab': Icons.science,
    'appointment': Icons.event,
    'prescription': Icons.medication,
    'preventive': Icons.health_and_safety,
    'all_clear': Icons.check_circle,
  };

  /// The navigator returns web routes; the phone's equivalents differ for a
  /// few of them, so map rather than pushing a path this app has no route for.
  String? _appRoute(String? webRoute) {
    if (webRoute == null) return null;
    const map = {
      '/lab-tests': '/lab-tests',
      '/book': '/book',
      '/appointments': '/appointments',
      '/preventive-care': '/preventive-care',
      '/prescriptions': '/wallet',
      '/passport': '/passport',
      '/pharmacy': '/pharmacy',
      '/symptom-checker': '/triage',
    };
    final base = webRoute.split('?').first;
    return map[base];
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final neu = Theme.of(context).extension<NeumorphicColors>()!;

    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(title: Text(locale.t('my_care'))),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                children: [
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(_error!,
                          style: const TextStyle(color: Colors.red, fontWeight: FontWeight.w600)),
                    ),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: Text(locale.t('my_care_subtitle'),
                        style: const TextStyle(fontSize: 13, color: Colors.black54)),
                  ),
                  if (_items.isEmpty && _error == null) ...[
                    const SizedBox(height: 80),
                    Center(child: Text(locale.t('my_care_none'))),
                  ],
                  ..._items.map((item) {
                    final priority = item['priority'] as String? ?? 'LOW';
                    final color = _priorityColors[priority] ?? _theme;
                    final route = _appRoute(item['cta_route'] as String?);
                    return Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(_categoryIcons[item['category']] ?? Icons.info_outline,
                                    size: 18, color: color),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(item['title'] as String? ?? '',
                                      style: const TextStyle(fontWeight: FontWeight.bold)),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: color.withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Text(
                                    locale.t('priority_${priority.toLowerCase()}'),
                                    style: TextStyle(
                                        fontSize: 11, color: color, fontWeight: FontWeight.bold),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Text(item['reason'] as String? ?? '',
                                style: const TextStyle(fontSize: 13, color: Colors.black54)),
                            if (route != null) ...[
                              const SizedBox(height: 10),
                              SizedBox(
                                width: double.infinity,
                                child: OutlinedButton(
                                  onPressed: () => context.push(route),
                                  style: OutlinedButton.styleFrom(foregroundColor: color),
                                  child: Text(item['cta_label'] as String? ?? locale.t('open')),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
    );
  }
}
