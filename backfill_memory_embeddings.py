#!/usr/bin/env python3
"""
Backfill embeddings for existing memories
Generer embeddings for alle memories som ikke har det
"""

import sqlite3
import pickle
import json
from duck_memory import MemoryManager

def backfill_embeddings():
    """Generer embeddings for alle memories uten embeddings"""
    
    manager = MemoryManager()
    
    conn = sqlite3.connect('/home/admog/Code/chatgpt-and/duck_memory.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Hent alle memories uten embeddings
    c.execute("""
        SELECT id, text
        FROM memories
        WHERE embedding IS NULL
    """)
    
    memories_to_process = c.fetchall()
    total = len(memories_to_process)
    
    print(f"📊 Fant {total} memories uten embeddings")
    print(f"💰 Dette vil koste ca ${(total * 75 * 0.02 / 1_000_000):.5f}")
    print()
    
    if total == 0:
        print("✅ Alle memories har allerede embeddings!")
        conn.close()
        return
    
    # Generer embeddings
    success_count = 0
    error_count = 0
    
    for i, row in enumerate(memories_to_process, 1):
        memory_id = row['id']
        text = row['text']
        
        try:
            # Generer embedding
            embedding_array = manager.generate_embedding(text)
            embedding_blob = pickle.dumps(embedding_array)
            
            # Lagre
            c.execute("""
                UPDATE memories
                SET embedding = ?
                WHERE id = ?
            """, (embedding_blob, memory_id))
            conn.commit()
            
            success_count += 1
            print(f"[{i}/{total}] ✅ Memory {memory_id}: {text[:60]}...")
            
        except Exception as e:
            error_count += 1
            print(f"[{i}/{total}] ❌ Memory {memory_id}: Feil - {e}")
    
    conn.close()
    
    print()
    print("=" * 60)
    print(f"✅ Vellykket: {success_count}")
    print(f"❌ Feil: {error_count}")
    print(f"📊 Total prosessert: {total}")
    print("=" * 60)

if __name__ == '__main__':
    backfill_embeddings()
