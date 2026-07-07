import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/appointment.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/doctor_session.dart';
import '../services/firebase_notification_service.dart';
import '../theme/app_theme.dart';
import '../widgets/status_badge.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  List<Appointment> _appointments = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final session = context.read<DoctorSession>();
      if (session.doctorId == null) {
        await session.loadProfile();
      }
      // Re-sync FCM token on every dashboard load (idempotent no-op if unchanged) —
      // covers the case where login happened in a previous app session.
      unawaited(FirebaseNotificationService().syncTokenWithBackend());
      await _loadQueue();
    });
  }

  Future<void> _loadQueue() async {
    final session = context.read<DoctorSession>();
    final doctorId = session.doctorId;
    if (doctorId == null) {
      setState(() {
        _loading = false;
        _error = context.read<LocaleService>().t('error_generic');
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await ApiService().client.get('/appointments/doctor/$doctorId/queue');
      final list = (res.data as List)
          .map((j) => Appointment.fromJson(j as Map<String, dynamic>))
          .toList()
        ..sort((a, b) => a.scheduledAt.compareTo(b.scheduledAt));
      setState(() {
        _appointments = list;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = context.read<LocaleService>().t('error_generic');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    final session = context.watch<DoctorSession>();

    return Scaffold(
      appBar: AppBar(
        title: Text(locale.t('dashboard')),
        actions: [
          IconButton(
            icon: const Icon(Icons.language),
            tooltip: locale.t('language'),
            onPressed: () => locale.setCode(locale.isTamil ? 'en' : 'ta'),
          ),
        ],
      ),
      drawer: _AppDrawer(locale: locale),
      body: RefreshIndicator(
        onRefresh: _loadQueue,
        child: _buildBody(locale, session),
      ),
    );
  }

  Widget _buildBody(LocaleService locale, DoctorSession session) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return ListView(
        children: [
          const SizedBox(height: 120),
          Icon(Icons.error_outline, size: 48, color: Colors.grey.shade400),
          const SizedBox(height: 12),
          Center(child: Text(_error!)),
          const SizedBox(height: 12),
          Center(
            child: OutlinedButton(onPressed: _loadQueue, child: Text(locale.t('retry'))),
          ),
        ],
      );
    }
    if (_appointments.isEmpty) {
      return ListView(
        children: [
          const SizedBox(height: 120),
          Icon(Icons.event_available, size: 56, color: Colors.grey.shade400),
          const SizedBox(height: 16),
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                locale.t('no_appointments'),
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.black54),
              ),
            ),
          ),
        ],
      );
    }

    final dateFmt = DateFormat('EEE, MMM d  •  hh:mm a');

    return ListView.builder(
      padding: const EdgeInsets.only(top: 8, bottom: 24),
      itemCount: _appointments.length,
      itemBuilder: (context, index) {
        final appt = _appointments[index];
        return Card(
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            leading: CircleAvatar(
              backgroundColor: AppTheme.skyBlue,
              child: Text(
                '#${appt.patientId}',
                style: const TextStyle(fontSize: 11, color: AppTheme.deepBlue, fontWeight: FontWeight.bold),
              ),
            ),
            title: Text(
              dateFmt.format(appt.scheduledAt.toLocal()),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: appt.triageSummary != null && appt.triageSummary!.isNotEmpty
                ? Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      appt.triageSummary!,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.black54, fontSize: 13),
                    ),
                  )
                : null,
            trailing: StatusBadge(status: appt.status, locale: locale),
            onTap: () => context.push('/patient/${appt.patientId}', extra: appt),
          ),
        );
      },
    );
  }
}

class _AppDrawer extends StatelessWidget {
  final LocaleService locale;
  const _AppDrawer({required this.locale});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<DoctorSession>();
    final profile = session.profile;
    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            DrawerHeader(
              decoration: const BoxDecoration(color: AppTheme.primaryBlue),
              child: Align(
                alignment: Alignment.bottomLeft,
                child: Text(
                  profile?.fullName ?? locale.t('app_title'),
                  style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.dashboard_outlined),
              title: Text(locale.t('dashboard')),
              onTap: () {
                Navigator.pop(context);
                context.go('/');
              },
            ),
            ListTile(
              leading: const Icon(Icons.calendar_month_outlined),
              title: Text(locale.t('my_schedule')),
              onTap: () {
                Navigator.pop(context);
                context.push('/schedule');
              },
            ),
            ListTile(
              leading: const Icon(Icons.warning_amber_rounded, color: AppTheme.criticalRed),
              title: Text(locale.t('critical_alerts')),
              onTap: () {
                Navigator.pop(context);
                context.push('/alerts');
              },
            ),
            ListTile(
              leading: const Icon(Icons.person_outline),
              title: Text(locale.t('profile')),
              onTap: () {
                Navigator.pop(context);
                context.push('/profile');
              },
            ),
          ],
        ),
      ),
    );
  }
}
