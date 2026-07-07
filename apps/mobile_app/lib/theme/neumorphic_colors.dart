import 'package:flutter/material.dart';

/// Theme-aware neumorphic palette for the patient app.
///
/// The app's entire visual language is soft-UI neumorphism: a flat base
/// color plus a light/dark shadow pair that fakes an embossed or pressed
/// look. Every screen used to hardcode these four colors directly, which
/// meant there was no way to offer a dark mode without a full rewrite.
///
/// This uses Flutter's [ThemeExtension] mechanism (the supported way to add
/// custom, theme-aware values to a [ThemeData]) so screens can look up
/// `Theme.of(context).extension<NeumorphicColors>()!` and automatically get
/// the right palette for the current [Brightness], including following the
/// device's system setting via `ThemeMode.system`.
///
/// Per-module accent colors (teal for triage, green for pharmacy, indigo
/// primary, red for emergency/SOS, etc.) are deliberately NOT part of this
/// palette — those are brand/identity colors that stay constant across
/// light and dark mode.
@immutable
class NeumorphicColors extends ThemeExtension<NeumorphicColors> {
  const NeumorphicColors({
    required this.background,
    required this.shadowLight,
    required this.shadowDark,
    required this.foreground,
    required this.foregroundMuted,
    required this.cardBackground,
  });

  /// The flat neumorphic base surface (scaffold background, panel fill).
  final Color background;

  /// The "raised" shadow — light source side of a neumorphic BoxShadow pair.
  final Color shadowLight;

  /// The "recessed" shadow — dark side of a neumorphic BoxShadow pair.
  final Color shadowDark;

  /// Primary text/icon color.
  final Color foreground;

  /// Secondary/muted text color (captions, hints, subtitles).
  final Color foregroundMuted;

  /// Background for elevated cards/containers sitting on top of [background].
  final Color cardBackground;

  /// Current light-mode palette — matches the values every screen used to
  /// hardcode, so light mode stays pixel-identical after migration.
  static const NeumorphicColors light = NeumorphicColors(
    background: Color(0xFFE0E5EC),
    shadowLight: Color(0xFFFFFFFF),
    shadowDark: Color(0xFFA3B1C6),
    foreground: Color(0xFF2D3748),
    foregroundMuted: Color(0xFF718096),
    cardBackground: Color(0xFFE0E5EC),
  );

  /// Dark-mode palette — shares the same dark neumorphic values used by the
  /// web portal (`apps/web_portal/src/app/globals.css`) for a consistent
  /// GramCare family look across platforms.
  static const NeumorphicColors dark = NeumorphicColors(
    background: Color(0xFF1e1e24),
    shadowLight: Color(0xFF2c2c35),
    shadowDark: Color(0xFF101013),
    foreground: Color(0xFFe2e8f0),
    foregroundMuted: Color(0xFFA0AEC0),
    cardBackground: Color(0xFF1e1e24),
  );

  @override
  NeumorphicColors copyWith({
    Color? background,
    Color? shadowLight,
    Color? shadowDark,
    Color? foreground,
    Color? foregroundMuted,
    Color? cardBackground,
  }) {
    return NeumorphicColors(
      background: background ?? this.background,
      shadowLight: shadowLight ?? this.shadowLight,
      shadowDark: shadowDark ?? this.shadowDark,
      foreground: foreground ?? this.foreground,
      foregroundMuted: foregroundMuted ?? this.foregroundMuted,
      cardBackground: cardBackground ?? this.cardBackground,
    );
  }

  @override
  NeumorphicColors lerp(ThemeExtension<NeumorphicColors>? other, double t) {
    if (other is! NeumorphicColors) {
      return this;
    }
    return NeumorphicColors(
      background: Color.lerp(background, other.background, t)!,
      shadowLight: Color.lerp(shadowLight, other.shadowLight, t)!,
      shadowDark: Color.lerp(shadowDark, other.shadowDark, t)!,
      foreground: Color.lerp(foreground, other.foreground, t)!,
      foregroundMuted:
          Color.lerp(foregroundMuted, other.foregroundMuted, t)!,
      cardBackground: Color.lerp(cardBackground, other.cardBackground, t)!,
    );
  }
}
