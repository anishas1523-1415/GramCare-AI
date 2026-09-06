import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/appointment.dart';
import '../models/doctor.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../theme/neumorphic_colors.dart';

/// This patient's own bookings (GET /appointments/my) — previously this app
/// had no booking flow at all, so there was nothing to list here either.
/// A CONFIRMED appointment scheduled for now (within a 15-minute window,
/// same as the join-window convention doctor_app's appointment queue
/// implies) surfaces a "Join Video Call" action into the same
/// /video-call/:appointmentId screen the doctor side already has.
class MyAppointmentsScreen extends StatefulWidget {
  const MyAppointmentsScreen({super.key});

  @override
  State<MyAppointmentsScreen> createState() => _MyAppointmentsScreenState();
}

class _MyAppointmentsScreenState extends State<MyAppointmentsScreen> {
  bool _loading = true;
  String? _error;
  List<Appointment> _appointments = [];
  final Map<int, String> _doctorNames = {};

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
      final results = await Future.wait([
        ApiService().client.get('/appointments/my'),
        ApiService().client.get('/doctors'),
      ]);
      final appts = (results[0].data as List)
          .map((e) => Appointment.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      final doctors = (results[1].data as List)
          .map((e) => DoctorPublic.fromJson(Map<String, dynamic>.from(e as Map)));
      setState(() {
        _appointments = appts;
        _doctorNames
          ..clear()
          ..addEntries(doctors.map((d) => MapEntry(d.id, d.fullName)));
      });
    } catch (_) {
      setState(() => _error = 'error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _canJoinNow(Appointment a) {
    if (a.status != 'CONFIRMED') return false;
    final now = DateTime.now();
    final diff = a.scheduledAt.difference(now).inMinutes;
    // Joinable from 15 minutes before the scheduled time until 60 minutes
    // after (covers a doctor running late without leaving the window open
    // indefinitely for a long-past appointment).
    return diff <= 15 && diff >= -60;
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'CONFIRMED':
        return const Color(0xFF2DD4BF);
      case 'COMPLETED':
        return const Color(0xFF10B981);
      case 'CANCELLED':
        return Colors.red;
      default:
        return const Color(0xFFF59E0B);
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
        title: Text(locale.t('my_appointments'), style: TextStyle(color: neu.foreground, fontWeight: FontWeight.bold)),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? ListView(children: [const SizedBox(height: 120), Center(child: Text(locale.t('offline_note')))])
                  : _appointments.isEmpty
                      ? ListView(children: [
                          const SizedBox(height: 120),
                          Center(child: Text(locale.t('no_appointments_yet'), style: TextStyle(color: neu.foregroundMuted))),
                        ])
                      : ListView.builder(
                          padding: const EdgeInsets.all(20),
                          itemCount: _appointments.length,
                          itemBuilder: (context, i) {
                            final a = _appointments[i];
                            final canJoin = _canJoinNow(a);
                            return Container(
                              margin: const EdgeInsets.only(bottom: 14),
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: neu.background,
                                borderRadius: BorderRadius.circular(16),
                                border: Border(left: BorderSide(color: _statusColor(a.status), width: 5)),
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
                                        child: Text(
                                          _doctorNames[a.doctorId] ?? '${locale.t('doctor')} #${a.doctorId}',
                                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: neu.foreground),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: _statusColor(a.status).withValues(alpha: 0.15),
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Text(a.status, style: TextStyle(color: _statusColor(a.status), fontWeight: FontWeight.bold, fontSize: 11)),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Text(a.scheduledAt.toLocal().toString().substring(0, 16),
                                      style: TextStyle(fontSize: 13, color: neu.foregroundMuted)),
                                  if (a.triageSummary != null && a.triageSummary!.isNotEmpty) ...[
                                    const SizedBox(height: 8),
                                    Text(a.triageSummary!, style: TextStyle(fontSize: 13, color: neu.foreground)),
                                  ],
                                  if (canJoin) ...[
                                    const SizedBox(height: 12),
                                    SizedBox(
                                      width: double.infinity,
                                      child: ElevatedButton.icon(
                                        onPressed: () => context.push('/video-call/${a.id}'),
                                        icon: const Icon(Icons.videocam),
                                        label: Text(locale.t('join_video_call')),
                                        style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF2DD4BF)),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            );
                          },
                        ),
        ),
      ),
    );
  }
}
