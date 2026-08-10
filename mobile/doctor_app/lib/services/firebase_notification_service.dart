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

/// Two Android notification channels for the doctor app: Critical (SOS +
/// escalations doctors must "review on the move" per the planning doc) and
/// Appointments (new bookings/status changes in their queue). Channel IDs
/// are distinct from apps/mobile_app's so both apps can coexist on a
/// reviewer's device without colliding, but must still match whatever the
/// backend's `_CHANNEL_BY_TYPE` sends for this app's registered tokens.
const AndroidNotificationChannel _criticalChannel = AndroidNotificationChannel(
  'gramcare_doctor_critical_channel',
  'GramCare Doctor Critical Alerts',
  description: 'Active SOS emergencies and escalations.',
  importance: Importance.high,
);

const AndroidNotificationChannel _appointmentsChannel = AndroidNotificationChannel(
  'gramcare_doctor_appointments_channel',
  'GramCare Doctor Appointments',
  description: 'New bookings and appointment status updates.',
  importance: Importance.defaultImportance,
);

const List<AndroidNotificationChannel> _allChannels = [
  _criticalChannel,
  _appointmentsChannel,
];

AndroidNotificationChannel _channelForType(String? type) {
  switch (type) {
    case 'sos_alert':
      return _criticalChannel;
    case 'appointment_reminder':
    case 'appointment_booked':
    default:
      return _appointmentsChannel;
  }
}

/// Must be a top-level function — Firebase registers it as a background
/// isolate entry point. `@pragma('vm:entry-point')` stops release-mode
/// tree-shaking from removing it since nothing in the normal call graph
/// appears to reference it.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
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

/// Owns the Firebase Cloud Messaging lifecycle for the doctor app: init,
/// permission request, token issuance + backend registration, token
/// refresh, and foreground/background/terminated message handling with
/// type-based navigation.
///
/// Navigation mapping:
///   sos_alert                          -> /alerts (Critical Alerts feed)
///   appointment_reminder/appointment_booked -> / (Dashboard queue)
///   anything else / unknown            -> / (Dashboard)
class FirebaseNotificationService {
  static final FirebaseNotificationService _instance =
      FirebaseNotificationService._internal();
  factory FirebaseNotificationService() => _instance;
  FirebaseNotificationService._internal();

  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;
    _initialized = true;

    await Firebase.initializeApp();

    FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;
    PlatformDispatcher.instance.onError = (error, stack) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      return true;
    };
    await FirebaseCrashlytics.instance.setCrashlyticsCollectionEnabled(true);

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

    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    FirebaseMessaging.onMessage.listen(_showForegroundNotification);

    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      _logEvent('notification_tapped', {'type': message.data['type'] ?? 'unknown', 'source': 'background_opened_app'});
      _navigateForNotification(message.data);
    });

    final initialMessage = await FirebaseMessaging.instance.getInitialMessage();
    if (initialMessage != null) {
      _logEvent('notification_tapped', {'type': initialMessage.data['type'] ?? 'unknown', 'source': 'terminated_launch'});
      Future.delayed(const Duration(milliseconds: 700), () {
        _navigateForNotification(initialMessage.data);
      });
    }

    FirebaseMessaging.instance.onTokenRefresh.listen((newToken) async {
      _logEvent('fcm_token_refreshed', {});
      await _registerTokenWithBackend(newToken);
    });
  }

  /// Call after a successful login, and again on dashboard init while
  /// already authenticated — idempotent: skips the POST if unchanged.
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
      debugPrint('FCM token sync failed (non-fatal): $e');
      await FirebaseCrashlytics.instance.recordError(e, st, fatal: false);
    }
  }

  Future<NotificationSettings> _requestPermission() {
    return FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );
  }

  Future<void> _registerTokenWithBackend(String token) async {
    final lastRegistered = await SecureStore().getLastRegisteredFcmToken();
    if (lastRegistered == token) {
      debugPrint('FCM token unchanged since last registration — skipping POST.');
      return;
    }

    final hasSession = await SecureStore().getToken() != null;
    if (!hasSession) {
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
    if (notification == null) return;

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
      payload: jsonEncode(message.data),
    );
  }

  void _navigateForNotification(Map<String, dynamic> data) {
    final type = data['type'] as String?;
    switch (type) {
      case 'sos_alert':
        appRouter.go('/alerts');
        break;
      case 'appointment_reminder':
      case 'appointment_booked':
        appRouter.go('/');
        break;
      default:
        appRouter.go('/');
    }
  }

  void _logEvent(String name, Map<String, Object> parameters) {
    FirebaseAnalytics.instance.logEvent(name: name, parameters: parameters).catchError((e) {
      debugPrint('Analytics logEvent($name) failed: $e');
    });
  }
}
