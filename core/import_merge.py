"""
Import merge service for smart member matching during imports.
Provides matching algorithm and preview generation for CSV/scrape imports.
"""
import re
from typing import Dict, List, Optional, Tuple, Any
from core.models import db, District, Companionship, Member, Booking, NotificationLog


# Match score constants
SCORE_NAME_AND_EMAIL = 100
SCORE_NAME_AND_PHONE = 95
SCORE_EMAIL_ONLY = 90
SCORE_PHONE_ONLY = 85
SCORE_NAME_ONLY = 50
SCORE_NO_MATCH = 0


def normalize_name(name: str) -> str:
    """
    Normalize name for comparison.
    Converts "Last, First" to "first last" format, lowercase, trimmed.
    """
    if not name:
        return ""
    name = name.strip().lower()
    # Handle "Last, First" format (with or without space after comma)
    if ',' in name:
        parts = [p.strip() for p in name.split(',', 1)]
        if len(parts) == 2:
            name = f"{parts[1]} {parts[0]}"
    return name


def normalize_email(email: str) -> str:
    """Normalize email: lowercase, trim whitespace."""
    if not email:
        return ""
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    """Normalize phone: digits only."""
    if not phone:
        return ""
    return re.sub(r'\D', '', phone)


def calculate_match_score(import_row: Dict, member: Member) -> Tuple[int, str]:
    """
    Calculate match score between import row and existing member.
    Returns (score, reason) tuple.

    Matching priority:
    1. Check match_email/match_phone first (LCR identity)
    2. Fall back to email/phone (catches manual corrections)
    """
    import_name = normalize_name(import_row.get('name', ''))
    import_email = normalize_email(import_row.get('email', ''))
    import_phone = normalize_phone(import_row.get('phone', ''))

    member_name = normalize_name(member.name)

    # Check both match_* fields and regular fields
    member_match_email = normalize_email(member.match_email or '')
    member_email = normalize_email(member.email or '')
    member_match_phone = normalize_phone(member.match_phone or '')
    member_phone = normalize_phone(member.phone or '')

    # Email matches if it matches either match_email or email
    email_match = False
    if import_email:
        email_match = (import_email == member_match_email) or (import_email == member_email)

    # Phone matches if it matches either match_phone or phone
    phone_match = False
    if import_phone:
        phone_match = (import_phone == member_match_phone) or (import_phone == member_phone)

    name_match = import_name == member_name if import_name and member_name else False

    # Scoring logic
    if name_match and email_match:
        return (SCORE_NAME_AND_EMAIL, "Name + Email match")
    elif name_match and phone_match:
        return (SCORE_NAME_AND_PHONE, "Name + Phone match")
    elif email_match:
        return (SCORE_EMAIL_ONLY, "Email match (name differs)")
    elif phone_match:
        return (SCORE_PHONE_ONLY, "Phone match (name differs)")
    elif name_match:
        return (SCORE_NAME_ONLY, "Name only (ambiguous)")
    else:
        return (SCORE_NO_MATCH, "No match")


def find_member_matches(import_row: Dict, existing_members: List[Member]) -> List[Dict]:
    """
    Find potential matches for an import row among existing members.
    Returns list of potential matches sorted by score (highest first).
    """
    matches = []
    for member in existing_members:
        score, reason = calculate_match_score(import_row, member)
        if score > SCORE_NO_MATCH:
            matches.append({
                'member_id': member.id,
                'member_name': member.name,
                'member_email': member.email,
                'member_phone': member.phone,
                'score': score,
                'reason': reason,
                'has_bookings': len(member.bookings) > 0
            })

    # Sort by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches


def build_import_preview(import_data: List[Dict]) -> Dict[str, Any]:
    """
    Build a preview of what will happen during import.

    Args:
        import_data: List of districts with companionships and members
                    Each district: {'name': str, 'interviewer': str, 'companionships': [...]}
                    Each companionship: {'companionship_id': str, 'members': [...]}
                    Each member: {'name': str, 'email': str, 'phone': str}

    Returns:
        Preview dict with categorized actions
    """
    # Get all existing members (active and inactive)
    existing_members = Member.query.all()
    existing_member_ids = {m.id for m in existing_members}

    # Flatten import data to list of member rows with district/companionship context
    import_rows = []
    for district_data in import_data:
        for comp_data in district_data['companionships']:
            for member_data in comp_data['members']:
                import_rows.append({
                    'name': member_data.get('name', ''),
                    'email': member_data.get('email', ''),
                    'phone': member_data.get('phone', ''),
                    'district_name': district_data['name'],
                    'district_interviewer': district_data['interviewer'],
                    'companionship_id': comp_data['companionship_id']
                })

    # Track which existing members were matched
    matched_member_ids = set()

    # Results
    members_to_update = []  # Exact matches (score >= 90)
    members_to_create = []  # New members
    ambiguous_matches = []  # Need user decision (50 <= score < 90)

    for import_row in import_rows:
        matches = find_member_matches(import_row, existing_members)

        if not matches:
            # No matches found - new member
            members_to_create.append({
                'name': import_row['name'],
                'email': import_row['email'],
                'phone': import_row['phone'],
                'district_name': import_row['district_name'],
                'companionship_id': import_row['companionship_id']
            })
        else:
            best_match = matches[0]

            if best_match['score'] >= 90:
                # Exact enough match - will update
                matched_member_ids.add(best_match['member_id'])

                # Determine what changes
                member = Member.query.get(best_match['member_id'])
                changes = []
                if member.companionship:
                    if member.companionship.district.name != import_row['district_name']:
                        changes.append(f"District: {member.companionship.district.name} -> {import_row['district_name']}")
                    else:
                        changes.append("Companionship updated")
                else:
                    changes.append("Will be assigned to companionship")

                if not member.is_active:
                    changes.append("Will be reactivated")

                members_to_update.append({
                    'existing_id': best_match['member_id'],
                    'name': import_row['name'],
                    'existing_name': member.name,
                    'email': import_row['email'],
                    'phone': import_row['phone'],
                    'match_score': best_match['score'],
                    'match_reason': best_match['reason'],
                    'changes': changes,
                    'district_name': import_row['district_name'],
                    'companionship_id': import_row['companionship_id']
                })
            else:
                # Ambiguous match - need user decision
                # Track all potential match IDs so we don't delete them
                for match in matches[:5]:
                    matched_member_ids.add(match['member_id'])

                ambiguous_matches.append({
                    'import_data': {
                        'name': import_row['name'],
                        'email': import_row['email'],
                        'phone': import_row['phone'],
                        'district_name': import_row['district_name'],
                        'companionship_id': import_row['companionship_id']
                    },
                    'potential_matches': matches[:5]  # Top 5 potential matches
                })

    # Find members not in import (and not potential ambiguous matches)
    unmatched_members = [m for m in existing_members if m.id not in matched_member_ids]

    members_to_deactivate = []
    members_to_delete = []

    for member in unmatched_members:
        booking_count = len(member.bookings)
        notification_count = len(member.notifications) if hasattr(member, 'notifications') else 0

        # Has booking or notification history - deactivate instead of delete
        if booking_count > 0 or notification_count > 0:
            last_booking = None
            if member.bookings:
                slots = [b.slot for b in member.bookings if b.slot]
                if slots:
                    sorted_slots = sorted(slots, key=lambda s: s.date, reverse=True)
                    last_booking = sorted_slots[0].date.isoformat() if sorted_slots else None

            members_to_deactivate.append({
                'id': member.id,
                'name': member.name,
                'email': member.email,
                'phone': member.phone,
                'booking_count': booking_count,
                'notification_count': notification_count,
                'last_booking': last_booking,
                'district_name': member.companionship.district.name if member.companionship else 'Unassigned',
                'is_currently_active': member.is_active
            })
        else:
            # No history at all - can be deleted
            members_to_delete.append({
                'id': member.id,
                'name': member.name,
                'email': member.email,
                'phone': member.phone,
                'district_name': member.companionship.district.name if member.companionship else 'Unassigned'
            })

    # Build stats
    stats = {
        'total_import': len(import_rows),
        'exact_matches': len(members_to_update),
        'ambiguous': len(ambiguous_matches),
        'new': len(members_to_create),
        'to_deactivate': len(members_to_deactivate),
        'to_delete': len(members_to_delete)
    }

    return {
        'members_to_update': members_to_update,
        'members_to_create': members_to_create,
        'ambiguous_matches': ambiguous_matches,
        'members_to_deactivate': members_to_deactivate,
        'members_to_delete': members_to_delete,
        'stats': stats,
        'import_data': import_data  # Keep original for execution
    }


def execute_import(preview: Dict, ambiguous_decisions: Dict[str, str], update_contact_decisions: Dict[str, str] = None, skip_delete: bool = False) -> Dict[str, Any]:
    """
    Execute the import based on preview and user decisions for ambiguous matches.

    Args:
        preview: The preview dict from build_import_preview
        ambiguous_decisions: Dict mapping ambiguous index to decision
                            Value is either 'new' or member_id as string
        update_contact_decisions: Dict mapping ambiguous index to member_id when contact should be updated
        skip_delete: If True, skip the deactivate/delete steps (used when clear_existing was selected)

    Returns:
        Result dict with counts
    """
    if update_contact_decisions is None:
        update_contact_decisions = {}
    import_data = preview['import_data']

    # Step 1: Delete all companionships (this removes their member associations)
    # but keeps members themselves
    Companionship.query.delete()
    db.session.flush()

    # Step 2: Create/update districts
    district_map = {}  # name -> District
    for district_data in import_data:
        district = District.query.filter_by(name=district_data['name']).first()
        if district:
            # Update interviewer name
            district.interviewer_name = district_data['interviewer']
        else:
            # Create new district
            district = District(
                name=district_data['name'],
                interviewer_name=district_data['interviewer']
            )
            db.session.add(district)
        db.session.flush()
        district_map[district_data['name']] = district

    # Step 3: Create new companionships from import
    companionship_map = {}  # (district_name, comp_id) -> Companionship
    for district_data in import_data:
        district = district_map[district_data['name']]
        for comp_data in district_data['companionships']:
            companionship = Companionship(district_id=district.id)
            db.session.add(companionship)
            db.session.flush()
            companionship_map[(district_data['name'], comp_data['companionship_id'])] = companionship

    # Step 4: Update matched members
    updated_count = 0
    for match_info in preview['members_to_update']:
        member = Member.query.get(match_info['existing_id'])
        if member:
            # Get the new companionship
            key = (match_info['district_name'], match_info['companionship_id'])
            companionship = companionship_map.get(key)

            if companionship:
                member.companionship_id = companionship.id
                member.is_active = True  # Reactivate if was inactive

                # Update match_* fields with import data (LCR values)
                if match_info.get('email'):
                    member.match_email = match_info['email']
                if match_info.get('phone'):
                    member.match_phone = match_info['phone']

                updated_count += 1

    # Step 5: Create new members
    created_count = 0
    for new_member in preview['members_to_create']:
        key = (new_member['district_name'], new_member['companionship_id'])
        companionship = companionship_map.get(key)

        if companionship:
            member = Member(
                name=new_member['name'],
                email=new_member.get('email', ''),
                phone=new_member.get('phone', ''),
                match_email=new_member.get('email', ''),
                match_phone=new_member.get('phone', ''),
                companionship_id=companionship.id,
                is_active=True
            )
            db.session.add(member)
            created_count += 1

    # Step 6: Handle ambiguous decisions
    ambiguous_resolved = 0
    for idx, decision in ambiguous_decisions.items():
        idx = int(idx)
        if idx < len(preview['ambiguous_matches']):
            ambiguous_info = preview['ambiguous_matches'][idx]
            import_info = ambiguous_info['import_data']

            key = (import_info['district_name'], import_info['companionship_id'])
            companionship = companionship_map.get(key)

            if companionship:
                if decision == 'new':
                    # Create as new member
                    member = Member(
                        name=import_info['name'],
                        email=import_info.get('email', ''),
                        phone=import_info.get('phone', ''),
                        match_email=import_info.get('email', ''),
                        match_phone=import_info.get('phone', ''),
                        companionship_id=companionship.id,
                        is_active=True
                    )
                    db.session.add(member)
                    created_count += 1
                else:
                    # Match to existing member
                    member_id = int(decision)
                    member = Member.query.get(member_id)
                    if member:
                        member.companionship_id = companionship.id
                        member.is_active = True
                        if import_info.get('email'):
                            member.match_email = import_info['email']
                        if import_info.get('phone'):
                            member.match_phone = import_info['phone']

                        # Check if user wants to update contact info too
                        if str(idx) in update_contact_decisions and update_contact_decisions[str(idx)] == str(member_id):
                            if import_info.get('email'):
                                member.email = import_info['email']
                            if import_info.get('phone'):
                                member.phone = import_info['phone']

                        updated_count += 1

                ambiguous_resolved += 1

    # Step 7: Mark unmatched members with bookings as inactive (skip if clear_existing was used)
    deactivated_count = 0
    if not skip_delete:
        for deactivate_info in preview['members_to_deactivate']:
            member = Member.query.get(deactivate_info['id'])
            if member:
                member.is_active = False
                member.companionship_id = None
                deactivated_count += 1

    # Step 8: Delete unmatched members without bookings (skip if clear_existing was used)
    deleted_count = 0
    if not skip_delete:
        for delete_info in preview['members_to_delete']:
            member = Member.query.get(delete_info['id'])
            if member:
                # Delete notification logs first (foreign key constraint)
                NotificationLog.query.filter_by(member_id=member.id).delete()
                db.session.delete(member)
                deleted_count += 1

    db.session.commit()

    return {
        'updated': updated_count,
        'created': created_count,
        'deactivated': deactivated_count,
        'deleted': deleted_count,
        'ambiguous_resolved': ambiguous_resolved
    }
