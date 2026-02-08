#!/usr/bin/env python3
"""
Script for å backfille session_id og metadata på eksisterende meldinger
"""
import sqlite3
import json
import uuid
from datetime import datetime, timedelta

DB_PATH = "/home/admog/Code/chatgpt-and/duck_memory.db"
SESSION_TIMEOUT_MINUTES = 30

def generate_message_metadata(user_text: str, ai_response: str, timestamp: str) -> dict:
    """Generer metadata for en melding"""
    metadata = {
        'user_length': len(user_text),
        'ai_length': len(ai_response),
        'has_question': '?' in user_text,
        'timestamp': timestamp
    }
    
    # Topic detection
    topics = []
    user_lower = user_text.lower()
    
    topic_keywords = {
        'weather': ['vær', 'temperatur', 'regn', 'sol', 'varmt', 'kaldt', 'været'],
        'time': ['klokk', 'tid', 'dato', 'dag', 'måned', 'år'],
        'family': ['mamma', 'pappa', 'søster', 'bror', 'familie', 'barn', 'datter', 'sønn', 'far', 'mor'],
        'work': ['jobb', 'arbeid', 'kontor', 'møte', 'kollega', 'sjef'],
        'health': ['lege', 'syk', 'tannlege', 'time', 'smerter', 'vondt'],
        'home': ['hus', 'leilighet', 'rom', 'kjøkken', 'bad', 'soverom'],
        'food': ['mat', 'middag', 'lunsj', 'frokost', 'spise', 'sultne'],
        'music': ['sang', 'musikk', 'spill', 'syng', 'låt'],
        'lights': ['lys', 'lampe', 'skru på', 'skru av', 'dimme']
    }
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in user_lower for keyword in keywords):
            topics.append(topic)
    
    metadata['topics'] = topics if topics else ['general']
    
    # Importance scoring
    importance = 5
    if metadata['has_question']:
        importance += 2
    if metadata['user_length'] > 100:
        importance += 1
    if len(topics) > 0:
        importance += 1
    
    metadata['importance'] = min(importance, 10)
    
    return metadata

def backfill_sessions_and_metadata():
    """Gruppér meldinger i sessions og generer metadata"""
    print("🔄 Backfiller sessions og metadata for eksisterende meldinger")
    print("=" * 70)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Hent alle meldinger uten session_id, sortert etter timestamp
    c.execute("""
        SELECT id, user_text, ai_response, timestamp, user_name
        FROM messages
        WHERE session_id IS NULL OR session_id = ''
        ORDER BY timestamp ASC
    """)
    
    messages = c.fetchall()
    total_messages = len(messages)
    
    print(f"📊 Fant {total_messages} meldinger uten session_id")
    print()
    
    if total_messages == 0:
        print("✅ Ingen meldinger å prosessere")
        conn.close()
        return
    
    # Gruppér meldinger i sessions basert på timestamp gaps
    sessions = []
    current_session = []
    current_session_id = str(uuid.uuid4())
    last_timestamp = None
    
    print("🔍 Grupperer meldinger i sessions...")
    for msg in messages:
        msg_time = datetime.fromisoformat(msg['timestamp'])
        
        # Sjekk om dette er en ny session (> 30 min gap)
        if last_timestamp:
            time_gap = msg_time - last_timestamp
            if time_gap > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                # Start ny session
                if current_session:
                    sessions.append((current_session_id, current_session))
                current_session_id = str(uuid.uuid4())
                current_session = []
        
        current_session.append(dict(msg))
        last_timestamp = msg_time
    
    # Legg til siste session
    if current_session:
        sessions.append((current_session_id, current_session))
    
    print(f"  ✅ Opprettet {len(sessions)} sessions")
    print()
    
    # Oppdater messages med session_id og metadata
    print("💾 Oppdaterer messages...")
    updated_count = 0
    
    for session_id, session_messages in sessions:
        for msg in session_messages:
            # Generer metadata
            metadata = generate_message_metadata(
                msg['user_text'],
                msg['ai_response'],
                msg['timestamp']
            )
            metadata_json = json.dumps(metadata, ensure_ascii=False)
            
            # Oppdater message
            c.execute("""
                UPDATE messages
                SET session_id = ?, metadata = ?
                WHERE id = ?
            """, (session_id, metadata_json, msg['id']))
            
            updated_count += 1
            
            if updated_count % 50 == 0:
                print(f"  Prosessert {updated_count}/{total_messages} meldinger...")
    
    conn.commit()
    print(f"  ✅ Oppdatert {updated_count} meldinger")
    print()
    
    # Opprett session summaries
    print("📝 Oppretter session summaries...")
    summaries_created = 0
    
    for session_id, session_messages in sessions:
        if len(session_messages) < 1:
            continue
        
        # Samle topics fra alle meldinger i session
        all_topics = set()
        for msg in session_messages:
            metadata_str = c.execute(
                "SELECT metadata FROM messages WHERE id = ?",
                (msg['id'],)
            ).fetchone()['metadata']
            
            if metadata_str:
                try:
                    meta = json.loads(metadata_str)
                    all_topics.update(meta.get('topics', []))
                except:
                    pass
        
        topics_str = ', '.join(sorted(all_topics)) if all_topics else 'general'
        summary = f"Samtale med {len(session_messages)} meldinger. Topics: {topics_str}"
        start_time = session_messages[0]['timestamp']
        end_time = session_messages[-1]['timestamp']
        
        # Lagre summary
        c.execute("""
            INSERT INTO session_summaries 
            (session_id, summary, message_count, topics, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, summary, len(session_messages), topics_str, start_time, end_time))
        
        summaries_created += 1
    
    conn.commit()
    print(f"  ✅ Opprettet {summaries_created} session summaries")
    print()
    
    # Vis statistikk
    print("📊 Oppsummering:")
    print(f"  Sessions: {len(sessions)}")
    print(f"  Meldinger oppdatert: {updated_count}")
    print(f"  Summaries opprettet: {summaries_created}")
    print()
    
    # Vis eksempel på sessions
    print("🔍 Eksempel på sessions:")
    for i, (session_id, session_messages) in enumerate(sessions[:3]):
        start = session_messages[0]['timestamp']
        end = session_messages[-1]['timestamp']
        print(f"  Session {i+1}: {session_id[:8]}... ({len(session_messages)} msg, {start[:10]} - {end[:10]})")
    
    if len(sessions) > 3:
        print(f"  ... og {len(sessions) - 3} flere sessions")
    
    conn.close()
    print()
    print("✅ Ferdig!")

if __name__ == "__main__":
    print()
    response = input("Dette vil oppdatere alle eksisterende meldinger. Fortsette? (ja/nei): ").strip().lower()
    if response in ['ja', 'j', 'yes', 'y']:
        backfill_sessions_and_metadata()
    else:
        print("Avbrutt.")
