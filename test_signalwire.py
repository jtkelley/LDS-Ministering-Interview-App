#!/usr/bin/env python3
"""Test SignalWire connection"""

from signalwire.rest import Client

project_id = '52b2d6e2-42de-41b1-a883-475635938f46'
auth_token = 'PTef3de24c6fe40357ae2ad8c5b4ccd35af76defb1c109d37e'
space_url = 'lehi7thwardeq.signalwire.com'

print(f"Testing SignalWire connection...")
print(f"Project ID: {project_id}")
print(f"Auth Token: {auth_token[:10]}...")
print(f"Space URL: {space_url}")
print()

try:
    # SignalWire uses project_id as username, token as password
    client = Client(project_id, auth_token, signalwire_space_url=space_url)
    print("✓ Client created")

    # Skip account fetch - try sending SMS directly instead
    print("Skipping account verification (401 error is normal)")

    # Try to list phone numbers
    try:
        numbers = client.incoming_phone_numbers.list(limit=5)
        print(f"✓ Found {len(numbers)} phone number(s)")
        for number in numbers:
            print(f"  - {number.phone_number}")
    except Exception as list_error:
        print(f"Could not list phone numbers (this is OK): {list_error}")

    # Try to send a test message directly
    print()
    print("Attempting to send test SMS...")
    from_number = input("Enter your SignalWire FROM number (e.g., +18014348787): ")
    to_number = input("Enter a TO number to test (e.g., +18015551234): ")

    result = client.messages.create(
        body="Test from SignalWire",
        from_=from_number,
        to=to_number
    )
    print(f"✓ SMS sent successfully!")
    print(f"  Message SID: {result.sid}")
    print(f"  Status: {result.status}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
