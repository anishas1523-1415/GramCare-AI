import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../models/stock_item.dart';
import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../theme.dart';

/// The most-used screen in the app (planning doc): one big tap logs one
/// sale via POST /pharmacy/decrement/{id}. Optimistic UI update — the count
/// decrements instantly on tap, and syncs to the backend in the background;
/// on failure the local count is rolled back and the pharmacist is told to
/// retry, so the on-screen number never silently drifts from the server.
///
/// Also hosts "set end-of-day count" (POST /pharmacy/set_stock/{id}) and
/// "add stock / shipment" (POST /pharmacy/update_stock/{id}) since both are
/// natural companions to viewing/adjusting a single medicine's count.
class SellItemScreen extends StatefulWidget {
  final StockItem item;

  const SellItemScreen({super.key, required this.item});

  @override
  State<SellItemScreen> createState() => _SellItemScreenState();
}

class _SellItemScreenState extends State<SellItemScreen> {
  final _service = PharmacyService();
  late int _count;
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    _count = widget.item.stockCount;
  }

  Future<void> _sellOne() async {
    if (_count <= 0) return;
    HapticFeedback.lightImpact();
    final previous = _count;
    setState(() => _count = _count - 1); // optimistic, instant feedback
    try {
      final newCount = await _service.decrementStock(widget.item.id);
      if (mounted) setState(() => _count = newCount);
    } catch (e) {
      if (mounted) {
        setState(() => _count = previous); // roll back
        final locale = context.read<LocaleService>();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('error_generic'))));
      }
    }
  }

  Future<void> _showSetCountDialog(LocaleService locale) async {
    final controller = TextEditingController(text: '$_count');
    final result = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(locale.t('set_count')),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          autofocus: true,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text(locale.t('cancel'))),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, int.tryParse(controller.text)),
            child: Text(locale.t('set')),
          ),
        ],
      ),
    );
    if (result == null || result < 0) return;
    setState(() => _syncing = true);
    try {
      await _service.setStock(widget.item.id, result);
      setState(() {
        _count = result;
        _syncing = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _syncing = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('error_generic'))));
      }
    }
  }

  Future<void> _showAddStockDialog(LocaleService locale) async {
    final controller = TextEditingController();
    final result = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(locale.t('add_stock')),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          autofocus: true,
          decoration: InputDecoration(hintText: locale.t('initial_stock')),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text(locale.t('cancel'))),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, int.tryParse(controller.text)),
            child: Text(locale.t('save')),
          ),
        ],
      ),
    );
    if (result == null || result <= 0) return;
    setState(() => _syncing = true);
    try {
      await _service.updateStock(widget.item.id, result);
      setState(() {
        _count = _count + result;
        _syncing = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _syncing = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('error_generic'))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final status = _count <= 0 ? 'Out of Stock' : (_count < 50 ? 'Low' : 'Optimal');
    return Scaffold(
      appBar: AppBar(title: Text(widget.item.medicineName)),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    Text(locale.t('remaining'), style: const TextStyle(color: Colors.black54)),
                    const SizedBox(height: 8),
                    Text('$_count', style: TextStyle(fontSize: 56, fontWeight: FontWeight.bold, color: PharmacyTheme.statusColor(status))),
                    Container(
                      margin: const EdgeInsets.only(top: 8),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: PharmacyTheme.statusColor(status).withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(status, style: TextStyle(color: PharmacyTheme.statusColor(status), fontWeight: FontWeight.bold)),
                    ),
                    if (_syncing) ...[
                      const SizedBox(height: 8),
                      const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            // The core one-tap-per-sale button — large, single tap, no
            // confirmation dialog by design (speed at a busy counter).
            Expanded(
              child: GestureDetector(
                onTap: _count > 0 ? _sellOne : null,
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: _count > 0 ? PharmacyTheme.primaryGreen : Colors.grey.shade400,
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.touch_app, color: Colors.white, size: 56),
                        const SizedBox(height: 12),
                        Text(
                          locale.t('tap_to_sell'),
                          style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _showSetCountDialog(locale),
                    icon: const Icon(Icons.edit),
                    label: Text(locale.t('set_count')),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _showAddStockDialog(locale),
                    icon: const Icon(Icons.add_box),
                    label: Text(locale.t('add_stock')),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
