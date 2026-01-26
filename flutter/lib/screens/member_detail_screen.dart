import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../models/member.dart';
import '../providers/members_provider.dart';

class MemberDetailScreen extends StatefulWidget {
  final int memberId;

  const MemberDetailScreen({super.key, required this.memberId});

  @override
  State<MemberDetailScreen> createState() => _MemberDetailScreenState();
}

class _MemberDetailScreenState extends State<MemberDetailScreen> {
  Member? _member;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadMember();
  }

  Future<void> _loadMember() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final provider = context.read<MembersProvider>();
      final member = await provider.getMemberDetail(widget.memberId);

      if (mounted) {
        setState(() {
          _member = member;
          _isLoading = false;
          if (member == null) {
            _error = 'Member not found';
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load member: $e';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _sendEmail() async {
    if (_member == null || !_member!.canReceiveEmail) return;

    final provider = context.read<MembersProvider>();
    final success = await provider.inviteService.sendEmailNative(
      _member!,
      provider.targetQuarter,
      provider.targetYear,
    );

    if (mounted) {
      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Email app opened')),
        );
        _loadMember(); // Refresh to show new notification
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to open email app')),
        );
      }
    }
  }

  Future<void> _sendSms() async {
    if (_member == null || !_member!.canReceiveSms) return;

    final provider = context.read<MembersProvider>();
    final success = await provider.inviteService.sendSmsNative(
      _member!,
      quarter: provider.targetQuarter,
      year: provider.targetYear,
    );

    if (mounted) {
      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('SMS app opened')),
        );
        _loadMember(); // Refresh to show new notification
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to open SMS app')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_member?.name ?? 'Member Details'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
            const SizedBox(height: 16),
            Text(_error!),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadMember,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (_member == null) {
      return const Center(child: Text('Member not found'));
    }

    return RefreshIndicator(
      onRefresh: _loadMember,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Contact info card
            _buildContactCard(),
            const SizedBox(height: 16),

            // Quarter selector
            _buildQuarterSelector(),
            const SizedBox(height: 16),

            // Send buttons
            _buildSendButtons(),
            const SizedBox(height: 16),

            // District info
            if (_member!.district != null) ...[
              _buildDistrictCard(),
              const SizedBox(height: 16),
            ],

            // Companionship members
            if (_member!.companionshipMembers.isNotEmpty) ...[
              _buildCompanionshipCard(),
              const SizedBox(height: 16),
            ],

            // Notification history
            _buildNotificationHistory(),
          ],
        ),
      ),
    );
  }

  Widget _buildContactCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 30,
                  backgroundColor: Colors.blue.shade100,
                  child: Text(
                    _member!.name.isNotEmpty ? _member!.name[0].toUpperCase() : '?',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: Colors.blue.shade700,
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _member!.name,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (_member!.hasBooking)
                        Container(
                          margin: const EdgeInsets.only(top: 4),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.green.shade100,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Has Booking',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.green.shade700,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 24),

            // Email
            if (_member!.email != null) ...[
              _buildContactRow(
                Icons.email,
                _member!.email!,
                _member!.canReceiveEmail ? Colors.blue : Colors.grey,
              ),
              const SizedBox(height: 8),
            ],

            // Phone
            if (_member!.phone != null) ...[
              _buildContactRow(
                Icons.phone,
                _member!.phone!,
                _member!.canReceiveSms ? Colors.green : Colors.grey,
              ),
              if (_member!.noSms)
                Padding(
                  padding: const EdgeInsets.only(left: 32, top: 4),
                  child: Text(
                    'SMS disabled for this member',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.orange.shade700,
                    ),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildContactRow(IconData icon, String text, Color color) {
    return Row(
      children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            text,
            style: TextStyle(color: color),
          ),
        ),
      ],
    );
  }

  Widget _buildQuarterSelector() {
    return Consumer<MembersProvider>(
      builder: (context, provider, _) {
        final showDropdown = provider.currentQuarterHasSlots || provider.nextQuarterHasSlots;
        if (!showDropdown) {
          return Text(
            'Sending for Q${provider.targetQuarter} ${provider.targetYear}',
            style: const TextStyle(fontWeight: FontWeight.w500),
          );
        }

        // Guard: only show dropdown if target matches an available option
        final targetKey = '${provider.targetQuarter}_${provider.targetYear}';
        final currentKey = '${provider.currentQuarter}_${provider.currentYear}';
        final nextKey = '${provider.nextQuarter}_${provider.nextYear}';
        final hasValidTarget = (provider.currentQuarterHasSlots && targetKey == currentKey) ||
            (provider.nextQuarterHasSlots && targetKey == nextKey);

        if (!hasValidTarget) {
          return Text(
            'Sending for Q${provider.targetQuarter} ${provider.targetYear}',
            style: const TextStyle(fontWeight: FontWeight.w500),
          );
        }

        return Row(
          children: [
            const Text('Quarter: ', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButton<String>(
                value: targetKey,
                isExpanded: true,
                items: [
                  if (provider.currentQuarterHasSlots)
                    DropdownMenuItem<String>(
                      value: currentKey,
                      child: Text('Q${provider.currentQuarter} ${provider.currentYear} (Current)'),
                    ),
                  if (provider.nextQuarterHasSlots)
                    DropdownMenuItem<String>(
                      value: nextKey,
                      child: Text('Q${provider.nextQuarter} ${provider.nextYear} (Next)'),
                    ),
                ],
                onChanged: (value) {
                  if (value != null) {
                    final parts = value.split('_');
                    provider.setTargetQuarter(int.parse(parts[0]), int.parse(parts[1]));
                    _loadMember(); // Reload member detail for new quarter
                  }
                },
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildSendButtons() {
    final isOptedOut = _member!.optedOut;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (isOptedOut)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.orange.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.orange.shade200),
            ),
            child: Row(
              children: [
                Icon(Icons.block, size: 18, color: Colors.orange.shade700),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'This member has opted out of invitations',
                    style: TextStyle(color: Colors.orange.shade700, fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                onPressed: (!isOptedOut && _member!.canReceiveEmail) ? _sendEmail : null,
                icon: const Icon(Icons.email),
                label: const Text('Send Email'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: (!isOptedOut && _member!.canReceiveSms) ? _sendSms : null,
                icon: Icon(_member!.noSms ? Icons.sms_failed : Icons.sms),
                label: const Text('Send SMS'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDistrictCard() {
    final district = _member!.district!;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'District',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(district.name),
            if (district.interviewerName.isNotEmpty)
              Text(
                'Interviewer: ${district.interviewerName}',
                style: TextStyle(color: Colors.grey.shade600),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildCompanionshipCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Companionship Members',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            ..._member!.companionshipMembers.map((m) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: [
                      Icon(
                        m.hasBooking
                            ? Icons.check_circle
                            : Icons.remove,
                        size: 18,
                        color: m.hasBooking ? Colors.green : Colors.grey,
                      ),
                      const SizedBox(width: 8),
                      Text(m.name),
                      Text(
                        m.hasBooking ? ' (booked)' : ' (not booked)',
                        style: TextStyle(
                          color: m.hasBooking ? Colors.green.shade600 : Colors.grey.shade600,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }

  Widget _buildNotificationHistory() {
    final dateFormat = DateFormat('MMM d, yyyy h:mm a');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Notification History',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            if (_member!.notificationHistory.isEmpty)
              Text(
                'No notifications sent yet',
                style: TextStyle(color: Colors.grey.shade600),
              )
            else
              ..._member!.notificationHistory.map((n) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Row(
                      children: [
                        Icon(
                          n.method == 'email' ? Icons.email : Icons.sms,
                          size: 18,
                          color: n.success ? Colors.blue : Colors.red,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${n.method.toUpperCase()} - Q${n.quarter} ${n.year}',
                                style: const TextStyle(fontWeight: FontWeight.w500),
                              ),
                              Text(
                                dateFormat.format(n.sentAt),
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey.shade600,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          n.success ? Icons.check_circle : Icons.error,
                          size: 18,
                          color: n.success ? Colors.green : Colors.red,
                        ),
                      ],
                    ),
                  )),
          ],
        ),
      ),
    );
  }
}
