/// District model representing an organizational unit
class District {
  final int id;
  final String name;
  final String interviewerName;
  final int? companionshipCount;
  final int? memberCount;

  District({
    required this.id,
    required this.name,
    required this.interviewerName,
    this.companionshipCount,
    this.memberCount,
  });

  factory District.fromJson(Map<String, dynamic> json) {
    return District(
      id: json['id'],
      name: json['name'],
      interviewerName: json['interviewer_name'] ?? '',
      companionshipCount: json['companionship_count'],
      memberCount: json['member_count'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'interviewer_name': interviewerName,
      'companionship_count': companionshipCount,
      'member_count': memberCount,
    };
  }

  @override
  String toString() => 'District($name)';
}
