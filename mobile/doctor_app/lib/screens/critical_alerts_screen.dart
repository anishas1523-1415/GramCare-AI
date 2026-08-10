import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/sos_alert.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/app_theme.dart';

/// Read-only feed of active SOS emergencies (GET /sos/active), for doctors
/// to "review critical updates on the move" per the planning doc. The
/// primary responder surface is the web Hospital Emergency Desk; this
/// screen just needs to surface the same active list and auto-refresh.
class CriticalAlertsScreen extends StatefulWidget {
  const CriticalAlertsScreen({super.key});

  @override
  State<CriticalAlertsScreen> createState() => _CriticalAlertsScreenState();
}

class _CriticalAlertsScreenState extends State<CriticalAlertsScreen> {
  List<SosAlert> _alerts = [];
  bool _loading = true;
  String? _error;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadAlerts();
    // Periodic refresh — SOS alerts are time-critical; a doctor glancing at
    // this screen should see new alerts without manually pulling to refresh.
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) => _loadAlerts(silent: true));
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadAlerts({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final res = await ApiService().client.get('/sos/active');
      final list = (res.data as List).map((j) => SosAlert.fromJson(j as Map<String, dynamic>)).toList();
      if (!mounted) return;
      setState(() {
        _alerts = list;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        if (!silent) _error = context.read<LocaleService>().t('error_generic');
      });
    }
  }

  Color _severityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return AppTheme.criticalRed;
      case 'HIGH':
        return AppTheme.pendingAmber;
      default:
        return AppTheme.confirmedBlue;
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();

    return Scaffold(
      appBar: AppBar(title: Text(locale.t('critical_alerts'))),
      body: RefreshIndicator(
        onRefresh: () => _loadAlerts(),
        child: _buildBody(locale),
      ),
    );
  }

  Widget _buildBody(LocaleService locale) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return ListView(
        children: [
          const SizedBox(height: 100),
          Center(child: Text(_error!)),
          const SizedBox(height: 12),
          Center(child: OutlinedButton(onPressed: () => _loadAlerts(), child: Text(locale.t('retry')))),
        ],
      );
    }
    if (_alerts.isEmpty) {
      return ListView(
        children: [
          const SizedBox(height: 100),
          Icon(Icons.check_circle_outline, size: 56, color: Colors.grey.shade400),
          const SizedBox(height: 16),
          Center(child: Text(locale.t('no_active_alerts'), style: const TextStyle(color: Colors.black54))),
        ],
      );
    }

    final dateFmt = DateFormat('MMM d, hh:mm a');
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _alerts.length,
      itemBuilder: (context, index) {
        final alert = _alerts[index];
        final color = _severityColor(alert.severity);
        return Card(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: BorderSide(color: color.withValues(alpha: 0.4)),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: color),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${locale.t('sos_severity')}: ${alert.severity}',
                        style: TextStyle(fontWeight: FontWeight.bold, color: color),
                      ),
                    ),
                    Text(dateFmt.format(alert.createdAt.toLocal()), style: const TextStyle(fontSize: 12, color: Colors.black54)),
                  ],
                ),
                const SizedBox(height: 8),
                Text('Patient ID: ${alert.patientId}'),
                if (alert.locationText != null && alert.locationText!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.location_on_outlined, size: 16, color: Colors.black54),
                      const SizedBox(width: 4),
                      Expanded(child: Text(alert.locationText!, style: const TextStyle(fontSize: 13))),
                    ],
                  ),
                ],
                const SizedBox(height: 4),
                Text('${locale.t('sos_status')}: ${alert.status}', style: const TextStyle(fontSize: 13)),
              ],
            ),
          ),
        );
      },
    );
  }
}
