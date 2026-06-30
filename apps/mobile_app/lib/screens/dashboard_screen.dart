import 'package:flutter/material.dart';
import 'dart:ui';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/health_record.dart';
import '../services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  // Simulate adding a record offline
  void _addMockRecord() {
    final box = Hive.box<HealthRecord>('health_wallet');
    final record = HealthRecord(
      patientName: 'Jane Doe',
      symptoms: 'Mild fever, dry cough',
      aiSeverity: 'LOW',
      timestamp: DateTime.now(),
    );
    box.add(record);
    
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Saved to Health Wallet (Offline)'),
        backgroundColor: Color(0xFF10B981),
      )
    );
  }

  void _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    if (mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
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
                  const Text(
                    'Offline-First Healthcare Ecosystem',
                    style: TextStyle(
                      fontSize: 16,
                      color: Color(0xFF718096),
                    ),
                  ),
                  const SizedBox(height: 48),
                  
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
                            iconColor: Color(0xFFEF4444), // keeping the styling consistent
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
        onPressed: () {
          // Trigger global SOS
          ApiService().client.post('/sos/trigger', data: {
            'patient_id': '1', // Hardcoded demo ID
            'location': 'Rural Clinic Alpha',
            'severity': 'CRITICAL'
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('EMERGENCY SOS BROADCASTED TO ALL DOCTORS'),
              backgroundColor: Colors.red,
            )
          );
        },
        backgroundColor: Colors.red,
        icon: const Icon(Icons.warning, color: Colors.white),
        label: const Text('EMERGENCY SOS', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
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
