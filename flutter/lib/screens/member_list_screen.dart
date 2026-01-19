import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/auth_provider.dart';
import '../providers/members_provider.dart';
import '../models/member.dart';
import 'login_screen.dart';
import 'member_detail_screen.dart';

class MemberListScreen extends StatefulWidget {
  const MemberListScreen({super.key});

  @override
  State<MemberListScreen> createState() => _MemberListScreenState();
}

class _MemberListScreenState extends State<MemberListScreen> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Load data when screen initializes
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<MembersProvider>();
      provider.loadDistricts();
      provider.loadMembers();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      final authProvider = context.read<AuthProvider>();
      await authProvider.logout();
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const LoginScreen()),
        );
      }
    }
  }

  Future<void> _sendBulkSms() async {
    final provider = context.read<MembersProvider>();
    final selectedCount = provider.selectedMembers.where((m) => m.canReceiveSms).length;

    if (selectedCount == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No selected members have valid phone numbers')),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Send SMS'),
        content: Text(
          Platform.isAndroid
              ? 'Send SMS to $selectedCount members using your phone plan?'
              : 'This will open your Messages app for each of the $selectedCount members.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Send'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    if (!mounted) return;

    // Show progress indicator
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => const AlertDialog(
        content: Row(
          children: [
            CircularProgressIndicator(),
            SizedBox(width: 16),
            Text('Sending SMS...'),
          ],
        ),
      ),
    );

    final result = await provider.sendBulkSms();

    if (mounted) {
      Navigator.pop(context); // Close progress dialog
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result['message'] ?? 'Done')),
      );
    }
  }

  Future<void> _sendBulkEmail() async {
    final provider = context.read<MembersProvider>();
    final selectedCount = provider.selectedMembers.where((m) => m.canReceiveEmail).length;

    if (selectedCount == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No selected members have valid email addresses')),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Send Emails'),
        content: Text('Send invitation emails to $selectedCount members?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Send'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    if (!mounted) return;

    // Show progress indicator
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => const AlertDialog(
        content: Row(
          children: [
            CircularProgressIndicator(),
            SizedBox(width: 16),
            Text('Sending emails...'),
          ],
        ),
      ),
    );

    final result = await provider.sendBulkEmail();

    if (mounted) {
      Navigator.pop(context); // Close progress dialog
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result['message'] ?? 'Done')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Consumer<MembersProvider>(
          builder: (context, provider, _) {
            return Text('Q${provider.currentQuarter} ${provider.currentYear} Invitations');
          },
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => context.read<MembersProvider>().loadMembers(),
            tooltip: 'Refresh',
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: _logout,
            tooltip: 'Logout',
          ),
        ],
      ),
      body: Column(
        children: [
          // Filters
          _buildFilters(),

          // Selection actions bar
          _buildSelectionBar(),

          // Member list
          Expanded(child: _buildMemberList()),
        ],
      ),
    );
  }

  Widget _buildFilters() {
    return Consumer<MembersProvider>(
      builder: (context, provider, _) {
        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.grey.shade100,
            border: Border(bottom: BorderSide(color: Colors.grey.shade300)),
          ),
          child: Column(
            children: [
              // Search bar
              TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  hintText: 'Search by name...',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: provider.searchQuery.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear),
                          onPressed: () {
                            _searchController.clear();
                            provider.clearSearch();
                          },
                        )
                      : null,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  filled: true,
                  fillColor: Colors.white,
                  contentPadding: const EdgeInsets.symmetric(vertical: 0),
                ),
                onChanged: provider.setSearchQuery,
              ),
              const SizedBox(height: 12),

              // District filter
              Row(
                children: [
                  const Text('District: '),
                  const SizedBox(width: 8),
                  Expanded(
                    child: DropdownButton<int?>(
                      value: provider.filterDistrictId,
                      isExpanded: true,
                      hint: const Text('All Districts'),
                      items: [
                        const DropdownMenuItem<int?>(
                          value: null,
                          child: Text('All Districts'),
                        ),
                        ...provider.districts.map((d) => DropdownMenuItem<int?>(
                              value: d.id,
                              child: Text(d.name),
                            )),
                      ],
                      onChanged: (value) => provider.setDistrictFilter(value),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              // Needs invite toggle
              Row(
                children: [
                  Switch(
                    value: provider.filterNeedsInviteOnly,
                    onChanged: provider.setNeedsInviteFilter,
                  ),
                  const Text('Show only members who need invitations'),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSelectionBar() {
    return Consumer<MembersProvider>(
      builder: (context, provider, _) {
        final filteredMembers = provider.filteredMembers;
        final selectedInView = filteredMembers
            .where((m) => provider.selectedMemberIds.contains(m.id))
            .length;
        final totalCount = filteredMembers.length;

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: selectedInView > 0 ? Colors.blue.shade50 : Colors.white,
            border: Border(bottom: BorderSide(color: Colors.grey.shade300)),
          ),
          child: Row(
            children: [
              // Select all checkbox
              Checkbox(
                value: provider.allSelected && totalCount > 0,
                tristate: true,
                onChanged: (_) => provider.toggleSelectAll(),
              ),
              Text(
                selectedInView > 0
                    ? '$selectedInView of $totalCount selected'
                    : '$totalCount members',
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
              const Spacer(),

              // Bulk action buttons (show if any members are selected across all views)
              if (provider.selectedMemberIds.isNotEmpty) ...[
                ElevatedButton.icon(
                  onPressed: _sendBulkSms,
                  icon: const Icon(Icons.sms, size: 18),
                  label: const Text('SMS'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  onPressed: _sendBulkEmail,
                  icon: const Icon(Icons.email, size: 18),
                  label: const Text('Email'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Widget _buildMemberList() {
    return Consumer<MembersProvider>(
      builder: (context, provider, _) {
        if (provider.isLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (provider.error != null) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
                const SizedBox(height: 16),
                Text(provider.error!),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () => provider.loadMembers(),
                  child: const Text('Retry'),
                ),
              ],
            ),
          );
        }

        final filteredMembers = provider.filteredMembers;

        if (provider.members.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.check_circle_outline, size: 48, color: Colors.green.shade300),
                const SizedBox(height: 16),
                const Text(
                  'All members have scheduled their interviews!',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          );
        }

        if (filteredMembers.isEmpty && provider.searchQuery.isNotEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.search_off, size: 48, color: Colors.grey.shade400),
                const SizedBox(height: 16),
                Text(
                  'No members match "${provider.searchQuery}"',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey.shade600),
                ),
              ],
            ),
          );
        }

        return RefreshIndicator(
          onRefresh: () => provider.loadMembers(),
          child: ListView.builder(
            itemCount: filteredMembers.length,
            itemBuilder: (context, index) {
              final member = filteredMembers[index];
              return _MemberListTile(
                member: member,
                isSelected: provider.selectedMemberIds.contains(member.id),
                onToggle: () => provider.toggleMemberSelection(member.id),
                onTap: () => _openMemberDetail(member),
              );
            },
          ),
        );
      },
    );
  }

  void _openMemberDetail(Member member) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MemberDetailScreen(memberId: member.id),
      ),
    );
  }
}

class _MemberListTile extends StatelessWidget {
  final Member member;
  final bool isSelected;
  final VoidCallback onToggle;
  final VoidCallback onTap;

  const _MemberListTile({
    required this.member,
    required this.isSelected,
    required this.onToggle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MMM d');

    return ListTile(
      leading: Checkbox(
        value: isSelected,
        onChanged: (_) => onToggle(),
      ),
      title: Text(
        member.name,
        style: const TextStyle(fontWeight: FontWeight.w500),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (member.district != null)
            Text(
              member.district!.name,
              style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
            ),
          Row(
            children: [
              if (member.canReceiveEmail)
                Icon(Icons.email, size: 14, color: Colors.grey.shade500),
              if (member.canReceiveEmail) const SizedBox(width: 4),
              if (member.canReceiveSms)
                Icon(Icons.sms, size: 14, color: Colors.grey.shade500),
              if (member.lastNotification != null) ...[
                const SizedBox(width: 8),
                Text(
                  'Last: ${dateFormat.format(member.lastNotification!)}',
                  style: TextStyle(color: Colors.grey.shade500, fontSize: 12),
                ),
              ],
            ],
          ),
        ],
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}
