import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/neumorphic_colors.dart';

/// Nearby medicine availability — planning doc: "பக்கத்துல இருக்கற எந்த
/// பார்மசியில அந்த மருந்து இருக்குன்னு காட்டும்" with green/red coding and
/// generic substitutes when unavailable.
///
/// GPS capture ships with roadmap Phase 6 (geolocator lands alongside the
/// SOS work); until then the search runs unlocated and the server returns
/// all registered pharmacies with availability.
class PharmacySearchScreen extends StatefulWidget {
  const PharmacySearchScreen({super.key});

  @override
  State<PharmacySearchScreen> createState() => _PharmacySearchScreenState();
}

class _PharmacySearchScreenState extends State<PharmacySearchScreen> {
  final TextEditingController _controller = TextEditingController();
  bool _loading = false;
  String _error = '';
  List<Map<String, dynamic>>? _results;
  final Set<int> _preorderedPharmacyIds = {};

  // Pharmacy module theme: green (planning doc's per-module color identity)
  static const _themeColor = Color(0xFF10B981);

  Future<void> _preorder(int pharmacyId, LocaleService locale) async {
    final query = _controller.text.trim();
    try {
      await ApiService().client.post('/pharmacy/preorders', data: {
        'pharmacy_id': pharmacyId,
        'medicine_name': query,
        'quantity': 1,
      });
      if (mounted) setState(() => _preorderedPharmacyIds.add(pharmacyId));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(locale.t('preorder_failed'))),
        );
      }
    }
  }

  Future<void> _search(LocaleService locale) async {
    final query = _controller.text.trim();
    if (query.length < 2) return;
    setState(() {
      _loading = true;
      _error = '';
      _results = null;
    });
    try {
      final res = await ApiService().client.get(
        '/pharmacy/search',
        queryParameters: {'medicine': query},
      );
      setState(() {
        _results = List<Map<String, dynamic>>.from(res.data as List);
      });
    } catch (_) {
      setState(() => _error = locale.t('search_failed'));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    final locale = context.watch<LocaleService>();
    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: neu.foreground),
          onPressed: () => context.pop(),
        ),
        title: Text(
          locale.t('find_medicine'),
          style: TextStyle(color: neu.foreground, fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Row(
                children: [
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        color: neu.background,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [
                          BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                          BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
                        ],
                      ),
                      child: TextField(
                        controller: _controller,
                        onSubmitted: (_) => _search(locale),
                        decoration: InputDecoration(
                          hintText: locale.t('medicine_name_hint'),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.all(18),
                          prefixIcon: const Icon(Icons.medication, color: _themeColor),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  GestureDetector(
                    onTap: _loading ? null : () => _search(locale),
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: _themeColor,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [
                          BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                        ],
                      ),
                      child: _loading
                          ? const SizedBox(
                              width: 22, height: 22,
                              child: CircularProgressIndicator(
                                  color: Colors.white, strokeWidth: 2))
                          : const Icon(Icons.search, color: Colors.white),
                    ),
                  ),
                ],
              ),
            ),

            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Text(_error,
                    style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
              ),

            Expanded(
              child: _results == null
                  ? Center(
                      child: Text(
                        locale.t('search_medicine_prompt'),
                        style: TextStyle(color: neu.foregroundMuted),
                      ),
                    )
                  : _results!.isEmpty
                      ? Center(
                          child: Text(locale.t('no_pharmacies_found'),
                              style: TextStyle(color: neu.foregroundMuted)),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 24),
                          itemCount: _results!.length,
                          itemBuilder: (context, i) {
                            final r = _results![i];
                            final available = r['available'] == true;
                            final isJanAushadhi = r['is_jan_aushadhi'] == true;
                            final pharmacyId = r['pharmacy_id'] as int?;
                            final subs = List<String>.from(r['substitutes'] as List? ?? const []);
                            return Container(
                              margin: const EdgeInsets.only(bottom: 14),
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: neu.background,
                                borderRadius: BorderRadius.circular(16),
                                border: Border(
                                  left: BorderSide(
                                    color: available ? _themeColor : Colors.red.shade400,
                                    width: 6,
                                  ),
                                ),
                                boxShadow: [
                                  BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                                  BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
                                ],
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Expanded(
                                        child: Row(
                                          children: [
                                            Flexible(
                                              child: Text(
                                                r['pharmacy_name'] as String? ?? 'Pharmacy',
                                                style: const TextStyle(
                                                    fontWeight: FontWeight.bold, fontSize: 17),
                                                overflow: TextOverflow.ellipsis,
                                              ),
                                            ),
                                            if (isJanAushadhi) ...[
                                              const SizedBox(width: 6),
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                                decoration: BoxDecoration(
                                                  color: Colors.blue.shade50,
                                                  borderRadius: BorderRadius.circular(20),
                                                ),
                                                child: Text(
                                                  locale.t('jan_aushadhi'),
                                                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.blue.shade700),
                                                ),
                                              ),
                                            ],
                                          ],
                                        ),
                                      ),
                                      Icon(
                                        available ? Icons.check_circle : Icons.cancel,
                                        color: available ? _themeColor : Colors.red,
                                      ),
                                    ],
                                  ),
                                  if (r['address'] != null)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 4),
                                      child: Text(r['address'] as String,
                                          style: TextStyle(
                                              fontSize: 13, color: neu.foregroundMuted)),
                                    ),
                                  const SizedBox(height: 8),
                                  Text(
                                    available
                                        ? '${locale.t('in_stock')}${r['price'] != null ? ' · ₹${r['price']}' : ''}'
                                        : locale.t('not_available'),
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      color: available ? _themeColor : Colors.red,
                                    ),
                                  ),
                                  if (!available && subs.isNotEmpty) ...[
                                    const SizedBox(height: 8),
                                    Container(
                                      padding: const EdgeInsets.all(10),
                                      decoration: BoxDecoration(
                                        color: _themeColor.withValues(alpha: 0.12),
                                        borderRadius: BorderRadius.circular(10),
                                      ),
                                      child: Text(
                                        '${locale.t('alternatives')}: ${subs.join(', ')}',
                                        style: const TextStyle(fontSize: 13),
                                      ),
                                    ),
                                  ],
                                  if (!available && pharmacyId != null) ...[
                                    const SizedBox(height: 10),
                                    SizedBox(
                                      width: double.infinity,
                                      child: OutlinedButton.icon(
                                        onPressed: _preorderedPharmacyIds.contains(pharmacyId)
                                            ? null
                                            : () => _preorder(pharmacyId, locale),
                                        icon: const Icon(Icons.add_shopping_cart, size: 16),
                                        label: Text(
                                          _preorderedPharmacyIds.contains(pharmacyId)
                                              ? locale.t('preordered_notify')
                                              : locale.t('preorder_cta'),
                                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                                        ),
                                        style: OutlinedButton.styleFrom(
                                          foregroundColor: const Color(0xFF4F46E5),
                                          side: const BorderSide(color: Color(0xFF4F46E5)),
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            );
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
