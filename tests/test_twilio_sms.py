#!/usr/bin/env python3
"""
Quick test script for Twilio SMS sending
"""
import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Your Twilio credentials from environment
ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
FROM_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# Validate credentials
if not all([ACCOUNT_SID, AUTH_TOKEN, FROM_NUMBER]):
    print("❌ Missing Twilio credentials in .env file")
    print("Required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
    exit(1)

# Your mobile number (Norwegian)
TO_NUMBER = input("Enter your mobile number (e.g., +4712345678): ").strip()

# Validate number format
if not TO_NUMBER.startswith('+'):
    print("❌ Number must start with + (e.g., +4712345678)")
    exit(1)

# Create Twilio client
print(f"\n📞 Connecting to Twilio...")
client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Send test SMS
print(f"📨 Sending SMS from {FROM_NUMBER} to {TO_NUMBER}...")

try:
    message = client.messages.create(
        body='Kvakk! 🦆 Dette er en testmelding fra Samantha via Twilio!',
        from_=FROM_NUMBER,
        to=TO_NUMBER
    )
    
    print(f"✅ SMS sent successfully!")
    print(f"   Message SID: {message.sid}")
    print(f"   Status: {message.status}")
    print(f"\n🎉 Check your phone - you should receive the SMS within seconds!")
    
except Exception as e:
    print(f"❌ Error sending SMS: {e}")
