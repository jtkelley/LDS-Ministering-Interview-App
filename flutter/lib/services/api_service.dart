import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';
import '../models/member.dart';
import '../models/district.dart';
import '../models/message_templates.dart';

/// Service for communicating with the Flask backend API
class ApiService {
  static const String _tokenKey = 'auth_token';
  String? _token;

  /// Get stored auth token
  Future<String?> getToken() async {
    if (_token != null) return _token;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_tokenKey);
    return _token;
  }

  /// Store auth token
  Future<void> setToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  /// Clear auth token (logout)
  Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  /// Check if user is logged in
  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }

  /// Build authorization headers
  Future<Map<String, String>> _authHeaders() async {
    final token = await getToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// Login and get JWT token
  Future<Map<String, dynamic>> login(String email, String password) async {
    final url = ApiConfig.url(ApiConfig.loginEndpoint);
    print('LOGIN: POST to $url');

    final response = await http.post(
      Uri.parse(url),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );

    print('LOGIN: Status ${response.statusCode}, Body length: ${response.body.length}');

    // Check if response is HTML (error page)
    if (response.body.trim().startsWith('<!') || response.body.trim().startsWith('<html')) {
      return {'success': false, 'error': 'Server error (status ${response.statusCode})'};
    }

    final data = jsonDecode(response.body);

    if (response.statusCode == 200) {
      await setToken(data['token']);
      return {'success': true, 'user': data['user']};
    } else {
      return {'success': false, 'error': data['error'] ?? 'Login failed'};
    }
  }

  /// Logout
  Future<void> logout() async {
    await clearToken();
  }

  /// Get current user info
  Future<Map<String, dynamic>?> getCurrentUser() async {
    final response = await http.get(
      Uri.parse(ApiConfig.url(ApiConfig.meEndpoint)),
      headers: await _authHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    return null;
  }

  /// Get current quarter info
  Future<Map<String, dynamic>?> getCurrentQuarter() async {
    final response = await http.get(
      Uri.parse(ApiConfig.url(ApiConfig.quarterEndpoint)),
      headers: await _authHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    return null;
  }

  /// Get all districts
  Future<List<District>> getDistricts() async {
    final response = await http.get(
      Uri.parse(ApiConfig.url(ApiConfig.districtsEndpoint)),
      headers: await _authHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['districts'] as List)
          .map((d) => District.fromJson(d))
          .toList();
    }
    return [];
  }

  /// Get members with optional filtering
  Future<Map<String, dynamic>> getMembers({
    int? districtId,
    bool needsInviteOnly = false,
  }) async {
    var url = ApiConfig.url(ApiConfig.membersEndpoint);
    final params = <String>[];

    if (districtId != null) {
      params.add('district_id=$districtId');
    }
    if (needsInviteOnly) {
      params.add('needs_invite=true');
    }

    if (params.isNotEmpty) {
      url = '$url?${params.join('&')}';
    }

    final response = await http.get(
      Uri.parse(url),
      headers: await _authHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return {
        'members': (data['members'] as List)
            .map((m) => Member.fromListJson(m))
            .toList(),
        'quarter': data['quarter'],
        'year': data['year'],
        'total_count': data['total_count'],
      };
    }
    return {'members': [], 'quarter': 0, 'year': 0, 'total_count': 0};
  }

  /// Get member details
  Future<Member?> getMemberDetail(int memberId) async {
    final response = await http.get(
      Uri.parse(ApiConfig.url(ApiConfig.memberDetailEndpoint(memberId))),
      headers: await _authHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return Member.fromDetailJson(data);
    }
    return null;
  }

  /// Log a notification sent via native app
  Future<bool> logNotification(int memberId, String method, {bool success = true, String? errorMessage}) async {
    final response = await http.post(
      Uri.parse(ApiConfig.url(ApiConfig.logNotificationEndpoint(memberId))),
      headers: await _authHeaders(),
      body: jsonEncode({
        'method': method,
        'success': success,
        if (errorMessage != null) 'error_message': errorMessage,
      }),
    );

    return response.statusCode == 200;
  }

  /// Send bulk emails via server
  Future<Map<String, dynamic>> sendBulkEmail(List<int> memberIds) async {
    final response = await http.post(
      Uri.parse(ApiConfig.url(ApiConfig.bulkEmailEndpoint)),
      headers: await _authHeaders(),
      body: jsonEncode({'member_ids': memberIds}),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    return {
      'sent': 0,
      'failed': memberIds.length,
      'errors': ['Server error: ${response.statusCode}'],
    };
  }

  /// Log bulk notifications (for Android bulk SMS)
  Future<bool> logBulkNotifications(List<int> memberIds, String method, {bool success = true}) async {
    final response = await http.post(
      Uri.parse(ApiConfig.url(ApiConfig.logBulkEndpoint)),
      headers: await _authHeaders(),
      body: jsonEncode({
        'member_ids': memberIds,
        'method': method,
        'success': success,
      }),
    );

    return response.statusCode == 200;
  }

  /// Get message templates for formatting notifications
  Future<MessageTemplates?> getMessageTemplates() async {
    try {
      final response = await http.get(
        Uri.parse(ApiConfig.url(ApiConfig.messageTemplatesEndpoint)),
        headers: await _authHeaders(),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return MessageTemplates.fromJson(data);
      }
    } catch (e) {
      print('Error fetching message templates: $e');
    }
    return null;
  }
}
