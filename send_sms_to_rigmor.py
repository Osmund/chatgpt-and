#!/usr/bin/env python3
"""Send en ordentlig SMS til Rigmor som svar på hilsenen"""

import sys
import os
sys.path.insert(0, '/home/admog/Code/chatgpt-and')

from dotenv import load_dotenv
load_dotenv()

import requests
import sqlite3
from datetime import datetime

# Hent Rigmors kontaktinfo
conn = sqlite3.connect('/home/admog/Code/chatgpt-and/duck_memory.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT * FROM sms_contacts WHERE name = 'Rigmor'")
rigmor = dict(c.fetchone())
conn.close()

# Generer AI-respons direkte med OpenAI
incoming_message = "Jeg skal hilse til deg fra venninnene mine!"
current_date = datetime.now().strftime('%d. %B %Y')

prompt = f"""Du er Anda, en snakkende and.
I dag er det {current_date}.
Kontakt: Rigmor (venn)

Ny melding fra Rigmor: {incoming_message}

VIKTIG: Svar på hilsenen fra venninnene hennes på en varm og hyggelig måte. Hils tilbake!
Svar kort og naturlig (maks 155 tegn). Bruk emoji 🦆 hvis passende."""

response = requests.post(
    'https://api.openai.com/v1/chat/completions',
    headers={'Authorization': f'Bearer {os.getenv("OPENAI_API_KEY")}'},
    json={
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.9
    }
)

if response.status_code == 200:
    ai_message = response.json()['choices'][0]['message']['content'].strip()
    print(f"✅ AI genererte: {ai_message}")
    
    # Send SMS via Twilio
    from src.duck_sms import SMSManager
    sms_manager = SMSManager()
    result = sms_manager.send_sms(rigmor['phone'], ai_message)
    
    if result['status'] == 'sent':
        print(f"✅ SMS sendt!")
        
        # Lagre til database
        conn = sqlite3.connect('/home/admog/Code/chatgpt-and/duck_memory.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO sms_history (contact_id, direction, message, timestamp)
            VALUES ((SELECT id FROM sms_contacts WHERE name = 'Rigmor'), 'outbound', ?, ?)
        """, (ai_message, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        print("✅ Lagret i database")
    else:
        print(f"❌ SMS feilet: {result.get('error')}")
else:
    print(f"❌ AI feilet: {response.status_code} - {response.text}")
