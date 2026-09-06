import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/doctor.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../theme/neumorphic_colors.dart';

/// Consultation booking. Previously entirely absent from this app — the
/// dashboard had no way to reach a doctor at all, even though the web
/// portal's /book flow (choose doctor -> pick slot -> pay -> confirm) has
/// existed for a while. Same backend endpoints: GET /doctors,
/// GET /doctors/{id}/slots, POST /appointments/book.
///
/// SCOPING NOTE: booking a doctor whose consultation_fee is 0 works fully
/// here. A paid doctor's booking is enforced server-side to require a
/// verified Razorpay payment_order_id (_book_appointment_core in
/// modules/appointments/router.py) — integrating Razorpay's native SDK is a
/// separate, larger piece of work this screen doesn't attempt yet, so a
/// paid doctor is shown with its fee and a note to complete that booking on
/// the web portal for now, rather than either hiding paid doctors entirely
/// or presenting a payment step that doesn't actually work.
class BookConsultationScreen extends StatefulWidget {
  const BookConsultationScreen({super.key});

  @override
  State<BookConsultationScreen> createState() => _BookConsultationScreenState();
}

enum _Step { doctor, slot, done }

class _BookConsultationScreenState extends State<BookConsultationScreen> {
  _Step _step = _Step.doctor;
  bool _loading = true;
  String? _error;
  List<DoctorPublic> _doctors = [];
  List<DoctorSlot> _slots = [];
  DoctorPublic? _doctor;
  DoctorSlot? _slot;
  final _symptomsController = TextEditingController();
  bool _booking = false;

  @override
  void initState() {
    super.initState();
    _loadDoctors();
  }

  @override
  void dispose() {
    _symptomsController.dispose();
    super.dispose();
  }

  Future<void> _loadDoctors() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await ApiService().client.get('/doctors');
      final all = (res.data as List)
          .map((e) => DoctorPublic.fromJson(Map<String, dynamic>.from(e as Map)))
          .where((d) => d.isAvailable)
          .toList();
      setState(() => _doctors = all);
    } catch (_) {
      setState(() => _error = 'error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _chooseDoctor(DoctorPublic d) async {
    setState(() {
      _doctor = d;
      _loading = true;
      _error = null;
    });
    try {
      final res = await ApiService().client.get('/doctors/${d.id}/slots');
      final slots = (res.data as List)
          .map((e) => DoctorSlot.fromJson(Map<String, dynamic>.from(e as Map)))
          .where((s) => !s.isBooked)
          .toList();
      setState(() {
        _slots = slots;
        _step = _Step.slot;
      });
    } catch (_) {
      setState(() => _error = 'error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _book(LocaleService locale) async {
    if (_doctor == null || _slot == null) return;
    setState(() {
      _booking = true;
      _error = null;
    });
    final active = context.read<ProfileService>().active;
    try {
      await ApiService().client.post('/appointments/book', data: {
        'doctor_id': _doctor!.id,
        'slot_id': _slot!.id,
        'triage_summary': _symptomsController.text.trim().isEmpty ? null : _symptomsController.text.trim(),
        'family_profile_id': active?.id,
        'payment_order_id': null,
      });
      setState(() => _step = _Step.done);
    } on DioException catch (e) {
      final detail = e.response?.data is Map ? (e.response?.data as Map)['detail'] : null;
      setState(() => _error = detail is String ? detail : locale.t('booking_failed'));
    } catch (_) {
      setState(() => _error = locale.t('booking_failed'));
    } finally {
      if (mounted) setState(() => _booking = false);
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
        title: Text(locale.t('book_consultation'), style: TextStyle(color: neu.foreground, fontWeight: FontWeight.bold)),
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _buildStep(neu, locale),
      ),
    );
  }

  Widget _buildStep(NeumorphicColors neu, LocaleService locale) {
    switch (_step) {
      case _Step.doctor:
        return _doctorList(neu, locale);
      case _Step.slot:
        return _slotPicker(neu, locale);
      case _Step.done:
        return _confirmation(neu, locale);
    }
  }

  Widget _doctorList(NeumorphicColors neu, LocaleService locale) {
    if (_doctors.isEmpty) {
      return Center(child: Text(locale.t('no_doctors_available'), style: TextStyle(color: neu.foregroundMuted)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: _doctors.length,
      itemBuilder: (context, i) {
        final d = _doctors[i];
        final free = d.consultationFee <= 0;
        return GestureDetector(
          onTap: () => _chooseDoctor(d),
          child: Container(
            margin: const EdgeInsets.only(bottom: 14),
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: neu.background,
              borderRadius: BorderRadius.circular(18),
              boxShadow: [
                BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(d.fullName, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: neu.foreground)),
                      Text(d.specialty, style: const TextStyle(color: Color(0xFF2DD4BF), fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      Text(
                        '${d.qualifications != null ? '${d.qualifications} · ' : ''}${d.experienceYears} ${locale.t('yrs_experience')}',
                        style: TextStyle(fontSize: 12, color: neu.foregroundMuted),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      free ? locale.t('free') : '₹${d.consultationFee.toStringAsFixed(0)}',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Color(0xFF4F46E5)),
                    ),
                    if (!free)
                      Text(locale.t('pay_on_web'), style: TextStyle(fontSize: 10, color: neu.foregroundMuted)),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _slotPicker(NeumorphicColors neu, LocaleService locale) {
    final doctor = _doctor!;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextButton.icon(
            onPressed: () => setState(() { _step = _Step.doctor; _slot = null; }),
            icon: const Icon(Icons.arrow_back, size: 16),
            label: Text(locale.t('choose_different_doctor')),
          ),
          Text('${locale.t('available_times_for')} ${doctor.fullName}',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: neu.foreground)),
          const SizedBox(height: 16),
          if (_slots.isEmpty)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(locale.t('no_open_slots'), style: TextStyle(color: neu.foregroundMuted)),
            )
          else
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: _slots.map((s) {
                final selected = _slot?.id == s.id;
                return GestureDetector(
                  onTap: () => setState(() => _slot = s),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: selected ? const Color(0xFF2DD4BF) : neu.background,
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: selected
                          ? null
                          : [
                              BoxShadow(color: neu.shadowDark, offset: const Offset(3, 3), blurRadius: 6),
                              BoxShadow(color: neu.shadowLight, offset: const Offset(-3, -3), blurRadius: 6),
                            ],
                    ),
                    child: Text(
                      '${_weekday(s.startTime)} ${_time(s.startTime)}',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: selected ? Colors.white : neu.foreground),
                    ),
                  ),
                );
              }).toList(),
            ),
          const SizedBox(height: 24),
          Text(locale.t('describe_problem_for_doctor'), style: TextStyle(fontWeight: FontWeight.w600, color: neu.foreground)),
          const SizedBox(height: 8),
          Container(
            decoration: BoxDecoration(
              color: neu.background,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
              ],
            ),
            child: TextField(
              controller: _symptomsController,
              maxLines: 3,
              decoration: InputDecoration(
                hintText: locale.t('symptoms_hint_example'),
                border: InputBorder.none,
                contentPadding: const EdgeInsets.all(16),
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Text(_error!, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
          ],
          const SizedBox(height: 24),
          GestureDetector(
            onTap: (_slot == null || _booking) ? null : () => _book(locale),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 18),
              decoration: BoxDecoration(
                color: _slot == null ? const Color(0xFF4F46E5).withValues(alpha: 0.4) : const Color(0xFF4F46E5),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Center(
                child: _booking
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : Text(
                        doctor.consultationFee <= 0 ? locale.t('confirm_free_consultation') : locale.t('confirm_booking'),
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _confirmation(NeumorphicColors neu, LocaleService locale) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle, size: 72, color: Color(0xFF10B981)),
            const SizedBox(height: 20),
            Text(locale.t('appointment_confirmed'), style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: neu.foreground)),
            const SizedBox(height: 8),
            Text(
              '${_doctor?.fullName ?? ''} · ${_slot != null ? '${_weekday(_slot!.startTime)} ${_time(_slot!.startTime)}' : ''}',
              textAlign: TextAlign.center,
              style: TextStyle(color: neu.foregroundMuted),
            ),
            const SizedBox(height: 28),
            GestureDetector(
              onTap: () => context.go('/appointments'),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                decoration: BoxDecoration(color: const Color(0xFF4F46E5), borderRadius: BorderRadius.circular(14)),
                child: Text(locale.t('view_my_appointments'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _weekday(DateTime dt) => const ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][dt.weekday - 1];
  String _time(DateTime dt) {
    final h = dt.hour % 12 == 0 ? 12 : dt.hour % 12;
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m ${dt.hour >= 12 ? 'PM' : 'AM'}';
  }
}
