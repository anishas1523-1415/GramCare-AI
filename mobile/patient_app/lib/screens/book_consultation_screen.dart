import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:razorpay_flutter/razorpay_flutter.dart';

import '../models/doctor.dart';
import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/profile_service.dart';
import '../theme/neumorphic_colors.dart';

/// Consultation booking. Previously entirely absent from this app — the
/// dashboard had no way to reach a doctor at all, even though the web
/// portal's /book flow (choose doctor -> pick slot -> pay -> confirm) has
/// existed for a while. Same backend endpoints: GET /doctors,
/// GET /doctors/{id}/slots, POST /appointments/book, and — for a paid
/// doctor — the same POST /payments/create-order + /payments/verify pair
/// RazorpayCheckout.tsx drives on the web portal.
///
/// The backend itself decides mock vs. real: create-order returns
/// `is_mock: true` whenever RAZORPAY_KEY_ID/SECRET aren't configured
/// server-side (modules/payments/router.py), in which case this screen
/// verifies with the same "mock_sig_{order_id}_..." signature the web
/// client uses instead of opening the native checkout — no Razorpay
/// dashboard/native SDK involved at all in that mode. When real credentials
/// are configured, the same public key_id the web bundles as
/// NEXT_PUBLIC_RAZORPAY_KEY_ID is used to open the native Razorpay Checkout
/// (key_id is meant to be public by Razorpay's own design — only
/// key_secret is sensitive, and that never leaves the backend).
class BookConsultationScreen extends StatefulWidget {
  const BookConsultationScreen({super.key});

  @override
  State<BookConsultationScreen> createState() => _BookConsultationScreenState();
}

enum _Step { doctor, slot, done }

// Same test-mode publishable key the web portal bundles as
// NEXT_PUBLIC_RAZORPAY_KEY_ID (frontend/patient_web_portal/.env.production).
// A publishable key is safe to ship in the APK, but going live should not
// mean editing Dart and hoping nobody forgets, so a build can override it:
//   flutter build apk --release --dart-define=RAZORPAY_KEY_ID=rzp_live_xxxx
// The test key stays the default so a plain build still works out of the box.
const String _razorpayKeyId = String.fromEnvironment(
  'RAZORPAY_KEY_ID',
  defaultValue: 'rzp_test_T981BiZ3S5Jcof',
);

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
  late final Razorpay _razorpay;

  @override
  void initState() {
    super.initState();
    _loadDoctors();
    _razorpay = Razorpay();
    _razorpay.on(Razorpay.EVENT_PAYMENT_SUCCESS, _onPaymentSuccess);
    _razorpay.on(Razorpay.EVENT_PAYMENT_ERROR, _onPaymentError);
  }

  @override
  void dispose() {
    _symptomsController.dispose();
    _razorpay.clear();
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

  /// Entry point for the confirm button — routes to the payment flow first
  /// for a paid doctor, or books directly for a free one.
  Future<void> _confirm(LocaleService locale) async {
    if (_doctor == null || _slot == null) return;
    if (_doctor!.consultationFee <= 0) {
      await _bookAppointment(locale, paymentOrderId: null);
      return;
    }
    await _startPayment(locale);
  }

  Future<void> _bookAppointment(LocaleService locale, {required String? paymentOrderId}) async {
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
        'payment_order_id': paymentOrderId,
      });
      if (mounted) setState(() => _step = _Step.done);
    } on DioException catch (e) {
      final detail = e.response?.data is Map ? (e.response?.data as Map)['detail'] : null;
      if (mounted) setState(() => _error = detail is String ? detail : locale.t('booking_failed'));
    } catch (_) {
      if (mounted) setState(() => _error = locale.t('booking_failed'));
    } finally {
      if (mounted) setState(() => _booking = false);
    }
  }

  Future<void> _startPayment(LocaleService locale) async {
    setState(() {
      _booking = true;
      _error = null;
    });
    try {
      final orderRes = await ApiService().client.post('/payments/create-order', data: {
        'amount': _doctor!.consultationFee,
      });
      final order = orderRes.data as Map;
      final orderId = order['order_id'] as String;
      final isMock = order['is_mock'] as bool? ?? false;

      if (isMock) {
        // Mock gateway (no RAZORPAY_KEY_ID/SECRET configured server-side):
        // same signature convention RazorpayCheckout.tsx uses, verified by
        // the same POST /payments/verify — no native checkout involved.
        final mockPaymentId = 'mock_pay_${DateTime.now().millisecondsSinceEpoch}';
        final verifyRes = await ApiService().client.post('/payments/verify', data: {
          'razorpay_order_id': orderId,
          'razorpay_payment_id': mockPaymentId,
          'razorpay_signature': 'mock_sig_${orderId}_valid',
        });
        if ((verifyRes.data as Map)['status'] == 'SUCCESS') {
          await _bookAppointment(locale, paymentOrderId: orderId);
        } else if (mounted) {
          setState(() {
            _error = locale.t('payment_verification_failed');
            _booking = false;
          });
        }
        return;
      }

      // Real gateway — open the native Razorpay Checkout. Prefill with the
      // signed-in patient's real details, same as the web checkout.
      String prefillName = '';
      String prefillEmail = '';
      String prefillPhone = '';
      try {
        final me = await ApiService().client.get('/auth/me');
        final data = me.data as Map;
        prefillName = (data['full_name'] as String?) ?? (data['username'] as String?) ?? '';
        prefillEmail = (data['email'] as String?) ?? '';
        prefillPhone = (data['phone'] as String?) ?? '';
      } catch (_) {
        // Prefill is a convenience, not a requirement — proceed without it.
      }

      _pendingOrderId = orderId;
      setState(() => _booking = false); // the checkout UI itself is the "in progress" state now
      _razorpay.open({
        'key': _razorpayKeyId,
        'amount': order['amount'],
        'currency': order['currency'] ?? 'INR',
        'name': 'GramCare AI',
        'description': 'Telehealth Consultation',
        'order_id': orderId,
        'prefill': {
          'contact': prefillPhone.isNotEmpty ? prefillPhone : '9999999999',
          'email': prefillEmail,
          'name': prefillName,
        },
        'theme': {'color': '#4F46E5'},
      });
    } on DioException catch (e) {
      final detail = e.response?.data is Map ? (e.response?.data as Map)['detail'] : null;
      if (mounted) {
        setState(() {
          _error = detail is String ? detail : locale.t('payment_init_failed');
          _booking = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = locale.t('payment_init_failed');
          _booking = false;
        });
      }
    }
  }

  String? _pendingOrderId;

  Future<void> _onPaymentSuccess(PaymentSuccessResponse response) async {
    final locale = context.read<LocaleService>();
    final orderId = response.orderId ?? _pendingOrderId;
    if (orderId == null) return;
    try {
      final verifyRes = await ApiService().client.post('/payments/verify', data: {
        'razorpay_order_id': orderId,
        'razorpay_payment_id': response.paymentId,
        'razorpay_signature': response.signature,
      });
      if ((verifyRes.data as Map)['status'] == 'SUCCESS') {
        await _bookAppointment(locale, paymentOrderId: orderId);
      } else if (mounted) {
        setState(() => _error = locale.t('payment_verification_failed'));
      }
    } catch (_) {
      // The charge may have gone through on Razorpay's side even though this
      // call failed (dropped connection, backend restart) — POST /webhook
      // is the server-side safety net that marks it PAID independently, so
      // this is a "couldn't confirm", not necessarily a real failure.
      if (mounted) setState(() => _error = locale.t('payment_confirm_network_error'));
    }
  }

  void _onPaymentError(PaymentFailureResponse response) {
    final locale = context.read<LocaleService>();
    if (!mounted) return;
    setState(() {
      _error = response.code == Razorpay.PAYMENT_CANCELLED
          ? locale.t('payment_cancelled')
          : (response.message?.isNotEmpty == true ? response.message! : locale.t('payment_failed'));
    });
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
                      Text(locale.t('per_consult'), style: TextStyle(fontSize: 10, color: neu.foregroundMuted)),
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
            onTap: (_slot == null || _booking) ? null : () => _confirm(locale),
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
                        doctor.consultationFee <= 0
                            ? locale.t('confirm_free_consultation')
                            : '${locale.t('pay_and_book')} ₹${doctor.consultationFee.toStringAsFixed(0)}',
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
              onTap: () => context.pushReplacement('/appointments'),
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
