# ChatGPT Duck - Intelligente Anda 🦆

Et komplett AI-basert stemmeassistent-system med ChatGPT, Azure Speech Services, fysisk nebb-bevegelse, RGB LED-status og web-basert kontrollpanel.

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

## 📚 Dokumentasjon

- **[DOCUMENTATION.md](DOCUMENTATION.md)** - 📋 Oversikt over all dokumentasjon
- **[INSTALL.md](INSTALL.md)** - 🔧 Komplett installasjonsveiledning (start her!)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 🏗️ Teknisk arkitektur og design
- **[PORTS.md](PORTS.md)** - 🌐 Nettverks- og port-konfigurasjon
- **[CHANGELOG.md](CHANGELOG.md)** - 📝 Versionshistorikk og nye funksjoner

## Hovedfunksjoner

- 🎤 **Wake Word Detection**: Offline wake word (Vosk) - si "alexa" eller "ulrika"
- 💬 **ChatGPT Samtaler**: Naturlig dialog med AI-personligheter
- 🗣️ **Azure TTS**: Høykvalitets norsk talesyntese med flere stemmer
- 👄 **Synkron Nebb-bevegelse**: Servostyrt nebb som beveger seg til lyden
- 💡 **RGB LED Status**: Visuell tilbakemelding for alle systemtilstander
- 🌐 **Web Kontrollpanel**: Komplett fjernstyring via nettleser
- 📊 **Sanntids Logger**: Live systemlogger og statusovervåking
- 🔧 **Justerbar Talehastighet**: Fra treg til lynrask tale
- 🔊 **Volumkontroll**: Juster lydnivå i sanntid
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
EOF

# 4. Last ned Vosk-modell
wget https://alphacephei.com/vosk/models/vosk-model-small-sv-rhasspy-0.15.zip
unzip vosk-model-small-sv-rhasspy-0.15.zip

# 5. Installer og start services
sudo ./install-services.sh
sudo systemctl start chatgpt-duck.service
sudo systemctl start duck-control.service

# 6. Åpne kontrollpanel i nettleser
# http://<pi-ip>:3000
```

**For detaljert guide, se [INSTALL.md](INSTALL.md)**

## Maskinvare

- Raspberry Pi (testet på Pi 400 og Pi 5)
- Monk Makes RGB LED (koblet: R=GPIO17, G=GPIO27, B=GPIO22)
- Servo til nebb (koblet til f.eks. GPIO14) - **NB: Bruk separat strømforsyning til servoen!**
- Mikrofon (USB eller Pi-kompatibel)
- Høyttaler (3.5mm jack eller USB)

## Programvare - Installasjon

### 1. System-avhengigheter (før pip install)

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv portaudio19-dev libportaudio2 ffmpeg
```

### 2. Opprett virtuelt miljø

```bash
cd /home/admog/Code/MyFirst
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Installer Python-pakker

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Last ned Vosk-modell

```bash
wget https://alphacephei.com/vosk/models/vosk-model-small-sv-rhasspy-0.15.zip
unzip vosk-model-small-sv-rhasspy-0.15.zip
```

Mappen `vosk-model-small-sv-rhasspy-0.15/` skal ligge i prosjektmappen.

### 5. Opprett `.env`-fil

Opprett filen `/home/admog/Code/MyFirst/.env` med følgende innhold:

```
OPENAI_API_KEY=din_openai_nøkkel
AZURE_TTS_KEY=din_azure_tts_nøkkel
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=din_azure_stt_nøkkel
AZURE_STT_REGION=westeurope
```

**Skaff API-nøkler:**
- OpenAI: https://platform.openai.com/api-keys
- Azure Speech: https://portal.azure.com (Cognitive Services)

## Nødvendige filer

Prosjektet trenger disse Python-filene:
- `chatgpt_voice.py` (hovedprogram)
- `duck_beak.py` (servo-kontroll for nebb)
- `rgb_duck.py` (RGB LED-kontroll)

## Wake Word med Vosk

Prosjektet bruker **Vosk** for offline wake word detection (svensk modell).

**Standard wake words er "alexa" eller "ulrika"** – du kan endre dette i `wait_for_wake_word()`-funksjonen.

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
- **Talehastighet**: Juster hastighet fra treg (0%) til lynrask (100%)
  - 0%: Veldig sakte (–50% hastighet)
  - 50%: Normal hastighet
  - 100%: Dobbel hastighet (+100%)

#### 👄 Nebb-kontroll
- **På/Av**: Aktiver eller deaktiver nebb-bevegelse
- **Test**: Send testmelding for å verifisere funksjonalitet

#### 💬 Send Meldinger
Tre moduser for direkte kommunikasjon:
- **🔊 Bare si det (TTS)**: Anda leser opp meldingen uten AI-behandling
- **🤖 Send til ChatGPT (stille)**: AI svarer uten lyd
- **🎯 Full behandling**: AI svarer med tale og nebb-bevegelse

#### 📱 Nettverk
- **WiFi-nettverk**: Vis tilgjengelige nettverk
- **Hotspot-modus**: Bytt til WiFi-portal for konfigurasjon
- **System**: Reboot eller shutdown via kontrollpanel

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
sudo ./install-services.sh
```

Dette installerer:
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
python chatgpt_voice.py
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

### Vosk finner ikke modell
- Sjekk at `vosk-model-small-sv-rhasspy-0.15/` finnes i prosjektmappen
- Verifiser at mappen inneholder `am/`, `graph/`, etc.

## Tips

- Hvis LED eller Pi flikrer/rebooter: **bruk separat strøm til servoen!**
- For å endre LED-blink, juster i `rgb_duck.py`.
- For å endre wake words, endre sjekken i `wait_for_wake_word()`-funksjonen.
- Vosk støtter flere språk – last ned norsk modell (`vosk-model-small-no-0.22`) hvis du vil bruke norske wake words.

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
├── README.md
├── PORTS.md                           # Port-dokumentasjon
│
├── chatgpt_voice.py                   # Hovedapplikasjon
├── duck-control.py                    # Web kontrollpanel (HTTP server)
├── duck_beak.py                       # Servo-kontroll for nebb
├── duck_beak_gpiozero.py             # Alternativ nebb-implementering
├── rgb_duck.py                        # RGB LED-kontroll
├── oww_models.py                      # Wake word modeller
├── wifi-portal.py                     # WiFi-oppsett portal
│
├── chatgpt-duck.service               # Systemd service for hovedapp
├── duck-control.service               # Systemd service for kontrollpanel
├── auto-hotspot.service               # Systemd service for WiFi hotspot
├── install-services.sh                # Installasjonsskript for services
│
├── duck.sh                            # Start-skript
├── emergency-stop.sh                  # Nødstopp-skript
├── wifi-setup.sh                      # WiFi-konfigurasjonsskript
├── wait-for-network.sh               # Nettverks-wait helper
├── auto-hotspot.sh                    # Hotspot-oppstartsskript
│
├── test/                              # Test-filer
├── test_beak_amplitude.py            # Test nebb-amplitude
├── test-boot-sequence.sh             # Test boot-sekvens
├── test-hotspot.sh                   # Test hotspot
│
├── Quack-quack.ppn                   # Porcupine wake word modell
└── vosk-model-small-sv-rhasspy-0.15/ # Vosk svensk modell
    ├── README
    ├── am/                            # Akustisk modell
    ├── conf/                          # Konfigurasjon
    ├── graph/                         # Språkmodell
    └── ivector/                       # i-vector ekstraktor
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