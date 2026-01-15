# ChatGPT Duck - Intelligente Anda 🦆

Et komplett AI-basert stemmeassistent-system med ChatGPT, Azure Speech Services, fysisk nebb-bevegelse, RGB LED-status og web-basert kontrollpanel.

[![Version](https://img.shields.io/badge/version-2.1.2-blue.svg)](docs/CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

**[English documentation](docs/README_EN.md)** | **[Norsk dokumentasjon](README.md)**

## 📚 Dokumentasjon

- **[DOCUMENTATION.md](docs/DOCUMENTATION.md)** - 📋 Oversikt over all dokumentasjon
- **[INSTALL.md](docs/INSTALL.md)** - 🔧 Komplett installasjonsveiledning (start her!)
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 🏗️ Teknisk arkitektur og design
- **[PORTS.md](docs/PORTS.md)** - 🌐 Nettverks- og port-konfigurasjon
- **[CHANGELOG.md](docs/CHANGELOG.md)** - 📝 Versionshistorikk og nye funksjoner
- **[MEMORY_SYSTEM.md](docs/MEMORY_SYSTEM.md)** - 🧠 Persistent minnessystem

## Hovedfunksjoner

- 🎤 **Wake Word Detection**: Porcupine wake word - si "Samantha"
- 💬 **ChatGPT Samtaler**: Naturlig dialog med AI-personligheter
- 🗣️ **Azure TTS**: Høykvalitets norsk talesyntese med flere stemmer
- 👄 **Synkron Nebb-bevegelse**: Servostyrt nebb som beveger seg til lyden
- 🎵 **Sang-avspilling**: Anda kan synge med synkronisert nebb og LED-pulsing
- 🌤️ **Værmelding**: Live værdata fra yr.no for hele Norge
- ⏰ **Dato og tid**: Anda vet alltid hva klokka er og hvilken dato det er
- 💡 **Philips Hue**: Styr smarte lys med stemmen (på/av, dimming, 8 farger)
- 🔴 **RGB LED Status**: Visuell tilbakemelding for alle systemtilstander
- 🌐 **Web Kontrollpanel**: Komplett fjernstyring via nettleser
- 📊 **Sanntids Logger**: Live systemlogger og statusovervåking
- 🔧 **Justerbar Talehastighet**: Fra treg til lynrask tale
- 🔊 **Volumkontroll**: Juster lydnivå i sanntid
- 🌀 **Automatisk Viftekontroll**: Temperaturbasert kjøling med manuell overstyring
- 🎭 **Flere Personligheter**: Velg mellom ulike AI-personligheter
- 📱 **WiFi Portal**: Innebygd WiFi-oppsett for enkel konfigurasjon

## ⚡ Quick Start

```bash
# 1. Installer system-pakker
sudo apt-get update && sudo apt-get install -y python3-pip python3-venv portaudio19-dev ffmpeg

# 2. Klon og sett opp
git clone https://github.com/Osmund/chatgpt-and.git
cd chatgpt-and
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Opprett .env med API-nøkler
cat > .env << EOF
OPENAI_API_KEY=sk-your-key
AZURE_TTS_KEY=your-key
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=your-key
AZURE_STT_REGION=westeurope
PICOVOICE_API_KEY=your-picovoice-key
EOF

# 4. Installer og start services
sudo ./scripts/install-services.sh
sudo systemctl start chatgpt-duck.service
sudo systemctl start duck-control.service

# 6. Åpne kontrollpanel i nettleser
# http://<pi-ip>:3000
```

**For detaljert guide, se [INSTALL.md](docs/INSTALL.md)**

## Maskinvare

- Raspberry Pi (testet på Pi 400 og Pi 5)
- Monk Makes RGB LED (koblet: R=GPIO17, G=GPIO27, B=GPIO22)
- USB-C PD-trigger med avklippet USB-C kabel koblet til Pi
- PCA9685 servo-kontroller (koblet til PD-trigger for 5V strøm)
- Servo til nebb (koblet til PCA9685 kanal 0) - **NB: Strøm fra PD-trigger, ikke Pi!**
- Mikrofon (USB eller Pi-kompatibel)
- Høyttaler (3.5mm jack eller USB)

## Hardware & software endringer (Pi 5 / MAX98357A) - 2025-11-11

Dette prosjektet er oppdatert for Raspberry Pi 5 og for bruk med en
MAX98357A I2S Class-D forsterker. Under er kortfattede instruksjoner og
forklaringer på valg og endringer som er gjort under utvikling.

Maskinvare (anbefalt kobling)
- MAX98357A (I2S mono amp):
  - VCC -> 5V eller 3.3V avhengig av board (sjekk din modul)
  - GND -> GND
  - DIN -> GPIO21 (PCM_DOUT / I2S Data)
  - BCLK -> GPIO18 (PCM_CLK / Bit Clock)
  - LRCK/WS (LRCLK) -> GPIO19 (PCM_FS / Word Select)
  - SD (shutdown / enable) -> Koble til fast 3.3V (pin 1 eller 17) for "alltid på",
    alternativt kan SD styres fra en GPIO hvis du vil slå forsterkeren av mellom avspillinger.
  - GAIN -> Koble til GND for lavere forsterkning (9dB) hvis pop eller forvrengning
    er et problem (standard er 15dB når GAIN flyter eller er til VCC).

  Notat: Koble GAIN til GND reduserer forsterkning og ofte reduserer start/stop-pop
  merkbart. Hvis du opplever gjenstående pop, vurder en DC-blocking kondensator
  mellom høyttalerutganger (SPK+/SPK-) eller bytt til en DAC/amp med innebygd
  pop-suppression.

- PCA9685 servo driver (beak servo):
  - I2C SDA -> GPIO2
  - I2C SCL -> GPIO3
  - Servo signal -> valgt kanal (default kanal 0 i `duck_beak.py`)
  - VCC (logikk) -> 3.3V fra Pi
  - V+ (servo strøm) -> 5V fra USB-C PD-trigger
  - **Viktig**: USB-C PD-trigger med avklippet kabel gir stabil 5V til servokontrolleren
  - Dette unngår at servoen trekker strøm direkte fra Pi'en (forhindrer reboots)

Software / kodeendringer
- `duck_beak.py`:
  - Migrert fra pigpio til `adafruit_servokit` som snakker til en PCA9685 over I2C.
  - Konfigurasjon: `SERVO_CHANNEL`, `CLOSE_DEG`, `OPEN_DEG`, og pulse width range
    (`CLOSE_US_DEFAULT` / `OPEN_US_DEFAULT`) finnes i toppen av filen for enkel kalibrering.

- `chatgpt_voice.py` (hovedorchestrator):
  - Importerer og bruker moduler fra `src/` mappen
  - Støtter I2S (Google Voice HAT / MAX98357A)
  - TTS, wake word, AI-integrasjon håndteres av moduler
    og sett ALSA Master (~70%) for best kombinasjon av lydnivå og lav forvrengning.
  - Hvis du vil gjøre videre feilsøking: sjekk `journalctl -u chatgpt-duck.service` og
    `alsamixer -c 1`.

ALSA / lydoppsett
- En anbefalt `.asoundrc` er lagt inn for å bruke softvol + dmix og S32_LE format
  for Google Voice HAT. Hvis du bytter til USB-lyd, oppdater `pcm`-innstillingene
  eller la `aplay -l` / `sd.query_devices()` vise devices.

Råd for minimal størrelse (inn i lekeand)
- MAX98357A er kompakt og fortsatt det beste alternativet når plass er kritisk.
- Hvis du vil eliminere pop helt, vurder en DAC/HAT med pop-suppression
  (f.eks. HifiBerry / PCM5102A-baserte moduler), men de tar mer plass og/eller
  krever ekstra strømforsyning.

Feilsøking / tips
- Hvis du hører pop etter disse endringene, prøv i denne rekkefølgen:
  1. Koble `GAIN` til GND (gjort)
  2. Sett ALSA Master til ~70%: `amixer -c 1 sset Master 70%`
  3. Hvis pop fortsatt er plagsomt: legg til en DC-blocking kondensator (100–1000µF
     ikke-polarisert) mellom SPK+ og SPK- eller bytt til en DAC med innebygd pop-suppression.

Hvor i koden finner du dette?
- `duck_beak.py` - servo & PCA9685
- `chatgpt_voice.py` - hovedorchestrator
- `src/` moduler - alle kjernefunksjoner (TTS, wake-word, AI, minne, etc.)

Hvis du ønsker, kan jeg også:
- Lage en liten pinout-skisse for plassering internt i anden
- Flytte lyd til et USB-lydkort (ingen GPIO brukt) hvis du får plass


## Programvare - Installasjon

### 1. System-avhengigheter (før pip install)

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv portaudio19-dev libportaudio2 ffmpeg
```

### 2. Opprett virtuelt miljø

```bash
cd /home/admog/Code/chatgpt-and
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Installer Python-pakker

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Opprett `.env`-fil

Opprett filen `/home/admog/Code/chatgpt-and/.env` med følgende innhold:

```
OPENAI_API_KEY=din_openai_nøkkel
AZURE_TTS_KEY=din_azure_tts_nøkkel
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=din_azure_stt_nøkkel
AZURE_STT_REGION=westeurope
PICOVOICE_API_KEY=din_picovoice_nøkkel
```

**Skaff API-nøkler:**
- OpenAI: https://platform.openai.com/api-keys
- Azure Speech: https://portal.azure.com (Cognitive Services)
- Picovoice: https://console.picovoice.ai/ (gratis)

## Nødvendige filer

Prosjektet trenger disse Python-filene:
- `chatgpt_voice.py` (hovedprogram)
- `duck_beak.py` (servo-kontroll for nebb)
- `rgb_duck.py` (RGB LED-kontroll)

## Wake Word med Porcupine

Prosjektet bruker **Porcupine** fra Picovoice for offline wake word detection.

**Standard wake word er "Samantha"** (definert i `samantha_en_raspberry-pi_v4_0_0.ppn`). Du kan laste ned andre wake words fra [Picovoice Console](https://console.picovoice.ai/).

## Web Kontrollpanel

Systemet inkluderer et komplett web-basert kontrollpanel tilgjengelig på `http://<raspberry-pi-ip>:3000`

### Funksjoner i Kontrollpanelet

#### 🎮 Service-kontroll
- **Start/Stopp/Restart**: Full kontroll over duck-servicen
- **Sanntids Status**: Automatisk oppdatering hvert 5. sekund
- **Logger**: Live visning av systemlogger med fargekodet output

#### 🤖 AI-konfigurasjon
- **Modellvalg**: Velg mellom ChatGPT-modeller
  - `gpt-3.5-turbo` (rask, billig)
  - `gpt-4` (smartere, dyrere)
  - `gpt-4-turbo` (balanse)
- **Personligheter**: 
  - Normal (balansert og høflig)
  - Entusiastisk (energisk og positiv)
  - Filosofisk (reflekterende og dyp)
  - Humoristisk (morsom og spøkefull)
  - Kort (konsise svar)

#### 🗣️ Stemme og Lyd
- **Stemmevalg**: Velg Azure TTS stemme
  - `nb-NO-FinnNeural` (mann, dyp stemme)
  - `nb-NO-PernilleNeural` (kvinne, klar stemme)
  - `nb-NO-IselinNeural` (kvinne, varm stemme)
- **Volumkontroll**: Juster lydnivå 0-100% i sanntid
  - 0%: Stille (ingen lyd)
  - 50%: Normal lydstyrke (gain 1.0)
  - 100%: Dobbelt lydstyrke (gain 2.0)
  - Slideren viser live prosent-visning mens du justerer
  - Volumet anvendes direkte på lydsamplene før avspilling
- **Talehastighet**: Juster hastighet fra treg (0%) til lynrask (100%)
  - 0%: Veldig sakte (–50% hastighet)
  - 50%: Normal hastighet
  - 100%: Dobbel hastighet (+100%)

#### 👄 Nebb-kontroll
- **På/Av**: Aktiver eller deaktiver nebb-bevegelse
- **Test**: Send testmelding for å verifisere funksjonalitet

#### 🌀 Viftekontroll
- **Automatisk modus**: Starter vifte ved 55°C, stopper ved 50°C
- **Manuell overstyring**: Tving vifte på eller av
- **Sanntids temperaturvisning**: Fargekodet (grønn < 55°C, orange < 60°C, rød ≥ 60°C)
- **Live status**: Se om vifta går akkurat nå

#### 💬 Send Meldinger
Tre moduser for direkte kommunikasjon:
- **🔊 Bare si det (TTS)**: Anda leser opp meldingen uten AI-behandling
- **🤖 Send til ChatGPT (stille)**: AI svarer uten lyd
- **🎯 Full behandling**: AI svarer med tale og nebb-bevegelse

#### 📱 Nettverk
- **WiFi-nettverk**: Vis tilgjengelige nettverk
- **Hotspot-modus**: Bytt til WiFi-portal for konfigurasjon
- **System**: Reboot eller shutdown via kontrollpanel

## Oppstartsmelding

Ved oppstart annonserer anda sin IP-adresse hvis nettverket er tilgjengelig:
- **Med nettverk**: "Kvakk kvakk! Jeg er nå klar for andeprat. Min IP-adresse er [IP]. Du finner kontrollpanelet på port 3000. Si navnet mitt for å starte en samtale!"
- **Uten nettverk**: "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"

Anda forsøker å koble til nettverket i opptil 10 sekunder før den gir opp og annonserer at den ikke har tilkobling.

## RGB LED Status-indikatorer

RGB LED-en gir visuell tilbakemelding for alle systemtilstander:

| Farge | Betydning |
|-------|-----------|
| 🔵 Blå | Venter på wake word ("alexa" eller "ulrika") |
| 🟢 Grønn | Lytter - snakk nå! |
| 🟡 Gul blinkende | Sender til Azure Speech Recognition |
| 🟣 Lilla blinkende | Venter på ChatGPT-respons |
| 🔴 Rød | Anda snakker (TTS aktiv) |
| ⚪ Av | Idle/hvile-modus |

## Stemmekommandoer

- **"alexa"** eller **"ulrika"**: Aktiver anda (wake word)
- **"stopp"** eller **"takk"**: Avslutt samtale og gå tilbake til wake word-modus
- Snakk naturlig - anda forstår kontekst og kan føre lengre samtaler

## Systemd Services

Prosjektet kjører som systemd-services for automatisk oppstart og administrasjon.

### Installer Services

```bash
cd /home/admog/Code/chatgpt-and
sudo ./scripts/install-services.sh
```

This installerer:
- `chatgpt-duck.service` - Hovedapplikasjonen (port: standard lyd)
- `duck-control.service` - Web kontrollpanel (port: 3000)
- `auto-hotspot.service` - WiFi hotspot ved behov

### Service-kommandoer

```bash
# Start services
sudo systemctl start chatgpt-duck.service
sudo systemctl start duck-control.service

# Stopp services
sudo systemctl stop chatgpt-duck.service
sudo systemctl stop duck-control.service

# Restart
sudo systemctl restart chatgpt-duck.service

# Se status
sudo systemctl status chatgpt-duck.service

# Se logger
sudo journalctl -u chatgpt-duck.service -f
sudo journalctl -u duck-control.service -f

# Aktiver automatisk oppstart ved boot
sudo systemctl enable chatgpt-duck.service
sudo systemctl enable duck-control.service
```

## Kjøring

### Via Systemd (anbefalt)
```bash
sudo systemctl start chatgpt-duck.service
sudo systemctl start duck-control.service
```

Åpne kontrollpanel i nettleser: `http://<raspberry-pi-ip>:3000`

### Manuell kjøring (for testing)
```bash
source .venv/bin/activate
python3 chatgpt_voice.py
```

### Kjør kontrollpanel separat
```bash
python duck-control.py
```

## Feilsøking

### Portaudio-feil
```bash
sudo apt-get install portaudio19-dev libportaudio2
pip install --upgrade pyaudio
```

### GPIO-advarsler
```bash
pip install lgpio
```

### Ingen lyd
- Sjekk `alsamixer` (kjør i terminal)
- Test høyttaler: `speaker-test -t wav -c 2`
- Sjekk mikrofon: `arecord -l`

### Porcupine finner ikke wake word model
- Sjekk at `.ppn` filer finnes i `porcupine/` mappen
- Verifiser at mappen inneholder `am/`, `graph/`, etc.

## Tips

- Hvis LED eller Pi flikrer/rebooter: **bruk separat strøm til servoen!**
- For å endre LED-blink, juster i `rgb_duck.py`.
- For å endre wake words, endre sjekken i `wait_for_wake_word()`-funksjonen.
- Porcupine støtter flere språk – last ned custom wake words fra [Picovoice Console](https://console.picovoice.ai/) hvis du vil bruke andre ord.

## Arkitektur og Kommunikasjon

### Inter-Process Communication (IPC)
Systemet bruker tmp-filer for kommunikasjon mellom kontrollpanel og hovedapplikasjon:

| Fil | Formål | Verdier |
|-----|--------|---------|
| `/tmp/duck_personality.txt` | AI-personlighet | normal, entusiastic, philosophical, humorous, concise |
| `/tmp/duck_voice.txt` | Azure TTS stemme | nb-NO-FinnNeural, nb-NO-PernilleNeural, nb-NO-IselinNeural |
| `/tmp/duck_volume.txt` | Lydvolum | 0-100 |
| `/tmp/duck_beak.txt` | Nebb-bevegelse | on, off |
| `/tmp/duck_speed.txt` | Talehastighet | 0-100 (0=treg, 50=normal, 100=rask) |
| `/tmp/duck_model.txt` | ChatGPT-modell | gpt-3.5-turbo, gpt-4, gpt-4-turbo |
| `/tmp/duck_message.txt` | Direktemeldinger | Tekst som skal behandles |
| `/tmp/duck_fan.txt` | Viftemodus | auto, on, off |
| `/tmp/duck_fan_status.txt` | Viftestatus | mode\|running\|temp (f.eks. auto\|True\|62.3) |

### API Endpoints (duck-control.py)

#### GET Endpoints
- `/` - Hovedside med kontrollpanel
- `/duck-status` - Service running status (JSON)
- `/status` - Alle gjeldende innstillinger (JSON)
- `/logs` - Systemlogger (journalctl output)
- `/current-model` - Gjeldende AI-modell
- `/current-personality` - Gjeldende personlighet
- `/current-voice` - Gjeldende stemme
- `/current-volume` - Gjeldende volum
- `/current-beak` - Gjeldende nebb-status
- `/current-speed` - Gjeldende talehastighet
- `/wifi-networks` - Tilgjengelige WiFi-nettverk (nmcli scan)

#### POST Endpoints
- `/control` - Start/stopp/restart service
- `/test-beak` - Test nebb-bevegelse
- `/change-model` - Bytt AI-modell
- `/change-personality` - Bytt personlighet
- `/change-voice` - Bytt stemme
- `/change-volume` - Endre volum
- `/change-beak` - Aktiver/deaktiver nebb
- `/change-speed` - Endre talehastighet
- `/set-fan-mode` - Endre viftemodus (auto/on/off)
- `/fan-status` - Hent viftestatus og temperatur
- `/speak` - Send melding (kun TTS)
- `/ask` - Send til ChatGPT (stille)
- `/full-response` - Send med full behandling (AI + TTS + nebb)
- `/start-portal` - Start WiFi-portal
- `/reboot` - Reboot system
- `/shutdown` - Shutdown system

## Talehastighet-implementering

Talehastigheten kontrolleres via Azure TTS SSML `rate`-parameter:

```python
# Mapping: slider 0-100 til Azure rate
if speed_value < 50:
    # 0-49: Sakte (x-slow til normal)
    rate_percent = (speed_value - 50)  # -50% til 0%
else:
    # 50-100: Rask (normal til x-fast)
    rate_percent = (speed_value - 50) * 2  # 0% til +100%

ssml = f"""
<speak version='1.0' xml:lang='nb-NO'>
    <voice name='{voice}'>
        <prosody rate='{rate_percent:+d}%'>
            {text}
        </prosody>
    </voice>
</speak>
"""
```

## Komplett filstruktur

```
/home/admog/Code/chatgpt-and/
├── .venv/                              # Python virtual environment
├── .env                                # API-nøkler (IKKE commit til git!)
├── .gitignore
├── requirements.txt                    # Python dependencies
├── README.md                           # Denne filen
│
├── docs/                               # 📚 Dokumentasjon
│   ├── ARCHITECTURE.md                # Teknisk arkitektur
│   ├── CHANGELOG.md                   # Versionshistorikk
│   ├── DOCUMENTATION.md               # Dokumentasjonsoversikt
│   ├── INSTALL.md                     # Installasjonsveiledning
│   ├── MEMORY_SYSTEM.md               # Minnessystem dokumentasjon
│   ├── PINOUT.md                      # Pin-konfigurasjon
│   ├── PORTS.md                       # Port-dokumentasjon
│   └── README_EN.md                   # Engelsk README
│
├── scripts/                            # 🔧 Shell scripts
│   ├── auto-hotspot.sh                # WiFi hotspot
│   ├── duck.sh                        # Start-skript
│   ├── emergency-stop.sh              # Nødstopp
│   ├── install-services.sh            # Service installasjon
│   ├── setup_max98357a.sh             # Audio setup
│   ├── wait-for-network.sh            # Network wait helper
│   └── wifi-setup.sh                  # WiFi konfigurasjon
│
├── tests/                              # 🧪 Test-filer
│   ├── test                           # Test-skript
│   ├── test_beak_amplitude.py         # Nebb amplitude test
│   ├── test_servo.py                  # Servo test
│   ├── test-boot-sequence.sh          # Boot sekvens test
│   └── test-hotspot.sh                # Hotspot test
│
├── services/                           # ⚙️ Systemd services
│   ├── auto-hotspot.service           # WiFi hotspot service
│   ├── chatgpt-duck.service           # Hovedapplikasjon
│   ├── duck-control.service           # Web kontrollpanel
│   ├── duck-memory-hygiene.service    # Memory maintenance
│   ├── duck-memory-hygiene.timer      # Memory maintenance timer
│   ├── duck-memory-worker.service     # Memory worker
│   └── fan-control.service            # Viftekontroll
│
├── src/                               # 📦 Kildekode moduler
│   ├── duck_ai.py                     # 🤖 ChatGPT integrasjon og verktøy
│   ├── duck_audio.py                  # 🔊 TTS og lydavspilling
│   ├── duck_config.py                 # ⚙️ Konfigurasjon og konstanter
│   ├── duck_conversation.py           # 💬 Samtaleflyt og brukerhåndtering
│   ├── duck_memory.py                 # 🧠 Memory manager
│   ├── duck_memory_hygiene.py         # 🧠 Memory hygiene
│   ├── duck_memory_worker.py          # 🧠 Memory worker
│   ├── duck_music.py                  # 🎵 Musikkavspilling
│   ├── duck_speech.py                 # 🎤 Wake word og talegjenkjenning
│   └── duck_user_manager.py           # 👥 Brukerhåndtering
│
├── chatgpt_voice.py                   # 🦆 Hovedapplikasjon (entry point)
├── duck-control.py                    # 🌐 Web kontrollpanel (HTTP server)
├── duck_beak.py                       # 👄 Servo-kontroll for nebb
├── fan_control.py                     # 🌀 Viftekontroll
├── rgb_duck.py                        # 💡 RGB LED-kontroll
├── wifi-portal.py                     # 📱 WiFi-oppsett portal
│
├── Quack-quack.ppn                    # 🎤 Porcupine wake word modell
├── porcupine/                         # 🎤 Porcupine wake word models
│   └── samantha_en_raspberry-pi_v4_0_0.ppn
│       ├── README
│       ├── am/                        # Akustisk modell
│       ├── conf/                      # Konfigurasjon
│       ├── graph/                     # Språkmodell
│       └── ivector/                   # i-vector ekstraktor
│
├── musikk/                            # 🎵 Musikkfiler
└── vosk-model-small-sv-rhasspy-0.15/ # 🎤 Vosk modell
```

## Systemkrav

### Hardware
- **Raspberry Pi**: Pi 4, Pi 5, eller Pi 400 (minimum 2GB RAM)
- **Mikrofon**: USB mikrofon eller HAT med mikrofon
- **Høyttaler**: 3.5mm jack, HDMI, eller USB høyttaler
- **RGB LED**: Monk Makes RGB LED eller lignende (GPIO 17, 27, 22)
- **Servo**: SG90 eller lignende 5V servo til nebb (GPIO 14)
- **Strømforsyning**: 
  - 5V/3A til Raspberry Pi
  - **Separat 5V strøm til servo** (viktig for stabilitet!)

### Software
- **OS**: Raspberry Pi OS (Bookworm eller nyere)
- **Python**: 3.9 eller nyere
- **Systemd**: For service-administrasjon
- **NetworkManager**: For WiFi-administrasjon

### Nettverkskrav
- Internett-tilkobling (for ChatGPT og Azure APIs)
- Port 3000 åpen for web kontrollpanel

### API-nøkler (påkrevd)
- **OpenAI API Key**: For ChatGPT (https://platform.openai.com/api-keys)
- **Azure Speech Service**: For TTS og STT (https://portal.azure.com)
  - Region: Anbefalt `westeurope` eller `northeurope`
  - Både Speech-to-Text og Text-to-Speech må være aktivert

---

**God andeprat! 🦆💬**