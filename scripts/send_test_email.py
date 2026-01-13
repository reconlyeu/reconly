#!/usr/bin/env python3
"""Quick test script to verify email configuration."""
import sys
import io
import os
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Load environment variables
load_dotenv()

from reconly_core.services.email_service import EmailService

# Test data - create a simple digest
test_digests = [
    {
        'title': 'Test Digest Email',
        'summary': 'This is a test email to verify your Reconly email configuration is working correctly. If you receive this, everything is set up properly!',
        'url': 'https://github.com/reconly/reconly',
        'source_type': 'test',
        'language': 'en',
        'tags': ['test', 'email-setup']
    }
]

print("=" * 80)
print("Reconly Email Configuration Test")
print("=" * 80)
print()

# Check configuration
smtp_host = os.getenv('SMTP_HOST')
smtp_user = os.getenv('SMTP_USER')
smtp_password = os.getenv('SMTP_PASSWORD')
recipient = os.getenv('EMAIL_RECIPIENT')

print("Configuration Status:")
print(f"  SMTP Host: {smtp_host or '[NOT SET]'}")
print(f"  SMTP User: {smtp_user or '[NOT SET]'}")
print(f"  SMTP Password: {'[SET]' if smtp_password else '[NOT SET]'}")
print(f"  Recipient: {recipient or '[NOT SET]'}")
print()

if not all([smtp_host, smtp_user, smtp_password, recipient]):
    print("❌ ERROR: Email configuration incomplete!")
    print()
    print("Please edit .env file and set:")
    print("  - SMTP_USER (your Gmail address)")
    print("  - SMTP_PASSWORD (your Gmail App Password)")
    print("  - EMAIL_RECIPIENT (where to send digests)")
    print()
    print("For Gmail App Password:")
    print("  1. Go to: https://myaccount.google.com/apppasswords")
    print("  2. Create an App Password for 'Mail'")
    print("  3. Copy the 16-character password to .env")
    sys.exit(1)

# Initialize email service
email_service = EmailService()

print(f"Sending test email to: {recipient}")
print()

# Send test email
success = email_service.send_digest_email(
    to_email=recipient,
    digests=test_digests,
    date=datetime.now(),
    language='en'
)

if success:
    print("=" * 80)
    print("✅ SUCCESS! Test email sent.")
    print("=" * 80)
    print()
    print(f"Check your inbox at {recipient}")
    print()
    print("Next steps:")
    print("  - Send recent digests: python run_reconly.py --send-digest")
    print("  - Send specific tags: python run_reconly.py --send-digest --tags tech")
    print("  - Send to different email: python run_reconly.py --send-digest --email other@example.com")
else:
    print("=" * 80)
    print("❌ FAILED to send email")
    print("=" * 80)
    print()
    print("Common issues:")
    print("  1. Gmail App Password not set (must be 16 characters, no spaces)")
    print("  2. Wrong SMTP settings (default: smtp.gmail.com:587)")
    print("  3. 2-Factor Authentication not enabled on Gmail")
    print()
    print("Check the error message above for details.")
    sys.exit(1)
