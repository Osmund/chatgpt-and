#!/usr/bin/env python3
"""
ChatGPT Duck - Memory Management System

Håndterer persistent minne på tvers av samtaler:
- Korttidsminne (siste N meldinger)
- Langtidsminne (profile facts)
- Episodisk minne (søkbare minner med vekting)
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import math


@dataclass
class ProfileFact:
    """Strukturert faktum om bruker"""
    key: str
    value: str
    topic: str
    confidence: float = 1.0
    frequency: int = 1
    source: str = 'user'  # 'user', 'assistant', 'inferred'
    last_updated: Optional[str] = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()


@dataclass
class Memory:
    """Episodisk minne"""
    id: Optional[int] = None
    text: str = ""
    topic: str = "general"
    frequency: int = 1
    confidence: float = 1.0
    source: str = 'extracted'
    first_seen: Optional[str] = None
    last_accessed: Optional[str] = None
    metadata: Optional[Dict] = None
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if self.first_seen is None:
            self.first_seen = now
        if self.last_accessed is None:
            self.last_accessed = now
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def relevance_score(self) -> float:
        """Beregn relevans-score for sortering"""
        # Topic weights
        TOPIC_WEIGHTS = {
            'family': 1.5,
            'hobby': 1.5,
            'work': 1.3,
            'projects': 1.4,
            'health': 1.2,
            'pets': 1.2,
            'preferences': 1.0,
            'technical': 1.1,
            'weather': 0.3,
            'general': 0.8
        }
        
        base_weight = TOPIC_WEIGHTS.get(self.topic, 1.0)
        
        # Frekvens-bonus (log scale)
        frequency_multiplier = 1 + (math.log(self.frequency + 1) * 0.3)
        
        # Recency decay
        if self.last_accessed:
            last_access = datetime.fromisoformat(self.last_accessed)
            days_since = (datetime.now() - last_access).days
            recency_decay = math.exp(-days_since / 30)
        else:
            recency_decay = 1.0
        
        return (base_weight * 
                frequency_multiplier * 
                recency_decay * 
                self.confidence)


@dataclass
class Message:
    """Samtalemelding"""
    id: Optional[int] = None
    user_text: str = ""
    ai_response: str = ""
    timestamp: Optional[str] = None
    processed: int = 0  # 0 = ikke prosessert av worker
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class MemoryMetrics:
    """Performance metrics"""
    def __init__(self):
        self.search_latency: List[float] = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.memory_extractions = 0
        self.total_searches = 0
    
    @property
    def avg_search_latency(self) -> float:
        if not self.search_latency:
            return 0.0
        return sum(self.search_latency) / len(self.search_latency)
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    def to_dict(self) -> Dict:
        return {
            'avg_search_latency_ms': round(self.avg_search_latency * 1000, 2),
            'cache_hit_rate': round(self.cache_hit_rate * 100, 1),
            'total_searches': self.total_searches,
            'memory_extractions': self.memory_extractions
        }


class MemoryManager:
    """
    Hovedklasse for memory management
    
    Funksjoner:
    - Lagre og hente minner
    - FTS5 søk
    - Vektet ranking
    - Session state management
    - Caching
    """
    
    def __init__(self, db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db"):
        self.db_path = db_path
        self.metrics = MemoryMetrics()
        
        # In-memory cache
        self._cache = {
            'top_facts': None,
            'top_facts_ts': 0,
            'session_state': None,
            'session_state_ts': 0
        }
        self.CACHE_TTL = 300  # 5 minutter
        
        # Initialiser database
        self._init_database()
    
    def _init_database(self):
        """Opprett tabeller og indexes"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Messages tabell
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_text TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                processed INTEGER DEFAULT 0,
                session_id TEXT,
                metadata TEXT
            )
        """)
        
        # Profile facts tabell
        c.execute("""
            CREATE TABLE IF NOT EXISTS profile_facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                topic TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                frequency INTEGER DEFAULT 1,
                source TEXT DEFAULT 'user',
                last_updated TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Memories tabell
        c.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                topic TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                confidence REAL DEFAULT 1.0,
                source TEXT DEFAULT 'extracted',
                first_seen TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Topic stats tabell
        c.execute("""
            CREATE TABLE IF NOT EXISTS topic_stats (
                topic TEXT PRIMARY KEY,
                mention_count INTEGER DEFAULT 0,
                last_mentioned TEXT NOT NULL,
                avg_importance REAL DEFAULT 1.0
            )
        """)
        
        # Session summaries
        c.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                topics TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL
            )
        """)
        
        # FTS5 virtual table for full-text search on memories
        # unicode61 tokenizer for bedre håndtering av æøå
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts 
            USING fts5(text, content='memories', content_rowid='id', 
                      tokenize='unicode61 remove_diacritics 0')
        """)
        
        # FTS5 virtual table for profile_facts med unicode61 og trigram
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS profile_facts_fts 
            USING fts5(key, value, topic, content='profile_facts', content_rowid='rowid',
                      tokenize='unicode61 remove_diacritics 0')
        """)
        
        # Trigram-tabell for fuzzy matching av norske ord
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS profile_facts_trigram
            USING fts5(key, value, topic, content='profile_facts', content_rowid='rowid',
                      tokenize='trigram')
        """)
        
        # Triggers for memories FTS sync
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai 
            AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, text) 
                VALUES (new.id, new.text);
            END
        """)
        
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad 
            AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, text) 
                VALUES('delete', old.id, old.text);
            END
        """)
        
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au 
            AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, text) 
                VALUES('delete', old.id, old.text);
                INSERT INTO memories_fts(rowid, text) 
                VALUES (new.id, new.text);
            END
        """)
        
        # Triggers for profile_facts FTS sync
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS profile_facts_ai 
            AFTER INSERT ON profile_facts BEGIN
                INSERT INTO profile_facts_fts(rowid, key, value, topic) 
                VALUES (new.rowid, new.key, new.value, new.topic);
                INSERT INTO profile_facts_trigram(rowid, key, value, topic) 
                VALUES (new.rowid, new.key, new.value, new.topic);
            END
        """)
        
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS profile_facts_ad 
            AFTER DELETE ON profile_facts BEGIN
                INSERT INTO profile_facts_fts(profile_facts_fts, rowid, key, value, topic) 
                VALUES('delete', old.rowid, old.key, old.value, old.topic);
                INSERT INTO profile_facts_trigram(profile_facts_trigram, rowid, key, value, topic) 
                VALUES('delete', old.rowid, old.key, old.value, old.topic);
            END
        """)
        
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS profile_facts_au 
            AFTER UPDATE ON profile_facts BEGIN
                INSERT INTO profile_facts_fts(profile_facts_fts, rowid, key, value, topic) 
                VALUES('delete', old.rowid, old.key, old.value, old.topic);
                INSERT INTO profile_facts_fts(rowid, key, value, topic) 
                VALUES (new.rowid, new.key, new.value, new.topic);
                INSERT INTO profile_facts_trigram(profile_facts_trigram, rowid, key, value, topic) 
                VALUES('delete', old.rowid, old.key, old.value, old.topic);
                INSERT INTO profile_facts_trigram(rowid, key, value, topic) 
                VALUES (new.rowid, new.key, new.value, new.topic);
            END
        """)
        
        # Indexes for performance
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_processed ON messages(processed, timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_memories_topic ON memories(topic)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_memories_frequency ON memories(frequency DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_memories_accessed ON memories(last_accessed DESC)")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Memory database initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Hent database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ==================== MESSAGE STORAGE ====================
    
    def save_message(self, user_text: str, ai_response: str, session_id: Optional[str] = None) -> int:
        """Lagre melding til database (synkront, rask)"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO messages (user_text, ai_response, timestamp, session_id)
            VALUES (?, ?, ?, ?)
        """, (user_text, ai_response, datetime.now().isoformat(), session_id))
        
        message_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return message_id
    
    def get_unprocessed_messages(self, limit: int = 10) -> List[Message]:
        """Hent meldinger som ikke er prosessert av worker"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT * FROM messages 
            WHERE processed = 0 
            ORDER BY timestamp ASC 
            LIMIT ?
        """, (limit,))
        
        messages = []
        for row in c.fetchall():
            messages.append(Message(
                id=row['id'],
                user_text=row['user_text'],
                ai_response=row['ai_response'],
                timestamp=row['timestamp'],
                processed=row['processed'],
                session_id=row['session_id']
            ))
        
        conn.close()
        return messages
    
    def mark_message_processed(self, message_id: int):
        """Marker melding som prosessert"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("UPDATE messages SET processed = 1 WHERE id = ?", (message_id,))
        conn.commit()
        conn.close()
    
    # ==================== PROFILE FACTS ====================
    
    def save_profile_fact(self, fact: ProfileFact) -> bool:
        """Lagre eller oppdater profile fact"""
        conn = self._get_connection()
        c = conn.cursor()
        
        # Sjekk om key allerede eksisterer
        c.execute("SELECT frequency FROM profile_facts WHERE key = ?", (fact.key,))
        existing = c.fetchone()
        
        if existing:
            # Oppdater: øk frekvens, oppdater verdi hvis ny
            new_freq = existing['frequency'] + 1
            c.execute("""
                UPDATE profile_facts 
                SET value = ?, 
                    confidence = ?, 
                    frequency = ?,
                    last_updated = ?,
                    source = ?
                WHERE key = ?
            """, (fact.value, fact.confidence, new_freq, 
                  datetime.now().isoformat(), fact.source, fact.key))
        else:
            # Ny fact
            c.execute("""
                INSERT INTO profile_facts 
                (key, value, topic, confidence, frequency, source, last_updated, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (fact.key, fact.value, fact.topic, fact.confidence, 
                  fact.frequency, fact.source, fact.last_updated, 
                  json.dumps(fact.metadata) if hasattr(fact, 'metadata') else '{}'))
        
        conn.commit()
        conn.close()
        
        # Invalidate cache
        self._cache['top_facts'] = None
        
        return True
    
    def get_profile_facts(self, limit: Optional[int] = None) -> List[ProfileFact]:
        """Hent profile facts sortert etter relevans"""
        conn = self._get_connection()
        c = conn.cursor()
        
        query = """
            SELECT * FROM profile_facts 
            ORDER BY frequency DESC, confidence DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        
        c.execute(query)
        
        facts = []
        for row in c.fetchall():
            facts.append(ProfileFact(
                key=row['key'],
                value=row['value'],
                topic=row['topic'],
                confidence=row['confidence'],
                frequency=row['frequency'],
                source=row['source'],
                last_updated=row['last_updated']
            ))
        
        conn.close()
        return facts
    
    def get_top_facts_cached(self, limit: int = 10) -> List[ProfileFact]:
        """Hent top facts med caching"""
        now = time.time()
        
        if (self._cache['top_facts'] is not None and 
            now - self._cache['top_facts_ts'] < self.CACHE_TTL):
            self.metrics.cache_hits += 1
            return self._cache['top_facts']
        
        self.metrics.cache_misses += 1
        facts = self.get_profile_facts(limit=limit)
        self._cache['top_facts'] = facts
        self._cache['top_facts_ts'] = now
        
        return facts
    
    def search_profile_facts(self, query: str, limit: int = 10) -> List[ProfileFact]:
        """Søk etter relevante profile facts basert på query"""
        conn = self._get_connection()
        c = conn.cursor()
        
        # Ekstraher nøkkelord fra norsk query
        keywords = []
        query_lower = query.lower()
        
        # Mapping fra norske ord til database keys
        keyword_map = {
            'søster': 'sister',
            'søstre': 'sister', 
            'søsken': 'sister',
            'bror': 'brother',
            'far': 'father',
            'mor': 'mother',
            'pappa': 'father',
            'mamma': 'mother',
            'familie': 'family',
            'jobb': 'job',
            'arbeid': 'job',
            'bolig': 'home',
            'hus': 'home',
            'navn': 'name',
            'heter': 'name',
            'bursdag': 'birthday',
            'alder': 'age',
            'år': 'age',
            'hvor': 'location',
            'bor': 'location'
        }
        
        # Finn relevante nøkkelord
        for norsk, engelsk in keyword_map.items():
            if norsk in query_lower:
                keywords.append(engelsk)
        
        # Hvis vi fant nøkkelord, prøv FTS søk først
        if keywords:
            keyword_query = ' OR '.join(keywords)
            try:
                c.execute("""
                    SELECT pf.*, bm25(profile_facts_fts) as score
                    FROM profile_facts_fts
                    JOIN profile_facts pf ON pf.rowid = profile_facts_fts.rowid
                    WHERE profile_facts_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                """, (keyword_query, limit))
                
                facts = []
                for row in c.fetchall():
                    facts.append(ProfileFact(
                        key=row['key'],
                        value=row['value'],
                        topic=row['topic'],
                        confidence=row['confidence'],
                        frequency=row['frequency'],
                        source=row['source'],
                        last_updated=row['last_updated']
                    ))
                
                if facts:
                    conn.close()
                    return facts
            except Exception:
                pass  # Fall through
        
        # Prøv trigram fuzzy matching for norske ord
        try:
            c.execute("""
                SELECT pf.*, bm25(profile_facts_trigram) as score
                FROM profile_facts_trigram
                JOIN profile_facts pf ON pf.rowid = profile_facts_trigram.rowid
                WHERE profile_facts_trigram MATCH ?
                ORDER BY score
                LIMIT ?
            """, (query_lower, limit // 2))
            
            facts = []
            for row in c.fetchall():
                facts.append(ProfileFact(
                    key=row['key'],
                    value=row['value'],
                    topic=row['topic'],
                    confidence=row['confidence'],
                    frequency=row['frequency'],
                    source=row['source'],
                    last_updated=row['last_updated']
                ))
            
            if facts:
                conn.close()
                return facts
        except Exception:
            pass  # Fall through
        
        # Fallback: LIKE-søk med både original query og keywords
        search_terms = [query] + keywords
        placeholders = ' OR '.join(['key LIKE ? OR value LIKE ? OR topic LIKE ?'] * len(search_terms))
        params = []
        for term in search_terms:
            params.extend([f'%{term}%', f'%{term}%', f'%{term}%'])
        params.append(limit)
        
        c.execute(f"""
            SELECT * FROM profile_facts
            WHERE {placeholders}
            ORDER BY frequency DESC, confidence DESC
            LIMIT ?
        """, params)
        
        facts = []
        for row in c.fetchall():
            facts.append(ProfileFact(
                key=row['key'],
                value=row['value'],
                topic=row['topic'],
                confidence=row['confidence'],
                frequency=row['frequency'],
                source=row['source'],
                last_updated=row['last_updated']
            ))
        
        conn.close()
        return facts
    
    # ==================== MEMORIES ====================
    
    def save_memory(self, memory: Memory) -> int:
        """Lagre nytt minne"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO memories 
            (text, topic, frequency, confidence, source, first_seen, last_accessed, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (memory.text, memory.topic, memory.frequency, memory.confidence,
              memory.source, memory.first_seen, memory.last_accessed,
              json.dumps(memory.metadata)))
        
        memory_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Oppdater topic stats
        self._update_topic_stats(memory.topic)
        
        return memory_id
    
    def search_memories(self, query: str, limit: int = 10) -> List[Tuple[Memory, float]]:
        """
        Søk i minner med FTS5 + vektet scoring
        Returnerer: List[(Memory, score)]
        """
        start_time = time.time()
        
        conn = self._get_connection()
        c = conn.cursor()
        
        # FTS5 søk - først sjekk om det finnes noen minner
        c.execute("SELECT COUNT(*) as count FROM memories")
        if c.fetchone()['count'] == 0:
            conn.close()
            return []
        
        # FTS5 MATCH query - bruk enkle søkeord uten special chars
        search_limit = limit * 3
        try:
            c.execute(f"""
                SELECT m.*, memories_fts.rank
                FROM memories_fts 
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT {search_limit}
            """, (query,))
        except sqlite3.OperationalError:
            # Fallback til LIKE hvis FTS feiler
            c.execute(f"""
                SELECT *, 0 as rank FROM memories 
                WHERE text LIKE ?
                LIMIT {search_limit}
            """, (f"%{query}%",))
        
        # Beregn scores og re-rank
        scored_memories = []
        for row in c.fetchall():
            memory = Memory(
                id=row['id'],
                text=row['text'],
                topic=row['topic'],
                frequency=row['frequency'],
                confidence=row['confidence'],
                source=row['source'],
                first_seen=row['first_seen'],
                last_accessed=row['last_accessed'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            )
            
            # Kombinert score: FTS rank + relevance score
            fts_score = 1.0 / (abs(row['rank']) + 1)
            combined_score = fts_score * 2.0 + memory.relevance_score
            
            scored_memories.append((memory, combined_score))
        
        conn.close()
        
        # Sorter etter kombinert score
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        
        # Oppdater last_accessed for returnerte minner
        for memory, _ in scored_memories[:limit]:
            self._touch_memory(memory.id)
        
        # Metrics
        elapsed = time.time() - start_time
        self.metrics.search_latency.append(elapsed)
        self.metrics.total_searches += 1
        
        return scored_memories[:limit]
    
    def _touch_memory(self, memory_id: int):
        """Oppdater last_accessed og øk frequency"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("""
            UPDATE memories 
            SET last_accessed = ?,
                frequency = frequency + 1
            WHERE id = ?
        """, (datetime.now().isoformat(), memory_id))
        conn.commit()
        conn.close()
    
    # ==================== TOPIC STATS ====================
    
    def _update_topic_stats(self, topic: str):
        """Oppdater topic statistikk"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO topic_stats (topic, mention_count, last_mentioned)
            VALUES (?, 1, ?)
            ON CONFLICT(topic) DO UPDATE SET
                mention_count = mention_count + 1,
                last_mentioned = ?
        """, (topic, datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_topic_stats(self, limit: int = 10) -> List[Dict]:
        """Hent topic statistikk"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT * FROM topic_stats 
            ORDER BY mention_count DESC 
            LIMIT ?
        """, (limit,))
        
        stats = []
        for row in c.fetchall():
            stats.append({
                'topic': row['topic'],
                'mention_count': row['mention_count'],
                'last_mentioned': row['last_mentioned'],
                'avg_importance': row['avg_importance']
            })
        
        conn.close()
        return stats
    
    # ==================== SESSION STATE ====================
    
    def build_context_for_ai(self, query: str, recent_messages: int = 5) -> Dict:
        """
        Bygg komplett context for AI-prompt
        
        Returnerer dict med:
        - profile_facts: Top fakta om bruker (kombinasjon av søkte + frekvente)
        - relevant_memories: Søkte minner
        - recent_topics: Hva snakker vi om?
        - conversation_summary: Hvis tilgjengelig
        """
        # 1. Søk etter relevante facts basert på query
        searched_facts = self.search_profile_facts(query, limit=8)
        
        # 2. Hent også de mest frekvente facts
        frequent_facts = self.get_top_facts_cached(limit=10)
        
        # 3. Kombiner og dedupliser (prioriter søkte facts)
        seen_keys = set()
        combined_facts = []
        
        # Legg til søkte facts først
        for fact in searched_facts:
            if fact.key not in seen_keys:
                combined_facts.append(fact)
                seen_keys.add(fact.key)
        
        # Legg til frekvente facts
        for fact in frequent_facts:
            if fact.key not in seen_keys:
                combined_facts.append(fact)
                seen_keys.add(fact.key)
        
        # Begrens til max 15 facts totalt
        profile_facts = combined_facts[:15]
        
        # 4. Relevant memories (FTS søk)
        relevant_memories = self.search_memories(query, limit=8)
        
        # 5. Recent topics
        topic_stats = self.get_topic_stats(limit=5)
        
        # 6. Recent conversation (siste N meldinger)
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT user_text, ai_response FROM messages 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (recent_messages,))
        recent_conv = [dict(row) for row in c.fetchall()]
        recent_conv.reverse()  # Eldst først
        conn.close()
        
        context = {
            'profile_facts': [asdict(f) for f in profile_facts],
            'relevant_memories': [(m.text, score) for m, score in relevant_memories],
            'recent_topics': topic_stats,
            'recent_conversation': recent_conv,
            'metadata': {
                'total_facts': len(profile_facts),
                'total_memories': len(relevant_memories),
                'query': query
            }
        }
        
        return context
    
    # ==================== MAINTENANCE ====================
    
    def decay_old_memories(self, days: int = 30):
        """Reduser confidence for gamle, sjeldent brukte minner"""
        conn = self._get_connection()
        c = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        c.execute("""
            UPDATE memories
            SET confidence = confidence * 0.9
            WHERE last_accessed < ?
              AND frequency <= 2
              AND confidence > 0.3
        """, (cutoff_date,))
        
        affected = c.rowcount
        conn.commit()
        conn.close()
        
        return affected
    
    def cleanup_low_confidence(self, threshold: float = 0.2):
        """Slett minner med veldig lav confidence"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            DELETE FROM memories 
            WHERE confidence < ? 
              AND frequency = 1
              AND topic IN ('weather', 'time', 'general')
        """, (threshold,))
        
        deleted = c.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_stats(self) -> Dict:
        """Hent database statistikk"""
        conn = self._get_connection()
        c = conn.cursor()
        
        stats = {}
        
        # Counts
        c.execute("SELECT COUNT(*) as count FROM messages")
        stats['total_messages'] = c.fetchone()['count']
        
        c.execute("SELECT COUNT(*) as count FROM messages WHERE processed = 0")
        stats['unprocessed_messages'] = c.fetchone()['count']
        
        c.execute("SELECT COUNT(*) as count FROM memories")
        stats['total_memories'] = c.fetchone()['count']
        
        c.execute("SELECT COUNT(*) as count FROM profile_facts")
        stats['total_facts'] = c.fetchone()['count']
        
        # Database size
        db_path = Path(self.db_path)
        if db_path.exists():
            stats['db_size_mb'] = round(db_path.stat().st_size / (1024 * 1024), 2)
        
        # Performance metrics
        stats['performance'] = self.metrics.to_dict()
        
        conn.close()
        return stats


if __name__ == "__main__":
    # Test setup
    print("Testing MemoryManager...")
    
    manager = MemoryManager()
    
    # Test save profile fact
    fact = ProfileFact(
        key="home_city",
        value="Stavanger",
        topic="personal",
        confidence=1.0,
        source="user"
    )
    manager.save_profile_fact(fact)
    print(f"✅ Saved profile fact: {fact.key} = {fact.value}")
    
    # Test save memory
    memory = Memory(
        text="Brukeren pendler til Sokndal hver dag",
        topic="work",
        confidence=0.9
    )
    mem_id = manager.save_memory(memory)
    print(f"✅ Saved memory: {memory.text} (id={mem_id})")
    
    # Test save message
    msg_id = manager.save_message(
        user_text="Hei, hvordan går det?",
        ai_response="Hei! Det går bra, takk for at du spør!"
    )
    print(f"✅ Saved message (id={msg_id})")
    
    # Test search
    results = manager.search_memories("Sokndal", limit=5)
    print(f"✅ Search found {len(results)} results")
    
    # Test context building
    context = manager.build_context_for_ai("Hvor bor jeg?")
    print(f"✅ Built context with {len(context['profile_facts'])} facts")
    
    # Stats
    stats = manager.get_stats()
    print(f"\n📊 Database stats:")
    for key, value in stats.items():
        if key != 'performance':
            print(f"  {key}: {value}")
    
    print(f"\n⚡ Performance:")
    for key, value in stats['performance'].items():
        print(f"  {key}: {value}")
    
    print("\n✅ All tests passed!")
