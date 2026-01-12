"""
Service functions for email and notifications (minimal - no SMS).
"""
from flask import url_for, current_app
from flask_mail import Message
from datetime import datetime


def apply_email_config():
    """Load email config from database and apply to Flask app config"""
    from models import SystemConfig
    from shared import mail

    try:
        config = SystemConfig.query.first()
        if config:
            decrypted = config.decrypt_fields()
            current_app.config['MAIL_SERVER'] = decrypted['mail_server']
            current_app.config['MAIL_PORT'] = decrypted['mail_port']
            current_app.config['MAIL_USE_TLS'] = decrypted['mail_use_tls']
            current_app.config['MAIL_USERNAME'] = decrypted['mail_username']
            current_app.config['MAIL_PASSWORD'] = decrypted['mail_password']
            current_app.config['MAIL_DEFAULT_SENDER'] = decrypted['mail_from_email']

            # Reinitialize mail with new config
            mail.init_app(current_app)

            print(f"Email configured: {decrypted['mail_server']}:{decrypted['mail_port']} (TLS: {decrypted['mail_use_tls']})")
            return decrypted['mail_from_email']
    except Exception as e:
        print(f"Error loading email config: {e}")
        import traceback
        traceback.print_exc()
    return None


def reschedule_reminder_job(config, scheduler=None):
    """Reschedule the reminder job based on config settings"""
    from apscheduler.triggers.cron import CronTrigger

    # Get scheduler from app if not provided
    if scheduler is None:
        from flask import current_app
        scheduler = current_app.scheduler

    try:
        # Remove existing job if it exists
        if scheduler.get_job('booking_reminders'):
            scheduler.remove_job('booking_reminders')

        # Only add job if reminders are enabled
        if config.reminder_enabled:
            # Map day of week to cron format (0=Mon in our DB, mon in cron)
            day_map = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            day_of_week = day_map[config.reminder_day_of_week]

            scheduler.add_job(
                func=send_booking_reminders,
                trigger=CronTrigger(
                    day_of_week=day_of_week,
                    hour=config.reminder_hour,
                    minute=config.reminder_minute
                ),
                id='booking_reminders',
                name='Send booking reminders to members without appointments',
                replace_existing=True
            )
            print(f"Reminder job rescheduled: {day_of_week.capitalize()} at {config.reminder_hour}:{config.reminder_minute:02d}")
        else:
            print("Reminder job disabled")
    except Exception as e:
        print(f"Error rescheduling reminder job: {e}")


def send_booking_reminders():
    """
    Scheduled job: Send reminders to members who haven't booked for current quarter.
    Schedule configured in System Settings.
    """
    from models import Member, Companionship, District
    from flask_mail import Mail

    # Get Flask app and mail from current context
    app = current_app._get_current_object()
    mail = Mail(app)

    with app.app_context():
        try:
            # Get current quarter
            today = datetime.now().date()
            current_quarter = ((today.month - 1) // 3) + 1
            current_year = today.year

            # Load email config
            sender_email = apply_email_config()

            if not sender_email:
                print("Email not configured, skipping reminder job")
                return

            # Find all members without bookings for current quarter
            members_without_bookings = []
            all_members = Member.query.join(Companionship).join(District).all()

            for member in all_members:
                if not member.has_booking_for_quarter(current_quarter, current_year):
                    members_without_bookings.append(member)

            print(f"Found {len(members_without_bookings)} members without bookings for Q{current_quarter} {current_year}")

            # Send email notifications
            email_sent = 0
            errors = []

            for member in members_without_bookings:
                link = url_for('schedule', token=member.token, _external=True)

                # Send email
                if member.email:
                    try:
                        msg = Message(
                            f'Reminder: Schedule Your Interview for Q{current_quarter}',
                            sender=sender_email,
                            recipients=[member.email]
                        )
                        msg.body = f'''Hello {member.name},

This is a reminder to schedule your ministering interview for Quarter {current_quarter} of {current_year}.

Click the link below to view available times and book your interview:
{link}

If your companion has already booked, you'll see their appointment highlighted so you can join them.

Thank you!
'''
                        msg.html = f'''<p>Hello {member.name},</p>
<p>This is a reminder to schedule your ministering interview for <strong>Quarter {current_quarter} of {current_year}</strong>.</p>
<p><a href="{link}">Click here to view available times and book your interview</a></p>
<p>If your companion has already booked, you'll see their appointment highlighted so you can join them.</p>
<p>Thank you!</p>
'''
                        mail.send(msg)
                        email_sent += 1
                    except Exception as e:
                        errors.append(f"Email to {member.email}: {str(e)}")

            print(f"Booking reminders sent: {email_sent} emails")
            if errors:
                print(f"Errors: {errors}")

        except Exception as e:
            print(f"Error in send_booking_reminders job: {str(e)}")
