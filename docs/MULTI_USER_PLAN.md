# Multi-User Support - Implementeringsplan

**Dato:** 13. januar 2026  
**Feature:** Multi-bruker support for Anda - La flere personer bruke anda med separate minner  
**Status:** ✅ **IMPLEMENTERT** (branch: oDuckberry7)

---

## ✅ Implementasjonsstatus

**Implementert:** 13. januar 2026  
**Branch:** `oDuckberry7`  
**Commits:**
- `463db20` - Multi-user system: database migration, UserManager, og chat integration
- `3866838` - Kontrollpanel: multi-user UI med brukerbytte
- `ec41c21` - Memory worker: track user_name for minner
- `238615a` - Fix ProfileFact: legg til metadata felt og @dataclass
- `de56d5a` - Fix sqlite3.Row compatibility i get_unprocessed_messages

**Testet:**
- ✅ Brukerbytte via voice ("bytt bruker" → "Miriam")
- ✅ Meldinger lagres med riktig user_name
- ✅ Memory worker ekstraherer minner med bruker-attributering
- ✅ Facts forblir globale (delt på tvers av brukere)
- ✅ 30 minutters timeout til Osmund
- ✅ Kontrollpanel viser current user og bruker-liste
- ✅ API endpoints for brukerbytte

**Filer modifisert:**
- `duck_user_manager.py` - Ny fil, user session management
- `chatgpt_voice.py` - User context i prompts, brukerbytte-dialog
- `duck_memory.py` - user_name i Message, save_memory parameter
- `duck_memory_worker.py` - Logger og lagrer minner med user_name
- `duck-control.py` - Multi-user UI, API endpoints
- `scripts/migrate_multi_user.py` - Database migration script

---

## 🎯 Mål
Tillate at flere personer kan snakke med Anda, hvor hver person får sine egne samtaler, minner og facts lagret separat, men alle data er tilgjengelig for primærbruker (Osmund) i kontrollpanel.

## 📋 Krav

### 1. Default Oppførsel
- **Alltid default til Osmund ved reboot**
- Bytt bruker kun på forespørsel ("bytt bruker" kommando)

### 2. Brukerbytte
- Detekter "bytt bruker" kommando
- Spør: "Hvem snakker jeg med?"
- Hvis navn matcher existing fact (f.eks. sister_1_name = Miriam):
  - Bekreft: "Er du Miriam, søsteren til Osmund?"
  - Hvis ja → bytt til Miriam
- Hvis ukjent navn:
  - Spør: "Hva er din relasjon til Osmund?"
  - Lagre som ny bruker

### 3. Session Management
- **30 minutters timeout** → automatisk tilbake til Osmund
- **UNNTATT** hvis:
  - Siste melding < 5 min siden
  - Aktivt i multiturn samtale
- **"Bytt tilbake"** kommando → alltid tilbake til Osmund
- Voice feedback når timeout skjer

### 4. Privacy & Access
- ✅ Osmund ser alt i database
- ✅ Ingen private mode
- ✅ Cross-user memory access (Miriam kan spørre om Osmund)

### 5. Kontrollpanel
- Vis current user status
- Live countdown (tid til timeout)
- Manual override button
- User-filtrert view i database

## 🗄️ Database Endringer

### Nye kolonner
```sql
-- messages tabell
ALTER TABLE messages ADD COLUMN user_name TEXT DEFAULT 'Osmund';

-- memories tabell  
ALTER TABLE memories ADD COLUMN user_name TEXT DEFAULT 'Osmund';

-- profile_facts tabell
-- Ikke user_name her - facts er globale, men source metadata kan ha user info

-- Ny users tabell
CREATE TABLE users (
    username TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    relation_to_primary TEXT,  -- "søster", "far", "venn", etc.
    first_seen TEXT NOT NULL,
    last_active TEXT NOT NULL,
    total_messages INTEGER DEFAULT 0,
    metadata TEXT  -- JSON: {matched_fact_key: "sister_1_name", etc}
);
```

### Migration Script
```python
def migrate_database():
    """Legg til multi-user support i eksisterende database"""
    conn = sqlite3.connect('duck_memory.db')
    c = conn.cursor()
    
    # Sjekk om kolonner allerede eksisterer
    c.execute("PRAGMA table_info(messages)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'user_name' not in columns:
        c.execute("ALTER TABLE messages ADD COLUMN user_name TEXT DEFAULT 'Osmund'")
        c.execute("ALTER TABLE memories ADD COLUMN user_name TEXT DEFAULT 'Osmund'")
        print("✅ Added user_name columns")
    
    # Opprett users tabell
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
    
    # Legg til Osmund som primary user
    c.execute("""
        INSERT OR IGNORE INTO users (username, display_name, relation_to_primary, first_seen, last_active, metadata)
        VALUES ('Osmund', 'Osmund', 'owner', ?, ?, '{"is_primary": true}')
    """, (datetime.now().isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    print("✅ Database migration completed")
```

## 📝 Implementering

### Fase 1: Database & Session State (1-2 timer)

**1.1 Database migration**
- Kjør migration script
- Legg til indexes for user_name
- Test backward compatibility

**1.2 Session state management**
```python
# current_user.json
{
    "username": "Osmund",
    "display_name": "Osmund", 
    "relation": "owner",
    "switched_at": "2026-01-13T12:00:00",
    "timeout_at": "2026-01-13T12:30:00",
    "last_activity": "2026-01-13T12:15:00"
}
```

**Fil:** `/tmp/duck_current_user.json`

**1.3 UserManager klasse**
```python
class UserManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.session_file = "/tmp/duck_current_user.json"
    
    def get_current_user(self) -> Dict:
        """Hent nåværende bruker (default Osmund)"""
        
    def switch_user(self, username: str, relation: str = None) -> bool:
        """Bytt til annen bruker"""
        
    def check_timeout(self) -> bool:
        """Sjekk om timeout skal trigges"""
        
    def find_user_by_name(self, name: str) -> Optional[Dict]:
        """Søk etter bruker i profile_facts eller users tabell"""
        
    def update_activity(self):
        """Oppdater last_activity timestamp"""
```

### Fase 2: Smart Name Matching (1 time)

**2.1 Name matching logic**
```python
def match_name_to_fact(self, name: str) -> Optional[Dict]:
    """
    Søk i profile_facts etter match:
    - sister_1_name, sister_2_name, sister_3_name
    - father_name, mother_name
    - sister_X_husband_name
    - etc.
    
    Returner: {
        'matched_key': 'sister_1_name',
        'display_name': 'Miriam',
        'relation': 'søster'  # Utledet fra key
    }
    """
```

**2.2 Relation extraction**
```python
def extract_relation_from_key(self, key: str) -> str:
    """
    'sister_1_name' → 'søster'
    'father_name' → 'far'
    'sister_2_husband_name' → 'svoger'
    """
```

### Fase 3: Kommando-deteksjon (1 time)

**3.1 Wake word handler endring**
```python
# I chatgpt_voice.py

def handle_user_text(self, user_text: str):
    # Sjekk for brukerbytte-kommandoer FØRST
    if self._is_switch_user_command(user_text):
        self._handle_user_switch()
        return
    
    # Normal samtale...
    
def _is_switch_user_command(self, text: str) -> bool:
    """Detekter 'bytt bruker', 'switch user', etc."""
    keywords = ['bytt bruker', 'ny bruker', 'switch user', 'endre bruker']
    return any(kw in text.lower() for kw in keywords)

def _handle_user_switch(self):
    """Multi-turn samtale for brukerbytte"""
    # 1. Spør om navn
    self.speak("Hvem snakker jeg med?")
    # 2. Lytt til svar
    name_response = self.listen()
    # 3. Match mot database
    match = self.user_manager.find_user_by_name(name_response)
    # 4. Bekreft eller spør om relasjon
    # 5. Switch user
    # 6. Bekreft med voice
```

**3.2 "Bytt tilbake" kommando**
```python
def _is_switch_back_command(self, text: str) -> bool:
    """Detekter 'bytt tilbake', 'jeg er osmund', etc."""
    keywords = ['bytt tilbake', 'jeg er osmund', 'osmund nå']
    return any(kw in text.lower() for kw in keywords)
```

### Fase 4: Timeout Background Thread (30 min)

**4.1 Timeout checker**
```python
def check_user_timeout(self):
    """Kjører i background thread, sjekker hver 60 sekunder"""
    while True:
        time.sleep(60)
        
        current_user = self.user_manager.get_current_user()
        
        # Skip hvis Osmund
        if current_user['username'] == 'Osmund':
            continue
        
        # Sjekk timeout
        if self.user_manager.check_timeout():
            # Sjekk om aktivt i samtale
            last_msg = self.memory_manager.get_last_message_time()
            if (datetime.now() - last_msg).seconds < 300:  # 5 min
                continue  # Ikke timeout midt i samtale
            
            # Switch tilbake
            self.user_manager.switch_user('Osmund')
            self.speak("Jeg går tilbake til Osmund-modus nå.")
```

### Fase 5: Prompt Injection (30 min)

**5.1 Context building endring**
```python
# I build_prompt_with_memory()

current_user = self.user_manager.get_current_user()

if current_user['username'] == 'Osmund':
    identity_section = """
    Du snakker med Osmund, din primære eier og skaperen din.
    Navn: Osmund (Åsmund)
    """
else:
    identity_section = f"""
    Du snakker nå med {current_user['display_name']}, som er {current_user['relation']} til Osmund.
    
    Osmund er din primære eier, men du hjelper gjerne {current_user['display_name']} også.
    Tilpass språk og tone basert på relasjonen.
    
    Du har tilgang til Osmunds minner og facts, men lagre nye minner for {current_user['username']}.
    """
```

**5.2 Memory filtering**
```python
# Når vi bygger context
context = self.memory_manager.build_context_for_ai(
    query=user_text,
    current_user=current_user['username']  # Filter memories
)
```

### Fase 6: Kontrollpanel (30 min)

**6.1 User status indicator**
```javascript
// I duck-control.py HTML
<div id="current-user-status" style="...">
    👤 Snakker med: <strong id="user-name">Osmund</strong>
    <span id="user-relation" style="color: #666;"></span>
    <div id="timeout-countdown" style="display: none;">
        Bytt tilbake om: <strong id="time-left">--</strong>
    </div>
    <button onclick="switchBackToOsmund()">Bytt tilbake til Osmund</button>
</div>
```

**6.2 User filter i database views**
```javascript
// Legg til filter dropdown
<select id="user-filter" onchange="filterByUser()">
    <option value="all">Alle brukere</option>
    <option value="Osmund">Osmund</option>
    <option value="Miriam">Miriam</option>
    <!-- Dynamic fra /api/users -->
</select>
```

**6.3 API endpoints**
```python
# /api/current-user
def get_current_user():
    return json.dumps(user_manager.get_current_user())

# /api/users
def get_all_users():
    return json.dumps(user_manager.get_all_users())

# POST /api/switch-user
def switch_user():
    data = json.loads(request.body)
    user_manager.switch_user(data['username'])
```

## 🧪 Testing Plan

### Test Cases

**TC1: Bytt til eksisterende bruker (Miriam)**
1. Si "bytt bruker"
2. Anda: "Hvem snakker jeg med?"
3. Svar: "Miriam"
4. Anda: "Er du Miriam, søsteren til Osmund?"
5. Svar: "Ja"
6. Anda: "Hyggelig å snakke med deg, Miriam!"
7. Verify: current_user.json = Miriam

**TC2: Bytt til ukjent bruker**
1. Si "bytt bruker"
2. Anda: "Hvem snakker jeg med?"
3. Svar: "Tom"
4. Anda: "Hva er din relasjon til Osmund?"
5. Svar: "Venn"
6. Anda: "Hyggelig å møte deg, Tom!"
7. Verify: users tabell har Tom

**TC3: Timeout etter 30 min**
1. Switch til Miriam
2. Vent 31 minutter (mock time)
3. Verify: Automatisk tilbake til Osmund
4. Verify: Voice feedback gitt

**TC4: Ikke timeout under samtale**
1. Switch til Miriam
2. Start samtale
3. 25 min: Send melding
4. 31 min total: Sjekk
5. Verify: Fortsatt Miriam (aktivitet < 5 min)

**TC5: Manuell bytt tilbake**
1. Switch til Miriam
2. Si "bytt tilbake"
3. Verify: Tilbake til Osmund umiddelbart

**TC6: Memories lagres korrekt**
1. Som Miriam, si "Jeg liker pizza"
2. Verify: memory lagret med user_name='Miriam'
3. Bytt til Osmund
4. Spør: "Hva liker Miriam?"
5. Verify: Anda kan svare (cross-user access)

**TC7: Reboot default**
1. Switch til Miriam
2. Reboot system
3. Verify: current_user.json = Osmund

## 📊 Estimert Tidsbruk

| Fase | Oppgave | Estimat |
|------|---------|---------|
| 1 | Database & Session State | 1-2 timer |
| 2 | Smart Name Matching | 1 time |
| 3 | Kommando-deteksjon | 1 time |
| 4 | Timeout Background | 30 min |
| 5 | Prompt Injection | 30 min |
| 6 | Kontrollpanel | 30 min |
| **Total** | | **4-5 timer** |

## 🚀 Deployment

1. **Backup database** før migration
2. Kjør migration script
3. Test med test-bruker først
4. Deploy kontrollpanel endringer
5. Restart chatgpt-duck service
6. Verifiser default til Osmund

## 📝 Dokumentasjon

### For brukere

**Hvordan bytte bruker:**

**Via voice:**
1. Si wake word ("Samantha" eller "Quack quack")
2. Si "bytt bruker"
3. Anda spør: "Hvem snakker jeg med?"
4. Si ditt navn (f.eks. "Miriam")
5. Hvis navnet er kjent fra profile_facts, får du bekreftelse
6. Hvis ukjent, spør Anda om relasjon til Osmund

**Via kontrollpanel:**
1. Gå til http://192.168.10.138:3000 (eller din Anda IP)
2. Klikk på "👥 Bytt Bruker" knappen
3. Velg bruker fra dropdown eller skriv nytt navn
4. Klikk på bruker i listen

**Timeout-regler:**
- 30 minutters inaktivitet → automatisk tilbake til Osmund
- Timer pauses hvis aktiv samtale (siste melding < 5 min)
- Si "bytt tilbake" for å gå tilbake til Osmund manuelt

**Hvem kan se hva:**
- Alle minner (`memories`) er knyttet til brukeren som sa dem
- Alle facts (`profile_facts`) er globale - alle brukere ser samme facts
- Osmund (owner) kan se alle meldinger, minner og facts i kontrollpanelet
- Cross-user queries fungerer: Miriam kan spørre "Når har Osmund bursdag?"

### For utviklere

**UserManager API:**
```python
from duck_user_manager import UserManager

um = UserManager()

# Hent current user
user = um.get_current_user()
# Returns: {'username': 'Osmund', 'display_name': 'Osmund', 'relation': 'owner', ...}

# Bytt bruker
um.switch_user('Miriam')

# Sjekk timeout
if um.check_timeout():
    um.switch_user('Osmund')

# Finn bruker basert på navn
user = um.find_user_by_name('Miriam')

# Få alle brukere
users = um.get_all_users()
```

**Database schema:**
```sql
-- users tabell
CREATE TABLE users (
    username TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_active TEXT,
    message_count INTEGER DEFAULT 0
);

-- messages med user_name
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    user_text TEXT,
    ai_response TEXT,
    timestamp TEXT,
    user_name TEXT DEFAULT 'Osmund',  -- NY
    ...
);

-- memories med user_name
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    text TEXT,
    topic TEXT,
    user_name TEXT DEFAULT 'Osmund',  -- NY
    ...
);

-- profile_facts (globale, ingen user_name)
CREATE TABLE profile_facts (
    key TEXT PRIMARY KEY,
    value TEXT,
    -- Ingen user_name - facts er delt
    ...
);
```

**Session management:**
- Session lagres i `/tmp/duck_current_user.json`
- Inneholder: username, display_name, relation, timeout_at, last_activity
- Leses ved hver wake word for timeout-sjekk
- Oppdateres ved brukerbytte og meldinger

**Testing procedures:**
```bash
# Test brukerbytte
python3 -c "
from duck_user_manager import UserManager
um = UserManager()
um.switch_user('TestUser')
print(um.get_current_user())
"

# Test melding med user_name
python3 -c "
from duck_memory import MemoryManager
mm = MemoryManager()
msg_id = mm.save_message('Test message', 'Test response', user_name='TestUser')
print(f'Message {msg_id} saved')
"

# Sjekk at worker lagrer med user_name
sudo journalctl -u duck-memory-worker -n 20 | grep "Memory"
# Forvent: "✅ Memory [TestUser]: ..."
```

**Migrering til multi-user:**
```bash
# Kjør migrasjonsskriptet
cd /home/admog/Code/chatgpt-and
python3 scripts/migrate_multi_user.py

# Restart tjenester
sudo systemctl restart chatgpt-duck
sudo systemctl restart duck-memory-worker

# Verifiser
python3 -c "from duck_user_manager import UserManager; print(UserManager().get_current_user())"
```

## ⚠️ Edge Cases

1. **To personer med samme navn**
   - "Sven" (sister_1_husband og sister_3_husband)
   - Løsning: Spør "Sven som er gift med Miriam eller Gine?"

2. **Ukjent barn**
   - Sivert (8 år) bruker anda
   - Løsning: Registrer som user, men ingen special handling

3. **Flere bytte-forsøk raskt etter hverandre**
   - Løsning: Cooldown på 10 sekunder mellom switches

4. **Timeout mens Anda snakker**
   - Løsning: Sjekk kun mellom samtaler, aldri midt i respons

5. **Database corruption under switch**
   - Løsning: Atomic writes til session file

## 🔮 Fremtidige Forbedringer

- **Voice recognition**: Automatisk gjenkjenne stemme
- **Private mode**: Optional secrets per bruker
- **User avatars**: I kontrollpanel
- **Usage statistics**: Per bruker (tid, meldinger, topics)
- **Family tree view**: Visualisering av relasjoner
- **Guest mode**: Temporary users (ingen permanent lagring)

---

**Status:** 📝 Planlagt  
**Neste steg:** Fase 1 - Database migration
