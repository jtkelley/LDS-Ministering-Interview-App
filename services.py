"""
Service functions for email, SMS, and notifications.
"""
from flask import url_for, current_app
from flask_mail import Message
from datetime import datetime

# Global SMS client storage
sms_config = {
    'provider': None,
    'client': None,
    'from_number': None
}


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


def apply_sms_config():
    """Load SMS config from database and initialize SMS client"""
    from models import SystemConfig
    global sms_config

    try:
        config = SystemConfig.query.first()
        if not config:
            return False

        decrypted = config.decrypt_fields()
        provider = decrypted.get('sms_provider', 'twilio')

        if provider == 'twilio':
            account_sid = decrypted.get('twilio_account_sid')
            auth_token = decrypted.get('twilio_auth_token')
            phone_number = decrypted.get('twilio_phone_number')

            if account_sid and auth_token and phone_number:
                from twilio.rest import Client
                sms_config['provider'] = 'twilio'
                sms_config['client'] = Client(account_sid, auth_token)

                # Ensure phone number is in E.164 format (+1XXXXXXXXXX)
                if not phone_number.startswith('+'):
                    # Remove any non-digit characters
                    digits_only = ''.join(filter(str.isdigit, phone_number))
                    # Add +1 for US/Canada if not present
                    if len(digits_only) == 10:
                        phone_number = '+1' + digits_only
                    elif len(digits_only) == 11 and digits_only.startswith('1'):
                        phone_number = '+' + digits_only
                    else:
                        phone_number = '+' + digits_only

                sms_config['from_number'] = phone_number
                return True

        elif provider == 'aws_sns':
            access_key = decrypted.get('aws_access_key_id')
            secret_key = decrypted.get('aws_secret_access_key')
            region = decrypted.get('aws_region')

            if access_key and secret_key and region:
                import boto3
                sms_config['provider'] = 'aws_sns'
                sms_config['client'] = boto3.client(
                    'sns',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region
                )
                sms_config['sender_id'] = decrypted.get('aws_sns_sender_id', '')
                return True

        elif provider == 'signalwire':
            project_id = decrypted.get('signalwire_project_id')
            auth_token = decrypted.get('signalwire_auth_token')
            space_url = decrypted.get('signalwire_space_url')
            phone_number = decrypted.get('signalwire_phone_number')

            if project_id and auth_token and space_url and phone_number:
                from signalwire.rest import Client as SignalWireClient
                sms_config['provider'] = 'signalwire'

                # Ensure space_url doesn't have https:// prefix (SignalWire client adds it)
                if space_url.startswith('https://'):
                    space_url = space_url.replace('https://', '')
                elif space_url.startswith('http://'):
                    space_url = space_url.replace('http://', '')

                print(f"Initializing SignalWire client:")
                print(f"  Project ID: {project_id[:8]}...")
                print(f"  Auth Token: {auth_token[:8]}...")
                print(f"  Space URL: {space_url}")

                try:
                    sms_config['client'] = SignalWireClient(project_id, auth_token, signalwire_space_url=space_url)
                    print(f"  ✓ SignalWire client initialized successfully")
                except Exception as init_error:
                    print(f"  ✗ Failed to initialize SignalWire client: {init_error}")
                    raise

                # Ensure phone number is in E.164 format (+1XXXXXXXXXX)
                if not phone_number.startswith('+'):
                    # Remove any non-digit characters
                    digits_only = ''.join(filter(str.isdigit, phone_number))
                    # Add +1 for US/Canada if not present
                    if len(digits_only) == 10:
                        phone_number = '+1' + digits_only
                    elif len(digits_only) == 11 and digits_only.startswith('1'):
                        phone_number = '+' + digits_only
                    else:
                        phone_number = '+' + digits_only

                sms_config['from_number'] = phone_number
                return True

    except Exception as e:
        print(f"Error loading SMS config: {e}")

    return False


def format_sms_message(link, member=None):
    """
    Format SMS message based on system configuration
    Returns formatted message string
    """
    from models import SystemConfig

    config = SystemConfig.query.first()
    if not config:
        # Fallback if no config
        return f"Ministering Interview\n\nPlease schedule your interview: {link}"

    # Base message
    message = "Ministering Interview\n\n"
    message += f"Please schedule your interview: {link}\n\n"

    # Add do-not-reply warning if using 1-way mode
    if config.sms_mode == 'one_way':
        message += "Do not reply to this text.\n\n"

        # Add personal contact if enabled
        if config.sms_contact_enabled and config.sms_contact_name and config.sms_contact_phone:
            message += f"Questions? Call/text {config.sms_contact_name} at {config.sms_contact_phone}"

    return message


def send_sms(to_number, message):
    """Send SMS using configured provider"""
    global sms_config

    if not sms_config.get('provider') or not sms_config.get('client'):
        print("SMS not configured")
        return False

    try:
        if sms_config['provider'] == 'twilio':
            sms_config['client'].messages.create(
                body=message,
                from_=sms_config['from_number'],
                to=to_number
            )
            return True

        elif sms_config['provider'] == 'aws_sns':
            params = {
                'PhoneNumber': to_number,
                'Message': message
            }
            if sms_config.get('sender_id'):
                params['MessageAttributes'] = {
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': sms_config['sender_id']
                    }
                }
            sms_config['client'].publish(**params)
            return True

        elif sms_config['provider'] == 'signalwire':
            sms_config['client'].messages.create(
                body=message,
                from_=sms_config['from_number'],
                to=to_number
            )
            return True

    except Exception as e:
        print(f"Error sending SMS: {e}")
        return False

    return False


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

            # Load email and SMS configs
            sender_email = apply_email_config()
            apply_sms_config()

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

            # Send notifications
            email_sent = 0
            sms_sent = 0
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

                # Send SMS if enabled
                if member.can_receive_sms():
                    try:
                        sms_message = format_sms_message(link, member)
                        if send_sms(member.phone, sms_message):
                            sms_sent += 1
                    except Exception as e:
                        errors.append(f"SMS to {member.phone}: {str(e)}")

            print(f"Booking reminders sent: {email_sent} emails, {sms_sent} SMS")
            if errors:
                print(f"Errors: {errors}")

        except Exception as e:
            print(f"Error in send_booking_reminders job: {str(e)}")
