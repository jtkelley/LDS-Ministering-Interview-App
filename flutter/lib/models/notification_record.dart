/// Notification record for tracking sent invitations
class NotificationRecord {
  final int id;
  final String method; // 'email' or 'sms'
  final DateTime sentAt;
  final int quarter;
  final int year;
  final bool success;
  final String? errorMessage;

  NotificationRecord({
    required this.id,
    required this.method,
    required this.sentAt,
    required this.quarter,
    required this.year,
    required this.success,
    this.errorMessage,
  });

  factory NotificationRecord.fromJson(Map<String, dynamic> json) {
    return NotificationRecord(
      id: json['id'],
      method: json['method'],
      sentAt: DateTime.parse(json['sent_at']),
      quarter: json['quarter'],
      year: json['year'],
      success: json['success'] ?? true,
      errorMessage: json['error_message'],
    );
  }

  String get methodIcon => method == 'email' ? 'email' : 'sms';

  String get statusText => success ? 'Sent' : 'Failed';

  @override
  String toString() => 'NotificationRecord($method, Q$quarter $year, $statusText)';
}
