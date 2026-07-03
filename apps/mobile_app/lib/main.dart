import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:provider/provider.dart';

import 'models/health_record.dart';
import 'router.dart';
import 'services/profile_service.dart';
import 'services/secure_store.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lift any legacy plain-text token into the platform keystore first.
  await SecureStore().migrateLegacyToken();

  // Initialize Hive Offline-First Database — the health wallet box is now
  // AES-encrypted with a key held in the platform keystore (clinical data
  // was previously stored in plaintext on disk).
  await Hive.initFlutter();
  Hive.registerAdapter(HealthRecordAdapter());
  final hiveKey = await SecureStore().getOrCreateHiveKey();
  await Hive.openBox<HealthRecord>(
    'health_wallet',
    encryptionCipher: HiveAesCipher(hiveKey),
  );

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => ProfileService()),
      ],
      child: const GramCareApp(),
    ),
  );
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
