import 'dart:io';

import 'package:dio/dio.dart';

import 'secure_store.dart';

/// Dio client — verbatim pattern from apps/mobile_app/lib/services/api_service.dart.
class ApiService {
  static final ApiService _instance = ApiService._internal();
  late Dio _dio;

  static String get baseUrl {
    return 'https://gramcare-fastapi.onrender.com/api/v1';
  }

  factory ApiService() {
    return _instance;
  }

  ApiService._internal() {
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
