import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/app_strings.dart';
import '../services/firebase_notification_service.dart';
import '../services/pharmacy_service.dart';
import '../services/secure_store.dart';
import '../theme.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _service = PharmacyService();
  bool _loading = true;
  String? _error;
  int _pendingOrders = 0;
  int _expiringSoon = 0;
  int _lowStock = 0;
  String _pharmacyName = '';

  @override
  void initState() {
    super.initState();
    // Re-sync the FCM token on every dashboard load too — matches
    // apps/mobile_app's approach (idempotent no-op if unchanged).
    unawaited(FirebaseNotificationService().syncTokenWithBackend());
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _service.getMyPharmacy(),
        _service.getQueue(),
        _service.getExpiring(),
        _service.getStock(),
      ]);
      final pharmacy = results[0] as Map<String, dynamic>;
      final queue = results[1] as List;
      final expiring = results[2] as List;
      final stock = results[3] as List;

      setState(() {
        _pharmacyName = pharmacy['name'] as String? ?? '';
        _pendingOrders = queue.length;
        _expiringSoon = expiring.length;
        _lowStock = stock.where((s) => s.status != 'Optimal').length;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _logout() async {
    await SecureStore().clearAll();
    if (mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      appBar: AppBar(
        title: Text(_pharmacyName.isNotEmpty ? _pharmacyName : locale.t('app_title')),
        actions: [
          IconButton(
            icon: const Icon(Icons.language),
            tooltip: locale.t('language'),
            onPressed: () => locale.setCode(locale.isTamil ? 'en' : 'ta'),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: locale.t('logout'),
            onPressed: _logout,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _buildError(locale)
                : _buildContent(locale),
      ),
    );
  }

  Widget _buildError(LocaleService locale) {
    return ListView(
      children: [
        const SizedBox(height: 120),
        Center(child: Text(locale.t('offline_note'))),
        const SizedBox(height: 16),
        Center(
          child: ElevatedButton(onPressed: _load, child: Text(locale.t('retry'))),
        ),
      ],
    );
  }

  Widget _buildContent(LocaleService locale) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(child: _StatCard(
              icon: Icons.receipt_long,
              label: locale.t('pending_orders'),
              value: _pendingOrders,
              color: PharmacyTheme.primaryGreen,
              onTap: () => context.go('/queue'),
            )),
            const SizedBox(width: 12),
            Expanded(child: _StatCard(
              icon: Icons.warning_amber_rounded,
              label: locale.t('expiring_soon'),
              value: _expiringSoon,
              color: PharmacyTheme.statusLow,
              onTap: () => context.go('/expiring'),
            )),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _StatCard(
              icon: Icons.inventory_2,
              label: locale.t('low_stock'),
              value: _lowStock,
              color: PharmacyTheme.statusOut,
              onTap: () => context.go('/shortages'),
            )),
            const SizedBox(width: 12),
            const Expanded(child: SizedBox()),
          ],
        ),
        const SizedBox(height: 28),
        _NavTile(
          icon: Icons.receipt_long,
          title: locale.t('order_queue'),
          onTap: () => context.go('/queue'),
        ),
        _NavTile(
          icon: Icons.medication,
          title: locale.t('stock_management'),
          onTap: () => context.go('/stock'),
        ),
        _NavTile(
          icon: Icons.event_busy,
          title: locale.t('expiry_alerts'),
          onTap: () => context.go('/expiring'),
        ),
        _NavTile(
          icon: Icons.production_quantity_limits,
          title: locale.t('shortage_alerts'),
          onTap: () => context.go('/shortages'),
        ),
        _NavTile(
          icon: Icons.storefront,
          title: locale.t('profile'),
          onTap: () => context.go('/profile'),
        ),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final int value;
  final Color color;
  final VoidCallback onTap;

  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color, size: 28),
              const SizedBox(height: 8),
              Text('$value', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: color)),
              Text(label, style: const TextStyle(fontSize: 13, color: Colors.black54)),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;

  const _NavTile({required this.icon, required this.title, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: Icon(icon, color: PharmacyTheme.primaryGreen, size: 28),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),
    );
  }
}
