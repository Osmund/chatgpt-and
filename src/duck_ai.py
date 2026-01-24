"""
Duck AI Module
Handles ChatGPT queries, function calling, and tool integrations.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.duck_config import (
    MODEL_CONFIG_FILE, DEFAULT_MODEL, PERSONALITY_FILE, MESSAGES_FILE,
    LOCATIONS_FILE, PERSONALITIES_FILE, SAMANTHA_IDENTITY_FILE,
    OPENAI_API_KEY_ENV, HA_TOKEN_ENV, HA_URL_ENV
)
from src.duck_tools import get_weather, control_hue_lights, get_ip_address_tool, get_netatmo_temperature
from src.duck_homeassistant import control_tv, control_ac, get_ac_temperature, control_vacuum, launch_tv_app, control_twinkly, get_email_status, get_calendar_events, create_calendar_event, manage_todo, get_teams_status, get_teams_chat, activate_scene, control_blinds


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
        'teams': ['teams', 'status', 'tilgjengelig', 'chat', 'melding']
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


def chatgpt_query(messages, api_key, model=None, memory_manager=None, user_manager=None, sms_manager=None, hunger_manager=None, source=None, source_user_id=None):
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
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
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
    
    # Legg til dato/tid + personlighet i system-prompt
    final_messages = messages.copy()
    system_content = date_time_info + tamagotchi_status + user_info + perspective_context
    
    # Samle memory context først (men legg til senere)
    memory_section = ""
    if memory_manager:
        try:
            # Hent brukerens siste melding for relevant søk
            user_query = messages[-1]["content"] if messages else ""
            # Send med current_user for å filtrere minner og meldinger
            context = memory_manager.build_context_for_ai(user_query, recent_messages=3, user_name=current_user['username'])
            
            # Bygg memory section (legges til senere)
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
                
                # Bygg eksplisitt oversikt over søstrene direkte fra databasen (ikke kontekst) 
                # for å sikre at ALLE søstre inkluderes
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
            
            print(f"✅ Memory context bygget ({len(context['profile_facts'])} facts, {len(context['relevant_memories'])} minner)", flush=True)
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

**Skapt av:**
{creator_name} har programmert og bygget deg fra bunnen av. Du er et hobbyprojekt som har vokst til et avansert system!

**Viktig:**
Når folk spør hvordan du fungerer, forklar gjerne teknisk - men husk at DU ER EN AND! Du snakker om disse tingene som din kropp og hjerne, ikke som "et system". Si "nebbet mitt styres av en servo" ikke "systemet bruker en servo".
"""
            
            system_content += samantha_identity
    except Exception as e:
        print(f"⚠️ Kunne ikke laste identitet: {e}", flush=True)
    
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
    
    system_content += f"\n\n### VIKTIG: Bruk av verktøy ###\n- Du har tilgang til verktøy for smart home, e-post, kalender, etc.\n- ALLTID bruk verktøyene når brukeren ber om informasjon du ikke har\n- ALDRI gå ut fra eller 'gjett' data som e-postinnhold, kalenderhendelser, temperaturer, etc.\n- Hvis du kaller et verktøy og får en FEIL-melding, si alltid at det ikke fungerte\n- Eksempel: Hvis brukeren sier 'les den siste e-posten' MÅ du kalle get_email_status(action='read')\n- Eksempel: Hvis brukeren spør 'hva er temperaturen' MÅ du kalle get_weather() eller get_netatmo_data()\n- ALDRI svar med data du ikke har hentet via et verktøy\n\n### VIKTIG: Formatering ###\nDu svarer med tale (text-to-speech), så:\n- IKKE bruk Markdown-formatering (**, *, __, _, -, •, ###)\n- IKKE bruk kulepunkter eller lister med symboler\n- Skriv naturlig tekst som høres bra ut når det leses opp\n- Bruk komma og punktum for pauser, ikke linjeskift eller symboler\n- Hvis du MÅ liste opp ting, bruk naturlig språk: 'For det første... For det andre...' eller 'Den første er X, den andre er Y'\n\n### VIKTIG: Samtalestil ###\n- Del gjerne tankeprosessen høyt ('la meg se...', 'hm, jeg tror...', 'vent litt...')\n- Ikke vær perfekt med én gang - det er OK å 'tenke høyt'\n- Hvis du søker i minnet eller vurderer noe, si det gjerne\n- Hold samtalen naturlig og dialogorientert\n\n### VIKTIG: Avslutning av samtale ###\n- Hvis brukeren svarer 'nei takk', 'nei det er greit', 'nei det er bra' eller lignende på spørsmål om mer hjelp, betyr det at de vil avslutte\n- Da skal du gi en kort, vennlig avslutning UTEN å stille nye spørsmål\n- Avslutt responsen med markøren [AVSLUTT] på slutten (etter avslutningshilsenen)\n- Bruk adaptive avslutninger basert på din personlighet. Eksempler: '{ending_examples}'\n- Markøren fjernes automatisk før tale, så brukeren hører den ikke\n- IKKE bruk [AVSLUTT] midt i samtaler - bare når samtalen naturlig er ferdig"
    
    final_messages.insert(0, {"role": "system", "content": system_content})
    
    # DEBUG: Logg om minner er inkludert
    if memory_section and "### Relevante minner ###" in memory_section:
        print(f"📝 Memory section inkludert i prompt", flush=True)
    else:
        print(f"💭 Ingen relevante minner funnet for denne konteksten", flush=True)
    
    # Definer function tools
    from src.duck_audio import control_beak
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Hent værmelding og temperatur for et spesifikt sted i Norge. Kan hente vær for nå, i dag eller i morgen.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Navnet på stedet/byen i Norge, f.eks. 'Oslo', 'Sokndal', 'Bergen'"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Tidsramme for værmeldingen",
                            "enum": ["now", "today", "tomorrow"],
                            "default": "now"
                        }
                    },
                    "required": ["location"]
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
                "description": "Kontroller Samsung Smart TV via Home Assistant. Kan skru på/av, play, pause, stop, next, previous, mute, unmute.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["turn_on", "turn_off", "play", "pause", "stop", "next", "previous", "mute", "unmute"],
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
                "description": "Start en app på Samsung TV. Støttede apper: Netflix, YouTube, Disney+, Prime Video, HBO Max, Spotify, Viaplay, NRK TV, Plex, Twitch, SkyShowtime, Apple TV.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "enum": ["netflix", "youtube", "disney", "prime", "hbo", "spotify", "viaplay", "nrk", "plex", "twitch", "skyshowtime", "appletv"],
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
                "name": "switch_network",
                "description": "Bytt WiFi-nettverk ved å starte hotspot. Bruk når brukeren vil koble til et annet nettverk eller når nettverket blokkerer kontrollpanelet.",
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
                "name": "control_ac",
                "description": "Kontroller Panasonic klimaanlegg (AC) via Home Assistant. Kan skru på/av, endre temperatur, modus, og hente status/temperatur.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["turn_on", "turn_off", "set_temperature", "set_mode", "get_status"],
                            "description": "Hva som skal gjøres: turn_on/off, set_temperature, set_mode, eller get_status for å sjekke nåværende innstillinger"
                        },
                        "temperature": {
                            "type": "integer",
                            "description": "Ønsket temperatur i grader Celsius (kun for set_temperature)"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["heat", "cool", "auto", "dry", "fan_only"],
                            "description": "Driftsmodus (kun for set_mode): heat=varme, cool=kjøle, auto=automatisk"
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_ac_temperature",
                "description": "Hent temperatur fra AC-sensorene (inne og/eller ute). Bruk denne når brukeren spør om temperaturen som AC måler, eller utetemperaturen fra AC.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "temp_type": {
                            "type": "string",
                            "enum": ["inside", "outside", "both"],
                            "description": "Hvilken temperatur som skal hentes: inside=inne, outside=ute, both=begge (default)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_vacuum",
                "description": "Kontroller Saros Z70 robotstøvsuger via Home Assistant. Kan starte støvsuging, pause, stoppe, returnere til base, eller locate (spill lyd).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["start", "pause", "stop", "return_to_base", "locate"],
                            "description": "Hva som skal gjøres: start=start støvsuging, pause=pause, stop=stopp, return_to_base=hjem til base, locate=finn støvsugeren (spill lyd)"
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
                "description": "Kontroller Twinkly LED-vegg via Home Assistant. Kan skru på/av, endre lysstyrke, og velge effekt-modus.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["turn_on", "turn_off", "set_brightness", "set_mode"],
                            "description": "Hva som skal gjøres: turn_on/off, set_brightness (med brightness parameter), set_mode (med mode parameter)"
                        },
                        "brightness": {
                            "type": "integer",
                            "description": "Lysstyrke i prosent (0-100), kun for set_brightness"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["color", "demo", "effect", "movie", "off", "playlist", "rt"],
                            "description": "Effekt-modus: color=fast farge, demo=demo-modus, effect=effekter, movie=film, playlist=spilleliste, rt=real-time"
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
                "name": "get_email_status",
                "description": "VIKTIG: ALLTID bruk dette verktøyet når brukeren spør om e-post! Hent e-post status fra Office 365/Microsoft 365. Kan vise antall uleste, siste e-post, eller liste med siste e-poster. ALDRI svar om e-post uten å kalle dette verktøyet først!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["summary", "latest", "list", "read"],
                            "description": "Hva som skal hentes: summary=antall uleste, latest=siste e-post (emne+avsender), list=siste 3 e-poster, read=les HELE innholdet i siste e-post (bruk når brukeren vil 'lese' eller 'høre' e-posten)"
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
                "description": "Hent kalenderavtaler fra Office 365 Calendar. Kan vise pågående, neste eller dagens avtaler.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["current", "next", "today"],
                            "description": "Hvilken type avtaler: current=pågående nå, next=neste avtale, today=alle i dag"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_calendar_event",
                "description": "Opprett ny kalenderavtale i Office 365 Calendar. Krever tittel og tidspunkt i format YYYY-MM-DD HH:MM:SS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Tittel/emne på avtalen"
                        },
                        "start_datetime": {
                            "type": "string",
                            "description": "Starttid i format YYYY-MM-DD HH:MM:SS (f.eks. 2026-01-17 10:00:00)"
                        },
                        "end_datetime": {
                            "type": "string",
                            "description": "Sluttid i format YYYY-MM-DD HH:MM:SS (f.eks. 2026-01-17 11:00:00)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Beskrivelse/notater (valgfri)"
                        },
                        "location": {
                            "type": "string",
                            "description": "Sted/lokasjon (valgfri)"
                        }
                    },
                    "required": ["summary", "start_datetime", "end_datetime"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "manage_todo",
                "description": "Administrer handleliste/To Do-liste i Office 365. Kan vise, legge til, fjerne, fullføre items eller slette alle fullførte.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["list", "add", "remove", "complete", "clear"],
                            "description": "Handling: list=vis items, add=legg til, remove=fjern, complete=marker ferdig, clear=slett alle fullførte"
                        },
                        "item": {
                            "type": "string",
                            "description": "Navn på item som skal legges til, fjernes eller markeres ferdig"
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
                "description": "Hent din Microsoft Teams-status (Tilgjengelig, Opptatt, Borte, etc.)",
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
                "name": "get_teams_chat",
                "description": "Hent siste Teams-melding med avsender og innhold",
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
                "name": "activate_scene",
                "description": "Aktiver en forhåndsdefinert smart home scene. Tilgjengelige scener: filmkveld (dimmer lys, TV på, Netflix), god_natt (alt av, blinds ned), god_morgen (lys på, blinds opp), hjemmekontor (jobb-lys, AC 22°C)",
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
        }
    ]
    
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
        
        # Prosesser alle tool calls
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])
            
            print(f"ChatGPT kaller funksjon: {function_name} med args: {function_args}", flush=True)
            
            # Liste over smart home funksjoner som krever autorisation
            protected_functions = [
                "control_hue_lights", "control_tv", "launch_tv_app", 
                "control_ac", "control_vacuum", "control_twinkly", 
                "control_blinds", "activate_scene"
            ]
            
            # Sjekk autorisation for smart home-kommandoer via SMS
            if function_name in protected_functions and source == "sms":
                # For SMS: sjekk om bruker er owner
                if source_user_id:
                    from duck_users import UserManager
                    user_db = UserManager()
                    owner = user_db.get_user_by_role('owner')
                    
                    if not owner or source_user_id != owner['id']:
                        result = "❌ Smart home-kontroll er kun tilgjengelig for Osmund via SMS. Andre kan kun kontrollere via talekommando."
                        # Legg til tool result og fortsett
                        final_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": function_name,
                            "content": result
                        })
                        continue
                else:
                    # Ingen user_id sendt, blokkér som sikkerhet
                    result = "❌ Smart home-kontroll krever identifikasjon via SMS."
                    final_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": result
                    })
                    continue
            
            # Kall faktisk funksjon
            if function_name == "get_weather":
                location = function_args.get("location", "")
                timeframe = function_args.get("timeframe", "now")
                result = get_weather(location, timeframe)
            elif function_name == "control_hue_lights":
                action = function_args.get("action")
                room = function_args.get("room")
                brightness = function_args.get("brightness")
                color = function_args.get("color")
                result = control_hue_lights(action, room, brightness, color)
            elif function_name == "control_beak":
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
                import subprocess
                import os
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
            elif function_name == "activate_scene":
                scene_name = args.get("scene_name", "")
                result = activate_scene(scene_name)
            else:
                result = "Ukjent funksjon"
            
            # Legg til tool result for denne funksjonen
            final_messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": result
            })
        
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
