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
        
    def extract_from_conversation(self, user_text: str, ai_response: str) -> Dict:
        """
        Ekstraher minner fra én utveksling
        
        Returnerer:
        {
            'profile_facts': [...],
            'memories': [...],
            'topics': [...],
            'importance': 1-5
        }
        """
        
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

3. **Topics**: Emne-kategorier
   - Velg fra: family, hobby, work, projects, technical, health, pets, preferences, weather, time, general, collection

4. **Importance**: Hvor viktig er denne samtalen? (1-5)
   - 1: Triviell (vær, tid, small talk)
   - 3: Moderat (informasjon, spørsmål)
   - 5: Viktig (personlig info, planer, preferanser)

**Samtale:**
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
    
    def _process_message(self, msg):
        """
        Prosesser én melding: ekstraher og lagre minner
        """
        # Ekstraher minner via LLM
        extracted = self.extractor.extract_from_conversation(
            msg.user_text,
            msg.ai_response
        )
        
        # Lagre profile facts
        for fact_data in extracted.get('profile_facts', []):
            try:
                fact = ProfileFact(
                    key=fact_data['key'],
                    value=fact_data['value'],
                    topic=fact_data.get('topic', 'general'),
                    confidence=fact_data.get('confidence', 0.8),
                    source=fact_data.get('source', 'extracted')
                )
                self.memory_manager.save_profile_fact(fact)
                
                # Generer embedding for ny fact
                self.memory_manager.update_fact_embedding(fact.key)
                
                print(f"  ✅ Fact: {fact.key} = {fact.value}", flush=True)
            except Exception as e:
                print(f"  ⚠️ Kunne ikke lagre fact: {e}", flush=True)
        
        # Lagre memories
        for mem_data in extracted.get('memories', []):
            try:
                memory = Memory(
                    text=mem_data['text'],
                    topic=mem_data.get('topic', 'general'),
                    confidence=mem_data.get('confidence', 0.8),
                    source='extracted'
                )
                self.memory_manager.save_memory(memory)
                print(f"  ✅ Memory: {memory.text[:50]}...", flush=True)
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
        
        while True:
            try:
                # Prosesser ventende meldinger
                processed = self.process_pending_messages()
                
                # Print stats hver 60. iterasjon (5 min ved 5s interval)
                stats_counter += 1
                if stats_counter >= 60:
                    self.print_stats()
                    stats_counter = 0
                
                # Vent før neste sjekk
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n👋 Memory Worker stopper...", flush=True)
                self.print_stats()
                break
            except Exception as e:
                print(f"❌ Worker error: {e}", flush=True)
                time.sleep(CHECK_INTERVAL * 2)  # Lengre pause ved feil


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
