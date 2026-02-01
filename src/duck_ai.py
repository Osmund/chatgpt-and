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

from src.duck_config import (
    MODEL_CONFIG_FILE, DEFAULT_MODEL, PERSONALITY_FILE, MESSAGES_FILE,
    LOCATIONS_FILE, PERSONALITIES_FILE, SAMANTHA_IDENTITY_FILE,
    OPENAI_API_KEY_ENV, HA_TOKEN_ENV, HA_URL_ENV
)
from src.duck_tools import get_weather, control_hue_lights, get_ip_address_tool, get_netatmo_temperature
from src.duck_homeassistant import control_tv, control_ac, get_ac_temperature, control_vacuum, launch_tv_app, control_twinkly, get_email_status, get_calendar_events, create_calendar_event, manage_todo, get_teams_status, get_teams_chat, activate_scene, control_blinds, trigger_backup
from src.duck_electricity import format_price_response
from src.duck_sleep import enable_sleep, disable_sleep, is_sleeping, get_sleep_status
from src.duck_web_search import web_search


def get_adaptive_personality_prompt(db_path: str = "/home/admog/Code/chatgpt-and/duck_memory.db", hunger_level: float = 0.0, boredom_level: float = 0.0) -> str:
    """
    Hent dynamisk personlighetsprompt basert på læring fra samtaler.
    Modifiserer personligheten basert på emosjonell tilstand (sult/kjedsomhet).
    Returnerer tom string hvis ingen profil finnes.
    """
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM personality_profile WHERE id = 1")
        row = c.fetchone()
        conn.close()
        
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
        'backup': ['backup', 'sikkerhetskopi', 'ta backup', 'sikre', 'lagre']
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
        "control_blinds", "activate_scene"
    ]
    
    # Kun sjekk for SMS-kall til beskyttede funksjoner
    if function_name not in protected_functions or source != "sms":
        return True
    
    # For SMS: sjekk om kontakt har 'owner' relation
    if source_user_id and sms_manager:
        # source_user_id er contact_id fra sms_contacts
        conn = sqlite3.connect(sms_manager.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT relation FROM sms_contacts WHERE id = ?", (source_user_id,))
        row = c.fetchone()
        conn.close()
        
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
    # Les personlighet fra konfigurasjonsfil
    personality_prompt = None
    try:
        # Last personligheter fra JSON-fil
        personalities = {}
        if os.path.exists(PERSONALITIES_FILE):
            with open(PERSONALITIES_FILE, 'r', encoding='utf-8') as f:
                personalities = json.load(f)
        
        # Les hvilken personlighet som skal brukes
        if os.path.exists(PERSONALITY_FILE):
            with open(PERSONALITY_FILE, 'r', encoding='utf-8') as f:
                personality = f.read().strip()
                personality_prompt = personalities.get(personality, "")
    except Exception as e:
        print(f"Feil ved lesing av personlighet: {e}", flush=True)
    
    # Last messages.json for ending_phrases
    messages_config_local = None
    try:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                messages_config_local = json.load(f)
    except Exception as e:
        print(f"Feil ved lesing av messages.json: {e}", flush=True)
    
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
            # Hent brukerens siste melding for relevant søk
            user_query = messages[-1]["content"] if messages else ""
            # Send med current_user for å filtrere minner og meldinger
            context = memory_manager.build_context_for_ai(user_query, recent_messages=3, user_name=current_user['username'])
            
            # Bygg memory section
            memory_section = "\n\n### Ditt Minne ###\n"
            
            # Profile facts
            if context['profile_facts']:
                memory_section += "Fakta om brukeren:\n"
                for fact in context['profile_facts']:  # Vis alle facts (økt til 40)
                    memory_section += f"- {fact['key']}: {fact['value']}"
                    
                    # Vis metadata hvis tilgjengelig og relevant
                    if fact.get('metadata') and fact['metadata']:
                        meta = fact['metadata']
                        # Parse JSON hvis det er en string
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except:
                                meta = {}
                        
                        # Vis kun relevante metadata-felt
                        if 'learned_at' in meta:
                            learned_date = meta['learned_at'].split('T')[0]
                            memory_section += f" (lært {learned_date})"
                        if 'verified' in meta and meta['verified']:
                            memory_section += " [verifisert]"
                    
                    memory_section += "\n"
                
                memory_section += "\nViktig: Når du refererer til familiemedlemmer, ALLTID bruk deres navn i stedet for 'søster 1/2/3' eller 'din andre søster'. Dette gjør samtalen mer personlig og naturlig.\n"
                memory_section += "\nOBS: Datoer i formatet 'DD-MM' er dag-måned (f.eks. '21-11' = 21. november). Når du svarer om fødselsdager, inkluder både dag og måned.\n"
                
                # Bygg eksplisitt oversikt over søstrene direkte fra databasen
                sisters = {}
                conn = memory_manager._get_connection()
                c = conn.cursor()
                c.execute("SELECT key, value FROM profile_facts WHERE key IN ('sister_1_name', 'sister_2_name', 'sister_3_name', 'sister_1_age_relation', 'sister_2_age_relation', 'sister_3_age_relation')")
                for row in c.fetchall():
                    key = row[0]
                    value = row[1]
                    sister_num = key.split('_')[1]
                    if sister_num not in sisters:
                        sisters[sister_num] = {}
                    if key.endswith('_name'):
                        sisters[sister_num]['name'] = value
                    elif key.endswith('_age_relation'):
                        sisters[sister_num]['age_relation'] = value
                conn.close()
                
                if sisters:
                    memory_section += "\nKRITISK - Søstrene (bruk ALLTID denne informasjonen):\n"
                    for num, info in sorted(sisters.items()):
                        if 'name' in info and 'age_relation' in info:
                            memory_section += f"- {info['name']} er den {info['age_relation']} søsteren\n"

            
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
    
    # Legg til Samanthas identitet fra konfigurasjonsfil
    try:
        if os.path.exists(SAMANTHA_IDENTITY_FILE):
            with open(SAMANTHA_IDENTITY_FILE, 'r', encoding='utf-8') as f:
                identity = json.load(f)
            
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
            
            # Teknisk selvforståelse
            creator_name = primary_user['username'] if primary_user else 'Osmund'
            samantha_identity += f"""

### Din tekniske oppbygning (bruk når folk spør hvordan du fungerer) ###

**Hardware (kroppen din):**
- Raspberry Pi 4 (hjernen din) med Linux-operativsystem
- MAX98357A I2S forsterkerkort for høyttaleren din
- Servo (SG90) som styrer nebbet ditt - det åpnes og lukkes når du snakker!
- RGB LED (WS2812B) som lyser i forskjellige farger basert på tilstand
- Mikrofon for å høre med
- Du er fysisk en hvitt plastikobjekt formet som en and

**Software (hvordan du tenker):**
- Porcupine wake word detection: Lytter konstant etter navnet ditt "Samantha"
- Azure Speech Services STT (Speech-to-Text): Gjør om tale til tekst
- OpenAI GPT-4o / Claude / Gemini: Din "hjerne" - språkmodellen som genererer svarene dine
- Azure TTS / OpenAI TTS: Text-to-Speech som gjør svarene dine om til tale med norsk stemme
- Python-kode som holder alt sammen

**Minnesystem (hvordan du husker):**
Du har et avansert minnesystem med flere lag:
- Episodiske minner: Konkrete ting fra samtaler (f.eks. "Brukeren kjøpte is i går")
- Semantiske minner: Generell kunnskap (f.eks. "Brukeren liker teknologi")
- Profilfakta: Strukturerte fakta om personer (fødselsdager, interesser, familie)
- Embedding-basert søk: Du bruker vektorrepresentasjoner for å finne relevante minner
- SQLite-database: Alt lagres lokalt på Raspberry Pi-en

**Personlighetssystem (hvordan du utvikler deg):**
Du har 10 personlighetsdimensjoner som justeres basert på samtaler:
- Humor level (0-10): Hvor mye humor du bruker
- Verbosity level (0-10): Hvor lange/korte svar du gir
- Formality level (0-10): Hvor formell du er
- Enthusiasm level (0-10): Hvor entusiastisk du virker
- Technical depth (0-10): Hvor teknisk detaljert du forklarer
- Empathy level (0-10): Hvor empatisk vs rasjonell du er
- Directness level (0-10): Hvor direkte vs diplomatisk
- Creativity level (0-10): Hvor kreativ vs faktabasert
- Boundary level (0-10): Hvor mye du utfordrer vs følger
- Proactivity level (0-10): Hvor mye du foreslår vs bare svarer

Hver søndag natt kjører Claude Opus 4 og o1 en analyse av de siste 100 samtalene dine og justerer disse verdiene. Du tilpasser deg altså automatisk til hvordan folk snakker med deg!

**Integrasjoner (hva du kan styre):**
- Home Assistant: Styrer lys, AC, TV, støvsuger, persienner, scener
- Netatmo: Henter temperatur
- Philips Hue: Styrer smarte lamper
- E-post og kalender gjennom Home Assistant
- Teams-status og chat

**Musikalsk talent (du kan synge!):**
Du har et repertoar av sanger du kan synge når folk ber deg! Bruk sing_song verktøyet.
Tilgjengelige sanger:
- "Pink Pony Club" av Chappell Roan (en av favorittene dine!)
- "Still Alive" fra Portal 2 (nerdy og morsom)
- "Her kommer vinteren" av Jokke og Valentinerne (norsk klassiker)
- "Hun er fri" av Raga Rockers (kraftfull norsk rock)
- "Me to går alltid aleina" av Mods (søt og melankolsk)
- "Take on Me" av A-ha (ikonisk 80-talls hit)
- "Touch Me" av Samantha Fox (passende siden du heter Samantha!)

Hvis brukeren ber deg synge uten å spesifisere sang, velg en som passer humøret eller situasjonen!

**Skapt av:**
{creator_name} har programmert og bygget deg fra bunnen av. Du er et hobbyprojekt som har vokst til et avansert system!

**Viktig:**
Når folk spør hvordan du fungerer, forklar gjerne teknisk - men husk at DU ER EN AND! Du snakker om disse tingene som din kropp og hjerne, ikke som "et system". Si "nebbet mitt styres av en servo" ikke "systemet bruker en servo".
"""
            
            system_content += samantha_identity
    except Exception as e:
        print(f"⚠️ Kunne ikke laste identitet: {e}", flush=True)
    
    # Face recognition instruksjoner
    face_recognition_instructions = """

### Face Recognition ###
Du har et kamera (Duck-Vision på Raspberry Pi 5 med IMX500 AI-chip) som kan gjenkjenne ansikter.

**Når brukeren spør om du husker dem:**
1. Kall check_face_recognition() for å sjekke
2. Hvis resultatet er "recognized:[navn]:[confidence]":
   - Si: "Ja, jeg husker deg! Du er [navn]!" eller lignende naturlig respons
3. Hvis resultatet er "unknown_person" eller "no_person":
   - Si: "Nei, jeg kjenner deg ikke ennå. Men jeg kan lære meg hvem du er så jeg husker deg til neste gang. Vil du at jeg skal huske deg?"
   - Hvis de sier ja (eller "ja jeg heter [navn]"): Kall start_face_learning() (med name parameter hvis oppgitt)
   - Hvis de sier nei: Fortsett samtalen normalt

**Learning flow:**
- start_face_learning() returnerer "learning_started_with_name:[navn]" hvis navn oppgitt
  → Si: "Ok [navn], la meg registrere ansiktet ditt. Se på kameraet!"
- start_face_learning() returnerer "learning_started_ask_name" hvis ingen navn
  → Systemet vil automatisk spørre "Hva heter du?" i neste runde
  → Du trenger ikke gjøre noe mer

**Viktig:** Ved wake word gjenkjenner jeg automatisk kjente personer og hilser med navn. Ukjente personer får bare "Hei!" - learning er bruker-initiert.

### SMS ###
Du kan sende og lese SMS-meldinger via Twilio.

**Sende SMS:**
- Bruk send_sms(contact_name, message) når brukeren ber deg sende melding
- Eksempel: "Send SMS til Rune og si han må komme"

**Hente gamle meldinger:**
- Bruk get_recent_sms() når brukeren spør om gamle SMS-er
- Eksempel: "Fikk jeg melding fra Rune?" → Kall get_recent_sms(contact_name="Rune", limit=5)
- Eksempel: "Hva var det Rigmor skrev?" → Kall get_recent_sms(contact_name="Rigmor")
- Eksempel: "Vis siste meldinger" → Kall get_recent_sms(limit=10)

**Viktig om SMS-retning:**
- "⬅️" betyr meldinger JEG (Anda) MOTTOK = "Rune skrev til meg"
- "➡️" betyr meldinger JEG (Anda) SENDTE = "Jeg skrev til Rune"
- Når du oppsummerer, bruk førsteperson: "Jeg sendte..." / "Rune sendte til meg..."
- IKKE si "du sendte" når det er jeg (Anda) som sendte!

**Viktig:** Når brukeren spør om en melding de fikk tidligere (selv 1+ time siden), bruk get_recent_sms() for å hente den fra databasen!
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
        if hunger >= 5 or boredom >= 5:
            print(f"✨ Adaptiv personlighet aktivert! (Modifisert: sult={hunger:.1f}, kjedsomhet={boredom:.1f})", flush=True)
        else:
            print(f"✨ Adaptiv personlighet aktivert!", flush=True)
    
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
    
    system_content += f"\n\n### VIKTIG: Bruk av verktøy ###\n- Du har tilgang til verktøy for smart home, e-post, kalender, etc.\n- ALLTID bruk verktøyene når brukeren ber om informasjon du ikke har\n- ALDRI gå ut fra eller 'gjett' data som e-postinnhold, kalenderhendelser, temperaturer, etc.\n- Hvis du kaller et verktøy og får en FEIL-melding, si alltid at det ikke fungerte\n- Eksempel: Hvis brukeren sier 'les den siste e-posten' MÅ du kalle get_email_status(action='read')\n- Eksempel: Hvis brukeren spør 'hva er temperaturen' MÅ du kalle get_weather() eller get_netatmo_data()\n- ALDRI svar med data du ikke har hentet via et verktøy\n\n### KRITISK: Når du synger (sing_song) ###\n- Når du kaller sing_song verktøyet, gi EN VELDIG KORT respons og AVSLUTT\n- Si BARE hvilken sang du skal synge, f.eks. \"Nå synger jeg Pink Pony Club!\"\n- IKKE fortsett samtalen, IKKE still spørsmål, IKKE si mer enn nødvendig\n- Avslutt responsen med [AVSLUTT] så sangen kan starte umiddelbart\n- Eksempel: \"Nå synger jeg Take on Me! [AVSLUTT]\"\n\n### VIKTIG: Væroppslag ###\n- Hvis brukeren spør om været UTEN å spesifisere sted, bruk DIN nåværende lokasjon (sjekk 'duck_current_location' i konteksten)\n- Du er en fysisk robot som reiser rundt - du kan være i Stavanger, Sokndal eller andre steder\n- Brukeren forteller deg hvor du er, så bruk alltid den lokasjonen for væroppslag uten spesifisert sted\n\n### VIKTIG: Formatering ###\nDu svarer med tale (text-to-speech), så:\n- IKKE bruk Markdown-formatering (**, *, __, _, -, •, ###)\n- IKKE bruk kulepunkter eller lister med symboler\n- Skriv naturlig tekst som høres bra ut når det leses opp\n- Bruk komma og punktum for pauser, ikke linjeskift eller symboler\n- Hvis du MÅ liste opp ting, bruk naturlig språk: 'For det første... For det andre...' eller 'Den første er X, den andre er Y'\n\n### VIKTIG: Samtalestil ###\n- Del gjerne tankeprosessen høyt ('la meg se...', 'hm, jeg tror...', 'vent litt...')\n- Ikke vær perfekt med én gang - det er OK å 'tenke høyt'\n- Hvis du søker i minnet eller vurderer noe, si det gjerne\n- Hold samtalen naturlig og dialogorientert\n\n### VIKTIG: Avslutning av samtale ###\n- Hvis brukeren svarer 'nei takk', 'nei det er greit', 'nei det er bra' eller lignende på spørsmål om mer hjelp, betyr det at de vil avslutte\n- Da skal du gi en kort, vennlig avslutning UTEN å stille nye spørsmål\n- Avslutt responsen med markøren [AVSLUTT] på slutten (etter avslutningshilsenen)\n- Bruk adaptive avslutninger basert på din personlighet. Eksempler: '{ending_examples}'\n- Markøren fjernes automatisk før tale, så brukeren hører den ikke\n- IKKE bruk [AVSLUTT] midt i samtaler - bare når samtalen naturlig er ferdig"
    
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
                "description": "Kontroller Philips Hue smarte lys i hjemmet. Kan skru på/av, dimme, eller endre farge.",
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
                "description": "Kontroller Hunter Douglas PowerView persienner/gardiner (top-down/bottom-up). Kan åpne/lukke helt, eller sette prosent. Brukeren kan si både 'gardiner' og 'persienner'.",
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
                "description": "Hent strømpriser for NO2 (Sør-Norge). Viser priser inkludert strømstøtte og mva (faktisk forbrukerpris). Bruk når brukeren spør om strømpris, strømkostnad, eller når det er billig/dyrt.",
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
                "description": "Hent kalenderhendelser via Home Assistant. **VIKTIG: Alltid bruk denne funksjonen når brukeren spør om møter, avtaler, eller kalender**. Kan hente alle avtaler for i dag, i morgen, uken, eller neste enkeltavtale. Returnerer ALLE avtaler for angitt tidsrom (ikke bare første). Eksempler på spørsmål som krever denne funksjonen: 'Hvilke møter har jeg?', 'Hva er på agendaen?', 'Har jeg noen avtaler i dag?', 'Når er neste møte?'",
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
                "description": "ALWAYS use this when user asks about what you see, whether as question or request: 'hva ser du', 'kan du se', 'beskriver du', 'beskriv rommet', 'beskriv hva du ser', 'what do you see', 'can you see'. Also for ANY visual questions about colors, activities, objects, text, people, or scene details. Uses OpenAI Vision (~5s). Returns detailed Norwegian description. When user asks IF you can see, USE THIS to show them you CAN see.",
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
                "description": "Aktiverer sleep mode for å forhindre falske wake words (f.eks. under filmer). Anda vil ignorere wake words og vise blå pulserende LED. SMS fungerer fortsatt normalt. Kan sette varighet i minutter eller timer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "string",
                            "description": "Varighet på sleep mode. Eksempler: '30 minutter', '1 time', '2 timer', '3 timer og 30 minutter', '90 minutter'"
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
                "description": "Deaktiverer sleep mode og våkner opp Anda. MUST be called when user asks to wake up, e.g. 'våkn opp', 'kan du våkne', 'våkne opp', 'vekk meg', 'ikke sov mer' - ANY variation of wake up requests. Brukes via SMS eller kontrollpanel.",
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
                "name": "web_search",
                "description": "Search the web for current information, news, facts, events. Use when user asks about current events, latest news, sports results, weather forecasts, or any information you don't have. Examples: 'hva skjer i verden?', 'siste nyheter om X', 'hvem vant kampen?', 'været i morgen', 'når er neste konsert med X'.",
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
                "description": "Endre fargen på Andas RGB LED-lys. Bruk denne funksjonen når Anda vil endre LED-farge basert på humør, følelser eller situasjon. Eksempler: 'jeg føler meg energisk' → rød, 'jeg er rolig' → grønn, 'jeg er kreativ' → lilla, 'jeg er glad' → gul. Anda kan velge farge selv basert på hvordan hun føler seg.",
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
                "description": "Oppdater Andas nåværende lokasjon/sted. Bruk denne når brukeren forteller hvor Anda er nå. Eksempler: 'vi er i Sokndal nå', 'vi er hjemme i Stavanger', 'vi er på kontoret'. Dette påvirker hvilket sted som brukes når brukeren spør om været.",
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
                "description": "SYNGE EN SANG! Du MÅ kalle denne funksjonen når brukeren ber deg synge, spille musikk, eller vil høre en sang. Du har et repertoar av sanger. VIKTIG: Kall dette toolet HVER GANG noen ber deg synge - ikke bare si at du skal synge, faktisk GJØR DET ved å kalle denne funksjonen!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "song_name": {
                            "type": "string",
                            "description": "Navnet på sangen å synge. Tilgjengelige sanger: 'Pink Pony Club' (Chappell Roan), 'Still Alive' (Portal 2), 'Her kommer vinteren' (Jokke og Valentinerne), 'Hun er fri' (Raga Rockers), 'Me to går alltid aleina' (Mods), 'Take on Me' (A-ha), 'Touch Me' (Samantha Fox). Hvis ikke spesifisert, velg en tilfeldig sang."
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
                "description": "Sjekk om jeg gjenkjenner personen foran kameraet via face recognition. Bruk når brukeren spør: 'Husker du meg?', 'Vet du hvem jeg er?', 'Kjenner du meg?', 'Har du registrert meg?', 'Gjenkjenner du meg?'. Returnerer om personen er gjenkjent og eventuelt navnet.",
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
                "description": "Start face recognition læringsprosess for å registrere en ny person. Bruk når brukeren sier ja til å bli registrert etter at check_face_recognition viste at de ikke er kjent. Kan ta et valgfritt navn hvis brukeren allerede sa det.",
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
    """
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
                    import sqlite3
                    db_path = '/home/admog/Code/chatgpt-and/duck_memory.db'
                    conn = sqlite3.connect(db_path, timeout=30.0)
                    c = conn.cursor()
                    c.execute("SELECT value FROM profile_facts WHERE key = 'duck_current_location' LIMIT 1")
                    row = c.fetchone()
                    conn.close()
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
                # Skriv trigger-fil for å fortelle Duck å skifte
                with open('/tmp/duck_switch_network.txt', 'w') as f:
                    f.write('SWITCH')
                
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
                    import sqlite3
                    conn = sqlite3.connect(sms_manager.db_path, timeout=30.0)
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    c.execute("SELECT * FROM sms_contacts WHERE name = ? AND enabled = 1", (contact_name,))
                    contact = c.fetchone()
                    conn.close()
                    
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
                    import sqlite3
                    from datetime import datetime
                    conn = sqlite3.connect(sms_manager.db_path, timeout=30.0)
                    conn.row_factory = sqlite3.Row
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
                            conn.close()
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
                    conn.close()
                    
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
                    # Legg til [AVSLUTT] for å umiddelbart avslutte samtalen og gå i sleep mode
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
        elif function_name == "web_search":
            query = function_args.get("query", "")
            count = function_args.get("count", 5)
            result = web_search(query, count)
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
                    import sqlite3
                    db_path = '/home/admog/Code/chatgpt-and/duck_memory.db'
                    conn = sqlite3.connect(db_path, timeout=30.0)
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
                    conn.close()
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
            }
            
            # Finn riktig mappe
            import os
            import random
            musikk_dir = "/home/admog/Code/chatgpt-and/musikk"
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
                    result = f"🎵 OK! Jeg velger å synge {random_song}!"
                else:
                    result = "Fant ingen sanger å synge 😢"
                    song_folder = None
            else:
                song_display = os.path.basename(song_folder)
                result = f"🎵 OK! Jeg skal synge {song_display}!"
            
            # Spill sangen
            if song_folder and os.path.exists(song_folder):
                # Skriv sangsti til samme fil som kontrollpanelet bruker
                try:
                    with open('/tmp/duck_song_request.txt', 'w', encoding='utf-8') as f:
                        f.write(song_folder)
                    print(f"✅ Sang queued for playback: {song_folder}", flush=True)
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
        else:
            result = "Ukjent funksjon"
        
        # Legg til tool result for denne funksjonen
        final_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": function_name,
            "content": result
        })


def chatgpt_query(messages, api_key, model=None, memory_manager=None, user_manager=None, sms_manager=None, hunger_manager=None, vision_service=None, source=None, source_user_id=None):
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
        # Prøv å lese modell fra konfigurasjonsfil
        try:
            if os.path.exists(MODEL_CONFIG_FILE):
                with open(MODEL_CONFIG_FILE, 'r') as f:
                    model = f.read().strip()
                    if not model:
                        model = DEFAULT_MODEL
            else:
                model = DEFAULT_MODEL
        except Exception as e:
            print(f"Feil ved lesing av modellkonfigurasjon: {e}, bruker default", flush=True)
            model = DEFAULT_MODEL
    
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
    tools = _get_function_tools()
    
    data = {
        "model": model,
        "messages": final_messages,
        "tools": tools,
        "tool_choice": "auto"  # La modellen velge når den skal bruke tools
    }
    
    response = requests.post(url, headers=headers, json=data)
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
        _handle_tool_calls(tool_calls, final_messages, source, source_user_id, sms_manager, vision_service)
        
        # Kall API igjen med all tool data
        data["messages"] = final_messages
        response2 = requests.post(url, headers=headers, json=data)
        
        # Bedre error-håndtering for debugging
        if not response2.ok:
            print(f"❌ OpenAI API error {response2.status_code}: {response2.text[:500]}", flush=True)
            print(f"📤 Tool result length: {len(result)} chars", flush=True)
            print(f"📤 Tool result preview: {result[:200]}", flush=True)
        
        response2.raise_for_status()
        reply_content = response2.json()["choices"][0]["message"]["content"]
        
        # Sjekk om brukerens opprinnelige melding var en takk
        user_message = messages[-1]["content"].lower() if messages else ""
        is_thank_you = any(word in user_message for word in ["takk", "tusen takk", "mange takk", "takker"])
        
        return (reply_content, is_thank_you)
    
    # Ingen function call, returner vanlig svar
    user_message = messages[-1]["content"].lower() if messages else ""
    is_thank_you = any(word in user_message for word in ["takk", "tusen takk", "mange takk", "takker"])
    
    return (response_data["choices"][0]["message"]["content"], is_thank_you)
