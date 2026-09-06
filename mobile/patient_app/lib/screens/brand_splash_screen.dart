import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../services/secure_store.dart';

/// Animated brand intro, shown once at cold start. flutter_native_splash
/// already paints the same icon instantly at the OS level before Flutter
/// even loads — this picks up right where that leaves off with a real
/// Flutter animation (the icon settles in with a soft pop, then the
/// wordmark/tagline rise in beneath it) instead of a jarring hard cut
/// straight to the login screen or dashboard. Self-navigates once both the
/// animation and the auth-token check are done, whichever finishes last.
class BrandSplashScreen extends StatefulWidget {
  const BrandSplashScreen({super.key});

  @override
  State<BrandSplashScreen> createState() => _BrandSplashScreenState();
}

class _BrandSplashScreenState extends State<BrandSplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _iconScale;
  late final Animation<double> _iconOpacity;
  late final Animation<double> _textOpacity;
  late final Animation<Offset> _textSlide;

  static const _bg = Color(0xFFECF8EF);
  static const _dark = Color(0xFF1B5E3F);
  static const _accent = Color(0xFF2E7D5B);

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
    _iconScale = Tween<double>(begin: 0.72, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: const Interval(0.0, 0.7, curve: Curves.easeOutBack)),
    );
    _iconOpacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: const Interval(0.0, 0.45, curve: Curves.easeOut)),
    );
    _textOpacity = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: const Interval(0.45, 1.0, curve: Curves.easeOut)),
    );
    _textSlide = Tween<Offset>(begin: const Offset(0, 0.15), end: Offset.zero).animate(
      CurvedAnimation(parent: _controller, curve: const Interval(0.45, 1.0, curve: Curves.easeOutCubic)),
    );
    _controller.forward();
    _navigateNext();
  }

  Future<void> _navigateNext() async {
    final results = await Future.wait([
      SecureStore().getToken(),
      Future.delayed(const Duration(milliseconds: 1700)),
    ]);
    final token = results[0] as String?;
    if (!mounted) return;
    context.go(token != null ? '/' : '/login');
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedBuilder(
              animation: _controller,
              builder: (context, child) => Opacity(
                opacity: _iconOpacity.value,
                child: Transform.scale(scale: _iconScale.value, child: child),
              ),
              child: Container(
                width: 132,
                height: 132,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(30),
                  boxShadow: [
                    BoxShadow(color: _accent.withValues(alpha: 0.22), blurRadius: 34, spreadRadius: 2),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(30),
                  child: Image.asset('assets/icon.png', fit: BoxFit.cover),
                ),
              ),
            ),
            const SizedBox(height: 28),
            AnimatedBuilder(
              animation: _controller,
              builder: (context, child) => Opacity(
                opacity: _textOpacity.value,
                child: SlideTransition(position: _textSlide, child: child),
              ),
              child: Column(
                children: [
                  RichText(
                    text: const TextSpan(
                      style: TextStyle(fontSize: 27, fontWeight: FontWeight.w800),
                      children: [
                        TextSpan(text: 'GramCare ', style: TextStyle(color: _dark)),
                        TextSpan(text: 'AI', style: TextStyle(color: _accent)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'PATIENT',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, letterSpacing: 3, color: _accent),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Care Closer to Home',
                    style: TextStyle(fontSize: 13.5, color: Colors.black.withValues(alpha: 0.48), letterSpacing: 0.3),
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
