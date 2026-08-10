import 'package:flutter/material.dart';

import '../services/app_strings.dart';
import '../theme/app_theme.dart';

/// Small colored pill showing an appointment/SOS status, used across the
/// dashboard queue and patient detail screens.
class StatusBadge extends StatelessWidget {
  final String status;
  final LocaleService locale;

  const StatusBadge({super.key, required this.status, required this.locale});

  String _label() {
    switch (status) {
      case 'PENDING':
        return locale.t('status_pending');
      case 'CONFIRMED':
        return locale.t('status_confirmed');
      case 'COMPLETED':
        return locale.t('status_completed');
      case 'CANCELLED':
        return locale.t('status_cancelled');
      default:
        return status;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.statusColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        _label(),
        style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12),
      ),
    );
  }
}
