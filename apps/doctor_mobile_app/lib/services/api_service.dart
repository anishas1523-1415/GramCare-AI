import 'dart:io';

import 'package:dio/dio.dart';

import 'secure_store.dart';

/// Dio client for the Doctor mobile app — same base-URL resolution and auth
/// interceptor pattern as apps/mobile_app's ApiService, pointed at the same
/// backend (/api/v1).
class ApiService {
  static final ApiService _instance = ApiService._internal();
  late Dio _dio;

  factory ApiService() {
    return _instance;
  }

  ApiService._internal() {
    // For Android emulator to reach localhost, use 10.0.2.2.
    // For iOS emulator or physical device on same network, use local IP.
    // Overridable at build time: flutter build --dart-define=API_BASE_URL=...
    const configured = String.fromEnvironment('API_BASE_URL');
    final String baseUrl = configured.isNotEmpty
        ? configured
        : (Platform.isAndroid
            ? 'http://10.0.2.2:8000/api/v1'
            : 'http://localhost:8000/api/v1');

    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
        headers: {
          'Content-Type': 'application/json',
        },
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
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
