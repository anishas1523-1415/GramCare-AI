import 'package:dio/dio.dart';

import 'app_strings.dart';

/// Every failure path in this app rendered the same "you are offline"
/// string, so a 500, an expired token and a genuinely dropped connection
/// all read the same and only one of those explanations was ever true.
///
/// Returns a translation key describing what actually went wrong.
String errorKeyFor(Object? error) {
  if (error is DioException) {
    final status = error.response?.statusCode;
    if (status == 401 || status == 403) return 'session_expired_note';
    if (status != null && status >= 500) return 'server_error_note';
    if (status != null) return 'request_failed_note';
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return 'offline_note';
      default:
        return 'request_failed_note';
    }
  }
  return 'request_failed_note';
}

String errorTextFor(LocaleService locale, Object? error) =>
    locale.t(errorKeyFor(error));
