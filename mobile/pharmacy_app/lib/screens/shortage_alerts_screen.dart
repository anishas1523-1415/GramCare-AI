import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/stock_item.dart';
import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../theme.dart';

/// Shortage Alerts — items the backend already flags as "Low" or
/// "Out of Stock" via the `status` field computed in _status_for()
/// (apps/backend_service/modules/pharmacy_inventory/router.py:50-57).
/// Reuses GET /pharmacy/stock and filters client-side rather than inventing
/// new backend logic, since the status field already covers this.
class ShortageAlertsScreen extends StatefulWidget {
  const ShortageAlertsScreen({super.key});

  @override
  State<ShortageAlertsScreen> createState() => _ShortageAlertsScreenState();
}

class _ShortageAlertsScreenState extends State<ShortageAlertsScreen> {
  final _service = PharmacyService();
  bool _loading = true;
  String? _error;
  List<StockItem> _items = [];

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
      final stock = await _service.getStock();
      final shortages = stock.where((s) => s.status != 'Optimal').toList()
        ..sort((a, b) => a.stockCount.compareTo(b.stockCount));
      setState(() {
        _items = shortages;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      appBar: AppBar(title: Text(locale.t('shortage_alerts'))),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? ListView(children: [const SizedBox(height: 100), Center(child: Text(locale.t('offline_note')))])
                : _items.isEmpty
                    ? ListView(children: [const SizedBox(height: 100), Center(child: Text(locale.t('no_shortages')))])
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: _items.length,
                        itemBuilder: (context, i) {
                          final item = _items[i];
                          final color = PharmacyTheme.statusColor(item.status);
                          return Card(
                            margin: const EdgeInsets.only(bottom: 10),
                            color: color.withValues(alpha: 0.08),
                            child: ListTile(
                              leading: Icon(
                                item.status == 'Out of Stock' ? Icons.remove_shopping_cart : Icons.trending_down,
                                color: color,
                              ),
                              title: Text(item.medicineName, style: const TextStyle(fontWeight: FontWeight.w600)),
                              subtitle: Text('${locale.t('remaining')}: ${item.stockCount}'),
                              trailing: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(color: color.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(8)),
                                child: Text(item.status, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12)),
                              ),
                            ),
                          );
                        },
                      ),
      ),
    );
  }
}
