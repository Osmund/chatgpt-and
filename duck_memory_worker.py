#!/usr/bin/env python3
"""
ChatGPT Duck - Memory Extraction Worker

Background service som prosesserer nye meldinger og ekstraherer:
- Profile facts (strukturerte fakta om bruker)
- Episodiske minner (ting verdt å huske)
- Topic klassifisering

Kjører kontinuerlig og prosesserer nye meldinger asynkront
for å ikke påvirke hovedappens latency.
"""

import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import requests
from duck_memory import MemoryManager, ProfileFact, Memory
import sys

# Flush stdout for journalctl
sys.stdout.reconfigure(line_buffering=True)

# Load environment
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Worker config
CHECK_INTERVAL = 5  # Sjekk hver 5. sekund
BATCH_SIZE = 5      # Prosesser opptil 5 meldinger per batch
USE_CHEAP_MODEL = False  # Bruk gpt-4o-mini for bedre family extraction


class MemoryExtractor:
    """
    Ekstraherer minner fra samtaler ved hjelp av LLM
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.extraction_count = 0
        
    def extract_from_conversation(self, user_text: str, ai_response: str, context: List[tuple] = None) -> Dict:
        """
        Ekstraher minner fra én utveksling (med kontekst)
        
        Args:
            user_text: Brukerens melding
            ai_response: AI-assistentens svar
            context: Liste av (user_text, ai_response) fra tidligere meldinger
        
        Returnerer:
        {
            'profile_facts': [...],
            'memories': [...],
            'topics': [...],
            'importance': 1-5
        }
        """
        
        # Bygg kontekst-seksjon hvis tilgjengelig
        context_section = ""
        if context:
            context_section = "\n**Tidligere samtale (kontekst):**\n"
            for i, (prev_user, prev_ai) in enumerate(context, 1):
                context_section += f"\nMelding {i}:\n"
                context_section += f"Bruker: {prev_user}\n"
                context_section += f"AI: {prev_ai[:100]}...\n" if len(prev_ai) > 100 else f"AI: {prev_ai}\n"
        
        prompt = f"""
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
            "confidence": 0.9", "oldString": "3. **Topics**: Emne-kategorier\n   - Velg fra: family, hobby, work, projects, technical, health, pets, preferences, weather, time, general, collection, social_media, achievements, location, emotions, daily_life\n\n4. **Importance**: Hvor viktig er denne samtalen? (1-5)\n   - 1: Triviell (vær, tid, small talk)\n   - 3: Moderat (informasjon, spørsmål)\n   - 5: Viktig (personlig info, planer, preferanser)\n\n**Samtale:**\nBruker: \"{user_text}\"\nAI: \"{ai_response}\"", "newString": "3. **Topics**: Emne-kategorier\n   - Velg fra: family, hobby, work, projects, technical, health, pets, preferences, weather, time, general, collection, social_media, achievements, location, emotions, daily_life, documentation\n\n4. **Importance**: Hvor viktig er denne samtalen? (1-5)\n   - 1: Triviell (vær, tid, small talk)\n   - 3: Moderat (informasjon, spørsmål)\n   - 5: Viktig (personlig info, planer, preferanser)\n\n**VIKTIG om kontekst:**\n- Hvis du får tidligere meldinger som kontekst, bruk dem til å forstå sammenhengen\n- Kombiner informasjon fra flere meldinger til ett minneverdig utsagn hvis det gir mening\n- Eksempel: \"Mange lurte på hvordan jeg laget deg\" + \"Jeg har dokumentert prosessen på GitHub\" \n  → Memory: \"Brukeren har dokumentert Anda-prosjektet på GitHub fordi mange lurte på hvordan den ble laget\"\n- Ekstraher kun fra den nåværende meldingen, men bruk kontekst til å forstå sammenhengen\n{context_section}\n\n**Nåværende melding å analysere:**\nBruker: \"{user_text}\"\nAI: \"{ai_response}\"", "oldString": "3. **Topics**: Emne-kategorier\n   - Velg fra: family, hobby, work, projects, technical, health, pets, preferences, weather, time, general, collection, social_media, achievements, location, emotions, daily_life\n\n4. **Importance**: Hvor viktig er denne samtalen? (1-5)\n   - 1: Triviell (vær, tid, small talk)\n   - 3: Moderat (informasjon, spørsmål)\n   - 5: Viktig (personlig info, planer, preferanser)\n\n**Samtale:**\nBruker: \"{user_text}\"\nAI: \"{ai_response}\""

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
        
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            model = "gpt-3.5-turbo" if USE_CHEAP_MODEL else "gpt-4o-mini"
            
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Du er en memory extraction assistent. Returner kun valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # Lav temp for konsistent output
                "response_format": {"type": "json_object"}  # Force JSON
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            
            self.extraction_count += 1
            return result
            
        except Exception as e:
            print(f"❌ Memory extraction feilet: {e}", flush=True)
            return {
                'profile_facts': [],
                'memories': [],
                'topics': [],
                'importance': 1
            }


class MemoryWorker:
    """
    Background worker som prosesserer meldinger
    """
    
    def __init__(self, memory_manager: MemoryManager, extractor: MemoryExtractor):
        self.memory_manager = memory_manager
        self.extractor = extractor
        self.processed_count = 0
        self.start_time = datetime.now()
        
    def process_pending_messages(self):
        """
        Prosesser alle ventende meldinger
        """
        messages = self.memory_manager.get_unprocessed_messages(limit=BATCH_SIZE)
        
        if not messages:
            return 0
        
        print(f"📝 Prosesserer {len(messages)} meldinger...", flush=True)
        
        for msg in messages:
            try:
                self._process_message(msg)
                self.memory_manager.mark_message_processed(msg.id)
                self.processed_count += 1
                
            except Exception as e:
                print(f"❌ Feil ved prosessering av melding {msg.id}: {e}", flush=True)
                # Marker som prosessert likevel for å unngå at den blokkerer køen
                self.memory_manager.mark_message_processed(msg.id)
        
        return len(messages)
    
    def _get_conversation_context(self, current_msg_id: int, context_size: int = 2) -> List[tuple]:
        """
        Hent tidligere meldinger som kontekst
        Returnerer liste av (user_text, ai_response) tupler
        """
        conn = self.memory_manager._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_text, ai_response
            FROM messages
            WHERE id < ?
            ORDER BY id DESC
            LIMIT ?
        """, (current_msg_id, context_size))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Returner i kronologisk rekkefølge (eldste først)
        return list(reversed(rows))
    
    def _get_session_context(self, session_id: str) -> List[dict]:
        """
        Hent alle meldinger i samme session for full kontekst
        Returnerer liste av dict med id, user_text, ai_response, metadata
        """
        conn = self.memory_manager._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, user_text, ai_response, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
        """, (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def _process_message(self, msg):
        """
        Prosesser én melding: ekstraher og lagre minner
        """
        # Hent session context hvis tilgjengelig
        session_context = []
        if msg.session_id:
            session_context = self._get_session_context(msg.session_id)
            print(f"  📋 Session context: {len(session_context)} meldinger i session {msg.session_id[:8]}...", flush=True)
        
        # Bruk session context hvis tilgjengelig, ellers fallback til vanlig context
        if session_context:
            # Bruk alle meldinger i session som context (ekskluder nåværende)
            context = [(row['user_text'], row['ai_response']) for row in session_context if row['id'] < msg.id]
        else:
            # Fallback til vanlig context (2 siste meldinger)
            context = self._get_conversation_context(msg.id, context_size=2)
        
        # Ekstraher minner via LLM med kontekst
        extracted = self.extractor.extract_from_conversation(
            msg.user_text,
            msg.ai_response,
            context=context
        )
        
        # Lagre profile facts
        for fact_data in extracted.get('profile_facts', []):
            try:
                # Automatisk metadata med kontekst
                auto_metadata = {
                    'learned_at': datetime.now().isoformat(),
                    'source_message_id': msg.id,
                    'extraction_confidence': fact_data.get('confidence', 0.8),
                    'learned_from': 'conversation'
                }
                
                fact = ProfileFact(
                    key=fact_data['key'],
                    value=fact_data['value'],
                    topic=fact_data.get('topic', 'general'),
                    confidence=fact_data.get('confidence', 0.8),
                    source=fact_data.get('source', 'extracted'),
                    metadata=auto_metadata
                )
                self.memory_manager.save_profile_fact(fact)
                
                # Generer embedding for ny fact
                self.memory_manager.update_fact_embedding(fact.key)
                
                print(f"  ✅ Fact: {fact.key} = {fact.value}", flush=True)
            except Exception as e:
                print(f"  ⚠️ Kunne ikke lagre fact: {e}", flush=True)
        
        # Lagre memories (med duplikat-sjekk)
        for mem_data in extracted.get('memories', []):
            try:
                # Automatisk metadata for memories
                auto_metadata = {
                    'learned_at': datetime.now().isoformat(),
                    'source_message_id': msg.id,
                    'importance': mem_data.get('importance', 3),
                    'learned_from': 'conversation'
                }
                
                memory = Memory(
                    text=mem_data['text'],
                    topic=mem_data.get('topic', 'general'),
                    confidence=mem_data.get('confidence', 0.8),
                    source='extracted',
                    metadata=auto_metadata
                )
                # save_memory vil nå sjekke for duplikater og merge hvis nødvendig
                memory_id = self.memory_manager.save_memory(memory, check_duplicates=True, user_name=msg.user_name)
                print(f"  ✅ Memory [{msg.user_name}]: {memory.text[:50]}...", flush=True)
            except Exception as e:
                print(f"  ⚠️ Kunne ikke lagre memory: {e}", flush=True)
        
        # Log hvis viktig samtale
        importance = extracted.get('importance', 1)
        if importance >= 4:
            print(f"  ⭐ Viktig samtale (importance={importance})", flush=True)
    
    def print_stats(self):
        """
        Print worker statistikk
        """
        uptime = (datetime.now() - self.start_time).total_seconds()
        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"
        
        stats = self.memory_manager.get_stats()
        
        print(f"\n📊 Memory Worker Stats", flush=True)
        print(f"  Uptime: {uptime_str}", flush=True)
        print(f"  Meldinger prosessert: {self.processed_count}", flush=True)
        print(f"  Extractions: {self.extractor.extraction_count}", flush=True)
        print(f"  Ventende meldinger: {stats['unprocessed_messages']}", flush=True)
        print(f"  Total minner: {stats['total_memories']}", flush=True)
        print(f"  Total facts: {stats['total_facts']}", flush=True)
        print(f"  Database størrelse: {stats['db_size_mb']} MB\n", flush=True)
    
    def _generate_session_summary(self, session_id: str):
        """
        Generer automatisk oppsummering av en session
        """
        try:
            # Hent alle meldinger i session
            conn = self.memory_manager._get_connection()
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
                conn.close()
                return
            
            # Finn start og slutt tid
            start_time = session_messages[0]['timestamp']
            end_time = session_messages[-1]['timestamp']
            
            # Ekstraher topics fra metadata
            import json
            all_topics = set()
            for msg in session_messages:
                if msg.get('metadata'):
                    try:
                        meta = json.loads(msg['metadata'])
                        all_topics.update(meta.get('topics', []))
                    except:
                        pass
            
            topics_str = ', '.join(sorted(all_topics)) if all_topics else 'general'
            
            # Lag en kort oppsummering ved å samle første og siste melding
            summary = f"Samtale med {len(session_messages)} meldinger. Topics: {topics_str}"
            
            # Lagre summary
            c.execute("""
                INSERT INTO session_summaries 
                (session_id, summary, message_count, topics, start_time, end_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, summary, len(session_messages), topics_str, start_time, end_time))
            conn.commit()
            conn.close()
            
            print(f"  ✅ Session summary lagret: {summary}", flush=True)
        except Exception as e:
            print(f"  ⚠️ Kunne ikke generere session summary: {e}", flush=True)
    
    def run(self):
        """
        Hovedløkke: kjør kontinuerlig
        """
        print("🚀 Memory Worker startet", flush=True)
        print(f"  Check interval: {CHECK_INTERVAL}s", flush=True)
        print(f"  Batch size: {BATCH_SIZE}", flush=True)
        print(f"  Model: {'gpt-3.5-turbo' if USE_CHEAP_MODEL else 'gpt-4o-mini'}", flush=True)
        print(f"  API key: {'✅' if OPENAI_API_KEY else '❌'}\n", flush=True)
        
        if not OPENAI_API_KEY:
            print("❌ OPENAI_API_KEY ikke satt i .env!", flush=True)
            return
        
        stats_counter = 0
        summary_counter = 0
        
        while True:
            try:
                # Prosesser ventende meldinger
                processed = self.process_pending_messages()
                
                # Print stats hver 60. iterasjon (5 min ved 5s interval)
                stats_counter += 1
                if stats_counter >= 60:
                    self.print_stats()
                    stats_counter = 0
                
                # Generer session summaries hver 120. iterasjon (10 min ved 5s interval)
                summary_counter += 1
                if summary_counter >= 120:
                    self._check_and_summarize_old_sessions()
                    summary_counter = 0
                
                # Vent før neste sjekk
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n👋 Memory Worker stopper...", flush=True)
                self.print_stats()
                break
            except Exception as e:
                print(f"❌ Worker error: {e}", flush=True)
                time.sleep(CHECK_INTERVAL * 2)  # Lengre pause ved feil
    
    def _check_and_summarize_old_sessions(self):
        """
        Finn sessions som er eldre enn 30 min og generer summaries
        """
        try:
            from datetime import datetime, timedelta
            cutoff_time = (datetime.now() - timedelta(minutes=30)).isoformat()
            
            conn = self.memory_manager._get_connection()
            c = conn.cursor()
            
            # Finn sessions uten summary som er gamle nok
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
            conn.close()
            
            if old_sessions:
                print(f"📝 Fant {len(old_sessions)} session(s) å oppsummere", flush=True)
                for row in old_sessions:
                    self._generate_session_summary(row['session_id'])
        except Exception as e:
            print(f"⚠️ Feil ved session summary check: {e}", flush=True)


def main():
    """
    Main entry point
    """
    try:
        # Initialiser
        memory_manager = MemoryManager()
        extractor = MemoryExtractor(OPENAI_API_KEY)
        worker = MemoryWorker(memory_manager, extractor)
        
        # Kjør worker
        worker.run()
        
    except Exception as e:
        print(f"❌ Fatal error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
