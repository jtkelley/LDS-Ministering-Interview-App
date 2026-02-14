import 'package:flutter/foundation.dart';
import '../models/member.dart';
import '../models/district.dart';
import '../services/api_service.dart';
import '../services/invite_service.dart';

/// Provider for member list and selection state
class MembersProvider with ChangeNotifier {
  final ApiService _apiService;
  late final InviteService _inviteService;

  List<Member> _members = [];
  List<District> _districts = [];
  Set<int> _selectedMemberIds = {};
  int? _filterDistrictId;
  String _bookingFilter = 'not_booked'; // 'all', 'not_booked', 'companionship_not_booked'
  String _searchQuery = '';
  int _currentQuarter = 1;
  int _currentYear = 2024;
  int _targetQuarter = 1;
  int _targetYear = 2024;
  int _nextQuarter = 2;
  int _nextYear = 2024;
  bool _currentQuarterHasSlots = false;
  bool _nextQuarterHasSlots = false;
  bool _isLoading = false;
  String? _error;

  MembersProvider(this._apiService) {
    _inviteService = InviteService(_apiService);
  }

  // Getters
  List<Member> get members => _members;
  List<District> get districts => _districts;
  Set<int> get selectedMemberIds => _selectedMemberIds;
  int? get filterDistrictId => _filterDistrictId;
  String get bookingFilter => _bookingFilter;
  String get searchQuery => _searchQuery;
  int get currentQuarter => _currentQuarter;
  int get currentYear => _currentYear;
  int get targetQuarter => _targetQuarter;
  int get targetYear => _targetYear;
  int get nextQuarter => _nextQuarter;
  int get nextYear => _nextYear;
  bool get currentQuarterHasSlots => _currentQuarterHasSlots;
  bool get nextQuarterHasSlots => _nextQuarterHasSlots;
  bool get isLoading => _isLoading;
  String? get error => _error;
  InviteService get inviteService => _inviteService;

  /// Get members filtered by search query
  List<Member> get filteredMembers {
    if (_searchQuery.isEmpty) return _members;
    final query = _searchQuery.toLowerCase();
    return _members.where((m) => m.name.toLowerCase().contains(query)).toList();
  }

  /// Get selected members
  List<Member> get selectedMembers =>
      _members.where((m) => _selectedMemberIds.contains(m.id)).toList();

  /// Check if all filtered members are selected
  bool get allSelected {
    final filtered = filteredMembers;
    return filtered.isNotEmpty &&
           filtered.every((m) => _selectedMemberIds.contains(m.id));
  }

  /// Load districts
  Future<void> loadDistricts() async {
    try {
      _districts = await _apiService.getDistricts();
      notifyListeners();
    } catch (e) {
      _error = 'Failed to load districts: $e';
      notifyListeners();
    }
  }

  /// Load available quarters (current and next with slot availability)
  Future<void> loadAvailableQuarters() async {
    try {
      final result = await _apiService.getAvailableQuarters();
      if (result != null) {
        final current = result['current'] as Map<String, dynamic>;
        final next = result['next'] as Map<String, dynamic>;

        _currentQuarter = current['quarter'] as int;
        _currentYear = current['year'] as int;
        _currentQuarterHasSlots = current['has_slots'] as bool;

        _nextQuarter = next['quarter'] as int;
        _nextYear = next['year'] as int;
        _nextQuarterHasSlots = next['has_slots'] as bool;

        // Set target to current quarter by default
        if (_targetQuarter == 0 || _targetYear == 0) {
          _targetQuarter = _currentQuarter;
          _targetYear = _currentYear;
        }

        notifyListeners();
      }
    } catch (e) {
      _error = 'Failed to load quarter info: $e';
      notifyListeners();
    }
  }

  /// Set target quarter and reload members
  void setTargetQuarter(int quarter, int year) {
    _targetQuarter = quarter;
    _targetYear = year;
    loadMembers();
  }

  /// Load members with current filters
  Future<void> loadMembers() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _apiService.getMembers(
        districtId: _filterDistrictId,
        filterMode: _bookingFilter,
        quarter: _targetQuarter > 0 ? _targetQuarter : null,
        year: _targetYear > 0 ? _targetYear : null,
      );

      _members = result['members'] as List<Member>;
      // Update target quarter from response
      _targetQuarter = result['quarter'] as int;
      _targetYear = result['year'] as int;

      // Also update current if not set
      if (_currentQuarter == 0) {
        _currentQuarter = _targetQuarter;
        _currentYear = _targetYear;
      }

      // Clear selections for members no longer in list
      _selectedMemberIds.removeWhere(
        (id) => !_members.any((m) => m.id == id),
      );
    } catch (e) {
      _error = 'Failed to load members: $e';
      _members = [];
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Set district filter
  void setDistrictFilter(int? districtId) {
    _filterDistrictId = districtId;
    loadMembers();
  }

  /// Set booking filter mode: 'all', 'not_booked', 'companionship_not_booked'
  void setBookingFilter(String mode) {
    _bookingFilter = mode;
    loadMembers();
  }

  /// Set search query for filtering members by name
  void setSearchQuery(String query) {
    _searchQuery = query;
    notifyListeners();
  }

  /// Clear search query
  void clearSearch() {
    _searchQuery = '';
    notifyListeners();
  }

  /// Toggle member selection
  void toggleMemberSelection(int memberId) {
    if (_selectedMemberIds.contains(memberId)) {
      _selectedMemberIds.remove(memberId);
    } else {
      _selectedMemberIds.add(memberId);
    }
    notifyListeners();
  }

  /// Select all filtered members
  void selectAll() {
    _selectedMemberIds.addAll(filteredMembers.map((m) => m.id));
    notifyListeners();
  }

  /// Deselect all filtered members
  void deselectAll() {
    final filteredIds = filteredMembers.map((m) => m.id).toSet();
    _selectedMemberIds.removeAll(filteredIds);
    notifyListeners();
  }

  /// Toggle select all
  void toggleSelectAll() {
    if (allSelected) {
      deselectAll();
    } else {
      selectAll();
    }
  }

  /// Send bulk SMS to selected members
  /// Returns result map with 'sent' and 'failed' counts
  Future<Map<String, dynamic>> sendBulkSms() async {
    final members = selectedMembers.where((m) => m.canReceiveSms).toList();

    if (members.isEmpty) {
      return {'sent': 0, 'failed': 0, 'message': 'No members with valid phone numbers'};
    }

    final result = await _inviteService.sendBulkSmsAndroid(
      members,
      quarter: _targetQuarter > 0 ? _targetQuarter : null,
      year: _targetYear > 0 ? _targetYear : null,
    );

    // Reload to update notification status
    await loadMembers();

    return {
      ...result,
      'message': 'Sent ${result['sent']} SMS, ${result['failed']} failed',
    };
  }

  /// Send bulk email to selected members via server
  Future<Map<String, dynamic>> sendBulkEmail() async {
    final members = selectedMembers.where((m) => m.canReceiveEmail).toList();

    if (members.isEmpty) {
      return {'sent': 0, 'failed': 0, 'message': 'No members with valid email addresses'};
    }

    final result = await _inviteService.sendBulkEmailViaServer(
      members,
      quarter: _targetQuarter > 0 ? _targetQuarter : null,
      year: _targetYear > 0 ? _targetYear : null,
    );

    // Reload to update notification status
    await loadMembers();

    return result;
  }

  /// Send reminder SMS to selected members with upcoming appointments
  Future<Map<String, dynamic>> sendReminderSms() async {
    final members = selectedMembers.where((m) => m.canReceiveSms && m.hasBookingDetails).toList();

    if (members.isEmpty) {
      return {'sent': 0, 'failed': 0, 'message': 'No members with valid phone numbers and booking details'};
    }

    final result = await _inviteService.sendReminderSmsAndroid(
      members,
      quarter: _targetQuarter > 0 ? _targetQuarter : null,
      year: _targetYear > 0 ? _targetYear : null,
    );

    // Reload to update notification status
    await loadMembers();

    return {
      ...result,
      'message': 'Sent ${result['sent']} reminder SMS, ${result['failed']} failed',
    };
  }

  /// Send reminder email to selected members with upcoming appointments
  Future<Map<String, dynamic>> sendReminderEmail() async {
    final members = selectedMembers.where((m) => m.canReceiveEmail && m.hasBookingDetails).toList();

    if (members.isEmpty) {
      return {'sent': 0, 'failed': 0, 'message': 'No members with valid email addresses and booking details'};
    }

    final result = await _inviteService.sendReminderEmailViaServer(
      members,
      quarter: _targetQuarter > 0 ? _targetQuarter : null,
      year: _targetYear > 0 ? _targetYear : null,
    );

    // Reload to update notification status
    await loadMembers();

    return result;
  }

  /// Get member details
  Future<Member?> getMemberDetail(int memberId) async {
    return await _apiService.getMemberDetail(
      memberId,
      quarter: _targetQuarter > 0 ? _targetQuarter : null,
      year: _targetYear > 0 ? _targetYear : null,
    );
  }

  /// Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
