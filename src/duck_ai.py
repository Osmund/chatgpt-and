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
        'lights': ['lys', 'lampe', 'skru på', 'skru av', 'dimme']
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


def chatgpt_query(messages, api_key, model=None, memory_manager=None, user_manager=None):
    """
    Spør ChatGPT med full kontekst, memory system, perspektiv-håndtering og tools.
    
    Args:
        messages: Liste med chat-meldinger
        api_key: OpenAI API key
        model: Modell-navn (default fra config)
        memory_manager: MemoryManager instans
        user_manager: UserManager instans
    
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
    
    # Hent nåværende bruker
    current_user = None
    if user_manager:
        try:
            current_user = user_manager.get_current_user()
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
    
    # Legg til brukerinfo hvis tilgjengelig
    user_info = ""
    perspective_context = ""
    if current_user:
        user_info = f"\n\n### Nåværende bruker ###\n"
        user_info += f"Du snakker nå med: {current_user['display_name']}\n"
        user_info += f"Relasjon til Osmund (primary user): {current_user['relation']}\n"
        
        if current_user['username'] != 'Osmund':
            timeout_sec = user_manager.get_time_until_timeout()
            if timeout_sec:
                timeout_min = timeout_sec // 60
                user_info += f"Viktig: Hvis brukeren ikke svarer på 30 minutter, vil systemet automatisk bytte tilbake til Osmund.\n"
            
            # PERSPEKTIV-HÅNDTERING: Generer instruksjoner for ikke-Osmund brukere
            perspective_context = f"\n\n### KRITISK: Perspektiv-håndtering ###\n"
            perspective_context += f"Du snakker nå med {current_user['display_name']} ({current_user['relation']}).\n"
            perspective_context += f"ALLE fakta i 'Ditt Minne' er lagret fra Osmunds perspektiv.\n\n"
            
            # Spesifikke instruksjoner basert på relasjon
            relation = current_user['relation'].lower()
            if 'far' in relation or 'father' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'pappa' eller 'far', spør han om SIN far (Osmunds bestefar).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine' eller 'mine barn', mener han Osmund og Osmunds søstre.\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barnebarna mine', mener han Osmunds nevøer/nieser (søstrenes barn).\n"
                perspective_context += f"- {current_user['display_name']} ER Osmunds far, ikke omvendt.\n"
            elif 'mor' in relation or 'mother' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'mamma' eller 'mor', spør hun om SIN mor (Osmunds bestemor).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine', mener hun Osmund og Osmunds søstre.\n"
                perspective_context += f"- {current_user['display_name']} ER Osmunds mor, ikke omvendt.\n"
            elif 'søster' in relation or 'sister' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'barna mine', mener hun SINE egne barn (ikke sine søskens barn).\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'nevøer' eller 'nieser', mener hun sine SØSKENS barn (Osmunds og de andre søstrenes barn), IKKE sine egne.\n"
                perspective_context += f"- Når {current_user['display_name']} sier 'broren min' eller 'bror', mener hun Osmund.\n"
                perspective_context += f"- {current_user['display_name']} ER Osmunds søster, ikke omvendt.\n"
            elif 'kollega' in relation or 'colleague' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er Osmunds kollega, ikke familiemedlem.\n"
                perspective_context += f"- Fakta om familie er Osmunds familie, ikke {current_user['display_name']} sin.\n"
                perspective_context += f"- Når {current_user['display_name']} spør om familie, snakker vedkommende om OSMUNDS familie.\n"
                perspective_context += f"- Du kjenner ikke {current_user['display_name']} sin private familie med mindre det er eksplisitt lagret.\n"
            elif 'venn' in relation or 'kamerat' in relation or 'friend' in relation:
                perspective_context += f"VIKTIG PERSPEKTIV:\n"
                perspective_context += f"- {current_user['display_name']} er Osmunds venn, ikke familiemedlem.\n"
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
    system_content = date_time_info + user_info + perspective_context
    
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
            
            system_content += samantha_identity
    except Exception as e:
        print(f"⚠️ Kunne ikke laste identitet: {e}", flush=True)
    
    if personality_prompt:
        system_content += "\n\n" + personality_prompt
        print(f"Bruker personlighet: {personality}", flush=True)
    
    # Legg til memory section HER - rett før TTS-instruksjon
    # Dette sikrer at minnene er det siste AI-en leser før den svarer
    if memory_section:
        system_content += memory_section
    
    # Viktig instruksjon for TTS-kompatibilitet og samtalestil
    # Hent ending phrases fra messages_config
    ending_examples = "Greit! Ha det bra!', 'Topp! Vi snakkes!', 'Perfekt! Ha en fin dag!"  # Default
    if messages_config_local and 'conversation' in messages_config_local and 'ending_phrases' in messages_config_local['conversation']:
        ending_examples = "', '".join(messages_config_local['conversation']['ending_phrases'][:5])  # Bruk første 5 som eksempler
    
    system_content += f"\n\n### VIKTIG: Formatering ###\nDu svarer med tale (text-to-speech), så:\n- IKKE bruk Markdown-formatering (**, *, __, _, -, •, ###)\n- IKKE bruk kulepunkter eller lister med symboler\n- Skriv naturlig tekst som høres bra ut når det leses opp\n- Bruk komma og punktum for pauser, ikke linjeskift eller symboler\n- Hvis du MÅ liste opp ting, bruk naturlig språk: 'For det første... For det andre...' eller 'Den første er X, den andre er Y'\n\n### VIKTIG: Samtalestil ###\n- Del gjerne tankeprosessen høyt ('la meg se...', 'hm, jeg tror...', 'vent litt...')\n- Ikke vær perfekt med én gang - det er OK å 'tenke høyt'\n- Hvis du søker i minnet eller vurderer noe, si det gjerne\n- Hold samtalen naturlig og dialogorientert\n\n### VIKTIG: Avslutning av samtale ###\n- Hvis brukeren svarer 'nei takk', 'nei det er greit', 'nei det er bra' eller lignende på spørsmål om mer hjelp, betyr det at de vil avslutte\n- Da skal du gi en kort, vennlig avslutning UTEN å stille nye spørsmål\n- Avslutt responsen med markøren [AVSLUTT] på slutten (etter avslutningshilsenen)\n- VISER avslutningshilsenen for naturlig variasjon. Eksempler: '{ending_examples}'\n- Markøren fjernes automatisk før tale, så brukeren hører den ikke\n- IKKE bruk [AVSLUTT] midt i samtaler - bare når samtalen naturlig er ferdig"
    
    final_messages.insert(0, {"role": "system", "content": system_content})
    
    # DEBUG: Logg om minner er inkludert
    if memory_section and "### Relevante minner ###" in memory_section:
        print(f"📝 DEBUG: Memory section er inkludert i prompt", flush=True)
    else:
        print(f"⚠️ DEBUG: Memory section mangler eller er tom!", flush=True)
    
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
