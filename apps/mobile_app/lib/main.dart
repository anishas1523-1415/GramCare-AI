import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'models/health_record.dart';
import 'router.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Hive Offline-First Database
  await Hive.initFlutter();
  Hive.registerAdapter(HealthRecordAdapter());
  await Hive.openBox<HealthRecord>('health_wallet');
  
  runApp(const GramCareApp());
}

class GramCareApp extends StatelessWidget {
  const GramCareApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'GramCare AI',
      theme: ThemeData(
        scaffoldBackgroundColor: const Color(0xFFE0E5EC),
        primaryColor: const Color(0xFF4F46E5),
        fontFamily: 'Inter',
        useMaterial3: true,
      ),
      routerConfig: appRouter,
    );
  }
}
