import 'dart:io';
import 'package:url_launcher/url_launcher.dart';
import 'package:another_telephony/telephony.dart';
import '../models/member.dart';
import '../models/message_templates.dart';
import 'api_service.dart';

/// Service for sending invitations via native email/SMS apps
class InviteService {
  final ApiService _apiService;
  final Telephony _telephony = Telephony.instance;

  // Cached message templates
  MessageTemplates? _templates;
  DateTime? _templatesFetchedAt;
  static const _templatesCacheMinutes = 5;

  InviteService(this._apiService);

  /// Fetch message templates from server (with caching)
  Future<MessageTemplates> _getTemplates() async {
    // Check if we have cached templates that are still fresh
    if (_templates != null && _templatesFetchedAt != null) {
      final age = DateTime.now().difference(_templatesFetchedAt!);
      if (age.inMinutes < _templatesCacheMinutes) {
        return _templates!;
      }
    }

    // Fetch from server
    final templates = await _apiService.getMessageTemplates();
    if (templates != null) {
      _templates = templates;
      _templatesFetchedAt = DateTime.now();
      return templates;
    }

    // Fall back to defaults if server is unavailable
    return _templates ?? MessageTemplates.defaults();
  }

  /// Clear cached templates (call when user logs out or settings change)
  void clearTemplatesCache() {
    _templates = null;
    _templatesFetchedAt = null;
  }

  /// Generate email subject using templates
  Future<String> getEmailSubject() async {
    final templates = await _getTemplates();
    return templates.formatEmailSubject();
  }

  /// Generate email body using templates
  Future<String> getEmailBody(Member member) async {
    final templates = await _getTemplates();
    return templates.formatEmailBody(member.name, member.schedulingLink ?? '');
  }

  /// Generate SMS message using templates
  Future<String> getSmsMessage(Member member) async {
    final templates = await _getTemplates();
    return templates.formatSms(member.name, member.schedulingLink ?? '');
  }

  /// Send individual email via native email app
  Future<bool> sendEmailNative(Member member, int quarter, int year) async {
    if (!member.canReceiveEmail) return false;

    final subject = Uri.encodeComponent(await getEmailSubject());
    final body = Uri.encodeComponent(await getEmailBody(member));
    final uri = Uri.parse('mailto:${member.email}?subject=$subject&body=$body');

    try {
      final launched = await launchUrl(uri);
      if (launched) {
        // Log the notification with target quarter
        await _apiService.logNotification(member.id, 'email', quarter: quarter, year: year);
      }
      return launched;
    } catch (e) {
      return false;
    }
  }

  /// Send individual SMS via native SMS app (iOS and Android fallback)
  Future<bool> sendSmsNative(Member member, {int? quarter, int? year}) async {
    if (!member.canReceiveSms) return false;

    final message = Uri.encodeComponent(await getSmsMessage(member));
    final uri = Uri.parse('sms:${member.phone}?body=$message');

    try {
      final launched = await launchUrl(uri);
      if (launched) {
        // Log the notification with target quarter
        await _apiService.logNotification(member.id, 'sms', quarter: quarter, year: year);
      }
      return launched;
    } catch (e) {
      return false;
    }
  }

  /// Check if Android direct SMS is available
  Future<bool> canSendDirectSms() async {
    if (!Platform.isAndroid) return false;

    try {
      final permissionGranted = await _telephony.requestPhoneAndSmsPermissions;
      return permissionGranted ?? false;
    } catch (e) {
      return false;
    }
  }

  /// Send bulk SMS on Android (uses device SMS plan - FREE)
  /// Returns map with 'sent' and 'failed' counts
  Future<Map<String, int>> sendBulkSmsAndroid(List<Member> members, {int? quarter, int? year}) async {
    if (!Platform.isAndroid) {
      return {'sent': 0, 'failed': members.length};
    }

    final hasPermission = await canSendDirectSms();
    if (!hasPermission) {
      return {'sent': 0, 'failed': members.length};
    }

    // Pre-fetch templates once for all messages
    final templates = await _getTemplates();

    int sent = 0;
    int failed = 0;
    final sentMemberIds = <int>[];

    for (final member in members) {
      if (!member.canReceiveSms) {
        failed++;
        continue;
      }

      try {
        final message = templates.formatSms(member.name, member.schedulingLink ?? '');
        await _telephony.sendSms(
          to: member.phone!,
          message: message,
        );
        sent++;
        sentMemberIds.add(member.id);
      } catch (e) {
        failed++;
      }
    }

    // Log all sent notifications to backend with target quarter
    if (sentMemberIds.isNotEmpty) {
      await _apiService.logBulkNotifications(sentMemberIds, 'sms', quarter: quarter, year: year);
    }

    return {'sent': sent, 'failed': failed};
  }

  /// Send sequential SMS on iOS (opens native app for each)
  /// Returns after opening first SMS - user must manually proceed through each
  Future<int> sendSequentialSmsIOS(List<Member> members, {int? quarter, int? year}) async {
    int opened = 0;

    for (final member in members) {
      if (!member.canReceiveSms) continue;

      final sent = await sendSmsNative(member, quarter: quarter, year: year);
      if (sent) {
        opened++;
        // Small delay to let user interact with each message
        await Future.delayed(const Duration(milliseconds: 500));
      }
    }

    return opened;
  }

  /// Send bulk emails via server (works on all platforms)
  Future<Map<String, dynamic>> sendBulkEmailViaServer(List<Member> members, {int? quarter, int? year}) async {
    final memberIds = members.map((m) => m.id).toList();
    return await _apiService.sendBulkEmail(memberIds, quarter: quarter, year: year);
  }

  /// Generate reminder SMS message with appointment details
  String _getReminderSmsMessage(Member member) {
    final dateTime = member.formattedBookingDateTime;
    // Convert "Last, First" to "First Last"
    String displayName = member.name;
    if (member.name.contains(',')) {
      final parts = member.name.split(',').map((s) => s.trim()).toList();
      if (parts.length >= 2) {
        displayName = '${parts[1]} ${parts[0]}';
      }
    }
    return 'Hi $displayName, this is a reminder that your ministering interview is scheduled for $dateTime. '
        'If you need to change or cancel, use this link: ${member.schedulingLink}';
  }

  /// Send reminder SMS on Android for members with upcoming appointments
  Future<Map<String, int>> sendReminderSmsAndroid(List<Member> members, {int? quarter, int? year}) async {
    if (!Platform.isAndroid) {
      return {'sent': 0, 'failed': members.length};
    }

    final hasPermission = await canSendDirectSms();
    if (!hasPermission) {
      return {'sent': 0, 'failed': members.length};
    }

    int sent = 0;
    int failed = 0;
    final sentMemberIds = <int>[];

    for (final member in members) {
      if (!member.canReceiveSms || !member.hasBookingDetails) {
        failed++;
        continue;
      }

      try {
        final message = _getReminderSmsMessage(member);
        await _telephony.sendSms(
          to: member.phone!,
          message: message,
        );
        sent++;
        sentMemberIds.add(member.id);
      } catch (e) {
        failed++;
      }
    }

    // Log all sent notifications to backend
    if (sentMemberIds.isNotEmpty) {
      await _apiService.logBulkNotifications(sentMemberIds, 'sms', quarter: quarter, year: year);
    }

    return {'sent': sent, 'failed': failed};
  }

  /// Send reminder emails via server for members with upcoming appointments
  Future<Map<String, dynamic>> sendReminderEmailViaServer(List<Member> members, {int? quarter, int? year}) async {
    final memberIds = members.where((m) => m.hasBookingDetails).map((m) => m.id).toList();
    // Use the regular bulk email endpoint but the backend will need to know it's a reminder
    // For now, we'll use the existing endpoint and the server handles it
    return await _apiService.sendReminderEmail(memberIds, quarter: quarter, year: year);
  }
}
