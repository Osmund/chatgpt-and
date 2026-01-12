#!/usr/bin/env python3
"""
Script for å oppdatere metadata på eksisterende fakta og minner
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

def update_metadata():
    db_path = "/home/admog/Code/chatgpt-and/duck_memory.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔄 Oppdaterer metadata for eksisterende fakta...")
    
    # Hent alle profile_facts som mangler metadata
    cursor.execute("""
        SELECT key, confidence, last_updated, source
        FROM profile_facts
        WHERE metadata IS NULL OR metadata = '{}'
    """)
    
    facts = cursor.fetchall()
    updated_facts = 0
    
    for key, confidence, last_updated, source in facts:
        # Lag metadata basert på eksisterende data
        metadata = {
            'learned_at': last_updated if last_updated else datetime.now().isoformat(),
            'source_message_id': None,  # Ukjent for gamle fakta
            'extraction_confidence': confidence,
            'learned_from': source if source else 'unknown',
            'migrated': True,  # Markere at dette er migrert data
            'migration_date': datetime.now().isoformat()
        }
        
        cursor.execute("""
            UPDATE profile_facts
            SET metadata = ?
            WHERE key = ?
        """, (json.dumps(metadata), key))
        
        updated_facts += 1
    
    print(f"✅ Oppdatert {updated_facts} profile_facts")
    
    # Gjør det samme for memories
    cursor.execute("""
        SELECT id, confidence, first_seen, source
        FROM memories
        WHERE metadata IS NULL OR metadata = '{}'
    """)
    
    memories = cursor.fetchall()
    updated_memories = 0
    
    for memory_id, confidence, first_seen, source in memories:
        metadata = {
            'learned_at': first_seen if first_seen else datetime.now().isoformat(),
            'source_message_id': None,
            'extraction_confidence': confidence if confidence else 0.8,
            'learned_from': source if source else 'unknown',
            'migrated': True,
            'migration_date': datetime.now().isoformat()
        }
        
        cursor.execute("""
            UPDATE memories
            SET metadata = ?
            WHERE id = ?
        """, (json.dumps(metadata), memory_id))
        
        updated_memories += 1
    
    print(f"✅ Oppdatert {updated_memories} memories")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Ferdig! Totalt oppdatert {updated_facts + updated_memories} poster")

if __name__ == "__main__":
    print("=" * 60)
    print("METADATA MIGRATION SCRIPT")
    print("=" * 60)
    print("Dette scriptet oppdaterer eksisterende fakta og minner")
    print("med metadata basert på eksisterende data.")
    print()
    
    response = input("Fortsette? (ja/nei): ").strip().lower()
    if response in ['ja', 'j', 'yes', 'y']:
        update_metadata()
    else:
        print("Avbrutt.")
