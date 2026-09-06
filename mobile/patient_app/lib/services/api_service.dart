
import 'package:dio/dio.dart';

import 'secure_store.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  late Dio _dio;

  factory ApiService() {
    return _instance;
  }

  static String get baseUrl {
    return 'https://gramcare-fastapi.onrender.com/api/v1';
  }

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
