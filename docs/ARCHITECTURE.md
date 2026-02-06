# ChatGPT Duck - Teknisk Arkitektur

## Oversikt

ChatGPT Duck er et distribuert system med tre hovedkomponenter som kommuniserer via fildeling og systemd-kontroll. Koden er organisert i en modulær struktur med `src/` mappen for alle hovedmoduler.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Brukergrensesnitt                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │  Web Browser     │  │  Stemmekommando  │  │  Physical I/O │ │
│  │  (Port 3000)     │  │  (Mikrofon)      │  │  (RGB LED)    │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘ │
└───────────┼─────────────────────┼─────────────────────┼─────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌───────────────────────┐ ┌──────────────────────────────────────┐
│  duck-control.service │ │     chatgpt-duck.service             │
│  (Web Kontrollpanel)  │ │     (Hovedapplikasjon)               │
│                       │ │                                      │
│  - HTTP Server        │ │  - Wake Word Detection (Porcupine)  │
│  - REST API           │ │  - Speech Recognition (Azure STT)   │
│  - Service Control    │ │  - ChatGPT Integration              │
│  - Real-time Logs     │ │  - Text-to-Speech (Azure TTS)       │
│  - Settings UI        │ │  - Beak Servo Control               │
│                       │ │  - RGB LED Control                   │
└───────────┬───────────┘ └────────────┬─────────────────────────┘
            │                          │
            │  IPC via /tmp files      │
            └──────────────────────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
            ▼                       ▼
    ┌──────────────┐        ┌──────────────┐
    │   systemd    │        │  Hardware    │
    │   (Service   │        │  (GPIO pins) │
    │   Manager)   │        │              │
    └──────────────┘        └──────────────┘
```

## Kodestruktur

Prosjektet er organisert med en modulær arkitektur:

```
src/                              # Hovedmoduler
├── duck_config.py                # Konfigurasjon og konstanter
│                                 # - File paths (DB, wake word, temp files)
│                                 # - AI model configuration
│                                 # - Audio configuration (fade, beak timing)
│                                 # - Memory system configuration (NEW!)
│                                 #   * MEMORY_EMBEDDING_SEARCH_LIMIT = 30
│                                 #   * MEMORY_LIMIT = 8
│                                 #   * MEMORY_THRESHOLD = 0.35
│                                 #   * MEMORY_FREQUENT_FACTS_LIMIT = 15
│                                 #   * MEMORY_EXPAND_THRESHOLD = 15
├── duck_audio.py                 # TTS, lydavspilling, beak-kontroll
├── 2. src/duck_speech.py - Wake Word og Talegjenkjenning

**Wake Word Detection**:
- Bruker Porcupine (Picovoice) wake word detection
- Trigger: "Samantha" (custom wake word)
- Krever Picovoice API key i .env
- Modell: samantha_en_raspberry-pi_v4_0_0.ppn
- Sample rate: 16000 Hz (resampler fra USB mic 48000 Hz)
- RGB LED: Blå under lytting

**Speech Recognition**:
- Azure Speech-to-Text
- Høykvalitets cloud-basert gjenkjenning
- Norsk språkstøtte (nb-NO)
- Streaming recognition
- RGB LED: Grønn under innspilling, gul blinkende under prosessering

### 3. src/duck_ai.py - ChatGPT Integrasjon

**ChatGPT Integration**:
- Støtter gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4.1 mini
- System prompts basert på personlighet (fra config/personalities.json)
- Conversation history for kontekst
- Memory integration (henter relevant kontekst)
- Function calling for værmelding, lysstyring, IP-adresse, etc.
- RGB LED: Lilla blinkende under venting på respons

**Verktøy/Tools**:
- `get_weather()`: Henter værdata basert på stedsnavn (fra config/locations.json)
- `control_hue_lights()`: Kontrollerer Philips Hue-lys
- `get_ip_address_tool()`: Returnerer Pi'ens IP-adresse
- `open_beak_tool()`: Manuell kontroll av nebbet

### 4. src/duck_audio.py - TTS og Lydavspilling

**Text-to-Speech**:
- Azure TTS med SSML
- Norske neural voices (Finn, Pernille, Iselin)
- SSML prosody rate control for hastighet
- Synkron nebb-bevegelse via amplitude detection
- RGB LED: Rød under tale
- Markdown-rensing før TTS
- Pitch-shift for "andestemme"

**Lydavspilling**:
- Automatisk deteksjon av HiFiBerry DAC
- USB mikrofon support
- Volum-kontroll via /tmp/duck_volume.txt

### 5. src/duck_music.py - Musikkavspilling

**Sang-avspilling**:
#### ChatGPT Integration
```python
def get_chatgpt_response(text, conversation_history):
    """
    OpenAI GPT API
    - Støtter gpt-3.5-turbo, gpt-4, gpt-4-turbo
    - System prompts basert på personlighet
    - Conversation history for kontekst
    - RGB LED: Lilla blinkende under venting på respons
    """
```

#### Text-to-Speech
```python
def speak(text, voice='nb-NO-FinnNeural', speed=50):
    """
    Azure TTS med SSML
    - Norske neural voices (Finn, Pernille, Iselin)
    - SSML prosody rate control for hastighet
    - Synkron nebb-bevegelse via amplitude detection
    - RGB LED: Rød under tale
    """
```

#### Sang-avspilling (Nytt i 2025/2026)
```python
def play_song(song_path, beak, speech_config):
    """
    Spiller sanger med nebb og LED synkronisering
    - Dual-file system:
      - duck_mix.wav: Full mix for avspilling
      - vocals_duck.wav: Isolert vokal for nebb-synk
    - LED: Pulser i takt med musikkens amplitude
    - Nebb: Følger vokalens amplitude i sanntid
    - Threading: Separate threads for playback, LED og nebb
    - Auto-detection: Støtter stereo og mono WAV-filer
    - Progressbasert synkronisering: Nebb og LED følger playback position
    - Annonsering: Sier artist og sangtittel før avspilling
    - IPC: Kontrolleres via /tmp/duck_song_request.txt og /tmp/duck_song_stop.txt
    """
```

#### Oppstartshilsen med Nettverksdeteksjon
```python
def main():
    # Prøver å koble til nettverk i opptil 10 sekunder
    ip_address = None
    for attempt in range(5):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            if ip_address and ip_address != "127.0.0.1":
                break
        except:
            if attempt < 4:
                time.sleep(2)
    
    # Annonserer IP hvis tilgjengelig, ellers varsler om manglende tilkobling
    if ip_address and ip_address != "127.0.0.1":
        greeting = f"Kvakk kvakk! Jeg er nå klar for andeprat. Min IP-adresse er {ip_address.replace('.', ' punkt ')}. Du finner kontrollpanelet på port 3000. Si navnet mitt for å starte en samtale!"
    else:
        greeting = "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"
    
    speak(greeting, speech_config, beak)
```

**Personligheter** (system prompts):
```python
PERSONALITIES = {
    'normal': "Du er en hjelpsom assistent...",
    'entusiastic': "Du er veldig energisk og entusiastisk...",
    'philosophical': "Du er en dyp tenker...",
    'humorous': "Du er morsom og spøkefull...",
    'concise': "Du svarer kort og konsist..."
}
```

**IPC - Lesing av innstillinger**:
```python
# Leses ved hver interaksjon
personality = read_file('/tmp/duck_personality.txt', 'normal')
voice = read_file('/tmp/duck_voice.txt', 'nb-NO-FinnNeural')
volume = int(read_file('/tmp/duck_volume.txt', '50'))  # 0-100, konverteres til gain (0.0-2.0)
beak_enabled = read_file('/tmp/duck_beak.txt', 'on') == 'on'
speed = int(read_file('/tmp/duck_speed.txt', '50'))  # 0-100, konverteres til SSML rate
model = read_file('/tmp/duck_model.txt', 'gpt-3.5-turbo')
```

**Volumbehandling i TTS**:
```python
# I speak() funksjonen
volume_value = int(read_file('/tmp/duck_volume.txt', '50'))
volume_gain = volume_value / 50.0  # 0=0.0, 50=1.0, 100=2.0
samples = samples * volume_gain  # Anvend på float32 lydsamplene
```

### 2. duck-control.py - Web Kontrollpanel

**Ansvar**: HTTP server for konfigurasjon og administrasjon.

**Arkitektur**: BaseHTTPRequestHandler uten eksterne avhengigheter.

#### HTTP Request Handler
```python
class DuckControlHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Serve HTML, status, logs, current settings
        
    def do_POST(self):
        # Handle configuration changes, service control
```

**HTML Template**: Separate filer i `templates/` mappen.
- `index.html` - Struktur og inline scripts
- `style.css` - All styling (ingen inline-stiler)
- `app.js` - Hovedlogikk (2500+ linjer)

**Kontrollpanel-struktur** (7 seksjoner):
1. **Dashboard** - 2×3 grid med status (bruker, HA, lokasjon, vision, CPU, RAM)
2. **🎮 Tamagotchi** - Sult-, kjedsomhets- og søvnmeter
3. **💬 Snakk med Anda** - Samtale, meldinger og musikk
4. **📱 SMS** - Historikk/kontakter med tab-switching
5. **🎛️ Innstillinger** - Stemme/lyd + AI/oppførsel
6. **🎭 Personlighet** - 10 justerbare personlighetslidere
7. **🧠 Minne** - Stats, worker, fakta, søk, innstillinger
8. **⚙️ System** - Tjenester, brukere, logger, 3D-printer, vifte, backup, WiFi

#### Service Control
```python
subprocess.run(['sudo', 'systemctl', 'start|stop|restart', 'chatgpt-duck.service'])
subprocess.run(['systemctl', 'is-active', 'chatgpt-duck.service'])
```

#### IPC - Skriving av innstillinger
```python
# POST /change-personality
with open('/tmp/duck_personality.txt', 'w') as f:
    f.write(personality)

# POST /change-speed
with open('/tmp/duck_speed.txt', 'w') as f:
    f.write(str(speed))
```

#### Live Logging
```python
subprocess.run(['sudo', 'journalctl', '-u', 'chatgpt-duck.service', 
                '-n', '50', '--no-pager'])
```

**JavaScript Features**:
- Async/await for all API calls
- Smart scroll (only auto-scroll if at bottom)
- Color-coded log lines (red=error, orange=warning, green=success)
- Real-time status badge updates
- Form validation and error handling

### 3. fan_control.py - Automatisk Kjøling

**Ansvar**: Overvåke CPU-temperatur og styre vifte.

**Arkitektur**: 
```python
# Hovedløkke hvert 5. sekund
while True:
    temp = get_cpu_temp()  # Les fra /sys/class/thermal/thermal_zone0/temp
    mode = get_fan_mode()  # Les fra /tmp/duck_fan.txt
    
    if mode == 'auto':
        # Hysterese for å unngå flapping
        if temp >= 55.0:
            GPIO.output(13, GPIO.HIGH)  # Start vifte
        elif temp <= 50.0:
            GPIO.output(13, GPIO.LOW)   # Stopp vifte
    elif mode == 'on':
        GPIO.output(13, GPIO.HIGH)
    elif mode == 'off':
        GPIO.output(13, GPIO.LOW)
    
    write_fan_status(mode, running, temp)  # Skriv til /tmp/duck_fan_status.txt
```

**Hardware**: 
- GPIO 13 (blå ledning fra Raspberry Pi 5 vifte)
- 5V vifte
- PWM-pin (kan senere brukes for hastighetskontroll)

**IPC**:
- `/tmp/duck_fan.txt` - Modus (auto/on/off)
- `/tmp/duck_fan_status.txt` - Status (mode|running|temp)

### 4. duck_beak.py - Servo Kontroll

**Ansvar**: Kontrollere nebb-bevegelse synkront med lyd.

```python
def move_beak_with_amplitude(audio_file_path):
    """
    Amplitude-basert servo-kontroll:
    1. Last lydfilmen med pydub
    2. Beregn RMS amplitude per frame (50ms chunks)
    3. Map amplitude til servo-vinkel (0-180 grader)
    4. Synkroniser servo-bevegelse med lydavspilling
    """
```

**Teknisk detaljer**:
- Bruker `gpiozero.Servo` for PWM-kontroll
- GPIO pin: 14 (PWM capable)
- Amplitude threshold for bevegelse
- Smoothing for naturlig bevegelse

**Separat strømforsyning påkrevd**: Servo kan trekke opptil 1A under bevegelse, som kan forårsake voltage drops og Pi-reboot hvis servet deler strøm med Pi.

### 4. rgb_duck.py - LED Status

**Ansvar**: Visuell tilbakemelding via RGB LED.

```python
class RGBDuck:
    def __init__(self, red_pin=17, green_pin=27, blue_pin=22):
        self.red = LED(red_pin)
        self.green = LED(green_pin)
        self.blue = LED(blue_pin)
    
    def color(self, r, g, b):
        """Set RGB color (0.0 - 1.0)"""
        
    def blink_yellow_purple(self, duration=3.0):
        """Thinking animation"""
        
    def off(self):
        """Turn off all LEDs"""
```

**Farger og tilstander**:
| RGB Verdi | Farge | Tilstand |
|-----------|-------|----------|
| (0, 0, 1) | Blå | Wake word |
| (0, 1, 0) | Grønn | Lytter |
| (1, 1, 0) | Gul | STT prosessering |
| (1, 0, 1) | Lilla | ChatGPT tenking |
| (1, 0, 0) | Rød | Snakker |
| (0, 0, 0) | Av | Idle |

## Data Flow

### Brukerinitialisert Samtale

```
1. Bruker sier "alexa"
   └─> Porcupine detekterer wake word
       └─> RGB: Blå → Grønn
           └─> Azure STT lytter
               └─> RGB: Gul (blinker)
                   └─> Tekst → ChatGPT
                       └─> RGB: Lilla (blinker)
                           └─> Respons → Azure TTS
                               └─> RGB: Rød
                                   └─> Audio + Servo synkronisert
                                       └─> RGB: Blå (tilbake til wake word)
```

### Web-initialisert Melding (Full behandling)

```
1. Bruker skriver i web-panel
   └─> POST /full-response
       └─> Skriver til /tmp/duck_message.txt
           └─> chatgpt_voice.py leser fil
               └─> Tekst → ChatGPT
                   └─> Respons → Azure TTS
                       └─> Audio + Servo synkronisert
```

### Sang-avspilling (Nytt i v2.1.2)

```
1. Bruker klikker "Spill" på sang i web-panel
   └─> POST /play-song {song: "Artist - Title"}
       └─> Skriver "Artist - Title" til /tmp/duck_song_request.txt
           └─> chatgpt_voice.py leser fil i main loop
               └─> Annonserer artist og tittel via speak()
                   └─> play_song() starter
                       │
                       ├─> Last duck_mix.wav (full mix)
                       ├─> Last vocals_duck.wav (isolert vokal)
                       │
                       ├─> Konverter til numpy arrays
                       │   ├─> mix_samples (stereo/mono)
                       │   └─> vocals_samples (mono)
                       │
                       ├─> Start tre threads:
                       │   │
                       │   ├─> Playback thread (main):
                       │   │   └─> sounddevice.OutputStream
                       │   │       └─> Spiller mix_samples i 4096-frame chunks
                       │   │           └─> Oppdaterer mix_idx for synkronisering
                       │   │
                       │   ├─> LED controller thread:
                       │   │   └─> Leser mix amplitude ved current position (mix_idx)
                       │   │       └─> Pulser LED intensity basert på amplitude
                       │   │           └─> Sleep 30ms, repeat
                       │   │
                       │   └─> Beak controller thread:
                       │       └─> Mapper mix_idx til vocals position
                       │           ├─> progress = mix_idx / total_frames
                       │           ├─> vocals_pos = progress * vocals_length
                       │           └─> Leser vocals amplitude ved vocals_pos
                       │               └─> Åpner nebb basert på amplitude
                       │                   └─> Sleep 30ms, repeat
                       │
                       └─> Når ferdig: RGB tilbake til blå (wake word mode)

2. Bruker klikker "Stopp sang"
   └─> POST /stop-song
       └─> Skriver "stop" til /tmp/duck_song_stop.txt
           └─> Threads detekterer stop-fil
               └─> Avslutter playback og threads gracefully
```

**Tekniske detaljer**:
- **Dual-file system**: Separate filer for mix og vocals
- **Progressbasert synkronisering**: `vocals_pos = (mix_idx / total_frames) * vocals_length`
- **Stereo/mono håndtering**: Auto-detection og konvertering
- **Threading**: Separate daemon threads for LED og nebb
- **Sample rates**: Automatisk detection av framerate
- **Chunk sizes**: 30ms for nebb/LED (smooth movement), 4096 frames for playback (stable audio)

### Innstillingsendring

```
1. Bruker velger ny talehastighet (70%)
   └─> JavaScript: POST /change-speed {speed: 70}
       └─> duck-control.py: write('/tmp/duck_speed.txt', '70')
           └─> Response: {success: true}
               └─> JavaScript: updateUI()
   
2. Neste gang anda snakker:
   └─> chatgpt_voice.py: speed = read('/tmp/duck_speed.txt')
       └─> SSML: <prosody rate="+40%">
```

## Sikkerhet og Rettigheter

### Sudo-rettigheter

`duck-control.py` krever sudo for:
- `systemctl start|stop|restart` - Service-kontroll
- `journalctl -u chatgpt-duck.service` - Loggtilgang

**Konfigurasjon** (`/etc/sudoers.d/duck-control`):
```
admog ALL=(ALL) NOPASSWD: /bin/systemctl start chatgpt-duck.service
admog ALL=(ALL) NOPASSWD: /bin/systemctl stop chatgpt-duck.service
admog ALL=(ALL) NOPASSWD: /bin/systemctl restart chatgpt-duck.service
admog ALL=(ALL) NOPASSWD: /bin/journalctl -u chatgpt-duck.service*
```

### API-nøkler

Lagret i `.env` (IKKE commit til git):
```
OPENAI_API_KEY=sk-...
AZURE_TTS_KEY=...
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=...
AZURE_STT_REGION=westeurope
```

### Filrettigheter

```bash
# /tmp filer kan leses/skrives av begge services
chmod 666 /tmp/duck_*.txt

# Service-filer
chmod 644 /etc/systemd/system/*.service

# Executable scripts
chmod +x *.sh
chmod +x *.py
```

## IPC (Inter-Process Communication)

Alle IPC-filer ligger i `/tmp/` for kommunikasjon mellom services:

| Fil | Retning | Formål | Format | Eksempel |
|-----|---------|--------|--------|----------|
| `/tmp/duck_personality.txt` | → chatgpt_voice.py | AI-personlighet | String | `normal`, `humorous`, `philosophical` |
| `/tmp/duck_voice.txt` | → chatgpt_voice.py | TTS-stemme | String | `nb-NO-FinnNeural`, `nb-NO-PernilleNeural` |
| `/tmp/duck_volume.txt` | → chatgpt_voice.py | Lydvolum | Integer (0-100) | `50` (normal), `100` (høyt) |
| `/tmp/duck_speed.txt` | → chatgpt_voice.py | Talehastighet | Integer (0-100) | `50` (normal), `75` (rask) |
| `/tmp/duck_beak.txt` | → chatgpt_voice.py | Nebb på/av | String | `on`, `off` |
| `/tmp/duck_model.txt` | → chatgpt_voice.py | GPT-modell | String | `gpt-3.5-turbo`, `gpt-4` |
| `/tmp/duck_song_request.txt` | → chatgpt_voice.py | Sang-forespørsel | String (path) | `/path/to/song/folder` |
| `/tmp/duck_song_stop.txt` | → chatgpt_voice.py | Stopp sang | String | `stop` |
| `/tmp/duck_fan.txt` | → fan_control.py | Viftemodus | String | `auto`, `on`, `off` |
| `/tmp/duck_fan_status.txt` | ← fan_control.py | Viftestatus | CSV | `auto,running,58.2` |

### Database Storage (NEW!)

Memory-innstillinger lagres i `duck_memory.db` (`profile_facts` tabell) med `topic='system'`:

| Key | Type | Default | Range | Beskrivelse |
|-----|------|---------|-------|-------------|
| `max_context_facts` | int | 100 | 1-200 | Totalt antall fakta i AI kontekst |
| `embedding_search_limit` | int | 30 | 10-100 | Antall facts fra embedding-søk |
| `memory_limit` | int | 8 | 1-20 | Episodiske minner i kontekst |
| `memory_threshold` | float | 0.35 | 0.2-0.8 | Similarity threshold for embeddings |

**Fallback**: Hvis ikke satt i database, brukes defaults fra `duck_config.py`:
- `MEMORY_EMBEDDING_SEARCH_LIMIT`
- `MEMORY_LIMIT`
- `MEMORY_THRESHOLD`
- `MEMORY_FREQUENT_FACTS_LIMIT`
- `MEMORY_EXPAND_THRESHOLD`
| `/tmp/duck_message.txt` | → chatgpt_voice.py | Direktemelding | String | `Hva er været i dag?` |
| `/tmp/duck_song_request.txt` | → chatgpt_voice.py | Sang-forespørsel | String | `A-ha - Take on me` |
| `/tmp/duck_song_stop.txt` | → chatgpt_voice.py | Stopp sang | Eksistens | Fil eksisterer = stopp |
| `/tmp/duck_fan.txt` | → fan_control.py | Vifte-modus | String | `auto`, `on`, `off` |
| `/tmp/duck_fan_status.txt` | ← fan_control.py | Vifte-status | CSV | `auto|true|52.3` (mode\|running\|temp) |

**Filrettigheter**: Alle `/tmp/duck_*.txt` filer må ha 666 permissions for å la services dele data:
```bash
chmod 666 /tmp/duck_*.txt
```

**Lesing (chatgpt_voice.py)**:
```python
def read_file(file_path, default):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return f.read().strip()
    except:
        pass
    return default
```

**Skriving (duck-control.py)**:
```python
def write_file(file_path, content):
    with open(file_path, 'w') as f:
        f.write(content)
```

## Feilhåndtering

### Hovedapplikasjon (chatgpt_voice.py)

**Wake Word Recovery**:
```python
while True:
    try:
        wait_for_wake_word()
        # Conversation loop
    except Exception as e:
        print(f"Error: {e}")
        rgb.color(1, 0, 0)  # Red for error
        time.sleep(2)
        rgb.color(0, 0, 1)  # Back to blue
```

**API Timeouts**:
- Azure STT: 10s timeout
- ChatGPT: 30s timeout
- Azure TTS: 15s timeout

**Retry Logic**:
- 3 attempts for API calls
- Exponential backoff
- User notification via RGB

### Web Panel (duck-control.py)

**HTTP Error Responses**:
```python
try:
    result = subprocess.run(...)
    if result.returncode == 0:
        return {'success': True}
    else:
        return {'success': False, 'error': result.stderr}
except Exception as e:
    return {'success': False, 'error': str(e)}
```

**JavaScript Error Handling**:
```javascript
try {
    const response = await fetch('/endpoint');
    const data = await response.json();
    if (data.success === true) {
        // Success
    } else {
        alert('Feil: ' + data.error);
    }
} catch (error) {
    alert('Feil: ' + error.message);
}
```

## Performance og Optimalisering

### Latency Breakdown (typisk)

| Komponent | Latency | Optimalisering |
|-----------|---------|----------------|
| Wake Word Detection | <100ms | Offline (Porcupine) |
| Speech-to-Text | 1-2s | Azure streaming |
| ChatGPT Response | 2-5s | Avhenger av modell og lengde |
| Text-to-Speech | 1-2s | Azure neural |
| Total (wake → første ord) | 4-9s | Kan ikke reduseres mye |

### Memory Usage

- chatgpt_voice.py: ~200-300 MB (inkl. Porcupine engine)
- duck-control.py: ~20-30 MB (minimal HTTP server)
- Total: ~250-350 MB

### CPU Usage

- Idle (wake word): 5-10%
- Active conversation: 20-40%
- Audio processing: 30-50%

### Storage

- Porcupine models: ~1-2 MB
- Python packages: ~500 MB
- Logs (rotert): max 100 MB

## Skalering og Utvidelser

### Mulige utvidelser

1. **Multi-bruker support**: Session-basert web-panel
2. **Lokalbaserte modeller**: Whisper for STT, lokal LLM
3. **Custom wake words**: Porcupine eller Snowboy
4. **MQTT integration**: IoT-kontroll
5. **Database logging**: SQLite for samtalehistorikk
6. **WebSocket live updates**: Real-time status uten polling
7. **Docker deployment**: Containerisert deployment
8. **Multi-room audio**: Snapcast eller PulseAudio

### Ytterligere hardware

- **LCD display**: Status-visning uten web
- **Knapper**: Physical control (GPIO)
- **Flere servos**: Øyne, hode-bevegelse
- **Kamera**: Computer vision integration

## Hardware Arkitektur

### Strømforsyning

**Raspberry Pi:**
- Offisiell 5V/5A USB-C strømforsyning
- Forbruker: ~3-5W (idle til full load)

**PCA9685 og Servo (USB-C PD-trigger løsning):**
- **USB-C PD-trigger** med avklippet USB-C kabel koblet til Pi
- PD-trigger leverer stabil 5V til PCA9685 V+ pin
- PCA9685 VCC (logikk) koblet til Pi 3.3V
- Felles ground mellom Pi, PD-trigger og PCA9685
- **Hvorfor PD-trigger?** Servos kan trekke 1-2A under bevegelse, nok til å reboote Pi hvis strømmen trekkes fra Pi's 5V pin
- **Fordeler**: Kompakt, pålitelig, ingen eksterne strømforsyninger nødvendig

### GPIO Bruk

**I2C (PCA9685 servo-kontroller):**
- GPIO2 (SDA)
- GPIO3 (SCL)

**I2S (MAX98357A audio):**
- GPIO18 (BCLK)
- GPIO19 (LRCK)
- GPIO21 (DIN)

**RGB LED:**
- GPIO17 (Rød)
- GPIO27 (Grønn)
- GPIO22 (Blå)

**Totalt:** 8 GPIO pins brukt

## Debugging og Logging

### Systematiske debugging

```bash
# Service status
sudo systemctl status chatgpt-duck.service
sudo systemctl status duck-control.service

# Live logs
sudo journalctl -u chatgpt-duck.service -f
sudo journalctl -u duck-control.service -f

# Sjekk tmp-filer
cat /tmp/duck_*.txt

# GPIO test
python3 -c "from gpiozero import LED; led = LED(17); led.on()"

# Audio test
speaker-test -t wav -c 2

# Nettverk
curl http://localhost:3000/duck-status
```

### Common Issues

| Problem | Diagnose | Løsning |
|---------|----------|---------|
| No wake word detection | Porcupine model missing | Check .ppn files |
| No audio output | Wrong audio device | Configure ALSA |
| Servo jittering | Voltage drop | Separate power supply |
| RGB not working | Wrong GPIO pins | Check wiring |
| Web panel 404 | Service not running | `systemctl start duck-control` |
| ChatGPT errors | API key invalid | Check .env file |

## Teknologivalg - Begrunnelser

### Python som hovedspråk
- Rikt økosystem for AI/ML
- Excellent hardware support (GPIO)
- Rask prototyping

### BaseHTTPRequestHandler vs Flask/FastAPI
- Ingen eksterne avhengigheter for web-panel
- Enklere deployment
- Tilstrekkelig for våre behov

### Tmp-filer vs Database/Redis
- Enkleste IPC-metode
- Ingen ekstra services
- Atomic writes
- Lett å debugge

### Porcupine vs andre wake word engines
- Fully offline
- Gratis (ingen cloud-costs)
- God nok accuracy
- Svensk modell funker bra

### Azure Speech vs alternatives
- Høyeste kvalitet norske stemmer
- God dokumentasjon
- Reliable streaming
- Konkurransedyktige priser

### Systemd vs Docker
- Native Pi integration
- Automatic restart on failure
- Logs via journald
- Enklere å debugge

---

**Sist oppdatert**: 10. november 2025
