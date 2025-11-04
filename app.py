
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_user import UserManager, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func
from twilio_config import twilio_client, twilio_number
import secrets
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
import uuid
import threading

# Global thread-safe storage for progress data
progress_store = {}
progress_lock = threading.Lock()

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interviews.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration (update with your SMTP settings)
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_PORT'] = 1025
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

# Flask-User configuration
app.config['USER_APP_NAME'] = 'Ministering Interview App'
app.config['USER_EMAIL_SENDER_EMAIL'] = os.environ.get('MAIL_USERNAME', 'noreply@example.com')
app.config['USER_EMAIL_SENDER_NAME'] = 'Ministering Interview App'
app.config['USER_ENABLE_EMAIL'] = True
app.config['USER_ENABLE_USERNAME'] = False  # Use email as login identifier
app.config['USER_ENABLE_REGISTER'] = False  # Disable registration - only via invite or admin
app.config['USER_REQUIRE_RETYPE_PASSWORD'] = False
app.config['USER_PASSWORD_MIN_LENGTH'] = 6
app.config['USER_PASSLIB_CRYPTCONTEXT_SCHEMES'] = ['pbkdf2_sha256', 'bcrypt', 'argon2']
# Note: USER_AFTER_LOGIN_ENDPOINT removed - we handle redirects based on role in a custom handler
app.config['USER_ENABLE_FORGOT_PASSWORD'] = True
app.config['USER_ENABLE_CHANGE_PASSWORD'] = True
app.config['USER_ENABLE_CHANGE_EMAIL'] = False
# Important: Tell Flask-User to use our session
app.config['USER_ENABLE_RETYPE_EMAIL'] = False
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)

db = SQLAlchemy(app)
mail = Mail(app)

# Context processor to make 'now' available in all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Redirect authenticated users away from login page, based on role
@app.before_request
def redirect_authenticated_user():
    if current_user.is_authenticated and request.endpoint == 'user.login':
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        # Redirect based on role
        if current_user.role == 'admin':
            return redirect(url_for('admin'))
        else:  # interviewer
            return redirect(url_for('interviewer_dashboard'))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'interviewer'
    active = db.Column(db.Boolean(), nullable=False, default=True)
    email_confirmed_at = db.Column(db.DateTime())

class UserInvitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    token = db.Column(db.String(64), nullable=False, unique=True)
    role = db.Column(db.String(20), nullable=False, default='interviewer')  # 'admin' or 'interviewer'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    accepted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_used = db.Column(db.Boolean, default=False)

# Flask-User setup (after User model is defined)
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
    teams = db.relationship('Team', backref='district', lazy=True)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    members = db.relationship('Member', backref='team', lazy=True)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False, default=lambda: secrets.token_hex(16))

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
    member = db.relationship('Member', backref='bookings')

# Custom login redirect handler
@app.route('/login_redirect')
def login_redirect():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin'))
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
        if not email or not password:
            flash('Email and password are required.')
            return redirect(url_for('setup_admin'))
        
        # Check password length (Werkzeug limit is 72 bytes)
        if len(password.encode('utf-8')) > 72:
            flash('Password must be 72 bytes or less. Please choose a shorter password.')
            return redirect(url_for('setup_admin'))
        
        # Let Flask-User handle password hashing
        user = User(email=email, password=user_manager.hash_password(password), role='admin', active=True, email_confirmed_at=datetime.now())
        db.session.add(user)
        db.session.commit()
        flash('Admin account created. Please log in.')
        return redirect(url_for('user.login'))
    return render_template('setup_admin.html')

# Routes
@app.route('/')
def index():
    # If already logged in, redirect to appropriate dashboard
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin'))
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
        return redirect(url_for('admin'))
    
    try:
        cleanup_date = datetime.strptime(cleanup_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format.')
        return redirect(url_for('admin'))
    
    # Validate that cleanup_date is not in the current quarter
    current_month = datetime.now().month
    current_quarter = ((current_month - 1) // 3) + 1
    cleanup_quarter = ((cleanup_date.month - 1) // 3) + 1
    if cleanup_quarter == current_quarter and cleanup_date.year == datetime.now().year:
        flash('Cannot delete slots in the current quarter.')
        return redirect(url_for('admin'))
    
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
    return redirect(url_for('admin'))

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
            msg = Message(
                'You are invited to Ministering Interview App',
                sender=app.config['MAIL_USERNAME'],
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
                'companionships_found': 0,
                'members_found': 0,
                'errors': []
            }
        
        def run_scrape():
            try:
                # Import the scraper module
                from app_scraper import scrape_ministering_data

                def progress_callback(message):
                    # Update progress store with the message
                    with progress_lock:
                        progress_store[progress_id]['message'] = message
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
        return redirect(url_for('admin'))
    return render_template('new_district.html')

@app.route('/admin/district/<int:id>')
@admin_required
def district_detail(id):
    district = District.query.get_or_404(id)
    return render_template('district_detail.html', district=district)

@app.route('/admin/district/<int:id>/team/new', methods=['GET', 'POST'])
@admin_required
def new_team(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        team = Team(district_id=id)
        db.session.add(team)
        db.session.commit()
        
        # Handle existing members
        existing_member_ids = request.form.getlist('existing_members[]')
        for member_id in existing_member_ids:
            member = Member.query.get(int(member_id))
            if member and member.team.district_id == id:
                # Cancel existing bookings
                bookings = Booking.query.filter_by(member_id=member.id).all()
                for booking in bookings:
                    db.session.delete(booking)
                # Reassign to new team
                member.team_id = team.id
        
        # Add new members
        member_names = request.form.getlist('member_name[]')
        member_phones = request.form.getlist('member_phone[]')
        member_emails = request.form.getlist('member_email[]')
        
        for name, phone, email in zip(member_names, member_phones, member_emails):
            if name:  # Only require name
                member = Member(team_id=team.id, name=name, phone=phone, email=email)
                db.session.add(member)
        
        db.session.commit()
        flash('Companionship created successfully!')
        return redirect(url_for('district_detail', id=id))
    
    # Get existing members from all districts for reassignment
    existing_members = Member.query.outerjoin(Team).outerjoin(District).order_by(District.name, Member.name).all()
    return render_template('new_team.html', district=district, existing_members=existing_members)

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
    district = member.team.district
    current_quarter = ((datetime.now().month - 1) // 3) + 1
    available_slots = InterviewSlot.query.filter_by(district_id=district.id).filter(
        InterviewSlot.date >= datetime.now().date(),
        InterviewSlot.quarter == current_quarter
    ).outerjoin(Booking).group_by(InterviewSlot.id).having(
        func.count(Booking.id) < InterviewSlot.max_slots
    ).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
    return render_template('schedule.html', member=member, slots=available_slots)

@app.route('/book/<int:slot_id>/<token>', methods=['POST'])
def book_slot(slot_id, token):
    member = Member.query.filter_by(token=token).first_or_404()
    slot = InterviewSlot.query.get_or_404(slot_id)
    
    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member.id).first()
    if existing:
        flash('You are already booked for this slot.')
        return redirect(url_for('schedule', token=token))
    
    # Check team restriction
    if slot.bookings:
        existing_team = slot.bookings[0].member.team
        if member.team != existing_team:
            flash('This slot is reserved for another team.')
            return redirect(url_for('schedule', token=token))
    
    if len(slot.bookings) < slot.max_slots:
        booking = Booking(slot_id=slot_id, member_id=member.id)
        db.session.add(booking)
        db.session.commit()
        flash('Slot booked successfully!')
    else:
        flash('Slot is full.')
    
    return redirect(url_for('schedule', token=token))

@app.route('/admin/send_notifications/<int:district_id>')
@admin_required
def send_notifications(district_id):
    district = District.query.get_or_404(district_id)
    slots = InterviewSlot.query.filter_by(district_id=district_id).all()
    
    for team in district.teams:
        for member in team.members:
            link = url_for('schedule', token=member.token, _external=True)
            # Send email
            if member.email:
                msg = Message('Interview Scheduling', sender=app.config['MAIL_USERNAME'], 
                            recipients=[member.email])
                msg.body = f'Please schedule your interview: {link}'
                mail.send(msg)
            # Send SMS (placeholder - integrate Twilio)
            if member.phone and twilio_client:
                twilio_client.messages.create(body=f'Interview link: {link}', from_=twilio_number, to=member.phone)
    
    flash('Notifications sent!')
    return redirect(url_for('district_detail', id=district_id))

@app.route('/admin/add_booking/<int:slot_id>', methods=['POST'])
@admin_required
def add_booking(slot_id):
    slot = InterviewSlot.query.get_or_404(slot_id)
    member_id = request.form['member_id']
    member = Member.query.get_or_404(member_id)
    
    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member_id).first()
    if existing:
        flash(f'{member.name} is already booked for this slot.')
    else:
        # Check team restriction
        if slot.bookings:
            existing_team = slot.bookings[0].member.team
            if member.team != existing_team:
                flash('This slot is reserved for another team.')
                return redirect(url_for('admin'))
        
        if len(slot.bookings) < slot.max_slots:
            booking = Booking(slot_id=slot_id, member_id=member_id)
            db.session.add(booking)
            db.session.commit()
            flash(f'Added {member.name} to the slot.')
        else:
            flash('Slot is full.')
    
    return redirect(url_for('admin'))

@app.route('/admin/remove_booking/<int:booking_id>', methods=['POST'])
@admin_required
def remove_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    slot = booking.slot
    member_name = booking.member.name
    db.session.delete(booking)
    db.session.commit()
    flash(f'Removed {member_name} from the slot.')
    return redirect(url_for('admin'))

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

@app.route('/admin/team/<int:team_id>/add_member', methods=['GET', 'POST'])
@admin_required
def add_member(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Get all members from all districts for reassignment
    all_members = Member.query.outerjoin(Team).outerjoin(District).order_by(District.name, Member.name).all()
    
    if request.method == 'POST':
        # Check if reassigning an existing member or creating a new one
        existing_member_id = request.form.get('existing_member_id')
        
        if existing_member_id:
            # Reassign existing member to this team
            member = Member.query.get_or_404(existing_member_id)
            
            # Remove any existing bookings
            bookings = Booking.query.filter_by(member_id=member.id).all()
            for booking in bookings:
                db.session.delete(booking)
            
            # Reassign to new team
            old_team_id = member.team_id
            member.team_id = team_id
            db.session.commit()
            flash(f'Reassigned {member.name} to this companionship!')
            return redirect(url_for('district_detail', id=team.district_id))
        else:
            # Create new member
            name = request.form['name']
            phone = request.form.get('phone', '')
            email = request.form['email']
            if name and email:
                member = Member(team_id=team_id, name=name, phone=phone, email=email)
                db.session.add(member)
                db.session.commit()
                flash(f'Added {name} to companionship!')
                return redirect(url_for('district_detail', id=team.district_id))
    
    return render_template('add_member.html', team=team, all_members=all_members)

@app.route('/admin/unassign_member/<int:member_id>', methods=['POST'])
@admin_required
def unassign_member(member_id):
    member = Member.query.get_or_404(member_id)
    district_id = member.team.district_id if member.team else None
    
    # Cancel any existing bookings
    bookings = Booking.query.filter_by(member_id=member_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    # Unassign from team
    member.team_id = None
    db.session.commit()
    flash(f'Unassigned {member.name} from companionship!')
    
    if district_id:
        return redirect(url_for('district_detail', id=district_id))
    else:
        return redirect(url_for('manage_members'))

@app.route('/admin/remove_team/<int:team_id>', methods=['POST'])
@admin_required
def remove_team(team_id):
    team = Team.query.get_or_404(team_id)
    district_id = team.district_id
    name = f"Companionship {team.id}"
    
    # Remove all members and their bookings
    for member in team.members:
        bookings = Booking.query.filter_by(member_id=member.id).all()
        for booking in bookings:
            db.session.delete(booking)
        db.session.delete(member)
    
    db.session.delete(team)
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
    members = Member.query.outerjoin(Team).outerjoin(District).order_by(District.name.nulls_last(), Team.id.nulls_last(), Member.name).all()
    districts = District.query.all()
    return render_template('manage_members.html', members=members, districts=districts)

@app.route('/admin/member/<int:member_id>/reassign', methods=['POST'])
@admin_required
def reassign_member(member_id):
    """Reassign a member to a different companionship."""
    member = Member.query.get_or_404(member_id)
    new_team_id = request.form.get('new_team_id', type=int)
    
    if not new_team_id:
        flash('Please select a companionship.')
        return redirect(url_for('manage_members'))
    
    new_team = Team.query.get_or_404(new_team_id)
    old_team_id = member.team_id
    
    # Remove any existing bookings
    bookings = Booking.query.filter_by(member_id=member_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    # Reassign to new team
    member.team_id = new_team_id
    db.session.commit()
    
    flash(f'Reassigned {member.name} to Companionship {new_team_id} in {new_team.district.name}')
    return redirect(url_for('manage_members'))

@app.route('/admin/edit_member/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        member.name = request.form['name']
        member.phone = request.form['phone']
        member.email = request.form['email']
        db.session.commit()
        flash(f'Updated {member.name}!')
        return redirect(url_for('district_detail', id=member.team.district_id))
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
                Team.query.delete()
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
                    # Create team
                    team = Team(district_id=district.id)
                    db.session.add(team)
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
                            # Reassign to new team
                            existing_member.team_id = team.id
                            member = existing_member
                        else:
                            # Create new member
                            member = Member(
                                name=member_data['name'],
                                phone=member_data['phone'],
                                email=member_data['email'],
                                team_id=team.id
                            )
                            db.session.add(member)
                        
                        # Ensure member is in the team
                        if member not in team.members:
                            team.members.append(member)
                    
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
                Team.query.delete()
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
                    # Create team
                    team = Team(district_id=district.id)
                    db.session.add(team)
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
                            # Reassign to new team
                            existing_member.team_id = team.id
                            member = existing_member
                        else:
                            # Create new member
                            member = Member(
                                name=member_data['name'],
                                phone=member_data['phone'],
                                email=member_data['email'],
                                team_id=team.id
                            )
                            db.session.add(member)
                        
                        # Ensure member is in the team
                        if member not in team.members:
                            team.members.append(member)
                    
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

@app.route('/admin/send_all_notifications')
def send_all_notifications():
    districts = District.query.all()
    total_sent = 0
    for district in districts:
        for team in district.teams:
            for member in team.members:
                link = url_for('schedule', token=member.token, _external=True)
                if member.email:
                    msg = Message('Interview Scheduling', sender=app.config['MAIL_USERNAME'], 
                                recipients=[member.email])
                    msg.body = f'Please schedule your interview: {link}'
                    mail.send(msg)
                    total_sent += 1
                if member.phone and twilio_client:
                    twilio_client.messages.create(body=f'Interview link: {link}', from_=twilio_number, to=member.phone)
                    total_sent += 1
    flash(f'Notifications sent to {total_sent} contacts!')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=8181)