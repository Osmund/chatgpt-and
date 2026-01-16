"""
Home Assistant Integration for Duck Assistant
Kontroller enheter via Home Assistant REST API
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Home Assistant konfig (legges i .env)
HA_URL = os.getenv('HA_URL', 'http://homeassistant.local:8123')
HA_TOKEN = os.getenv('HA_TOKEN', '')


def call_ha_service(domain, service, entity_id=None, data=None):
    """
    Kall en Home Assistant service
    
    Args:
        domain: f.eks. 'light', 'climate', 'media_player', 'cover'
        service: f.eks. 'turn_on', 'turn_off', 'set_temperature'
        entity_id: f.eks. 'light.stue' (valgfritt)
        data: Ekstra data som temperatur, brightness etc.
    
    Returns:
        dict: Response fra HA eller feilmelding
    """
    if not HA_TOKEN:
        return "Home Assistant token mangler i .env (HA_TOKEN)"
    
    url = f"{HA_URL}/api/services/{domain}/{service}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {}
    if entity_id:
        payload['entity_id'] = entity_id
    if data:
        payload.update(data)
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        return f"✅ {service} utført på {entity_id or 'alle enheter'}"
    except requests.exceptions.RequestException as e:
        return f"❌ Home Assistant feil: {e}"


def control_tv(action):
    """Kontroller Samsung TV via HA"""
    entity = "media_player.samsung_tv"
    
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
    
    url_base = f"{HA_URL}/api/states/"
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


def control_blinds(action, room=None, position=None):
    """Kontroller Luxaflex gardiner via HA (når du får Gateway)"""
    
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
    """Hent tilstand for en enhet fra HA"""
    if not HA_TOKEN:
        return "Home Assistant token mangler"
    
    url = f"{HA_URL}/api/states/{entity_id}"
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
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


# Test funksjon
if __name__ == "__main__":
    print("Testing Home Assistant integrasjon...")
    print("\n⚠️  Først må du:")
    print("1. Installer Home Assistant på Pi3B")
    print("2. Lag en Long-Lived Access Token i HA")
    print("3. Legg til i .env:")
    print("   HA_URL=http://homeassistant.local:8123")
    print("   HA_TOKEN=din_token_her")
