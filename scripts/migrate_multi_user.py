#!/usr/bin/env python3
"""
Database migration for multi-user support
Legger til user_name kolonner og users tabell
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = "/home/admog/Code/chatgpt-and/duck_memory.db"

def migrate_database():
    """Legg til multi-user support i eksisterende database"""
    print("🦆 ChatGPT Duck - Multi-User Migration")
    print("="*60)
    print()
    
    if not Path(DB_PATH).exists():
        print(f"❌ Database ikke funnet: {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("📊 Database statistikk (før migration):")
    c.execute("SELECT COUNT(*) as count FROM messages")
    msg_count = c.fetchone()['count']
    print(f"   Meldinger: {msg_count}")
    
    c.execute("SELECT COUNT(*) as count FROM memories")
    mem_count = c.fetchone()['count']
    print(f"   Minner: {mem_count}")
    
    c.execute("SELECT COUNT(*) as count FROM profile_facts")
    fact_count = c.fetchone()['count']
    print(f"   Facts: {fact_count}")
    print()
    
    # Sjekk om migration allerede er kjørt
    c.execute("PRAGMA table_info(messages)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'user_name' in columns:
        print("⚠️  Migration ser ut til å være kjørt allerede")
        print("   user_name kolonne eksisterer i messages tabell")
        
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if c.fetchone():
            print("   users tabell eksisterer")
            print()
            print("Vil du kjøre migration på nytt? (ja/nei): ", end='')
            response = input().strip().lower()
            if response != 'ja':
                print("❌ Migration avbrutt")
                conn.close()
                sys.exit(0)
            print()
    
    try:
        print("🔧 Kjører migration...")
        print()
        
        # 1. Legg til user_name i messages
        print("1️⃣  Legger til user_name i messages tabell...")
        try:
            c.execute("ALTER TABLE messages ADD COLUMN user_name TEXT DEFAULT 'Osmund'")
            print("   ✅ user_name kolonne lagt til")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ⏭️  user_name kolonne eksisterer allerede")
            else:
                raise
        
        # 2. Legg til user_name i memories
        print("2️⃣  Legger til user_name i memories tabell...")
        try:
            c.execute("ALTER TABLE memories ADD COLUMN user_name TEXT DEFAULT 'Osmund'")
            print("   ✅ user_name kolonne lagt til")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ⏭️  user_name kolonne eksisterer allerede")
            else:
                raise
        
        # 3. Opprett users tabell
        print("3️⃣  Oppretter users tabell...")
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                relation_to_primary TEXT,
                first_seen TEXT NOT NULL,
                last_active TEXT NOT NULL,
                total_messages INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        print("   ✅ users tabell opprettet")
        
        # 4. Legg til Osmund som primary user
        print("4️⃣  Legger til Osmund som primary user...")
        now = datetime.now().isoformat()
        c.execute("""
            INSERT OR REPLACE INTO users 
            (username, display_name, relation_to_primary, first_seen, last_active, total_messages, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('Osmund', 'Osmund', 'owner', now, now, msg_count, '{"is_primary": true}'))
        print("   ✅ Osmund lagt til som primary user")
        
        # 5. Opprett indexes for performance
        print("5️⃣  Oppretter indexes...")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_name, timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_name, last_accessed DESC)")
        print("   ✅ Indexes opprettet")
        
        conn.commit()
        print()
        print("✅ Migration fullført!")
        print()
        
        # Vis ny statistikk
        print("📊 Database statistikk (etter migration):")
        c.execute("SELECT COUNT(*) as count FROM users")
        user_count = c.fetchone()['count']
        print(f"   Brukere: {user_count}")
        
        c.execute("SELECT username, display_name, relation_to_primary, total_messages FROM users")
        for row in c.fetchall():
            print(f"   - {row['display_name']} ({row['relation_to_primary']}): {row['total_messages']} meldinger")
        print()
        
        print("💡 Neste steg:")
        print("   1. Test systemet: sudo systemctl restart chatgpt-duck")
        print("   2. Verifiser i kontrollpanel")
        print("   3. Si 'bytt bruker' for å teste")
        
    except Exception as e:
        conn.rollback()
        print()
        print(f"❌ Migration feilet: {e}")
        print()
        print("💾 Ingen endringer er lagret (rollback)")
        print("   Du kan restore fra backup hvis nødvendig")
        sys.exit(1)
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
