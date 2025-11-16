

# --- Refactored app.py ---
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_user import UserManager, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import defaultdict
from sqlalchemy import func, extract
import secrets
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
import uuid
import threading
from cryptography.fernet import Fernet
import base64
import hashlib
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
from flask_migrate import Migrate

# Load environment variables
load_dotenv()

# Global thread-safe storage for progress data
progress_store = {}
progress_lock = threading.Lock()

# Global SMS client storage
sms_config = {
    'provider': None,
    'client': None,
    'from_number': None
}

# Import config, models, utils, services
from config import config as app_config
from models import db, User, UserInvitation, SystemConfig, IncomingSMS, District, Companionship, Member, InterviewSlot, Booking, NotificationLog
from utils import EncryptionHelper, admin_required
import services

# Create Flask app
app = Flask(__name__)
app.config.from_object(app_config['development'])

# Ensure instance directory exists for SQLite
os.makedirs('instance', exist_ok=True)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
user_manager = UserManager(app, db, User)

# Initialize scheduler (disabled by default)
scheduler = BackgroundScheduler()
atexit.register(lambda: scheduler.shutdown())

# Context processor to make 'now' available in all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}


# Register Blueprints
from routes_admin import admin_bp
app.register_blueprint(admin_bp)

# ...existing non-admin route code...

# Initialize database and load config
with app.app_context():
    db.create_all()
    services.apply_email_config()
    services.apply_sms_config()
    config_obj = SystemConfig.query.first()
    if config_obj and config_obj.reminder_enabled:
        services.reschedule_reminder_job(config_obj)
    else:
        print("Reminders are disabled by default. Scheduler not started.")

# Custom login redirect handler
@app.route('/login_redirect')
def login_redirect():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin'))
        else:
            # For non-admin users, redirect to home or show access denied
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('index'))
    else:
        return redirect(url_for('user.login'))

# Flask-User provides login/logout routes automatically

@app.route('/setup_admin', methods=['GET', 'POST'])
def setup_admin():
    # Only allow if no admin exists
    if User.query.filter_by(role='admin').first():
        return redirect(url_for('user.login'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate required fields
        if not email or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return redirect(url_for('setup_admin'))

        # Check password match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
            return redirect(url_for('setup_admin'))

        # Check minimum password length
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('setup_admin'))

        # Check password length (Werkzeug limit is 72 bytes)
        if len(password.encode('utf-8')) > 72:
            flash('Password must be 72 bytes or less. Please choose a shorter password.', 'error')
            return redirect(url_for('setup_admin'))

        # Let Flask-User handle password hashing
        user = User(email=email, password=user_manager.hash_password(password), role='admin', active=True, email_confirmed_at=datetime.now())
        db.session.add(user)
        db.session.commit()
        flash('Admin account created successfully! Please log in.', 'success')
        return redirect(url_for('user.login'))
    return render_template('setup_admin.html')

# Routes
@app.route('/')
def index():
    # If already logged in, redirect to appropriate dashboard
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin'))
        else:  # interviewer
            return redirect(url_for('interviewer_dashboard'))
    # Check if any admin exists
    admin_exists = User.query.filter_by(role='admin').first()
    # If no admin, show setup admin form
    if not admin_exists:
        return redirect(url_for('setup_admin'))
    # Otherwise, redirect to login
    return redirect(url_for('user.login'))

@app.route('/dashboard')
def interviewer_dashboard():
    """Dashboard for interviewers - shows their interview calendar"""
    # Require login
    if not current_user.is_authenticated:
        return redirect(url_for('user.login', next=request.path))
    
    # Interviewers can access their calendar
    # Admin can also access this if they want
    
    # Get all districts
    today = datetime.now().date()
    current_month = today.month
    current_quarter = ((current_month - 1) // 3) + 1
    
    districts = District.query.all()
    district_slots = {}
    
    # Get slots for the current and future quarters only
    for district in districts:
        slots = InterviewSlot.query.filter_by(district_id=district.id)\
            .filter(InterviewSlot.date >= today)\
            .order_by(InterviewSlot.date, InterviewSlot.start_time).all()
        district_slots[district.id] = slots
    
    return render_template('interviewer_dashboard.html', districts=districts, district_slots=district_slots)

@app.route('/admin')
def admin():
    # Check if admin exists first
    admin_exists = User.query.filter_by(role='admin').first()
    if not admin_exists:
        return redirect(url_for('setup_admin'))
    
    # Require login for admin access (Flask-User handles this)
    if not current_user.is_authenticated:
        return redirect(url_for('user.login', next=request.path))
    
    # Check if user has admin role
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('index'))
    
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

@app.route('/admin/delete_old_slots', methods=['POST'])
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
@app.route('/admin/users')
@admin_required
def manage_users():
    users = User.query.all()
    invitations = UserInvitation.query.filter_by(is_used=False).all()
    return render_template('manage_users.html', users=users, invitations=invitations)

    # Notification Report Route
    @app.route('/admin/notification_report')
    @admin_required
    def notification_report():
        logs = NotificationLog.query.order_by(NotificationLog.sent_at.desc()).all()
        return render_template('notification_report.html', logs=logs)
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
                    report_data.append({
                        'member': member,
                        'district': district,
                        'companionship': companionship,
                        'email_sent': email_sent,
                        'sms_sent': sms_sent,
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

@app.route('/admin/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'interviewer')
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('manage_users'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'error')
            return redirect(url_for('manage_users'))
        
        # Check if invitation exists for this email
        if UserInvitation.query.filter_by(email=email, is_used=False).first():
            flash('An invitation already exists for this email.', 'error')
            return redirect(url_for('manage_users'))
        
        try:
            # Check password length (Werkzeug limit is 72 bytes)
            if len(password.encode('utf-8')) > 72:
                flash('Password must be 72 bytes or less.', 'error')
                return redirect(url_for('manage_users'))
            
            user = User(
                email=email,
                password=user_manager.hash_password(password),
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
        
        return redirect(url_for('manage_users'))
    
    return render_template('create_user.html')

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent editing yourself or the last admin
    if user.id == current_user.id:
        flash('Cannot edit your own account here. Use "Change Password" in your profile.', 'warning')
        return redirect(url_for('manage_users'))
    
    if request.method == 'POST':
        role = request.form.get('role')
        active = request.form.get('active') == 'on'
        
        # Prevent removing the last admin
        if user.role == 'admin' and role != 'admin':
            admin_count = User.query.filter_by(role='admin', active=True).count()
            if admin_count <= 1:
                flash('Cannot change role - this is the last active admin.', 'error')
                return redirect(url_for('manage_users'))
        
        user.role = role
        user.active = active
        db.session.commit()
        flash(f'User {user.email} updated successfully.', 'success')
        return redirect(url_for('manage_users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('manage_users'))
    
    # Prevent deleting the last admin
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot delete the last admin account.', 'error')
            return redirect(url_for('manage_users'))
    
    email = user.email
    db.session.delete(user)
    db.session.commit()
    flash(f'User {email} deleted successfully.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/invite', methods=['GET', 'POST'])
@admin_required
def invite_user():
    if request.method == 'POST':
        email = request.form.get('email')
        role = request.form.get('role', 'interviewer')
        
        if not email:
            flash('Email is required.', 'error')
            return redirect(url_for('invite_user'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'error')
            return redirect(url_for('invite_user'))
        
        # Check if invitation already exists and is still valid
        existing_invite = UserInvitation.query.filter_by(email=email, is_used=False).first()
        if existing_invite:
            if existing_invite.expires_at > datetime.now():
                flash('An active invitation already exists for this email.', 'warning')
                return redirect(url_for('invite_user'))
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
            invite_link = url_for('accept_invitation', token=token, _external=True)
            
            # Load email config
            sender_email = apply_email_config()
            if not sender_email:
                flash('Email configuration not set up. Please configure email settings first.', 'error')
                db.session.delete(invitation)
                db.session.commit()
                return redirect(url_for('invite_user'))
            
            print(f"Using MAIL_SERVER: {app.config.get('MAIL_SERVER')}, MAIL_PORT: {app.config.get('MAIL_PORT')}, MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
            
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
            return redirect(url_for('manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error sending invitation: {str(e)}', 'error')
            return redirect(url_for('invite_user'))
    
    return render_template('invite_user.html')

@app.route('/admin/invitations/<int:invitation_id>/cancel', methods=['POST'])
@admin_required
def cancel_invitation(invitation_id):
    invitation = UserInvitation.query.get_or_404(invitation_id)
    
    if invitation.is_used:
        flash('Cannot cancel an accepted invitation.', 'error')
        return redirect(url_for('manage_users'))
    
    email = invitation.email
    db.session.delete(invitation)
    db.session.commit()
    flash(f'Invitation cancelled for {email}.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/user/accept-invite/<token>', methods=['GET', 'POST'])
def accept_invitation(token):
    invitation = UserInvitation.query.filter_by(token=token, is_used=False).first_or_404()
    
    # Check if invitation has expired
    if invitation.expires_at < datetime.now():
        flash('This invitation has expired. Please contact an administrator for a new one.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if not password:
            flash('Password is required.', 'error')
            return redirect(url_for('accept_invitation', token=token))
        
        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('accept_invitation', token=token))
        
        try:
            # Check password length
            if len(password.encode('utf-8')) > 72:
                flash('Password must be 72 bytes or less.', 'error')
                return redirect(url_for('accept_invitation', token=token))
            
            # Create user account
            user = User(
                email=invitation.email,
                password=user_manager.hash_password(password),
                role=invitation.role,
                active=True,
                email_confirmed_at=datetime.now()
            )
            db.session.add(user)
            db.session.flush()  # Get the user ID
            
            # Mark invitation as used
            invitation.is_used = True
            invitation.accepted_at = datetime.now()
            invitation.accepted_by_user_id = user.id
            
            db.session.commit()
            
            flash('Account created successfully! Please log in with your credentials.', 'success')
            return redirect(url_for('user.login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'error')
            return redirect(url_for('accept_invitation', token=token))
    
    return render_template('accept_invitation.html', email=invitation.email, expires_at=invitation.expires_at)

@app.route('/admin/districts')
@admin_required
def manage_districts():
    districts = District.query.all()
    return render_template('manage_districts.html', districts=districts)

@app.route('/admin/scrape', methods=['GET', 'POST'])
@admin_required
def scrape_data():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('scrape_data'))
        
        # Run scraping in a thread to avoid blocking
        progress_id = str(uuid.uuid4())
        with progress_lock:
            progress_store[progress_id] = {
                'status': 'running',
                'message': 'Initializing scraper...',
                'step': 0,
                'total_steps': 10,
                'districts_found': 0,
                'companionships_found': 0,
                'members_found': 0,
                'errors': []
            }
        
        def run_scrape():
            try:
                # Import the scraper module
                from app_scraper import scrape_ministering_data

                def progress_callback(message, counts=None):
                    # Update progress store with the message
                    with progress_lock:
                        progress_store[progress_id]['message'] = message

                        # Update counts if provided
                        if counts and isinstance(counts, dict):
                            if 'districts' in counts:
                                progress_store[progress_id]['districts_found'] = counts['districts']
                            if 'companionships' in counts:
                                progress_store[progress_id]['companionships_found'] = counts['companionships']
                            if 'members' in counts:
                                progress_store[progress_id]['members_found'] = counts['members']

                        # Try to extract step information from message
                        if 'Step' in message:
                            try:
                                step_num = int(message.split('Step')[1].split(':')[0].strip())
                                progress_store[progress_id]['step'] = step_num
                            except:
                                pass

                        # Check if this is an error message and add to errors list
                        if message.startswith('❌') or message.startswith('[ERROR]') or 'Error' in message or 'Failed' in message:
                            progress_store[progress_id]['errors'].append(message)
                            progress_store[progress_id]['status'] = 'error'
                        else:
                            progress_store[progress_id]['status'] = 'running'

                # Run the scraper
                results = scrape_ministering_data(username, password, progress_callback)

                if results:
                    with progress_lock:
                        progress_store[progress_id]['status'] = 'completed'
                        progress_store[progress_id]['message'] = 'Scraping completed'
                        progress_store[progress_id]['step'] = 10
                        progress_store[progress_id]['districts_found'] = len(set(row['district'] for row in results))
                        progress_store[progress_id]['companionships_found'] = len(set(row['companionship_id'] for row in results))
                        progress_store[progress_id]['members_found'] = len(results)
                        progress_store[progress_id]['scraped_districts'] = group_results_by_district(results)
                        progress_store[progress_id]['raw_results'] = results  # Store raw results for CSV download
                else:
                    with progress_lock:
                        progress_store[progress_id]['status'] = 'error'
                        # Check if we have any error messages from the progress callback
                        if progress_store[progress_id]['errors']:
                            progress_store[progress_id]['message'] = 'Scraping failed - check errors below'
                        else:
                            progress_store[progress_id]['message'] = 'Scraping failed - no data returned'
                            progress_store[progress_id]['errors'].append('Scraper returned no data. Check credentials and network connection.')

            except Exception as e:
                with progress_lock:
                    progress_store[progress_id]['status'] = 'error'
                    progress_store[progress_id]['message'] = str(e)
                    progress_store[progress_id]['errors'].append(str(e))
        
        thread = threading.Thread(target=run_scrape)
        thread.start()
        
        return redirect(url_for('scrape_progress', progress_id=progress_id))
    
    return render_template('scrape.html')

@app.route('/admin/scrape_progress/<progress_id>')
@admin_required
def scrape_progress(progress_id):
    return render_template('scrape_progress.html', progress_id=progress_id)

@app.route('/admin/download_csv/<progress_id>')
@admin_required
def download_csv(progress_id):
    with progress_lock:
        progress_data = progress_store.get(progress_id)
    
    if not progress_data or progress_data['status'] != 'completed':
        flash('No completed scrape data found.')
        return redirect(url_for('scrape_data'))
    
    raw_results = progress_data.get('raw_results')
    if not raw_results:
        flash('No raw data available for download.')
        return redirect(url_for('scrape_data'))
    
    # Create CSV in memory
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['district', 'interviewer', 'name', 'phone', 'email', 'companionship_id'])
    writer.writeheader()
    for row in raw_results:
        writer.writerow(row)
    
    # Create response
    output.seek(0)
    response = send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='ministering_brothers.csv'
    )
    
    return response

@app.route('/admin/import_csv', methods=['GET', 'POST'])
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
            return redirect(url_for('import_csv_confirm'))
        
        except Exception as e:
            flash(f'Error processing CSV: {str(e)}')
            return redirect(request.url)
    
    return render_template('import_csv.html')

@app.route('/admin/district/new', methods=['GET', 'POST'])
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

@app.route('/admin/district/<int:id>')
@admin_required
def district_detail(id):
    district = District.query.get_or_404(id)
    return render_template('district_detail.html', district=district)

@app.route('/admin/district/<int:id>/companionship/new', methods=['GET', 'POST'])
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
        return redirect(url_for('district_detail', id=id))
    
    # Get existing members from all districts for reassignment
    existing_members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name, Member.name).all()
    return render_template('new_companionship.html', district=district, existing_members=existing_members)

@app.route('/admin/district/<int:id>/slots', methods=['GET', 'POST'])
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
                return redirect(url_for('manage_slots', id=id))
            
            if start_date >= end_date:
                flash('Start date must be before end date.')
                return redirect(url_for('manage_slots', id=id))
            
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
                                max_slots=1  # Assuming 1 slot per time
                            )
                            db.session.add(slot)
                            slots_created += 1
                current_date += timedelta(days=1)
            
            db.session.commit()
            flash(f'Generated {slots_created} recurring slots!')
            if skipped_slots:
                combined_msg = "The following slots were skipped due to conflicts:<br>" + "<br>".join(skipped_slots)
                flash(combined_msg, 'warning')
            return redirect(url_for('manage_slots', id=id))
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
            return redirect(url_for('manage_slots', id=id))
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
            return redirect(url_for('manage_slots', id=id))
    
    slots = InterviewSlot.query.filter_by(district_id=id).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
    return render_template('manage_slots.html', district=district, slots=slots, default_end_date=default_end_date, today=today)

@app.route('/schedule/<token>')
def schedule(token):
    member = Member.query.filter_by(token=token).first_or_404()
    district = member.companionship.district
    current_quarter = ((datetime.now().month - 1) // 3) + 1
    available_slots = InterviewSlot.query.filter_by(district_id=district.id).filter(
        InterviewSlot.date >= datetime.now().date(),
        InterviewSlot.quarter == current_quarter
    ).outerjoin(Booking).group_by(InterviewSlot.id).having(
        func.count(Booking.id) < InterviewSlot.max_slots
    ).order_by(InterviewSlot.date, InterviewSlot.start_time).all()

    # Find member's current booking for this quarter
    my_booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == current_quarter,
        InterviewSlot.date >= datetime.now().date()
    ).first()

    # Find if any companion (companionship member) has already booked a slot
    companion_booking = None
    if member.companionship:
        for companionship_member in member.companionship.members:
            if companionship_member.id != member.id:  # Check other companionship members
                booking = Booking.query.join(InterviewSlot).filter(
                    Booking.member_id == companionship_member.id,
                    InterviewSlot.quarter == current_quarter,
                    InterviewSlot.date >= datetime.now().date()
                ).first()
                if booking:
                    companion_booking = {
                        'slot': booking.slot,
                        'companion_name': companionship_member.name
                    }
                    break  # Only show first companion's booking

    return render_template('schedule.html', member=member, slots=available_slots, companion_booking=companion_booking, my_booking=my_booking)

@app.route('/book/<int:slot_id>/<token>', methods=['POST'])
def book_slot(slot_id, token):
    member = Member.query.filter_by(token=token).first_or_404()
    slot = InterviewSlot.query.get_or_404(slot_id)
    interview_type = request.form.get('interview_type', 'in-person')

    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member.id).first()
    if existing:
        flash('You are already booked for this slot.')
        return redirect(url_for('schedule', token=token))

    # Check companionship restriction
    if slot.bookings:
        existing_companionship = slot.bookings[0].member.companionship
        if member.companionship != existing_companionship:
            flash('This slot is reserved for another companionship.')
            return redirect(url_for('schedule', token=token))

    if len(slot.bookings) < slot.max_slots:
        booking = Booking(slot_id=slot_id, member_id=member.id, interview_type=interview_type)
        db.session.add(booking)
        db.session.commit()
        flash('Slot booked successfully!', 'success')
    else:
        flash('Slot is full.', 'error')

    return redirect(url_for('schedule', token=token))

@app.route('/unbook/<token>', methods=['POST'])
def unbook_slot(token):
    member = Member.query.filter_by(token=token).first_or_404()
    current_quarter = ((datetime.now().month - 1) // 3) + 1

    # Find member's current booking for this quarter
    booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == current_quarter,
        InterviewSlot.date >= datetime.now().date()
    ).first()

    if booking:
        db.session.delete(booking)
        db.session.commit()
        flash('Your booking has been cancelled. You can now book a different time slot.', 'success')
    else:
        flash('No booking found to cancel.', 'error')

    return redirect(url_for('schedule', token=token))

@app.route('/admin/send_notifications/<int:district_id>')
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
        return redirect(url_for('district_detail', id=district_id))

    # Load email and SMS config
    sender_email = apply_email_config()
    sms_configured = apply_sms_config()

    if not sender_email:
        flash('Email not configured. Please configure email settings before sending notifications.', 'error')
        return redirect(url_for('district_detail', id=district_id))

    sent_count = 0
    skipped_count = 0

    for companionship in district.companionships:
        for member in companionship.members:
            # Skip if member already has a booking for current quarter
            if member.has_booking_for_quarter(current_quarter, current_year):
                skipped_count += 1
                continue

            link = url_for('schedule', token=member.token, _external=True)

            # Send email
            if member.email:
                try:
                    msg = Message(
                        f'Interview Scheduling Available for Q{current_quarter} {current_year}',
                        sender=sender_email,
                        recipients=[member.email]
                    )
                    msg.body = f'''Dear {member.name},

Interview slots are now available for the current quarter (Q{current_quarter} {current_year}).

Please visit the following link to schedule your interview:

{link}

If you have any questions, please contact your district interviewer.

Thank you,
Ministering Interview App
'''
                    msg.html = f'''<p>Dear {member.name},</p>
<p>Interview slots are now available for the current quarter (Q{current_quarter} {current_year}).</p>
<p><a href="{link}">Click here to schedule your interview</a></p>
<p>If you have any questions, please contact your district interviewer.</p>
<p>Thank you,<br>Ministering Interview App</p>
'''
                    mail.send(msg)
                    sent_count += 1
                except Exception as e:
                    print(f"Failed to send email to {member.email}: {e}")

            # Send SMS (only if enabled and configured)
            if sms_configured and member.can_receive_sms():
                try:
                    # Assuming SMS sending function is implemented
                    # send_sms(member.phone, f'Interview slots available. Schedule at: {link}')
                    pass
                except Exception as e:
                    print(f"Failed to send SMS to {member.phone}: {e}")

    # Commit all notification logs
    db.session.commit()

    message = f'Notifications sent to {sent_count} members.'
    if skipped_count > 0:
        message += f' Skipped {skipped_count} members who already have bookings.'
    flash(message, 'success')
    return redirect(url_for('district_detail', id=district_id))

@app.route('/admin/add_booking/<int:slot_id>', methods=['POST'])
@admin_required
def add_booking(slot_id):
    slot = InterviewSlot.query.get_or_404(slot_id)
    member_id = request.form['member_id']
    interview_type = request.form.get('interview_type', 'in-person')
    member = Member.query.get_or_404(member_id)

    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member_id).first()
    if existing:
        flash(f'{member.name} is already booked for this slot.')
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

@app.route('/admin/remove_booking/<int:booking_id>', methods=['POST'])
@admin_required
def remove_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    slot = booking.slot
    member_name = booking.member.name
    db.session.delete(booking)
    db.session.commit()
    flash(f'Removed {member_name} from the slot.')
    return redirect(url_for('admin.admin'))

@app.route('/admin/delete_slot/<int:slot_id>', methods=['POST'])
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
    return redirect(url_for('manage_slots', id=district_id))

@app.route('/admin/companionship/<int:companionship_id>/add_member', methods=['GET', 'POST'])
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

@app.route('/admin/unassign_member/<int:member_id>', methods=['POST'])
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
        return redirect(url_for('district_detail', id=district_id))
    else:
        return redirect(url_for('manage_members'))

@app.route('/admin/remove_companionship/<int:companionship_id>', methods=['POST'])
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
    return redirect(url_for('district_detail', id=district_id))

@app.route('/admin/district/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_district(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        district.name = request.form['name']
        district.interviewer_name = request.form['interviewer']
        db.session.commit()
        flash('District updated successfully!')
        return redirect(url_for('manage_districts'))
    return render_template('edit_district.html', district=district)

@app.route('/admin/members')
@admin_required
def manage_members():
    """View and manage all members across all districts."""
    members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name.nulls_last(), Companionship.id.nulls_last(), Member.name).all()
    districts = District.query.all()
    return render_template('manage_members.html', members=members, districts=districts)

@app.route('/admin/member/<int:member_id>/reassign', methods=['POST'])
@admin_required
def reassign_member(member_id):
    """Reassign a member to a different companionship."""
    member = Member.query.get_or_404(member_id)
    new_companionship_id = request.form.get('new_companionship_id', type=int)
    
    if not new_companionship_id:
        flash('Please select a companionship.')
        return redirect(url_for('manage_members'))
    
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
    return redirect(url_for('manage_members'))

@app.route('/admin/edit_member/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        member.name = request.form.get('name')
        member.phone = request.form.get('phone')
        member.email = request.form.get('email')
        member.no_sms = request.form.get('no_sms') == 'on'
        db.session.commit()
        flash('Member updated successfully!')
        return redirect(url_for('manage_members'))
    return render_template('edit_member.html', member=member)

def group_results_by_district(results):
    """Group scraping results by district for display."""
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
    
    return scraped_districts

@app.route('/admin/import_companionships', methods=['GET', 'POST'])
def import_companionships():
    if request.method == 'POST':
        # Process the uploaded districts from session
        uploaded_districts = session.get('uploaded_districts')
        if not uploaded_districts:
            flash('No data to import.')
            return redirect(url_for('import_csv'))
        
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

@app.route('/admin/import_progress/<progress_id>')
def import_progress(progress_id):
    # This would be for real-time import progress, but for now just redirect
    return redirect(url_for('admin.admin'))

@app.route('/admin/import_confirm', methods=['GET', 'POST'])
def import_csv_confirm():
    uploaded_districts = session.get('uploaded_districts')
    if not uploaded_districts:
        flash('No data to confirm.')
        return redirect(url_for('import_csv'))
    
    if request.method == 'POST':
        return redirect(url_for('import_companionships'))
    
    return render_template('import_confirm.html', districts=uploaded_districts)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8181)
    """Incoming SMS messages (for 2-way messaging in Phase 2)"""
    __tablename__ = 'incoming_sms'

    id = db.Column(db.Integer, primary_key=True)

    # Message details
    from_number = db.Column(db.String(20), nullable=False, index=True)
    to_number = db.Column(db.String(20))  # Our SMS number (for 2-way)
    message_body = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(20))  # 'twilio', 'aws', 'signalwire'

    # Timestamps
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    # Member association (auto-match by phone)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=True, index=True)
    member = db.relationship('Member', backref='received_sms')

    # Handling status
    status = db.Column(db.String(20), default='new')  # 'new', 'read', 'responded', 'archived', 'auto_handled'
    is_stop_request = db.Column(db.Boolean, default=False)

    # Response tracking
    responded_at = db.Column(db.DateTime, nullable=True)
    response_text = db.Column(db.Text, nullable=True)
    handled_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    handled_by = db.relationship('User', foreign_keys=[handled_by_user_id])

    # Raw data for debugging
    raw_webhook_data = db.Column(db.JSON, nullable=True)

    # Notes
    admin_notes = db.Column(db.Text, nullable=True)

# Flask-User setup (after User model is defined)
# Initialize UserManager - this must happen at module level for gunicorn compatibility
user_manager = UserManager(app, db, User)

# Admin access decorator
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('user.login', next=request.path))
        if current_user.role != 'admin':
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    interviewer_name = db.Column(db.String(100), nullable=False)
    companionships = db.relationship('Companionship', backref='district', lazy=True)

class Companionship(db.Model):
    __tablename__ = 'companionship'
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    members = db.relationship('Member', backref='companionship', lazy=True)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    companionship_id = db.Column(db.Integer, db.ForeignKey('companionship.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False, default=lambda: secrets.token_hex(16))
    no_sms = db.Column(db.Boolean, nullable=False, default=False)  # Disable SMS for this member

    def has_booking_for_quarter(self, quarter, year=None):
        """Check if member has a booking for the specified quarter"""
        if year is None:
            year = datetime.now().year
        bookings = Booking.query.filter_by(member_id=self.id).join(InterviewSlot).filter(
            InterviewSlot.quarter == quarter,
            db.extract('year', InterviewSlot.date) == year
        ).first()
        return bookings is not None

    def can_receive_sms(self):
        """Check if member can receive SMS (has phone and SMS not disabled)"""
        return bool(self.phone and not self.no_sms)

class InterviewSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    max_slots = db.Column(db.Integer, nullable=False)
    quarter = db.Column(db.Integer, nullable=False, default=0)  # Auto-calculated
    bookings = db.relationship('Booking', backref='slot', lazy=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.date:
            self.quarter = ((self.date.month - 1) // 3) + 1

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('interview_slot.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    interview_type = db.Column(db.String(20), nullable=False, default='in-person')
    member = db.relationship('Member', backref='bookings')

class NotificationLog(db.Model):
    """Track when notifications are sent to members"""
    __tablename__ = 'notification_log'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    member = db.relationship('Member', backref='notifications')
    method = db.Column(db.String(10), nullable=False)  # 'email' or 'sms'
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    quarter = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    success = db.Column(db.Boolean, nullable=False, default=True)
    error_message = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<NotificationLog {self.member.name if self.member else "Unknown"} - {self.method} - Q{self.quarter} {self.year}>'

# Initialize database and load config (runs for both direct execution and gunicorn)
# Ensure the instance directory exists for SQLite
os.makedirs('instance', exist_ok=True)

with app.app_context():
    db.create_all()
    # Load email/SMS config from database if it exists
    apply_email_config()
    apply_sms_config()

# Custom login redirect handler
@app.route('/login_redirect')
def login_redirect():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin'))
        else:
            # For non-admin users, redirect to home or show access denied
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('index'))
    else:
        return redirect(url_for('user.login'))

# Flask-User provides login/logout routes automatically

@app.route('/setup_admin', methods=['GET', 'POST'])
def setup_admin():
    # Only allow if no admin exists
    if User.query.filter_by(role='admin').first():
        return redirect(url_for('user.login'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate required fields
        if not email or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return redirect(url_for('setup_admin'))

        # Check password match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
            return redirect(url_for('setup_admin'))

        # Check minimum password length
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('setup_admin'))

        # Check password length (Werkzeug limit is 72 bytes)
        if len(password.encode('utf-8')) > 72:
            flash('Password must be 72 bytes or less. Please choose a shorter password.', 'error')
            return redirect(url_for('setup_admin'))

        # Let Flask-User handle password hashing
        user = User(email=email, password=user_manager.hash_password(password), role='admin', active=True, email_confirmed_at=datetime.now())
        db.session.add(user)
        db.session.commit()
        flash('Admin account created successfully! Please log in.', 'success')
        return redirect(url_for('user.login'))
    return render_template('setup_admin.html')

# Routes
@app.route('/')
def index():
    # If already logged in, redirect to appropriate dashboard
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin'))
        else:  # interviewer
            return redirect(url_for('interviewer_dashboard'))
    # Check if any admin exists
    admin_exists = User.query.filter_by(role='admin').first()
    # If no admin, show setup admin form
    if not admin_exists:
        return redirect(url_for('setup_admin'))
    # Otherwise, redirect to login
    return redirect(url_for('user.login'))

@app.route('/dashboard')
def interviewer_dashboard():
    """Dashboard for interviewers - shows their interview calendar"""
    # Require login
    if not current_user.is_authenticated:
        return redirect(url_for('user.login', next=request.path))
    
    # Interviewers can access their calendar
    # Admin can also access this if they want
    
    # Get all districts
    today = datetime.now().date()
    current_month = today.month
    current_quarter = ((current_month - 1) // 3) + 1
    
    districts = District.query.all()
    district_slots = {}
    
    # Get slots for the current and future quarters only
    for district in districts:
        slots = InterviewSlot.query.filter_by(district_id=district.id)\
            .filter(InterviewSlot.date >= today)\
            .order_by(InterviewSlot.date, InterviewSlot.start_time).all()
        district_slots[district.id] = slots
    
    return render_template('interviewer_dashboard.html', districts=districts, district_slots=district_slots)

from routes_admin import admin_bp
app.register_blueprint(admin_bp)

@app.route('/admin/delete_old_slots', methods=['POST'])
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
@app.route('/admin/users')
@admin_required
def manage_users():
    users = User.query.all()
    invitations = UserInvitation.query.filter_by(is_used=False).all()
    return render_template('manage_users.html', users=users, invitations=invitations)

@app.route('/admin/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'interviewer')
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('manage_users'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'error')
            return redirect(url_for('manage_users'))
        
        # Check if invitation exists for this email
        if UserInvitation.query.filter_by(email=email, is_used=False).first():
            flash('An invitation already exists for this email.', 'error')
            return redirect(url_for('manage_users'))
        
        try:
            # Check password length (Werkzeug limit is 72 bytes)
            if len(password.encode('utf-8')) > 72:
                flash('Password must be 72 bytes or less.', 'error')
                return redirect(url_for('manage_users'))
            
            user = User(
                email=email,
                password=user_manager.hash_password(password),
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
        
        return redirect(url_for('manage_users'))
    
    return render_template('create_user.html')

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent editing yourself or the last admin
    if user.id == current_user.id:
        flash('Cannot edit your own account here. Use "Change Password" in your profile.', 'warning')
        return redirect(url_for('manage_users'))
    
    if request.method == 'POST':
        role = request.form.get('role')
        active = request.form.get('active') == 'on'
        
        # Prevent removing the last admin
        if user.role == 'admin' and role != 'admin':
            admin_count = User.query.filter_by(role='admin', active=True).count()
            if admin_count <= 1:
                flash('Cannot change role - this is the last active admin.', 'error')
                return redirect(url_for('manage_users'))
        
        user.role = role
        user.active = active
        db.session.commit()
        flash(f'User {user.email} updated successfully.', 'success')
        return redirect(url_for('manage_users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('manage_users'))
    
    # Prevent deleting the last admin
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot delete the last admin account.', 'error')
            return redirect(url_for('manage_users'))
    
    email = user.email
    db.session.delete(user)
    db.session.commit()
    flash(f'User {email} deleted successfully.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/invite', methods=['GET', 'POST'])
@admin_required
def invite_user():
    if request.method == 'POST':
        email = request.form.get('email')
        role = request.form.get('role', 'interviewer')
        
        if not email:
            flash('Email is required.', 'error')
            return redirect(url_for('invite_user'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'error')
            return redirect(url_for('invite_user'))
        
        # Check if invitation already exists and is still valid
        existing_invite = UserInvitation.query.filter_by(email=email, is_used=False).first()
        if existing_invite:
            if existing_invite.expires_at > datetime.now():
                flash('An active invitation already exists for this email.', 'warning')
                return redirect(url_for('invite_user'))
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
            invite_link = url_for('accept_invitation', token=token, _external=True)
            
            # Load email config
            sender_email = apply_email_config()
            if not sender_email:
                flash('Email configuration not set up. Please configure email settings first.', 'error')
                db.session.delete(invitation)
                db.session.commit()
                return redirect(url_for('invite_user'))
            
            print(f"Using MAIL_SERVER: {app.config.get('MAIL_SERVER')}, MAIL_PORT: {app.config.get('MAIL_PORT')}, MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
            
            msg = Message(
                'You are invited to Ministering Interview App',
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
            return redirect(url_for('manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error sending invitation: {str(e)}', 'error')
            return redirect(url_for('invite_user'))
    
    return render_template('invite_user.html')

@app.route('/admin/invitations/<int:invitation_id>/cancel', methods=['POST'])
@admin_required
def cancel_invitation(invitation_id):
    invitation = UserInvitation.query.get_or_404(invitation_id)
    
    if invitation.is_used:
        flash('Cannot cancel an accepted invitation.', 'error')
        return redirect(url_for('manage_users'))
    
    email = invitation.email
    db.session.delete(invitation)
    db.session.commit()
    flash(f'Invitation cancelled for {email}.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/user/accept-invite/<token>', methods=['GET', 'POST'])
def accept_invitation(token):
    invitation = UserInvitation.query.filter_by(token=token, is_used=False).first_or_404()
    
    # Check if invitation has expired
    if invitation.expires_at < datetime.now():
        flash('This invitation has expired. Please contact an administrator for a new one.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if not password:
            flash('Password is required.', 'error')
            return redirect(url_for('accept_invitation', token=token))
        
        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('accept_invitation', token=token))
        
        try:
            # Check password length
            if len(password.encode('utf-8')) > 72:
                flash('Password must be 72 bytes or less.', 'error')
                return redirect(url_for('accept_invitation', token=token))
            
            # Create user account
            user = User(
                email=invitation.email,
                password=user_manager.hash_password(password),
                role=invitation.role,
                active=True,
                email_confirmed_at=datetime.now()
            )
            db.session.add(user)
            db.session.flush()  # Get the user ID
            
            # Mark invitation as used
            invitation.is_used = True
            invitation.accepted_at = datetime.now()
            invitation.accepted_by_user_id = user.id
            
            db.session.commit()
            
            flash('Account created successfully! Please log in with your credentials.', 'success')
            return redirect(url_for('user.login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'error')
            return redirect(url_for('accept_invitation', token=token))
    
    return render_template('accept_invitation.html', email=invitation.email, expires_at=invitation.expires_at)

@app.route('/admin/districts')
@admin_required
def manage_districts():
    districts = District.query.all()
    return render_template('manage_districts.html', districts=districts)

@app.route('/admin/scrape', methods=['GET', 'POST'])
@admin_required
def scrape_data():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('scrape_data'))
        
        # Run scraping in a thread to avoid blocking
        progress_id = str(uuid.uuid4())
        with progress_lock:
            progress_store[progress_id] = {
                'status': 'running',
                'message': 'Initializing scraper...',
                'step': 0,
                'total_steps': 10,
                'districts_found': 0,
                'companionships_found': 0,
                'members_found': 0,
                'errors': []
            }
        
        def run_scrape():
            try:
                # Import the scraper module
                from app_scraper import scrape_ministering_data

                def progress_callback(message, counts=None):
                    # Update progress store with the message
                    with progress_lock:
                        progress_store[progress_id]['message'] = message

                        # Update counts if provided
                        if counts and isinstance(counts, dict):
                            if 'districts' in counts:
                                progress_store[progress_id]['districts_found'] = counts['districts']
                            if 'companionships' in counts:
                                progress_store[progress_id]['companionships_found'] = counts['companionships']
                            if 'members' in counts:
                                progress_store[progress_id]['members_found'] = counts['members']

                        # Try to extract step information from message
                        if 'Step' in message:
                            try:
                                step_num = int(message.split('Step')[1].split(':')[0].strip())
                                progress_store[progress_id]['step'] = step_num
                            except:
                                pass

                        # Check if this is an error message and add to errors list
                        if message.startswith('❌') or message.startswith('[ERROR]') or 'Error' in message or 'Failed' in message:
                            progress_store[progress_id]['errors'].append(message)
                            progress_store[progress_id]['status'] = 'error'
                        else:
                            progress_store[progress_id]['status'] = 'running'

                # Run the scraper
                results = scrape_ministering_data(username, password, progress_callback)

                if results:
                    with progress_lock:
                        progress_store[progress_id]['status'] = 'completed'
                        progress_store[progress_id]['message'] = 'Scraping completed'
                        progress_store[progress_id]['step'] = 10
                        progress_store[progress_id]['districts_found'] = len(set(row['district'] for row in results))
                        progress_store[progress_id]['companionships_found'] = len(set(row['companionship_id'] for row in results))
                        progress_store[progress_id]['members_found'] = len(results)
                        progress_store[progress_id]['scraped_districts'] = group_results_by_district(results)
                        progress_store[progress_id]['raw_results'] = results  # Store raw results for CSV download
                else:
                    with progress_lock:
                        progress_store[progress_id]['status'] = 'error'
                        # Check if we have any error messages from the progress callback
                        if progress_store[progress_id]['errors']:
                            progress_store[progress_id]['message'] = 'Scraping failed - check errors below'
                        else:
                            progress_store[progress_id]['message'] = 'Scraping failed - no data returned'
                            progress_store[progress_id]['errors'].append('Scraper returned no data. Check credentials and network connection.')

            except Exception as e:
                with progress_lock:
                    progress_store[progress_id]['status'] = 'error'
                    progress_store[progress_id]['message'] = str(e)
                    progress_store[progress_id]['errors'].append(str(e))
        
        thread = threading.Thread(target=run_scrape)
        thread.start()
        
        return redirect(url_for('scrape_progress', progress_id=progress_id))
    
    return render_template('scrape.html')

@app.route('/admin/scrape_progress/<progress_id>')
@admin_required
def scrape_progress(progress_id):
    return render_template('scrape_progress.html', progress_id=progress_id)

@app.route('/admin/download_csv/<progress_id>')
@admin_required
def download_csv(progress_id):
    with progress_lock:
        progress_data = progress_store.get(progress_id)
    
    if not progress_data or progress_data['status'] != 'completed':
        flash('No completed scrape data found.')
        return redirect(url_for('scrape_data'))
    
    raw_results = progress_data.get('raw_results')
    if not raw_results:
        flash('No raw data available for download.')
        return redirect(url_for('scrape_data'))
    
    # Create CSV in memory
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['district', 'interviewer', 'name', 'phone', 'email', 'companionship_id'])
    writer.writeheader()
    for row in raw_results:
        writer.writerow(row)
    
    # Create response
    output.seek(0)
    response = send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='ministering_brothers.csv'
    )
    
    return response

@app.route('/admin/import_csv', methods=['GET', 'POST'])
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
            import csv
            import io
            
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
            return redirect(url_for('import_csv_confirm'))
        
        except Exception as e:
            flash(f'Error processing CSV: {str(e)}')
            return redirect(request.url)
    
    return render_template('import_csv.html')
@app.route('/admin/district/new', methods=['GET', 'POST'])
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

@app.route('/admin/district/<int:id>')
@admin_required
def district_detail(id):
    district = District.query.get_or_404(id)
    return render_template('district_detail.html', district=district)

@app.route('/admin/district/<int:id>/companionship/new', methods=['GET', 'POST'])
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
        return redirect(url_for('district_detail', id=id))
    
    # Get existing members from all districts for reassignment
    existing_members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name, Member.name).all()
    return render_template('new_companionship.html', district=district, existing_members=existing_members)

@app.route('/admin/district/<int:id>/slots', methods=['GET', 'POST'])
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
                return redirect(url_for('manage_slots', id=id))
            
            if start_date >= end_date:
                flash('Start date must be before end date.')
                return redirect(url_for('manage_slots', id=id))
            
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
                            existing_end_time = (datetime.combine(current_date, existing.start_time) + timedelta(minutes=existing.duration)).time()
                            if existing.start_time < slot_end_time and slot_time < existing_end_time:
                                overlap = True
                                break
                        
                        if overlap:
                            skipped_slots.append(f"Skipped slot on {current_date} at {slot_time} - overlaps with existing slot")
                        else:
                            slot = InterviewSlot(district_id=id, date=current_date, start_time=slot_time, 
                                               duration=duration, max_slots=10)
                            db.session.add(slot)
                            slots_created += 1
                current_date += timedelta(days=1)
            
            db.session.commit()
            flash(f'Generated {slots_created} recurring slots!')
            if skipped_slots:
                combined_msg = "The following slots were skipped due to conflicts:<br>" + "<br>".join(skipped_slots)
                flash(combined_msg, 'warning')
            return redirect(url_for('manage_slots', id=id))
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
            return redirect(url_for('manage_slots', id=id))
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
            return redirect(url_for('manage_slots', id=id))
    
    slots = InterviewSlot.query.filter_by(district_id=id).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
    return render_template('manage_slots.html', district=district, slots=slots, default_end_date=default_end_date, today=today)

@app.route('/schedule/<token>')
def schedule(token):
    member = Member.query.filter_by(token=token).first_or_404()
    district = member.companionship.district
    current_quarter = ((datetime.now().month - 1) // 3) + 1
    available_slots = InterviewSlot.query.filter_by(district_id=district.id).filter(
        InterviewSlot.date >= datetime.now().date(),
        InterviewSlot.quarter == current_quarter
    ).outerjoin(Booking).group_by(InterviewSlot.id).having(
        func.count(Booking.id) < InterviewSlot.max_slots
    ).order_by(InterviewSlot.date, InterviewSlot.start_time).all()

    # Find member's current booking for this quarter
    my_booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == current_quarter,
        InterviewSlot.date >= datetime.now().date()
    ).first()

    # Find if any companion (companionship member) has already booked a slot
    companion_booking = None
    if member.companionship:
        for companionship_member in member.companionship.members:
            if companionship_member.id != member.id:  # Check other companionship members
                booking = Booking.query.join(InterviewSlot).filter(
                    Booking.member_id == companionship_member.id,
                    InterviewSlot.quarter == current_quarter,
                    InterviewSlot.date >= datetime.now().date()
                ).first()
                if booking:
                    companion_booking = {
                        'slot': booking.slot,
                        'companion_name': companionship_member.name
                    }
                    break  # Only show first companion's booking

    return render_template('schedule.html', member=member, slots=available_slots, companion_booking=companion_booking, my_booking=my_booking)

@app.route('/book/<int:slot_id>/<token>', methods=['POST'])
def book_slot(slot_id, token):
    member = Member.query.filter_by(token=token).first_or_404()
    slot = InterviewSlot.query.get_or_404(slot_id)
    interview_type = request.form.get('interview_type', 'in-person')

    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member.id).first()
    if existing:
        flash('You are already booked for this slot.')
        return redirect(url_for('schedule', token=token))

    # Check companionship restriction
    if slot.bookings:
        existing_companionship = slot.bookings[0].member.companionship
        if member.companionship != existing_companionship:
            flash('This slot is reserved for another companionship.')
            return redirect(url_for('schedule', token=token))

    if len(slot.bookings) < slot.max_slots:
        booking = Booking(slot_id=slot_id, member_id=member.id, interview_type=interview_type)
        db.session.add(booking)
        db.session.commit()
        flash('Slot booked successfully!', 'success')
    else:
        flash('Slot is full.', 'error')

    return redirect(url_for('schedule', token=token))

@app.route('/unbook/<token>', methods=['POST'])
def unbook_slot(token):
    member = Member.query.filter_by(token=token).first_or_404()
    current_quarter = ((datetime.now().month - 1) // 3) + 1

    # Find member's current booking for this quarter
    booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == current_quarter,
        InterviewSlot.date >= datetime.now().date()
    ).first()

    if booking:
        db.session.delete(booking)
        db.session.commit()
        flash('Your booking has been cancelled. You can now book a different time slot.', 'success')
    else:
        flash('No booking found to cancel.', 'error')

    return redirect(url_for('schedule', token=token))

@app.route('/admin/send_notifications/<int:district_id>')
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
        return redirect(url_for('district_detail', id=district_id))

    # Load email and SMS config
    sender_email = apply_email_config()
    sms_configured = apply_sms_config()

    if not sender_email:
        flash('Email not configured. Please configure email settings before sending notifications.', 'error')
        return redirect(url_for('district_detail', id=district_id))

    sent_count = 0
    skipped_count = 0

    for companionship in district.companionships:
        for member in companionship.members:
            # Skip if member already has a booking for current quarter
            if member.has_booking_for_quarter(current_quarter, current_year):
                skipped_count += 1
                continue

            link = url_for('schedule', token=member.token, _external=True)

            # Send email
            if member.email:
                try:
                    msg = Message('Ministering Interview', sender=sender_email,
                                recipients=[member.email])
                    msg.body = f'Please schedule your interview: {link}'
                    mail.send(msg)
                    sent_count += 1

                    # Log successful email send
                    log = NotificationLog(
                        member_id=member.id,
                        method='email',
                        quarter=current_quarter,
                        year=current_year,
                        success=True
                    )
                    db.session.add(log)
                except Exception as e:
                    print(f"Failed to send email to {member.email}: {e}")

                    # Log failed email send
                    log = NotificationLog(
                        member_id=member.id,
                        method='email',
                        quarter=current_quarter,
                        year=current_year,
                        success=False,
                        error_message=str(e)
                    )
                    db.session.add(log)

            # Send SMS (only if enabled and configured)
            if sms_configured and member.can_receive_sms():
                try:
                    sms_message = format_sms_message(link, member)
                    send_sms(member.phone, sms_message)

                    # Log successful SMS send
                    log = NotificationLog(
                        member_id=member.id,
                        method='sms',
                        quarter=current_quarter,
                        year=current_year,
                        success=True
                    )
                    db.session.add(log)
                except Exception as e:
                    print(f"Failed to send SMS to {member.phone}: {e}")

                    # Log failed SMS send
                    log = NotificationLog(
                        member_id=member.id,
                        method='sms',
                        quarter=current_quarter,
                        year=current_year,
                        success=False,
                        error_message=str(e)
                    )
                    db.session.add(log)

    # Commit all notification logs
    db.session.commit()

    message = f'Notifications sent to {sent_count} members.'
    if skipped_count > 0:
        message += f' Skipped {skipped_count} members who already have bookings.'
    flash(message, 'success')
    return redirect(url_for('district_detail', id=district_id))

@app.route('/admin/add_booking/<int:slot_id>', methods=['POST'])
@admin_required
def add_booking(slot_id):
    slot = InterviewSlot.query.get_or_404(slot_id)
    member_id = request.form['member_id']
    interview_type = request.form.get('interview_type', 'in-person')
    member = Member.query.get_or_404(member_id)

    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member_id).first()
    if existing:
        flash(f'{member.name} is already booked for this slot.')
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
            flash(f'Added {member.name} to the slot.')
        else:
            flash('Slot is full.')

    return redirect(url_for('admin.admin'))

@app.route('/admin/remove_booking/<int:booking_id>', methods=['POST'])
@admin_required
def remove_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    slot = booking.slot
    member_name = booking.member.name
    db.session.delete(booking)
    db.session.commit()
    flash(f'Removed {member_name} from the slot.')
    return redirect(url_for('admin.admin'))

@app.route('/admin/delete_slot/<int:slot_id>', methods=['POST'])
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
    return redirect(url_for('manage_slots', id=district_id))

@app.route('/admin/companionship/<int:companionship_id>/add_member', methods=['GET', 'POST'])
@admin_required
def add_member(companionship_id):
    companionship = Companionship.query.get_or_404(companionship_id)

    # Get all members from all districts for reassignment
    all_members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name, Member.name).all()

    if request.method == 'POST':
        # Check if reassigning an existing member or creating a new one
        existing_member_id = request.form.get('existing_member_id')

        if existing_member_id:
            # Reassign existing member to this companionship
            member = Member.query.get_or_404(existing_member_id)

            # Remove any existing bookings
            bookings = Booking.query.filter_by(member_id=member.id).all()
            for booking in bookings:
                db.session.delete(booking)

            # Reassign to new companionship
            old_companionship_id = member.companionship_id
            member.companionship_id = companionship_id
            db.session.commit()
            flash(f'Reassigned {member.name} to this companionship!')
            return redirect(url_for('district_detail', id=companionship.district_id))
        else:
            # Create new member
            name = request.form['name']
            phone = request.form.get('phone', '')
            email = request.form['email']
            if name and email:
                member = Member(companionship_id=companionship_id, name=name, phone=phone, email=email)
                db.session.add(member)
                db.session.commit()
                flash(f'Added {name} to companionship!')
                return redirect(url_for('district_detail', id=companionship.district_id))

    return render_template('add_member.html', companionship=companionship, all_members=all_members)

@app.route('/admin/unassign_member/<int:member_id>', methods=['POST'])
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
        return redirect(url_for('district_detail', id=district_id))
    else:
        return redirect(url_for('manage_members'))

@app.route('/admin/remove_companionship/<int:companionship_id>', methods=['POST'])
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
    return redirect(url_for('district_detail', id=district_id))

@app.route('/admin/district/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_district(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        district.name = request.form['name']
        district.interviewer_name = request.form['interviewer']
        db.session.commit()
        flash('District updated!')
        return redirect(url_for('district_detail', id=id))
    return render_template('edit_district.html', district=district)

@app.route('/admin/members')
@admin_required
def manage_members():
    """View and manage all members across all districts."""
    members = Member.query.outerjoin(Companionship).outerjoin(District).order_by(District.name.nulls_last(), Companionship.id.nulls_last(), Member.name).all()
    districts = District.query.all()
    return render_template('manage_members.html', members=members, districts=districts)

@app.route('/admin/member/<int:member_id>/reassign', methods=['POST'])
@admin_required
def reassign_member(member_id):
    """Reassign a member to a different companionship."""
    member = Member.query.get_or_404(member_id)
    new_companionship_id = request.form.get('new_companionship_id', type=int)
    
    if not new_companionship_id:
        flash('Please select a companionship.')
        return redirect(url_for('manage_members'))
    
    new_companionship = Companionship.query.get_or_404(new_companionship_id)
    old_companionship_id = member.companionship_id
    
    # Remove any existing bookings
    bookings = Booking.query.filter_by(member_id=member_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    # Reassign to new companionship
    member.companionship_id = new_companionship_id
    db.session.commit()
    
    flash(f'Reassigned {member.name} to Companionship {new_companionship_id} in {new_companionship.district.name}')
    return redirect(url_for('manage_members'))

@app.route('/admin/edit_member/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        member.name = request.form['name']
        member.phone = request.form['phone']
        member.email = request.form['email']
        member.no_sms = request.form.get('no_sms') == 'on'
        db.session.commit()
        flash(f'Updated {member.name}!')
        return redirect(url_for('district_detail', id=member.companionship.district_id))
    return render_template('edit_member.html', member=member)

def group_results_by_district(results):
    """Group scraping results by district for display."""
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
    
    return scraped_districts

@app.route('/admin/import_companionships', methods=['GET', 'POST'])
def import_companionships():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Initialize progress tracking
        progress_id = str(uuid.uuid4())
        progress_data = {
            'id': progress_id,
            'status': 'starting',
            'message': 'Setting up Chrome browser...',
            'step': 0,
            'total_steps': 8,
            'districts_found': 0,
            'companionships_found': 0,
            'members_found': 0,
            'errors': []
        }
        
        with progress_lock:
            progress_store[progress_id] = progress_data
        
        # Start the scraping in a background thread
        from threading import Thread
        thread = Thread(target=perform_scraping, args=(username, password, progress_id, app))
        thread.daemon = True
        thread.start()
        
        # Return progress ID for frontend polling
        return {'progress_id': progress_id, 'status': 'started'}
    
    return render_template('import_companionships.html')

@app.route('/admin/import_progress/<progress_id>')
def import_progress(progress_id):
    with progress_lock:
        progress_data = progress_store.get(progress_id)
    if progress_data:
        return {
            'status': progress_data['status'],
            'message': progress_data['message'],
            'step': progress_data['step'],
            'total_steps': progress_data['total_steps'],
            'districts_found': progress_data.get('districts_found', 0),
            'companionships_found': progress_data['companionships_found'],
            'members_found': progress_data['members_found'],
            'errors': progress_data['errors'],
            'redirect_url': progress_data.get('redirect_url'),
            'scraped_districts': progress_data.get('scraped_districts', [])
        }
    return {'status': 'not_found'}

@app.route('/admin/import_confirm', methods=['GET', 'POST'])
def import_confirm():
    progress_id = request.args.get('progress_id')
    
    with progress_lock:
        progress_data = progress_store.get(progress_id)
        if not progress_data or progress_data['status'] != 'completed':
            flash('No completed scrape data found.')
            return redirect(url_for('scrape_data'))
        
        scraped_districts = progress_data['scraped_districts']
    
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
                        existing_member = Member.query.filter_by(email=member_data['email']).first()
                        
                        if existing_member:
                            # Update phone if different
                            if existing_member.phone != member_data['phone'] and member_data['phone']:
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
                                phone=member_data['phone'],
                                email=member_data['email'],
                                companionship_id =companionship.id
                            )
                            db.session.add(member)
                        
                        # Ensure member is in the companionship
                        if member not in companionship.members:
                            companionship.members.append(member)
                    
                    db.session.commit()
            
            flash('Data imported successfully!')
            return redirect(url_for('admin_calendar'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}')
            return redirect(url_for('scrape_progress', progress_id=progress_id))
    
    # Display confirmation
    return render_template('import_confirm.html', scraped_districts=scraped_districts, progress_id=progress_id, confirm_endpoint='import_confirm')

@app.route('/admin/import_csv_confirm', methods=['GET', 'POST'])
def import_csv_confirm():
    scraped_districts = session.get('uploaded_districts')
    if not scraped_districts:
        flash('No uploaded data found.')
        return redirect(url_for('import_csv'))
    
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
                        existing_member = Member.query.filter_by(email=member_data['email']).first()
                        
                        if existing_member:
                            # Update phone if different
                            if existing_member.phone != member_data['phone'] and member_data['phone']:
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
                                phone=member_data['phone'],
                                email=member_data['email'],
                                companionship_id =companionship.id
                            )
                            db.session.add(member)
                        
                        # Ensure member is in the companionship
                        if member not in companionship.members:
                            companionship.members.append(member)
                    
                    db.session.commit()
            
            session.pop('uploaded_districts', None)
            flash('Data imported successfully!')
            return redirect(url_for('admin_calendar'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}')
            return redirect(url_for('import_csv_confirm'))
    
    # Display confirmation
    return render_template('import_confirm.html', scraped_districts=scraped_districts, confirm_endpoint='import_csv_confirm')

@app.route('/admin/trigger_reminders')
@admin_required
def trigger_reminders_manually():
    """Manually trigger the booking reminder job (for testing)"""
    try:
        send_booking_reminders()
        flash('Reminder job executed successfully! Check console for details.', 'success')
    except Exception as e:
        flash(f'Error running reminder job: {str(e)}', 'error')
    return redirect(url_for('admin.admin'))

@app.route('/admin/send_all_notifications')
@admin_required
def send_all_notifications():
    districts = District.query.all()

    # Get current quarter
    today = datetime.now().date()
    current_quarter = ((today.month - 1) // 3) + 1
    current_year = today.year

    # Load email and SMS config
    sender_email = apply_email_config()
    sms_configured = apply_sms_config()

    if not sender_email:
        flash('Email not configured. Please configure email settings before sending notifications.', 'error')
        return redirect(url_for('admin.admin'))

    sent_count = 0
    skipped_count = 0
    districts_without_slots = []

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

        for companionship in district.companionships:
            for member in companionship.members:
                # Skip if member already has a booking for current quarter
                if member.has_booking_for_quarter(current_quarter, current_year):
                    skipped_count += 1
                    continue

                link = url_for('schedule', token=member.token, _external=True)

                # Send email
                if member.email:
                    try:
                        msg = Message('Ministering Interview', sender=sender_email,
                                    recipients=[member.email])
                        msg.body = f'Please schedule your interview: {link}'
                        mail.send(msg)
                        sent_count += 1

                        # Log successful email send
                        log = NotificationLog(
                            member_id=member.id,
                            method='email',
                            quarter=current_quarter,
                            year=current_year,
                            success=True
                        )
                        db.session.add(log)
                    except Exception as e:
                        print(f"Failed to send email to {member.email}: {e}")

                        # Log failed email send
                        log = NotificationLog(
                            member_id=member.id,
                            method='email',
                            quarter=current_quarter,
                            year=current_year,
                            success=False,
                            error_message=str(e)
                        )
                        db.session.add(log)

                # Send SMS (only if enabled and configured)
                if sms_configured and member.can_receive_sms():
                    try:
                        sms_message = format_sms_message(link, member)
                        send_sms(member.phone, sms_message)

                        # Log successful SMS send
                        log = NotificationLog(
                            member_id=member.id,
                            method='sms',
                            quarter=current_quarter,
                            year=current_year,
                            success=True
                        )
                        db.session.add(log)
                    except Exception as e:
                        print(f"Failed to send SMS to {member.phone}: {e}")

                        # Log failed SMS send
                        log = NotificationLog(
                            member_id=member.id,
                            method='sms',
                            quarter=current_quarter,
                            year=current_year,
                            success=False,
                            error_message=str(e)
                        )
                        db.session.add(log)

    # Commit all notification logs
    db.session.commit()

    message = f'Notifications sent to {sent_count} members.'
    if skipped_count > 0:
        message += f' Skipped {skipped_count} members who already have bookings.'
    if districts_without_slots:
        message += f' Skipped districts without slots: {", ".join(districts_without_slots)}.'
    flash(message, 'success')
    return redirect(url_for('admin.admin'))

@app.route('/admin/notification_report')
@admin_required
def notification_report():
    """Generate report of notification sends by quarter"""
    # Get current quarter
    today = datetime.now().date()
    current_quarter = ((today.month - 1) // 3) + 1
    current_year = today.year

    # Allow filtering by quarter and year
    selected_quarter = request.args.get('quarter', current_quarter, type=int)
    selected_year = request.args.get('year', current_year, type=int)

    # Get filter parameters
    filter_not_sent = request.args.get('not_sent', 'off') == 'on'
    filter_sent = request.args.get('sent', 'off') == 'on'
    filter_no_booking = request.args.get('no_booking', 'off') == 'on'

    # Get all members grouped by district and companionship
    districts = District.query.order_by(District.name).all()

    # Build report data
    report_data = []
    for district in districts:
        for companionship in district.companionships:
            for member in companionship.members:
                # Get notification logs for this member and quarter
                notifications = NotificationLog.query.filter_by(
                    member_id=member.id,
                    quarter=selected_quarter,
                    year=selected_year
                ).order_by(NotificationLog.sent_at.desc()).all()

                # Separate by method
                email_logs = [n for n in notifications if n.method == 'email']
                sms_logs = [n for n in notifications if n.method == 'sms']

                email_sent = len(email_logs) > 0
                sms_sent = len(sms_logs) > 0
                any_sent = email_sent or sms_sent
                has_booking = member.has_booking_for_quarter(selected_quarter, selected_year)

                member_data = {
                    'member': member,
                    'district': district,
                    'companionship': companionship,
                    'email_sent': email_sent,
                    'email_success': email_logs[0].success if email_logs else None,
                    'email_sent_at': email_logs[0].sent_at if email_logs else None,
                    'email_error': email_logs[0].error_message if email_logs and not email_logs[0].success else None,
                    'sms_sent': sms_sent,
                    'sms_success': sms_logs[0].success if sms_logs else None,
                    'sms_sent_at': sms_logs[0].sent_at if sms_logs else None,
                    'sms_error': sms_logs[0].error_message if sms_logs and not sms_logs[0].success else None,
                    'has_booking': has_booking,
                    'any_sent': any_sent
                }

                # Apply filters
                if filter_not_sent and any_sent:
                    continue
                if filter_sent and not any_sent:
                    continue
                if filter_no_booking and has_booking:
                    continue

                report_data.append(member_data)

    # Calculate summary statistics (from original data before filtering)
    all_data = []
    for district in districts:
        for companionship in district.companionships:
            for member in companionship.members:
                notifications = NotificationLog.query.filter_by(
                    member_id=member.id,
                    quarter=selected_quarter,
                    year=selected_year
                ).all()
                email_sent = any(n.method == 'email' for n in notifications)
                sms_sent = any(n.method == 'sms' for n in notifications)
                has_booking = member.has_booking_for_quarter(selected_quarter, selected_year)
                all_data.append({
                    'email_sent': email_sent,
                    'sms_sent': sms_sent,
                    'has_booking': has_booking
                })

    total_members = len(all_data)
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

@app.route('/admin/send_individual_notification/<int:member_id>', methods=['POST'])
@admin_required
def send_individual_notification(member_id):
    """Send notification to a single member"""
    member = Member.query.get_or_404(member_id)

    # Get current quarter
    today = datetime.now().date()
    current_quarter = ((today.month - 1) // 3) + 1
    current_year = today.year

    # Get member's district
    district = member.companionship.district if member.companionship else None
    if not district:
        return jsonify({'success': False, 'error': 'Member is not assigned to a district'}), 400

    # Check if there are any available slots for this district in current quarter
    available_slots = InterviewSlot.query.filter_by(district_id=district.id).filter(
        InterviewSlot.date >= today,
        InterviewSlot.quarter == current_quarter
    ).all()

    if not available_slots:
        return jsonify({'success': False, 'error': 'No interview slots available for the current quarter'}), 400

    # Load email and SMS config
    sender_email = apply_email_config()
    sms_configured = apply_sms_config()

    if not sender_email:
        return jsonify({'success': False, 'error': 'Email not configured'}), 400

    link = url_for('schedule', token=member.token, _external=True)
    email_sent = False
    sms_sent = False
    errors = []

    # Send email
    if member.email:
        try:
            msg = Message('Ministering Interview', sender=sender_email,
                        recipients=[member.email])
            msg.body = f'Please schedule your interview: {link}'
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
        except Exception as e:
            errors.append(f"Email failed: {str(e)}")

            # Log failed email send
            log = NotificationLog(
                member_id=member.id,
                method='email',
                quarter=current_quarter,
                year=current_year,
                success=False,
                error_message=str(e)
            )
            db.session.add(log)

    # Send SMS (only if enabled and configured)
    if sms_configured and member.can_receive_sms():
        try:
            sms_message = format_sms_message(link, member)
            send_sms(member.phone, sms_message)
            sms_sent = True

            # Log successful SMS send
            log = NotificationLog(
                member_id=member.id,
                method='sms',
                quarter=current_quarter,
                year=current_year,
                success=True
            )
            db.session.add(log)
        except Exception as e:
            errors.append(f"SMS failed: {str(e)}")

            # Log failed SMS send
            log = NotificationLog(
                member_id=member.id,
                method='sms',
                quarter=current_quarter,
                year=current_year,
                success=False,
                error_message=str(e)
            )
            db.session.add(log)

    # Commit all notification logs
    db.session.commit()

    # Prepare response message
    messages = []
    if email_sent:
        messages.append('Email sent')
    if sms_sent:
        messages.append('SMS sent')

    if not email_sent and not sms_sent:
        return jsonify({
            'success': False,
            'error': ' | '.join(errors) if errors else 'No notifications sent'
        }), 400

    return jsonify({
        'success': True,
        'message': ' and '.join(messages),
        'email_sent': email_sent,
        'sms_sent': sms_sent
    })

# System Settings Routes
@app.route('/admin/settings', methods=['GET'])
@admin_required
def system_settings():
    """Display system settings page"""
    config = SystemConfig.query.first()
    if not config:
        config = SystemConfig()
    else:
        # Decrypt fields for display
        config = type('obj', (object,), config.decrypt_fields())()
    
    return render_template('system_settings.html', config=config)

@app.route('/admin/settings/save', methods=['POST'])
@admin_required
def save_system_settings():
    """Save system settings"""
    config_type = request.form.get('config_type')
    
    # Get or create config
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
            
            # Only update password if provided
            mail_password = request.form.get('mail_password', '')
            if mail_password:
                config.mail_password = mail_password
            
        elif config_type == 'sms':
            # SMS Mode and Contact Settings
            config.sms_mode = request.form.get('sms_mode', 'one_way')
            config.sms_contact_enabled = request.form.get('sms_contact_enabled') == 'on'
            config.sms_contact_name = request.form.get('sms_contact_name', '')
            config.sms_contact_phone = request.form.get('sms_contact_phone', '')

            # SMS Provider
            config.sms_provider = request.form.get('sms_provider', 'twilio')

            # Twilio settings
            if config.sms_provider == 'twilio':
                config.twilio_account_sid = request.form.get('twilio_account_sid', '')
                config.twilio_phone_number = request.form.get('twilio_phone_number', '')
                twilio_auth_token = request.form.get('twilio_auth_token', '')
                if twilio_auth_token:
                    config.twilio_auth_token = twilio_auth_token

            # AWS SNS settings
            elif config.sms_provider == 'aws_sns':
                config.aws_access_key_id = request.form.get('aws_access_key_id', '')
                config.aws_region = request.form.get('aws_region', '')
                config.aws_sns_sender_id = request.form.get('aws_sns_sender_id', '')
                aws_secret_key = request.form.get('aws_secret_access_key', '')
                if aws_secret_key:
                    config.aws_secret_access_key = aws_secret_key

            # SignalWire settings
            elif config.sms_provider == 'signalwire':
                config.signalwire_project_id = request.form.get('signalwire_project_id', '')
                config.signalwire_space_url = request.form.get('signalwire_space_url', '')
                config.signalwire_phone_number = request.form.get('signalwire_phone_number', '')
                signalwire_auth_token = request.form.get('signalwire_auth_token', '')
                if signalwire_auth_token:
                    config.signalwire_auth_token = signalwire_auth_token

        elif config_type == 'scheduler':
            config.reminder_enabled = request.form.get('reminder_enabled') == 'on'
            config.reminder_day_of_week = int(request.form.get('reminder_day_of_week', 0))
            config.reminder_hour = int(request.form.get('reminder_hour', 9))
            config.reminder_minute = int(request.form.get('reminder_minute', 0))

            # Reschedule the reminder job with new settings
            reschedule_reminder_job(config)

        # Encrypt sensitive fields before saving
        config.encrypt_fields()

        db.session.add(config)
        db.session.commit()
        
        flash(f'{config_type.capitalize()} settings saved successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error saving settings: {str(e)}', 'error')

    # Redirect back to the same tab
    return redirect(url_for('admin.system_settings') + f'#{config_type}')

@app.route('/admin/settings/test-email')
@admin_required
def send_test_email():
    """Send a test email"""
    config = SystemConfig.query.first()
    if not config:
        flash('System settings not configured yet.', 'error')
        return redirect(url_for('admin.system_settings'))
    
    try:
        # Decrypt and apply settings
        decrypted = config.decrypt_fields()
        app.config['MAIL_SERVER'] = decrypted['mail_server']
        app.config['MAIL_PORT'] = decrypted['mail_port']
        app.config['MAIL_USE_TLS'] = decrypted['mail_use_tls']
        app.config['MAIL_USERNAME'] = decrypted['mail_username']
        app.config['MAIL_PASSWORD'] = decrypted['mail_password']
        
        msg = Message(
            'Test Email from Ministering Interview App',
            sender=decrypted['mail_from_email'],
            recipients=[current_user.email]
        )
        msg.body = 'This is a test email to verify your email settings are working correctly.'
        mail.send(msg)
        
        flash(f'Test email sent successfully to {current_user.email}!', 'success')
    except Exception as e:
        flash(f'Failed to send test email: {str(e)}', 'error')

    return redirect(url_for('admin.system_settings') + '#email')

@app.route('/admin/settings/test-sms', methods=['POST'])
@admin_required
def send_test_sms():
    """Send a test SMS"""
    config = SystemConfig.query.first()
    if not config:
        flash('System settings not configured yet.', 'error')
        return redirect(url_for('admin.system_settings') + '#sms')

    # Get phone number from form
    test_phone = request.form.get('test_phone_number', '').strip()
    if not test_phone:
        flash('Please enter a phone number to send the test SMS.', 'error')
        return redirect(url_for('admin.system_settings') + '#sms')

    try:
        # Reload SMS config
        if not apply_sms_config():
            flash('❌ SMS not configured. Please configure your SMS provider settings first.', 'error')
            return redirect(url_for('admin.system_settings') + '#sms')

        # Create a test link
        test_link = request.url_root + 'schedule/test-token-123'

        # Format the message using the same function as real notifications
        test_message = format_sms_message(test_link)

        # Send the test SMS - call provider directly to get detailed errors
        global sms_config

        if not sms_config.get('provider') or not sms_config.get('client'):
            flash('❌ SMS provider not configured properly. Check your credentials.', 'error')
            return redirect(url_for('admin.system_settings') + '#sms')

        # Send based on provider (with detailed error handling)
        if sms_config['provider'] == 'twilio':
            result = sms_config['client'].messages.create(
                body=test_message,
                from_=sms_config['from_number'],
                to=test_phone
            )
            flash(f'✅ Test SMS sent successfully to {test_phone}! Message SID: {result.sid}', 'success')

        elif sms_config['provider'] == 'aws_sns':
            params = {
                'PhoneNumber': test_phone,
                'Message': test_message
            }
            if sms_config.get('sender_id'):
                params['MessageAttributes'] = {
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': sms_config['sender_id']
                    }
                }
            result = sms_config['client'].publish(**params)
            flash(f'✅ Test SMS sent successfully to {test_phone}! Message ID: {result["MessageId"]}', 'success')

        elif sms_config['provider'] == 'signalwire':
            result = sms_config['client'].messages.create(
                body=test_message,
                from_=sms_config['from_number'],
                to=to_number
            )
            flash(f'✅ Test SMS sent successfully to {test_phone}! Message SID: {result.sid}', 'success')

    except Exception as e:
        # Show detailed error information
        error_type = type(e).__name__
        error_msg = str(e)

        # Try to extract more detailed error info from provider-specific exceptions
        detailed_msg = f'❌ Failed to send test SMS\n\n'
        detailed_msg += f'<strong>Error Type:</strong> {error_type}\n'
        detailed_msg += f'<strong>Error Message:</strong> {error_msg}\n\n'

        # Add troubleshooting hints based on error
        if 'credentials' in error_msg.lower() or 'auth' in error_msg.lower():
            detailed_msg += '<strong>💡 Hint:</strong> Check your API credentials (Account SID, Auth Token, Access Keys)'
        elif 'phone' in error_msg.lower() or 'number' in error_msg.lower():
            detailed_msg += '<strong>💡 Hint:</strong> Verify phone number format (use international format: +1234567890)'
        elif 'region' in error_msg.lower():
            detailed_msg += '<strong>💡 Hint:</strong> Check your AWS region setting'
        elif 'from' in error_msg.lower():
            detailed_msg += '<strong>💡 Hint:</strong> Verify your sender phone number is configured correctly'
        else:
            detailed_msg += f'<strong>💡 Hint:</strong> Check your SMS provider console for more details'

        flash(detailed_msg, 'error')

    return redirect(url_for('admin.system_settings') + '#sms')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Load email config from database if it exists (for Flask-User compatibility)
        apply_email_config()
        # Load SMS config from database
        apply_sms_config()
        # UserManager is already initialized at module level (for gunicorn compatibility)

        # Schedule automated reminder job based on database settings
        config = SystemConfig.query.first()
        if config:
            reschedule_reminder_job(config)
        else:
            # Default schedule if no config exists
            print("No system config found, using default schedule (Monday 9:00 AM)")
            scheduler.add_job(
                func=send_booking_reminders,
                trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
                id='booking_reminders',
                name='Send booking reminders to members without appointments',
                replace_existing=True
            )

    app.run(debug=True, host='0.0.0.0', port=8181)