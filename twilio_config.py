from twilio.rest import Client
import os

# Twilio configuration
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_number = os.environ.get('TWILIO_NUMBER')

if account_sid and auth_token:
    twilio_client = Client(account_sid, auth_token)
else:
    twilio_client = None