/// Message templates for formatting notifications
class MessageTemplates {
  final String organizationName;
  final String greetingStyle;
  final String greetingPrefix;
  final String orgPrefix;
  final String customInstructions;
  final String signatureName;
  final String signatureTitle;
  final String signature;
  final int quarter;
  final int year;
  final String smsTemplate;
  final String emailSubjectTemplate;
  final String emailBodyTemplate;
  final String emailBodyTemplatePlain; // Plain text version for mailto: links

  MessageTemplates({
    required this.organizationName,
    required this.greetingStyle,
    required this.greetingPrefix,
    required this.orgPrefix,
    required this.customInstructions,
    required this.signatureName,
    required this.signatureTitle,
    required this.signature,
    required this.quarter,
    required this.year,
    required this.smsTemplate,
    required this.emailSubjectTemplate,
    required this.emailBodyTemplate,
    required this.emailBodyTemplatePlain,
  });

  factory MessageTemplates.fromJson(Map<String, dynamic> json) {
    return MessageTemplates(
      organizationName: json['organization_name'] ?? '',
      greetingStyle: json['greeting_style'] ?? 'Dear',
      greetingPrefix: json['greeting_prefix'] ?? '',
      orgPrefix: json['org_prefix'] ?? '',
      customInstructions: json['custom_instructions'] ?? '',
      signatureName: json['signature_name'] ?? '',
      signatureTitle: json['signature_title'] ?? '',
      signature: json['signature'] ?? '',
      quarter: json['quarter'] ?? 1,
      year: json['year'] ?? DateTime.now().year,
      smsTemplate: json['sms_template'] ?? '',
      emailSubjectTemplate: json['email_subject_template'] ?? '',
      emailBodyTemplate: json['email_body_template'] ?? '',
      emailBodyTemplatePlain: json['email_body_template_plain'] ?? json['email_body_template'] ?? '',
    );
  }

  /// Default templates when server templates aren't available
  factory MessageTemplates.defaults() {
    final now = DateTime.now();
    final quarter = ((now.month - 1) ~/ 3) + 1;
    final year = now.year;

    const defaultBody = '''Dear {name},

Interview slots are now available for the current quarter (Q{quarter} {year}).

Please click the link below to schedule your interview:

{link}

Thank you,''';

    return MessageTemplates(
      organizationName: '',
      greetingStyle: 'Dear',
      greetingPrefix: 'Dear ',
      orgPrefix: '',
      customInstructions: '',
      signatureName: '',
      signatureTitle: '',
      signature: '',
      quarter: quarter,
      year: year,
      smsTemplate: 'Ministering Interview\nDear {name}, schedule your interview: {link}',
      emailSubjectTemplate: 'Ministering Interview - Q$quarter $year',
      emailBodyTemplate: defaultBody.replaceAll('{quarter}', quarter.toString()).replaceAll('{year}', year.toString()),
      emailBodyTemplatePlain: defaultBody.replaceAll('{quarter}', quarter.toString()).replaceAll('{year}', year.toString()),
    );
  }

  /// Convert name from "Last, First" format to "First Last" format
  /// Matches Python backend behavior in core/services.py:format_email_notification
  static String formatDisplayName(String name) {
    if (name.contains(', ')) {
      final parts = name.split(', ');
      return parts.reversed.join(' ');
    }
    return name;
  }

  /// Format SMS message for a specific member
  String formatSms(String name, String link) {
    final displayName = formatDisplayName(name);
    return smsTemplate
        .replaceAll('{name}', displayName)
        .replaceAll('{link}', link);
  }

  /// Format email subject
  String formatEmailSubject() {
    return emailSubjectTemplate;
  }

  /// Format email body for a specific member (plain text for mailto: links)
  String formatEmailBody(String name, String link) {
    final displayName = formatDisplayName(name);
    return emailBodyTemplatePlain
        .replaceAll('{name}', displayName)
        .replaceAll('{link}', link);
  }
}
