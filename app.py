

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

# Import config, models, utils, services, shared
from config import config as app_config
from models import db, User, UserInvitation, SystemConfig, IncomingSMS, District, Companionship, Member, InterviewSlot, Booking, NotificationLog
from utils import EncryptionHelper, admin_required, group_results_by_district
import services
from shared import mail, progress_store, progress_lock

# Create Flask app
app = Flask(__name__)
app.config.from_object(app_config['development'])

# Ensure instance directory exists for SQLite
os.makedirs('instance', exist_ok=True)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
mail.init_app(app)  # mail imported from shared.py
user_manager = UserManager(app, db, User)

# Initialize scheduler (disabled by default)
scheduler = BackgroundScheduler()
atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)

# Store scheduler in app for access from services
app.scheduler = scheduler

# Context processor to make 'now' available in all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}


# Error handlers for graceful session handling
@app.errorhandler(AttributeError)
def handle_attribute_error(e):
    """Handle AttributeError from stale sessions (e.g., deleted users)"""
    error_msg = str(e)
    # Check if it's a user-related AttributeError (common when user is deleted but session exists)
    if 'NoneType' in error_msg and ('password' in error_msg or 'email' in error_msg or 'role' in error_msg):
        session.clear()
        flash('Your session has expired or your account no longer exists. Please log in again.', 'warning')
        return redirect(url_for('user.login'))
    # Re-raise if it's a different AttributeError
    raise e


@app.before_request
def check_user_validity():
    """Verify that the logged-in user still exists in the database"""
    if current_user.is_authenticated:
        try:
            # Try to access a user attribute to trigger error if user is None/deleted
            _ = current_user.email
        except AttributeError:
            # User object is invalid, clear session and redirect
            session.clear()
            flash('Your session is invalid. Please log in again.', 'warning')
            return redirect(url_for('user.login'))


# Register Blueprints
from routes_public import public_bp
from routes_admin import admin_bp
from routes_api import api_bp
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Initialize database and load config
with app.app_context():
    db.create_all()
    services.apply_email_config()
    services.apply_sms_config()
    config_obj = SystemConfig.query.first()
    if config_obj and config_obj.reminder_enabled:
        services.reschedule_reminder_job(config_obj, scheduler)
    else:
        print("Reminders are disabled by default. Scheduler not started.")

# ============================================================================
# PUBLIC ROUTES MOVED TO routes_public.py
# The following routes have been moved to the public_bp blueprint:
# - /login_redirect
# - /setup_admin
# - /clear-session
# - / (index)
# - /dashboard (interviewer_dashboard)
# - /user/accept-invite/<token>
# - /schedule/<token>
# - /book/<int:slot_id>/<token>
# - /unbook/<token>
# ============================================================================

# Flask-User provides login/logout routes automatically

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Load email config from database if it exists (for Flask-User compatibility)
        services.apply_email_config()
        # Load SMS config from database
        services.apply_sms_config()
        # UserManager is already initialized at module level (for gunicorn compatibility)

        # Schedule automated reminder job based on database settings
        config = SystemConfig.query.first()
        if config:
            services.reschedule_reminder_job(config, scheduler)
        else:
            # Default schedule if no config exists
            print("No system config found, using default schedule (Monday 9:00 AM)")
            scheduler.add_job(
                func=services.send_booking_reminders,
                trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
                id='booking_reminders',
                name='Send booking reminders to members without appointments',
                replace_existing=True
            )

    app.run(debug=True, host='0.0.0.0', port=8181)