"""
Duck Reminders & Alarm System
Påminnelser og vekkeklokke for Samantha.

Funksjoner:
- Sett påminnelser med naturlig språk ("om 30 minutter", "klokka 14")
- Vekkeklokke som vekker anda fra sleep mode
- Gjentakende påminnelser (valgfritt)
- Persistent lagring i SQLite
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from src.duck_database import get_db

load_dotenv()

# Reminder types
REMINDER_TYPE_NORMAL = 'reminder'
REMINDER_TYPE_ALARM = 'alarm'


class ReminderManager:
    """
    Håndterer påminnelser og vekkeklokker.
    
    Påminnelser lagres i SQLite og sjekkes periodisk.
    Alarmer vekker anda fra sleep mode.
    """
    
    def __init__(self, db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db"):
        self.db_path = db_path
        self.db = get_db(db_path)
        self._init_database()
    
    def _init_database(self):
        """Opprett reminders-tabell hvis den ikke finnes"""
        conn = self.db.connection()
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reminder_type TEXT NOT NULL DEFAULT 'reminder',
                user_name TEXT DEFAULT 'Osmund',
                status TEXT DEFAULT 'pending',
                announced_at TEXT
            )
        """)
        
        conn.commit()
        print("✅ Reminders database initialized", flush=True)
    
    def set_reminder(self, message: str, remind_at: datetime, 
                     reminder_type: str = REMINDER_TYPE_NORMAL,
                     user_name: str = 'Osmund') -> Dict:
        """
        Sett en ny påminnelse eller alarm.
        
        Args:
            message: Påminnelsestekst
            remind_at: Tidspunkt for påminnelsen
            reminder_type: 'reminder' eller 'alarm'
            user_name: Brukerens navn
            
        Returns:
            {'status': 'set', 'id': int, 'remind_at': str, 'type': str}
        """
        conn = self.db.connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO reminders (message, remind_at, created_at, reminder_type, user_name, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (message, remind_at.isoformat(), datetime.now().isoformat(), 
              reminder_type, user_name))
        
        reminder_id = c.lastrowid
        conn.commit()
        
        type_str = "⏰ Alarm" if reminder_type == REMINDER_TYPE_ALARM else "🔔 Påminnelse"
        print(f"{type_str} satt: '{message}' kl {remind_at.strftime('%H:%M')}", flush=True)
        
        return {
            'status': 'set',
            'id': reminder_id,
            'remind_at': remind_at.isoformat(),
            'remind_at_formatted': remind_at.strftime('%H:%M'),
            'type': reminder_type,
            'message': message
        }
    
    def get_due_reminders(self) -> List[Dict]:
        """
        Hent alle påminnelser som er forfalt (tid er passert).
        
        Returns:
            Liste med forfallene påminnelser
        """
        conn = self.db.connection()
        c = conn.cursor()
        
        now = datetime.now().isoformat()
        
        c.execute("""
            SELECT id, message, remind_at, reminder_type, user_name
            FROM reminders
            WHERE status = 'pending' AND remind_at <= ?
            ORDER BY remind_at ASC
        """, (now,))
        
        reminders = [dict(row) for row in c.fetchall()]
        
        return reminders
    
    def mark_announced(self, reminder_id: int):
        """Marker en påminnelse som annonsert"""
        conn = self.db.connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE reminders 
            SET status = 'announced', announced_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), reminder_id))
        
        conn.commit()
    
    def cancel_reminder(self, reminder_id: int) -> Dict:
        """Avbryt en påminnelse"""
        conn = self.db.connection()
        c = conn.cursor()
        
        c.execute("SELECT message, reminder_type FROM reminders WHERE id = ? AND status = 'pending'", (reminder_id,))
        row = c.fetchone()
        
        if not row:
            return {'status': 'not_found', 'message': f'Fant ingen pending påminnelse med id {reminder_id}'}
        
        c.execute("UPDATE reminders SET status = 'cancelled' WHERE id = ?", (reminder_id,))
        conn.commit()
        
        return {'status': 'cancelled', 'id': reminder_id, 'message': row[0]}
    
    def get_pending_reminders(self) -> List[Dict]:
        """Hent alle ventende påminnelser"""
        conn = self.db.connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT id, message, remind_at, reminder_type, user_name
            FROM reminders
            WHERE status = 'pending'
            ORDER BY remind_at ASC
        """)
        
        reminders = [dict(row) for row in c.fetchall()]
        
        return reminders
    
    def format_announcement(self, reminder: Dict) -> str:
        """
        Formater påminnelse som talemelding.
        
        Args:
            reminder: Dict med reminder-data
            
        Returns:
            Formattert tekst for TTS
        """
        message = reminder['message']
        user_name = reminder.get('user_name', 'Osmund')
        reminder_type = reminder.get('reminder_type', REMINDER_TYPE_NORMAL)
        
        if reminder_type == REMINDER_TYPE_ALARM:
            return f"God morgen {user_name}! Det er på tide å stå opp! {message}"
        else:
            return f"Hei {user_name}! Huskelapp fra meg: {message}"
    
    def parse_time_description(self, time_desc: str) -> Optional[datetime]:
        """
        Parse naturlig tidsbeskrivelse til datetime.
        
        Eksempler:
            "om 30 minutter" → now + 30 min
            "om 1 time" → now + 1 hour
            "klokka 14" → today 14:00
            "klokka 14:30" → today 14:30
            "i morgen klokka 7" → tomorrow 07:00
            
        Returns:
            datetime eller None
        """
        import re
        now = datetime.now()
        time_lower = time_desc.lower().strip()
        
        # "om X minutter/minutt"
        match = re.search(r'om\s+(\d+)\s+minutt', time_lower)
        if match:
            minutes = int(match.group(1))
            return now + timedelta(minutes=minutes)
        
        # "om X timer/time"
        match = re.search(r'om\s+(\d+)\s+time', time_lower)
        if match:
            hours = int(match.group(1))
            return now + timedelta(hours=hours)
        
        # "om en halv time"
        if 'halv time' in time_lower:
            return now + timedelta(minutes=30)
        
        # "om X sekunder/sekund"
        match = re.search(r'om\s+(\d+)\s+sekund', time_lower)
        if match:
            seconds = int(match.group(1))
            return now + timedelta(seconds=seconds)
        
        # "i morgen klokka/kl HH:MM" eller "i morgen klokka/kl HH"
        match = re.search(r'i\s+morgen\s+(?:klokk?a?|kl\.?)\s*(\d{1,2})(?::(\d{2}))?', time_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # "klokka/kl HH:MM" eller "klokka/kl HH"
        match = re.search(r'(?:klokk?a?|kl\.?)\s*(\d{1,2})(?::(\d{2}))?', time_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # Hvis tiden allerede er passert i dag, sett den til i morgen
            if target <= now:
                target += timedelta(days=1)
            return target
        
        return None


# Test script
if __name__ == "__main__":
    print("🧪 Testing ReminderManager...")
    
    rm = ReminderManager()
    
    # Test parse_time_description
    tests = [
        "om 30 minutter",
        "om 1 time",
        "klokka 14",
        "klokka 14:30",
        "i morgen klokka 7",
        "om en halv time",
        "kl 8",
    ]
    
    for t in tests:
        result = rm.parse_time_description(t)
        if result:
            print(f"  '{t}' → {result.strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"  '{t}' → FAILED TO PARSE")
    
    # Test set reminder
    remind_at = datetime.now() + timedelta(minutes=5)
    result = rm.set_reminder("Test påminnelse", remind_at)
    print(f"\nSet reminder: {result}")
    
    # Test pending
    pending = rm.get_pending_reminders()
    print(f"Pending reminders: {len(pending)}")
    
    # Test alarm
    alarm_at = datetime.now() + timedelta(hours=8)
    result = rm.set_reminder("Stå opp!", alarm_at, reminder_type=REMINDER_TYPE_ALARM)
    print(f"Set alarm: {result}")
