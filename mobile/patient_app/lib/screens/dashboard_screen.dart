import 'dart:async';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/firebase_notification_service.dart';
import '../services/profile_service.dart';
import '../services/secure_store.dart';
import '../services/sos_service.dart';
import '../services/sync_service.dart';
import '../theme/neumorphic_colors.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _sosInFlight = false;
  double _holdProgress = 0;
  Timer? _holdTimer;
  final stt.SpeechToText _sosSpeech = stt.SpeechToText();
  String _sosVoiceNote = '';
  List<Map<String, dynamic>> _recallAlerts = [];

  static const _holdDuration = Duration(seconds: 3);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      // Load profiles (offline-cached) and run a background wallet sync.
      final profiles = context.read<ProfileService>();
      await profiles.load();
      // Warm the emergency-contact cache so the offline SMS fallback works
      // even if the SOS moment itself has no connectivity.
      SosService().cachedContactNumbers();
      // Covers the "already logged in, app relaunched" path — login_screen
      // only fires this right after a fresh login, so a returning session
      // (app reopened, token still valid) needs its own registration point.
      // syncTokenWithBackend() is a no-op network-wise if the token hasn't
      // changed since the last successful registration.
      unawaited(FirebaseNotificationService().syncTokenWithBackend());
      try {
        final me = await ApiService().client.get('/auth/me');
        final myId = me.data['id'] as int?;
        if (myId != null) {
          await SyncService().fullSync(myId);
        }
      } catch (_) {
        await SyncService().pushUnsynced();
      }
      _loadRecallAlerts();
    });
  }

  // Batch Recall Alerts (planning doc): "பார்மசிஸ்ட்களும் யூசர்களும் உடனே
  // அலர்ட் ஆகணும்" — patients must be alerted too, not just pharmacists.
  Future<void> _loadRecallAlerts() async {
    try {
      final res = await ApiService().client.get('/pharmacy/recalls/affecting-me');
      if (mounted) setState(() => _recallAlerts = List<Map<String, dynamic>>.from(res.data as List));
    } catch (_) {
      // Silent — this is a supplementary alert, not core dashboard function.
    }
  }

  @override
  void dispose() {
    _holdTimer?.cancel();
    _sosSpeech.stop();
    super.dispose();
  }

  void _logout() async {
    await SecureStore().clearToken();
    if (mounted) {
      await context.read<ProfileService>().clearOnLogout();
    }
    if (mounted) context.go('/login');
  }

  // --- Hold-to-activate SOS (planning doc: "Hold for 3 seconds" guard
  // against accidental / child presses) --------------------------------
  //
  // The planning doc also asks the AI Voice Assistant to ask "what
  // happened?" and bundle the on-device transcription into the alert
  // ("அந்த வாய்ஸை டெக்ஸ்டா மாத்தி ... அலர்ட்டோட சேர்த்து அனுப்பும்") — but
  // a medical SOS "must happen in a fraction of a second", so we don't ask
  // a separate question and wait. Instead, listening starts the instant the
  // hold begins and runs concurrently with the 3-second accidental-press
  // guard; whatever's been said by the time the hold completes rides along
  // as the voice note, at zero added latency.
  void _startHold() {
    if (_sosInFlight) return;
    final s = context.read<LocaleService>();
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    const tick = Duration(milliseconds: 100);
    int elapsed = 0;
    _sosVoiceNote = '';
    _listenForSosNote(s);
    _holdTimer?.cancel();
    _holdTimer = Timer.periodic(tick, (timer) {
      elapsed += tick.inMilliseconds;
      setState(() => _holdProgress = elapsed / _holdDuration.inMilliseconds);
      if (elapsed >= _holdDuration.inMilliseconds) {
        timer.cancel();
        setState(() => _holdProgress = 0);
        _fireSos();
      }
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(s.t('hold_to_sos_listening')), duration: _holdDuration),
    );
  }

  Future<void> _listenForSosNote(LocaleService s) async {
    try {
      final available = await _sosSpeech.initialize();
      if (!available || !mounted) return;
      await _sosSpeech.listen(
        listenOptions: stt.SpeechListenOptions(
          partialResults: true,
          localeId: s.isTamil ? 'ta-IN' : 'en-IN',
        ),
        onResult: (result) => _sosVoiceNote = result.recognizedWords,
      );
    } catch (_) {
      // Never let a mic/permission failure block the emergency flow.
    }
  }

  void _cancelHold() {
    _holdTimer?.cancel();
    _sosSpeech.stop();
    _sosVoiceNote = '';
    if (_holdProgress > 0) setState(() => _holdProgress = 0);
  }

  Future<void> _fireSos() async {
    if (_sosInFlight) return;
    setState(() => _sosInFlight = true);
    final s = context.read<LocaleService>();
    final activeProfile = context.read<ProfileService>().active;
    await _sosSpeech.stop();

    final result = await SosService().trigger(
      familyProfileId: activeProfile?.id,
      voiceNote: _sosVoiceNote.isNotEmpty ? _sosVoiceNote : null,
    );

    if (!mounted) return;
    if (result.sent) {
      context.push('/sos-active?lat=${result.position?.latitude ?? 0}&lng=${result.position?.longitude ?? 0}');
    } else if (result.smsFallbackUsed) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(s.t('sos_sms_fallback')),
        backgroundColor: Colors.orange.shade800,
        duration: const Duration(seconds: 6),
      ));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(s.t('sos_failed')),
        backgroundColor: Colors.red.shade900,
        duration: const Duration(seconds: 8),
      ));
    }
    setState(() => _sosInFlight = false);
  }

  Color _profileColor(ProfileService profiles) {
    final tag = profiles.active?.colorTag;
    if (tag != null && tag.startsWith('#') && tag.length == 7) {
      return Color(int.parse('FF${tag.substring(1)}', radix: 16));
    }
    return const Color(0xFF4F46E5);
  }

  @override
  Widget build(BuildContext context) {
    final profiles = context.watch<ProfileService>();
    final s = context.watch<LocaleService>();
    final neu = Theme.of(context).extension<NeumorphicColors>()!;

    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            Positioned(
              top: -100,
              left: -100,
              child: Container(
                width: 300,
                height: 300,
                decoration: BoxDecoration(
                  color: const Color(0xFF4F46E5).withValues(alpha: 0.3),
                  shape: BoxShape.circle,
                ),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 50, sigmaY: 50),
                  child: Container(color: Colors.transparent),
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        s.t('app_title'),
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.w900,
                          color: neu.foreground,
                          letterSpacing: -1,
                        ),
                      ),
                      Row(children: [
                        // Language toggle (Tamil-first per planning doc)
                        TextButton(
                          onPressed: () => s.setCode(s.isTamil ? 'en' : 'ta'),
                          child: Text(s.isTamil ? 'EN' : 'தமிழ்',
                              style: const TextStyle(fontWeight: FontWeight.bold)),
                        ),
                        IconButton(
                          tooltip: s.t('emergency_contacts'),
                          icon: const Icon(Icons.contact_phone, color: Color(0xFFEF4444)),
                          onPressed: () => context.push('/emergency-contacts'),
                        ),
                        IconButton(
                          icon: const Icon(Icons.logout, color: Colors.redAccent),
                          onPressed: _logout,
                        ),
                      ]),
                    ],
                  ),
                  const SizedBox(height: 8),

                  GestureDetector(
                    onTap: () => context.push('/profiles'),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      decoration: BoxDecoration(
                        color: neu.background,
                        borderRadius: BorderRadius.circular(30),
                        boxShadow: [
                          BoxShadow(color: neu.shadowDark, offset: const Offset(3, 3), blurRadius: 6),
                          BoxShadow(color: neu.shadowLight, offset: const Offset(-3, -3), blurRadius: 6),
                        ],
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CircleAvatar(
                            radius: 14,
                            backgroundColor: _profileColor(profiles),
                            child: Text(
                              profiles.active?.initials ?? 'ME',
                              style: const TextStyle(
                                  fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            profiles.active == null
                                ? s.t('acting_for_self')
                                : '${s.t('acting_for')}: ${profiles.active!.fullName}',
                            style: TextStyle(
                                fontWeight: FontWeight.bold, color: neu.foreground),
                          ),
                          const SizedBox(width: 6),
                          Icon(Icons.swap_horiz, size: 18, color: neu.foregroundMuted),
                        ],
                      ),
                    ),
                  ),

                  if (_recallAlerts.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    ..._recallAlerts.map((r) => Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: Colors.red.shade50,
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: Colors.red.shade300),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.warning_amber_rounded, color: Colors.red.shade700, size: 22),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${s.t('medicine_recall_alert')}: ${r['medicine_name']}',
                                      style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red.shade800, fontSize: 13),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      r['reason'] as String? ?? '',
                                      style: TextStyle(color: Colors.red.shade700, fontSize: 12),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        )),
                  ],

                  const SizedBox(height: 32),

                  Expanded(
                    child: GridView.count(
                      crossAxisCount: 2,
                      crossAxisSpacing: 24,
                      mainAxisSpacing: 24,
                      children: [
                        GestureDetector(
                          onTap: () => context.push('/wallet'),
                          child: NeumorphicCard(
                            icon: Icons.favorite,
                            title: s.t('health_wallet'),
                            iconColor: const Color(0xFF4F46E5),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/triage'),
                          child: NeumorphicCard(
                            icon: Icons.psychology,
                            title: s.t('symptom_checker'),
                            iconColor: const Color(0xFF2DD4BF),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/scan'),
                          child: NeumorphicCard(
                            icon: Icons.document_scanner,
                            title: s.t('scan_prescription'),
                            iconColor: const Color(0xFF8B5CF6),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/pharmacy'),
                          child: NeumorphicCard(
                            icon: Icons.local_pharmacy,
                            title: s.t('find_medicine'),
                            iconColor: const Color(0xFF10B981),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/vitals'),
                          child: NeumorphicCard(
                            icon: Icons.monitor_heart,
                            title: s.t('iot_vitals'),
                            iconColor: const Color(0xFF3B82F6),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/reminders'),
                          child: GlassmorphicCard(
                            icon: Icons.notifications_active,
                            title: s.t('medicine_reminders'),
                            iconColor: const Color(0xFFEF4444),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      // Hold-to-activate SOS: long-press 3 seconds (accidental-press guard),
      // progress ring shows the hold state.
      floatingActionButton: GestureDetector(
        onLongPressStart: (_) => _startHold(),
        onLongPressEnd: (_) => _cancelHold(),
        onLongPressCancel: _cancelHold,
        onTap: () {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(s.t('hold_to_sos'))),
          );
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          decoration: BoxDecoration(
            color: Colors.red,
            borderRadius: BorderRadius.circular(30),
            boxShadow: [
              BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_sosInFlight)
                const SizedBox(
                    width: 20, height: 20,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
              else if (_holdProgress > 0)
                SizedBox(
                  width: 20, height: 20,
                  child: CircularProgressIndicator(
                      value: _holdProgress, color: Colors.white, strokeWidth: 3),
                )
              else
                const Icon(Icons.warning, color: Colors.white),
              const SizedBox(width: 8),
              Text(s.t('emergency_sos'),
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold)),
            ],
          ),
        ),
      ),
    );
  }
}

class NeumorphicCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final Color iconColor;

  const NeumorphicCard({
    super.key,
    required this.icon,
    required this.title,
    required this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    return Container(
      decoration: BoxDecoration(
        color: neu.background,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(color: neu.shadowDark, offset: const Offset(8, 8), blurRadius: 16),
          BoxShadow(color: neu.shadowLight, offset: const Offset(-8, -8), blurRadius: 16),
        ],
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: neu.background,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
                BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
              ],
            ),
            child: Icon(icon, size: 32, color: iconColor),
          ),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Text(
              title,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: neu.foreground,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class GlassmorphicCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final Color iconColor;

  const GlassmorphicCard({
    super.key,
    required this.icon,
    required this.title,
    required this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.2),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: Colors.white.withValues(alpha: 0.4), width: 1.5),
            boxShadow: [
              BoxShadow(color: Colors.red.withValues(alpha: 0.1), blurRadius: 24, spreadRadius: 4),
            ],
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, size: 32, color: iconColor),
              ),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Text(
                  title,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: iconColor,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
