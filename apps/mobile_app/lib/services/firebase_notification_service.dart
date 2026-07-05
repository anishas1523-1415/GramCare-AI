import 'dart:convert';
import 'dart:io';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../router.dart';
import 'api_service.dart';
import 'secure_store.dart';

/// Four Android notification channels, one per notification category, so a
/// user can mute/lower "Pharmacy" or "General" chatter without silencing
/// SOS emergency alerts. IDs must exactly match the backend's
/// `_CHANNEL_BY_TYPE` mapping in `core/notifications.py` — Android decides
/// which channel a background/terminated notification lands in based on the
/// `channel_id` the *backend* puts in the FCM payload's AndroidConfig, so
/// the two sides must agree on IDs even though they're defined independently.
const AndroidNotificationChannel _emergencyChannel = AndroidNotificationChannel(
  'gramcare_emergency_channel',
  'GramCare Emergency',
  description: 'Critical SOS alerts and emergency escalation updates.',
  importance: Importance.high,
);

const AndroidNotificationChannel _appointmentsChannel = AndroidNotificationChannel(
  'gramcare_appointments_channel',
  'GramCare Appointments',
  description: 'Appointment reminders and confirmations.',
  importance: Importance.defaultImportance,
);

const AndroidNotificationChannel _pharmacyChannel = AndroidNotificationChannel(
  'gramcare_pharmacy_channel',
  'GramCare Pharmacy',
  description: 'Prescription-ready and pharmacy order updates.',
  importance: Importance.defaultImportance,
);

const AndroidNotificationChannel _generalChannel = AndroidNotificationChannel(
  'gramcare_general_channel',
  'GramCare General',
  description: 'Doctor messages and other app updates.',
  importance: Importance.low,
);

const List<AndroidNotificationChannel> _allChannels = [
  _emergencyChannel,
  _appointmentsChannel,
  _pharmacyChannel,
  _generalChannel,
];

/// Maps a notification's `data['type']` to the channel it should be shown
/// on — mirrors [FirebaseNotificationService._navigateForNotification]'s
/// switch, and must stay in lockstep with the backend's `_CHANNEL_BY_TYPE`.
AndroidNotificationChannel _channelForType(String? type) {
  switch (type) {
    case 'sos_alert':
      return _emergencyChannel;
    case 'appointment_reminder':
      return _appointmentsChannel;
    case 'pharmacy_ready':
    case 'pharmacy_update':
      return _pharmacyChannel;
    default:
      return _generalChannel;
  }
}

/// Must be a top-level (or static) function, not a class method — the
/// Firebase plugin registers this as an isolate entry point that Android can
/// invoke on a background isolate while the app process isn't running.
///
/// `@pragma('vm:entry-point')` stops the Dart compiler's tree-shaker from
/// stripping this function in release builds since nothing in the normal
/// call graph appears to reference it directly.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Background isolates get no implicit Firebase context — every plugin
  // that touches Firebase (Analytics here) needs its own initializeApp call.
  await Firebase.initializeApp();
  try {
    await FirebaseAnalytics.instance.logEvent(
      name: 'notification_received_background',
      parameters: {'type': message.data['type'] ?? 'unknown'},
    );
  } catch (_) {
    // Analytics must never crash the background handler.
  }
  debugPrint('[FCM background] ${message.messageId}: ${message.data}');
}

/// Owns the whole Firebase Cloud Messaging lifecycle for GramCare AI:
/// init (Core/Messaging/Crashlytics/Analytics/local notifications), runtime
/// permission, token issuance + backend registration, token refresh, and
/// foreground/background/terminated message handling with type-based
/// navigation and per-category notification channels (see [_channelForType]).
///
/// Navigation mapping (documented since this patient-facing app has no
/// literal "SOS screen" / "Doctor dashboard" — those are web_portal/
/// react_dashboard concepts): notification `data.type` routes to the
/// closest existing screen:
///   sos_alert                       -> /emergency-contacts
///   appointment_reminder            -> /reminders
///   doctor_message, prescription_*  -> /wallet   (Health Wallet)
///   pharmacy_ready, pharmacy_update -> /pharmacy  (Pharmacy Search)
///   anything else / unknown         -> /  (Dashboard)
class FirebaseNotificationService {
  static final FirebaseNotificationService _instance =
      FirebaseNotificationService._internal();
  factory FirebaseNotificationService() => _instance;
  FirebaseNotificationService._internal();

  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  /// Call once, before runApp(). Sets up everything that doesn't depend on
  /// the user being logged in yet: Crashlytics hooks, the local-notification
  /// channel, and the message listeners. Token registration with the
  /// backend is deliberately NOT done here — see [syncTokenWithBackend],
  /// called from the login screen and the dashboard instead, since it needs
  /// an authenticated JWT that may not exist yet at process start.
  Future<void> initialize() async {
    if (_initialized) return;
    _initialized = true;

    await Firebase.initializeApp();

    // --- Crashlytics: catch both framework (widget build/layout) errors and
    // errors outside the Flutter framework (e.g. thrown in a raw Future). ---
    FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;
    PlatformDispatcher.instance.onError = (error, stack) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      return true;
    };
    // Debug builds default this to false upstream; explicit for clarity —
    // we always want crash collection, including from debug/test devices
    // used during rollout to rural clinics.
    await FirebaseCrashlytics.instance.setCrashlyticsCollectionEnabled(true);

    // --- Local notifications (foreground display) ---------------------
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings();
    await _localNotifications.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
      onDidReceiveNotificationResponse: (NotificationResponse response) {
        final payload = response.payload;
        if (payload == null || payload.isEmpty) return;
        try {
          final data = Map<String, dynamic>.from(jsonDecode(payload) as Map);
          _logEvent('notification_tapped', {'type': data['type'] ?? 'unknown', 'source': 'foreground_local'});
          _navigateForNotification(data);
        } catch (e) {
          debugPrint('Failed to decode local notification payload: $e');
        }
      },
    );
    final androidPlugin = _localNotifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    for (final channel in _allChannels) {
      await androidPlugin?.createNotificationChannel(channel);
    }

    // Must be registered before runApp per FlutterFire's documented setup —
    // handles messages that arrive while the app process is not running.
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

    // --- Foreground messages: FCM does NOT show a system notification for
    // these automatically on Android, so we render one ourselves. ---------
    FirebaseMessaging.onMessage.listen(_showForegroundNotification);

    // --- App was backgrounded (not terminated) and the user tapped the
    // system notification to bring it back to the foreground. ------------
    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      _logEvent('notification_tapped', {'type': message.data['type'] ?? 'unknown', 'source': 'background_opened_app'});
      _navigateForNotification(message.data);
    });

    // --- App was fully terminated and launched BY tapping a notification.
    // Delay slightly so GoRouter's own auth redirect (SecureStore lookup)
    // has settled before we issue a second, competing navigation. ---------
    final initialMessage = await FirebaseMessaging.instance.getInitialMessage();
    if (initialMessage != null) {
      _logEvent('notification_tapped', {'type': initialMessage.data['type'] ?? 'unknown', 'source': 'terminated_launch'});
      Future.delayed(const Duration(milliseconds: 700), () {
        _navigateForNotification(initialMessage.data);
      });
    }

    // Fires only when the token actually rotates (app reinstall, Firebase
    // token expiry/rotation, app data cleared, etc.) — safe to always POST.
    FirebaseMessaging.instance.onTokenRefresh.listen((newToken) async {
      _logEvent('fcm_token_refreshed', {});
      await _registerTokenWithBackend(newToken);
    });
  }

  /// Call after a successful login, and again on every app start while
  /// already authenticated (dashboard's initState) — idempotent by design:
  /// skips the network call entirely if the current token already matches
  /// the last one this install successfully registered.
  Future<void> syncTokenWithBackend() async {
    try {
      final settings = await _requestPermission();
      _logEvent('notification_permission_requested', {
        'status': settings.authorizationStatus.name,
      });

      final token = await FirebaseMessaging.instance.getToken();
      if (token == null) {
        debugPrint('FirebaseMessaging.getToken() returned null — cannot register.');
        return;
      }
      _logEvent('fcm_token_obtained', {});
      await _registerTokenWithBackend(token);
    } catch (e, st) {
      // Notification setup must never block login/dashboard load.
      debugPrint('FCM token sync failed (non-fatal): $e');
      await FirebaseCrashlytics.instance.recordError(e, st, fatal: false);
    }
  }

  Future<NotificationSettings> _requestPermission() {
    return FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      // Rural connectivity is often intermittent — provisional delivery
      // (iOS quiet notifications before an explicit prompt) is preferable
      // to no delivery while we wait for an explicit user decision.
      provisional: false,
    );
  }

  /// Duplicate handling: compares against the last token this install
  /// actually succeeded in registering, and skips the POST if unchanged —
  /// the backend's own dedup (by user_id + device_id + platform, plus a
  /// cross-user deactivation pass) makes a redundant POST harmless, but
  /// avoiding it saves a request on every login/dashboard load for the
  /// common case where the token hasn't rotated.
  Future<void> _registerTokenWithBackend(String token) async {
    final lastRegistered = await SecureStore().getLastRegisteredFcmToken();
    if (lastRegistered == token) {
      debugPrint('FCM token unchanged since last registration — skipping POST.');
      return;
    }

    final hasSession = await SecureStore().getToken() != null;
    if (!hasSession) {
      // Not logged in yet (e.g. app cold-start before login) — token will
      // be registered right after login instead via syncTokenWithBackend().
      return;
    }

    try {
      final deviceId = await SecureStore().getOrCreateDeviceId();
      await ApiService().client.post('/auth/fcm-token', data: {
        'fcm_token': token,
        'device_id': deviceId,
        'platform': Platform.isIOS ? 'ios' : 'android',
      });
      await SecureStore().setLastRegisteredFcmToken(token);
      _logEvent('fcm_token_registered_backend', {});
    } catch (e, st) {
      debugPrint('Failed to register FCM token with backend: $e');
      await FirebaseCrashlytics.instance.recordError(e, st, fatal: false);
    }
  }

  Future<void> _showForegroundNotification(RemoteMessage message) async {
    _logEvent('notification_received_foreground', {'type': message.data['type'] ?? 'unknown'});

    final notification = message.notification;
    if (notification == null) return; // data-only message: nothing to show

    final channel = _channelForType(message.data['type'] as String?);
    await _localNotifications.show(
      notification.hashCode,
      notification.title,
      notification.body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          channel.id,
          channel.name,
          channelDescription: channel.description,
          icon: '@mipmap/ic_launcher',
          importance: channel.importance,
          priority: channel.importance == Importance.high
              ? Priority.high
              : Priority.defaultPriority,
        ),
        iOS: const DarwinNotificationDetails(),
      ),
      // Round-trips the FCM data payload to onDidReceiveNotificationResponse
      // so a tap on this locally-shown notification routes the same way a
      // tap on a background/terminated system notification does.
      payload: jsonEncode(message.data),
    );
  }

  void _navigateForNotification(Map<String, dynamic> data) {
    final type = data['type'] as String?;
    switch (type) {
      case 'sos_alert':
        appRouter.go('/emergency-contacts');
        break;
      case 'appointment_reminder':
        appRouter.go('/reminders');
        break;
      case 'doctor_message':
      case 'prescription_issued':
        appRouter.go('/wallet');
        break;
      case 'pharmacy_ready':
      case 'pharmacy_update':
        appRouter.go('/pharmacy');
        break;
      default:
        appRouter.go('/');
    }
  }

  void _logEvent(String name, Map<String, Object> parameters) {
    // Analytics is best-effort observability, never allowed to throw into
    // caller code (e.g. during login or the background isolate).
    FirebaseAnalytics.instance.logEvent(name: name, parameters: parameters).catchError((e) {
      debugPrint('Analytics logEvent($name) failed: $e');
    });
  }
}
