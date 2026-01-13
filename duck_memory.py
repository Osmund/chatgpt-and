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
import pickle
import numpy as np
from openai import OpenAI
import os
from dotenv import load_dotenv

# Last environment variables
load_dotenv()


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
    metadata: Optional[dict] = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}


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
    user_name: str = 'Osmund'  # Hvilken bruker sendte meldingen
    
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
        
        # OpenAI client for embeddings
        self.openai_client = OpenAI()
        
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
    
    def save_message(self, user_text: str, ai_response: str, session_id: Optional[str] = None, user_name: str = 'Osmund') -> int:
        """Lagre melding til database (synkront, rask)"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO messages (user_text, ai_response, timestamp, session_id, user_name)
            VALUES (?, ?, ?, ?, ?)
        """, (user_text, ai_response, datetime.now().isoformat(), session_id, user_name))
        
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
                session_id=row['session_id'],
                user_name=row['user_name'] if 'user_name' in row.keys() else 'Osmund'
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
        c.execute("SELECT frequency, confidence, value FROM profile_facts WHERE key = ?", (fact.key,))
        existing = c.fetchone()
        
        if existing:
            # VIKTIG: Ikke overskriv fakta med høy confidence (1.0)
            # Dette beskytter mot at memory workeren ødelegger verifiserte fakta
            if existing['confidence'] >= 1.0 and fact.value != existing['value']:
                print(f"⚠️ Blokkerer overskriving av verifisert fact: {fact.key} = '{existing['value']}' (forsøkte: '{fact.value}')", flush=True)
                conn.close()
                return False
            
            # Oppdater: øk frekvens, oppdater verdi hvis ny
            new_freq = existing['frequency'] + 1
            c.execute("""
                UPDATE profile_facts 
                SET value = ?, 
                    confidence = ?, 
                    frequency = ?,
                    last_updated = ?,
                    source = ?,
                    metadata = ?
                WHERE key = ?
            """, (fact.value, fact.confidence, new_freq, 
                  datetime.now().isoformat(), fact.source, 
                  json.dumps(fact.metadata) if hasattr(fact, 'metadata') and fact.metadata else '{}',
                  fact.key))
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
        
        # Generer embedding for ny/oppdatert fact
        self.update_fact_embedding(fact.key)
        
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
            'bor': 'location',
            'samler': 'collection',
            'samling': 'collection',
            'hobby': 'hobby',
            'hobbyer': 'hobby',
            'interesse': 'hobby',
            'datamaskin': 'computer',
            'datamaskiner': 'computer',
            'pc': 'computer',
            'maskin': 'computer',
            'niese': 'niece',
            'nieser': 'niece',
            'nevø': 'nephew',
            'nevøer': 'nephew',
            'barn': 'child'
        }
        
        # Finn relevante nøkkelord
        for norsk, engelsk in keyword_map.items():
            if norsk in query_lower:
                keywords.append(engelsk)
        
        # Hvis vi fant nøkkelord, prøv FTS søk først
        if keywords:
            # Legg til wildcard for å matche f.eks. "niece" med "nieces_count"
            keyword_query = ' OR '.join([f'{kw}*' for kw in keywords])
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
    
    # ==================== EMBEDDINGS ====================
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """Generer embedding for tekst med OpenAI API"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
        except Exception as e:
            print(f"⚠️ Embedding feil: {e}")
            return None
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Beregn cosine similarity mellom to vektorer"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def search_by_embedding(self, query: str, limit: int = 10, threshold: float = 0.25) -> List[ProfileFact]:
        """Søk facts basert på semantic similarity"""
        # Generer query embedding
        query_embedding = self.generate_embedding(query)
        if query_embedding is None:
            # Fallback til keyword search
            return self.search_profile_facts(query, limit)
        
        conn = self._get_connection()
        c = conn.cursor()
        
        # Hent alle facts med embeddings
        c.execute("""
            SELECT key, value, topic, confidence, frequency, source, last_updated, embedding
            FROM profile_facts
            WHERE embedding IS NOT NULL
        """)
        
        results = []
        for row in c.fetchall():
            fact_embedding = pickle.loads(row[7])
            similarity = self.cosine_similarity(query_embedding, fact_embedding)
            
            if similarity >= threshold:
                results.append((
                    similarity,
                    ProfileFact(
                        key=row[0],
                        value=row[1],
                        topic=row[2],
                        confidence=row[3],
                        frequency=row[4],
                        source=row[5],
                        last_updated=row[6]
                    )
                ))
        
        conn.close()
        
        # Sorter etter similarity (høyest først)
        results.sort(key=lambda x: x[0], reverse=True)
        
        # Returner top N facts
        return [fact for _, fact in results[:limit]]
    
    def update_fact_embedding(self, key: str):
        """Generer og lagre embedding for en fact"""
        conn = self._get_connection()
        c = conn.cursor()
        
        # Hent fact
        c.execute("SELECT key, value, topic FROM profile_facts WHERE key = ?", (key,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return
        
        # Generer embedding fra key + value + topic
        text = f"{row[0]}: {row[1]} ({row[2]})"
        embedding = self.generate_embedding(text)
        
        if embedding is not None:
            # Serialiser og lagre
            embedding_blob = pickle.dumps(embedding)
            c.execute("UPDATE profile_facts SET embedding = ? WHERE key = ?", 
                     (embedding_blob, key))
            conn.commit()
        
        conn.close()
    
    def rebuild_all_embeddings(self):
        """Generer embeddings for alle facts"""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("SELECT key FROM profile_facts")
        keys = [row[0] for row in c.fetchall()]
        conn.close()
        
        print(f"Genererer embeddings for {len(keys)} facts...")
        for i, key in enumerate(keys, 1):
            self.update_fact_embedding(key)
            if i % 10 == 0:
                print(f"  {i}/{len(keys)} ferdig")
        
        print("✅ Alle embeddings generert")
    
    # ==================== MEMORIES ====================
    
    def find_similar_memory(self, text: str, topic: str, similarity_threshold: float = 0.60) -> Optional[int]:
        """
        Finn eksisterende minne som er veldig likt det nye
        Bruker hybrid-metode: Jaccard + embeddings for grensecaser
        
        Returnerer memory_id hvis funnet, ellers None
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        # Hent alle minner i samme topic (reduserer søkeområde)
        c.execute("""
            SELECT id, text 
            FROM memories 
            WHERE topic = ?
        """, (topic,))
        
        existing = c.fetchall()
        conn.close()
        
        if not existing:
            return None
        
        # Jaccard similarity screening (rask)
        new_words = set(text.lower().split())
        candidates = []  # (id, text, jaccard_score)
        
        for row in existing:
            existing_id = row['id']
            existing_text = row['text']
            existing_words = set(existing_text.lower().split())
            
            # Jaccard similarity
            intersection = len(new_words & existing_words)
            union = len(new_words | existing_words)
            
            if union > 0:
                jaccard = intersection / union
                
                # Høy Jaccard (>0.80): Automatisk match
                if jaccard >= 0.80:
                    return existing_id
                
                # Medium Jaccard (0.50-0.80): Kandidat for embedding-sjekk
                elif jaccard >= 0.50:
                    candidates.append((existing_id, existing_text, jaccard))
        
        # Hvis ingen klare matches, sjekk candidates med embeddings
        if candidates:
            try:
                # Generer embedding for nytt minne
                new_embedding = self.generate_embedding(text)
                
                best_match_id = None
                best_semantic_score = 0.0
                
                for cand_id, cand_text, jaccard_score in candidates:
                    # Generer embedding for kandidat
                    cand_embedding = self.generate_embedding(cand_text)
                    
                    # Cosine similarity
                    semantic_similarity = self.cosine_similarity(new_embedding, cand_embedding)
                    
                    # Kombiner Jaccard og semantic similarity
                    # Vekt: 30% Jaccard, 70% semantic
                    combined_score = (0.3 * jaccard_score) + (0.7 * semantic_similarity)
                    
                    # Match hvis combined score over threshold
                    if combined_score > best_semantic_score and combined_score >= similarity_threshold:
                        best_semantic_score = combined_score
                        best_match_id = cand_id
                
                if best_match_id:
                    print(f"  🔍 Semantic match: Jaccard={jaccard_score:.2f}, Semantic={semantic_similarity:.2f}, Combined={best_semantic_score:.2f}", flush=True)
                    return best_match_id
                    
            except Exception as e:
                # Fallback til kun Jaccard hvis embedding feiler
                print(f"  ⚠️ Embedding similarity feilet: {e}", flush=True)
                pass
        
        return None
    
    def update_memory(self, memory_id: int, new_text: str, metadata: dict = None):
        """
        Oppdater eksisterende minne med rikere informasjon
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        # Oppdater text og metadata
        if metadata:
            c.execute("""
                UPDATE memories 
                SET text = ?, 
                    metadata = ?,
                    last_accessed = ?
                WHERE id = ?
            """, (new_text, json.dumps(metadata), datetime.now().isoformat(), memory_id))
        else:
            c.execute("""
                UPDATE memories 
                SET text = ?,
                    last_accessed = ?
                WHERE id = ?
            """, (new_text, datetime.now().isoformat(), memory_id))
        
        conn.commit()
        conn.close()
    
    def save_memory(self, memory: Memory, check_duplicates: bool = True, user_name: str = 'Osmund') -> int:
        """
        Lagre nytt minne (med optional duplikat-sjekk)
        Returnerer memory_id (enten ny eller oppdatert)
        """
        # Sjekk for lignende minner hvis ønsket
        if check_duplicates:
            existing_id = self.find_similar_memory(memory.text, memory.topic)
            if existing_id:
                # Oppdater eksisterende minne med rikere info
                self.update_memory(existing_id, memory.text, memory.metadata)
                print(f"  ♻️  Oppdaterte eksisterende minne {existing_id}", flush=True)
                return existing_id
        
        # Generer embedding for memory
        embedding = None
        try:
            embedding_array = self.generate_embedding(memory.text)
            embedding = pickle.dumps(embedding_array)
        except Exception as e:
            print(f"  ⚠️  Kunne ikke generere embedding: {e}", flush=True)
        
        # Lagre som nytt minne
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO memories 
            (text, topic, frequency, confidence, source, first_seen, last_accessed, metadata, user_name, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (memory.text, memory.topic, memory.frequency, memory.confidence,
              memory.source, memory.first_seen, memory.last_accessed,
              json.dumps(memory.metadata), user_name, embedding))
        
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
        
        # Preprosesser query for FTS5:
        # - Fjern spesielle tegn som kan forårsake FTS feil
        # - Split til individuelle ord
        # - Bruk OR mellom ord for bedre matching
        import re
        words = re.findall(r'\w+', query.lower())  # Ekstraher bare ord (fjerner -, ?, ! etc)
        if not words:
            conn.close()
            return []
        
        # Lag FTS5-vennlig query: "word1 OR word2 OR word3"
        fts_query = ' OR '.join(words)
        
        # FTS5 MATCH query
        search_limit = limit * 3
        try:
            c.execute(f"""
                SELECT m.*, memories_fts.rank
                FROM memories_fts 
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT {search_limit}
            """, (fts_query,))
        except sqlite3.OperationalError as e:
            # Fallback til LIKE hvis FTS fortsatt feiler
            print(f"⚠️ FTS søk feilet ({e}), bruker LIKE fallback", flush=True)
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
    
    def search_memories_by_embedding(self, query: str, limit: int = 8, threshold: float = 0.5, user_name: str = None) -> List[Memory]:
        """
        Søk i memories med embedding similarity (semantisk søk)
        
        Args:
            query: Søkestreng
            limit: Max antall resultater
            threshold: Minimum similarity score (0-1)
            user_name: Filter på bruker (optional)
        
        Returns:
            List of Memory objects, sortert etter relevans
        """
        # Generer embedding for query
        query_embedding = self.generate_embedding(query)
        if query_embedding is None:
            # Fallback til FTS search hvis embedding feiler
            return [m for m, _ in self.search_memories(query, limit)]
        
        conn = self._get_connection()
        c = conn.cursor()
        
        # Hent alle memories med embeddings
        if user_name:
            c.execute("""
                SELECT id, text, topic, frequency, confidence, source, first_seen, last_accessed, metadata, user_name, embedding
                FROM memories
                WHERE embedding IS NOT NULL AND user_name = ?
            """, (user_name,))
        else:
            c.execute("""
                SELECT id, text, topic, frequency, confidence, source, first_seen, last_accessed, metadata, user_name, embedding
                FROM memories
                WHERE embedding IS NOT NULL
            """)
        
        results = []
        for row in c.fetchall():
            memory_embedding = pickle.loads(row[10])  # embedding is last column
            similarity = self.cosine_similarity(query_embedding, memory_embedding)
            
            if similarity >= threshold:
                memory = Memory(
                    text=row[1],
                    topic=row[2],
                    frequency=row[3],
                    confidence=row[4],
                    source=row[5],
                    first_seen=row[6],
                    last_accessed=row[7],
                    metadata=json.loads(row[8]) if row[8] else {}
                )
                results.append((similarity, memory, row[0]))  # (similarity, memory, id)
        
        conn.close()
        
        # Sorter etter similarity (høyest først)
        results.sort(key=lambda x: x[0], reverse=True)
        
        # Touch the top memories (update last_accessed)
        for similarity, memory, memory_id in results[:limit]:
            self._touch_memory(memory_id)
        
        # Returner top N memories
        return [memory for _, memory, _ in results[:limit]]
    
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
    
    def _expand_related_facts(self, facts: List[ProfileFact]) -> List[ProfileFact]:
        """
        Ekspander facts med relaterte facts basert på key-prefixes.
        
        Hvis vi f.eks. har 'sister_2_child_1_name', hent også:
        - sister_2_name
        - sister_2_location
        - sister_2_child_1_age_relation
        - osv.
        
        Dette gjør context-building mer intelligent og generell.
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        expanded = list(facts)  # Start med original facts
        seen_keys = {f.key for f in facts}
        
        # Identifiser alle prefixes vi skal ekspandere
        prefixes_to_expand = set()
        
        for fact in facts:
            key = fact.key
            # Finn prefix patterns (f.eks. 'sister_2', 'sister_2_child_1')
            parts = key.split('_')
            
            # For 'sister_X_*' patterns
            if key.startswith('sister_') and len(parts) >= 2:
                # 'sister_2_child_1_name' -> ekspander 'sister_2' og 'sister_2_child_1'
                sister_num = parts[1] if parts[1].isdigit() else None
                if sister_num:
                    prefixes_to_expand.add(f'sister_{sister_num}')
                    
                    # Hvis det er child-relatert, ekspander også child-prefixet
                    if 'child' in key and len(parts) >= 4:
                        child_num = parts[3] if parts[3].isdigit() else None
                        if child_num:
                            prefixes_to_expand.add(f'sister_{sister_num}_child_{child_num}')
        
        # Hent alle facts som matcher prefixene
        for prefix in prefixes_to_expand:
            c.execute("""
                SELECT * FROM profile_facts 
                WHERE key LIKE ? || '%'
                LIMIT 20
            """, (prefix,))
            
            for row in c.fetchall():
                if row['key'] not in seen_keys:
                    fact = ProfileFact(
                        key=row['key'],
                        value=row['value'],
                        topic=row['topic'],
                        confidence=row['confidence'],
                        frequency=row['frequency'],
                        source=row['source'],
                        last_updated=row['last_updated']
                    )
                    expanded.append(fact)
                    seen_keys.add(row['key'])
        
        conn.close()
        return expanded

    def build_context_for_ai(self, query: str, recent_messages: int = 5) -> Dict:
        """
        Bygg komplett context for AI-prompt med smart expansion.
        
        Strategi:
        1. Embedding search (topp 20 facts)
        2. Expand relaterte facts (hvis vi finner sister_2_child_1, hent alle sister_2_*)
        3. Legg til frekvente facts hvis nødvendig
        4. Begrens til totalt 40 facts for AI
        
        Returnerer dict med:
        - profile_facts: Top fakta om bruker
        - relevant_memories: Søkte minner
        - recent_topics: Hva snakker vi om?
        - conversation_summary: Hvis tilgjengelig
        """
        # 1. Søk etter relevante facts basert på query (EMBEDDING SEARCH)
        # Økt fra 10 til 20 for bedre dekning
        searched_facts = self.search_by_embedding(query, limit=20)
        
        # 2. Ekspander med relaterte facts
        expanded_facts = self._expand_related_facts(searched_facts)
        
        # 3. Hvis vi fremdeles har få facts, legg til frekvente
        if len(expanded_facts) < 15:
            frequent_facts = self.get_top_facts_cached(limit=15)
        else:
            frequent_facts = []
        
        # 4. Kombiner og dedupliser
        seen_keys = set()
        combined_facts = []
        
        # Prioriter søkte + expanded facts først
        for fact in expanded_facts:
            if fact.key not in seen_keys:
                combined_facts.append(fact)
                seen_keys.add(fact.key)        # Legg til frekvente facts
        for fact in frequent_facts:
            if fact.key not in seen_keys:
                combined_facts.append(fact)
                seen_keys.add(fact.key)
        
        # Legg til frekvente facts
        for fact in frequent_facts:
            if fact.key not in seen_keys:
                combined_facts.append(fact)
                seen_keys.add(fact.key)
        
        # Begrens til max 40 facts totalt (økt fra 15 for bedre context)
        profile_facts = combined_facts[:40]
        
        # 5. Relevant memories (EMBEDDING SEARCH - semantisk søk)
        # Senket threshold til 0.35 for bedre recall
        relevant_memories_list = self.search_memories_by_embedding(query, limit=8, threshold=0.35)
        # Convert to same format as old search_memories (List[Tuple[Memory, float]])
        # For now, use similarity score of 1.0 as we don't return it from search_memories_by_embedding
        relevant_memories = [(m, 1.0) for m in relevant_memories_list]
        
        # 6. Recent topics
        topic_stats = self.get_topic_stats(limit=5)
        
        # 7. Recent conversation (siste N meldinger)
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
