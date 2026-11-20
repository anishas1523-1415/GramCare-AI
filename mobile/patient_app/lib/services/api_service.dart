
import 'package:dio/dio.dart';

import 'secure_store.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  late Dio _dio;

  factory ApiService() {
    return _instance;
  }

  /// The API root.
  ///
  /// Defaults to production, so a normal build is unchanged. An integration
  /// test overrides it with
  /// `--dart-define=GRAMCARE_API_BASE=http://localhost:8000/api/v1` so the
  /// test drives a backend on the developer's machine (reached through
  /// `adb reverse`) instead of writing synthetic records into production.
  /// `String.fromEnvironment` is const-folded at compile time, so a release
  /// build has no way to point this anywhere else at runtime.
  static const String _envBase = String.fromEnvironment(
    'GRAMCARE_API_BASE',
    defaultValue: 'https://gramcare-fastapi.onrender.com/api/v1',
  );

  static String get baseUrl => _envBase;

  ApiService._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        // The backend runs on Render's free tier, which spins the service
        // down after idle periods — the first request after that can take
        // 30-60s to wake it (measured: a real cold start took ~62s). A 10s
        // timeout meant every cold-start request (login included) failed
        // with a generic connection-timeout error that looked identical to
        // "the app is broken". The web portal's login page already accounts
        // for this same cold-start window.
        connectTimeout: const Duration(seconds: 65),
        receiveTimeout: const Duration(seconds: 65),
        headers: {
          'Content-Type': 'application/json',
        },
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Token now comes from the platform keystore (SecureStore), not
          // plain shared_preferences.
          final token = await SecureStore().getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException error, handler) async {
          if (error.response?.statusCode == 401) {
            await SecureStore().clearToken();
          }
          return handler.next(error);
        },
      ),
    );
  }

  Dio get client => _dio;
}
