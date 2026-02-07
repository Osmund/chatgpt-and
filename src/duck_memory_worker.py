#!/usr/bin/env python3
"""
ChatGPT Duck - Memory Extraction Worker v2

Background service som prosesserer nye meldinger og ekstraherer:
- Profile facts (strukturerte fakta om bruker)
- Episodiske minner (ting verdt å huske)
- Topic klassifisering
- Session-level innsikter
- Contradiction detection

Forbedringer i v2:
- Eksponentiell backoff ved feil (unngår crash-loop)
- Triviell-melding-filter (sparer ~30-50% API-kall)
- API retry med backoff (robusthet ved 429/500)
- Gjenbrukt DB-connections (mindre overhead)
- Session-level extraction (rikere minner)
- LLM-basert session summary (bedre kontekst)
- Contradiction detection (korrekthet)
- Temporale fakta med TTL (friskere fakta)
- DRY extraction (felles metode for SMS og samtale)
"""

import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
import requests
from src.duck_memory import MemoryManager, ProfileFact, Memory
import sys

# Flush stdout for journalctl
sys.stdout.reconfigure(line_buffering=True)

# Load environment
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MEMORY_MODEL = os.getenv("AI_MODEL_MEMORY", "gpt-4.1-mini-2025-04-14")
SMS_MODEL = os.getenv("AI_MODEL_SMS", "gpt-4o-mini")

# Worker config
CHECK_INTERVAL = 5        # Sjekk hver 5. sekund
BATCH_SIZE = 5            # Prosesser opptil 5 meldinger per batch
MAX_BACKOFF = 300          # Maks 5 min mellom retries ved vedvarende feil
MAX_API_RETRIES = 3        # Antall retries for API-kall
API_RETRY_BASE = 2         # Base for exponential backoff (2, 4, 8 sek)

# Topics som aldri gir noe nyttig fra LLM-extraction
TRIVIAL_TOPICS = {'time', 'weather', 'lights', 'tv', 'ac', 'vacuum', 'music', 'twinkly', 'backup'}

# Topic-til-TTL mapping for temporale fakta (antall dager)
TOPIC_TTL = {
    'emotions': 7,
    'daily_life': 7,
    'health': 14,
    'work': 30,
    'weather': 1,
    # Alt annet = permanent (None)
}


def _detect_trivial_topics(user_text: str) -> set:
    """
    Rask keyword-basert topic detection for triviell-melding-filter.
    Returnerer set med detekterte topics.
    """
    topics = set()
    user_lower = user_text.lower()

    topic_keywords = {
        'weather': ['vær', 'temperatur', 'regn', 'sol', 'varmt', 'kaldt', 'netatmo', 'sensor'],
        'time': ['klokk', 'tid', 'dato'],
        'music': ['sang', 'musikk', 'spill', 'syng', 'låt'],
        'lights': ['lys', 'lampe', 'skru på', 'skru av', 'dimme'],
        'tv': ['tv', 'fjernsyn', 'netflix', 'spill av', 'pause'],
        'ac': ['ac', 'aircondition', 'klimaanlegg'],
        'vacuum': ['støvsuger', 'vacuum', 'robotstøvsuger', 'saros'],
        'twinkly': ['twinkly', 'led', 'ledvegg'],
        'backup': ['backup', 'sikkerhetskopi', 'ta backup'],
    }

    for topic, keywords in topic_keywords.items():
        if any(kw in user_lower for kw in keywords):
            topics.add(topic)

    return topics


def _is_trivial_message(user_text: str) -> bool:
    """
    Sjekk om en melding er triviell og ikke verdt å kjøre LLM-extraction på.
    Returnerer True hvis meldingen kun handler om trivielle topics.
    """
    # Veldig korte meldinger uten innhold
    if len(user_text.strip()) < 5:
        return True

    detected = _detect_trivial_topics(user_text)

    # Hvis alle detekterte topics er trivielle, og det er minst ett treff
    if detected and detected.issubset(TRIVIAL_TOPICS):
        return True

    return False


class MemoryExtractor:
    """
    Ekstraherer minner fra samtaler ved hjelp av LLM.
    Felles extraction-metode for både samtaler og SMS (DRY).
    Inkluderer retry med exponential backoff.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.extraction_count = 0
        self.skipped_trivial = 0

    def _call_openai(self, prompt: str, model: str = None) -> dict:
        """
        Felles OpenAI API-kall med retry og backoff.
        Returnerer parsed JSON-dict, eller tomt resultat ved feil.
        """
        model = model or MEMORY_MODEL
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Du er en memory extraction assistent. Returner kun valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        last_error = None
        for attempt in range(MAX_API_RETRIES):
            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)

                # Rate limit — vent og prøv igjen
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', API_RETRY_BASE ** (attempt + 1)))
                    print(f"  ⏳ Rate limited, venter {retry_after}s...", flush=True)
                    time.sleep(retry_after)
                    continue

                # Server error — retry
                if response.status_code >= 500:
                    wait = API_RETRY_BASE ** (attempt + 1)
                    print(f"  ⏳ Server error {response.status_code}, retry om {wait}s...", flush=True)
                    time.sleep(wait)
                    continue

                response.raise_for_status()

                content = response.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                self.extraction_count += 1
                return result

            except requests.exceptions.Timeout:
                last_error = "Timeout"
                wait = API_RETRY_BASE ** (attempt + 1)
                print(f"  ⏳ API timeout, retry {attempt+1}/{MAX_API_RETRIES} om {wait}s...", flush=True)
                time.sleep(wait)
            except Exception as e:
                last_error = str(e)
                if attempt < MAX_API_RETRIES - 1:
                    wait = API_RETRY_BASE ** (attempt + 1)
                    print(f"  ⏳ API feil: {e}, retry om {wait}s...", flush=True)
                    time.sleep(wait)

        print(f"❌ API-kall feilet etter {MAX_API_RETRIES} forsøk: {last_error}", flush=True)
        return {'profile_facts': [], 'memories': [], 'topics': [], 'importance': 1}

    def extract_from_conversation(self, user_text: str, ai_response: str, context: List[tuple] = None) -> Dict:
        """
        Ekstraher minner fra én utveksling (med kontekst).
        Triviell-melding-filter: hopper over meldinger som ikke gir noe nyttig.
        """
        # Triviell-melding-filter
        if _is_trivial_message(user_text):
            self.skipped_trivial += 1
            return {
                'profile_facts': [], 'memories': [],
                'topics': list(_detect_trivial_topics(user_text)),
                'importance': 1
            }

        prompt = self._build_conversation_prompt(user_text, ai_response, context)
        return self._call_openai(prompt, model=MEMORY_MODEL)

    def extract_from_sms(self, sender_name: str, message: str) -> dict:
        """Ekstraher minner fra SMS med korrekt kontekst om avsender."""
        prompt = self._build_sms_prompt(sender_name, message)
        return self._call_openai(prompt, model=SMS_MODEL)

    def extract_session_insights(self, session_messages: List[dict]) -> dict:
        """
        Ekstraher innsikter fra en hel session — fanger mønstre og temaer
        som per-melding-extraction ikke ser.
        """
        if len(session_messages) < 3:
            return {'profile_facts': [], 'memories': [], 'topics': [], 'importance': 1}

        # Bygg konversasjonslogg
        conversation_log = ""
        for i, msg in enumerate(session_messages, 1):
            conversation_log += f"\n[{i}] Bruker: {msg['user_text']}"
            ai_short = msg['ai_response'][:200] + "..." if len(msg['ai_response']) > 200 else msg['ai_response']
            conversation_log += f"\n    AI: {ai_short}\n"

        prompt = f"""
Analyser følgende HELE samtale-session mellom bruker og AI-assistent.
Du skal finne innsikter som kun er synlige når man ser hele samtalen samlet.

**VIKTIG: Per-melding-extraction har allerede kjørt. Du skal IKKE gjenta individuelle fakta.**
**Fokuser på:**
1. Overordnede temaer og mønstre i samtalen
2. Emosjonell tone og stemning (var brukeren glad, frustrert, nostalgisk?)
3. Sammenhenger mellom ulike meldinger som gir dypere innsikt
4. Planer eller intensjoner som fremkommer gradvis gjennom samtalen
5. Relasjoner eller dynamikker som viser seg over tid

**Samtale ({len(session_messages)} meldinger):**
{conversation_log}

Returner JSON:
{{
    "profile_facts": [
        {{"key": "...", "value": "...", "topic": "...", "confidence": 0.7, "source": "session_insight"}}
    ],
    "memories": [
        {{"text": "...", "topic": "...", "importance": 3, "confidence": 0.8}}
    ],
    "session_mood": "glad|nøytral|frustrert|nostalgisk|engasjert|sliten",
    "session_theme": "kort beskrivelse av samtalens hovedtema",
    "topics": ["..."],
    "importance": 1-5
}}

**Regler:**
- memories skal være oppsummeringer, ikke gjentakelser av enkelt-meldinger
- Eksempel RIKTIG: "Osmund hadde en lang og engasjert samtale om barndommen sin i Sokndal med fokus på far og besteforeldre"
- Eksempel FEIL: "Brukeren nevnte faren sin" (dette fanges allerede per-melding)
- Returner tomme lister hvis ingen session-level innsikter finnes
"""
        return self._call_openai(prompt, model=MEMORY_MODEL)

    def _build_conversation_prompt(self, user_text: str, ai_response: str, context: List[tuple] = None) -> str:
        """Bygg extraction-prompt for samtale."""
        context_section = ""
        if context:
            context_section = "\n**Tidligere samtale (kontekst):**\n"
            for i, (prev_user, prev_ai) in enumerate(context, 1):
                context_section += f"\nMelding {i}:\n"
                context_section += f"Bruker: {prev_user}\n"
                context_section += f"AI: {prev_ai[:100]}...\n" if len(prev_ai) > 100 else f"AI: {prev_ai}\n"

        return f"""
Analyser følgende samtale mellom bruker og AI-assistent.
Identifiser og ekstraher:

1. **Profile Facts**: Fakta om brukeren som bør lagres strukturert
   - Navn, bopel, jobb, familie, hobbyer, preferanser, samlinger, etc.
   - Kun faktiske fakta som brukeren eksplisitt sier
   - Ikke anta eller infer ting
   
   **SPESIELT VIKTIG FOR FAMILIE:**
   - Lagre hvert familiemedlem individuelt med unike keys:
     * father_name, mother_name, sister_1_name, sister_2_name, brother_1_name, etc.
   - Lagre bursdager: sister_1_birthday, father_birthday (format: DD-MM eller "31. januar")
   - Lagre fødselsår: father_birth_year, mother_birth_year, sister_1_birth_year (format: YYYY f.eks. "1949")
   - Lagre alder: father_age, sister_1_age (kun tall)
   - Lagre antall søsken: sibling_count (verdi: 3)
   - Lagre antall nieser/nevøer: nieces_count, nephews_count
   - Lagre barn til søsken: sister_1_child_1_name, sister_2_child_1_name, etc.
   - Lagre antall barn: sister_1_children_count, sister_2_children_count
   - Lagre alder-relasjoner: sister_1_age_relation (verdier: "eldste", "yngste", "mellomste")
   - Lagre lokasjon: father_location, sister_1_location
   - Lagre relasjonsinfo: father_neighbor=true, father_birthplace=Sokndal
   
   **SPESIELT VIKTIG FOR HOBBYER OG SAMLINGER:**
   - Lagre hva brukeren samler på: collection_1, collection_2, etc.
   - Lagre spesifikke modeller/typer: computer_collection, toy_collection, etc.
   - Lagre hobbyaktiviteter: hobby_programming, hobby_gaming, etc.
   - Eksempler:
     * collection_retro_computers = "Commodore og Amiga"
     * collection_toys = "Kenneth Star Wars figurer"
     * hobby_programming_platform = "Amiga assembler"
     * computer_model_1 = "Amiga 32"
   
   Eksempler familie:
   {{"key": "father_name", "value": "Arvid", "topic": "family", "confidence": 1.0, "source": "user"}}
   {{"key": "sister_1_name", "value": "Miriam", "topic": "family", "confidence": 1.0, "source": "user"}}
   {{"key": "sister_1_birthday", "value": "31-01", "topic": "family", "confidence": 1.0, "source": "user"}}
   {{"key": "sister_1_age_relation", "value": "eldste", "topic": "family", "confidence": 0.9, "source": "user"}}
   
   Eksempler hobbyer:
   {{"key": "collection_retro_computers", "value": "Commodore og Amiga", "topic": "hobby", "confidence": 1.0, "source": "user"}}
   {{"key": "collection_toys", "value": "Kenneth Star Wars figurer", "topic": "hobby", "confidence": 1.0, "source": "user"}}
   {{"key": "hobby_programming", "value": "Amiga assembler", "topic": "hobby", "confidence": 0.9, "source": "user"}}

2. **Memories**: Episodiske minner verdt å huske
   - Hendelser, planer, samtaleemner
   - Ting som kan være nyttig i fremtidige samtaler
   - Kort og konsist (1-2 setninger)
   - Inkluder familieinteraksjoner og spesielle hendelser
   - Inkluder nostalgiske minner om hobbyer og samlinger
   - **VIKTIG: Inkluder også brukerens interaksjoner med Anda:**
     * Videoer eller innlegg brukeren lager om Anda
     * Sosial respons (visninger, kommentarer, likes)
     * Media-oppmerksomhet eller artikler om Anda
     * Reaksjoner fra andre folk på Anda
     * Milepæler og prestasjoner relatert til Anda-prosjektet
   - Eksempel: "Brukeren lastet opp video av Anda på Reddit som fikk 15 000 visninger"
   - Eksempel: "En journalist i England kontaktet brukeren om Anda"
   - **VIKTIG: Fang også opp daglige samtaler og personlige emner:**
     * Jobbrelaterte hendelser (prosjekter, møter, kollegaer, utfordringer, suksesser)
     * Steder brukeren nevner (hjemby, reisemål, favorittplasser)
     * Følelser og mental tilstand (stress, glede, bekymringer, humør)
     * Helse og velvære (sykdom, trening, søvn, mat, energinivå)
     * Planer for fremtiden (reiser, prosjekter, mål)
     * Daglige rutiner og aktiviteter
   - Eksempel: "Brukeren hadde en stressende dag på jobb"
   - Eksempel: "Brukeren planlegger å dra til Sokndal i helgen"
   - Eksempel: "Brukeren føler seg sliten og trenger mer søvn"

3. **Topics**: Emne-kategorier
   - Velg fra: family, hobby, work, projects, technical, health, pets, preferences, weather, time, general, collection, social_media, achievements, location, emotions, daily_life, documentation

4. **Importance**: Hvor viktig er denne samtalen? (1-5)
   - 1: Triviell (vær, tid, small talk)
   - 3: Moderat (informasjon, spørsmål)
   - 5: Viktig (personlig info, planer, preferanser)

**VIKTIG om kontekst:**
- Hvis du får tidligere meldinger som kontekst, bruk dem til å forstå sammenhengen
- Kombiner informasjon fra flere meldinger til ett minneverdig utsagn hvis det gir mening
- Eksempel: "Mange lurte på hvordan jeg laget deg" + "Jeg har dokumentert prosessen på GitHub" 
  → Memory: "Brukeren har dokumentert Anda-prosjektet på GitHub fordi mange lurte på hvordan den ble laget"
- Ekstraher kun fra den nåværende meldingen, men bruk kontekst til å forstå sammenhengen
{context_section}

**Nåværende melding å analysere:**
Bruker: "{user_text}"
AI: "{ai_response}"

**Returner JSON:**
{{
    "profile_facts": [
        {{
            "key": "hobby_name",
            "value": "fotografi",
            "topic": "hobby",
            "confidence": 0.9,
            "source": "user"
        }}
    ],
    "memories": [
        {{
            "text": "Brukeren planlegger tur til fjellet",
            "topic": "hobby",
            "importance": 3,
            "confidence": 0.9
        }}
    ],
    "topics": ["hobby", "preferences"],
    "importance": 3
}}

**Viktig:**
- Returner kun JSON, ingen forklaring
- Hvis ingenting å ekstrahere: returner tomme lister
- Vær konservativ: bedre å ikke lagre enn å lagre feil info
- confidence: 0.5-1.0 (høyere = mer sikker)
- For familiemedlemmer: bruk alltid unike keys (sister_1, sister_2, etc.)
- For samlinger: vær spesifikk (collection_retro_computers, ikke bare "hobby")
"""

    def _build_sms_prompt(self, sender_name: str, message: str) -> str:
        """Bygg extraction-prompt for SMS."""
        return f"""
Analyser følgende SMS-melding fra {sender_name} til AI-assistenten Anda.

**KRITISK: Dette er en SMS FRA {sender_name} (IKKE fra Osmund)**

Identifiser og ekstraher:

1. **Profile Facts**: Fakta om {sender_name}
   - Kun faktiske fakta som {sender_name} eksplisitt nevner om seg selv
   - Bruk samme key-struktur som for Osmund, men prefikset med lavercased navn:
     * {sender_name.lower()}_location, {sender_name.lower()}_partner_name, etc.
   
2. **Memories**: Episodiske minner verdt å huske
   - **VIKTIG**: Skriv minner i tredjeperson om {sender_name}, IKKE "brukeren"
   - Eksempel RIKTIG: "{sender_name} og Gunn Torill varmer seg ved ovnen"
   - Eksempel FEIL: "Brukeren og Gunn Torill varmer seg ved ovnen"
   - Kort og konsist (1-2 setninger)

SMS fra {sender_name}: {message}

Returner JSON:
{{
    "profile_facts": [
        {{"key": "...", "value": "...", "topic": "...", "confidence": 0.7, "source": "sms"}}
    ],
    "memories": [
        {{"text": "...", "topic": "...", "confidence": 0.7, "importance": 1-5}}
    ],
    "topics": ["..."],
    "importance": 1-5
}}
"""


class MemoryWorker:
    """
    Background worker som prosesserer meldinger.
    Inkluderer crash-protection, connection reuse, og session-level extraction.
    """

    def __init__(self, memory_manager: MemoryManager, extractor: MemoryExtractor):
        self.memory_manager = memory_manager
        self.extractor = extractor
        self.processed_count = 0
        self.sms_processed_count = 0
        self.trivial_skipped_count = 0
        self.contradiction_count = 0
        self.session_extractions = 0
        self.start_time = datetime.now()
        self._conn = None  # Gjenbrukt connection
        self._ensure_tables()

    def _get_conn(self):
        """Gjenbruk database-connection (lazy init)."""
        if self._conn is None:
            self._conn = self.memory_manager._get_connection()
        return self._conn

    def _close_conn(self):
        """No-op: connection managed by DatabaseManager."""
        pass

    def _ensure_tables(self):
        """Opprett nødvendige tabeller."""
        try:
            conn = self._get_conn()
            c = conn.cursor()

            c.execute("""
                CREATE TABLE IF NOT EXISTS sms_processed (
                    sms_id INTEGER PRIMARY KEY,
                    processed_at TEXT NOT NULL,
                    FOREIGN KEY (sms_id) REFERENCES sms_history(id)
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS memory_contradictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_key TEXT NOT NULL,
                    existing_value TEXT NOT NULL,
                    new_value TEXT NOT NULL,
                    existing_confidence REAL,
                    new_confidence REAL,
                    source TEXT,
                    detected_at TEXT NOT NULL,
                    resolved INTEGER DEFAULT 0
                )
            """)

            # Sjekk om session_summaries har nye kolonner
            c.execute("PRAGMA table_info(session_summaries)")
            columns = {row['name'] for row in c.fetchall()}

            if columns:  # Tabellen eksisterer
                if 'session_mood' not in columns:
                    try:
                        c.execute("ALTER TABLE session_summaries ADD COLUMN session_mood TEXT DEFAULT 'nøytral'")
                    except Exception:
                        pass
                if 'session_theme' not in columns:
                    try:
                        c.execute("ALTER TABLE session_summaries ADD COLUMN session_theme TEXT DEFAULT ''")
                    except Exception:
                        pass

            conn.commit()
        except Exception as e:
            print(f"⚠️ Kunne ikke opprette tabeller: {e}", flush=True)
            self._close_conn()

    def process_pending_messages(self):
        """Prosesser alle ventende meldinger med triviell-filter."""
        messages = self.memory_manager.get_unprocessed_messages(limit=BATCH_SIZE)

        if not messages:
            return 0

        print(f"📝 Prosesserer {len(messages)} meldinger...", flush=True)

        for msg in messages:
            try:
                # Triviell-filter sjekk
                if _is_trivial_message(msg.user_text):
                    self.trivial_skipped_count += 1
                    self.memory_manager.mark_message_processed(msg.id)
                    self.processed_count += 1
                    print(f"  ⏭️  Triviell: {msg.user_text[:40]}...", flush=True)
                    continue

                self._process_message(msg)
                self.memory_manager.mark_message_processed(msg.id)
                self.processed_count += 1

            except Exception as e:
                print(f"❌ Feil ved prosessering av melding {msg.id}: {e}", flush=True)
                # Marker som prosessert for å unngå at den blokkerer køen
                self.memory_manager.mark_message_processed(msg.id)

        return len(messages)

    def process_pending_sms(self):
        """Prosesser uprosesserte innkommende SMS med connection reuse."""
        try:
            conn = self._get_conn()
            c = conn.cursor()

            c.execute("""
                SELECT sh.id, sh.message, sh.timestamp, sc.name, sc.phone
                FROM sms_history sh
                JOIN sms_contacts sc ON sh.contact_id = sc.id
                LEFT JOIN sms_processed sp ON sh.id = sp.sms_id
                WHERE sh.direction = 'inbound'
                  AND sp.sms_id IS NULL
                ORDER BY sh.timestamp ASC
                LIMIT ?
            """, (BATCH_SIZE,))

            sms_list = [dict(row) for row in c.fetchall()]

            if not sms_list:
                return 0

            print(f"📱 Prosesserer {len(sms_list)} SMS...", flush=True)

            for sms in sms_list:
                try:
                    self._process_sms(sms)
                except Exception as e:
                    print(f"❌ Feil ved prosessering av SMS {sms['id']}: {e}", flush=True)

                # Marker alltid som prosessert (gjenbruk connection)
                c.execute("""
                    INSERT OR IGNORE INTO sms_processed (sms_id, processed_at)
                    VALUES (?, ?)
                """, (sms['id'], datetime.now().isoformat()))
                conn.commit()
                self.sms_processed_count += 1

            return len(sms_list)

        except Exception as e:
            print(f"❌ Feil ved SMS-prosessering: {e}", flush=True)
            self._close_conn()  # Reset connection ved DB-feil
            return 0

    def _process_sms(self, sms: dict):
        """Prosesser én SMS-melding."""
        extracted = self.extractor.extract_from_sms(
            sender_name=sms['name'],
            message=sms['message']
        )

        self._save_extracted_data(
            extracted,
            source='sms',
            source_id_key='source_sms_id',
            source_id=sms['id'],
            default_confidence=0.7,
            sender=sms['name'],
            user_name='Osmund',
            log_prefix=f"SMS [fra {sms['name']}]"
        )

    def _get_conversation_context(self, current_msg_id: int, context_size: int = 2) -> List[tuple]:
        """Hent tidligere meldinger som kontekst."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_text, ai_response
            FROM messages
            WHERE id < ?
            ORDER BY id DESC
            LIMIT ?
        """, (current_msg_id, context_size))

        rows = cursor.fetchall()
        return list(reversed(rows))

    def _get_session_context(self, session_id: str) -> List[dict]:
        """Hent alle meldinger i samme session."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_text, ai_response, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
        """, (session_id,))

        return [dict(row) for row in cursor.fetchall()]

    def _process_message(self, msg):
        """Prosesser én melding: ekstraher og lagre minner."""
        # Hent session context
        session_context = []
        if msg.session_id:
            session_context = self._get_session_context(msg.session_id)
            print(f"  📋 Session context: {len(session_context)} meldinger i session {msg.session_id[:8]}...", flush=True)

        if session_context:
            context = [(row['user_text'], row['ai_response']) for row in session_context if row['id'] < msg.id]
        else:
            context = self._get_conversation_context(msg.id, context_size=2)

        # Ekstraher minner via LLM
        extracted = self.extractor.extract_from_conversation(
            msg.user_text, msg.ai_response, context=context
        )

        self._save_extracted_data(
            extracted,
            source='extracted',
            source_id_key='source_message_id',
            source_id=msg.id,
            default_confidence=0.8,
            user_name=msg.user_name,
            log_prefix=f"[{msg.user_name}]"
        )

        # Log viktige samtaler
        importance = extracted.get('importance', 1)
        if importance >= 4:
            print(f"  ⭐ Viktig samtale (importance={importance})", flush=True)

    def _save_extracted_data(self, extracted: dict, source: str, source_id_key: str,
                            source_id: int, default_confidence: float = 0.8,
                            sender: str = None, user_name: str = 'Osmund',
                            log_prefix: str = ""):
        """
        Felles metode for å lagre ekstraherte facts og memories.
        Brukes av samtale, SMS, og session-level extraction (DRY).
        Inkluderer contradiction detection og temporale fakta.
        """
        # Lagre profile facts
        for fact_data in extracted.get('profile_facts', []):
            try:
                confidence = fact_data.get('confidence', default_confidence)

                # Contradiction detection
                contradiction = self._check_contradiction(
                    fact_data['key'], fact_data['value'], confidence
                )
                if contradiction == 'blocked':
                    continue

                auto_metadata = {
                    'learned_at': datetime.now().isoformat(),
                    source_id_key: source_id,
                    'extraction_confidence': confidence,
                    'learned_from': source,
                }
                if sender:
                    auto_metadata['sender'] = sender

                # Temporal TTL
                topic = fact_data.get('topic', 'general')
                ttl_days = TOPIC_TTL.get(topic)
                if ttl_days:
                    auto_metadata['expires_at'] = (datetime.now() + timedelta(days=ttl_days)).isoformat()

                fact = ProfileFact(
                    key=fact_data['key'],
                    value=fact_data['value'],
                    topic=topic,
                    confidence=confidence,
                    source=fact_data.get('source', source),
                    metadata=auto_metadata
                )
                self.memory_manager.save_profile_fact(fact)
                self.memory_manager.update_fact_embedding(fact.key)

                print(f"  ✅ {log_prefix} Fact: {fact.key} = {fact.value}", flush=True)
            except Exception as e:
                print(f"  ⚠️ Kunne ikke lagre fact: {e}", flush=True)

        # Lagre memories
        for mem_data in extracted.get('memories', []):
            try:
                topic = mem_data.get('topic', 'general')
                auto_metadata = {
                    'learned_at': datetime.now().isoformat(),
                    source_id_key: source_id,
                    'importance': mem_data.get('importance', 3),
                    'learned_from': source,
                }
                if sender:
                    auto_metadata['sender'] = sender
                    auto_metadata['about_person'] = sender

                # Temporal TTL for memories
                ttl_days = TOPIC_TTL.get(topic)
                if ttl_days:
                    auto_metadata['expires_at'] = (datetime.now() + timedelta(days=ttl_days)).isoformat()

                memory = Memory(
                    text=mem_data['text'],
                    topic=topic,
                    confidence=mem_data.get('confidence', default_confidence),
                    source=source,
                    metadata=auto_metadata
                )
                memory_id = self.memory_manager.save_memory(
                    memory, check_duplicates=True, user_name=user_name
                )
                print(f"  ✅ {log_prefix} Memory: {memory.text[:50]}...", flush=True)
            except Exception as e:
                print(f"  ⚠️ Kunne ikke lagre memory: {e}", flush=True)

    def _check_contradiction(self, key: str, new_value: str, new_confidence: float) -> str:
        """
        Sjekk om en ny fact contradicts en eksisterende.
        Returnerer: 'ok' (lagre), 'blocked' (ikke lagre)
        Logger contradictions til memory_contradictions-tabellen.
        """
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("SELECT value, confidence FROM profile_facts WHERE key = ?", (key,))
            existing = c.fetchone()

            if not existing:
                return 'ok'

            existing_value = existing['value']
            existing_confidence = existing['confidence']

            # Samme verdi — ingen contradiction
            if existing_value.lower().strip() == new_value.lower().strip():
                return 'ok'

            # Eksisterende har høy confidence — blokker og logg
            if existing_confidence >= 0.9 and new_confidence < existing_confidence:
                c.execute("""
                    INSERT INTO memory_contradictions
                    (fact_key, existing_value, new_value, existing_confidence, new_confidence, source, detected_at)
                    VALUES (?, ?, ?, ?, ?, 'extraction', ?)
                """, (key, existing_value, new_value, existing_confidence, new_confidence,
                      datetime.now().isoformat()))
                conn.commit()
                self.contradiction_count += 1
                print(f"  ⚡ Contradiction: {key}={new_value} (eksisterende: {existing_value}, conf={existing_confidence})", flush=True)
                return 'blocked'

            # Ny har høyere confidence — tillat oppdatering, men logg
            if new_confidence > existing_confidence:
                c.execute("""
                    INSERT INTO memory_contradictions
                    (fact_key, existing_value, new_value, existing_confidence, new_confidence, source, detected_at, resolved)
                    VALUES (?, ?, ?, ?, ?, 'extraction', ?, 1)
                """, (key, existing_value, new_value, existing_confidence, new_confidence,
                      datetime.now().isoformat()))
                conn.commit()
                print(f"  🔄 Oppdaterer {key}: {existing_value} → {new_value} (høyere confidence)", flush=True)
                return 'ok'

            return 'ok'

        except Exception as e:
            print(f"  ⚠️ Contradiction check feilet: {e}", flush=True)
            return 'ok'

    def print_stats(self):
        """Print worker statistikk."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"

        stats = self.memory_manager.get_stats()

        print(f"\n📊 Memory Worker v2 Stats", flush=True)
        print(f"  Uptime: {uptime_str}", flush=True)
        print(f"  Meldinger prosessert: {self.processed_count}", flush=True)
        print(f"  SMS prosessert: {self.sms_processed_count}", flush=True)
        print(f"  Trivielle hoppet over: {self.trivial_skipped_count}", flush=True)
        print(f"  LLM extractions: {self.extractor.extraction_count}", flush=True)
        print(f"  Session extractions: {self.session_extractions}", flush=True)
        print(f"  Contradictions: {self.contradiction_count}", flush=True)
        print(f"  Ventende meldinger: {stats['unprocessed_messages']}", flush=True)
        print(f"  Total minner: {stats['total_memories']}", flush=True)
        print(f"  Total facts: {stats['total_facts']}", flush=True)
        print(f"  Database størrelse: {stats['db_size_mb']} MB\n", flush=True)

    def _generate_session_summary(self, session_id: str):
        """
        Generer LLM-basert oppsummering av en session + session-level extraction.
        """
        try:
            conn = self._get_conn()
            c = conn.cursor()

            c.execute("""
                SELECT id, user_text, ai_response, timestamp, metadata
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))

            session_messages = [dict(row) for row in c.fetchall()]

            if len(session_messages) < 2:
                print(f"  ⏭️  Session for kort for oppsummering ({len(session_messages)} meldinger)", flush=True)
                return

            start_time = session_messages[0]['timestamp']
            end_time = session_messages[-1]['timestamp']

            # Ekstraher topics fra metadata
            all_topics = set()
            for msg in session_messages:
                if msg.get('metadata'):
                    try:
                        meta = json.loads(msg['metadata'])
                        all_topics.update(meta.get('topics', []))
                    except (json.JSONDecodeError, TypeError):
                        pass

            topics_str = ', '.join(sorted(all_topics)) if all_topics else 'general'

            # === Session-level extraction (fanger mønstre over hele samtalen) ===
            session_mood = 'nøytral'
            session_theme = ''

            if len(session_messages) >= 3:
                print(f"  🧠 Kjører session-level extraction for {session_id[:8]}...", flush=True)
                session_insights = self.extractor.extract_session_insights(session_messages)

                session_mood = session_insights.get('session_mood', 'nøytral')
                session_theme = session_insights.get('session_theme', '')

                # Lagre session-level facts og memories
                self._save_extracted_data(
                    session_insights,
                    source='session_insight',
                    source_id_key='source_session',
                    source_id=0,
                    default_confidence=0.7,
                    user_name='Osmund',
                    log_prefix="Session"
                )
                self.session_extractions += 1

            # === LLM-basert summary ===
            conversation_text = ""
            for msg in session_messages[:10]:  # Maks 10 meldinger for summary
                conversation_text += f"Bruker: {msg['user_text'][:100]}\n"
                conversation_text += f"AI: {msg['ai_response'][:100]}\n\n"

            summary_prompt = f"""
Oppsummer følgende samtale i 1-2 setninger på norsk.
Fokuser på hva samtalen handlet om og hva som er verdt å huske.

Samtale ({len(session_messages)} meldinger):
{conversation_text}

Returner JSON:
{{"summary": "kort oppsummering"}}
"""
            summary_result = self.extractor._call_openai(summary_prompt)
            summary = summary_result.get('summary', f"Samtale med {len(session_messages)} meldinger. Topics: {topics_str}")

            # Lagre summary
            c.execute("""
                INSERT INTO session_summaries
                (session_id, summary, message_count, topics, start_time, end_time, session_mood, session_theme)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, summary, len(session_messages), topics_str,
                  start_time, end_time, session_mood, session_theme))
            conn.commit()

            print(f"  ✅ Session summary: {summary}", flush=True)
            if session_mood != 'nøytral':
                print(f"     Stemning: {session_mood} | Tema: {session_theme}", flush=True)

        except Exception as e:
            print(f"  ⚠️ Kunne ikke generere session summary: {e}", flush=True)

    def _check_and_summarize_old_sessions(self):
        """Finn sessions eldre enn 30 min og generer summaries."""
        try:
            cutoff_time = (datetime.now() - timedelta(minutes=30)).isoformat()

            conn = self._get_conn()
            c = conn.cursor()

            c.execute("""
                SELECT DISTINCT m.session_id, MAX(m.timestamp) as last_msg_time
                FROM messages m
                LEFT JOIN session_summaries s ON m.session_id = s.session_id
                WHERE m.session_id IS NOT NULL
                  AND s.session_id IS NULL
                  AND m.timestamp < ?
                GROUP BY m.session_id
            """, (cutoff_time,))

            old_sessions = c.fetchall()

            if old_sessions:
                print(f"📝 Fant {len(old_sessions)} session(s) å oppsummere", flush=True)
                for row in old_sessions:
                    self._generate_session_summary(row['session_id'])
        except Exception as e:
            print(f"⚠️ Feil ved session summary check: {e}", flush=True)
            self._close_conn()

    def run(self):
        """
        Hovedløkke med eksponentiell backoff ved gjentatte feil.
        Unngår crash-loop som kan reboote Pi-en.
        """
        print("🚀 Memory Worker v2 startet", flush=True)
        print(f"  Check interval: {CHECK_INTERVAL}s", flush=True)
        print(f"  Batch size: {BATCH_SIZE}", flush=True)
        print(f"  Model: {MEMORY_MODEL}", flush=True)
        print(f"  Trivielle topics (skip): {', '.join(sorted(TRIVIAL_TOPICS))}", flush=True)
        print(f"  API key: {'✅' if OPENAI_API_KEY else '❌'}\n", flush=True)

        if not OPENAI_API_KEY:
            print("❌ OPENAI_API_KEY ikke satt i .env!", flush=True)
            return

        stats_counter = 0
        summary_counter = 0
        consecutive_errors = 0
        current_backoff = CHECK_INTERVAL

        while True:
            try:
                # Prosesser ventende meldinger
                processed = self.process_pending_messages()

                # Prosesser ventende SMS
                sms_processed = self.process_pending_sms()

                # Suksess — reset backoff
                if consecutive_errors > 0:
                    print(f"✅ Gjenopprettet etter {consecutive_errors} feil", flush=True)
                consecutive_errors = 0
                current_backoff = CHECK_INTERVAL

                # Print stats hver 60. iterasjon (5 min)
                stats_counter += 1
                if stats_counter >= 60:
                    self.print_stats()
                    stats_counter = 0

                # Generer session summaries hver 120. iterasjon (10 min)
                summary_counter += 1
                if summary_counter >= 120:
                    self._check_and_summarize_old_sessions()
                    summary_counter = 0

                # Vent før neste sjekk
                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                print("\n👋 Memory Worker stopper...", flush=True)
                self.print_stats()
                self._close_conn()
                break
            except Exception as e:
                consecutive_errors += 1
                current_backoff = min(current_backoff * 2, MAX_BACKOFF)

                print(f"❌ Worker error #{consecutive_errors}: {e}", flush=True)
                print(f"   Neste forsøk om {current_backoff}s (backoff)", flush=True)

                # Reset connection ved vedvarende feil
                self._close_conn()

                # Ved 10+ feil på rad — noe er fundamentalt galt
                if consecutive_errors >= 10:
                    print(f"🛑 {consecutive_errors} feil på rad — venter {MAX_BACKOFF}s", flush=True)
                    import traceback
                    traceback.print_exc()

                time.sleep(current_backoff)


def main():
    """Main entry point."""
    try:
        memory_manager = MemoryManager()
        extractor = MemoryExtractor(OPENAI_API_KEY)
        worker = MemoryWorker(memory_manager, extractor)
        worker.run()

    except Exception as e:
        print(f"❌ Fatal error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
