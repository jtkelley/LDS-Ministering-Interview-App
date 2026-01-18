"""
Admin routes for the Ministering Interview application.
All routes require admin authentication via @admin_required decorator.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify, current_app
from flask_mail import Message
from flask_user import current_user
from datetime import datetime, timedelta
from sqlalchemy import func, extract
from collections import defaultdict
import secrets
import uuid
import threading
import io
import csv
import re

from models import db, User, UserInvitation, SystemConfig, District, Companionship, Member, InterviewSlot, Booking, NotificationLog, MessageTemplates
from utils import admin_required, group_results_by_district
from shared import mail, progress_store, progress_lock
import services

# Create blueprint with /admin URL prefix
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('')
def admin():
    # Check if admin exists first
    admin_exists = User.query.filter_by(role='admin').first()
    if not admin_exists:
        return redirect(url_for('public.setup_admin'))
    
    # Require login for admin access (Flask-User handles this)
    if not current_user.is_authenticated:
        return redirect(url_for('user.login', next=request.path))
    
    # Check if user has admin role
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('public.index'))
    
    # User is authenticated and is admin - proceed with rendering
    today = datetime.now().date()
    selected_district_id = request.args.get('district', type=int)
    show_past = request.args.get('show_past', 'false').lower() == 'true'
    
    # Calculate current quarter and previous quarter end date
    current_month = today.month
    current_quarter = ((current_month - 1) // 3) + 1
    previous_quarter = current_quarter - 1 if current_quarter > 1 else 4
    previous_year = today.year if previous_quarter < current_quarter else today.year - 1
    
    # End dates for quarters
    quarter_end_dates = {
        1: datetime(previous_year, 3, 31).date(),
        2: datetime(previous_year, 6, 30).date(),
        3: datetime(previous_year, 9, 30).date(),
        4: datetime(previous_year, 12, 31).date()
    }
    previous_quarter_end = quarter_end_dates[previous_quarter]
    min_cleanup_date = previous_quarter_end + timedelta(days=1)  # Start from the day after previous quarter ends
    
    query = InterviewSlot.query.filter(InterviewSlot.date >= today) if not show_past else InterviewSlot.query
    
    if selected_district_id:
        districts = District.query.filter_by(id=selected_district_id).all()
        district_slots = {}
        for district in districts:
            slots = query.filter_by(district_id=district.id).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
            district_slots[district.id] = slots
    else:
        districts = District.query.all()
        district_slots = {}
        for district in districts:
            slots = query.filter_by(district_id=district.id).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
            district_slots[district.id] = slots
    
    all_districts = District.query.all()
    has_districts = len(all_districts) > 0
    has_slots = InterviewSlot.query.first() is not None
    return render_template('admin_calendar.html', districts=districts, district_slots=district_slots, all_districts=all_districts, selected_district_id=selected_district_id, show_past=show_past, min_cleanup_date=min_cleanup_date, has_districts=has_districts, has_slots=has_slots)

@admin_bp.route('/delete_old_slots', methods=['POST'])
@admin_required
def delete_old_slots():
    cleanup_date_str = request.form.get('cleanup_date')
    if not cleanup_date_str:
        flash('Please select a date.')
        return redirect(url_for('admin.admin'))
    
    try:
        cleanup_date = datetime.strptime(cleanup_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format.')
        return redirect(url_for('admin.admin'))
    
    # Validate that cleanup_date is not in the current quarter
    current_month = datetime.now().month
    current_quarter = ((current_month - 1) // 3) + 1
    cleanup_quarter = ((cleanup_date.month - 1) // 3) + 1
    if cleanup_quarter == current_quarter and cleanup_date.year == datetime.now().year:
        flash('Cannot delete slots in the current quarter.')
        return redirect(url_for('admin.admin'))
    
    # Delete slots before the selected date, including their bookings
    old_slots = InterviewSlot.query.filter(InterviewSlot.date < cleanup_date).all()
    deleted_count = 0
    for slot in old_slots:
        bookings = Booking.query.filter_by(slot_id=slot.id).all()
        for booking in bookings:
            db.session.delete(booking)
        db.session.delete(slot)
        deleted_count += 1
    
    db.session.commit()
    flash(f'Deleted {deleted_count} old slots and their bookings.')
    return redirect(url_for('admin.admin'))

# User Management Routes
@admin_bp.route('/users')
@admin_required
def manage_users():
    users = User.query.all()
    invitations = UserInvitation.query.filter_by(is_used=False).all()
    return render_template('manage_users.html', users=users, invitations=invitations)

    # Notification Report Route
@admin_bp.route('/notification_report')
@admin_required
def notification_report():
    """Generate report of notification sends by quarter"""
    today = datetime.now().date()
    current_quarter = ((today.month - 1) // 3) + 1
    current_year = today.year

    # Allow filtering by quarter and year
    selected_quarter = request.args.get('quarter', current_quarter, type=int)
    selected_year = request.args.get('year', current_year, type=int)

    # Get all members grouped by district and companionship
    districts = District.query.order_by(District.name).all()
    report_data = []
    for district in districts:
        for companionship in district.companionships:
            for member in companionship.members:
                notifications = NotificationLog.query.filter_by(
                    member_id=member.id,
                    quarter=selected_quarter,
                    year=selected_year
                ).order_by(NotificationLog.sent_at.desc()).all()
                email_logs = [n for n in notifications if n.method == 'email']
                sms_logs = [n for n in notifications if n.method == 'sms']
                email_sent = len(email_logs) > 0
                sms_sent = len(sms_logs) > 0
                has_booking = member.has_booking_for_quarter(selected_quarter, selected_year)

                # Get the most recent email and SMS log details
                latest_email = email_logs[0] if email_logs else None
                latest_sms = sms_logs[0] if sms_logs else None

                report_data.append({
                    'member': member,
                    'district': district,
                    'companionship': companionship,
                    'email_sent': email_sent,
                    'email_success': latest_email.success if latest_email else False,
                    'email_sent_at': latest_email.sent_at if latest_email else None,
                    'email_error': latest_email.error_message if latest_email and not latest_email.success else None,
                    'sms_sent': sms_sent,
                    'sms_success': latest_sms.success if latest_sms else False,
                    'sms_sent_at': latest_sms.sent_at if latest_sms else None,
                    'sms_error': latest_sms.error_message if latest_sms and not latest_sms.success else None,
                    'has_booking': has_booking
                })

    total_members = len(report_data)
    email_sent_count = sum(1 for m in report_data if m['email_sent'])
    sms_sent_count = sum(1 for m in report_data if m['sms_sent'])
    no_notification_count = sum(1 for m in report_data if not m['email_sent'] and not m['sms_sent'])
    has_booking_count = sum(1 for m in report_data if m['has_booking'])

    # Get available quarters for dropdown (last 4 quarters)
    available_quarters = []
    for i in range(4):
        q = current_quarter - i
        y = current_year
        if q <= 0:
            q += 4
            y -= 1
        available_quarters.append({'quarter': q, 'year': y})

    return render_template('notification_report.html',
                         report_data=report_data,
                         selected_quarter=selected_quarter,
                         selected_year=selected_year,
                         total_members=total_members,
                         email_sent_count=email_sent_count,
                         sms_sent_count=sms_sent_count,
                         no_notification_count=no_notification_count,
                         has_booking_count=has_booking_count,
                         available_quarters=available_quarters)

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'interviewer')
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('admin.manage_users'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'error')
            return redirect(url_for('admin.manage_users'))
        
        # Check if invitation exists for this email
        if UserInvitation.query.filter_by(email=email, is_used=False).first():
            flash('An invitation already exists for this email.', 'error')
            return redirect(url_for('admin.manage_users'))
        
        try:
            # Check password length (Werkzeug limit is 72 bytes)
            if len(password.encode('utf-8')) > 72:
                flash('Password must be 72 bytes or less.', 'error')
                return redirect(url_for('admin.manage_users'))
            
            user = User(
                email=email,
                password=current_app.user_manager.hash_password(password),
                role=role,
                active=True,
                email_confirmed_at=datetime.now()
            )
            db.session.add(user)
            db.session.commit()
            flash(f'User {email} created successfully with role "{role}".', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'error')
        
        return redirect(url_for('admin.manage_users'))
    
    return render_template('create_user.html')

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent editing yourself or the last admin
    if user.id == current_user.id:
        flash('Cannot edit your own account here. Use "Change Password" in your profile.', 'warning')
        return redirect(url_for('admin.manage_users'))
    
    if request.method == 'POST':
        role = request.form.get('role')
        active = request.form.get('active') == 'on'
        
        # Prevent removing the last admin
        if user.role == 'admin' and role != 'admin':
            admin_count = User.query.filter_by(role='admin', active=True).count()
            if admin_count <= 1:
                flash('Cannot change role - this is the last active admin.', 'error')
                return redirect(url_for('admin.manage_users'))
        
        user.role = role
        user.active = active
        db.session.commit()
        flash(f'User {user.email} updated successfully.', 'success')
        return redirect(url_for('admin.manage_users'))
    
    return render_template('edit_user.html', user=user)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('admin.manage_users'))
    
    # Prevent deleting the last admin
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot delete the last admin account.', 'error')
            return redirect(url_for('admin.manage_users'))
    
    email = user.email
    db.session.delete(user)
    db.session.commit()
    flash(f'User {email} deleted successfully.', 'success')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/users/invite', methods=['GET', 'POST'])
@admin_required
def invite_user():
    if request.method == 'POST':
        email = request.form.get('email')
        role = request.form.get('role', 'interviewer')
        
        if not email:
            flash('Email is required.', 'error')
            return redirect(url_for('admin.invite_user'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'error')
            return redirect(url_for('admin.invite_user'))
        
        # Check if invitation already exists and is still valid
        existing_invite = UserInvitation.query.filter_by(email=email, is_used=False).first()
        if existing_invite:
            if existing_invite.expires_at > datetime.now():
                flash('An active invitation already exists for this email.', 'warning')
                return redirect(url_for('admin.invite_user'))
            else:
                # Delete expired invitation
                db.session.delete(existing_invite)
                db.session.commit()
        
        try:
            # Generate unique token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(days=7)
            
            invitation = UserInvitation(
                email=email,
                token=token,
                role=role,
                expires_at=expires_at,
                created_by_user_id=current_user.id
            )
            db.session.add(invitation)
            db.session.commit()
            
            # Send invitation email
            invite_link = url_for('public.accept_invitation', token=token, _external=True)
            
            # Load email config
            sender_email = services.apply_email_config()
            if not sender_email:
                flash('Email configuration not set up. Please configure email settings first.', 'error')
                db.session.delete(invitation)
                db.session.commit()
                return redirect(url_for('admin.invite_user'))
            
            print(f"Using MAIL_SERVER: {current_app.config.get('MAIL_SERVER')}, MAIL_PORT: {current_app.config.get('MAIL_PORT')}, MAIL_USE_TLS: {current_app.config.get('MAIL_USE_TLS')}")
            
            msg = Message(
                'You are invited to join the Ministering Interview App',
                sender=sender_email,
                recipients=[email]
            )
            msg.body = f'''You have been invited to join the Ministering Interview App as a {role}.

Click the link below to accept the invitation and set your password:

{invite_link}

This link will expire in 7 days.

If you did not expect this invitation, please ignore this email.
'''
            msg.html = f'''<p>You have been invited to join the Ministering Interview App as a <strong>{role}</strong>.</p>
<p><a href="{invite_link}">Click here to accept the invitation</a> and set your password.</p>
<p>This link will expire in 7 days.</p>
<p>If you did not expect this invitation, please ignore this email.</p>
'''
            mail.send(msg)
            
            flash(f'Invitation sent to {email} with role "{role}".', 'success')
            return redirect(url_for('admin.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error sending invitation: {str(e)}', 'error')
            return redirect(url_for('admin.invite_user'))
    
    return render_template('invite_user.html')

@admin_bp.route('/invitations/<int:invitation_id>/cancel', methods=['POST'])
@admin_required
def cancel_invitation(invitation_id):
    invitation = UserInvitation.query.get_or_404(invitation_id)
    
    if invitation.is_used:
        flash('Cannot cancel an accepted invitation.', 'error')
        return redirect(url_for('admin.manage_users'))
    
    email = invitation.email
    db.session.delete(invitation)
    db.session.commit()
    flash(f'Invitation cancelled for {email}.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/districts')
@admin_required
def manage_districts():
    districts = District.query.all()
    return render_template('manage_districts.html', districts=districts)


@admin_bp.route('/import_csv', methods=['GET', 'POST'])
@admin_required
def import_csv():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file selected.')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected.')
            return redirect(request.url)
        
        if not file.filename.endswith('.csv'):
            flash('File must be a CSV.')
            return redirect(request.url)
        
        try:
            import io
            import csv
            
            # Read the CSV content
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            reader = csv.DictReader(stream)
            results = list(reader)
            
            # Group by district and companionship_id
            from collections import defaultdict
            districts_data = defaultdict(lambda: {'companionships': defaultdict(list)})
            for row in results:
                district_name = row['district']
                interviewer = row['interviewer']
                comp_id = row['companionship_id']
                districts_data[district_name]['interviewer'] = interviewer
                districts_data[district_name]['companionships'][comp_id].append({
                    'name': row['name'],
                    'phone': row['phone'],
                    'email': row['email']
                })
            
            scraped_districts = []
            for district_name, data in districts_data.items():
                companionships = []
                for comp_id, members in data['companionships'].items():
                    companionships.append({
                        'companionship_id': comp_id,
                        'members': members
                    })
                scraped_districts.append({
                    'name': district_name,
                    'interviewer': data['interviewer'],
                    'companionships': companionships
                })
            
            # Store in session for confirmation
            session['uploaded_districts'] = scraped_districts
            return redirect(url_for('admin.import_csv_confirm'))
        
        except Exception as e:
            flash(f'Error processing CSV: {str(e)}')
            return redirect(request.url)
    
    return render_template('import_csv.html')

@admin_bp.route('/district/new', methods=['GET', 'POST'])
@admin_required
def new_district():
    if request.method == 'POST':
        name = request.form['name']
        interviewer = request.form['interviewer']
        district = District(name=name, interviewer_name=interviewer)
        db.session.add(district)
        db.session.commit()
        flash('District created successfully!')
        return redirect(url_for('admin.admin'))
    return render_template('new_district.html')

@admin_bp.route('/district/<int:id>')
@admin_required
def district_detail(id):
    district = District.query.get_or_404(id)
    return render_template('district_detail.html', district=district)

@admin_bp.route('/district/<int:id>/companionship/new', methods=['GET', 'POST'])
@admin_required
def new_companionship(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        companionship = Companionship(district_id=id)
        db.session.add(companionship)
        db.session.commit()
        
        # Handle existing members
        existing_member_ids = request.form.getlist('existing_members[]')
        for member_id in existing_member_ids:
            member = Member.query.get(int(member_id))
            if member and member.companionship.district_id == id:
                # Cancel existing bookings
                bookings = Booking.query.filter_by(member_id=member.id).all()
                for booking in bookings:
                    db.session.delete(booking)
                # Reassign to new companionship
                member.companionship_id = companionship.id
        
        # Add new members
        member_names = request.form.getlist('member_name[]')
        member_phones = request.form.getlist('member_phone[]')
        member_emails = request.form.getlist('member_email[]')
        
        for name, phone, email in zip(member_names, member_phones, member_emails):
            if name:  # Only require name
                member = Member(companionship_id =companionship.id, name=name, phone=phone, email=email)
                db.session.add(member)
        
        db.session.commit()
        flash('Companionship created successfully!')
        return redirect(url_for('admin.district_detail', id=id))
    
    # Get existing members from all districts for reassignment
    existing_members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name, Member.name).all()
    return render_template('new_companionship.html', district=district, existing_members=existing_members)

@admin_bp.route('/district/<int:id>/slots', methods=['GET', 'POST'])
@admin_required
def manage_slots(id):
    district = District.query.get_or_404(id)
    
    # Calculate default end date: end of current quarter
    today = datetime.now().date()
    current_month = today.month
    current_quarter = ((current_month - 1) // 3) + 1
    if current_quarter == 1:
        default_end_date = datetime(today.year, 3, 31).date()
    elif current_quarter == 2:
        default_end_date = datetime(today.year, 6, 30).date()
    elif current_quarter == 3:
        default_end_date = datetime(today.year, 9, 30).date()
    else:
        default_end_date = datetime(today.year, 12, 31).date()
    
    if request.method == 'POST':
        if 'day_of_week' in request.form:
            # Generate slots
            day_of_week = int(request.form['day_of_week'])
            start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
            duration = int(request.form['duration'])
            num_slots = int(request.form['num_slots'])
            start_date_str = request.form['start_date']
            end_date_str = request.form['end_date']
            
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format.')
                return redirect(url_for('admin.manage_slots', id=id))
            
            if start_date >= end_date:
                flash('Start date must be before end date.')
                return redirect(url_for('admin.manage_slots', id=id))
            
            # Generate slots for each occurrence of day_of_week between start_date and end_date
            current_date = start_date
            slots_created = 0
            skipped_slots = []
            while current_date <= end_date:
                if current_date.weekday() == day_of_week:
                    # Get existing slots for this date and district
                    existing_slots = InterviewSlot.query.filter_by(district_id=id, date=current_date).all()
                    for j in range(num_slots):
                        slot_time = (datetime.combine(current_date, start_time) + timedelta(minutes=duration * j)).time()
                        slot_end_time = (datetime.combine(current_date, slot_time) + timedelta(minutes=duration)).time()
                        
                        # Check for overlap with existing slots
                        overlap = False
                        for existing in existing_slots:
                            if (slot_time < existing.start_time + timedelta(minutes=existing.duration) and
                                slot_end_time > existing.start_time):
                                overlap = True
                                break
                        
                        if overlap:
                            skipped_slots.append(f"{current_date} at {slot_time}")
                        else:
                            slot = InterviewSlot(
                                district_id=id,
                                date=current_date,
                                start_time=slot_time,
                                duration=duration,
                                max_slots=10  # Max 10 members per slot (companionship-based)
                            )
                            db.session.add(slot)
                            slots_created += 1
                current_date += timedelta(days=1)
            
            db.session.commit()
            flash(f'Generated {slots_created} recurring slots!')
            if skipped_slots:
                combined_msg = "The following slots were skipped due to conflicts:<br>" + "<br>".join(skipped_slots)
                flash(combined_msg, 'warning')
            return redirect(url_for('admin.manage_slots', id=id))
        elif request.form.get('action') == 'delete_all':
            # Delete all slots for this district
            slots = InterviewSlot.query.filter_by(district_id=id).all()
            for slot in slots:
                bookings = Booking.query.filter_by(slot_id=slot.id).all()
                for booking in bookings:
                    db.session.delete(booking)
                db.session.delete(slot)
            db.session.commit()
            flash('All slots deleted!')
            return redirect(url_for('admin.manage_slots', id=id))
        elif request.form.get('action') == 'delete_selected':
            # Delete selected slots
            slot_ids = request.form.getlist('slot_ids')
            for slot_id in slot_ids:
                slot = InterviewSlot.query.get(int(slot_id))
                if slot and slot.district_id == id:
                    bookings = Booking.query.filter_by(slot_id=slot.id).all()
                    for booking in bookings:
                        db.session.delete(booking)
                    db.session.delete(slot)
            db.session.commit()
            flash(f'Deleted {len(slot_ids)} slots!')
            return redirect(url_for('admin.manage_slots', id=id))
    
    slots = InterviewSlot.query.filter_by(district_id=id).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
    return render_template('manage_slots.html', district=district, slots=slots, default_end_date=default_end_date, today=today)


@admin_bp.route('/send_notifications/<int:district_id>')
@admin_required
def send_notifications(district_id):
    district = District.query.get_or_404(district_id)

    # Get current quarter
    today = datetime.now().date()
    current_quarter = ((today.month - 1) // 3) + 1
    current_year = today.year

    # Check if there are any available slots for this district in current quarter
    available_slots = InterviewSlot.query.filter_by(district_id=district_id).filter(
        InterviewSlot.date >= today,
        InterviewSlot.quarter == current_quarter
    ).all()

    if not available_slots:
        flash('No interview slots available for the current quarter. Please create slots before sending notifications.', 'warning')
        return redirect(url_for('admin.district_detail', id=district_id))

    # Load email config
    sender_email = services.apply_email_config()

    if not sender_email:
        flash('Email not configured. Please configure email settings before sending notifications.', 'error')
        return redirect(url_for('admin.district_detail', id=district_id))

    sent_count = 0
    skipped_count = 0

    for companionship in district.companionships:
        for member in companionship.members:
            # Skip if member already has a booking for current quarter
            if member.has_booking_for_quarter(current_quarter, current_year):
                skipped_count += 1
                continue

            link = url_for('public.schedule', token=member.token, _external=True)

            # Send email
            if member.email:
                try:
                    # Use message templates for formatting
                    subject, body = services.format_email_notification(member, link, current_quarter, current_year)
                    msg = Message(
                        subject,
                        sender=sender_email,
                        recipients=[member.email]
                    )
                    msg.html = body
                    msg.body = re.sub('<[^<]+?>', '', body)  # Plain text fallback
                    mail.send(msg)
                    sent_count += 1
                except Exception as e:
                    print(f"Failed to send email to {member.email}: {e}")


    # Commit all notification logs
    db.session.commit()

    message = f'Notifications sent to {sent_count} members.'
    if skipped_count > 0:
        message += f' Skipped {skipped_count} members who already have bookings.'
    flash(message, 'success')
    return redirect(url_for('admin.district_detail', id=district_id))


@admin_bp.route('/send_individual_notification/<int:member_id>', methods=['POST'])
@admin_required
def send_individual_notification(member_id):
    """Send notification to a specific member"""
    member = Member.query.get_or_404(member_id)

    # Get current quarter
    today = datetime.now().date()
    current_quarter = ((today.month - 1) // 3) + 1
    current_year = today.year

    # Load email config
    sender_email = services.apply_email_config()

    if not sender_email:
        return {'success': False, 'error': 'Email not configured'}, 400

    email_sent = False
    errors = []

    link = url_for('public.schedule', token=member.token, _external=True)

    # Send email
    if member.email:
        try:
            # Use message templates for formatting
            subject, body = services.format_email_notification(member, link, current_quarter, current_year)
            msg = Message(subject, sender=sender_email, recipients=[member.email])
            msg.html = body
            msg.body = re.sub('<[^<]+?>', '', body)  # Plain text fallback
            mail.send(msg)
            email_sent = True

            # Log successful email send
            log = NotificationLog(
                member_id=member.id,
                method='email',
                quarter=current_quarter,
                year=current_year,
                success=True
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            error_msg = str(e)
            errors.append(f'Email failed: {error_msg}')

            # Log failed email send
            try:
                log = NotificationLog(
                    member_id=member.id,
                    method='email',
                    quarter=current_quarter,
                    year=current_year,
                    success=False,
                    error_message=error_msg
                )
                db.session.add(log)
                db.session.commit()
            except Exception as log_error:
                print(f"Failed to log notification error: {log_error}")
                db.session.rollback()
    else:
        errors.append('No email address')

    # Build response
    if email_sent:
        return {'success': True, 'message': 'Email sent'}
    else:
        error_message = '; '.join(errors) if errors else 'Failed to send notification'
        return {'success': False, 'error': error_message}, 400


@admin_bp.route('/send_all_notifications')
@admin_required
def send_all_notifications():
    """Send notifications to all members across all districts who don't have bookings"""
    districts = District.query.all()

    # Get current quarter
    today = datetime.now().date()
    current_quarter = ((today.month - 1) // 3) + 1
    current_year = today.year

    # Load email config
    sender_email = services.apply_email_config()

    if not sender_email:
        flash('Email not configured. Please configure email settings before sending notifications.', 'error')
        return redirect(url_for('admin.admin'))

    sent_count = 0
    skipped_count = 0
    failed_count = 0
    error_messages = []  # Track unique error messages
    districts_without_slots = []
    districts_processed = []

    for district in districts:
        # Check if this specific district has available slots for current quarter
        district_slots = InterviewSlot.query.filter(
            InterviewSlot.district_id == district.id,
            InterviewSlot.date >= today,
            InterviewSlot.quarter == current_quarter
        ).count()

        if district_slots == 0:
            # Skip this entire district if no slots available
            districts_without_slots.append(district.name)
            continue

        districts_processed.append(district.name)

        for companionship in district.companionships:
            for member in companionship.members:
                # Skip if member already has a booking for current quarter
                if member.has_booking_for_quarter(current_quarter, current_year):
                    skipped_count += 1
                    continue

                link = url_for('public.schedule', token=member.token, _external=True)

                # Send email
                if member.email:
                    try:
                        # Use message templates for formatting
                        subject, body = services.format_email_notification(member, link, current_quarter, current_year)
                        msg = Message(subject, sender=sender_email, recipients=[member.email])
                        msg.html = body
                        msg.body = re.sub('<[^<]+?>', '', body)  # Plain text fallback
                        mail.send(msg)
                        sent_count += 1
                        print(f"✅ Email sent to {member.name} ({member.email})")

                        # Log successful email send
                        log = NotificationLog(
                            member_id=member.id,
                            method='email',
                            quarter=current_quarter,
                            year=current_year,
                            success=True
                        )
                        db.session.add(log)
                        db.session.commit()  # Commit immediately after each send
                    except Exception as e:
                        failed_count += 1
                        error_msg = str(e)
                        print(f"❌ Failed to send email to {member.name} ({member.email}): {error_msg}")

                        # Track unique error messages
                        if error_msg not in error_messages:
                            error_messages.append(error_msg)

                        # Log failed email send
                        try:
                            log = NotificationLog(
                                member_id=member.id,
                                method='email',
                                quarter=current_quarter,
                                year=current_year,
                                success=False,
                                error_message=error_msg
                            )
                            db.session.add(log)
                            db.session.commit()  # Commit immediately after each log
                        except Exception as log_error:
                            print(f"Failed to log notification error: {log_error}")
                            db.session.rollback()
                else:
                    print(f"⚠️ Skipping {member.name} - no email address")

    # Build detailed message
    message_parts = []

    if sent_count > 0:
        message_parts.append(f'✅ Successfully sent {sent_count} email(s)')

    if failed_count > 0:
        message_parts.append(f'❌ Failed to send {failed_count} email(s)')
        # Show the actual errors in the message
        if error_messages:
            for error_msg in error_messages[:3]:  # Show first 3 unique errors
                # Truncate long error messages
                short_error = error_msg if len(error_msg) < 100 else error_msg[:97] + '...'
                flash(f'Error: {short_error}', 'error')

    if skipped_count > 0:
        message_parts.append(f'⏭️ Skipped {skipped_count} member(s) who already have bookings')

    if districts_processed:
        message_parts.append(f'📊 Processed districts: {", ".join(districts_processed)}')

    if districts_without_slots:
        message_parts.append(f'⚠️ Skipped districts without slots: {", ".join(districts_without_slots)}')

    if not districts_processed and not sent_count:
        flash('No notifications sent. Either all districts have no slots, or all members already have bookings.', 'warning')
        return redirect(url_for('admin.admin'))

    message = ' | '.join(message_parts)
    flash_type = 'success' if sent_count > 0 and failed_count == 0 else 'warning' if sent_count > 0 else 'error'
    flash(message, flash_type)
    return redirect(url_for('admin.admin'))


@admin_bp.route('/add_booking/<int:slot_id>', methods=['POST'])
@admin_required
def add_booking(slot_id):
    slot = InterviewSlot.query.get_or_404(slot_id)
    member_id = request.form.get('member_id')

    # Validate member_id
    if not member_id or member_id == '':
        flash('Please select a member to book.', 'warning')
        return redirect(url_for('admin.admin'))

    interview_type = request.form.get('interview_type', 'in-person')
    member = Member.query.get_or_404(int(member_id))

    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member.id).first()
    if existing:
        flash(f'{member.name} is already booked for this slot.', 'warning')
    else:
        # Check companionship restriction
        if slot.bookings:
            existing_companionship = slot.bookings[0].member.companionship
            if member.companionship != existing_companionship:
                flash('This slot is reserved for another companionship.')
                return redirect(url_for('admin.admin'))

        if len(slot.bookings) < slot.max_slots:
            booking = Booking(slot_id=slot_id, member_id=member_id, interview_type=interview_type)
            db.session.add(booking)
            db.session.commit()
            flash(f'Booked {member.name} for the slot.')
        else:
            flash('Slot is full.')

    return redirect(url_for('admin.admin'))

@admin_bp.route('/remove_booking/<int:booking_id>', methods=['POST'])
@admin_required
def remove_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    slot = booking.slot
    member_name = booking.member.name
    db.session.delete(booking)
    db.session.commit()
    flash(f'Removed {member_name} from the slot.')
    return redirect(url_for('admin.admin'))

@admin_bp.route('/delete_slot/<int:slot_id>', methods=['POST'])
@admin_required
def delete_slot(slot_id):
    slot = InterviewSlot.query.get_or_404(slot_id)
    district_id = slot.district_id
    
    # Delete associated bookings first
    bookings = Booking.query.filter_by(slot_id=slot_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    db.session.delete(slot)
    db.session.commit()
    flash('Interview slot deleted successfully!')
    return redirect(url_for('admin.manage_slots', id=district_id))

@admin_bp.route('/companionship/<int:companionship_id>/add_member', methods=['GET', 'POST'])
@admin_required
def add_member(companionship_id):
    companionship = Companionship.query.get_or_404(companionship_id)

    # Get all members from all districts for reassignment
    all_members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name, Member.name).all()

    if request.method == 'POST':
        # Check if reassigning an existing member or creating a new one
        existing_member_id = request.form.get('existing_member_id')

        if existing_member_id:
            member = Member.query.get(int(existing_member_id))
            if member:
                # Cancel any existing bookings
                bookings = Booking.query.filter_by(member_id=member.id).all()
                for booking in bookings:
                    db.session.delete(booking)
                
                # Reassign to new companionship
                member.companionship_id = companionship_id
                db.session.commit()
                flash(f'Reassigned {member.name} to companionship!')
            else:
                flash('Member not found.')
        else:
            name = request.form.get('name')
            phone = request.form.get('phone')
            email = request.form.get('email')
            
            if name:
                member = Member(companionship_id=companionship_id, name=name, phone=phone, email=email)
                db.session.add(member)
                db.session.commit()
                flash(f'Added {name} to companionship!')
            else:
                flash('Name is required.')

    return render_template('add_member.html', companionship=companionship, all_members=all_members)

@admin_bp.route('/unassign_member/<int:member_id>', methods=['POST'])
@admin_required
def unassign_member(member_id):
    member = Member.query.get_or_404(member_id)
    district_id = member.companionship.district_id if member.companionship else None
    
    # Cancel any existing bookings
    bookings = Booking.query.filter_by(member_id=member_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    # Unassign from companionship
    member.companionship_id = None
    db.session.commit()
    flash(f'Unassigned {member.name} from companionship!')
    
    if district_id:
        return redirect(url_for('admin.district_detail', id=district_id))
    else:
        return redirect(url_for('admin.manage_members'))

@admin_bp.route('/remove_companionship/<int:companionship_id>', methods=['POST'])
@admin_required
def remove_companionship(companionship_id):
    companionship = Companionship.query.get_or_404(companionship_id)
    district_id = companionship.district_id
    name = f"Companionship {companionship.id}"

    # Remove all members and their bookings
    for member in companionship.members:
        bookings = Booking.query.filter_by(member_id=member.id).all()
        for booking in bookings:
            db.session.delete(booking)
        db.session.delete(member)

    db.session.delete(companionship)
    db.session.commit()
    flash(f'{name} removed!')
    return redirect(url_for('admin.district_detail', id=district_id))

@admin_bp.route('/district/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_district(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        district.name = request.form['name']
        district.interviewer_name = request.form['interviewer']
        db.session.commit()
        flash('District updated successfully!')
        return redirect(url_for('admin.manage_districts'))
    return render_template('edit_district.html', district=district)

@admin_bp.route('/district/<int:district_id>/delete', methods=['POST'])
@admin_required
def delete_district(district_id):
    """Delete a district and all associated data"""
    district = District.query.get_or_404(district_id)
    district_name = district.name

    try:
        # Delete all interview slots and their bookings for this district
        slots = InterviewSlot.query.filter_by(district_id=district_id).all()
        for slot in slots:
            bookings = Booking.query.filter_by(slot_id=slot.id).all()
            for booking in bookings:
                db.session.delete(booking)
            db.session.delete(slot)

        # Delete all companionships and their members for this district
        companionships = Companionship.query.filter_by(district_id=district_id).all()
        for companionship in companionships:
            for member in companionship.members:
                # Delete member's bookings (if any left)
                bookings = Booking.query.filter_by(member_id=member.id).all()
                for booking in bookings:
                    db.session.delete(booking)
                # Delete member's notification logs
                logs = NotificationLog.query.filter_by(member_id=member.id).all()
                for log in logs:
                    db.session.delete(log)
                db.session.delete(member)
            db.session.delete(companionship)

        # Finally delete the district
        db.session.delete(district)
        db.session.commit()

        flash(f'District "{district_name}" and all associated data deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting district: {str(e)}', 'error')

    return redirect(url_for('admin.manage_districts'))

@admin_bp.route('/members')
@admin_required
def manage_members():
    """View and manage all members across all districts."""
    members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name.nulls_last(), Companionship.id.nulls_last(), Member.name).all()
    districts = District.query.all()
    return render_template('manage_members.html', members=members, districts=districts)

@admin_bp.route('/member/<int:member_id>/reassign', methods=['POST'])
@admin_required
def reassign_member(member_id):
    """Reassign a member to a different companionship."""
    member = Member.query.get_or_404(member_id)
    new_companionship_id = request.form.get('new_companionship_id', type=int)
    
    if not new_companionship_id:
        flash('Please select a companionship.')
        return redirect(url_for('admin.manage_members'))
    
    new_companionship = Companionship.query.get_or_404(new_companionship_id)
    old_companionship_id = member.companionship_id
    
    # Remove any existing bookings
    bookings = Booking.query.filter_by(member_id=member_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    # Reassign to new companionship
    member.companionship_id = new_companionship_id
    db.session.commit()
    flash(f'Reassigned {member.name} to {new_companionship.district.name} companionship.')
    return redirect(url_for('admin.manage_members'))

@admin_bp.route('/edit_member/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        member.name = request.form.get('name')
        member.phone = request.form.get('phone')
        member.email = request.form.get('email')
        db.session.commit()
        flash('Member updated successfully!')
        return redirect(url_for('admin.manage_members'))
    return render_template('edit_member.html', member=member)


@admin_bp.route('/import_companionships', methods=['GET', 'POST'])
def import_companionships():
    if request.method == 'POST':
        # Process the uploaded districts from session
        uploaded_districts = session.get('uploaded_districts')
        if not uploaded_districts:
            flash('No data to import.')
            return redirect(url_for('admin.import_csv'))
        
        imported_count = 0
        for district_data in uploaded_districts:
            # Create district
            district = District(
                name=district_data['name'],
                interviewer_name=district_data['interviewer']
            )
            db.session.add(district)
            db.session.flush()  # Get district ID
            
            # Create companionships and members
            for comp_data in district_data['companionships']:
                companionship = Companionship(district_id=district.id)
                db.session.add(companionship)
                db.session.flush()
                
                for member_data in comp_data['members']:
                    member = Member(
                        companionship_id=companionship.id,
                        name=member_data['name'],
                        phone=member_data['phone'],
                        email=member_data['email']
                    )
                    db.session.add(member)
            
            imported_count += 1
        
        db.session.commit()
        session.pop('uploaded_districts', None)
        flash(f'Successfully imported {imported_count} districts!')
        return redirect(url_for('admin.admin'))
    
    return render_template('import_companionships.html')


@admin_bp.route('/import_csv_confirm', methods=['GET', 'POST'])
@admin_required
def import_csv_confirm():
    """Confirm and import data from CSV upload"""
    scraped_districts = session.get('uploaded_districts')
    if not scraped_districts:
        flash('No uploaded data found.')
        return redirect(url_for('admin.import_csv'))

    if request.method == 'POST' and 'confirm_import' in request.form:
        # Import the data
        try:
            # Clear existing data if requested
            if 'clear_existing' in request.form:
                # Delete in correct order due to foreign keys
                Booking.query.delete()
                InterviewSlot.query.delete()
                Member.query.delete()
                Companionship.query.delete()
                District.query.delete()
                db.session.commit()
                flash('Cleared all existing data for fresh import.')

            for district_data in scraped_districts:
                district_name = district_data['name']
                interviewer_name = district_data['interviewer']

                # Find or create district
                district = District.query.filter_by(name=district_name).first()
                if not district:
                    district = District(name=district_name, interviewer_name=interviewer_name)
                    db.session.add(district)
                    db.session.commit()

                for comp_data in district_data['companionships']:
                    # Create companionship
                    companionship = Companionship(district_id=district.id)
                    db.session.add(companionship)
                    db.session.commit()

                    for member_data in comp_data['members']:
                        # Try to find existing member by email globally
                        existing_member = Member.query.filter_by(email=member_data['email']).first() if member_data.get('email') else None

                        if existing_member:
                            # Update phone if different
                            if existing_member.phone != member_data.get('phone') and member_data.get('phone'):
                                existing_member.phone = member_data['phone']
                            # Update name if different
                            if existing_member.name != member_data['name']:
                                existing_member.name = member_data['name']
                            # Reassign to new companionship
                            existing_member.companionship_id = companionship.id
                            member = existing_member
                        else:
                            # Create new member
                            member = Member(
                                name=member_data['name'],
                                phone=member_data.get('phone'),
                                email=member_data.get('email'),
                                companionship_id=companionship.id
                            )
                            db.session.add(member)

                        # Ensure member is in the companionship
                        if member not in companionship.members:
                            companionship.members.append(member)

                    db.session.commit()

            session.pop('uploaded_districts', None)
            flash('Data imported successfully!')
            return redirect(url_for('admin.admin'))

        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}')
            return redirect(url_for('admin.import_csv_confirm'))

    # Display confirmation
    return render_template('import_confirm.html', scraped_districts=scraped_districts, confirm_endpoint='admin.import_csv_confirm')


# System Settings Routes
@admin_bp.route('/settings', methods=['GET'])
@admin_required
def system_settings():
    """Display system settings page"""
    config = SystemConfig.query.first()
    if not config:
        config = SystemConfig()
        # Create a decrypted view for template
        decrypted = {
            'mail_server': 'localhost',
            'mail_port': 1025,
            'mail_use_tls': False,
            'mail_username': '',
            'mail_password': '',
            'mail_from_email': '',
            'mail_from_name': 'Ministering Interview App',
            'reminder_enabled': True,
            'reminder_day_of_week': 0,
            'reminder_hour': 9,
            'reminder_minute': 0,
        }
    else:
        # Get decrypted fields as dictionary
        decrypted = config.decrypt_fields()

    # Create a simple object to hold decrypted values for template
    class DecryptedConfig:
        pass

    config_view = DecryptedConfig()
    for key, value in decrypted.items():
        setattr(config_view, key, value)

    # Get message templates
    msg_config = MessageTemplates.get_or_create()

    return render_template('system_settings.html', config=config_view, msg_config=msg_config)


@admin_bp.route('/settings/save', methods=['POST'])
@admin_required
def save_system_settings():
    """Save system settings"""
    config_type = request.form.get('config_type')
    config = SystemConfig.query.first()
    if not config:
        config = SystemConfig()

    try:
        if config_type == 'email':
            config.mail_server = request.form.get('mail_server', 'localhost')
            config.mail_port = int(request.form.get('mail_port', 1025))
            config.mail_use_tls = request.form.get('mail_use_tls') == 'on'
            config.mail_username = request.form.get('mail_username', '')
            config.mail_from_email = request.form.get('mail_from_email', '')
            config.mail_from_name = request.form.get('mail_from_name', 'Ministering Interview App')
            mail_password = request.form.get('mail_password', '')
            if mail_password:
                config.mail_password = mail_password

        elif config_type == 'scheduler':
            config.reminder_enabled = request.form.get('reminder_enabled') == 'on'
            config.reminder_day_of_week = int(request.form.get('reminder_day_of_week', 0))
            config.reminder_hour = int(request.form.get('reminder_hour', 9))
            config.reminder_minute = int(request.form.get('reminder_minute', 0))
            services.reschedule_reminder_job(config, current_app.scheduler)

        config.encrypt_fields()
        db.session.add(config)
        db.session.commit()

        # Immediately reload email config into Flask app after saving
        if config_type == 'email':
            services.apply_email_config()

        flash(f'{config_type.capitalize()} settings saved successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving settings: {str(e)}', 'error')

    return redirect(url_for('admin.system_settings') + f'#{config_type}')


@admin_bp.route('/settings/test-email')
@admin_required
def send_test_email():
    """Send a test email"""
    config = SystemConfig.query.first()
    if not config:
        flash('System settings not configured yet.', 'error')
        return redirect(url_for('admin.system_settings'))

    try:
        decrypted = config.decrypt_fields()
        current_app.config['MAIL_SERVER'] = decrypted['mail_server']
        current_app.config['MAIL_PORT'] = decrypted['mail_port']
        current_app.config['MAIL_USE_TLS'] = decrypted['mail_use_tls']
        current_app.config['MAIL_USERNAME'] = decrypted['mail_username']
        current_app.config['MAIL_PASSWORD'] = decrypted['mail_password']

        msg = Message('Test Email from Ministering Interview App',
                     sender=decrypted['mail_from_email'],
                     recipients=[current_user.email])
        msg.body = 'This is a test email to verify your email settings are working correctly.'
        mail.send(msg)
        flash(f'Test email sent successfully to {current_user.email}!', 'success')
    except Exception as e:
        flash(f'Failed to send test email: {str(e)}', 'error')

    return redirect(url_for('admin.system_settings') + '#email')


@admin_bp.route('/settings/save-messages', methods=['POST'])
@admin_required
def save_message_settings():
    """Save message customization settings"""
    try:
        msg_config = MessageTemplates.get_or_create()

        msg_config.organization_name = request.form.get('organization_name', '').strip() or None
        msg_config.greeting_style = request.form.get('greeting_style', 'Dear')
        msg_config.custom_instructions = request.form.get('custom_instructions', '').strip() or None
        msg_config.signature_name = request.form.get('signature_name', '').strip() or None
        msg_config.signature_title = request.form.get('signature_title', '').strip() or None

        db.session.commit()
        flash('Message settings saved successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving message settings: {str(e)}', 'error')

    return redirect(url_for('admin.system_settings') + '#messages')

