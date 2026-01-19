"""
SMS routes for test SMS functionality.
These routes are only available in the full app version.
"""
from flask import Blueprint, request, redirect, url_for, flash

from core.models import SystemConfig
from core.utils import admin_required
from features.sms import services as sms_services

# Create blueprint - will be registered under /admin prefix
sms_bp = Blueprint('sms', __name__, url_prefix='/admin')


@sms_bp.route('/settings/test-sms', methods=['POST'])
@admin_required
def send_test_sms():
    """Send a test SMS"""
    config = SystemConfig.query.first()
    if not config:
        flash('System settings not configured yet.', 'error')
        return redirect(url_for('admin.system_settings') + '#sms')

    test_phone = request.form.get('test_phone_number', '').strip()
    if not test_phone:
        flash('Please enter a phone number to send the test SMS.', 'error')
        return redirect(url_for('admin.system_settings') + '#sms')

    try:
        if not sms_services.apply_sms_config():
            flash('SMS not configured. Please configure your SMS provider settings first.', 'error')
            return redirect(url_for('admin.system_settings') + '#sms')

        test_link = request.url_root + 'schedule/test-token-123'
        test_message = sms_services.format_sms_message(test_link)

        if not sms_services.sms_config.get('provider') or not sms_services.sms_config.get('client'):
            flash('SMS provider not configured properly.', 'error')
            return redirect(url_for('admin.system_settings') + '#sms')

        if sms_services.sms_config['provider'] == 'twilio':
            result = sms_services.sms_config['client'].messages.create(
                body=test_message, from_=sms_services.sms_config['from_number'], to=test_phone)
            flash(f'Test SMS sent successfully to {test_phone}!', 'success')
        elif sms_services.sms_config['provider'] == 'aws_sns':
            params = {'PhoneNumber': test_phone, 'Message': test_message}
            if sms_services.sms_config.get('sender_id'):
                params['MessageAttributes'] = {'AWS.SNS.SMS.SenderID': {'DataType': 'String', 'StringValue': sms_services.sms_config['sender_id']}}
            result = sms_services.sms_config['client'].publish(**params)
            flash(f'Test SMS sent successfully to {test_phone}!', 'success')
        elif sms_services.sms_config['provider'] == 'signalwire':
            try:
                print(f"SignalWire - Sending SMS from {sms_services.sms_config['from_number']} to {test_phone}")
                result = sms_services.sms_config['client'].messages.create(
                    body=test_message,
                    from_=sms_services.sms_config['from_number'],
                    to=test_phone
                )
                flash(f'Test SMS sent successfully to {test_phone}! SID: {result.sid}', 'success')
            except Exception as sw_error:
                print(f"SignalWire error details: {sw_error}")
                import traceback
                traceback.print_exc()
                raise  # Re-raise to be caught by outer exception handler
    except Exception as e:
        error_msg = str(e)
        # Add more context for common errors
        if "Expecting value" in error_msg:
            error_msg = f"SignalWire API returned invalid response. Check: 1) Space URL is correct 2) Project ID and Auth Token are valid 3) Phone number format is correct. Original error: {error_msg}"
        flash(f'Failed to send test SMS: {error_msg}', 'error')

    return redirect(url_for('admin.system_settings') + '#sms')
