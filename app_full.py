"""
Full Flask Application Entry Point
Includes all features: scraping (Selenium) and SMS (Twilio/AWS/SignalWire)
"""
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_user import UserManager, current_user
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
from flask_migrate import Migrate

# Load environment variables
load_dotenv()

# Import from core
from core.config import config as app_config
from core.models import db, User, UserInvitation, SystemConfig, IncomingSMS, District, Companionship, Member, InterviewSlot, Booking, NotificationLog, MessageTemplates
from core.shared import mail, progress_store, progress_lock
from core import services

# Import SMS services for full app
from features.sms import services as sms_services

# Create Flask app
app = Flask(__name__)
app.config.from_object(app_config['development'])

# Ensure instance directory exists for SQLite
os.makedirs('instance', exist_ok=True)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
mail.init_app(app)
user_manager = UserManager(app, db, User)

# Initialize scheduler
scheduler = BackgroundScheduler()
atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)

# Store scheduler in app for access from services
app.scheduler = scheduler

# Context processor to make 'now' and feature flags available in all templates
@app.context_processor
def inject_globals():
    return {
        'now': datetime.now(),
        'features': {
            'scraping': True,
            'sms': True
        }
    }


# Error handlers for graceful session handling
@app.errorhandler(AttributeError)
def handle_attribute_error(e):
    """Handle AttributeError from stale sessions (e.g., deleted users)"""
    error_msg = str(e)
    if 'NoneType' in error_msg and ('password' in error_msg or 'email' in error_msg or 'role' in error_msg):
        session.clear()
        flash('Your session has expired or your account no longer exists. Please log in again.', 'warning')
        return redirect(url_for('user.login'))
    raise e


@app.before_request
def check_user_validity():
    """Verify that the logged-in user still exists in the database"""
    if current_user.is_authenticated:
        try:
            _ = current_user.email
        except AttributeError:
            session.clear()
            flash('Your session is invalid. Please log in again.', 'warning')
            return redirect(url_for('user.login'))


# Register Core Blueprints
from core.routes.public import public_bp
from core.routes.admin import admin_bp
from core.routes.api import api_bp
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Register Feature Blueprints (scraping and sms)
from features.scraping.routes import scraping_bp
from features.sms.routes import sms_bp
app.register_blueprint(scraping_bp)
app.register_blueprint(sms_bp)


# Initialize database and load config
with app.app_context():
    db.create_all()
    # Add opted_out column if missing (for existing databases)
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('member')]
    if 'opted_out' not in cols:
        db.session.execute(text("ALTER TABLE member ADD COLUMN opted_out BOOLEAN NOT NULL DEFAULT 0"))
        db.session.commit()
    # Initialize message templates with defaults if not present
    MessageTemplates.get_or_create()
    services.apply_email_config()
    sms_services.apply_sms_config()  # Full app has SMS
    config_obj = SystemConfig.query.first()
    if config_obj and config_obj.reminder_enabled:
        # Use SMS-enabled reminder function in full app
        services.reschedule_reminder_job(config_obj, scheduler)
    else:
        print("Reminders are disabled by default. Scheduler not started.")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        MessageTemplates.get_or_create()
        services.apply_email_config()
        sms_services.apply_sms_config()  # Full app has SMS

        # Schedule automated reminder job
        config = SystemConfig.query.first()
        if config:
            services.reschedule_reminder_job(config, scheduler)
        else:
            print("No system config found, using default schedule (Monday 9:00 AM)")
            scheduler.add_job(
                func=services.send_booking_reminders,
                trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
                id='booking_reminders',
                name='Send booking reminders to members without appointments',
                replace_existing=True
            )

    app.run(debug=True, host='0.0.0.0', port=8181)
