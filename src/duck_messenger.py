"""
Duck-to-Duck Messenger
Intelligent messaging system between ducks with loop prevention and token budgets.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()


class DuckMessenger:
    """
    Håndterer duck-to-duck kommunikasjon med:
    - Token budget tracking
    - Loop detection
    - Smart initering-regler
    - Memory integration
    """
    
    # Budsjett og grenser
    MAX_DAILY_INITIATED = 10      # Max meldinger initiert per dag
    MAX_DAILY_TOTAL = 20           # Max totale meldinger per dag
    MAX_TOKENS_PER_MESSAGE = 500   # Max tokens per AI-generert melding
    COOLDOWN_HOURS = 2             # Timer mellom initiering
    BOREDOM_THRESHOLD = 4.5        # Kedsomhet for auto-initering
    SIMILARITY_THRESHOLD = 0.9     # Loop detection threshold
    MAX_RAPID_MESSAGES = 5         # Max meldinger før rapid check (matcher Seven)
    RAPID_TIME_WINDOW = 10         # Minutter for rapid detection (matcher Seven)
    
    # Relasjon-mapping for naturlig tale
    # Seven er Samanthas lillesøster (rampete og frekk, men aldri ufin)
    # Samantha er Seven's storesøster (ansvarlig og omsorgsfull)
    DUCK_RELATIONS = {
        'seven': 'min lillesøster Seven',      # Fra Samantha's perspektiv
        'samantha': 'min søster Samantha',     # Fra Seven's perspektiv
        'oslo-duck': 'and-vennen min i Oslo'
    }
    
    def __init__(self, db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db"):
        self.db_path = db_path
        self.duck_name = os.getenv('DUCK_NAME', 'Samantha')
        self._init_database()
    
    def _init_database(self):
        """Opprett tabell for duck message tracking"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS duck_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_duck TEXT NOT NULL,
                to_duck TEXT NOT NULL,
                message TEXT NOT NULL,
                direction TEXT NOT NULL,  -- 'sent' eller 'received'
                initiated BOOLEAN DEFAULT 0,  -- 1 hvis vi initierte
                tokens_used INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Index for quick lookups
        c.execute("CREATE INDEX IF NOT EXISTS idx_duck_messages_date ON duck_messages(DATE(timestamp))")
        c.execute("CREATE INDEX IF NOT EXISTS idx_duck_messages_from ON duck_messages(from_duck, timestamp DESC)")
        
        conn.commit()
        conn.close()
    
    def can_initiate_message(self, boredom_level: float = 0.0) -> Tuple[bool, str]:
        """
        Sjekk om vi kan initiere en melding til annen and.
        
        Returns:
            (can_send, reason)
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        today = datetime.now().date().isoformat()
        now = datetime.now()
        
        # Sjekk daglig initiering-limit
        c.execute("""
            SELECT COUNT(*) as count
            FROM duck_messages
            WHERE DATE(timestamp) = ?
            AND direction = 'sent'
            AND initiated = 1
        """, (today,))
        
        daily_initiated = c.fetchone()['count']
        if daily_initiated >= self.MAX_DAILY_INITIATED:
            conn.close()
            return False, f"Daglig initiering-limit nådd ({daily_initiated}/{self.MAX_DAILY_INITIATED})"
        
        # Sjekk totalt daglig limit
        c.execute("""
            SELECT COUNT(*) as count
            FROM duck_messages
            WHERE DATE(timestamp) = ?
        """, (today,))
        
        daily_total = c.fetchone()['count']
        if daily_total >= self.MAX_DAILY_TOTAL:
            conn.close()
            return False, f"Daglig total-limit nådd ({daily_total}/{self.MAX_DAILY_TOTAL})"
        
        # Sjekk cooldown
        cooldown_time = now - timedelta(hours=self.COOLDOWN_HOURS)
        c.execute("""
            SELECT timestamp
            FROM duck_messages
            WHERE direction = 'sent'
            AND initiated = 1
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        
        last_initiated = c.fetchone()
        if last_initiated:
            last_time = datetime.fromisoformat(last_initiated['timestamp'])
            if last_time > cooldown_time:
                hours_left = (last_time + timedelta(hours=self.COOLDOWN_HOURS) - now).total_seconds() / 3600
                conn.close()
                return False, f"Cooldown aktiv ({hours_left:.1f} timer igjen)"
        
        # Sjekk kedsomhet
        if boredom_level < self.BOREDOM_THRESHOLD:
            conn.close()
            return False, f"Ikke kjed nok (kedsomhet: {boredom_level:.1f}, trenger {self.BOREDOM_THRESHOLD})"
        
        conn.close()
        return True, "OK"
    
    def detect_loop(self, from_duck: str, new_message: str) -> bool:
        """
        Detekter om vi er i en loop med samme and.
        Sjekker kun meldinger FRA from_duck TIL oss (ikke våre egne svar).
        
        Returns:
            True hvis loop detektert
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        our_duck_name = os.getenv('DUCK_NAME', 'Samantha').lower()
        
        # Hent siste meldinger FRA from_duck TIL oss (ikke våre egne svar)
        # Ekskluder meldinger fra siste 5 sekunder (for å unngå å sammenligne med seg selv)
        cutoff_time = (datetime.now() - timedelta(seconds=5)).isoformat()
        c.execute("""
            SELECT message, timestamp
            FROM duck_messages
            WHERE from_duck = ? AND to_duck = ? AND timestamp < ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (from_duck, our_duck_name, cutoff_time, self.MAX_RAPID_MESSAGES + 1))
        
        recent = c.fetchall()
        conn.close()
        
        if len(recent) < 2:
            return False
        
        # Sjekk similarity med siste melding
        last_message = recent[0]['message']
        similarity = SequenceMatcher(None, new_message.lower(), last_message.lower()).ratio()
        
        if similarity > self.SIMILARITY_THRESHOLD:
            print(f"⚠️ Loop detektert! Similarity: {similarity:.2%}", flush=True)
            return True
        
        # Sjekk rapid messages (mange meldinger på kort tid)
        if len(recent) >= self.MAX_RAPID_MESSAGES:
            first_time = datetime.fromisoformat(recent[-1]['timestamp'])
            last_time = datetime.fromisoformat(recent[0]['timestamp'])
            time_diff = (last_time - first_time).total_seconds() / 60  # minutter
            
            if time_diff < self.RAPID_TIME_WINDOW:  # 10+ meldinger på < 3 min
                print(f"⚠️ Rapid messaging detektert! {len(recent)} meldinger på {time_diff:.1f} min", flush=True)
                return True
        
        return False
    
    def log_message(self, from_duck: str, to_duck: str, message: str, 
                   direction: str, initiated: bool = False, tokens_used: int = 0):
        """Log duck message til database"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO duck_messages 
            (from_duck, to_duck, message, direction, initiated, tokens_used, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_duck, to_duck, message, direction, int(initiated), tokens_used, 
              datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_duck_relation(self, duck_name: str) -> str:
        """
        Få naturlig relasjonsbeskrivelse for and.
        
        Returns:
            'min søster Seven', 'and-vennen min', etc.
        """
        duck_lower = duck_name.lower()
        return self.DUCK_RELATIONS.get(duck_lower, f"and-vennen min {duck_name}")
    
    def get_daily_stats(self) -> Dict:
        """Få dagens statistikk"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        c.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN initiated = 1 THEN 1 ELSE 0 END) as initiated,
                SUM(tokens_used) as tokens
            FROM duck_messages
            WHERE DATE(timestamp) = ?
        """, (today,))
        
        row = c.fetchone()
        conn.close()
        
        return {
            'total_messages': row['total'] or 0,
            'initiated': row['initiated'] or 0,
            'tokens_used': row['tokens'] or 0,
            'remaining_initiated': self.MAX_DAILY_INITIATED - (row['initiated'] or 0),
            'remaining_total': self.MAX_DAILY_TOTAL - (row['total'] or 0)
        }
    
    def format_incoming_announcement(self, from_duck: str, message: str) -> str:
        """
        Formater annonsering av innkommende melding.
        
        Returns:
            "Jeg har fått en melding fra min søster Seven: [melding]"
        """
        relation = self.get_duck_relation(from_duck)
        
        # Kort annonsering hvis meldingen er lang
        if len(message) > 100:
            preview = message[:97] + "..."
            return f"Jeg har fått en melding fra {relation}. Den sier: {preview}"
        else:
            return f"Jeg har fått en melding fra {relation}. Den sier: {message}"


# Test script
if __name__ == "__main__":
    print("🧪 Testing DuckMessenger...")
    
    messenger = DuckMessenger()
    
    # Test 1: Can initiate?
    can_send, reason = messenger.can_initiate_message(boredom_level=5.0)
    print(f"Can initiate (boredom 5.0): {can_send} - {reason}")
    
    # Test 2: Get stats
    stats = messenger.get_daily_stats()
    print(f"Daily stats: {stats}")
    
    # Test 3: Relations
    print(f"Seven relation: {messenger.get_duck_relation('seven')}")
    print(f"Samantha relation: {messenger.get_duck_relation('samantha')}")
    
    # Test 4: Announcement formatting
    announcement = messenger.format_incoming_announcement(
        'seven', 
        'Hei Samantha! Hvordan går det med deg?'
    )
    print(f"Announcement: {announcement}")
    
    print("\n✅ DuckMessenger tests complete!")
