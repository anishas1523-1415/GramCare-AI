import 'package:flutter/material.dart';

/// Green pharmacy theme — per the planning doc's requirement that every
/// module carry its own distinct visual identity ("Pharmacy module ->
/// green color theme; pharmacy-related animated elements e.g. tablets/
/// medicine-themed animations and transitions").
class PharmacyTheme {
  static const Color primaryGreen = Color(0xFF2E7D5B);
  static const Color darkGreen = Color(0xFF1B5E3F);
  static const Color lightGreen = Color(0xFFE3F5EC);
  static const Color accentMint = Color(0xFF52C48A);

  static const Color statusOptimal = Color(0xFF2E7D5B);
  static const Color statusLow = Color(0xFFE8A33D);
  static const Color statusOut = Color(0xFFD64545);

  static ThemeData get themeData {
    final base = ColorScheme.fromSeed(
      seedColor: primaryGreen,
      brightness: Brightness.light,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: base.copyWith(
        primary: primaryGreen,
        secondary: accentMint,
      ),
      scaffoldBackgroundColor: const Color(0xFFF4FAF7),
      appBarTheme: const AppBarTheme(
        backgroundColor: primaryGreen,
        foregroundColor: Colors.white,
        centerTitle: false,
        elevation: 0,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryGreen,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 24),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: primaryGreen,
        foregroundColor: Colors.white,
      ),
      cardTheme: CardThemeData(
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        color: Colors.white,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
      ),
      fontFamily: 'Roboto',
    );
  }

  static Color statusColor(String status) {
    switch (status) {
      case 'Out of Stock':
        return statusOut;
      case 'Low':
        return statusLow;
      default:
        return statusOptimal;
    }
  }

  /// Dark mode (planning doc UI/UX requirement) — same green pharmacy
  /// identity, following the device's system setting via ThemeMode.system.
  static ThemeData get darkThemeData {
    const darkSurface = Color(0xFF10160F);
    const darkCard = Color(0xFF19241A);
    const accentGreen = Color(0xFF52C48A);

    final base = ColorScheme.fromSeed(
      seedColor: primaryGreen,
      brightness: Brightness.dark,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: base.copyWith(
        primary: accentGreen,
        secondary: accentMint,
        surface: darkSurface,
      ),
      scaffoldBackgroundColor: darkSurface,
      appBarTheme: const AppBarTheme(
        backgroundColor: darkGreen,
        foregroundColor: Colors.white,
        centerTitle: false,
        elevation: 0,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accentGreen,
          foregroundColor: Colors.black,
          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 24),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: accentGreen,
        foregroundColor: Colors.black,
      ),
      cardTheme: CardThemeData(
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        color: darkCard,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: darkCard,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
      ),
      fontFamily: 'Roboto',
    );
  }
}
