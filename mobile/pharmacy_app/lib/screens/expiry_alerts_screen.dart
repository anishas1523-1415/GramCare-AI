import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/stock_item.dart';
import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../theme.dart';

/// Orange-coded Expiry Alerts tab (planning doc) — GET /pharmacy/expiring,
/// already sorted soonest-first server-side.
class ExpiryAlertsScreen extends StatefulWidget {
  const ExpiryAlertsScreen({super.key});

  @override
  State<ExpiryAlertsScreen> createState() => _ExpiryAlertsScreenState();
}

class _ExpiryAlertsScreenState extends State<ExpiryAlertsScreen> {
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
      final items = await _service.getExpiring();
      setState(() {
        _items = items;
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
      appBar: AppBar(title: Text(locale.t('expiry_alerts'))),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? ListView(children: [const SizedBox(height: 100), Center(child: Text(locale.t('offline_note')))])
                : _items.isEmpty
                    ? ListView(children: [const SizedBox(height: 100), Center(child: Text(locale.t('no_expiring_items')))])
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: _items.length,
                        itemBuilder: (context, i) {
                          final item = _items[i];
                          Color alertColor = PharmacyTheme.statusOptimal;
                          if (item.daysLeft != null) {
                            if (item.daysLeft! <= 30) {
                              alertColor = PharmacyTheme.statusOutOfStock; // Red
                            } else if (item.daysLeft! <= 90) {
                              alertColor = PharmacyTheme.statusLow; // Orange
                            }
                          }
                          return Card(
                            margin: const EdgeInsets.only(bottom: 10),
                            color: alertColor.withValues(alpha: 0.08),
                            child: ListTile(
                              leading: Icon(Icons.warning_amber_rounded, color: alertColor),
                              title: Text(item.medicineName, style: const TextStyle(fontWeight: FontWeight.w600)),
                              subtitle: Text('${item.expiryDate ?? '-'} · ${locale.t('remaining')}: ${item.stockCount}'),
                              trailing: item.daysLeft != null
                                  ? Text('${item.daysLeft} ${locale.t('days_left')}',
                                      style: TextStyle(color: alertColor, fontWeight: FontWeight.bold))
                                  : null,
                            ),
                          );
                        },
                      ),
      ),
    );
  }
}
