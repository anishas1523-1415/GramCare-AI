import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/stock_item.dart';
import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../theme.dart';
import 'add_item_screen.dart';
import 'sell_item_screen.dart';

/// Stock Management — list of current inventory from GET /pharmacy/stock.
/// Tapping an item opens the tap-to-decrement sale screen (the busiest
/// screen in the app per the planning doc). The FAB opens the add-item flow.
class StockScreen extends StatefulWidget {
  const StockScreen({super.key});

  @override
  State<StockScreen> createState() => _StockScreenState();
}

class _StockScreenState extends State<StockScreen> {
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
      final items = await _service.getStock();
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
      appBar: AppBar(title: Text(locale.t('stock_management'))),
      floatingActionButton: FloatingActionButton.extended(
        icon: const Icon(Icons.add),
        label: Text(locale.t('add_item')),
        onPressed: () async {
          final added = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => const AddItemScreen()),
          );
          if (added == true) _load();
        },
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? ListView(children: [
                    const SizedBox(height: 100),
                    Center(child: Text(locale.t('offline_note'))),
                  ])
                : _items.isEmpty
                    ? ListView(children: [
                        const SizedBox(height: 100),
                        Center(child: Text(locale.t('no_stock_items'))),
                      ])
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(12, 12, 12, 80),
                        itemCount: _items.length,
                        itemBuilder: (context, i) {
                          final item = _items[i];
                          return Card(
                            margin: const EdgeInsets.only(bottom: 10),
                            child: ListTile(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                              title: Text(item.medicineName, style: const TextStyle(fontWeight: FontWeight.w600)),
                              subtitle: Text('₹${item.price.toStringAsFixed(2)}'),
                              trailing: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text('${item.stockCount}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: PharmacyTheme.statusColor(item.status).withValues(alpha: 0.15),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      item.status,
                                      style: TextStyle(color: PharmacyTheme.statusColor(item.status), fontSize: 11, fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                ],
                              ),
                              onTap: () async {
                                await Navigator.of(context).push(
                                  MaterialPageRoute(builder: (_) => SellItemScreen(item: item)),
                                );
                                _load();
                              },
                            ),
                          );
                        },
                      ),
      ),
    );
  }
}
