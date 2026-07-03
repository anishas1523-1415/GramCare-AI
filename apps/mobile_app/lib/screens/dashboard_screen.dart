import 'package:flutter/material.dart';
import 'dart:ui';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/profile_service.dart';
import '../services/secure_store.dart';
import '../services/sync_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _sosInFlight = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      // Load profiles (offline-cached) and run a background wallet sync.
      final profiles = context.read<ProfileService>();
      await profiles.load();
      try {
        final me = await ApiService().client.get('/auth/me');
        final myId = me.data['id'] as int?;
        if (myId != null) {
          await SyncService().fullSync(myId);
        }
      } catch (_) {
        // Offline — queued records will sync next time we're online.
        await SyncService().pushUnsynced();
      }
    });
  }

  void _logout() async {
    await SecureStore().clearToken();
    if (mounted) {
      await context.read<ProfileService>().clearOnLogout();
    }
    if (mounted) context.go('/login');
  }

  /// Emergency SOS. Fixed vs. the previous implementation, which sent a
  /// payload the backend schema silently dropped (`location` instead of
  /// `location_text`), hardcoded patient_id '1', and never awaited or
  /// surfaced errors — unacceptable for a life-safety feature.
  /// GPS capture and hold-to-activate arrive with roadmap Phase 6.
  Future<void> _triggerSos() async {
    if (_sosInFlight) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Send Emergency SOS?'),
        content: const Text(
            'This will alert doctors and emergency responders immediately.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('SEND SOS'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _sosInFlight = true);
    final activeProfile = context.read<ProfileService>().active;
    try {
      await ApiService().client.post('/sos/trigger', data: {
        'location_text': 'Location unavailable (GPS pending Phase 6)',
        'severity': 'CRITICAL',
        'family_profile_id': activeProfile?.id,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('EMERGENCY SOS SENT — help has been alerted'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text(
                'SOS FAILED TO SEND. Please call emergency services directly (108).'),
            backgroundColor: Colors.red.shade900,
            duration: const Duration(seconds: 8),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _sosInFlight = false);
    }
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

    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            // Background blobs for subtle glassmorphism effect
            Positioned(
              top: -100,
              left: -100,
              child: Container(
                width: 300,
                height: 300,
                decoration: BoxDecoration(
                  color: const Color(0xFF4F46E5).withOpacity(0.3),
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
                      const Text(
                        'GramCare AI',
                        style: TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.w900,
                          color: Color(0xFF2D3748),
                          letterSpacing: -1,
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.logout, color: Colors.redAccent),
                        onPressed: _logout,
                      )
                    ],
                  ),
                  const SizedBox(height: 8),

                  // Active family member chip — tap to switch (planning doc:
                  // every feature acts for the selected member).
                  GestureDetector(
                    onTap: () => context.push('/profiles'),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE0E5EC),
                        borderRadius: BorderRadius.circular(30),
                        boxShadow: const [
                          BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(3, 3), blurRadius: 6),
                          BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-3, -3), blurRadius: 6),
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
                                ? 'Acting for: Myself'
                                : 'Acting for: ${profiles.active!.fullName}',
                            style: const TextStyle(
                                fontWeight: FontWeight.bold, color: Color(0xFF2D3748)),
                          ),
                          const SizedBox(width: 6),
                          const Icon(Icons.swap_horiz, size: 18, color: Color(0xFF718096)),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 32),

                  // Neumorphic Feature Grid
                  Expanded(
                    child: GridView.count(
                      crossAxisCount: 2,
                      crossAxisSpacing: 24,
                      mainAxisSpacing: 24,
                      children: [
                        GestureDetector(
                          onTap: () => context.push('/wallet'),
                          child: const NeumorphicCard(
                            icon: Icons.favorite,
                            title: 'Health Wallet',
                            iconColor: Color(0xFF4F46E5),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/triage'),
                          child: const NeumorphicCard(
                            icon: Icons.psychology,
                            title: 'Symptom Checker',
                            iconColor: Color(0xFF2DD4BF),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/scan'),
                          child: const NeumorphicCard(
                            icon: Icons.document_scanner,
                            title: 'Scan Prescription',
                            iconColor: Color(0xFF8B5CF6),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/pharmacy'),
                          child: const NeumorphicCard(
                            icon: Icons.local_pharmacy,
                            title: 'Find Medicine',
                            iconColor: Color(0xFF10B981),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/vitals'),
                          child: const NeumorphicCard(
                            icon: Icons.monitor_heart,
                            title: 'IoT Vitals',
                            iconColor: Color(0xFF3B82F6),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/reminders'),
                          child: const GlassmorphicCard(
                            icon: Icons.notifications_active,
                            title: 'Medicine Reminders',
                            iconColor: Color(0xFFEF4444),
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
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _sosInFlight ? null : _triggerSos,
        backgroundColor: Colors.red,
        icon: _sosInFlight
            ? const SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
            : const Icon(Icons.warning, color: Colors.white),
        label: const Text('EMERGENCY SOS',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
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
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFE0E5EC),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color(0xFFA3B1C6),
            offset: Offset(8, 8),
            blurRadius: 16,
          ),
          BoxShadow(
            color: Color(0xFFFFFFFF),
            offset: Offset(-8, -8),
            blurRadius: 16,
          ),
        ],
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              color: Color(0xFFE0E5EC),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Color(0xFFA3B1C6),
                  offset: Offset(4, 4),
                  blurRadius: 8,
                ),
                BoxShadow(
                  color: Color(0xFFFFFFFF),
                  offset: Offset(-4, -4),
                  blurRadius: 8,
                ),
              ],
            ),
            child: Icon(icon, size: 32, color: iconColor),
          ),
          const SizedBox(height: 16),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: Color(0xFF2D3748),
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
            color: Colors.white.withOpacity(0.2),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: Colors.white.withOpacity(0.4),
              width: 1.5,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.red.withOpacity(0.1),
                blurRadius: 24,
                spreadRadius: 4,
              ),
            ],
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, size: 32, color: iconColor),
              ),
              const SizedBox(height: 16),
              Text(
                title,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: iconColor,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
