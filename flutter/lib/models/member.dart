import 'district.dart';
import 'notification_record.dart';

/// Companionship member (simplified)
class CompanionshipMember {
  final int id;
  final String name;
  final bool hasBooking;

  CompanionshipMember({
    required this.id,
    required this.name,
    required this.hasBooking,
  });

  factory CompanionshipMember.fromJson(Map<String, dynamic> json) {
    return CompanionshipMember(
      id: json['id'],
      name: json['name'],
      hasBooking: json['has_booking'] ?? false,
    );
  }
}

/// Member model with full details
class Member {
  final int id;
  final String name;
  final String? email;
  final String? phone;
  final bool noSms;
  final bool optedOut;
  final bool hasBooking;
  final District? district;
  final int? companionshipId;
  final DateTime? lastNotification;
  final String schedulingLink;
  final List<CompanionshipMember> companionshipMembers;
  final List<NotificationRecord> notificationHistory;
  // Booking details (populated when using upcoming_7_days filter)
  final DateTime? bookingDate;
  final String? bookingTime;
  final int? bookingDuration;
  final String? interviewType;

  Member({
    required this.id,
    required this.name,
    this.email,
    this.phone,
    this.noSms = false,
    this.optedOut = false,
    this.hasBooking = false,
    this.district,
    this.companionshipId,
    this.lastNotification,
    required this.schedulingLink,
    this.companionshipMembers = const [],
    this.notificationHistory = const [],
    this.bookingDate,
    this.bookingTime,
    this.bookingDuration,
    this.interviewType,
  });

  /// Create from list endpoint JSON (partial data)
  factory Member.fromListJson(Map<String, dynamic> json) {
    return Member(
      id: json['id'],
      name: json['name'],
      email: json['email'],
      phone: json['phone'],
      noSms: json['no_sms'] ?? false,
      optedOut: json['opted_out'] ?? false,
      hasBooking: json['has_booking'] ?? false,
      district: json['district'] != null ? District.fromJson(json['district']) : null,
      companionshipId: json['companionship_id'],
      lastNotification: json['last_notification'] != null
          ? DateTime.parse(json['last_notification'])
          : null,
      schedulingLink: json['scheduling_link'] ?? '',
      // Booking details (from upcoming_7_days filter)
      bookingDate: json['booking_date'] != null
          ? DateTime.parse(json['booking_date'])
          : null,
      bookingTime: json['booking_time'],
      bookingDuration: json['booking_duration'],
      interviewType: json['interview_type'],
    );
  }

  /// Create from detail endpoint JSON (full data)
  factory Member.fromDetailJson(Map<String, dynamic> json) {
    return Member(
      id: json['id'],
      name: json['name'],
      email: json['email'],
      phone: json['phone'],
      noSms: json['no_sms'] ?? false,
      optedOut: json['opted_out'] ?? false,
      hasBooking: json['has_booking'] ?? false,
      district: json['district'] != null ? District.fromJson(json['district']) : null,
      companionshipId: json['companionship_id'],
      schedulingLink: json['scheduling_link'] ?? '',
      companionshipMembers: (json['companionship_members'] as List<dynamic>?)
              ?.map((m) => CompanionshipMember.fromJson(m))
              .toList() ??
          [],
      notificationHistory: (json['notification_history'] as List<dynamic>?)
              ?.map((n) => NotificationRecord.fromJson(n))
              .toList() ??
          [],
    );
  }

  /// Check if member can receive SMS
  bool get canReceiveSms => phone != null && phone!.isNotEmpty && !noSms;

  /// Check if member can receive email
  bool get canReceiveEmail => email != null && email!.isNotEmpty;

  /// Check if member has upcoming booking details
  bool get hasBookingDetails => bookingDate != null && bookingTime != null;

  /// Get formatted booking date/time string
  String get formattedBookingDateTime {
    if (bookingDate == null || bookingTime == null) return '';
    final weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    final weekday = weekdays[bookingDate!.weekday - 1];
    final month = months[bookingDate!.month - 1];
    // Convert 24h time to 12h format
    final timeParts = bookingTime!.split(':');
    final hour = int.parse(timeParts[0]);
    final minute = timeParts[1];
    final period = hour >= 12 ? 'PM' : 'AM';
    final hour12 = hour == 0 ? 12 : (hour > 12 ? hour - 12 : hour);
    return '$weekday, $month ${bookingDate!.day} at $hour12:$minute $period';
  }

  @override
  String toString() => 'Member($name)';
}
