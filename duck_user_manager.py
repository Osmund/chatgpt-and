#!/usr/bin/env python3
"""
User Manager for multi-user support
Håndterer session state og brukerbytte
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path

SESSION_FILE = "/tmp/duck_current_user.json"
DB_PATH = "/home/admog/Code/chatgpt-and/duck_memory.db"

class UserManager:
    """
    Håndter bruker-sessions og brukerbytte
    
    Funksjoner:
    - Hent nåværende bruker (default Osmund)
    - Bytt bruker med smart name matching
    - Timeout management (30 min)
    - Find user by name (match mot profile_facts)
    """
    
    def __init__(self, db_path: str = DB_PATH, session_file: str = SESSION_FILE):
        self.db_path = db_path
        self.session_file = session_file
        self.timeout_minutes = 30
    
    def _get_connection(self) -> sqlite3.Connection:
        """Hent database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_current_user(self) -> Dict:
        """
        Hent nåværende bruker fra session fil
        Default: Osmund hvis ingen session
        
        Returns:
            {
                'username': str,
                'display_name': str,
                'relation': str,
                'switched_at': ISO timestamp,
                'timeout_at': ISO timestamp,
                'last_activity': ISO timestamp
            }
        """
        # Les session fil
        session_path = Path(self.session_file)
        
        if not session_path.exists():
            # Default til Osmund
            return self._create_default_session()
        
        try:
            with open(self.session_file, 'r') as f:
                session = json.load(f)
            
            # Sjekk timeout
            if session.get('username') != 'Osmund':
                timeout_at = datetime.fromisoformat(session['timeout_at'])
                if datetime.now() > timeout_at:
                    # Timeout - bytt tilbake til Osmund
                    print("⏰ User timeout - bytter tilbake til Osmund", flush=True)
                    return self._create_default_session()
            
            return session
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"⚠️ Ugyldig session fil, resetter til Osmund: {e}", flush=True)
            return self._create_default_session()
    
    def _create_default_session(self) -> Dict:
        """Opprett default session for Osmund"""
        now = datetime.now()
        session = {
            'username': 'Osmund',
            'display_name': 'Osmund',
            'relation': 'owner',
            'switched_at': now.isoformat(),
            'timeout_at': (now + timedelta(days=365)).isoformat(),  # Osmund har ingen timeout
            'last_activity': now.isoformat()
        }
        self._save_session(session)
        return session
    
    def _save_session(self, session: Dict):
        """Lagre session til fil"""
        with open(self.session_file, 'w') as f:
            json.dump(session, f, indent=2)
    
    def switch_user(self, username: str, display_name: str = None, relation: str = None) -> bool:
        """
        Bytt til annen bruker
        
        Args:
            username: Brukernavn (lowercase, uten mellomrom)
            display_name: Visningsnavn (optional, default = username)
            relation: Relasjon til Osmund (optional)
        
        Returns:
            True hvis vellykket
        """
        if display_name is None:
            display_name = username
        
        now = datetime.now()
        timeout_at = now + timedelta(minutes=self.timeout_minutes)
        
        # Hvis vi bytter til Osmund, ingen timeout
        if username == 'Osmund':
            timeout_at = now + timedelta(days=365)
        
        session = {
            'username': username,
            'display_name': display_name,
            'relation': relation or 'gjest',
            'switched_at': now.isoformat(),
            'timeout_at': timeout_at.isoformat(),
            'last_activity': now.isoformat()
        }
        
        self._save_session(session)
        
        # Oppdater eller opprett bruker i database
        self._ensure_user_exists(username, display_name, relation)
        
        print(f"✅ Byttet til bruker: {display_name} ({relation})", flush=True)
        return True
    
    def _ensure_user_exists(self, username: str, display_name: str, relation: str):
        """Sørg for at bruker eksisterer i database"""
        conn = self._get_connection()
        c = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Sjekk om bruker eksisterer
        c.execute("SELECT username FROM users WHERE username = ?", (username,))
        if c.fetchone():
            # Oppdater last_active
            c.execute("""
                UPDATE users 
                SET last_active = ?
                WHERE username = ?
            """, (now, username))
        else:
            # Opprett ny bruker
            c.execute("""
                INSERT INTO users 
                (username, display_name, relation_to_primary, first_seen, last_active, total_messages, metadata)
                VALUES (?, ?, ?, ?, ?, 0, '{}')
            """, (username, display_name, relation, now, now))
        
        conn.commit()
        conn.close()
    
    def update_activity(self):
        """Oppdater last_activity timestamp"""
        session = self.get_current_user()
        session['last_activity'] = datetime.now().isoformat()
        self._save_session(session)
    
    def check_timeout(self, last_message_time: datetime = None) -> bool:
        """
        Sjekk om timeout skal trigges
        
        Args:
            last_message_time: Tidspunkt for siste melding (optional)
        
        Returns:
            True hvis timeout skal trigges
        """
        session = self.get_current_user()
        
        # Osmund har aldri timeout
        if session['username'] == 'Osmund':
            return False
        
        # Sjekk om vi har passert timeout_at
        timeout_at = datetime.fromisoformat(session['timeout_at'])
        now = datetime.now()
        
        if now < timeout_at:
            return False
        
        # Hvis siste melding er < 5 min siden, ikke timeout (aktivt i samtale)
        if last_message_time:
            if (now - last_message_time).seconds < 300:  # 5 minutter
                return False
        
        return True
    
    def get_time_until_timeout(self) -> Optional[int]:
        """
        Få sekunder til timeout
        
        Returns:
            Sekunder til timeout, eller None hvis Osmund
        """
        session = self.get_current_user()
        
        if session['username'] == 'Osmund':
            return None
        
        timeout_at = datetime.fromisoformat(session['timeout_at'])
        now = datetime.now()
        
        seconds = (timeout_at - now).total_seconds()
        return max(0, int(seconds))
    
    def find_user_by_name(self, name: str) -> Optional[Dict]:
        """
        Søk etter bruker i profile_facts eller users tabell
        
        Args:
            name: Navn å søke etter (case-insensitive)
        
        Returns:
            {
                'username': str,
                'display_name': str,
                'relation': str,
                'matched_key': str (hvis funnet i profile_facts)
            }
            eller None hvis ikke funnet
        """
        name_lower = name.lower().strip()
        
        # 1. Søk i users tabell først
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT username, display_name, relation_to_primary
            FROM users
            WHERE LOWER(display_name) = ? OR LOWER(username) = ?
        """, (name_lower, name_lower))
        
        row = c.fetchone()
        if row:
            conn.close()
            return {
                'username': row['username'],
                'display_name': row['display_name'],
                'relation': row['relation_to_primary'],
                'matched_key': None
            }
        
        # 2. Søk i profile_facts
        # Sjekk alle *_name keys
        c.execute("""
            SELECT key, value, topic
            FROM profile_facts
            WHERE key LIKE '%_name' AND LOWER(value) = ?
        """, (name_lower,))
        
        row = c.fetchone()
        conn.close()
        
        if row:
            # Ekstraher relasjon fra key
            relation = self._extract_relation_from_key(row['key'])
            
            # Bruk value som display_name, lowercase som username
            return {
                'username': name_lower.replace(' ', '_'),
                'display_name': row['value'],
                'relation': relation,
                'matched_key': row['key']
            }
        
        return None
    
    def _extract_relation_from_key(self, key: str) -> str:
        """
        Ekstraher relasjon fra fact key
        
        Examples:
            'sister_1_name' → 'søster'
            'father_name' → 'far'
            'sister_2_husband_name' → 'svoger'
            'mother_name' → 'mor/mamma'
        """
        key_lower = key.lower()
        
        if 'sister' in key_lower:
            if 'husband' in key_lower or 'spouse' in key_lower:
                return 'svoger'
            return 'søster'
        elif 'brother' in key_lower:
            if 'wife' in key_lower or 'spouse' in key_lower:
                return 'svigerinne'
            return 'bror'
        elif 'father' in key_lower:
            return 'far'
        elif 'mother' in key_lower:
            return 'mor'
        elif 'maternal_grandmother' in key_lower:
            return 'bestemor (mors side)'
        elif 'paternal_grandmother' in key_lower:
            return 'bestemor (fars side)'
        elif 'maternal_grandfather' in key_lower:
            return 'bestefar (mors side)'
        elif 'paternal_grandfather' in key_lower:
            return 'bestefar (fars side)'
        elif 'child' in key_lower:
            if 'sister' in key_lower:
                return 'niese/nevø'
            return 'barn'
        else:
            return 'familie'
    
    def get_all_users(self) -> List[Dict]:
        """Hent alle brukere fra database"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT username, display_name, relation_to_primary, 
                   first_seen, last_active, total_messages
            FROM users
            ORDER BY last_active DESC
        """)
        
        users = []
        for row in c.fetchall():
            users.append({
                'username': row['username'],
                'display_name': row['display_name'],
                'relation': row['relation_to_primary'],
                'first_seen': row['first_seen'],
                'last_active': row['last_active'],
                'total_messages': row['total_messages']
            })
        
        conn.close()
        return users
    
    def increment_message_count(self, username: str):
        """Øk message count for bruker"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE users
            SET total_messages = total_messages + 1,
                last_active = ?
            WHERE username = ?
        """, (datetime.now().isoformat(), username))
        
        conn.commit()
        conn.close()


if __name__ == "__main__":
    # Test UserManager
    print("Testing UserManager...")
    print()
    
    manager = UserManager()
    
    # Test 1: Get current user (should be Osmund)
    current = manager.get_current_user()
    print(f"✅ Current user: {current['display_name']} ({current['relation']})")
    
    # Test 2: Find user by name
    found = manager.find_user_by_name("Miriam")
    if found:
        print(f"✅ Found user: {found['display_name']} ({found['relation']})")
        print(f"   Matched key: {found['matched_key']}")
    else:
        print("⚠️  Miriam not found in database")
    
    # Test 3: Switch user
    if found:
        manager.switch_user(
            username=found['username'],
            display_name=found['display_name'],
            relation=found['relation']
        )
        
        current = manager.get_current_user()
        print(f"✅ Switched to: {current['display_name']}")
        
        timeout_sec = manager.get_time_until_timeout()
        print(f"   Timeout in: {timeout_sec // 60} minutes")
    
    # Test 4: Switch back to Osmund
    manager.switch_user('Osmund', 'Osmund', 'owner')
    current = manager.get_current_user()
    print(f"✅ Switched back to: {current['display_name']}")
    
    # Test 5: Get all users
    users = manager.get_all_users()
    print(f"\n📋 All users ({len(users)}):")
    for user in users:
        print(f"   - {user['display_name']} ({user['relation']}): {user['total_messages']} messages")
    
    print("\n✅ All tests passed!")
