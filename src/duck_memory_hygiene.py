#!/usr/bin/env python3
"""
ChatGPT Duck - Memory Hygiene Service v2

Periodisk vedlikehold av memory database:
- Decay gamle minner
- Slett low-confidence ephemeral data
- Slett utløpte temporale fakta/minner
- Konsolider relaterte minner (LLM-basert)
- Slett resolved contradictions
- Vacuum database
- Stats logging

Kjøres daglig via systemd timer (03:00)
"""

import sys
import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.duck_memory import MemoryManager

# Flush stdout for journalctl
sys.stdout.reconfigure(line_buffering=True)

# Load environment for LLM consolidation
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MEMORY_MODEL = os.getenv("AI_MODEL_MEMORY", "gpt-4.1-mini-2025-04-14")

# Consolidation config
CONSOLIDATION_MIN_CLUSTER = 4    # Minst 4 minner i et topic før konsolidering
CONSOLIDATION_MAX_TOPICS = 5    # Maks 5 topics per natt (begrens API-bruk)


def _cleanup_expired(memory_manager) -> tuple:
    """
    Slett fakta og minner som har utløpt (expires_at i metadata).
    Returnerer (expired_facts, expired_memories).
    """
    conn = memory_manager._get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    # Finn utløpte facts
    expired_facts = 0
    c.execute("SELECT key, metadata FROM profile_facts WHERE metadata IS NOT NULL")
    for row in c.fetchall():
        try:
            meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            expires_at = meta.get('expires_at')
            if expires_at and expires_at < now:
                c.execute("DELETE FROM profile_facts WHERE key = ?", (row['key'],))
                expired_facts += 1
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Finn utløpte memories
    expired_memories = 0
    c.execute("SELECT id, metadata FROM memories WHERE metadata IS NOT NULL")
    for row in c.fetchall():
        try:
            meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            expires_at = meta.get('expires_at')
            if expires_at and expires_at < now:
                c.execute("DELETE FROM memories WHERE id = ?", (row['id'],))
                expired_memories += 1
        except (json.JSONDecodeError, TypeError):
            pass
    
    conn.commit()
    conn.close()
    return expired_facts, expired_memories


def _cleanup_old_contradictions(memory_manager) -> int:
    """Slett resolved contradictions eldre enn 30 dager."""
    conn = memory_manager._get_connection()
    c = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    
    try:
        c.execute("""
            DELETE FROM memory_contradictions 
            WHERE resolved = 1 AND detected_at < ?
        """, (cutoff,))
        deleted = c.rowcount
        conn.commit()
    except Exception:
        deleted = 0
    
    conn.close()
    return deleted


def _consolidate_memories(memory_manager) -> int:
    """
    Konsolider relaterte minner per topic via LLM.
    Finner topics med mange minner og slår dem sammen til
    færre, rikere innsikter.
    """
    if not OPENAI_API_KEY:
        print("  ⏭️  Ingen API-nøkkel, hopper over konsolidering", flush=True)
        return 0
    
    conn = memory_manager._get_connection()
    c = conn.cursor()
    
    # Finn topics med mange minner
    c.execute("""
        SELECT topic, COUNT(*) as cnt 
        FROM memories 
        GROUP BY topic 
        HAVING cnt >= ?
        ORDER BY cnt DESC
        LIMIT ?
    """, (CONSOLIDATION_MIN_CLUSTER, CONSOLIDATION_MAX_TOPICS))
    
    topics = [(row['topic'], row['cnt']) for row in c.fetchall()]
    conn.close()
    
    if not topics:
        print("  ℹ️  Ingen topics å konsolidere\n", flush=True)
        return 0
    
    total_consolidated = 0
    
    for topic, count in topics:
        try:
            consolidated = _consolidate_topic(memory_manager, topic)
            total_consolidated += consolidated
        except Exception as e:
            print(f"  ⚠️ Konsolidering av '{topic}' feilet: {e}", flush=True)
    
    return total_consolidated


def _consolidate_topic(memory_manager, topic: str) -> int:
    """
    Konsolider minner for ett topic.
    Sender gamle, lavfrekvente minner til LLM for oppsummering.
    Returnerer antall minner som ble slettet (erstattet av oppsummering).
    """
    conn = memory_manager._get_connection()
    c = conn.cursor()
    
    # Hent minner som er kandidater for konsolidering:
    # - Eldre enn 14 dager
    # - Lavfrekvent (frequency <= 2)
    # - Ikke for viktige (importance <= 3)
    cutoff = (datetime.now() - timedelta(days=14)).isoformat()
    
    c.execute("""
        SELECT id, text, metadata, confidence, first_seen
        FROM memories
        WHERE topic = ?
          AND last_accessed < ?
          AND frequency <= 2
          AND confidence < 0.9
        ORDER BY first_seen ASC
        LIMIT 20
    """, (topic, cutoff))
    
    candidates = [dict(row) for row in c.fetchall()]
    conn.close()
    
    if len(candidates) < CONSOLIDATION_MIN_CLUSTER:
        return 0
    
    # Bygg minne-liste for LLM
    memory_texts = "\n".join(f"- {m['text']}" for m in candidates)
    
    prompt = f"""
Du har {len(candidates)} individuelle minner om topic "{topic}".
Konsolider dem til 1-3 rikere, oppsummerende minner.

**Regler:**
- Behold all viktig informasjon
- Kombiner relaterte minner til én setning
- Fjern duplikater og trivielle detaljer
- Bruk naturlig norsk
- Hvert konsolidert minne skal være 1-2 setninger

**Individuelle minner:**
{memory_texts}

Returner JSON:
{{
    "consolidated_memories": [
        {{"text": "oppsummert minne", "importance": 3}}
    ]
}}
"""
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENAI_API_KEY}'},
            json={
                'model': MEMORY_MODEL,
                'messages': [
                    {'role': 'system', 'content': 'Du er en memory consolidation assistent. Returner kun valid JSON.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'response_format': {'type': 'json_object'}
            },
            timeout=30
        )
        response.raise_for_status()
        result = json.loads(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"  ⚠️ LLM consolidation API feil: {e}", flush=True)
        return 0
    
    consolidated = result.get('consolidated_memories', [])
    if not consolidated:
        return 0
    
    # Lagre nye konsoliderte minner
    from src.duck_memory import Memory
    for mem in consolidated:
        new_memory = Memory(
            text=mem['text'],
            topic=topic,
            confidence=0.85,
            source='consolidated',
            metadata={
                'consolidated_from': len(candidates),
                'consolidated_at': datetime.now().isoformat(),
                'importance': mem.get('importance', 3)
            }
        )
        memory_manager.save_memory(new_memory, check_duplicates=True)
    
    # Slett gamle individuelle minner som ble konsolidert
    conn = memory_manager._get_connection()
    c = conn.cursor()
    
    candidate_ids = [m['id'] for m in candidates]
    placeholders = ','.join('?' * len(candidate_ids))
    c.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", candidate_ids)
    deleted = c.rowcount
    conn.commit()
    conn.close()
    
    print(f"  🔄 {topic}: {deleted} minner → {len(consolidated)} konsoliderte", flush=True)
    return deleted


def run_maintenance():
    """
    Kjør alle maintenance tasks
    """
    print(f"\n{'='*60}", flush=True)
    print(f"🧹 Memory Hygiene v2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    try:
        memory_manager = MemoryManager()
        
        # 1. Database stats før cleanup
        stats_before = memory_manager.get_stats()
        print("📊 Stats før cleanup:", flush=True)
        print(f"  - Total meldinger: {stats_before['total_messages']}", flush=True)
        print(f"  - Total minner: {stats_before['total_memories']}", flush=True)
        print(f"  - Total facts: {stats_before['total_facts']}", flush=True)
        print(f"  - Database størrelse: {stats_before['db_size_mb']} MB\n", flush=True)
        
        # 2. Decay gamle minner (30+ dager)
        print("⏳ Decaying gamle minner...", flush=True)
        decayed = memory_manager.decay_old_memories(days=30)
        print(f"  ✅ {decayed} minner decayed\n", flush=True)
        
        # 3. Slett low-confidence ephemeral data
        print("🗑️  Sletter low-confidence minner...", flush=True)
        deleted = memory_manager.cleanup_low_confidence(threshold=0.2)
        print(f"  ✅ {deleted} minner slettet\n", flush=True)
        
        # 4. Slett utløpte temporale fakta/minner
        print("⏰ Sletter utløpte temporale data...", flush=True)
        expired_facts, expired_memories = _cleanup_expired(memory_manager)
        print(f"  ✅ {expired_facts} facts + {expired_memories} minner utløpt\n", flush=True)
        
        # 5. Slett resolved contradictions eldre enn 30 dager
        print("⚡ Rydder gamle contradictions...", flush=True)
        contradictions_cleaned = _cleanup_old_contradictions(memory_manager)
        print(f"  ✅ {contradictions_cleaned} resolved contradictions slettet\n", flush=True)
        
        # 6. Konsolider relaterte minner
        print("🧠 Konsoliderer relaterte minner...", flush=True)
        consolidated = _consolidate_memories(memory_manager)
        print(f"  ✅ {consolidated} minner konsolidert\n", flush=True)
        
        # 7. Slett veldig gamle meldinger (>90 dager)
        print("📝 Rydder gamle meldinger...", flush=True)
        conn = memory_manager._get_connection()
        c = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=90)).isoformat()
        c.execute("SELECT COUNT(*) as count FROM messages WHERE timestamp < ?", (cutoff,))
        old_messages = c.fetchone()['count']
        
        if old_messages > 0:
            c.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            conn.commit()
            print(f"  ✅ {old_messages} gamle meldinger slettet\n", flush=True)
        else:
            print(f"  ℹ️  Ingen gamle meldinger å slette\n", flush=True)
        
        conn.close()
        
        # 8. Vacuum database
        print("🗜️  Vacuum database...", flush=True)
        conn = memory_manager._get_connection()
        conn.execute("VACUUM")
        conn.close()
        print("  ✅ Vacuum ferdig\n", flush=True)
        
        # 9. Stats etter cleanup
        stats_after = memory_manager.get_stats()
        print("📊 Stats etter cleanup:", flush=True)
        print(f"  - Total meldinger: {stats_after['total_messages']}", flush=True)
        print(f"  - Total minner: {stats_after['total_memories']}", flush=True)
        print(f"  - Total facts: {stats_after['total_facts']}", flush=True)
        print(f"  - Database størrelse: {stats_after['db_size_mb']} MB\n", flush=True)
        
        # 10. Summary
        print("✅ Maintenance ferdig!", flush=True)
        print(f"  - Minner decayed: {decayed}", flush=True)
        print(f"  - Low-confidence slettet: {deleted}", flush=True)
        print(f"  - Utløpte fakta: {expired_facts}", flush=True)
        print(f"  - Utløpte minner: {expired_memories}", flush=True)
        print(f"  - Contradictions ryddet: {contradictions_cleaned}", flush=True)
        print(f"  - Minner konsolidert: {consolidated}", flush=True)
        print(f"  - Gamle meldinger slettet: {old_messages}", flush=True)
        print(f"  - Space saved: {stats_before['db_size_mb'] - stats_after['db_size_mb']:.2f} MB\n", flush=True)
        
    except Exception as e:
        print(f"❌ Maintenance feilet: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_maintenance()
