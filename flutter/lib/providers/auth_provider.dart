import 'package:flutter/foundation.dart';
import '../services/api_service.dart';

/// Provider for authentication state
class AuthProvider with ChangeNotifier {
  final ApiService _apiService;

  bool _isLoggedIn = false;
  bool _isLoading = false;
  String? _userEmail;
  String? _userRole;
  String? _error;

  AuthProvider(this._apiService);

  bool get isLoggedIn => _isLoggedIn;
  bool get isLoading => _isLoading;
  String? get userEmail => _userEmail;
  String? get userRole => _userRole;
  String? get error => _error;
  bool get isAdmin => _userRole == 'admin';

  /// Initialize auth state from stored token
  Future<void> initialize() async {
    _isLoading = true;
    notifyListeners();

    try {
      final hasToken = await _apiService.isLoggedIn();
      if (hasToken) {
        // Verify token is still valid
        final user = await _apiService.getCurrentUser();
        if (user != null) {
          _isLoggedIn = true;
          _userEmail = user['email'];
          _userRole = user['role'];
        } else {
          // Token invalid, clear it
          await _apiService.clearToken();
        }
      }
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Login with email and password
  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _apiService.login(email, password);

      if (result['success'] == true) {
        _isLoggedIn = true;
        _userEmail = result['user']['email'];
        _userRole = result['user']['role'];
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _error = result['error'] ?? 'Login failed';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = 'Connection error: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Logout
  Future<void> logout() async {
    await _apiService.logout();
    _isLoggedIn = false;
    _userEmail = null;
    _userRole = null;
    _error = null;
    notifyListeners();
  }

  /// Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
