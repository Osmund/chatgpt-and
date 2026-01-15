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


def get_coordinates(location_name):
    """
    Hent koordinater for et stedsnavn - sjekker først lokal database, deretter Nominatim.
    
    Returns:
        tuple: (lat, lon, display_name) eller None
    """
    try:
        # Først: Sjekk om stedet finnes i vår lokale database
        if os.path.exists(LOCATIONS_FILE):
            try:
                with open(LOCATIONS_FILE, 'r', encoding='utf-8') as f:
                    locations_data = json.load(f)
                    locations = locations_data.get('locations', {})
                    
                    # Søk case-insensitive
                    location_key = location_name.lower().strip()
                    if location_key in locations:
                        loc = locations[location_key]
                        print(f"📍 Bruker lokal koordinat for {loc['name']}", flush=True)
                        return loc['lat'], loc['lon'], loc['description']
            except Exception as e:
                print(f"Kunne ikke lese locations-fil: {e}", flush=True)
        
        # Fallback: Søk via Nominatim (OpenStreetMap)
        search_query = f"{location_name}, Norge"
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': search_query,
            'format': 'json',
            'limit': 1
        }
        headers = {
            'User-Agent': 'ChatGPTDuck/2.1.2 (contact: github.com/osmund/chatgpt-and)'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            display_name = data[0].get('display_name', location_name)
            print(f"📍 Bruker Nominatim for {location_name}", flush=True)
            return lat, lon, display_name
        return None
    except Exception as e:
        print(f"Geocoding feil for '{location_name}': {e}", flush=True)
        return None


def get_weather(location_name, timeframe="now"):
    """
    Hent værmelding fra yr.no (MET Norway API).
    
    Args:
        location_name: Navn på stedet
        timeframe: "now" (nå), "today" (i dag), "tomorrow" (i morgen)
    
    Returns:
        str: Værmelding med temperatur og beskrivelse
    """
    try:
        # Først: Finn koordinater for stedet
        coords = get_coordinates(location_name)
        if not coords:
            return f"Beklager, jeg fant ikke stedet '{location_name}'."
        
        lat, lon, display_name = coords
        print(f"Værdata for {display_name} (lat: {lat}, lon: {lon}), tidsramme: {timeframe}", flush=True)
        
        # Hent værdata fra MET Norway locationforecast API
        url = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
        params = {'lat': lat, 'lon': lon}
        headers = {
            'User-Agent': 'ChatGPTDuck/2.1.2 (contact: github.com/osmund/chatgpt-and)'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse værdata
        timeseries = data['properties']['timeseries']
        
        # Oversett symbolkoder til norsk
        symbol_translations = {
            'clearsky': 'klarvær',
            'cloudy': 'overskyet',
            'fair': 'lettskyet',
            'fog': 'tåke',
            'heavyrain': 'kraftig regn',
            'heavyrainandthunder': 'kraftig regn og torden',
            'heavyrainshowers': 'kraftige regnbyger',
            'heavysleet': 'kraftig sludd',
            'heavysleetandthunder': 'kraftig sludd og torden',
            'heavysnow': 'kraftig snø',
            'heavysnowandthunder': 'kraftig snø og torden',
            'heavysnowshowers': 'kraftige snøbyger',
            'lightrain': 'lett regn',
            'lightrainandthunder': 'lett regn og torden',
            'lightrainshowers': 'lette regnbyger',
            'lightsleet': 'lett sludd',
            'lightsleetandthunder': 'lett sludd og torden',
            'lightsnow': 'lett snø',
            'lightsnowandthunder': 'lett snø og torden',
            'lightsnowshowers': 'lette snøbyger',
            'partlycloudy': 'delvis skyet',
            'rain': 'regn',
            'rainandthunder': 'regn og torden',
            'rainshowers': 'regnbyger',
            'sleet': 'sludd',
            'sleetandthunder': 'sludd og torden',
            'sleetshowers': 'sluddbyger',
            'snow': 'snø',
            'snowandthunder': 'snø og torden',
            'snowshowers': 'snøbyger'
        }
        
        def get_weather_desc(symbol_code):
            symbol_base = symbol_code.split('_')[0]
            return symbol_translations.get(symbol_base, symbol_code)
        
        now = datetime.now()
        
        if timeframe == "tomorrow":
            # Finn værdata for i morgen
            tomorrow_date = (now + timedelta(days=1)).date()
            
            # Samle data for morgendagen
            tomorrow_temps = []
            tomorrow_symbols = []
            tomorrow_winds = []
            
            for ts in timeseries:
                ts_time = datetime.fromisoformat(ts['time'].replace('Z', '+00:00'))
                if ts_time.date() == tomorrow_date:
                    temp = ts['data']['instant']['details']['air_temperature']
                    tomorrow_temps.append(temp)
                    
                    # Hent vindstyrke
                    wind = ts['data']['instant']['details'].get('wind_speed', 0)
                    tomorrow_winds.append(wind)
                    
                    # Hent værsymbol hvis tilgjengelig
                    if 'next_1_hours' in ts['data']:
                        tomorrow_symbols.append(ts['data']['next_1_hours']['summary']['symbol_code'])
                    elif 'next_6_hours' in ts['data']:
                        tomorrow_symbols.append(ts['data']['next_6_hours']['summary']['symbol_code'])
            
            if not tomorrow_temps:
                return f"Beklager, jeg har ikke værdata for i morgen for {display_name}."
            
            # Beregn min/max temp og gjennomsnittsvind
            min_temp = min(tomorrow_temps)
            max_temp = max(tomorrow_temps)
            avg_wind = sum(tomorrow_winds) / len(tomorrow_winds) if tomorrow_winds else 0
            max_wind = max(tomorrow_winds) if tomorrow_winds else 0
            
            # Beskriv vindstyrke på norsk
            def get_wind_description(speed_ms):
                if speed_ms < 1.6:
                    return "vindstille"
                elif speed_ms < 3.4:
                    return "svak vind"
                elif speed_ms < 5.5:
                    return "lett bris"
                elif speed_ms < 8.0:
                    return "laber bris"
                elif speed_ms < 10.8:
                    return "frisk bris"
                elif speed_ms < 13.9:
                    return "liten kuling"
                elif speed_ms < 17.2:
                    return "stiv kuling"
                elif speed_ms < 20.8:
                    return "sterk kuling"
                elif speed_ms < 24.5:
                    return "liten storm"
                elif speed_ms < 28.5:
                    return "full storm"
                else:
                    return "sterk storm"
            
            wind_desc = get_wind_description(avg_wind)
            
            # Finn mest vanlige værsymbol
            most_common_symbol = "ukjent"
            if tomorrow_symbols:
                from collections import Counter
                most_common_symbol = Counter(tomorrow_symbols).most_common(1)[0][0]
            
            weather_desc = get_weather_desc(most_common_symbol)
            
            # Hent total nedbør for morgendagen
            total_precipitation = 0
            for ts in timeseries:
                ts_time = datetime.fromisoformat(ts['time'].replace('Z', '+00:00'))
                if ts_time.date() == tomorrow_date:
                    if 'next_1_hours' in ts['data'] and 'details' in ts['data']['next_1_hours']:
                        precip = ts['data']['next_1_hours']['details'].get('precipitation_amount', 0)
                        total_precipitation += precip
            
            result = f"Værmelding for {display_name} i morgen:\n"
            result += f"Temperatur: {min_temp:.1f}°C til {max_temp:.1f}°C\n"
            result += f"Vær: {weather_desc}\n"
            result += f"Vind: {wind_desc} (gjennomsnitt {avg_wind:.1f} m/s, maks {max_wind:.1f} m/s)\n"
            
            # Legg til nedbør hvis relevant
            if total_precipitation > 0.1:
                result += f"Nedbør: {total_precipitation:.1f} mm"
            else:
                result += "Ingen nedbør ventet"
            
        else:  # "now" eller "today"
            # Nåværende vær (første tidspunkt)
            current = timeseries[0]['data']['instant']['details']
            current_temp = current['air_temperature']
            
            # Hent vinddata
            wind_speed = current.get('wind_speed', 0)  # m/s
            wind_from_direction = current.get('wind_from_direction', None)  # grader
            
            # Konverter vindretning fra grader til kompassretning
            def get_wind_direction(degrees):
                if degrees is None:
                    return ""
                directions = ["nord", "nordøst", "øst", "sørøst", "sør", "sørvest", "vest", "nordvest"]
                index = round(degrees / 45) % 8
                return directions[index]
            
            # Beskriv vindstyrke på norsk (basert på Beaufort-skala)
            def get_wind_description(speed_ms):
                if speed_ms < 1.6:
                    return "vindstille"
                elif speed_ms < 3.4:
                    return "svak vind"
                elif speed_ms < 5.5:
                    return "lett bris"
                elif speed_ms < 8.0:
                    return "laber bris"
                elif speed_ms < 10.8:
                    return "frisk bris"
                elif speed_ms < 13.9:
                    return "liten kuling"
                elif speed_ms < 17.2:
                    return "stiv kuling"
                elif speed_ms < 20.8:
                    return "sterk kuling"
                elif speed_ms < 24.5:
                    return "liten storm"
                elif speed_ms < 28.5:
                    return "full storm"
                else:
                    return "sterk storm"
            
            wind_desc = get_wind_description(wind_speed)
            wind_dir = get_wind_direction(wind_from_direction)
            wind_text = f"{wind_desc}"
            if wind_dir and wind_speed >= 1.6:  # Kun vis retning hvis det er vind
                wind_text += f" fra {wind_dir}"
            wind_text += f" ({wind_speed:.1f} m/s)"
            
            # Finn symbolkode for nåværende vær
            current_symbol = "ukjent"
            if 'next_1_hours' in timeseries[0]['data']:
                current_symbol = timeseries[0]['data']['next_1_hours']['summary']['symbol_code']
            elif 'next_6_hours' in timeseries[0]['data']:
                current_symbol = timeseries[0]['data']['next_6_hours']['summary']['symbol_code']
            
            weather_desc = get_weather_desc(current_symbol)
            
            # Hent nedbør neste time og neste 6 timer
            precip_1h = 0
            precip_6h = 0
            if 'next_1_hours' in timeseries[0]['data'] and 'details' in timeseries[0]['data']['next_1_hours']:
                precip_1h = timeseries[0]['data']['next_1_hours']['details'].get('precipitation_amount', 0)
            if 'next_6_hours' in timeseries[0]['data'] and 'details' in timeseries[0]['data']['next_6_hours']:
                precip_6h = timeseries[0]['data']['next_6_hours']['details'].get('precipitation_amount', 0)
            
            # Hent prognose for resten av dagen (neste 6-12 timer)
            forecast_summary = []
            for i in range(1, min(13, len(timeseries))):  # Neste 12 timer
                ts = timeseries[i]
                time_str = ts['time']
                temp = ts['data']['instant']['details']['air_temperature']
                
                # Hent hver 3. time for å ikke overbelaste
                if i % 3 == 0:
                    hour = time_str.split('T')[1][:5]
                    forecast_summary.append(f"{hour}: {temp:.1f}°C")
            
            # Bygg svar
            result = f"Værmelding for {display_name}:\n"
            result += f"Nå: {current_temp:.1f}°C, {weather_desc}\n"
            result += f"Vind: {wind_text}\n"
            
            # Legg til nedbør-informasjon
            if precip_1h > 0.1:
                result += f"Nedbør neste time: {precip_1h:.1f} mm\n"
            elif precip_6h > 0.1:
                result += f"Nedbør neste 6 timer: {precip_6h:.1f} mm\n"
            else:
                result += "Ingen nedbør ventet\n"
            
            if forecast_summary:
                result += f"Prognose i dag: {', '.join(forecast_summary[:4])}"  # Max 4 tidspunkt
        
        return result
        
    except Exception as e:
        print(f"Værhenting feil: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Beklager, jeg kunne ikke hente værdata akkurat nå. Feil: {str(e)}"


def control_hue_lights(action, room=None, brightness=None, color=None):
    """
    Kontroller Philips Hue smarte lys.
    
    Args:
        action: "on", "off", "dim", "brighten" 
        room: Navnet på rommet/lyset (None = alle lys)
        brightness: 0-100 (prosent)
        color: "rød", "blå", "grønn", "gul", "hvit", "rosa", "lilla", "oransje"
    
    Returns:
        str: Beskrivelse av hva som ble gjort
    """
    try:
        bridge_ip = os.getenv("HUE_BRIDGE_IP")
        api_key = os.getenv("HUE_API_KEY")
        
        if not bridge_ip or not api_key:
            return "Philips Hue er ikke konfigurert. Legg til HUE_BRIDGE_IP og HUE_API_KEY i .env"
        
        base_url = f"http://{bridge_ip}/api/{api_key}"
        
        # Hent alle lys
        response = requests.get(f"{base_url}/lights", timeout=5)
        response.raise_for_status()
        lights = response.json()
        
        if not lights:
            return "Fant ingen Philips Hue-lys på nettverket."
        
        # Finn hvilke lys som skal styres
        target_lights = []
        if room:
            # Søk etter lys som matcher romnavnet
            room_lower = room.lower()
            for light_id, light_data in lights.items():
                light_name = light_data.get('name', '').lower()
                if room_lower in light_name:
                    target_lights.append((light_id, light_data['name']))
            
            if not target_lights:
                return f"Fant ingen lys som matcher '{room}'. Tilgjengelige lys: {', '.join([lights[lid]['name'] for lid in lights])}"
        else:
            # Alle lys
            target_lights = [(lid, lights[lid]['name']) for lid in lights]
        
        # Fargekart (Hue format: 0-65535)
        color_map = {
            'rød': {'hue': 0, 'sat': 254},
            'oransje': {'hue': 5000, 'sat': 254},
            'gul': {'hue': 12000, 'sat': 254},
            'grønn': {'hue': 25500, 'sat': 254},
            'cyan': {'hue': 35000, 'sat': 254},
            'blå': {'hue': 46920, 'sat': 254},
            'lilla': {'hue': 50000, 'sat': 254},
            'rosa': {'hue': 56100, 'sat': 254},
            'hvit': {'sat': 0, 'ct': 366}  # Varm hvit
        }
        
        # Bygg state-objektet
        state = {}
        
        if action == "on":
            state['on'] = True
            if brightness is not None:
                state['bri'] = int(brightness * 254 / 100)  # Konverter 0-100 til 0-254
            if color and color.lower() in color_map:
                state.update(color_map[color.lower()])
        
        elif action == "off":
            state['on'] = False
        
        elif action == "dim":
            current_bri = 100  # Default
            state['on'] = True
            if brightness:
                state['bri'] = int(brightness * 254 / 100)
            else:
                state['bri'] = 50  # 20% lysstyrke
        
        elif action == "brighten":
            state['on'] = True
            if brightness:
                state['bri'] = int(brightness * 254 / 100)
            else:
                state['bri'] = 254  # Full lysstyrke
        
        # Utfør kommandoen på alle target lys
        results = []
        for light_id, light_name in target_lights:
            try:
                url = f"{base_url}/lights/{light_id}/state"
                resp = requests.put(url, json=state, timeout=5)
                resp.raise_for_status()
                results.append(light_name)
            except Exception as e:
                print(f"Feil ved kontroll av {light_name}: {e}", flush=True)
        
        # Bygg svar
        action_desc = {
            'on': 'skrudd på',
            'off': 'skrudd av',
            'dim': 'dimmet',
            'brighten': 'gjort lysere'
        }.get(action, action)
        
        if results:
            result_msg = f"Jeg har {action_desc} {len(results)} lys: {', '.join(results)}"
            if brightness:
                result_msg += f" til {brightness}%"
            if color:
                result_msg += f" ({color} farge)"
            return result_msg
        else:
            return f"Kunne ikke kontrollere noen lys."
        
    except Exception as e:
        print(f"Hue-kontroll feil: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Beklager, jeg kunne ikke kontrollere Hue-lysene akkurat nå. Feil: {str(e)}"


def get_ip_address_tool():
    """
    Hent nåværende IP-adresse for Pi'en.
    
    Returns:
        str: IP-adresse formatert for tale
    """
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        
        if ip_address and ip_address != "127.0.0.1":
            # Formater IP-adresse for tale
            ip_spoken = ip_address.replace('.', ' punkt ')
            return f"Min IP-adresse er {ip_spoken}. Du finner kontrollpanelet på port 3000, altså: http://{ip_address}:3000"
        else:
            return "Jeg kunne ikke finne en gyldig IP-adresse. Jeg er kanskje ikke koblet til et nettverk."
    except Exception as e:
        print(f"Feil ved henting av IP-adresse: {e}", flush=True)
        return "Beklager, jeg kunne ikke hente IP-adressen min akkurat nå. Sjekk at jeg er koblet til nettverket."


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
        'weather': ['vær', 'temperatur', 'regn', 'sol', 'varmt', 'kaldt'],
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
        # Modellen vil kalle en funksjon
        tool_call = message["tool_calls"][0]
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
        else:
            result = "Ukjent funksjon"
        
        # Legg til function call og resultat i conversation
        final_messages.append(message)
        final_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": function_name,
            "content": result
        })
        
        # Kall API igjen med værdata
        data["messages"] = final_messages
        response2 = requests.post(url, headers=headers, json=data)
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
