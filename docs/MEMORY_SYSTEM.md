# ChatGPT Duck - Memory System Documentation

## Oversikt

Minnessystemet gir ChatGPT Duck evnen til å huske samtaler, fakta om brukeren, og læring mellom sesjoner. Systemet består av tre hovedkomponenter som jobber sammen for å gi persistent, intelligent minne uten å påvirke ytelsen.

## Arkitektur

```
┌─────────────────────────────────────────────────────────────────┐
│                     ChatGPT Duck Main App                       │
│                    (chatgpt_voice.py)                           │
│  - Henter minne-kontekst før hver respons                      │
│  - Lagrer alle meldinger til database                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Uses MemoryManager
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Memory Manager (Core)                         │
│                    (duck_memory.py)                             │
│  - SQLite database management                                  │
│  - FTS5 full-text search                                       │
│  - Vekted scoring & ranking                                    │
│  - In-memory caching (5 min TTL)                               │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Reads/Writes
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                    SQLite Database                              │
│                  (duck_memory.db)                               │
│                                                                 │
│  Tables:                                                        │
│  - messages          (alle samtaler)                           │
│  - profile_facts     (strukturerte fakta)                      │
│  - memories          (episodiske minner)                       │
│  - topic_stats       (emnestatistikk)                          │
│  - session_summaries (session sammendrag)                      │
│  - memories_fts      (FTS5 search index)                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Processed by
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│              Memory Worker (Background)                         │
│             (duck_memory_worker.py)                             │
│  - Kjører som systemd service                                  │
│  - Ekstraherer minner via gpt-4o-mini                          │
│  - Prosesserer 5 meldinger per batch                           │
│  - Nice=10 (lav CPU-prioritet)                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│           Memory Hygiene (Maintenance)                          │
│            (duck_memory_hygiene.py)                             │
│  - Kjører daglig kl 03:00 (systemd timer)                     │
│  - Decay gamle minner (30+ dager)                             │
│  - Sletter low-confidence data                                 │
│  - Vacuum database                                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Web Control Panel (UI)                             │
│               (duck-control.py)                                 │
│  - Memory stats dashboard                                      │
│  - View/search/delete facts & memories                         │
│  - REST API for memory management                              │
└─────────────────────────────────────────────────────────────────┘
```

## Komponenter

### 1. duck_memory.py (Core Memory Manager)

**Ansvar:**
- Database management (SQLite)
- Full-text search (FTS5)
- Scoring og ranking
- Caching (in-memory)
- Metrics tracking

**Klasser:**
- `ProfileFact` - Strukturert fakta om bruker
- `Memory` - Episodisk minne
- `MemoryMetrics` - Performance metrics
- `MemoryManager` - Hovedklasse

**Database Schema:**

```sql
-- Alle meldinger lagres permanent
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    user_text TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    session_id TEXT,
    metadata TEXT
);

-- Strukturerte fakta om brukeren
CREATE TABLE profile_facts (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    topic TEXT NOT NULL,  -- family, work, personal, hobby, etc.
    confidence REAL DEFAULT 1.0,
    frequency INTEGER DEFAULT 1,
    source TEXT DEFAULT 'user',
    last_updated TEXT NOT NULL,
    metadata TEXT
);

-- Episodiske minner (søkbare)
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    topic TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'extracted',
    first_seen TEXT NOT NULL,
    last_accessed TEXT,
    metadata TEXT
);

-- FTS5 for rask søking
CREATE VIRTUAL TABLE memories_fts USING fts5(
    text,
    content=memories,
    content_rowid=id
);

-- Topic statistikk
CREATE TABLE topic_stats (
    topic TEXT PRIMARY KEY,
    mention_count INTEGER DEFAULT 0,
    last_mentioned TEXT,
    avg_importance REAL DEFAULT 1.0
);

-- Session sammendrag
CREATE TABLE session_summaries (
    session_id TEXT PRIMARY KEY,
    summary TEXT,
    message_count INTEGER,
    start_time TEXT,
    end_time TEXT,
    topics TEXT
);
```

**Vekted Scoring:**

Relevans-score beregnes som:
```
score = base_weight × frequency_multiplier × recency_decay × confidence

hvor:
- base_weight = topic weights (family: 1.5, work: 1.3, etc.)
- frequency_multiplier = 1 + log(frequency + 1) × 0.3
- recency_decay = exp(-days_since / 30)
- confidence = 0.0-1.0
```

**Caching:**
- Top facts: 5 min TTL
- Session state: 5 min TTL
- Cache hit rate: ~87%

**Performance:**
- FTS5 search: 9.73ms gjennomsnitt
- Total overhead: <50ms
- Memory usage: minimal (~1-2 MB)

### 2. duck_memory_worker.py (Background Worker)

**Ansvar:**
- Asynkron prosessering av meldinger
- LLM-basert memory extraction
- Ingen påvirkning på hovedapp latency

**Systemd Service:**
```ini
[Service]
Type=simple
User=admog
WorkingDirectory=/home/admog/Code/chatgpt-and
ExecStart=/home/admog/Code/chatgpt-and/.venv/bin/python duck_memory_worker.py
Restart=always
Nice=10  # Lav CPU-prioritet
```

**Konfigurasjon:**
```python
CHECK_INTERVAL = 5      # Sjekk hver 5. sekund
BATCH_SIZE = 5          # Prosesser 5 meldinger per batch
MODEL = "gpt-4o-mini"   # Balanserer kvalitet og kostnad
```

**Extraction Prompt:**

Worker-en bruker en detaljert prompt for å ekstrahere:

1. **Profile Facts** (strukturerte fakta)
   - Format: `key=value, topic, confidence`
   - Spesielt viktig for familie-informasjon:
     - Individuelle medlemmer: `father_name`, `sister_1_name`, etc.
     - Bursdager: `sister_1_birthday`, `father_birthday`
     - Relasjoner: `sister_1_age_relation` (eldste/yngste)
     - Lokasjoner: `father_location`, `sister_1_location`

2. **Episodic Memories** (hendelser)
   - Format: `text, topic, confidence`
   - Konkrete hendelser og planer
   - Familieinteraksjoner

3. **Topics** (kategorisering)
   - Available: family, hobby, work, projects, technical, health, pets, preferences, weather, time, general
   - Importance score: 0.0-1.0

**Output Example:**
```json
{
  "profile_facts": [
    {"key": "father_name", "value": "Arvid", "topic": "family", "confidence": 1.0},
    {"key": "sister_1_name", "value": "Miriam", "topic": "family", "confidence": 1.0}
  ],
  "memories": [
    {"text": "Brukeren planlegger fjelltur", "topic": "hobby", "confidence": 0.9}
  ],
  "topics": ["family", "hobby"]
}
```

**Stats Logging:**
- Stats printes hvert 5. minutt
- Viser: totale meldinger prosessert, facts/memories ekstrahert
- Synlig i journalctl

### 3. duck_memory_hygiene.py (Maintenance)

**Ansvar:**
- Daglig vedlikehold av database
- Decay av gamle minner
- Cleanup av low-confidence data
- Database optimization

**Systemd Timer:**
```ini
[Timer]
OnCalendar=03:00
Persistent=true
```

**Maintenance Tasks:**

1. **Decay Old Memories** (30+ dager)
   ```python
   confidence = confidence * 0.9
   ```

2. **Delete Low-Confidence Data** (< 0.2)
   - Sletter episodiske minner med lav confidence
   - Bevarer profile facts (mer stabil info)

3. **Delete Old Messages** (90+ dager)
   - Rydder opp i message history
   - Holder database liten

4. **VACUUM Database**
   - Komprimerer database
   - Frigjør diskplass

**Output Example:**
```
📊 BEFORE:
  Messages: 150
  Memories: 45
  Database size: 2.5 MB

🔄 MAINTENANCE:
  ✅ Decayed 12 old memories
  ✅ Deleted 3 low-confidence memories
  ✅ Deleted 50 old messages
  ✅ Vacuumed database

📊 AFTER:
  Messages: 100
  Memories: 42
  Database size: 1.8 MB
```

### 4. Integration med chatgpt_voice.py

**Modifikasjoner:**

```python
from duck_memory import MemoryManager

# Initialize
memory_manager = MemoryManager()

# Build context before response
def build_memory_context(user_text: str) -> str:
    # Top profile facts
    facts = memory_manager.get_profile_facts(limit=8)
    
    # Relevant memories (FTS5 search)
    memories, scores = memory_manager.search_memories(user_text, limit=5)
    
    # Recent topics
    topics = memory_manager.get_recent_topics(days=7)
    
    context = "CONTEXT:\n"
    if facts:
        context += "\nAbout user:\n"
        for fact in facts:
            context += f"- {fact.key}: {fact.value}\n"
    
    if memories:
        context += "\nRelevant memories:\n"
        for memory in memories:
            context += f"- {memory.text}\n"
    
    return context

# Save message after response
memory_manager.save_message(user_text, ai_response)
```

**Performance Impact:**
- Memory context building: ~20ms
- Message saving: ~5ms
- FTS5 search: ~10ms
- **Total overhead: <50ms** ✅

### 5. Web UI (duck-control.py)

**API Endpoints:**

```python
# GET endpoints
GET /api/memory/stats           # Statistikk
GET /api/memory/profile         # Alle profile facts
GET /api/memory/memories?q=...  # Søk i minner
GET /api/memory/topics          # Topic statistikk
GET /api/memory/conversations   # Samtalehistorikk

# DELETE endpoints
DELETE /api/memory/profile/{key}  # Slett fact
DELETE /api/memory/memories/{id}  # Slett minne
```

**UI Features:**

1. **Stats Dashboard**
   - Message count
   - Profile facts count
   - Memories count
   - Topics count
   - Embedding status (ready/generating)
   - Worker status (running/stopped)

2. **Memory Settings (⚙️ Minneinnstillinger)**
   - **Max Kontekst Fakta** (1-200): Slider med live preview
   - **Embedding Søk Limit** (10-100): Justerer søkebredde
   - **Minnegrense** (1-20): Episodiske minner i kontekst
   - **Minne Threshold** (0.2-0.8): Similarity threshold
   - ✓/✗ status feedback ved lagring
   - Lagres umiddelbart i database
   - Brukes ved neste query (ingen restart nødvendig)

3. **Profile Facts Viewer**
   - Color-coded confidence (grønn: 80%+, oransje: 50-80%, rød: <50%)
   - Frequency counter
   - Topic categorization
   - Delete button (🗑️)
   - Search/filter funksjon

4. **Memory Search**
   - FTS5 full-text search
   - Score-based ranking
   - Topic filtering
   - Delete button (🗑️)
   - Real-time search

5. **Topic Statistics**
   - Bar chart visualization
   - Mention counts
   - Last mentioned timestamp

6. **Quick Facts**
   - Top 10 mest brukte facts
   - One-click access

**UI Design:**
- Responsive layout (mobilvennlig)
- Diskrete delete buttons (grå → rød ved hover)
- Absolute positioning for minimal space
- Auto-refresh hvert 10. sekund
- Real-time slider updates med visuell feedback

## Installation

### 1. Files
```bash
duck_memory.py              # Core memory manager
duck_memory_worker.py       # Background worker
duck_memory_hygiene.py      # Daily maintenance
duck-memory-worker.service  # Systemd service
duck-memory-hygiene.service # Systemd service
duck-memory-hygiene.timer   # Systemd timer
```

### 2. Dependencies
```bash
# Already included in requirements.txt
# No additional dependencies needed
```

### 3. Systemd Services
```bash
# Run installation script
./scripts/install-services.sh

# Or manually:
sudo cp services/duck-memory-worker.service /etc/systemd/system/
sudo cp services/duck-memory-hygiene.service /etc/systemd/system/
sudo cp services/duck-memory-hygiene.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable duck-memory-worker.service
sudo systemctl enable duck-memory-hygiene.timer
sudo systemctl start duck-memory-worker.service
sudo systemctl start duck-memory-hygiene.timer
```

### 4. Verify Installation
```bash
# Check services
sudo systemctl status duck-memory-worker.service
sudo systemctl status duck-memory-hygiene.timer

# Check logs
journalctl -u duck-memory-worker.service -f
journalctl -u duck-memory-hygiene.service

# Check database
ls -lh duck_memory.db
```

## Usage

### Programmatic Access

```python
from duck_memory import MemoryManager

# Initialize
memory = MemoryManager()

# Save message
memory.save_message("Hei, hvordan går det?", "Hei! Det går bra, takk!")

# Get profile facts
facts = memory.get_profile_facts(limit=10)
for fact in facts:
    print(f"{fact.key}: {fact.value} (confidence: {fact.confidence})")

# Search memories
results = memory.search_memories("familie", limit=5)
for mem, score in results:
    print(f"[{score:.2f}] {mem.text}")

# Get stats
stats = memory.get_stats()
print(f"Messages: {stats['message_count']}")
print(f"Facts: {stats['fact_count']}")
print(f"Memories: {stats['memory_count']}")
```

### Web UI

Access at: `http://<raspberry-pi-ip>:3000`

1. **View Memory Stats**
   - Click "👁️ Vis minner"
   - See counts and statistics

2. **View Profile Facts**
   - Scroll to "Profile Fakta"
   - See all stored facts
   - Click 🗑️ to delete unwanted facts

3. **Search Memories**
   - Use search box in "Episodiske Minner"
   - FTS5 full-text search
   - Click 🗑️ to delete memories

4. **View Topics**
   - See bar chart of topics
   - Sorted by frequency

### Manual Database Access

```bash
# Install DB Browser (optional)
sudo apt install sqlitebrowser
sqlitebrowser ~/Code/chatgpt-and/duck_memory.db

# Or use Python
python3
>>> import sqlite3
>>> conn = sqlite3.connect('duck_memory.db')
>>> c = conn.cursor()
>>> c.execute("SELECT * FROM profile_facts").fetchall()
```

## Maintenance

### Re-processing Messages

If you update the extraction logic, you can re-process old messages:

```python
import sqlite3
conn = sqlite3.connect('duck_memory.db')
c = conn.cursor()

# Mark messages as unprocessed
c.execute("UPDATE messages SET processed = 0 WHERE id >= 10 AND id <= 20")
conn.commit()
conn.close()

# Worker will pick them up within 5 seconds
```

### Manual Cleanup

```bash
# Run hygiene manually
python3 duck_memory_hygiene.py

# Or via systemd
sudo systemctl start duck-memory-hygiene.service
```

### Database Backup

```bash
# Simple backup
cp duck_memory.db duck_memory.db.backup

# With timestamp
cp duck_memory.db "duck_memory_$(date +%Y%m%d_%H%M%S).db"
```

### Monitoring

```bash
# Watch worker logs
journalctl -u duck-memory-worker.service -f

# Check last hygiene run
journalctl -u duck-memory-hygiene.service | tail -50

# Database size
ls -lh duck_memory.db

# Quick stats
python3 -c "from duck_memory import MemoryManager; m = MemoryManager(); print(m.get_stats())"
```

## Performance Tuning

### Adjust Worker Settings

Edit `duck_memory_worker.py`:
```python
CHECK_INTERVAL = 10  # Check every 10 seconds instead of 5
BATCH_SIZE = 10      # Process 10 messages per batch
```

### Adjust Hygiene Schedule

Edit timer: `sudo systemctl edit duck-memory-hygiene.timer`
```ini
[Timer]
OnCalendar=04:00  # Run at 4 AM instead of 3 AM
```

### Adjust Cache TTL

Edit `duck_memory.py`:
```python
self.CACHE_TTL = 600  # 10 minutes instead of 5
```

### Database Optimization

```sql
-- Add indexes if queries are slow
CREATE INDEX idx_messages_timestamp ON messages(timestamp);
CREATE INDEX idx_memories_topic ON memories(topic);

-- Analyze query plans
EXPLAIN QUERY PLAN SELECT ...;
```

## Troubleshooting

### Worker Not Processing

```bash
# Check if running
sudo systemctl status duck-memory-worker.service

# Restart
sudo systemctl restart duck-memory-worker.service

# Check logs
journalctl -u duck-memory-worker.service -n 50

# Common issues:
# - OPENAI_API_KEY not set
# - Database locked (another process using it)
# - Permission issues
```

### Database Locked

```python
# Add timeout to connections
conn = sqlite3.connect('duck_memory.db', timeout=30.0)
```

### High Memory Usage

```bash
# Check cache hit rate
python3 -c "from duck_memory import MemoryManager; m = MemoryManager(); print(m.metrics.cache_hit_rate)"

# If low (<70%), increase CACHE_TTL
# If high (>90%), cache is working well
```

### Slow Searches

```bash
# Check search latency
python3 -c "from duck_memory import MemoryManager; m = MemoryManager(); print(m.metrics.avg_search_latency)"

# If >100ms:
# 1. Check database size
# 2. Run VACUUM
# 3. Add indexes
```

## Configuration

### Memory Settings (Configurable via Web UI)

Alle viktige memory-innstillinger kan justeres via kontrollpanelet under "🧠 Andas Minne" → "⚙️ Minneinnstillinger":

#### 1. Max Kontekst Fakta (1-200)
- **Default**: 100
- **Beskrivelse**: Totalt antall fakta som sendes til AI i hver query
- **Bruk**: Øk for bedre kontekst, senk for raskere respons
- **Database key**: `max_context_facts`

#### 2. Embedding Søk Limit (10-100)
- **Default**: 30
- **Beskrivelse**: Hvor mange facts embedding-søket returnerer før expansion
- **Bruk**: Øk for bredere søk, senk for mer fokusert
- **Database key**: `embedding_search_limit`
- **Config fallback**: `MEMORY_EMBEDDING_SEARCH_LIMIT` i `duck_config.py`

#### 3. Minnegrense (1-20)
- **Default**: 8
- **Beskrivelse**: Antall episodiske minner som inkluderes i kontekst
- **Bruk**: Øk for mer samtalehistorikk, senk for kortere context
- **Database key**: `memory_limit`
- **Config fallback**: `MEMORY_LIMIT` i `duck_config.py`

#### 4. Minne Threshold (0.2-0.8)
- **Default**: 0.35
- **Beskrivelse**: Similarity threshold for embedding search (lavere = mer inkluderende)
- **Bruk**: Senk for flere treff, øk for mer relevante treff
- **Database key**: `memory_threshold`
- **Config fallback**: `MEMORY_THRESHOLD` i `duck_config.py`

### API Endpoints for Settings

```python
# GET alle memory settings
GET /api/settings/memory
# Returns: {status, embedding_search_limit, memory_limit, memory_threshold}

# POST oppdater settings (kan sende én eller flere)
POST /api/settings/memory
# Body: {embedding_search_limit: 40, memory_limit: 10, memory_threshold: 0.4}
# Returns: {success: true, ...updated_values}

# GET max context facts (legacy endpoint)
GET /api/settings/max-context-facts
# Returns: {status, max_context_facts}

# POST oppdater max context facts
POST /api/settings/max-context-facts
# Body: {max_context_facts: 150}
# Returns: {success: true, max_context_facts: 150}
```

### Hvordan innstillingene brukes

```python
# I duck_memory.py build_context_for_ai()

# 1. Les settings fra database (med fallback til config)
embedding_limit = int(settings.get('embedding_search_limit', MEMORY_EMBEDDING_SEARCH_LIMIT))
memory_limit = int(settings.get('memory_limit', MEMORY_LIMIT))
memory_threshold = float(settings.get('memory_threshold', MEMORY_THRESHOLD))
max_facts = int(settings.get('max_context_facts', 100))

# 2. Bruk settings i søk
searched_facts = self.search_by_embedding(query, limit=embedding_limit)
relevant_memories = self.search_memories_by_embedding(
    query, limit=memory_limit, threshold=memory_threshold
)

# 3. Begrens total output
profile_facts = combined_facts[:max_facts]
```

### Storage i Database

Settings lagres i `profile_facts` tabellen med `topic='system'`:

```sql
INSERT INTO profile_facts 
(key, value, topic, confidence, frequency, source, last_updated, metadata)
VALUES 
('embedding_search_limit', '30', 'system', 1.0, 10, 'user', datetime('now'), 
 '{"source": "control_panel"}');
```

## Best Practices

### 1. Profile Facts
- Use consistent key naming: `person_attribute` (e.g., `father_name`, `sister_1_birthday`)
- Keep values concise and structured
- Use high confidence (0.8-1.0) for verified facts
- Use appropriate topics (family, work, personal, etc.)

### 2. Memories
- Keep text concise (1-2 sentences)
- Use descriptive text that's easy to search
- Assign correct topics for better categorization
- Let confidence decay naturally over time

### 3. Performance
- Monitor cache hit rate (target: >80%)
- Keep database size reasonable (<10 MB for typical use)
- Run hygiene regularly (daily recommended)
- Use FTS5 search instead of LIKE queries
- **Tune memory settings** via web UI for optimal balance mellom accuracy og speed

### 4. Privacy
- Memory database contains personal information
- Secure the database file appropriately
- Consider encryption for sensitive deployments
- Regular backups recommended

## Future Enhancements

Potential improvements:

1. **Vector Embeddings**
   - Use sentence-transformers for semantic search
   - Better than FTS5 for conceptual similarity
   - Requires more storage and compute

2. **Context Window Management**
   - Smarter selection of which memories to include
   - Token counting for LLM context limits
   - Priority-based inclusion

3. **Memory Consolidation**
   - Merge similar memories
   - Detect contradictions
   - Update facts based on new information

4. **Multi-user Support**
   - Separate memory spaces per user
   - User identification
   - Privacy controls

5. **Export/Import**
   - JSON export of all memories
   - Import from other systems
   - Backup/restore functionality

6. **Analytics**
   - Conversation trends over time
   - Topic evolution
   - Memory quality metrics

## License

Part of ChatGPT Duck project. See main README for license information.

## Support

For issues or questions:
1. Check logs: `journalctl -u duck-memory-worker.service`
2. Verify services: `systemctl status duck-memory-*`
3. Test database: `python3 -c "from duck_memory import MemoryManager; MemoryManager()"`

## Version History

- **v1.0** (2026-01-11) - Initial release
  - Core memory manager with SQLite
  - FTS5 full-text search
  - Background worker with gpt-4o-mini
  - Daily hygiene maintenance
  - Web UI integration
  - Performance: <50ms overhead, 9.73ms search latency
