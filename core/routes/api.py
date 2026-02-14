"""
JSON API endpoints for mobile app integration.
Provides JWT authentication and member/notification management.
"""
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_mail import Message
from functools import wraps
from datetime import datetime, timedelta
# Password verification done via Flask-User's user_manager
import jwt
import re

from core.models import db, User, Member, District, Companionship, InterviewSlot, Booking, NotificationLog, MessageTemplates
from core.shared import mail
from core import services

api_bp = Blueprint('api', __name__, url_prefix='/api')

# JWT Configuration
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24


def get_jwt_secret():
    """Get JWT secret from app config"""
    return current_app.config.get('SECRET_KEY', 'fallback-secret-key')


def create_token(user_id, email, role):
    """Create a JWT token for a user"""
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def token_required(f):
    """Decorator to require JWT token for API endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            # Verify user still exists and is active
            user = User.query.get(payload['user_id'])
            if not user or not user.active:
                return jsonify({'error': 'User not found or inactive'}), 401
            request.current_user = user
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated


def get_current_quarter():
    """Get current quarter (1-4) and year"""
    now = datetime.now()
    quarter = ((now.month - 1) // 3) + 1
    return quarter, now.year


# =============================================================================
# Authentication Endpoints
# =============================================================================

@api_bp.route('/auth/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT token.

    Request body:
        {"email": "user@example.com", "password": "secret"}

    Response:
        {"token": "jwt...", "user": {"id": 1, "email": "...", "role": "admin"}}
    """
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    user = User.query.filter_by(email=data['email']).first()

    # Use Flask-User's password verification (compatible with its hash format)
    user_manager = current_app.user_manager
    if not user or not user_manager.verify_password(data['password'], user.password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.active:
        return jsonify({'error': 'Account is disabled'}), 401

    token = create_token(user.id, user.email, user.role)

    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'role': user.role
        }
    })


@api_bp.route('/auth/me', methods=['GET'])
@token_required
def get_current_user():
    """Get current authenticated user info"""
    user = request.current_user
    return jsonify({
        'id': user.id,
        'email': user.email,
        'role': user.role
    })


# =============================================================================
# Quarter Information
# =============================================================================

@api_bp.route('/quarter/current', methods=['GET'])
@token_required
def get_quarter_info():
    """Get current quarter and year"""
    quarter, year = get_current_quarter()
    return jsonify({
        'quarter': quarter,
        'year': year
    })


@api_bp.route('/quarter/available', methods=['GET'])
@token_required
def get_available_quarters():
    """Get current and next quarter with slot availability info"""
    from sqlalchemy import func

    today = datetime.now().date()
    current_quarter, current_year = get_current_quarter()
    next_quarter = current_quarter + 1 if current_quarter < 4 else 1
    next_year = current_year if current_quarter < 4 else current_year + 1

    # Check if current quarter has any slots
    current_has_slots = InterviewSlot.query.filter(
        InterviewSlot.quarter == current_quarter,
        func.extract('year', InterviewSlot.date) == current_year,
        InterviewSlot.date >= today
    ).first() is not None

    # Check if next quarter has any slots
    next_has_slots = InterviewSlot.query.filter(
        InterviewSlot.quarter == next_quarter,
        func.extract('year', InterviewSlot.date) == next_year
    ).first() is not None

    return jsonify({
        'current': {
            'quarter': current_quarter,
            'year': current_year,
            'has_slots': current_has_slots,
            'label': f'Q{current_quarter} {current_year}'
        },
        'next': {
            'quarter': next_quarter,
            'year': next_year,
            'has_slots': next_has_slots,
            'label': f'Q{next_quarter} {next_year}'
        }
    })


# =============================================================================
# District Endpoints
# =============================================================================

@api_bp.route('/districts', methods=['GET'])
@token_required
def get_districts():
    """Get all districts"""
    districts = District.query.all()
    return jsonify({
        'districts': [{
            'id': d.id,
            'name': d.name,
            'interviewer_name': d.interviewer_name,
            'companionship_count': len(d.companionships),
            'member_count': sum(len(c.members) for c in d.companionships)
        } for d in districts]
    })


# =============================================================================
# Member Endpoints
# =============================================================================

@api_bp.route('/members', methods=['GET'])
@token_required
def get_members():
    """
    Get members with optional filtering.

    Query params:
        district_id: Filter by district
        filter: Booking filter mode:
            'all' - show all members (default)
            'not_booked' - only members who have not booked
            'companionship_not_booked' - only members where no one in companionship has booked
            'upcoming_7_days' - only members with appointments in the next 7 days
        needs_invite: (deprecated, same as filter=not_booked) If 'true', only return members without bookings
        quarter: Target quarter (1-4), defaults to current
        year: Target year, defaults to current

    Response includes target quarter info and member details with booking status.
    """
    current_quarter, current_year = get_current_quarter()
    next_quarter = current_quarter + 1 if current_quarter < 4 else 1
    next_year = current_year if current_quarter < 4 else current_year + 1

    # Get target quarter from params (default to current)
    target_quarter = request.args.get('quarter', type=int, default=current_quarter)
    target_year = request.args.get('year', type=int, default=current_year)

    # Validate: only allow current or next quarter
    valid_quarters = [(current_quarter, current_year), (next_quarter, next_year)]
    if (target_quarter, target_year) not in valid_quarters:
        target_quarter = current_quarter
        target_year = current_year

    # Determine filter mode
    filter_mode = request.args.get('filter', 'all')
    # Backward compat: needs_invite=true maps to 'not_booked'
    if request.args.get('needs_invite', '').lower() == 'true' and filter_mode == 'all':
        filter_mode = 'not_booked'

    # Special handling for upcoming_7_days filter
    if filter_mode == 'upcoming_7_days':
        today = datetime.now().date()
        seven_days_from_now = today + timedelta(days=7)

        # Query members with bookings in the next 7 days
        query = db.session.query(Member, InterviewSlot, Booking).join(
            Companionship, Member.companionship_id == Companionship.id
        ).join(
            District, Companionship.district_id == District.id
        ).join(
            Booking, Member.id == Booking.member_id
        ).join(
            InterviewSlot, Booking.slot_id == InterviewSlot.id
        ).filter(
            InterviewSlot.date >= today,
            InterviewSlot.date <= seven_days_from_now
        )

        # Filter by district if specified
        district_id = request.args.get('district_id')
        if district_id:
            query = query.filter(District.id == int(district_id))

        query = query.order_by(InterviewSlot.date, InterviewSlot.start_time)
        rows = query.all()

        result = []
        for member, slot, booking in rows:
            last_notification = NotificationLog.query.filter_by(
                member_id=member.id
            ).order_by(NotificationLog.sent_at.desc()).first()

            district = member.companionship.district

            result.append({
                'id': member.id,
                'name': member.name,
                'email': member.email,
                'phone': member.phone,
                'no_sms': member.no_sms,
                'opted_out': member.opted_out,
                'has_booking': True,
                'booking_date': slot.date.isoformat(),
                'booking_time': slot.start_time.strftime('%H:%M'),
                'booking_duration': slot.duration,
                'interview_type': booking.interview_type,
                'district': {
                    'id': district.id,
                    'name': district.name,
                    'interviewer_name': district.interviewer_name
                },
                'companionship_id': member.companionship_id,
                'last_notification': last_notification.sent_at.isoformat() if last_notification else None,
                'scheduling_link': url_for('public.schedule', token=member.token, q=target_quarter, y=target_year, _external=True)
            })

        return jsonify({
            'members': result,
            'quarter': target_quarter,
            'year': target_year,
            'total_count': len(result)
        })

    # Build base query for other filters
    query = Member.query.join(Companionship).join(District)

    # Filter by district
    district_id = request.args.get('district_id')
    if district_id:
        query = query.filter(District.id == int(district_id))

    members = query.all()

    # Pre-compute companionship booking status for 'companionship_not_booked' filter
    companionship_has_booking = {}
    if filter_mode == 'companionship_not_booked':
        for member in members:
            comp_id = member.companionship_id
            if comp_id not in companionship_has_booking:
                # Check if ANY member in this companionship has a booking
                has_any = False
                for comp_member in member.companionship.members:
                    if comp_member.has_booking_for_quarter(target_quarter, target_year):
                        has_any = True
                        break
                companionship_has_booking[comp_id] = has_any

    # Build response with booking status
    result = []
    for member in members:
        has_booking = member.has_booking_for_quarter(target_quarter, target_year)

        # Apply filter
        if filter_mode == 'not_booked' and has_booking:
            continue
        if filter_mode == 'companionship_not_booked' and companionship_has_booking.get(member.companionship_id, False):
            continue

        # Get last notification
        last_notification = NotificationLog.query.filter_by(
            member_id=member.id
        ).order_by(NotificationLog.sent_at.desc()).first()

        district = member.companionship.district

        result.append({
            'id': member.id,
            'name': member.name,
            'email': member.email,
            'phone': member.phone,
            'no_sms': member.no_sms,
            'opted_out': member.opted_out,
            'has_booking': has_booking,
            'district': {
                'id': district.id,
                'name': district.name,
                'interviewer_name': district.interviewer_name
            },
            'companionship_id': member.companionship_id,
            'last_notification': last_notification.sent_at.isoformat() if last_notification else None,
            'scheduling_link': url_for('public.schedule', token=member.token, q=target_quarter, y=target_year, _external=True)
        })

    return jsonify({
        'members': result,
        'quarter': target_quarter,
        'year': target_year,
        'total_count': len(result)
    })


@api_bp.route('/members/<int:member_id>', methods=['GET'])
@token_required
def get_member_detail(member_id):
    """
    Get detailed member info including companionship members and notification history.
    """
    member = Member.query.get_or_404(member_id)
    current_quarter, current_year = get_current_quarter()

    # Accept quarter params (same as list endpoint)
    target_quarter = request.args.get('quarter', type=int, default=current_quarter)
    target_year = request.args.get('year', type=int, default=current_year)

    # Get companionship members
    companionship_members = []
    if member.companionship:
        for m in member.companionship.members:
            if m.id != member.id:
                companionship_members.append({
                    'id': m.id,
                    'name': m.name,
                    'has_booking': m.has_booking_for_quarter(target_quarter, target_year)
                })

    # Get notification history
    notifications = NotificationLog.query.filter_by(
        member_id=member.id
    ).order_by(NotificationLog.sent_at.desc()).limit(20).all()

    district = member.companionship.district if member.companionship else None

    return jsonify({
        'id': member.id,
        'name': member.name,
        'email': member.email,
        'phone': member.phone,
        'no_sms': member.no_sms,
        'opted_out': member.opted_out,
        'has_booking': member.has_booking_for_quarter(target_quarter, target_year),
        'district': {
            'id': district.id,
            'name': district.name,
            'interviewer_name': district.interviewer_name
        } if district else None,
        'companionship_id': member.companionship_id,
        'companionship_members': companionship_members,
        'scheduling_link': url_for('public.schedule', token=member.token, q=target_quarter, y=target_year, _external=True),
        'notification_history': [{
            'id': n.id,
            'method': n.method,
            'sent_at': n.sent_at.isoformat(),
            'quarter': n.quarter,
            'year': n.year,
            'success': n.success,
            'error_message': n.error_message
        } for n in notifications],
        'quarter': target_quarter,
        'year': target_year
    })


@api_bp.route('/members/<int:member_id>/log-notification', methods=['POST'])
@token_required
def log_notification(member_id):
    """
    Log that a notification was sent via native app (email/SMS).
    Used when mobile app sends via device's native email/SMS apps.

    Request body:
        {"method": "email" or "sms", "success": true/false, "error_message": "optional"}
    """
    member = Member.query.get_or_404(member_id)
    data = request.get_json()

    if not data or not data.get('method'):
        return jsonify({'error': 'Method (email/sms) is required'}), 400

    method = data['method'].lower()
    if method not in ['email', 'sms']:
        return jsonify({'error': 'Method must be "email" or "sms"'}), 400

    current_quarter, current_year = get_current_quarter()
    quarter = data.get('quarter', current_quarter)
    year = data.get('year', current_year)

    log = NotificationLog(
        member_id=member.id,
        method=method,
        quarter=quarter,
        year=year,
        success=data.get('success', True),
        error_message=data.get('error_message')
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'notification_id': log.id,
        'message': f'{method.upper()} notification logged for {member.name}'
    })


# =============================================================================
# Bulk Notification Endpoints
# =============================================================================

@api_bp.route('/notifications/send-bulk-email', methods=['POST'])
@token_required
def send_bulk_email():
    """
    Send scheduling invitation emails to selected members via server SMTP.

    Request body:
        {"member_ids": [1, 2, 3, ...], "quarter": 1, "year": 2026}

    Response:
        {"sent": 5, "failed": 1, "errors": [...]}
    """
    data = request.get_json()

    if not data or not data.get('member_ids'):
        return jsonify({'error': 'member_ids array is required'}), 400

    member_ids = data['member_ids']
    if not isinstance(member_ids, list):
        return jsonify({'error': 'member_ids must be an array'}), 400

    current_quarter, current_year = get_current_quarter()
    next_quarter = current_quarter + 1 if current_quarter < 4 else 1
    next_year = current_year if current_quarter < 4 else current_year + 1

    # Get target quarter from request (default to current)
    target_quarter = data.get('quarter', current_quarter)
    target_year = data.get('year', current_year)

    # Validate: only allow current or next quarter
    valid_quarters = [(current_quarter, current_year), (next_quarter, next_year)]
    if (target_quarter, target_year) not in valid_quarters:
        target_quarter = current_quarter
        target_year = current_year

    # Load email config
    services.apply_email_config()
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not sender_email:
        return jsonify({'error': 'Email not configured on server'}), 500

    sent_count = 0
    failed_count = 0
    errors = []

    for member_id in member_ids:
        member = Member.query.get(member_id)
        if not member:
            errors.append(f'Member {member_id} not found')
            failed_count += 1
            continue

        if member.opted_out:
            errors.append(f'{member.name}: Opted out')
            failed_count += 1
            continue

        if not member.email:
            errors.append(f'{member.name}: No email address')
            failed_count += 1
            continue

        # Skip if already has booking for target quarter
        if member.has_booking_for_quarter(target_quarter, target_year):
            errors.append(f'{member.name}: Already has booking for Q{target_quarter}')
            failed_count += 1
            continue

        try:
            link = url_for('public.schedule', token=member.token, q=target_quarter, y=target_year, _external=True)

            # Use message templates for formatting
            subject, body = services.format_email_notification(member, link, target_quarter, target_year)
            msg = Message(subject, sender=sender_email, recipients=[member.email])
            msg.html = body
            msg.body = services.html_to_plain_text(body)
            mail.send(msg)

            # Log the notification
            log = NotificationLog(
                member_id=member.id,
                method='email',
                quarter=target_quarter,
                year=target_year,
                success=True
            )
            db.session.add(log)
            sent_count += 1

        except Exception as e:
            # Log failed notification
            log = NotificationLog(
                member_id=member.id,
                method='email',
                quarter=target_quarter,
                year=target_year,
                success=False,
                error_message=str(e)
            )
            db.session.add(log)
            errors.append(f'{member.name}: {str(e)}')
            failed_count += 1

    db.session.commit()

    return jsonify({
        'sent': sent_count,
        'failed': failed_count,
        'errors': errors,
        'quarter': target_quarter,
        'year': target_year,
        'message': f'Sent {sent_count} emails for Q{target_quarter} {target_year}, {failed_count} failed'
    })


@api_bp.route('/notifications/send-reminder-email', methods=['POST'])
@token_required
def send_reminder_email():
    """
    Send appointment reminder emails to members with upcoming appointments.

    Request body:
        {"member_ids": [1, 2, 3, ...], "quarter": 1, "year": 2026}

    Response:
        {"sent": 5, "failed": 1, "errors": [...]}
    """
    data = request.get_json()

    if not data or not data.get('member_ids'):
        return jsonify({'error': 'member_ids array is required'}), 400

    member_ids = data['member_ids']
    if not isinstance(member_ids, list):
        return jsonify({'error': 'member_ids must be an array'}), 400

    current_quarter, current_year = get_current_quarter()
    target_quarter = data.get('quarter', current_quarter)
    target_year = data.get('year', current_year)

    # Load email config
    services.apply_email_config()
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not sender_email:
        return jsonify({'error': 'Email not configured on server'}), 500

    sent_count = 0
    failed_count = 0
    errors = []

    for member_id in member_ids:
        member = Member.query.get(member_id)
        if not member:
            errors.append(f'Member {member_id} not found')
            failed_count += 1
            continue

        if member.opted_out:
            errors.append(f'{member.name}: Opted out')
            failed_count += 1
            continue

        if not member.email:
            errors.append(f'{member.name}: No email address')
            failed_count += 1
            continue

        # Get the member's upcoming booking
        today = datetime.now().date()
        seven_days = today + timedelta(days=7)
        booking = db.session.query(Booking, InterviewSlot).join(
            InterviewSlot, Booking.slot_id == InterviewSlot.id
        ).filter(
            Booking.member_id == member.id,
            InterviewSlot.date >= today,
            InterviewSlot.date <= seven_days
        ).first()

        if not booking:
            errors.append(f'{member.name}: No upcoming appointment in next 7 days')
            failed_count += 1
            continue

        booking_record, slot = booking

        try:
            link = url_for('public.schedule', token=member.token, q=target_quarter, y=target_year, _external=True)

            # Format the appointment date/time
            weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            months = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
            weekday = weekdays[slot.date.weekday()]
            month = months[slot.date.month - 1]
            hour = slot.start_time.hour
            minute = slot.start_time.strftime('%M')
            period = 'PM' if hour >= 12 else 'AM'
            hour12 = hour if hour <= 12 else hour - 12
            if hour12 == 0:
                hour12 = 12
            formatted_datetime = f'{weekday}, {month} {slot.date.day} at {hour12}:{minute} {period}'

            # Convert "Last, First" to "First Last"
            display_name = member.name
            if ',' in member.name:
                parts = [p.strip() for p in member.name.split(',')]
                if len(parts) >= 2:
                    display_name = f'{parts[1]} {parts[0]}'

            # Build reminder email
            subject = 'Reminder: Your Ministering Interview Appointment'
            body = f'''<p>Hi {display_name},</p>

<p>This is a friendly reminder that your ministering interview is scheduled for:</p>

<p><strong>{formatted_datetime}</strong></p>

<p>If you need to change or cancel your appointment, please use the link below:</p>
<p><a href="{link}">{link}</a></p>

<p>We look forward to seeing you!</p>'''

            msg = Message(subject, sender=sender_email, recipients=[member.email])
            msg.html = body
            msg.body = services.html_to_plain_text(body)
            mail.send(msg)

            # Log the notification
            log = NotificationLog(
                member_id=member.id,
                method='email',
                quarter=target_quarter,
                year=target_year,
                success=True
            )
            db.session.add(log)
            sent_count += 1

        except Exception as e:
            # Log failed notification
            log = NotificationLog(
                member_id=member.id,
                method='email',
                quarter=target_quarter,
                year=target_year,
                success=False,
                error_message=str(e)
            )
            db.session.add(log)
            errors.append(f'{member.name}: {str(e)}')
            failed_count += 1

    db.session.commit()

    return jsonify({
        'sent': sent_count,
        'failed': failed_count,
        'errors': errors,
        'quarter': target_quarter,
        'year': target_year,
        'message': f'Sent {sent_count} reminder emails, {failed_count} failed'
    })


@api_bp.route('/notifications/log-bulk', methods=['POST'])
@token_required
def log_bulk_notifications():
    """
    Log multiple notifications sent via native app (for bulk SMS from Android).

    Request body:
        {"member_ids": [1, 2, 3], "method": "sms", "success": true}
    """
    data = request.get_json()

    if not data or not data.get('member_ids') or not data.get('method'):
        return jsonify({'error': 'member_ids and method are required'}), 400

    member_ids = data['member_ids']
    method = data['method'].lower()
    success = data.get('success', True)

    if method not in ['email', 'sms']:
        return jsonify({'error': 'Method must be "email" or "sms"'}), 400

    current_quarter, current_year = get_current_quarter()
    quarter = data.get('quarter', current_quarter)
    year = data.get('year', current_year)
    logged_count = 0

    for member_id in member_ids:
        member = Member.query.get(member_id)
        if member:
            log = NotificationLog(
                member_id=member.id,
                method=method,
                quarter=quarter,
                year=year,
                success=success
            )
            db.session.add(log)
            logged_count += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'logged': logged_count,
        'message': f'Logged {logged_count} {method.upper()} notifications'
    })


@api_bp.route('/message-templates', methods=['GET'])
@token_required
def get_message_templates():
    """
    Get message templates for formatting notifications.
    Returns the customization settings that can be used by mobile apps.

    Templates are partially rendered - settings-based placeholders are filled in,
    but {name} and {link} remain for the client to substitute.
    """
    from core.models import DEFAULT_SMS, DEFAULT_EMAIL_SUBJECT, DEFAULT_EMAIL_BODY

    msg_config = MessageTemplates.get_or_create()
    quarter, year = get_current_quarter()

    # Get format helpers from the model
    org_name = msg_config.format_org_name()
    greeting = msg_config.format_greeting()
    instructions = msg_config.format_instructions()
    signature_html = msg_config.format_signature(for_html=True)
    signature_plain = msg_config.format_signature(for_html=False)

    # Get stored templates (or defaults)
    sms_template = msg_config.sms_template or DEFAULT_SMS
    email_subject = msg_config.email_subject_template or DEFAULT_EMAIL_SUBJECT
    email_body = msg_config.email_body_template or DEFAULT_EMAIL_BODY

    # Partially render templates - substitute settings, leave {name} and {link}
    # We need to escape {name} and {link} so they don't get substituted
    sms_rendered = sms_template.replace('{name}', '{{name}}').replace('{link}', '{{link}}').format(
        org_name=org_name,
        greeting=greeting,
        custom_message=msg_config.format_custom_message(for_sms=True),
        instructions=msg_config.format_instructions(for_sms=True),
        signature=signature_plain
    ).replace('{{name}}', '{name}').replace('{{link}}', '{link}')

    email_subject_rendered = email_subject.format(
        org_name=org_name,
        quarter=quarter,
        year=year
    )

    email_body_rendered = email_body.replace('{name}', '{{name}}').replace('{link}', '{{link}}').format(
        org_name=org_name,
        greeting=greeting,
        quarter=quarter,
        year=year,
        custom_message=msg_config.format_custom_message(),
        instructions=instructions,
        signature=signature_html
    ).replace('{{name}}', '{name}').replace('{{link}}', '{link}')

    # Clean up extra blank lines (allow one blank line, collapse multiple)
    import re
    sms_rendered = re.sub(r'\n{3,}', '\n\n', sms_rendered).strip()
    email_body_rendered = re.sub(r'\n{3,}', '\n\n', email_body_rendered).strip()

    # Create plain text version of email body for mailto: links (which don't support HTML)
    email_body_plain = services.html_to_plain_text(email_body_rendered)

    return jsonify({
        'organization_name': msg_config.organization_name or '',
        'greeting_style': msg_config.greeting_style or 'Dear',
        'greeting_prefix': greeting,
        'org_prefix': org_name,
        'custom_instructions': msg_config.custom_instructions or '',
        'signature_name': msg_config.signature_name or '',
        'signature_title': msg_config.signature_title or '',
        'signature': signature_plain,
        'quarter': quarter,
        'year': year,
        # Partially rendered templates - {name} and {link} remain as placeholders
        'sms_template': sms_rendered,
        'email_subject_template': email_subject_rendered,
        'email_body_template': email_body_rendered,
        'email_body_template_plain': email_body_plain  # Plain text version for mailto: links
    })
