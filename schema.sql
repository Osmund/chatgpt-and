-- ChatGPT Duck - Complete Database Schema
-- Last updated: 2026-02-02
-- Denne filen inneholder det komplette database-schemaet for duck_memory.db

-- ============================================================================
-- CORE MEMORY TABLES
-- ============================================================================

-- Messages: Alle samtaler lagres permanent
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_text TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    session_id TEXT,
    user_name TEXT DEFAULT 'Osmund',
    metadata TEXT
);

-- Profile facts: Strukturerte fakta om brukere
CREATE TABLE IF NOT EXISTS profile_facts (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    topic TEXT NOT NULL,  -- family, work, personal, hobby, health, etc.
    confidence REAL DEFAULT 1.0,
    frequency INTEGER DEFAULT 1,
    source TEXT DEFAULT 'user',
    last_updated TEXT NOT NULL,
    metadata TEXT,
    embedding BLOB  -- Vector embedding for semantisk søk
);

-- Memories: Episodiske minner (søkbare)
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    topic TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'extracted',
    first_seen TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    user_name TEXT DEFAULT 'Osmund',
    metadata TEXT,
    embedding BLOB  -- Vector embedding for semantisk søk
);

-- Topic stats: Statistikk over samtaleemner
CREATE TABLE IF NOT EXISTS topic_stats (
    topic TEXT PRIMARY KEY,
    mention_count INTEGER DEFAULT 0,
    last_mentioned TEXT NOT NULL,
    avg_importance REAL DEFAULT 1.0
);

-- Session summaries: Sammendrag av samtaler
CREATE TABLE IF NOT EXISTS session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    topics TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);

-- Image history: Metadata om mottatte bilder
CREATE TABLE IF NOT EXISTS image_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT NOT NULL,
    sender TEXT NOT NULL,
    sender_relation TEXT,
    description TEXT NOT NULL,
    categories TEXT,
    message_text TEXT,
    source_url TEXT,
    people_in_image TEXT,
    timestamp TEXT NOT NULL,
    accessed_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    metadata TEXT
);

-- Users: Multi-user support
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    relation_to_primary TEXT,  -- "søster", "far", "venn", "owner", etc.
    first_seen TEXT NOT NULL,
    last_active TEXT NOT NULL,
    total_messages INTEGER DEFAULT 0,
    metadata TEXT  -- JSON: {matched_fact_key: "sister_1_name", etc}
);

-- ============================================================================
-- SMS / COMMUNICATION TABLES
-- ============================================================================

-- SMS contacts: Personer Samantha kan sende SMS til
CREATE TABLE IF NOT EXISTS sms_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    relation TEXT,
    priority INTEGER DEFAULT 5,
    max_daily_messages INTEGER DEFAULT 3,
    preferred_hours_start INTEGER DEFAULT 8,
    preferred_hours_end INTEGER DEFAULT 22,
    total_sent INTEGER DEFAULT 0,
    total_received INTEGER DEFAULT 0,
    last_sent_at TEXT,
    last_received_at TEXT,
    enabled BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- SMS history: Logg over sendte/mottatte SMS
CREATE TABLE IF NOT EXISTS sms_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    direction TEXT,  -- 'sent' eller 'received'
    message TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    boredom_level REAL,
    twilio_sid TEXT,
    FOREIGN KEY (contact_id) REFERENCES sms_contacts(id)
);

-- Boredom state: Samanthas kedsomhetsnivå
CREATE TABLE IF NOT EXISTS boredom_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_level REAL DEFAULT 0.0,
    threshold REAL DEFAULT 7.0,
    rate REAL DEFAULT 0.5,
    last_check TEXT,
    last_trigger TEXT,
    enabled BOOLEAN DEFAULT 1
);

-- Hunger state: Tamagotchi-style hunger tracking
CREATE TABLE IF NOT EXISTS hunger_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_level REAL DEFAULT 0.0,
    last_meal_time TEXT,
    next_meal_time TEXT,
    last_announcement TEXT,
    last_sms_nag TEXT,
    meals_today INTEGER DEFAULT 0,
    fed_today BOOLEAN DEFAULT 0
);

-- ============================================================================
-- FULL-TEXT SEARCH TABLES (FTS5)
-- ============================================================================

-- FTS5 for memories: Rask søking i minner
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts 
USING fts5(text, content='memories', content_rowid='id', 
          tokenize='unicode61 remove_diacritics 0');

-- FTS5 for profile_facts: Unicode-basert søk
CREATE VIRTUAL TABLE IF NOT EXISTS profile_facts_fts 
USING fts5(key, value, topic, content='profile_facts', content_rowid='rowid',
          tokenize='unicode61 remove_diacritics 0');

-- Trigram-tabell for fuzzy matching av norske ord
CREATE VIRTUAL TABLE IF NOT EXISTS profile_facts_trigram
USING fts5(key, value, topic, content='profile_facts', content_rowid='rowid',
          tokenize='trigram');

-- ============================================================================
-- TRIGGERS FOR FTS SYNC
-- ============================================================================

-- Memories triggers
CREATE TRIGGER IF NOT EXISTS memories_ai 
AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, text) 
    VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad 
AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, text) 
    VALUES('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS memories_au 
AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, text) 
    VALUES('delete', old.id, old.text);
    INSERT INTO memories_fts(rowid, text) 
    VALUES (new.id, new.text);
END;

-- Profile facts triggers
CREATE TRIGGER IF NOT EXISTS profile_facts_ai 
AFTER INSERT ON profile_facts BEGIN
    INSERT INTO profile_facts_fts(rowid, key, value, topic) 
    VALUES (new.rowid, new.key, new.value, new.topic);
    INSERT INTO profile_facts_trigram(rowid, key, value, topic) 
    VALUES (new.rowid, new.key, new.value, new.topic);
END;

CREATE TRIGGER IF NOT EXISTS profile_facts_ad 
AFTER DELETE ON profile_facts BEGIN
    INSERT INTO profile_facts_fts(profile_facts_fts, rowid, key, value, topic) 
    VALUES('delete', old.rowid, old.key, old.value, old.topic);
    INSERT INTO profile_facts_trigram(profile_facts_trigram, rowid, key, value, topic) 
    VALUES('delete', old.rowid, old.key, old.value, old.topic);
END;

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
END;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_processed ON messages(processed, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_name, timestamp DESC);

-- Memories indexes
CREATE INDEX IF NOT EXISTS idx_memories_topic ON memories(topic);
CREATE INDEX IF NOT EXISTS idx_memories_frequency ON memories(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_memories_accessed ON memories(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_name, last_accessed DESC);
