"""
DuckSettings — Thread-safe in-memory settings manager med JSON-persistens.

Lagrer settings til config/duck_settings.json slik at de overlever restart og reboot.
Beskyttet med threading.Lock for atomisk lesing/skriving.

Bruk:
    from src.duck_settings import get_settings

    settings = get_settings()
    voice = settings.voice          # Lese
    settings.voice = "nb-NO-FinnNeural"  # Skrive (auto-lagret til JSON)

    # Atomisk snapshot av alle TTS-settings:
    tts = settings.get_tts_settings()
    # → {'voice': '...', 'beak': True, 'speed': 40, 'volume': 50}

duck-control.py sender settings via HTTP til intern API-server (port 5111)
som oppdaterer dette objektet. Endringer persisteres automatisk.
"""

import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any

from src.duck_config import DEFAULT_MODEL, DEFAULT_VOICE

# Persistent settings-fil (overlever restart og reboot)
SETTINGS_FILE = Path(__file__).parent.parent / 'config' / 'duck_settings.json'


# ═══════════════════════════════════════════════════════════════
# Defaults — én autoritativ kilde
# ═══════════════════════════════════════════════════════════════
DEFAULTS = {
    'voice': DEFAULT_VOICE,          # nb-NO-IselinNeural
    'beak': 'on',
    'speed': 40,                     # 40 = litt saktere enn normal (-10%)
    'volume': 50,                    # 50 = normal (gain 1.0)
    'model': DEFAULT_MODEL,          # gpt-4.1-mini-2025-04-14
    'personality': 'normal',
}

# Intern API-port (kun localhost)
SETTINGS_API_PORT = 5111


class DuckSettings:
    """
    Thread-safe settings manager.
    Singleton — bruk get_settings() for å hente instansen.
    """
    _instance = None
    _create_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = dict(DEFAULTS)

    @classmethod
    def get_instance(cls) -> 'DuckSettings':
        if cls._instance is None:
            with cls._create_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Property-basert tilgang ──────────────────────────────

    @property
    def voice(self) -> str:
        with self._lock:
            return self._data['voice']

    @voice.setter
    def voice(self, value: str):
        with self._lock:
            self._data['voice'] = value
            self._save_locked()

    @property
    def beak(self) -> str:
        """'on' eller 'off'"""
        with self._lock:
            return self._data['beak']

    @beak.setter
    def beak(self, value: str):
        with self._lock:
            self._data['beak'] = value
            self._save_locked()

    @property
    def beak_enabled(self) -> bool:
        """Convenience: True hvis beak != 'off'"""
        with self._lock:
            return self._data['beak'] != 'off'

    @property
    def speed(self) -> int:
        with self._lock:
            return self._data['speed']

    @speed.setter
    def speed(self, value: int):
        with self._lock:
            self._data['speed'] = max(0, min(100, int(value)))
            self._save_locked()

    @property
    def volume(self) -> int:
        with self._lock:
            return self._data['volume']

    @volume.setter
    def volume(self, value: int):
        with self._lock:
            self._data['volume'] = max(0, min(100, int(value)))
            self._save_locked()

    @property
    def model(self) -> str:
        with self._lock:
            return self._data['model']

    @model.setter
    def model(self, value: str):
        with self._lock:
            self._data['model'] = value
            self._save_locked()

    @property
    def personality(self) -> str:
        with self._lock:
            return self._data['personality']

    @personality.setter
    def personality(self, value: str):
        with self._lock:
            self._data['personality'] = value
            self._save_locked()

    # ── Persistens ───────────────────────────────────────────

    def _save_locked(self):
        """Skriv settings til JSON-fil. MÅ kalles med self._lock holdt."""
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = SETTINGS_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))
            tmp.replace(SETTINGS_FILE)  # Atomisk rename
        except Exception as e:
            print(f"⚠️ Kunne ikke lagre settings: {e}", flush=True)

    def save(self):
        """Eksplisitt lagring (tar lock selv)."""
        with self._lock:
            self._save_locked()

    def load(self):
        """Last settings fra JSON-fil, med fallback til /tmp-filer for migrasjon."""
        loaded = False

        # 1. Prøv JSON-fil først
        if SETTINGS_FILE.exists():
            try:
                saved = json.loads(SETTINGS_FILE.read_text())
                with self._lock:
                    for key, value in saved.items():
                        if key in self._data:
                            if key in ('speed', 'volume'):
                                value = max(0, min(100, int(value)))
                            self._data[key] = value
                loaded = True
                print(f"📋 DuckSettings lastet fra {SETTINGS_FILE.name}", flush=True)
            except Exception as e:
                print(f"⚠️ Feil ved lasting av {SETTINGS_FILE}: {e}", flush=True)

        # 2. Fallback: migrer fra /tmp-filer (engangs)
        if not loaded:
            self._migrate_from_tmp_files()

        settings = self.get_all()
        print(f"📋 DuckSettings: model={settings['model']}, "
              f"voice={settings['voice']}, speed={settings['speed']}, "
              f"volume={settings['volume']}, beak={settings['beak']}, "
              f"personality={settings['personality']}", flush=True)

    def _migrate_from_tmp_files(self):
        """Engangs-migrasjon fra gamle /tmp-filer → JSON."""
        from src.duck_config import (
            VOICE_FILE, BEAK_FILE, SPEED_FILE, VOLUME_FILE,
            MODEL_CONFIG_FILE, PERSONALITY_FILE
        )

        file_map = {
            'voice': (VOICE_FILE, str),
            'beak': (BEAK_FILE, str),
            'speed': (SPEED_FILE, int),
            'volume': (VOLUME_FILE, int),
            'model': (MODEL_CONFIG_FILE, str),
            'personality': (PERSONALITY_FILE, str),
        }

        found_any = False
        with self._lock:
            for key, (filepath, cast) in file_map.items():
                try:
                    if os.path.exists(filepath):
                        with open(filepath, 'r') as f:
                            raw = f.read().strip()
                            if raw:
                                value = cast(raw)
                                if key in ('speed', 'volume'):
                                    value = max(0, min(100, value))
                                self._data[key] = value
                                found_any = True
                except Exception:
                    pass
            # Lagre til JSON så vi ikke trenger /tmp neste gang
            if found_any:
                self._save_locked()
                print("🔄 Migrerte settings fra /tmp-filer til JSON", flush=True)

    # ── Bulk-operasjoner (atomiske) ──────────────────────────

    def get_tts_settings(self) -> Dict[str, Any]:
        """Atomisk snapshot av alle TTS-settings (voice, beak, speed, volume)."""
        with self._lock:
            return {
                'voice': self._data['voice'],
                'beak_enabled': self._data['beak'] != 'off',
                'speed': self._data['speed'],
                'volume': self._data['volume'],
            }

    def get_all(self) -> Dict[str, Any]:
        """Atomisk snapshot av alle settings."""
        with self._lock:
            return dict(self._data)

    def update(self, updates: Dict[str, Any]):
        """Atomisk oppdatering av flere settings samtidig."""
        with self._lock:
            changed = False
            for key, value in updates.items():
                if key in self._data:
                    if key in ('speed', 'volume'):
                        value = max(0, min(100, int(value)))
                    self._data[key] = value
                    changed = True
            if changed:
                self._save_locked()

    def load_from_tmp_files(self):
        """DEPRECATED: Bruk load() i stedet. Beholdt for bakoverkompatibilitet."""
        self.load()

# ═══════════════════════════════════════════════════════════════
# Intern HTTP-server for settings (port 5111, kun localhost)
# duck-control.py POSTer settings hit i stedet for å skrive filer.
# ═══════════════════════════════════════════════════════════════

class _SettingsHandler(BaseHTTPRequestHandler):
    """Minimalistisk HTTP-handler for settings og events."""

    def do_POST(self):
        """POST /settings eller /event."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length).decode())

            if self.path == '/event':
                # Event fra tverr-prosess (duck-control, wifi-portal)
                from src.duck_event_bus import get_event_bus, Event
                bus = get_event_bus()
                event_name = body.get('type', '').upper()
                event_data = body.get('data')
                try:
                    event_type = Event[event_name]
                except KeyError:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': f'Unknown event type: {event_name}'
                    }).encode())
                    return
                bus.post(event_type, event_data)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
            else:
                # Default: settings update
                settings = get_settings()
                settings.update(body)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())

    def do_GET(self):
        """GET /settings — hent alle settings (for duck-control status)."""
        try:
            settings = get_settings()
            data = settings.get_all()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def log_message(self, format, *args):
        """Supprimer standard logging — dette er intern IPC."""
        pass


def start_settings_server():
    """
    Start intern settings-server i en daemon-tråd.
    Kalles fra chatgpt_voice.py ved oppstart.
    """
    server = HTTPServer(('127.0.0.1', SETTINGS_API_PORT), _SettingsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name='settings-api')
    thread.start()
    print(f"📡 Settings API server kjører på http://127.0.0.1:{SETTINGS_API_PORT}", flush=True)
    return server


# ═══════════════════════════════════════════════════════════════
# Global singleton
# ═══════════════════════════════════════════════════════════════

def get_settings() -> DuckSettings:
    """Hent singleton DuckSettings-instansen."""
    return DuckSettings.get_instance()
