"""
Home Assistant Integration for Duck Assistant
Kontroller enheter via Home Assistant REST API
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Home Assistant konfig (legges i .env)
HA_LOCAL_URL = os.getenv('HA_URL', 'http://homeassistant.local:8123')
HA_CLOUD_URL = os.getenv('HA_CLOUD_URL', '')
HA_TOKEN = os.getenv('HA_TOKEN', '')

# Global cache for aktiv URL (oppdateres ved fallback)
_active_ha_url = HA_LOCAL_URL


def get_ha_url():
    """
    Returner aktiv HA URL med smart fallback.
    Prøver lokal først (rask), deretter cloud (fungerer overalt).
    """
    global _active_ha_url
    return _active_ha_url


def _get_working_ha_url():
    """
    Test og returner en fungerende HA URL (lokal først, deretter cloud).
    Oppdaterer også _active_ha_url cache.
    """
    global _active_ha_url
    
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    
    # Test lokal først
    test_url_local = f"{HA_LOCAL_URL}/api/"
    if _try_ha_request(test_url_local, method='get', headers=headers, timeout=2):
        _active_ha_url = HA_LOCAL_URL
        return HA_LOCAL_URL
    
    # Fallback til cloud
    if HA_CLOUD_URL:
        test_url_cloud = f"{HA_CLOUD_URL}/api/"
        if _try_ha_request(test_url_cloud, method='get', headers=headers, timeout=5):
            _active_ha_url = HA_CLOUD_URL
            print(f"🌍 Byttet til HA Cloud", flush=True)
            return HA_CLOUD_URL
    
    return HA_LOCAL_URL  # Fallback til lokal selv om den feiler


def _try_ha_request(url, method='get', headers=None, json=None, timeout=3):
    """Helper for å prøve HA request med gitt URL"""
    try:
        if method == 'get':
            response = requests.get(url, headers=headers, timeout=timeout)
        else:
            response = requests.post(url, headers=headers, json=json, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException:
        return None


def call_ha_service(domain, service, entity_id=None, data=None):
    """
    Kall en Home Assistant service med smart fallback (lokal → cloud)
    
    Args:
        domain: f.eks. 'light', 'climate', 'media_player', 'cover'
        service: f.eks. 'turn_on', 'turn_off', 'set_temperature'
        entity_id: f.eks. 'light.stue' (valgfritt)
        data: Ekstra data som temperatur, brightness etc.
    
    Returns:
        dict: Response fra HA eller feilmelding
    """
    global _active_ha_url
    
    if not HA_TOKEN:
        return "Home Assistant token mangler i .env (HA_TOKEN)"
    
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {}
    if entity_id:
        payload['entity_id'] = entity_id
    if data:
        payload.update(data)
    
    # Prøv lokal URL først (rask)
    url_local = f"{HA_LOCAL_URL}/api/services/{domain}/{service}"
    response = _try_ha_request(url_local, method='post', headers=headers, json=payload, timeout=3)
    
    if response:
        _active_ha_url = HA_LOCAL_URL  # Oppdater cache
        return f"✅ {service} utført på {entity_id or 'alle enheter'} (lokal)"
    
    # Fallback til cloud URL hvis lokal feiler
    if HA_CLOUD_URL:
        url_cloud = f"{HA_CLOUD_URL}/api/services/{domain}/{service}"
        response = _try_ha_request(url_cloud, method='post', headers=headers, json=payload, timeout=10)
        
        if response:
            _active_ha_url = HA_CLOUD_URL  # Oppdater cache
            print(f"🌍 Bruker HA Cloud (lokal ikke tilgjengelig)", flush=True)
            return f"✅ {service} utført på {entity_id or 'alle enheter'} (cloud)"
    
    return f"❌ Home Assistant ikke tilgjengelig (prøvde lokal og cloud)"


def control_tv(action):
    """Kontroller Samsung TV via HA"""
    entity = "media_player.samsung_8_series_65_ue65ru8005uxxc"
    
    actions = {
        "turn_on": ("media_player", "turn_on"),
        "turn_off": ("media_player", "turn_off"),
        "play": ("media_player", "media_play"),
        "pause": ("media_player", "media_pause"),
        "stop": ("media_player", "media_stop"),
        "next": ("media_player", "media_next_track"),
        "previous": ("media_player", "media_previous_track"),
        "mute": ("media_player", "volume_mute", {"is_volume_muted": True}),
        "unmute": ("media_player", "volume_mute", {"is_volume_muted": False}),
    }
    
    if action not in actions:
        return f"Ugyldig TV-kommando: {action}"
    
    action_data = actions[action]
    domain, service = action_data[0], action_data[1]
    extra_data = action_data[2] if len(action_data) > 2 else None
    
    return call_ha_service(domain, service, entity, extra_data)


def launch_tv_app(app_name):
    """Start en app på Samsung TV"""
    entity = "media_player.samsung_8_series_65_ue65ru8005uxxc"
    
    # Samsung TV source names (from source_list)
    apps = {
        "netflix": "Netflix",
        "youtube": "YouTube",
        "disney": "Disney+",
        "prime": "Prime Video",
        "hbo": "HBO Max",
        "spotify": "Spotify - Music and Podcasts",
        "viaplay": "Viaplay",
        "nrk": "NRK TV",
        "plex": "Plex",
        "twitch": "Twitch",
        "skyshowtime": "SkyShowtime",
        "appletv": "Apple TV",
    }
    
    source = apps.get(app_name.lower())
    if not source:
        return f"Ukjent app: {app_name}. Tilgjengelige: {', '.join(apps.keys())}"
    
    # Samsung TV bruker select_source, ikke play_media
    return call_ha_service("media_player", "select_source", entity, {
        "source": source
    })


def control_ac(action, temperature=None, mode=None):
    """Kontroller Panasonic AC via HA"""
    entity = "climate.thordis_mor"
    
    if action == "turn_on":
        return call_ha_service("climate", "turn_on", entity)
    elif action == "turn_off":
        return call_ha_service("climate", "turn_off", entity)
    elif action == "set_temperature" and temperature:
        return call_ha_service("climate", "set_temperature", entity, 
                              {"temperature": temperature})
    elif action == "set_mode" and mode:
        return call_ha_service("climate", "set_hvac_mode", entity,
                              {"hvac_mode": mode})
    elif action == "get_status":
        # Hent status fra HA
        return get_ha_state(entity)
    else:
        return f"Ugyldig AC-kommando: {action}"


def get_ac_temperature(temp_type="both"):
    """
    Hent temperatur fra AC-sensorer
    
    Args:
        temp_type: "inside", "outside", eller "both" (default)
    
    Returns:
        str: Temperaturinformasjon
    """
    if not HA_TOKEN:
        return "Home Assistant token mangler"
    
    inside_entity = "sensor.thordis_mor_inside_temperature"
    outside_entity = "sensor.thordis_mor_outside_temperature"
    
    url_base = f"{_get_working_ha_url()}/api/states/"
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    
    try:
        result = []
        
        if temp_type in ["inside", "both"]:
            response = requests.get(url_base + inside_entity, headers=headers, timeout=5)
            if response.ok:
                inside_temp = response.json().get('state', 'N/A')
                result.append(f"Inne: {inside_temp}°C")
        
        if temp_type in ["outside", "both"]:
            response = requests.get(url_base + outside_entity, headers=headers, timeout=5)
            if response.ok:
                outside_temp = response.json().get('state', 'N/A')
                result.append(f"Ute: {outside_temp}°C")
        
        return ", ".join(result) if result else "Kunne ikke hente temperatur"
        
    except requests.exceptions.RequestException as e:
        return f"❌ Kunne ikke hente temperatur: {e}"


def control_vacuum(action):
    """Kontroller Saros Z70 støvsuger via HA"""
    entity = "vacuum.saros_z70"
    
    actions = {
        "start": ("vacuum", "start"),
        "pause": ("vacuum", "pause"),
        "stop": ("vacuum", "stop"),
        "return_to_base": ("vacuum", "return_to_base"),
        "locate": ("vacuum", "locate"),
    }
    
    if action not in actions:
        return f"Ugyldig støvsuger-kommando: {action}"
    
    domain, service = actions[action]
    return call_ha_service(domain, service, entity)


def control_twinkly(action, brightness=None, mode=None):
    """Kontroller Twinkly LED-vegg via HA"""
    light_entity = "light.otwinkley"
    mode_entity = "select.otwinkley_mode"
    
    if action == "turn_on":
        return call_ha_service("light", "turn_on", light_entity)
    elif action == "turn_off":
        return call_ha_service("light", "turn_off", light_entity)
    elif action == "set_brightness" and brightness:
        return call_ha_service("light", "turn_on", light_entity, 
                              {"brightness_pct": brightness})
    elif action == "set_mode" and mode:
        # Modes: color, demo, effect, movie, off, playlist, rt
        return call_ha_service("select", "select_option", mode_entity,
                              {"option": mode})
    else:
        return f"Ugyldig Twinkly-kommando: {action}"


def get_email_status(action="summary"):
    """
    Hent e-post status fra MS365 Mail
    
    Args:
        action: "summary" (antall uleste), "latest" (siste e-post), "list" (siste 3)
    
    Returns:
        str: E-post informasjon
    """
    if not HA_TOKEN:
        return "Home Assistant token mangler"
    
    entity = "sensor.m365_mail_mail"
    url = f"{_get_working_ha_url()}/api/states/{entity}"
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        total_count = data.get('state', '0')
        emails = data.get('attributes', {}).get('data', [])
        
        # Tell faktisk uleste e-poster
        unread_emails = [e for e in emails if not e.get('is_read', True)]
        unread_count = len(unread_emails)
        
        if action == "summary":
            if unread_count > 0:
                return f"Ja, du har {unread_count} uleste e-poster blant de {total_count} siste"
            else:
                return f"Nei, alle de {total_count} siste e-postene er lest"
        
        elif action == "latest" and emails:
            latest = emails[0]
            subject = latest.get('subject', 'Ingen emne')
            sender = latest.get('sender', 'Ukjent')
            received = latest.get('received', '')
            is_read = latest.get('is_read', False)
            
            read_status = "lest" if is_read else "ulest"
            return f"Siste e-post ({read_status}): '{subject}' fra {sender}"
        
        elif action == "list" and emails:
            result = f"Siste {min(3, len(emails))} e-poster:\n"
            for i, email in enumerate(emails[:3], 1):
                subject = email.get('subject', 'Ingen emne')
                sender = email.get('sender', 'Ukjent')
                is_read = "✓" if email.get('is_read') else "✉"
                result += f"{i}. {is_read} '{subject}' fra {sender}\n"
            return result.strip()
        
        elif action == "read" and emails:
            # Les innholdet i siste e-post
            latest = emails[0]
            subject = latest.get('subject', 'Ingen emne')
            sender = latest.get('sender', 'Ukjent')
            body_html = latest.get('body', '')
            
            print(f"📧 DEBUG get_email_status(read): sender={sender}, subject={subject}, has_body={bool(body_html)}", flush=True)
            
            if not body_html:
                print(f"📧 DEBUG: E-post mangler body-felt. Tilgjengelige felt: {list(latest.keys())}", flush=True)
                return f"FEIL: Kan ikke lese innhold i e-post fra {sender}. Body-feltet mangler i sensordataene."
            
            # Rens HTML-tags
            import re
            clean_body = re.sub(r'<[^>]+>', '', body_html)
            clean_body = clean_body.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&amp;', '&')
            clean_body = clean_body.strip()
            
            print(f"📧 DEBUG: Body lengde etter rensing: {len(clean_body)} tegn", flush=True)
            
            # Begrens lengde for TTS (maks ~500 tegn)
            if len(clean_body) > 500:
                clean_body = clean_body[:500] + "..."
            
            return f"E-post fra {sender} med emne '{subject}':\n\n{clean_body}"
        else:
            return "Ingen e-poster funnet"
            
    except requests.exceptions.RequestException as e:
        return f"❌ Kunne ikke hente e-post: {e}"


def get_calendar_events(action="next", calendar="calendar.m365_calendar_calendar"):
    """Hent kalenderavtaler fra M365 Calendar"""
    try:
        response = requests.get(
            f"{_get_working_ha_url()}/api/states/{calendar}",
            headers={"Authorization": f"Bearer {HA_TOKEN}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            state = data.get("state")
            attributes = data.get("attributes", {})
            
            if action == "current":
                # Vis pågående avtale
                if state == "on":
                    message = attributes.get("message", "Ukjent")
                    start = attributes.get("start_time", "")
                    end = attributes.get("end_time", "")
                    location = attributes.get("location", "")
                    loc_str = f" på {location}" if location else ""
                    return f"Pågående: '{message}'{loc_str} (til {end})"
                else:
                    return "Ingen pågående avtaler nå"
            
            elif action == "next":
                # Vis neste avtale
                events = attributes.get("data", [])
                if events and len(events) > 0:
                    next_event = events[0]
                    summary = next_event.get("summary", "Ukjent")
                    start = next_event.get("start", "")
                    location = next_event.get("location", "")
                    loc_str = f" på {location}" if location else ""
                    return f"Neste avtale: '{summary}'{loc_str} ({start})"
                else:
                    return "Ingen kommende avtaler"
            
            elif action == "today":
                # Vis avtaler i dag
                events = attributes.get("data", [])
                if events:
                    event_list = []
                    for event in events[:5]:  # Max 5 avtaler
                        summary = event.get("summary", "Ukjent")
                        start = event.get("start", "")
                        event_list.append(f"  - {summary} ({start})")
                    return f"Avtaler i dag:\n" + "\n".join(event_list)
                else:
                    return "Ingen avtaler i dag"
        
        return f"❌ Kunne ikke hente kalender: {response.status_code}"
    except Exception as e:
        return f"❌ Feil ved henting av kalender: {str(e)}"


def create_calendar_event(summary, start_datetime, end_datetime, description=None, location=None, calendar="calendar.m365_calendar_calendar"):
    """Opprett ny kalenderavtale i M365"""
    try:
        data = {
            "summary": summary,
            "start_date_time": start_datetime,
            "end_date_time": end_datetime
        }
        
        if description:
            data["description"] = description
        if location:
            data["location"] = location
        
        result = call_ha_service(
            "calendar",
            "create_event",
            calendar,
            data
        )
        
        return result
    except Exception as e:
        return f"❌ Feil ved opprettelse av avtale: {str(e)}"


def manage_todo(action="list", item=None, todo_list="todo.m365_todo_tasks"):
    """Administrer To Do-liste i M365"""
    try:
        if action == "list":
            # Hent alle items fra state attributes
            response = requests.get(
                f"{_get_working_ha_url()}/api/states/{todo_list}",
                headers={"Authorization": f"Bearer {HA_TOKEN}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                state = data.get("state", "0")
                return f"Handlelisten har {state} items"
        
        elif action == "add" and item:
            # Legg til item
            result = call_ha_service(
                "todo",
                "add_item",
                todo_list,
                {"item": item}
            )
            return result
        
        elif action == "remove" and item:
            # Fjern item
            result = call_ha_service(
                "todo",
                "remove_item",
                todo_list,
                {"item": item}
            )
            return result
        
        elif action == "complete" and item:
            # Marker som fullført
            result = call_ha_service(
                "todo",
                "update_item",
                todo_list,
                {"item": item, "status": "completed"}
            )
            return result
        
        elif action == "clear":
            # Fjern alle fullførte items
            result = call_ha_service(
                "todo",
                "remove_completed_items",
                todo_list,
                {}
            )
            return result
        
        return "❌ Ugyldig handling eller mangler item-navn"
    except Exception as e:
        return f"❌ Feil ved To Do: {str(e)}"


def get_teams_status():
    """Hent Teams-status"""
    try:
        response = requests.get(
            f"{_get_working_ha_url()}/api/states/sensor.m365_teams_status",
            headers={"Authorization": f"Bearer {HA_TOKEN}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("state", "Ukjent")
            
            # Oversett status til norsk
            status_map = {
                "Available": "Tilgjengelig",
                "Busy": "Opptatt",
                "DoNotDisturb": "Ikke forstyrr",
                "BeRightBack": "Straks tilbake",
                "Away": "Borte",
                "Offline": "Frakoblet"
            }
            
            norwegian_status = status_map.get(status, status)
            return f"Teams-status: {norwegian_status}"
        
        return f"❌ Kunne ikke hente Teams-status: {response.status_code}"
    except Exception as e:
        return f"❌ Feil ved henting av Teams-status: {str(e)}"


def get_teams_chat():
    """Hent siste Teams-melding"""
    try:
        response = requests.get(
            f"{_get_working_ha_url()}/api/states/sensor.m365_teams_chat",
            headers={"Authorization": f"Bearer {HA_TOKEN}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            attributes = data.get("attributes", {})
            
            from_name = attributes.get("from_display_name", "Ukjent")
            content = attributes.get("content", "")
            importance = attributes.get("importance", "normal")
            
            # Rens HTML-tags fra innhold
            import re
            clean_content = re.sub(r'<[^>]+>', '', content)
            clean_content = clean_content.replace('&nbsp;', ' ').strip()
            
            if clean_content:
                importance_str = " (viktig!)" if importance == "high" else ""
                return f"Siste Teams-melding{importance_str}:\nFra: {from_name}\n{clean_content}"
            else:
                return "Ingen Teams-meldinger funnet"
        
        return f"❌ Kunne ikke hente Teams-chat: {response.status_code}"
    except Exception as e:
        return f"❌ Feil ved henting av Teams-chat: {str(e)}"


def activate_scene(scene_name):
    """Aktiver en forhåndsdefinert scene i Home Assistant"""
    
    scenes = {
        "filmkveld": "scene.filmkveld",
        "god_natt": "scene.god_natt",
        "god_morgen": "scene.god_morgen",
        "hjemmekontor": "scene.hjemmekontor"
    }
    
    scene_entity = scenes.get(scene_name.lower().replace(" ", "_"))
    
    if not scene_entity:
        return f"❌ Ukjent scene: {scene_name}. Tilgjengelige: {', '.join(scenes.keys())}"
    
    result = call_ha_service("scene", "turn_on", scene_entity)
    
    # Spesialhåndtering for filmkveld: Start Netflix etter scene
    if scene_name.lower() == "filmkveld" and "✅" in str(result):
        import time
        time.sleep(2)  # Vent på at TV'en skrur seg på
        netflix_result = launch_tv_app("netflix")
        return f"✅ Filmkveld aktivert! Lys dimmet, TV på, Netflix starter..."
    
    if "✅" in str(result):
        return f"✅ Scene '{scene_name}' aktivert!"
    return result


def create_movie_scene():
    """Opprett 'Filmkveld' scene i Home Assistant"""
    
    scene_data = {
        "scene_id": "filmkveld",
        "snapshot_entities": [],
        "entities": {
            # Dimmer stue-lys til 10%
            "light.stue": {
                "state": "on",
                "brightness": 26  # 10% av 255
            },
            "light.stue_tv": {
                "state": "on",
                "brightness": 26
            },
            "light.stue_spisebord": {
                "state": "off"
            },
            # TV på
            "media_player.samsung_8_series_65_ue65ru8005uxxc": {
                "state": "on"
            },
            # PowerView blinds - lukk topp og bunn ved TV
            "cover.stue_tv_topp": {"state": "closed"},
            "cover.stue_tv_bunn": {"state": "closed"}
        }
    }
    
    try:
        HA_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
        HA_TOKEN = os.getenv("HA_TOKEN")
        
        if not HA_TOKEN:
            return "❌ HA_TOKEN mangler i .env"
        
        headers = {
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{_get_working_ha_url()}/api/services/scene/create",
            headers=headers,
            json=scene_data,
            timeout=10
        )
        
        if response.status_code == 200:
            return "✅ Filmkveld scene opprettet! Bruk 'activate_scene(\"filmkveld\")' for å aktivere."
        else:
            return f"❌ Kunne ikke opprette scene: {response.status_code}"
    except Exception as e:
        return f"❌ Feil ved oppretting av scene: {str(e)}"


def control_blinds(action, room=None, position=None):
    """Kontroller Luxaflex gardiner via PowerView Gateway (når installert)"""
    
    # Gardin entities
    entities = {
        "tv": "cover.luxaflex_tv",
        "spisebord": "cover.luxaflex_spisebord",
        "trapp": "cover.luxaflex_trapp"
    }
    
    target = entities.get(room) if room else None
    
    if action == "open":
        return call_ha_service("cover", "open_cover", target)
    elif action == "close":
        return call_ha_service("cover", "close_cover", target)
    elif action == "stop":
        return call_ha_service("cover", "stop_cover", target)
    elif action == "position" and position is not None:
        return call_ha_service("cover", "set_cover_position", target,
                              {"position": position})
    else:
        return f"Ugyldig gardin-kommando: {action}"


def get_ha_state(entity_id):
    """Hent tilstand for en enhet fra HA med smart fallback"""
    global _active_ha_url
    
    if not HA_TOKEN:
        return "Home Assistant token mangler"
    
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    
    # Prøv lokal først
    url_local = f"{HA_LOCAL_URL}/api/states/{entity_id}"
    response = _try_ha_request(url_local, method='get', headers=headers, timeout=3)
    
    if not response and HA_CLOUD_URL:
        # Fallback til cloud
        url_cloud = f"{HA_CLOUD_URL}/api/states/{entity_id}"
        response = _try_ha_request(url_cloud, method='get', headers=headers, timeout=10)
        if response:
            _active_ha_url = HA_CLOUD_URL
            print(f"🌍 Bruker HA Cloud for state query", flush=True)
    else:
        _active_ha_url = HA_LOCAL_URL
    
    if not response:
        return f"❌ Kunne ikke hente state for {entity_id}"
    
    try:
        data = response.json()
        state = data.get('state', 'unknown')
        attrs = data.get('attributes', {})
        
        # Format basert på type
        if entity_id.startswith('climate'):
            temp = attrs.get('current_temperature', 'N/A')
            target = attrs.get('temperature', 'N/A')
            return f"{entity_id}: {state}, Temperatur: {temp}°C, Mål: {target}°C"
        elif entity_id.startswith('cover'):
            pos = attrs.get('current_position', 'N/A')
            return f"{entity_id}: {state}, Posisjon: {pos}%"
        else:
            return f"{entity_id}: {state}"
            
    except requests.exceptions.RequestException as e:
        return f"❌ Kunne ikke hente status: {e}"


def control_blinds(location: str, action: str, position: int = None, section: str = None):
    """
    Kontroller Hunter Douglas PowerView persienner (top-down/bottom-up)
    
    Args:
        location: "tv", "spisebord", "inngang" (eller "alle")
        action: "åpne", "lukke", "opp", "ned", "sett" (for posisjon)
        position: 0-100 (valgfri, for prosentvis kontroll)
        section: "topp", "bunn", eller None (begge)
    
    Eksempler:
        - control_blinds("tv", "åpne")  # Åpner både topp og bunn
        - control_blinds("spisebord", "opp", 50, "topp")  # Åpner toppen 50%
        - control_blinds("alle", "lukke")  # Lukker alle
    """
    # Mapper location til entity IDs
    location_map = {
        "tv": "stue_tv",
        "spisebord": "stue_spisebord",
        "inngang": "mot_pappa"
    }
    
    # Velg hvilke entities som skal kontrolleres
    # Standard: åpne fra toppen hvis ikke spesifisert
    if section is None:
        section = "topp"
    
    if location == "alle":
        entities = []
        for loc in location_map.values():
            if section == "topp":
                entities.append(f"cover.{loc}_topp")
            elif section == "bunn":
                entities.append(f"cover.{loc}_bunn")
            elif section == "begge":
                entities.extend([f"cover.{loc}_topp", f"cover.{loc}_bunn"])
    else:
        if location not in location_map:
            return f"❌ Ukjent lokasjon: {location}. Bruk: tv, spisebord, inngang, eller alle"
        
        base = location_map[location]
        if section == "topp":
            entities = [f"cover.{base}_topp"]
        elif section == "bunn":
            entities = [f"cover.{base}_bunn"]
        elif section == "begge":
            entities = [f"cover.{base}_topp", f"cover.{base}_bunn"]
    
    # Bestem service og data basert på action
    if action in ["åpne", "opp"]:
        if position is not None:
            service = "cover.set_cover_position"
            service_data_template = {"position": position}
        else:
            service = "cover.open_cover"
            service_data_template = {}
    elif action in ["lukke", "ned"]:
        if position is not None:
            # "ned 20%" betyr posisjon 20 (20% åpent)
            service = "cover.set_cover_position"
            service_data_template = {"position": position}
        else:
            service = "cover.close_cover"
            service_data_template = {}
    elif action == "sett":
        if position is None:
            return "❌ Du må spesifisere posisjon (0-100) når du bruker 'sett'"
        service = "cover.set_cover_position"
        service_data_template = {"position": position}
    else:
        return f"❌ Ukjent handling: {action}. Bruk: åpne, lukke, opp, ned, sett"
    
    # Utfør kommandoen for hver entity
    results = []
    domain, service_name = service.split('.')
    
    for entity_id in entities:
        # Bruk call_ha_service med riktig argumenter
        extra_data = service_data_template.copy() if service_data_template else {}
        
        result = call_ha_service(domain, service_name, entity_id, extra_data)
        
        # Ekstraher bare entity navn for penere output
        entity_name = entity_id.replace("cover.", "").replace("_", " ").title()
        
        if "✅" in result:
            if position is not None:
                results.append(f"✅ {entity_name}: {position}%")
            else:
                results.append(f"✅ {entity_name}")
        else:
            results.append(f"❌ {entity_name}: Feil")
    
    # Formater output
    location_display = location.title() if location != "alle" else "Alle"
    section_display = f" ({section})" if section else ""
    
    return f"{location_display}{section_display}: {', '.join(results)}"


# Test funksjon
if __name__ == "__main__":
    print("Testing Home Assistant integrasjon...")
    print("\n⚠️  Først må du:")
    print("1. Installer Home Assistant på Pi3B")
    print("2. Lag en Long-Lived Access Token i HA")
    print("3. Legg til i .env:")
    print("   HA_URL=http://homeassistant.local:8123")
    print("   HA_TOKEN=din_token_her")
