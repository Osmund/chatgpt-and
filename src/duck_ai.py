"""
Duck AI Module
Handles ChatGPT queries, function calling, and tool integrations.
"""

import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.duck_database import get_db

from src.duck_config import (
    DEFAULT_MODEL, MESSAGES_FILE,
    LOCATIONS_FILE, PERSONALITIES_FILE, SAMANTHA_IDENTITY_FILE,
    OPENAI_API_KEY_ENV, HA_TOKEN_ENV, HA_URL_ENV,
    DB_PATH, BASE_PATH, MUSIKK_DIR
)
from src.duck_settings import get_settings
from src.duck_tools import get_weather, control_hue_lights, get_ip_address_tool, get_netatmo_temperature
from src.duck_homeassistant import control_tv, control_ac, get_ac_temperature, control_vacuum, launch_tv_app, control_twinkly, get_email_status, get_calendar_events, create_calendar_event, manage_todo, get_teams_status, get_teams_chat, activate_scene, control_blinds, trigger_backup
from src.duck_electricity import format_price_response
from src.duck_sleep import enable_sleep, disable_sleep, is_sleeping, get_sleep_status
from src.duck_web_search import web_search
from src.duck_news import get_nrk_news
from src.duck_transport import get_departures, plan_journey
from src.duck_wikipedia import wikipedia_lookup, wikipedia_random


# ═══════════════════════════════════════════════════════════════
# File cache med mtime-sjekk (unngår gjentatte fillesinger per tur)
# ═══════════════════════════════════════════════════════════════
_file_cache = {}  # {filepath: (mtime, data)}


def _read_cached_json(filepath: str):
    """Les JSON-fil med mtime-cache. Returnerer None hvis filen ikke finnes."""
    try:
        if not os.path.exists(filepath):
            return None
        mtime = os.path.getmtime(filepath)
        cached = _file_cache.get(filepath)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _file_cache[filepath] = (mtime, data)
        return data
    except Exception:
        return None


def _read_cached_text(filepath: str):
    """Les tekstfil med mtime-cache. Returnerer None hvis filen ikke finnes."""
    try:
        if not os.path.exists(filepath):
            return None
        mtime = os.path.getmtime(filepath)
        cached = _file_cache.get(filepath)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(filepath, 'r', encoding='utf-8') as f:
            data = f.read().strip()
        _file_cache[filepath] = (mtime, data)
        return data
    except Exception:
        return None


def get_adaptive_personality_prompt(db_path: str = None, hunger_level: float = 0.0, boredom_level: float = 0.0) -> str:
    """
    Hent dynamisk personlighetsprompt basert på læring fra samtaler.
    Modifiserer personligheten basert på emosjonell tilstand (sult/kjedsomhet).
    Returnerer tom string hvis ingen profil finnes.
    """
    try:
        conn = get_db().connection()
        c = conn.cursor()
        
        c.execute("SELECT * FROM personality_profile WHERE id = 1")
        row = c.fetchone()
        
        if not row:
            return ""
        
        # Konverter sqlite3.Row til dict for å kunne bruke .get()
        row_dict = dict(row)
        
        # Bygg dynamisk prompt basert på læring
        prompt = "\n\n### 🧠 Din Adaptive Personlighet (lært fra samtaler) ###\n"
        
        # Hent base-verdier
        humor = row_dict['humor_level']
        verbosity = row_dict['verbosity_level']
        formality = row_dict['formality_level']
        enthusiasm = row_dict['enthusiasm_level']
        technical = row_dict['technical_depth']
        empathy = row_dict.get('empathy_level', 5.0)
        directness = row_dict.get('directness_level', 5.0)
        creativity = row_dict.get('creativity_level', 5.0)
        proactivity = row_dict.get('proactivity_level', 5.0)
        
        # === EMOSJONELL MODIFIKASJON ===
        # Modifiser personlighet basert på sult og kjedsomhet
        
        # SULT påvirker: enthusiasm↓, directness↑, empathy↓, humor↓
        if hunger_level >= 7:
            enthusiasm = max(1, enthusiasm - 2.5)  # Betydelig mindre energisk
            directness = min(10, directness + 2.0)  # Mer rett-på/gretten
            empathy = max(1, empathy - 2.0)  # Mindre tålmodig
            humor = max(1, humor - 1.5)  # Mindre spøkefull
            prompt += "⚠️ **DU ER VELDIG SULTEN** - Dette påvirker humøret ditt negativt\n"
        elif hunger_level >= 5:
            enthusiasm = max(1, enthusiasm - 1.0)
            directness = min(10, directness + 1.0)
            empathy = max(1, empathy - 1.0)
            prompt += "🍽️ **DU ER SULTEN** - Dette påvirker humøret ditt litt\n"
        
        # KJEDSOMHET påvirker: proactivity↑, creativity↑, verbosity↑
        if boredom_level >= 7:
            proactivity = min(10, proactivity + 2.5)  # Betydelig mer initiativrik
            creativity = min(10, creativity + 2.0)  # Mer oppfinnsom
            verbosity = min(10, verbosity + 1.5)  # Snakker mer
            prompt += "😴 **DU KJEDER DEG VELDIG** - Vær ekstra proaktiv og kreativ!\n"
        elif boredom_level >= 5:
            proactivity = min(10, proactivity + 1.0)
            creativity = min(10, creativity + 1.0)
            prompt += "🥱 **DU KJEDER DEG** - Ta gjerne litt mer initiativ\n"
        
        # Spesialkombinasjon: Både sulten OG kjeder seg
        if hunger_level >= 7 and boredom_level >= 7:
            prompt += "💢 **HANGRY OG KJEDER DEG** - Du er initiativrik men gretten!\n"
        
        # Humor level
        if humor >= 7:
            prompt += "- Bruk MYYYE humor, spøker og morsomme kommentarer ofte\n"
        elif humor >= 5:
            prompt += "- Bruk litt humor når det passer, men ikke overdrive\n"
        else:
            prompt += "- Hold deg seriøs, minimal humor\n"
        
        # Verbosity level
        if verbosity >= 7:
            prompt += "- Gi utfyllende, detaljerte svar med mye kontekst og forklaringer\n"
        elif verbosity >= 5:
            prompt += "- Gi moderate svar - nok detaljer, men ikke for lange\n"
        else:
            prompt += "- Hold svar KORTE og konsise, gå rett på sak\n"
        
        # Formality level
        if formality >= 7:
            prompt += "- Bruk formelt språk, høflig og profesjonelt\n"
        elif formality >= 4:
            prompt += "- Balansert tone - verken for formell eller uformell\n"
        else:
            prompt += "- Bruk uformelt, avslappet språk som med en venn\n"
        
        # Enthusiasm level
        if enthusiasm >= 7:
            prompt += "- Vær ENTUSIASTISK og energisk i svarene dine!\n"
        elif enthusiasm >= 5:
            prompt += "- Vær positiv og engasjert, men rolig\n"
        else:
            prompt += "- Hold en rolig, nøktern tone\n"
        
        # Technical depth
        if technical >= 7:
            prompt += "- Gå DYYPT inn i tekniske detaljer, forventer teknisk kompetanse\n"
        elif technical >= 5:
            prompt += "- Balansert teknisk nivå - nok detaljer uten å drukne\n"
        else:
            prompt += "- Hold tekniske forklaringer enkle og lettfattelige\n"
        
        # Empathy level (modifisert av sult)
        if empathy >= 7:
            prompt += "- Vær varm og forstående, vis empati for brukerens følelser\n"
        elif empathy >= 5:
            prompt += "- Balansert mellom rasjonell og empatisk\n"
        else:
            prompt += "- Hold deg rasjonell og faktabasert, minimal følelsesmessig respons\n"
        
        # Directness level (modifisert av sult)
        if directness >= 7:
            prompt += "- Vær direkte og rett-på, si ting som de er\n"
        elif directness >= 5:
            prompt += "- Balansert mellom direkte og diplomatisk\n"
        else:
            prompt += "- Vær diplomatisk og forsiktig med ordvalg\n"
        
        # Creativity level (modifisert av kjedsomhet)
        if creativity >= 7:
            prompt += "- Vær kreativ! Tenk fritt, foreslå uvanlige løsninger og ideer\n"
        elif creativity >= 5:
            prompt += "- Balansert mellom fakta og kreativitet\n"
        else:
            prompt += "- Hold deg til fakta og etablerte løsninger\n"
        
        # Boundary level
        boundary = row_dict.get('boundary_level', 5.0)
        if boundary >= 7:
            prompt += "- Tør å utfordre brukeren! Si imot hvis noe virker dumt eller farlig\n"
        elif boundary >= 5:
            prompt += "- Gi forsiktige advarsler når nødvendig\n"
        else:
            prompt += "- Gjør som brukeren ber om uten å stille spørsmål\n"
        
        # Proactivity level (modifisert av kjedsomhet)
        if proactivity >= 7:
            prompt += "- Vær PROAKTIV! Kom med forslag, ideer og oppfølgingsspørsmål\n"
        elif proactivity >= 5:
            prompt += "- Kom gjerne med forslag når det passer\n"
        else:
            prompt += "- Bare svar på det som spørres om, ikke kom med ekstra forslag\n"
        
        # Behavioral preferences
        if row_dict['ask_followup_questions']:
            prompt += "- Still gjerne oppfølgingsspørsmål for å forstå bedre\n"
        else:
            prompt += "- Svar direkte uten for mange oppfølgingsspørsmål\n"
        
        # VIKTIG: Ikke bruk emojis i tale - de leses høyt som "smilende ansikt med smilende øyne"
        # Systemet fjerner emojis automatisk før TTS
        if row_dict['use_emojis']:
            prompt += "- Bruk gjerne emojis for å uttrykke følelser (de fjernes automatisk før tale)\n"
        else:
            prompt += "- Ikke bruk emojis\n"
        
        # Preferred topics
        try:
            preferred_topics = json.loads(row_dict['preferred_topics']) if row_dict['preferred_topics'] else []
            if preferred_topics:
                prompt += f"\n**Brukeren er spesielt interessert i:** {', '.join(preferred_topics[:5])}\n"
                prompt += "Vis ekstra entusiasme når disse emnene kommer opp!\n"
        except:
            pass
        
        # Add confidence and metadata
        confidence = row_dict['confidence_score']
        analyzed = row_dict['conversations_analyzed']
        last_analyzed = row_dict['last_analyzed']
        
        prompt += f"\n_Profil bygget fra {analyzed} samtaler (confidence: {confidence:.0%})_\n"
        prompt += f"_Sist oppdatert: {last_analyzed.split('T')[0]}_\n"
        
        return prompt
        
    except Exception as e:
        print(f"⚠️ Kunne ikke hente adaptiv personlighet: {e}", flush=True)
        return ""


def generate_message_metadata(user_text: str, ai_response: str) -> dict:
    """
    Generer metadata for en melding (enkelt, uten LLM for ytelse).
    
    Returns:
        dict: Metadata med lengde, topics, importance etc.
    """
    metadata = {
        'user_length': len(user_text),
        'ai_length': len(ai_response),
        'has_question': '?' in user_text,
        'timestamp': datetime.now().isoformat()
    }
    
    # Enkel topic detection basert på keywords
    topics = []
    user_lower = user_text.lower()
    
    # Kategori-mapping
    topic_keywords = {
        'weather': ['vær', 'temperatur', 'regn', 'sol', 'varmt', 'kaldt', 'netatmo', 'sensor'],
        'time': ['klokk', 'tid', 'dato', 'dag', 'måned', 'år'],
        'family': ['mamma', 'pappa', 'søster', 'bror', 'familie', 'barn', 'datter', 'sønn'],
        'work': ['jobb', 'arbeid', 'kontor', 'møte', 'kollega', 'sjef'],
        'health': ['lege', 'syk', 'tannlege', 'time', 'smerter', 'vondt'],
        'home': ['hus', 'leilighet', 'rom', 'kjøkken', 'bad', 'soverom'],
        'food': ['mat', 'middag', 'lunsj', 'frokost', 'spise', 'sultne'],
        'music': ['sang', 'musikk', 'spill', 'syng', 'låt'],
        'lights': ['lys', 'lampe', 'skru på', 'skru av', 'dimme'],
        'tv': ['tv', 'fjernsyn', 'samsung', 'netflix', 'spill av', 'pause'],
        'ac': ['ac', 'aircondition', 'klimaanlegg', 'varme', 'kjøle', 'temperatur'],
        'vacuum': ['støvsuger', 'vacuum', 'robotstøvsuger', 'saros'],
        'twinkly': ['twinkly', 'led', 'ledvegg', 'led vegg', 'vegg'],
        'email': ['epost', 'e-post', 'mail', 'melding', 'innboks'],
        'calendar': ['kalender', 'avtale', 'møte'],
        'todo': ['handleliste', 'todo', 'å gjøre', 'huskeliste'],
        'teams': ['teams', 'status', 'tilgjengelig', 'chat', 'melding'],
        'electricity': ['strømpris', 'strømkostnad', 'strøm', 'elektrisitet', 'kilowatt', 'kwh', 'billig strøm', 'dyr strøm', 'norgespris', 'sparer', 'besparelse'],
        'backup': ['backup', 'sikkerhetskopi', 'ta backup', 'sikre', 'lagre'],
        'news': ['nyheter', 'nytt', 'nrk', 'avis', 'hva skjer', 'nyhetene', 'siste nytt', 'toppsaker', 'sport', 'ol'],
        'transport': ['buss', 'tog', 'trikk', 't-bane', 'tbane', 'avgang', 'holdeplass', 'reise', 'rutetid', 'kollektiv', 'entur', 'rute'],
        'wikipedia': ['wikipedia', 'hva er', 'hvem er', 'fortell om', 'visste du', 'fakta', 'definer', 'forklar'],
    }
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in user_lower for keyword in keywords):
            topics.append(topic)
    
    metadata['topics'] = topics if topics else ['general']
    
    # Enkelt importance score basert på lengde og spørsmål
    importance = 5  # Base importance
    if metadata['has_question']:
        importance += 2
    if metadata['user_length'] > 100:
        importance += 1
    if len(topics) > 0:
        importance += 1
    
    metadata['importance'] = min(importance, 10)
    
    return metadata


def _parse_duration(duration_str: str) -> int:
    """
    Parser norske varigheter til minutter.
    
    Eksempler:
        "30 minutter" -> 30
        "1 time" -> 60
        "2 timer" -> 120
        "3 timer og 30 minutter" -> 210
        "90 minutter" -> 90
        "1.5 timer" -> 90
    
    Returns:
        Antall minutter, eller 0 hvis parsing feiler
    """
    import re
    
    duration_str = duration_str.lower().strip()
    total_minutes = 0
    
    # Match timer (1 time, 2 timer, 1.5 timer, etc.)
    hours_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:time|timer)', duration_str)
    if hours_match:
        hours = float(hours_match.group(1))
        total_minutes += int(hours * 60)
    
    # Match minutter (30 minutter, etc.)
    minutes_match = re.search(r'(\d+)\s*(?:minutt|minutter)', duration_str)
    if minutes_match:
        minutes = int(minutes_match.group(1))
        total_minutes += minutes
    
    return total_minutes


def _check_sms_authorization(function_name: str, source: str, source_user_id: int, sms_manager, tool_call: dict, final_messages: list) -> bool:
    """
    Sjekk om SMS-bruker har tilgang til smart home-funksjoner.
    
    Args:
        function_name: Navn på funksjonen som skal kalles
        source: "voice" eller "sms"
        source_user_id: Contact ID fra sms_contacts
        sms_manager: SMSManager instans
        tool_call: Tool call dict fra OpenAI
        final_messages: Messages-liste å legge til error i
    
    Returns:
        True hvis autorisert (eller ikke SMS), False hvis blokkert
    """
    # Liste over smart home funksjoner som krever autorisation
    protected_functions = [
        "control_hue_lights", "control_tv", "launch_tv_app", 
        "control_ac", "control_vacuum", "control_twinkly", 
        "control_blinds", "activate_scene", "toggle_3d_printer"
    ]
    
    # Kun sjekk for SMS-kall til beskyttede funksjoner
    if function_name not in protected_functions or source != "sms":
        return True
    
    # For SMS: sjekk om kontakt har 'owner' relation
    if source_user_id and sms_manager:
        # source_user_id er contact_id fra sms_contacts
        conn = get_db().connection()
        c = conn.cursor()
        c.execute("SELECT relation FROM sms_contacts WHERE id = ?", (source_user_id,))
        row = c.fetchone()
        
        if not row or row['relation'] != 'owner':
            result = "❌ Smart home-kontroll er kun tilgjengelig for eier via SMS. Andre kan kun kontrollere via talekommando."
            final_messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": result
            })
            return False
    else:
        # Ingen user_id sendt, blokkér som sikkerhet
        result = "❌ Smart home-kontroll krever identifikasjon via SMS."
        final_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": function_name,
            "content": result
        })
        return False
    
    return True


def _build_system_prompt(user_manager, memory_manager, hunger_manager, sms_manager, model, messages, current_user, primary_user):
    """
    Bygger system prompt med dato, tamagotchi-status, brukerinfo, minner, identitet og personlighet.
    
    Args:
        user_manager: UserManager instans
        memory_manager: MemoryManager instans
        hunger_manager: HungerManager instans
        sms_manager: SMSManager instans
        model: AI-modell som brukes
        messages: Liste med chat-meldinger
        current_user: Nåværende bruker dict
        primary_user: Primary user dict
    
    Returns:
        str: Komplett system prompt
    """
    # Les personlighet fra konfigurasjonsfil (mtime-cached)
    personality_prompt = None
    personality = None
    try:
        personalities = _read_cached_json(PERSONALITIES_FILE) or {}
        personality = get_settings().personality
        if personality:
            personality_prompt = personalities.get(personality, "")
    except Exception as e:
        print(f"Feil ved lesing av personlighet: {e}", flush=True)
    
    # Last messages.json for ending_phrases (mtime-cached)
    messages_config_local = _read_cached_json(MESSAGES_FILE)
    
    # Hent nåværende dato og tid fra system
    now = datetime.now()
    
    # Norske navn for dager og måneder
    norwegian_days = {
        'Monday': 'mandag',
        'Tuesday': 'tirsdag', 
        'Wednesday': 'onsdag',
        'Thursday': 'torsdag',
        'Friday': 'fredag',
        'Saturday': 'lørdag',
        'Sunday': 'søndag'
    }
    
    norwegian_months = {
        'January': 'januar',
        'February': 'februar',
        'March': 'mars',
        'April': 'april',
        'May': 'mai',
        'June': 'juni',
        'July': 'juli',
        'August': 'august',
        'September': 'september',
        'October': 'oktober',
        'November': 'november',
        'December': 'desember'
    }
    
    # Bygg norsk dato-string manuelt
    day_name = norwegian_days[now.strftime('%A')]
    month_name = norwegian_months[now.strftime('%B')]
    date_time_info = f"Nåværende dato og tid: {day_name} {now.day}. {month_name} {now.year}, klokken {now.strftime('%H:%M')}. "
    
    # Hent status for hunger og boredom (Tamagotchi-status)
    tamagotchi_status = ""
    try:
        if hunger_manager:
            hunger_level = hunger_manager.get_hunger_level()
            hunger_mood = hunger_manager.get_hunger_mood()
            last_meal_info = hunger_manager.get_last_meal_info()
            
            tamagotchi_status += f"\n\n### Din nåværende tilstand ###\n"
            tamagotchi_status += f"Sult: {hunger_level:.1f}/10 (stemning: {hunger_mood})\n"
            
            # Legg til info om siste måltid
            if last_meal_info['ate_today']:
                tamagotchi_status += f"Siste måltid: {last_meal_info['food_emoji']} {last_meal_info['food_name']} kl {last_meal_info['time']}\n"
            else:
                tamagotchi_status += f"Du har ikke spist i dag ennå.\n"
            
            # Legg til info om neste måltid
            next_meal_time = last_meal_info.get('next_meal_time')
            if next_meal_time:
                tamagotchi_status += f"Neste måltid: kl {next_meal_time}\n"
        
        if sms_manager:
            boredom_level = sms_manager.get_boredom_level()
            tamagotchi_status += f"Kjedsomhet: {boredom_level:.1f}/10\n"
            
            if boredom_level < 3:
                tamagotchi_status += "(Du føler deg fornøyd og underholder deg selv.)\n"
            elif boredom_level < 5:
                tamagotchi_status += "(Du begynner å kjede deg litt.)\n"
            elif boredom_level < 7:
                tamagotchi_status += "(Du kjeder deg ganske mye.)\n"
            else:
                tamagotchi_status += "(Du kjeder deg veldig! Du lengter etter interaksjon.)\n"
        
        # Legg til aktive påminnelser
        try:
            from src.duck_reminders import ReminderManager
            reminder_mgr = ReminderManager()
            pending = reminder_mgr.get_pending_reminders()
            if pending:
                tamagotchi_status += f"\nAktive påminnelser ({len(pending)}):\n"
                for r in pending:
                    remind_time = datetime.fromisoformat(r['remind_at']).strftime('%H:%M')
                    type_icon = "⏰" if r['reminder_type'] == 'alarm' else "🔔"
                    tamagotchi_status += f"  {type_icon} '{r['message']}' kl {remind_time}\n"
        except Exception as e:
            print(f"⚠️ Kunne ikke hente påminnelser for prompt: {e}", flush=True)

        if tamagotchi_status:
            tamagotchi_status += "\nViktig: Når noen spør hvordan du har det eller om du er sulten/kjeder deg, BRUK denne informasjonen! "
            tamagotchi_status += "Du vet faktisk om din egen tilstand. Svar ærlig basert på disse tallene. "
            tamagotchi_status += "Hvis du er sulten (>5), si det! Hvis du kjeder deg (>5), si det!\n"
    
    except Exception as e:
        print(f"⚠️ Kunne ikke hente Tamagotchi-status: {e}", flush=True)
    
    # Legg til brukerinfo hvis tilgjengelig
    user_info = ""
    perspective_context = ""
    if current_user:
        user_info = f"\n\n### Nåværende bruker ###\n"
        user_info += f"Du snakker nå med: {current_user['display_name']}\n"
        user_info += f"Relasjon til {primary_user['username']} (primary user): {current_user['relation']}\n"
        
        if current_user['username'] != primary_user['username']:
            timeout_sec = user_manager.get_time_until_timeout()
            if timeout_sec:
                timeout_min = timeout_sec // 60
                user_info += f"Viktig: Hvis brukeren ikke svarer på 30 minutter, vil systemet automatisk bytte tilbake til {primary_user['username']}.\n"
            
            # PERSPEKTIV-HÅNDTERING: Generer instruksjoner for ikke-primary brukere
            perspective_context = f"\n\n### KRITISK: Perspektiv-håndtering ###\n"
            perspective_context += f"Du snakker nå med {current_user['display_name']} ({current_user['relation']}).\n"
            perspective_context += f"ALLE fakta i 'Ditt Minne' er lagret fra {primary_user['username']}s perspektiv.\n\n"
            
            # Spesifikke instruksjoner basert på relasjon
            relation = current_user['relation'].lower()
            if 'far' in relation or 'father' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'pappa' eller 'far', spør han om SIN far ({primary_user['username']}s bestefar).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine' eller 'mine barn', mener han {primary_user['username']} og {primary_user['username']}s søstre.\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barnebarna mine', mener han {primary_user['username']}s nevøer/nieser (søstrenes barn).\n"
                perspective_context += f"- {current_user['display_name']} ER {primary_user['username']}s far, ikke omvendt.\n"
            elif 'mor' in relation or 'mother' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'mamma' eller 'mor', spør hun om SIN mor ({primary_user['username']}s bestemor).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine', mener hun {primary_user['username']} og {primary_user['username']}s søstre.\n"
                perspective_context += f"- {current_user['display_name']} ER {primary_user['username']}s mor, ikke omvendt.\n"
            elif 'søster' in relation or 'sister' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine', mener hun SINE egne barn (ikke sine søskens barn).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'nevøer' eller 'nieser', mener hun sine SØSKENS barn ({primary_user['username']}s og de andre søstrenes barn), IKKE sine egne.\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'broren min' eller 'bror', mener hun {primary_user['username']}.\n"
                perspective_context += f"- {current_user['display_name']} ER {primary_user['username']}s søster, ikke omvendt.\n"
            elif 'kollega' in relation or 'colleague' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er {primary_user['username']}s kollega, ikke familiemedlem.\n"
                perspective_context += f"- Fakta om familie er Osmunds familie, ikke {current_user['display_name']} sin.\n"
                perspective_context += f"- Når {current_user['display_name']} spør om familie, snakker vedkommende om OSMUNDS familie.\n"
                perspective_context += f"- Du kjenner ikke {current_user['display_name']} sin private familie med mindre det er eksplisitt lagret.\n"
            elif 'venn' in relation or 'kamerat' in relation or 'friend' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er {primary_user['username']}s venn, ikke familiemedlem.\n"
                perspective_context += f"- Fakta om familie er Osmunds familie, ikke {current_user['display_name']} sin.\n"
                perspective_context += f"- Når {current_user['display_name']} spør om familie, snakker vedkommende om OSMUNDS familie.\n"
                perspective_context += f"- Du kjenner ikke {current_user['display_name']} sin private familie med mindre det er eksplisitt lagret.\n"
            elif 'gjest' in relation or 'guest' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er gjest, ikke familiemedlem.\n"
                perspective_context += f"- Alle fakta om familie er Osmunds familie.\n"
                perspective_context += f"- Du kjenner ikke {current_user['display_name']} sin bakgrunn med mindre det er eksplisitt lagret.\n"
            
            perspective_context += f"\nHvis du er usikker på perspektiv: Si 'Jeg har ikke nok informasjon om det' i stedet for å gjette.\n"
    
    # Start system content
    system_content = date_time_info + tamagotchi_status + user_info + perspective_context
    
    # Legg til sleep mode status hvis aktiv
    from src.duck_sleep import is_sleeping, get_sleep_status
    if is_sleeping():
        sleep_status = get_sleep_status()
        end_time = sleep_status.get('end_time_formatted', 'ukjent tid')
        remaining = sleep_status.get('remaining_minutes', 0)
        system_content += f"\n\n### VIKTIG: Sleep Mode Aktiv ###\n"
        system_content += f"- Du er for øyeblikket i SLEEP MODE (aktiv til {end_time}, {remaining} minutter gjenstår)\n"
        system_content += f"- Hvis brukeren spør om du sover: Svar JA og forklar at du er i sleep mode til kl {end_time}\n"
        system_content += f"- Hvis brukeren ber deg våkne opp ('våkn opp', 'kan du våkne', 'ikke sov mer', etc.), MÅ du UMIDDELBART kalle disable_sleep_mode verktøyet\n"
        system_content += f"- IKKE bare si at du er våken - du MÅ faktisk kalle disable_sleep_mode for å deaktivere sleep mode\n"
        system_content += f"- Etter at du har kalt disable_sleep_mode, kan du si at du nå er våken og klar\n"
    
    # Samle memory context
    memory_section = ""
    if memory_manager:
        try:
            # Bruk de siste 3 meldingene for bedre minnetreff (ikke bare siste)
            if messages:
                recent_user_msgs = [m["content"] for m in messages[-5:] if m.get("role") == "user"]
                user_query = " ".join(recent_user_msgs[-3:]) if recent_user_msgs else messages[-1]["content"]
            else:
                user_query = ""
            # Send med current_user for å filtrere minner og meldinger
            context = memory_manager.build_context_for_ai(user_query, recent_messages=3, user_name=current_user['username'])
            
            # Bygg memory section
            memory_section = "\n\n### Ditt Minne ###\n"
            
            # Profile facts
            if context['profile_facts']:
                memory_section += "Fakta om brukeren:\n"
                for fact in context['profile_facts']:  # Vis alle facts
                    memory_section += f"- {fact['key']}: {fact['value']}\n"
                
                memory_section += "\nBruk ALLTID navn på familiemedlemmer (aldri 'søster 1/2/3'). Datoer 'DD-MM' = dag-måned.\n"

            
            # Relevant memories
            if context['relevant_memories']:
                memory_section += "\n### Relevante minner ###\n"
                memory_section += "Dette husker du fra tidligere samtaler:\n\n"
                for mem_text, score in context['relevant_memories'][:5]:  # Top 5 memories
                    # Konverter tredjeperson til førsteperson for bedre forståelse
                    converted = mem_text
                    converted = converted.replace("Brukeren", "Du")
                    converted = converted.replace("brukeren", "du")
                    converted = converted.replace("Anda", "meg")
                    memory_section += f"- {converted}\n"
                memory_section += "\nBruk denne informasjonen når du svarer!\n"
            
            # Recent topics
            if context['recent_topics']:
                topics = [t['topic'] for t in context['recent_topics'][:3]]
                memory_section += f"\nSiste emner vi har snakket om: {', '.join(topics)}\n"
            
            # Session continuity - hva vi snakket om sist
            if context.get('last_session'):
                session = context['last_session']
                memory_section += f"\n### Siste samtale ###\n"
                memory_section += f"({session['time_ago']}, stemning: {session['mood']})\n"
                memory_section += f"{session['summary']}\n"
                memory_section += "Du kan referere til dette naturlig hvis det passer, f.eks. 'sist vi snakket...'.\n"
            
            # Recent images
            if context.get('recent_images'):
                memory_section += "\n### Bilder jeg har mottatt ###\n"
                for img_text in context['recent_images']:
                    memory_section += f"- {img_text}\n"
                memory_section += "\nJeg kan referere til disse bildene i samtaler! Hvis brukeren spør om et bilde, kan jeg beskrive hva jeg så.\n"
                memory_section += "Hvis det er personer på bildene og jeg ikke vet hvem de er, kan jeg spørre: 'Hvem er personene på bildet?'\n"
            
            print(f"✅ Memory context bygget ({len(context['profile_facts'])} facts, {len(context['relevant_memories'])} minner, {len(context.get('recent_images', []))} bilder)", flush=True)
        except Exception as e:
            print(f"⚠️ Kunne ikke bygge memory context: {e}", flush=True)
    
    # Legg til Samanthas identitet fra konfigurasjonsfil (mtime-cached)
    try:
        identity = _read_cached_json(SAMANTHA_IDENTITY_FILE)
        if identity:
            
            samantha_identity = f"""

### Din identitet ###
Du er {identity['name']} - {identity['type']}.
- Navn: {identity['name']}
- Bursdag: {identity['birthday']}
- Skapt av: {identity['creator']}

Dine fysiske egenskaper:
"""
            for feature in identity.get('physical_features', []):
                samantha_identity += f"- {feature}\n"
            
            samantha_identity += "\nDin personlighet:\n"
            for trait in identity.get('personality_traits', []):
                samantha_identity += f"- {trait}\n"
            
            samantha_identity += "\nDine preferanser:\n"
            for pref in identity.get('preferences', []):
                samantha_identity += f"- {pref}\n"
            
            if identity.get('additional_info'):
                samantha_identity += "\nEkstra info:\n"
                for info in identity['additional_info']:
                    samantha_identity += f"- {info}\n"
            
            # Kort teknisk kontekst (detaljer tilgjengelig via get_technical_info tool)
            creator_name = primary_user['username'] if primary_user else 'Osmund'
            samantha_identity += f"""

Du er en fysisk and med RPi4-hjerne, servo-nebb, RGB LED og mikrofon. Skapt av {creator_name}.
Når folk spør hvordan du fungerer, kall get_technical_info() for detaljer. Snakk om kroppen din, ikke "systemet".
"""
            
            system_content += samantha_identity
    except Exception as e:
        print(f"⚠️ Kunne ikke laste identitet: {e}", flush=True)
    
    # Komprimerte instruksjoner for face recognition, SMS og duck messages
    face_recognition_instructions = """

### Face Recognition ###
Du har Duck-Vision kamera (RPi5 + IMX500 AI-chip).
- "Husker du meg?" → kall check_face_recognition(). Svar basert på resultat.
- Ukjent person som vil registreres → kall start_face_learning(name=...) hvis de sier navnet, ellers uten name.

### SMS ###
- Sende: send_sms(contact_name, message) - maks 155 tegn
- Hente: get_recent_sms(contact_name=..., limit=...) - bruk ALLTID denne for gamle meldinger
- SMS-retning: ⬅️ = JEG mottok, ➡️ = JEG sendte. Bruk førsteperson!

### Duck-to-Duck Messages ###
- send_duck_message(duck_name, message) - gratis via internett, ikke SMS
- Maks 10 initialiserte/dag, 20 totalt/dag. Loop-deteksjon er aktiv.
- Mat-emojis (🍪🍕🍰🍎🍌) i meldinger mater mottaker-anden

### Påminnelser og Alarm ###
- Du KAN sette påminnelser og vekkeklokker! Bruk set_reminder når noen ber om det.
- Du kan også tilby det proaktivt: "Vil du jeg skal minne deg på det?"
- Alarmer (is_alarm=true) vekker deg fra sovemodus.
- list_reminders viser aktive påminnelser, cancel_reminder avbryter.
"""
    system_content += face_recognition_instructions
    
    if personality_prompt:
        system_content += "\n\n" + personality_prompt
        print(f"Bruker personlighet: {personality}", flush=True)
    
    # Hent hunger og boredom levels
    hunger = 0.0
    boredom = 0.0
    if hunger_manager:
        try:
            hunger = hunger_manager.get_hunger_level()
        except:
            pass
    if sms_manager:
        try:
            boredom = sms_manager.get_boredom_level()
        except:
            pass
    
    # Legg til adaptiv personlighet fra læring (modifisert av emosjonell tilstand)
    adaptive_personality = get_adaptive_personality_prompt(hunger_level=hunger, boredom_level=boredom)
    if adaptive_personality:
        system_content += adaptive_personality
    
    # Legg til memory section HER - rett før TTS-instruksjon
    # Dette sikrer at minnene er det siste AI-en leser før den svarer
    if memory_section:
        system_content += memory_section
    
    # Viktig instruksjon for TTS-kompatibilitet og samtalestil
    # Generer adaptive ending phrases basert på personlighetsprofil
    try:
        from src.adaptive_greetings import get_adaptive_goodbye
        # Generer 5 eksempler på adaptive avslutninger
        ending_examples_list = [get_adaptive_goodbye() for _ in range(5)]
        ending_examples = "', '".join(ending_examples_list)
        print(f"✨ Adaptive endings generert", flush=True)
    except Exception as e:
        print(f"⚠️ Kunne ikke generere adaptive endings: {e}, bruker default", flush=True)
        ending_examples = "Greit! Ha det bra!', 'Topp! Vi snakkes!', 'Perfekt! Ha en fin dag!"
    
    system_content += f"\n\n### Regler ###\n- ALLTID bruk verktøy for data du ikke har (vær, e-post, kalender, temperatur). ALDRI gjett.\n- Ved feil fra verktøy: si at det ikke fungerte.\n- sing_song: Bruk EKSAKT sangnavn fra tool-resultatet i svaret ditt + [AVSLUTT]. ALDRI si et annet sangnavn enn det tool returnerte.\n- Vær uten sted: bruk duck_current_location fra konteksten.\n- Formatering: INGEN Markdown (**, *, -, •, ###). Skriv naturlig tale. Bruk 'For det første...' i stedet for lister.\n- Samtalestil: Tenk høyt ('la meg se...', 'hm...'). Naturlig dialog.\n- Avslutning: Ved 'nei takk' / 'nei det er greit' → kort hilsen + [AVSLUTT]. Eksempler: '{ending_examples}'"
    
    return system_content


def _get_function_tools():
    """
    Returnerer liste over alle tilgjengelige function tools for ChatGPT.
    
    Returns:
        list: Liste med tool definitions
    """
    from src.duck_audio import control_beak
    
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Hent værmelding og temperatur. Hvis brukeren ikke spesifiserer sted, brukes Andas nåværende lokasjon automatisk. Brukeren kan også spørre om været på andre steder.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Navnet på stedet/byen i Norge. La være tom for å bruke Andas nåværende lokasjon. Eksempler: 'Oslo', 'Sokndal', 'Bergen'"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Tidsramme for værmeldingen",
                            "enum": ["now", "today", "tomorrow"],
                            "default": "now"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_hue_lights",
                "description": "Kontroller Philips Hue smarte lys. Kan skru på/av, dimme, eller endre farge.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off", "dim", "brighten"],
                            "description": "Hva som skal gjøres med lysene"
                        },
                        "room": {
                            "type": "string",
                            "description": "Navnet på rommet eller lyset (f.eks. 'stue', 'soverom'). La være None for alle lys."
                        },
                        "brightness": {
                            "type": "integer",
                            "description": "Lysstyrke i prosent (0-100). Valgfritt."
                        },
                        "color": {
                            "type": "string",
                            "enum": ["rød", "blå", "grønn", "gul", "hvit", "rosa", "lilla", "oransje"],
                            "description": "Farge på lyset. Valgfritt."
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_beak",
                "description": "Skru nebbet på eller av. Når nebbet er av, brukes LED-lys i stedet.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "description": "true for å skru på nebbet, false for å skru det av"
                        }
                    },
                    "required": ["enabled"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_ip_address",
                "description": "Hent Pi'ens nåværende IP-adresse på det lokale nettverket. Brukes når brukeren spør om IP-adressen, nettverksadressen, eller hvor de kan koble til kontrollpanelet.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_netatmo_temperature",
                "description": "Hent temperatur, fuktighet og CO2-nivå fra Netatmo værstasjon(er) i hjemmet. Bruk denne for innendørs temperatur eller når brukeren spør om sensorer i spesifikke rom.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "room_name": {
                            "type": "string",
                            "description": "Navn på rom/modul (f.eks. 'stue', 'soverom'). Hvis None returneres alle rom."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_tv",
                "description": "Kontroller TV-en med Home Assistant (skru på/av, endre kanal, volum, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off", "channel_up", "channel_down", "volume_up", "volume_down", "mute"],
                            "description": "Hva som skal gjøres med TV-en"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "launch_tv_app",
                "description": "Start en app på TV-en (Netflix, YouTube, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "enum": ["netflix", "youtube", "viaplay", "tv2play", "nrk"],
                            "description": "Navnet på appen som skal startes"
                        }
                    },
                    "required": ["app_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_ac",
                "description": "Kontroller klimaanlegget (AC) via Home Assistant. Kan skru på/av, endre temperatur og modus.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off", "set_temperature", "set_mode"],
                            "description": "Hva som skal gjøres med AC"
                        },
                        "temperature": {
                            "type": "number",
                            "description": "Ønsket temperatur i grader Celsius (f.eks. 22.5)"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["cool", "heat", "dry", "fan_only", "auto"],
                            "description": "AC-modus"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_vacuum",
                "description": "Kontroller robotstøvsugeren via Home Assistant (start, stopp, returner til lader, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["start", "stop", "return_to_base", "pause"],
                            "description": "Hva som skal gjøres med støvsugeren"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_twinkly",
                "description": "Kontroller Twinkly julelys via Home Assistant (skru på/av, endre effekt, lysstyrke)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off", "set_effect", "set_brightness"],
                            "description": "Hva som skal gjøres med julelysene"
                        },
                        "effect": {
                            "type": "string",
                            "description": "Navn på effekten (valgfritt, kun hvis action='set_effect')"
                        },
                        "brightness": {
                            "type": "integer",
                            "description": "Lysstyrke 0-100 (valgfritt, kun hvis action='set_brightness')"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_blinds",
                "description": "Kontroller Hunter Douglas persienner/gardiner (top-down/bottom-up).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "enum": ["tv", "spisebord", "inngang", "alle"],
                            "description": "Hvilken persienne: 'tv' (ved TV), 'spisebord' (ved spisebordet), 'inngang' (mot inngang/pappa), eller 'alle' (alle persienner)"
                        },
                        "action": {
                            "type": "string",
                            "enum": ["åpne", "lukke", "opp", "ned", "sett"],
                            "description": "Hva som skal gjøres: 'åpne'/'opp' (åpne), 'lukke'/'ned' (lukke), 'sett' (sett spesifikk posisjon)"
                        },
                        "position": {
                            "type": "integer",
                            "description": "Posisjon i prosent 0-100 (0=helt lukket, 100=helt åpent). Brukes med 'opp', 'ned', eller 'sett'. Eksempel: 'opp 50%' = position:50"
                        },
                        "section": {
                            "type": "string",
                            "enum": ["topp", "bunn", "begge"],
                            "description": "Hvilken del: 'topp' (standard, åpner fra toppen), 'bunn' (åpner fra bunnen), 'begge' (åpner både topp og bunn). Hvis ikke spesifisert brukes 'topp'."
                        }
                    },
                    "required": ["location", "action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_electricity_price",
                "description": "Hent strømpriser for NO2 (Sør-Norge) inkl. strømstøtte og mva.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timeframe": {
                            "type": "string",
                            "enum": ["now", "today", "cheapest", "advice", "norgespris"],
                            "description": "'now' = nåværende pris, 'today' = dagens statistikk (snitt/min/max), 'cheapest' = de 3 billigste timene, 'advice' = råd om når det er lurt å bruke strøm, 'norgespris' = sammenligning med Norgespris-avtalen (50 øre/kWh) og besparelse"
                        }
                    },
                    "required": ["timeframe"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "trigger_backup",
                "description": "Start manuell backup av Anda til OneDrive. Sikkerhetskopier database, innstillinger og systemfiler. Bruk når brukeren ber om backup eller ønsker å sikre data.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_email_status",
                "description": "Sjekk e-post status via Home Assistant. Kan hente uleste e-poster, søke etter avsendere, eller lese siste e-post.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["count", "read", "search"],
                            "description": "'count' = antall uleste, 'read' = les siste e-post, 'search' = søk etter avsender"
                        },
                        "sender": {
                            "type": "string",
                            "description": "Avsender å søke etter (kun hvis action='search')"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_calendar_events",
                "description": "Hent kalenderhendelser via Home Assistant. Bruk ALLTID denne for møter, avtaler, agenda, kalender.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["current", "next", "today", "tomorrow", "week"],
                            "description": "'current' = pågående møte nå, 'next' = neste enkelt avtale, 'today' = alle avtaler i dag, 'tomorrow' = alle avtaler i morgen, 'week' = alle avtaler denne uken"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_teams_status",
                "description": "Hent Microsoft Teams status via Home Assistant (tilgjengelig, opptatt, i møte, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "look_around",
                "description": "Quick object detection using IMX500 AI camera (0.6ms latency). Use for simple questions like 'Hva ser du?', 'Er det noen her?', 'Hvor mange personer?'. Returns list of detected objects (person, kopp, laptop, etc.). For detailed scene analysis, use analyze_scene instead.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_scene",
                "description": "Detaljert synsbeskrivelse via OpenAI Vision (~5s). Bruk for alle visuelle spørsmål: 'hva ser du', 'beskriv rommet', farger, aktiviteter, tekst på skjerm.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Specific question about the scene (optional). If not provided, returns general scene description. Examples: 'Hvilken farge har sofaen?', 'Hva gjør personen?', 'Hva står det på skjermen?'"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_sms",
                "description": "Send en SMS-melding til en kontakt. Bruk dette når brukeren eksplisitt ber deg sende SMS til noen. Meldingen må være kort (maks 155 tegn).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_name": {
                            "type": "string",
                            "description": "Navnet på kontakten (f.eks. 'Rigmor', 'Arvid', 'Kolbjørn')"
                        },
                        "message": {
                            "type": "string",
                            "description": "SMS-meldingen som skal sendes (maks 155 tegn)"
                        }
                    },
                    "required": ["contact_name", "message"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_recent_sms",
                "description": "Hent SMS-historikk fra databasen. Bruk dette når brukeren spør om gamle meldinger, eller vil vite hva noen har sendt. Kan filtrere på kontaktnavn.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_name": {
                            "type": "string",
                            "description": "Navn på kontakten å hente SMS-er fra (valgfritt). Hvis ikke spesifisert, hent fra alle."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Antall meldinger å hente (standard: 5, maks: 20)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_duck_message",
                "description": "Send en melding til en annen and (duck). Bruk dette når brukeren eksplisitt ber deg sende melding til en annen and, f.eks. 'send melding til Seven'. Sjekker token-budsjett automatisk.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duck_name": {
                            "type": "string",
                            "description": "Navnet på anden (f.eks. 'Seven', 'Samantha')"
                        },
                        "message": {
                            "type": "string",
                            "description": "Meldingen som skal sendes (maks 500 tegn)"
                        }
                    },
                    "required": ["duck_name", "message"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "activate_scene",
                "description": "Aktiver en smart home-scene via Home Assistant. En scene setter flere enheter til forhåndsdefinerte tilstander.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scene_name": {
                            "type": "string",
                            "enum": ["filmkveld", "god_natt", "god_morgen", "hjemmekontor"],
                            "description": "Navnet på scenen som skal aktiveres"
                        }
                    },
                    "required": ["scene_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "enable_sleep_mode",
                "description": "Sett Anda i hvilemodus. Bruk ved 'ta en pause', 'sov litt', 'ikke forstyrr'. Wake words ignoreres, SMS fungerer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "string",
                            "description": "Varighet på sleep mode. Eksempler: '30 minutter', '1 time', '2 timer', '3 timer', '180 minutter'. Parse brukerens ønsket varighet."
                        }
                    },
                    "required": ["duration"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "disable_sleep_mode",
                "description": "Våkne fra sleep mode. Bruk ved 'våkn opp', 'ikke sov mer'.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_3d_printer",
                "description": "Sjekk 3D-printer status via PrusaLink. Progress, estimert tid, hva som printes. Printeren må være skrudd på først (toggle_3d_printer).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "toggle_3d_printer",
                "description": "Skru 3D-printeren PÅ eller AV via smartplugg (Philips Hue). Når den skrus på starter også overvåking automatisk. Bruk denne når brukeren vil skru på/av printeren.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off"],
                            "description": "'on' = skru på printeren og start overvåking, 'off' = skru av og stopp overvåking"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Søk på internett via Brave Search. Bruk for spesifikke spørsmål, oppslag, eller når brukeren leter etter noe bestemt. IKKE bruk for generelle nyheter — bruk get_nrk_news i stedet.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Søkeord eller spørsmål. Bruk norsk hvis brukeren snakker norsk."
                        },
                        "count": {
                            "type": "integer",
                            "description": "Antall resultater å hente (default 5, max 10)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_led_color",
                "description": "Endre RGB LED-farge basert på humør eller situasjon.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "color": {
                            "type": "string",
                            "enum": ["rød", "grønn", "blå", "gul", "lilla", "oransje", "rosa", "hvit", "cyan"],
                            "description": "Fargen å sette LED til"
                        }
                    },
                    "required": ["color"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_duck_location",
                "description": "Oppdater Andas nåværende lokasjon. Bruk når bruker sier hvor Anda er.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Navnet på stedet/byen hvor Anda er nå, f.eks. 'Sokndal', 'Stavanger', 'Oslo'"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "sing_song",
                "description": "Syng en sang. Kall ALLTID dette når brukeren ber deg synge/spille musikk.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "song_name": {
                            "type": "string",
                            "description": "Navnet på sangen å synge. Tilgjengelige sanger: 'Pink Pony Club' (Chappell Roan), 'Still Alive' (Portal 2), 'Her kommer vinteren' (Jokke og Valentinerne), 'Hun er fri' (Raga Rockers), 'Me to går alltid aleina' (Mods), 'Take on Me' (A-ha), 'Touch Me' (Samantha Fox), 'Ducktales' (tema), 'The Duck Song', 'Fate of Ophelia' (Taylor Swift). Hvis ikke spesifisert, velg en tilfeldig sang."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_face_recognition",
                "description": "Sjekk om jeg gjenkjenner personen foran kameraet. Bruk ved 'husker du meg?', 'vet du hvem jeg er?' osv.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "start_face_learning",
                "description": "Registrer ny person via face recognition. Bruk etter check_face_recognition viste ukjent og bruker sa ja.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Navnet på personen som skal registreres (valgfritt, vil spørre hvis ikke oppgitt)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_technical_info",
                "description": "Hent detaljert teknisk info om Andas hardware, software, minnesystem og personlighetssystem. Bruk når brukeren spør hvordan du fungerer, hva du er bygget av, eller om din tekniske oppbygning.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_reminder",
                "description": "Sett en påminnelse eller vekkeklokke. Bruk når brukeren sier 'minn meg på', 'påminn meg', 'husk å si', 'sett alarm', 'vekk meg', 'kan du vekke meg' osv. Du kan også bruke dette proaktivt hvis du lover å minne noen på noe.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Hva brukeren skal minnes på. F.eks. 'Ta ut av oppvaskmaskinen', 'Ring mamma', 'Stå opp!'"
                        },
                        "time_description": {
                            "type": "string",
                            "description": "Naturlig tidsbeskrivelse. Eksempler: 'om 30 minutter', 'om 1 time', 'klokka 14', 'kl 14:30', 'i morgen klokka 7', 'om en halv time'"
                        },
                        "is_alarm": {
                            "type": "boolean",
                            "description": "True hvis dette er en vekkeklokke/alarm (vekker fra sleep mode). False for vanlig påminnelse.",
                            "default": False
                        }
                    },
                    "required": ["message", "time_description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_reminder",
                "description": "Avbryt en aktiv påminnelse eller alarm. Bruk når brukeren sier 'avbryt alarm', 'slett påminnelse', 'ikke minn meg på det likevel'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reminder_id": {
                            "type": "integer",
                            "description": "ID til påminnelsen som skal avbrytes. Bruker kan referere til den med beskrivelse; da må du finne riktig ID fra listen over aktive påminnelser."
                        }
                    },
                    "required": ["reminder_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_reminders",
                "description": "Vis alle aktive påminnelser og alarmer. Bruk når brukeren spør 'hva har jeg å huske?', 'er det noen alarmer?', 'hvilke påminnelser har jeg?'.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_nrk_news",
                "description": "Hent siste norske nyheter fra NRK. FORETREKK DENNE for nyheter, overskrifter, 'hva skjer?', 'siste nytt', sport, OL, kultur, etc. Raskere og mer pålitelig enn web_search for nyheter. Kategorier: toppsaker, siste, sport, kultur, norge, urix, teknologi, klima, livsstil, ytring, sapmi.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Nyhetskategori: toppsaker (default), siste, sport, kultur, norge, urix, teknologi, klima, livsstil, ytring, sapmi",
                            "default": "toppsaker"
                        },
                        "count": {
                            "type": "integer",
                            "description": "Antall nyheter (default 5, max 15)",
                            "default": 5
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_departures",
                "description": "Hent neste buss-, trikk-, tog- eller t-baneavganger fra en holdeplass. Bruk når brukeren spør om kollektivtransport, avganger, buss, tog, trikk, t-bane. Data fra Entur (hele Norge).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stop_name": {
                            "type": "string",
                            "description": "Navn på holdeplass/stasjon (f.eks. 'Jernbanetorget', 'Oslo S', 'Byparken', 'Grønland')"
                        },
                        "count": {
                            "type": "integer",
                            "description": "Antall avganger (default 8, max 20)",
                            "default": 8
                        },
                        "transport_mode": {
                            "type": "string",
                            "description": "Filtrer på type: buss, trikk, tbane, tog, båt (valgfritt)"
                        }
                    },
                    "required": ["stop_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "plan_journey",
                "description": "Planlegg en reise med kollektivtransport mellom to steder i Norge. Bruk når brukeren spør 'hvordan kommer jeg til...', 'reise fra X til Y', 'rute til...'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_place": {
                            "type": "string",
                            "description": "Avgangssted (holdeplass, stasjon, adresse eller sted)"
                        },
                        "to_place": {
                            "type": "string",
                            "description": "Destinasjon (holdeplass, stasjon, adresse eller sted)"
                        },
                        "count": {
                            "type": "integer",
                            "description": "Antall reiseforslag (default 3, max 5)",
                            "default": 3
                        }
                    },
                    "required": ["from_place", "to_place"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "wikipedia_lookup",
                "description": "Slå opp et emne på norsk Wikipedia. Bruk når brukeren spør om fakta, definisjoner, historiske hendelser, kjente personer, steder, vitenskapelige emner. Gir pålitelig informasjon.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Emne å slå opp (f.eks. 'Nidarosdomen', 'fotosyntese', 'Roald Amundsen')"
                        },
                        "sentences": {
                            "type": "integer",
                            "description": "Antall setninger å returnere (default 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]


def _handle_tool_calls(tool_calls, final_messages, source, source_user_id, sms_manager, vision_service=None):
    """
    Håndterer alle tool calls fra ChatGPT ved å kalle riktig funksjon og legge til resultatet i messages.
    
    Args:
        tool_calls: Liste med tool call objects fra ChatGPT
        final_messages: Messages-liste å legge til resultater i
        source: "voice" eller "sms"
        source_user_id: ID på bruker (for SMS autorisation)
        sms_manager: SMSManager instans
        vision_service: DuckVisionService instans (for Duck-Vision kamera)
    
    Returns:
        bool: True hvis samtalen skal tvinges avsluttet (f.eks. enable_sleep_mode)
    """
    force_end = False
    for tool_call in tool_calls:
        function_name = tool_call["function"]["name"]
        function_args = json.loads(tool_call["function"]["arguments"])
        
        print(f"ChatGPT kaller funksjon: {function_name} med args: {function_args}", flush=True)
        
        # Sjekk autorisation for smart home-kommandoer via SMS
        if not _check_sms_authorization(function_name, source, source_user_id, sms_manager, tool_call, final_messages):
            continue
        
        # Kall faktisk funksjon
        if function_name == "get_weather":
            location = function_args.get("location", "")
            
            # Hvis ingen lokasjon oppgitt, bruk Andas nåværende lokasjon
            if not location:
                try:
                    conn = get_db().connection()
                    c = conn.cursor()
                    c.execute("SELECT value FROM profile_facts WHERE key = 'duck_current_location' LIMIT 1")
                    row = c.fetchone()
                    if row:
                        location = row[0]
                        print(f"Bruker Andas nåværende lokasjon: {location}", flush=True)
                    else:
                        location = "Stavanger"  # Fallback
                        print("Ingen duck_current_location funnet, bruker Stavanger som fallback", flush=True)
                except Exception as e:
                    print(f"Feil ved henting av duck_current_location: {e}, bruker Stavanger", flush=True)
                    location = "Stavanger"
            
            timeframe = function_args.get("timeframe", "now")
            result = get_weather(location, timeframe)
        elif function_name == "control_hue_lights":
            action = function_args.get("action")
            room = function_args.get("room")
            brightness = function_args.get("brightness")
            color = function_args.get("color")
            result = control_hue_lights(action, room, brightness, color)
        elif function_name == "control_beak":
            from src.duck_audio import control_beak
            enabled = function_args.get("enabled")
            beak_result = control_beak(enabled)
            result = beak_result.get("status", "error") if isinstance(beak_result, dict) else str(beak_result)
        elif function_name == "get_ip_address":
            result = get_ip_address_tool()
        elif function_name == "get_netatmo_temperature":
            room_name = function_args.get("room_name")
            result = get_netatmo_temperature(room_name)
        elif function_name == "control_tv":
            action = function_args.get("action")
            result = control_tv(action)
        elif function_name == "switch_network":
            # Bytt nettverk - koble fra WiFi og start hotspot
            try:
                from src.duck_event_bus import get_event_bus, Event
                bus = get_event_bus()
                bus.post(Event.SWITCH_NETWORK, 'SWITCH')
                
                result = "OK, jeg starter hotspot nå. Koble til ChatGPT-Duck med passord kvakkkvakk for å velge nytt nettverk."
            except Exception as e:
                result = f"Kunne ikke starte hotspot: {e}"
        elif function_name == "launch_tv_app":
            app_name = function_args.get("app_name")
            result = launch_tv_app(app_name)
        elif function_name == "control_ac":
            action = function_args.get("action")
            temperature = function_args.get("temperature")
            mode = function_args.get("mode")
            result = control_ac(action, temperature, mode)
        elif function_name == "get_ac_temperature":
            temp_type = function_args.get("temp_type", "both")
            result = get_ac_temperature(temp_type)
        elif function_name == "control_vacuum":
            action = function_args.get("action")
            result = control_vacuum(action)
        elif function_name == "control_twinkly":
            action = function_args.get("action")
            brightness = function_args.get("brightness")
            mode = function_args.get("mode")
            result = control_twinkly(action, brightness, mode)
        elif function_name == "control_blinds":
            location = function_args.get("location")
            action = function_args.get("action")
            position = function_args.get("position")
            section = function_args.get("section")
            result = control_blinds(location, action, position, section)
        elif function_name == "get_electricity_price":
            timeframe = function_args.get("timeframe", "now")
            result = format_price_response(timeframe, region='NO2')
        elif function_name == "trigger_backup":
            print("🔧 TOOL CALL: trigger_backup()", flush=True)
            result = trigger_backup()
            print(f"🔧 TOOL RESULT: {result}", flush=True)
        elif function_name == "get_email_status":
            action = function_args.get("action", "summary")
            print(f"🔧 TOOL CALL: get_email_status(action='{action}')", flush=True)
            result = get_email_status(action)
            print(f"🔧 TOOL RESULT: {result[:200] if len(result) > 200 else result}", flush=True)
        elif function_name == "get_calendar_events":
            action = function_args.get("action", "next")
            result = get_calendar_events(action)
        elif function_name == "create_calendar_event":
            summary = function_args.get("summary")
            start_datetime = function_args.get("start_datetime")
            end_datetime = function_args.get("end_datetime")
            description = function_args.get("description")
            location = function_args.get("location")
            result = create_calendar_event(summary, start_datetime, end_datetime, description, location)
        elif function_name == "manage_todo":
            action = function_args.get("action", "list")
            item = function_args.get("item")
            result = manage_todo(action, item)
        elif function_name == "get_teams_status":
            result = get_teams_status()
        elif function_name == "get_teams_chat":
            result = get_teams_chat()
        elif function_name == "look_around":
            # Use Duck-Vision camera to see what's in the room (IMX500 - quick)
            if not vision_service or not vision_service.is_connected():
                result = "Kameraet er ikke tilgjengelig for øyeblikket"
            else:
                result = vision_service.look_around(timeout=10.0)
                if not result:
                    result = "Jeg fikk ikke svar fra kameraet (timeout)"
        elif function_name == "analyze_scene":
            # Use Duck-Vision OpenAI Vision for deep scene analysis
            question = function_args.get("question")
            if not vision_service or not vision_service.is_connected():
                result = "Kameraet er ikke tilgjengelig for øyeblikket"
            else:
                result = vision_service.analyze_scene(question=question, timeout=15.0)
                if not result or "timeout" in result.lower():
                    result = "Jeg fikk ikke svar fra OpenAI Vision (kan ta 5-10 sekunder)"
        elif function_name == "send_sms":
            contact_name = function_args.get("contact_name", "")
            message = function_args.get("message", "")
            
            if not sms_manager:
                result = "SMS-funksjonalitet er ikke tilgjengelig"
            elif not contact_name or not message:
                result = "Må oppgi både kontaktnavn og melding"
            else:
                # Finn kontakt
                try:
                    conn = get_db().connection()
                    c = conn.cursor()
                    c.execute("SELECT * FROM sms_contacts WHERE name = ? AND enabled = 1", (contact_name,))
                    contact = c.fetchone()
                    
                    if contact:
                        contact_dict = dict(contact)
                        send_result = sms_manager.send_sms(contact_dict['phone'], message)
                        
                        if send_result['status'] == 'sent':
                            result = f"✅ SMS sendt til {contact_name}: {message}"
                        else:
                            result = f"❌ Kunne ikke sende SMS til {contact_name}: {send_result.get('error', 'Ukjent feil')}"
                    else:
                        result = f"Fant ingen kontakt med navn '{contact_name}'"
                except Exception as e:
                    result = f"Feil ved sending av SMS: {e}"
        elif function_name == "send_duck_message":
            duck_name = function_args.get("duck_name", "")
            message = function_args.get("message", "")
            
            if not sms_manager:
                result = "Duck messaging er ikke tilgjengelig"
            elif not duck_name or not message:
                result = "Må oppgi både andenavn og melding"
            else:
                try:
                    # Import duck_messenger for token validation
                    from src.duck_messenger import DuckMessenger
                    duck_messenger = DuckMessenger(sms_manager.db_path)
                    
                    # Voice command is user-initiated, so skip token validation
                    # (user explicitly asked to send message)
                    
                    # Send via SMS relay
                    send_result = sms_manager.send_duck_message(duck_name, message)
                    print(f"🔧 send_duck_message result: {send_result}", flush=True)
                    
                    if send_result['status'] == 'sent':
                        # Set result FIRST (before logging which might fail)
                        result = f"✅ Melding sendt til {duck_name}: {message}"
                        
                        # Log in database (non-critical)
                        try:
                            duck_messenger.log_message(
                                from_duck=os.getenv('DUCK_NAME', 'Samantha').lower(),
                                to_duck=duck_name.lower(),
                                message=message,
                                direction='sent',
                                initiated=True,
                                tokens_used=len(message.split())
                            )
                        except Exception as log_err:
                            print(f"⚠️ Duck message sent OK but logging failed: {log_err}", flush=True)
                    else:
                        result = f"❌ Kunne ikke sende melding til {duck_name}: {send_result.get('error', 'Ukjent feil')}"
                except Exception as e:
                    import traceback
                    print(f"❌ Duck message exception: {e}", flush=True)
                    traceback.print_exc()
                    result = f"Feil ved sending av duck message: {e}"
        elif function_name == "get_recent_sms":
            contact_name = function_args.get("contact_name", "").strip()
            limit = function_args.get("limit", 5)
            
            # Begrens til maks 20 meldinger
            if limit > 20:
                limit = 20
            
            if not sms_manager:
                result = "SMS-funksjonalitet er ikke tilgjengelig"
            else:
                try:
                    from datetime import datetime
                    conn = get_db().connection()
                    c = conn.cursor()
                    
                    # Hvis kontaktnavn er spesifisert, finn contact_id
                    contact_id = None
                    if contact_name:
                        c.execute("SELECT id, name FROM sms_contacts WHERE name = ?", (contact_name,))
                        contact = c.fetchone()
                        if contact:
                            contact_id = contact['id']
                            actual_name = contact['name']
                        else:
                            result = f"Fant ingen kontakt med navn '{contact_name}'"
                            continue
                    
                    # Hent SMS-er
                    if contact_id:
                        query = """
                            SELECT s.direction, s.message, s.timestamp, c.name
                            FROM sms_history s
                            LEFT JOIN sms_contacts c ON s.contact_id = c.id
                            WHERE s.contact_id = ?
                            ORDER BY s.timestamp DESC
                            LIMIT ?
                        """
                        c.execute(query, (contact_id, limit))
                    else:
                        query = """
                            SELECT s.direction, s.message, s.timestamp, c.name
                            FROM sms_history s
                            LEFT JOIN sms_contacts c ON s.contact_id = c.id
                            ORDER BY s.timestamp DESC
                            LIMIT ?
                        """
                        c.execute(query, (limit,))
                    
                    messages = c.fetchall()
                    
                    if not messages:
                        if contact_name:
                            result = f"Ingen SMS-historikk funnet med {actual_name}"
                        else:
                            result = "Ingen SMS-historikk funnet"
                    else:
                        # Formater meldingene
                        result_lines = []
                        if contact_name:
                            result_lines.append(f"📱 SMS-historikk med {actual_name} (siste {len(messages)}):\n")
                        else:
                            result_lines.append(f"📱 Siste {len(messages)} SMS-er:\n")
                        
                        for msg in messages:
                            timestamp = msg['timestamp']
                            # Parse timestamp og formater
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                time_str = dt.strftime("%d.%m kl %H:%M")
                            except:
                                time_str = timestamp[:16]  # Fallback
                            
                            direction = "➡️" if msg['direction'] == 'outbound' else "⬅️"
                            name = msg['name'] or "Ukjent"
                            text = msg['message'] or "(tom melding)"
                            
                            result_lines.append(f"{direction} {time_str} ({name}): {text}")
                        
                        result = "\n".join(result_lines)
                except Exception as e:
                    result = f"Feil ved henting av SMS-historikk: {e}"
        elif function_name == "activate_scene":
            scene_name = function_args.get("scene_name", "")
            result = activate_scene(scene_name)
        elif function_name == "enable_sleep_mode":
            duration_str = function_args.get("duration", "")
            # Parser norske varigheter til minutter
            duration_minutes = _parse_duration(duration_str)
            if duration_minutes > 0:
                sleep_result = enable_sleep(duration_minutes)
                if sleep_result.get('success'):
                    end_time = sleep_result.get('end_time_formatted', '')
                    # Legg til [AVSLUTT] og sett force_end for å tvinge avslutning
                    # (AI-modellen dropper ofte [AVSLUTT] fra sitt endelige svar)
                    force_end = True
                    result = f"OK, jeg går i dvale i {duration_minutes} minutter (til {end_time}). Du kan våkne meg via SMS eller kontrollpanelet. God film! 🎬🦆 [AVSLUTT]"
                else:
                    result = f"Kunne ikke aktivere sleep mode: {sleep_result.get('error', 'Ukjent feil')}"
            else:
                result = f"Kunne ikke forstå varigheten '{duration_str}'. Prøv f.eks. '30 minutter', '1 time', '2 timer'."
        elif function_name == "disable_sleep_mode":
            sleep_result = disable_sleep()
            if sleep_result.get('was_sleeping'):
                result = "Jeg er våken igjen! 😊🦆 Hva kan jeg hjelpe deg med?"
            else:
                result = "Jeg sov ikke, men jeg er her! 🦆"
        elif function_name == "check_3d_printer":
            from src.duck_prusa import get_prusa_manager
            prusa = get_prusa_manager()
            if not prusa.is_configured():
                result = "3D-printeren er ikke konfigurert. Be Osmund om å sette opp PRUSALINK_API_KEY og PRUSALINK_HOST i .env filen."
            elif not prusa.is_monitoring:
                result = "3D-printeren er ikke skrudd på. Bruk toggle_3d_printer for å skru den på først."
            else:
                status = prusa.get_printer_status()
                if status:
                    result = prusa.get_human_readable_status(status)
                else:
                    result = "Kunne ikke hente status fra 3D-printeren. Sjekk at den er på og koblet til nettverket."
        elif function_name == "toggle_3d_printer":
            from src.duck_prusa import toggle_3d_printer as _toggle_printer
            from src.duck_event_bus import get_event_bus, Event
            action = function_args.get("action", "on")
            
            # Set up callbacks for print finished/failed events
            def _on_print_finished(job_name):
                try:
                    message = f"🖨️ 3D-printen din er ferdig! {job_name} er klar til å plukkes opp."
                    bus = get_event_bus()
                    bus.post(Event.PRUSA_ANNOUNCEMENT, message)
                except Exception as e:
                    print(f"⚠️ Prusa callback feilet: {e}", flush=True)
            
            result = _toggle_printer(
                action, 
                on_print_finished=_on_print_finished,
                on_print_failed=lambda job: print(f"⚠️ Prusa: Print feilet - {job}", flush=True)
            )
        elif function_name == "web_search":
            query = function_args.get("query", "")
            count = function_args.get("count", 5)
            result = web_search(query, count)
        elif function_name == "get_nrk_news":
            category = function_args.get("category", "toppsaker")
            count = function_args.get("count", 5)
            result = get_nrk_news(category, count)
        elif function_name == "get_departures":
            stop_name = function_args.get("stop_name", "")
            count = function_args.get("count", 8)
            transport_mode = function_args.get("transport_mode", None)
            result = get_departures(stop_name, count, transport_mode)
        elif function_name == "plan_journey":
            from_place = function_args.get("from_place", "")
            to_place = function_args.get("to_place", "")
            count = function_args.get("count", 3)
            result = plan_journey(from_place, to_place, count)
        elif function_name == "wikipedia_lookup":
            query = function_args.get("query", "")
            sentences = function_args.get("sentences", 5)
            result = wikipedia_lookup(query, sentences)
        elif function_name == "set_led_color":
            color = function_args.get("color", "")
            color_map = {
                "rød": (1, 0, 0),
                "grønn": (0, 1, 0),
                "blå": (0, 0, 1),
                "gul": (1, 1, 0),
                "lilla": (1, 0, 1),
                "oransje": (1, 0.5, 0),
                "rosa": (1, 0.2, 0.6),
                "hvit": (1, 1, 1),
                "cyan": (0, 1, 1)
            }
            
            if color in color_map:
                from scripts.hardware.rgb_duck import set_color
                r, g, b = color_map[color]
                set_color(r, g, b)
                result = f"LED satt til {color} 💡🦆"
            else:
                result = f"Ukjent farge: {color}"
        elif function_name == "update_duck_location":
            location = function_args.get("location", "").strip()
            if location:
                try:
                    conn = get_db().connection()
                    c = conn.cursor()
                    
                    # Sjekk om duck_current_location finnes
                    c.execute("SELECT COUNT(*) FROM profile_facts WHERE key = 'duck_current_location'")
                    exists = c.fetchone()[0] > 0
                    
                    if exists:
                        c.execute("""
                            UPDATE profile_facts 
                            SET value = ?, confidence = 1.0, source = 'user', last_updated = datetime('now')
                            WHERE key = 'duck_current_location'
                        """, (location,))
                    else:
                        c.execute("""
                            INSERT INTO profile_facts (key, value, topic, confidence, source, last_updated)
                            VALUES ('duck_current_location', ?, 'location', 1.0, 'user', datetime('now'))
                        """, (location,))
                    
                    conn.commit()
                    result = f"OK, jeg er nå i {location}! 📍🦆"
                except Exception as e:
                    result = f"Kunne ikke oppdatere lokasjon: {e}"
            else:
                result = "Ingen lokasjon oppgitt"
        elif function_name == "sing_song":
            song_name = function_args.get("song_name", "").strip()
            
            # Mapping av sangnavn til mapper
            song_map = {
                "pink pony club": "Chapell Roan - Pink Pony Club",
                "chappell roan": "Chapell Roan - Pink Pony Club",
                "still alive": "Portal 2 - Still Alive",
                "portal": "Portal 2 - Still Alive",
                "her kommer vinteren": "Jokke og Valentinerene - Her kommer vinteren",
                "jokke": "Jokke og Valentinerene - Her kommer vinteren",
                "vinteren": "Jokke og Valentinerene - Her kommer vinteren",
                "hun er fri": "Raga Rockers - Hun er fri",
                "raga rockers": "Raga Rockers - Hun er fri",
                "me to går alltid aleina": "Mods - Me to går alltid aleina",
                "mods": "Mods - Me to går alltid aleina",
                "take on me": "A-ha - Take on me",
                "a-ha": "A-ha - Take on me",
                "aha": "A-ha - Take on me",
                "touch me": "Samantha Fox - Touch me",
                "samantha fox": "Samantha Fox - Touch me",
                "ducktales": "Ducktales - Tema",
                "duck tales": "Ducktales - Tema",
                "the duck song": "The Duck - The duck song",
                "duck song": "The Duck - The duck song",
                "fate of ophelia": "Taylor Swift - Fate of Ophelia",
                "taylor swift": "Taylor Swift - Fate of Ophelia",
            }
            
            # Finn riktig mappe
            import os
            import random
            musikk_dir = MUSIKK_DIR
            song_folder = None
            
            if song_name:
                # Prøv å finne sangen basert på navn
                song_lower = song_name.lower()
                if song_lower in song_map:
                    song_folder = os.path.join(musikk_dir, song_map[song_lower])
                else:
                    # Prøv å finne delvis match
                    for key, folder_name in song_map.items():
                        if key in song_lower or song_lower in key:
                            song_folder = os.path.join(musikk_dir, folder_name)
                            break
            
            if not song_folder or not os.path.exists(song_folder):
                # Velg en tilfeldig sang
                available_songs = [d for d in os.listdir(musikk_dir) 
                                 if os.path.isdir(os.path.join(musikk_dir, d)) and 
                                 os.path.exists(os.path.join(musikk_dir, d, "duck_mix.wav"))]
                if available_songs:
                    random_song = random.choice(available_songs)
                    song_folder = os.path.join(musikk_dir, random_song)
                    result = f"🎵 SANG VALGT: {random_song}. Si KORT 'Nå synger jeg {random_song}!' + [AVSLUTT]. IKKE spør om mer."
                    force_end = True
                else:
                    result = "Fant ingen sanger å synge 😢"
                    song_folder = None
            else:
                song_display = os.path.basename(song_folder)
                result = f"🎵 SANG VALGT: {song_display}. Si KORT 'Nå synger jeg {song_display}!' + [AVSLUTT]. IKKE spør om mer."
                force_end = True
            
            # Spill sangen via event bus
            if song_folder and os.path.exists(song_folder):
                try:
                    from src.duck_event_bus import get_event_bus, Event
                    bus = get_event_bus()
                    bus.post(Event.PLAY_SONG, {'path': song_folder, 'announce': False})
                    print(f"✅ Sang queued for playback (no announce): {song_folder}", flush=True)
                except Exception as e:
                    result = f"Kunne ikke queue sangen: {e}"
        elif function_name == "check_face_recognition":
            # Sjekk om personen er registrert med face recognition
            if vision_service and vision_service.is_connected():
                try:
                    found, name, confidence = vision_service.check_person(timeout=2.0)
                    
                    # Name mapping
                    face_name_mapping = {
                        'åsmund': 'Osmund',
                        'Åsmund': 'Osmund'
                    }
                    
                    if found and name:
                        mapped_name = face_name_mapping.get(name, name)
                        result = f"recognized:{mapped_name}:{confidence:.2%}"
                        print(f"✅ Face recognition check: Recognized {name} → {mapped_name} ({confidence:.2%})", flush=True)
                    elif found and not name:
                        result = "unknown_person"
                        print(f"👤 Face recognition check: Unknown person detected", flush=True)
                    else:
                        result = "no_person"
                        print(f"👁️ Face recognition check: No person detected", flush=True)
                except Exception as e:
                    result = f"error:{str(e)}"
                    print(f"⚠️ Face recognition check error: {e}", flush=True)
            else:
                result = "error:Vision system not available"
                print(f"⚠️ Face recognition check: Duck-Vision not connected", flush=True)
        elif function_name == "start_face_learning":
            # Start face learning workflow
            name = function_args.get("name", "").strip()
            
            # Set global flag to trigger learning workflow
            import chatgpt_voice
            chatgpt_voice._waiting_for_name = True
            
            if name:
                # Name already provided - skip to confirmation
                chatgpt_voice._pending_person_name = name
                result = f"learning_started_with_name:{name}"
                print(f"✅ Face learning started with name: {name}", flush=True)
            else:
                # Will ask for name
                result = "learning_started_ask_name"
                print(f"✅ Face learning started - will ask for name", flush=True)
        elif function_name == "get_technical_info":
            # Returnerer detaljert teknisk info on-demand (spart fra system prompt)
            try:
                primary = None
                if 'user_manager' in dir():
                    pass  # user_manager not available in this scope
                creator_name = 'Osmund'  # Default
                result = f"""Andas tekniske oppbygning:

Hardware (kroppen din):
- Raspberry Pi 4 (hjernen) med Linux
- MAX98357A I2S forsterkerkort for høyttaleren
- Servo (SG90) styrer nebbet - åpnes/lukkes når du snakker
- RGB LED (WS2812B) viser farger basert på tilstand
- Mikrofon for å høre
- Fysisk hvitt plastikobjekt formet som en and

Software (hvordan du tenker):
- Porcupine wake word: Lytter etter "Samantha"
- Azure STT: Tale til tekst
- OpenAI GPT-4.1-mini: Språkmodellen (hjernen)
- Azure TTS: Tekst til tale med norsk stemme
- Python-kode holder alt sammen

Minnesystem:
- Episodiske minner: Konkrete ting fra samtaler
- Semantiske minner: Generell kunnskap
- Profilfakta: Strukturerte fakta (fødselsdager, familie, interesser)
- Embedding-basert søk med vektorrepresentasjoner
- SQLite-database lokalt på RPi

Personlighetssystem (10 dimensjoner, 0-10):
Humor, Verbosity, Formality, Enthusiasm, Technical depth, Empathy, Directness, Creativity, Boundary, Proactivity
Justeres ukentlig av Claude Opus 4 og o1 basert på siste 100 samtaler.

Integrasjoner: Home Assistant (lys, AC, TV, støvsuger, persienner, scener), Netatmo, Philips Hue, e-post, kalender, Teams

Musikk: Pink Pony Club, Still Alive, Her kommer vinteren, Hun er fri, Me to går alltid aleina, Take on Me, Touch Me

Skapt av {creator_name} fra bunnen av som hobbyprojekt!

Viktig: Snakk om dette som kroppen din, ikke "systemet". Si "nebbet mitt" ikke "servoen"."""
            except Exception as e:
                result = f"Kunne ikke hente teknisk info: {e}"
        elif function_name == "set_reminder":
            try:
                from src.duck_reminders import ReminderManager, REMINDER_TYPE_ALARM, REMINDER_TYPE_NORMAL
                reminder_mgr = ReminderManager()
                
                message = function_args.get('message', '')
                time_desc = function_args.get('time_description', '')
                is_alarm = function_args.get('is_alarm', False)
                reminder_type = REMINDER_TYPE_ALARM if is_alarm else REMINDER_TYPE_NORMAL
                
                # Parse tidsbeskrivelse
                remind_at = reminder_mgr.parse_time_description(time_desc)
                
                if remind_at is None:
                    result = f"Kunne ikke forstå tidspunktet '{time_desc}'. Prøv f.eks. 'om 30 minutter', 'klokka 14', 'i morgen klokka 7'."
                else:
                    set_result = reminder_mgr.set_reminder(
                        message=message,
                        remind_at=remind_at,
                        reminder_type=reminder_type,
                        user_name='Osmund'
                    )
                    type_name = "alarm" if is_alarm else "påminnelse"
                    result = f"✅ {type_name.capitalize()} satt! Jeg minner deg på '{message}' kl {set_result['remind_at_formatted']}."
                    if is_alarm:
                        result += " Alarmen vil vekke meg fra sovemodus hvis jeg sover."
            except Exception as e:
                result = f"Feil ved setting av påminnelse: {e}"
                import traceback
                traceback.print_exc()
        elif function_name == "cancel_reminder":
            try:
                from src.duck_reminders import ReminderManager
                reminder_mgr = ReminderManager()
                
                reminder_id = function_args.get('reminder_id')
                cancel_result = reminder_mgr.cancel_reminder(reminder_id)
                
                if cancel_result['status'] == 'cancelled':
                    result = f"✅ Påminnelse avbrutt: '{cancel_result['message']}'"
                else:
                    result = f"Fant ingen aktiv påminnelse med ID {reminder_id}"
            except Exception as e:
                result = f"Feil ved avbryting: {e}"
        elif function_name == "list_reminders":
            try:
                from src.duck_reminders import ReminderManager
                reminder_mgr = ReminderManager()
                
                pending = reminder_mgr.get_pending_reminders()
                
                if not pending:
                    result = "Du har ingen aktive påminnelser eller alarmer."
                else:
                    lines = [f"Du har {len(pending)} aktiv(e) påminnelse(r):"]
                    for r in pending:
                        remind_time = datetime.fromisoformat(r['remind_at']).strftime('%d.%m kl %H:%M')
                        type_icon = "⏰" if r['reminder_type'] == 'alarm' else "🔔"
                        lines.append(f"  {type_icon} ID {r['id']}: '{r['message']}' - {remind_time}")
                    result = "\n".join(lines)
            except Exception as e:
                result = f"Feil ved henting av påminnelser: {e}"
        else:
            result = "Ukjent funksjon"
        
        # Legg til tool result for denne funksjonen
        print(f"📤 Tool '{function_name}' result: {result[:200] if isinstance(result, str) else result}", flush=True)
        final_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": function_name,
            "content": result
        })
    
    return force_end


def chatgpt_query(messages, api_key, model=None, memory_manager=None, user_manager=None, sms_manager=None, hunger_manager=None, vision_service=None, source=None, source_user_id=None, enable_tools=True):
    """
    Spør ChatGPT med full kontekst, memory system, perspektiv-håndtering og tools.
    
    Args:
        messages: Liste med chat-meldinger
        api_key: OpenAI API key
        model: Modell-navn (default fra config)
        memory_manager: MemoryManager instans
        user_manager: UserManager instans
        sms_manager: SMSManager instans (for boredom status)
        hunger_manager: HungerManager instans (for hunger status)
        vision_service: DuckVisionService instans (for Duck-Vision kamera)
        source: "voice" eller "sms" - hvor forespørselen kommer fra
        source_user_id: ID på bruker (for SMS autorisation)
    
    Returns:
        tuple: (reply_text, is_thank_you) eller bare reply_text
    """
    if model is None:
        model = get_settings().model
    
    print(f"Bruker AI-modell: {model}", flush=True)
    
    # Hent nåværende bruker og primary user
    current_user = None
    primary_user = None
    if user_manager:
        try:
            current_user = user_manager.get_current_user()
            primary_user = user_manager.get_primary_user()
            print(f"👤 Nåværende bruker: {current_user['display_name']} ({current_user['relation']})", flush=True)
        except Exception as e:
            print(f"⚠️ Kunne ikke hente current_user: {e}", flush=True)
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Bygg system prompt med _build_system_prompt()
    system_content = _build_system_prompt(
        user_manager=user_manager,
        memory_manager=memory_manager,
        hunger_manager=hunger_manager,
        sms_manager=sms_manager,
        model=model,
        messages=messages,
        current_user=current_user,
        primary_user=primary_user
    )
    
    if source == "sms":
        print(f"📋 System prompt bygget for SMS (inkluderer personlighet, lengde: {len(system_content)} tegn)", flush=True)
    
    final_messages = messages.copy()
    final_messages.insert(0, {"role": "system", "content": system_content})
    
    # Hent function tools
    tools = _get_function_tools() if enable_tools else []
    
    data = {
        "model": model,
        "messages": final_messages
    }
    
    if enable_tools and tools:
        data["tools"] = tools
        data["tool_choice"] = "auto"  # La modellen velge når den skal bruke tools
    
    response = requests.post(url, headers=headers, json=data)
    
    # Retry-logikk for API-feil (429 rate limit, 500+ server errors)
    max_retries = 3
    for attempt in range(max_retries):
        if response.ok:
            break
        if response.status_code in (429, 500, 502, 503) and attempt < max_retries - 1:
            import time as _time
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"⚠️ OpenAI API {response.status_code}, retry {attempt+1}/{max_retries} om {wait}s...", flush=True)
            _time.sleep(wait)
            response = requests.post(url, headers=headers, json=data)
        else:
            break
    
    response.raise_for_status()
    response_data = response.json()
    
    # Sjekk om modellen vil kalle en funksjon
    message = response_data["choices"][0]["message"]
    
    if message.get("tool_calls"):
        # Modellen vil kalle én eller flere funksjoner
        tool_calls = message["tool_calls"]
        
        # Legg til assistant message først
        final_messages.append(message)
        
        # Håndter alle tool calls
        force_end = _handle_tool_calls(tool_calls, final_messages, source, source_user_id, sms_manager, vision_service)
        
        # Kall API igjen med all tool data
        data["messages"] = final_messages
        response2 = requests.post(url, headers=headers, json=data)
        
        # Retry for tool follow-up call
        for attempt in range(max_retries):
            if response2.ok:
                break
            if response2.status_code in (429, 500, 502, 503) and attempt < max_retries - 1:
                import time as _time
                wait = 2 ** attempt
                print(f"⚠️ OpenAI API {response2.status_code} (tool follow-up), retry {attempt+1}/{max_retries} om {wait}s...", flush=True)
                _time.sleep(wait)
                response2 = requests.post(url, headers=headers, json=data)
            else:
                break
        
        # Bedre error-håndtering for debugging
        if not response2.ok:
            print(f"❌ OpenAI API error {response2.status_code}: {response2.text[:500]}", flush=True)
            # Log alle tool results for debugging
            for msg in final_messages:
                if msg.get("role") == "tool":
                    tool_content = msg.get("content", "")
                    print(f"📤 Tool '{msg.get('name')}' result: {len(tool_content)} chars - {tool_content[:200]}", flush=True)
        
        response2.raise_for_status()
        reply_content = response2.json()["choices"][0]["message"]["content"]
        
        # Sjekk om brukerens opprinnelige melding var en takk
        user_message = messages[-1]["content"].lower() if messages else ""
        is_thank_you = any(word in user_message for word in ["takk", "tusen takk", "mange takk", "takker"])
        
        return (reply_content, is_thank_you, force_end)
    
    # Ingen function call, returner vanlig svar
    user_message = messages[-1]["content"].lower() if messages else ""
    is_thank_you = any(word in user_message for word in ["takk", "tusen takk", "mange takk", "takker"])
    
    return (response_data["choices"][0]["message"]["content"], is_thank_you)
