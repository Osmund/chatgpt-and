#!/usr/bin/env python3
"""
ChatGPT Duck - Memory Hygiene Service

Periodisk vedlikehold av memory database:
- Decay gamle minner
- Slett low-confidence ephemeral data
- Vacuum database
- Backup
- Stats logging

Kjøres daglig via systemd timer (03:00)
"""

import sys
import time
from datetime import datetime, timedelta
from src.duck_memory import MemoryManager

# Flush stdout for journalctl
sys.stdout.reconfigure(line_buffering=True)


def run_maintenance():
    """
    Kjør alle maintenance tasks
    """
    print(f"\n{'='*60}", flush=True)
    print(f"🧹 Memory Hygiene - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
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
        
        # 4. Slett veldig gamle meldinger (>90 dager)
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
        
        # 5. Vacuum database
        print("🗜️  Vacuum database...", flush=True)
        conn = memory_manager._get_connection()
        conn.execute("VACUUM")
        conn.close()
        print("  ✅ Vacuum ferdig\n", flush=True)
        
        # 6. Stats etter cleanup
        stats_after = memory_manager.get_stats()
        print("📊 Stats etter cleanup:", flush=True)
        print(f"  - Total meldinger: {stats_after['total_messages']}", flush=True)
        print(f"  - Total minner: {stats_after['total_memories']}", flush=True)
        print(f"  - Total facts: {stats_after['total_facts']}", flush=True)
        print(f"  - Database størrelse: {stats_after['db_size_mb']} MB\n", flush=True)
        
        # 7. Summary
        print("✅ Maintenance ferdig!", flush=True)
        print(f"  - Minner decayed: {decayed}", flush=True)
        print(f"  - Minner slettet: {deleted}", flush=True)
        print(f"  - Meldinger slettet: {old_messages}", flush=True)
        print(f"  - Space saved: {stats_before['db_size_mb'] - stats_after['db_size_mb']:.2f} MB\n", flush=True)
        
    except Exception as e:
        print(f"❌ Maintenance feilet: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_maintenance()
