"""
Duck Tools Module
AI function calling tools: weather, lights, IP address, and geocoding.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.duck_config import LOCATIONS_FILE


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
