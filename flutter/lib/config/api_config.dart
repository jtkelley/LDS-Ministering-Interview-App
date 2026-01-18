import 'package:shared_preferences/shared_preferences.dart';

/// API configuration for connecting to the Flask backend
class ApiConfig {
  static const String _urlKey = 'api_base_url';
  static const String defaultUrl = 'http://10.0.2.2:8181';

  static String _baseUrl = defaultUrl;

  /// Get the current base URL
  static String get baseUrl => _baseUrl;

  /// Initialize from SharedPreferences (call on app startup)
  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(_urlKey) ?? defaultUrl;
  }

  /// Update the base URL and persist to storage
  static Future<void> setBaseUrl(String url) async {
    // Remove trailing slash if present
    _baseUrl = url.endsWith('/') ? url.substring(0, url.length - 1) : url;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_urlKey, _baseUrl);
  }

  /// Reset to default URL
  static Future<void> resetToDefault() async {
    _baseUrl = defaultUrl;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_urlKey);
  }

  // API endpoints
  static const String loginEndpoint = '/api/auth/login';
  static const String meEndpoint = '/api/auth/me';
  static const String quarterEndpoint = '/api/quarter/current';
  static const String districtsEndpoint = '/api/districts';
  static const String membersEndpoint = '/api/members';
  static String memberDetailEndpoint(int id) => '/api/members/$id';
  static String logNotificationEndpoint(int id) => '/api/members/$id/log-notification';
  static const String bulkEmailEndpoint = '/api/notifications/send-bulk-email';
  static const String logBulkEndpoint = '/api/notifications/log-bulk';
  static const String messageTemplatesEndpoint = '/api/message-templates';

  // Build full URL
  static String url(String endpoint) => '$baseUrl$endpoint';
}
