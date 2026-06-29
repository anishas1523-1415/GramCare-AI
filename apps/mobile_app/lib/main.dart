import 'package:flutter/material.dart';
import 'dart:ui';
import 'package:hive_flutter/hive_flutter.dart';
import 'models/health_record.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Hive Offline-First Database
  await Hive.initFlutter();
  
  // Register the generated adapter
  Hive.registerAdapter(HealthRecordAdapter());
  
  // Open the NoSQL Box for Health Records
  await Hive.openBox<HealthRecord>('health_wallet');
  
  runApp(const GramCareApp());
}

class GramCareApp extends StatelessWidget {
  const GramCareApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GramCare AI',
      theme: ThemeData(
        scaffoldBackgroundColor: const Color(0xFFE0E5EC),
        primaryColor: const Color(0xFF4F46E5),
        fontFamily: 'Inter',
        useMaterial3: true,
      ),
      home: const NeoGlassDashboard(),
    );
  }
}

class NeoGlassDashboard extends StatefulWidget {
  const NeoGlassDashboard({super.key});

  @override
  State<NeoGlassDashboard> createState() => _NeoGlassDashboardState();
}

class _NeoGlassDashboardState extends State<NeoGlassDashboard> {
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
                  const SizedBox(height: 40),
                  const Text(
                    'GramCare AI',
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFF2D3748),
                      letterSpacing: -1,
                    ),
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
                          onTap: _addMockRecord,
                          child: const NeumorphicCard(
                            icon: Icons.favorite,
                            title: 'Health Wallet',
                            iconColor: Color(0xFF4F46E5),
                          ),
                        ),
                        const NeumorphicCard(
                          icon: Icons.psychology,
                          title: 'Symptom Checker',
                          iconColor: Color(0xFF2DD4BF),
                        ),
                        const NeumorphicCard(
                          icon: Icons.medical_services,
                          title: 'Doctor Portal',
                          iconColor: Color(0xFF3B82F6),
                        ),
                        const GlassmorphicCard(
                          icon: Icons.warning,
                          title: 'Emergency SOS',
                          iconColor: Color(0xFFEF4444),
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
            decoration: BoxDecoration(
              color: const Color(0xFFE0E5EC),
              shape: BoxShape.circle,
              boxShadow: const [
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
