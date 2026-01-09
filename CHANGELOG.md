# Changelog

Alle viktige endringer i ChatGPT Duck-prosjektet dokumenteres her.

Formatet er basert på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.1.2] - 2026-01-09

### Ny funksjonalitet

#### 🌤️ Værmelding fra yr.no

**Beskrivelse**: Anda kan nå svare på spørsmål om været ved å hente live data fra yr.no (Meteorologisk institutt).

**Funksjoner**:
- **Automatisk stedsgjenkjenning**: Spør om været i en spesifikk by
- **Nåværende temperatur**: Henter live temperatur fra yr.no
- **Værbeskrivelse**: Beskriver nåværende vær (f.eks. "klarvær", "lett regn")
- **Prognose**: Viser temperatur utover dagen (neste 12 timer)
- **Intelligent dialog**: Hvis du ikke nevner sted, spør anda hvor du lurer på været

**Eksempler**:
- "Hva er været i Sokndal?"
- "Hvor varmt er det i Oslo nå?"
- "Hvordan blir været i Bergen i dag?"
- "Hva er været?" → Anda spør: "Hvor vil du vite været?"

**Teknisk implementering**:
- **OpenAI Function Calling**: ChatGPT bestemmer når den skal hente værdata
- **Nominatim geocoding**: Konverterer stedsnavn til koordinater (OpenStreetMap)
- **MET Norway API**: locationforecast/2.0 for værdata
- **Norsk oversettelse**: Symbolkoder oversettes automatisk til norsk

**Resultat**: Anda gir nøyaktige værmeldinger for hele Norge! 🌦️☀️

#### ⏰ Dato og Tid Bevissthet

**Beskrivelse**: ChatGPT kan nå svare på spørsmål om nåværende dato og tid ved å lese fra systemklokka.

**Funksjoner**:
- **Automatisk dato/tid injeksjon**: System prompt inkluderer alltid nåværende dato og tid
- **Norsk formatering**: "Torsdag 9. Januar 2026, klokken 11:53"
- **Naturlig dialog**: Anda kan svare på spørsmål som:
  - "Hva er klokka?"
  - "Hvilken dato er det?"
  - "Hvilken dag er det i dag?"
  - "Hvor lenge til midnatt?"

**Teknisk implementering**:
- `datetime.now()` henter systemtid ved hver ChatGPT-forespørsel
- Formateres med `strftime('%A %d. %B %Y, klokken %H:%M')`
- Legges til i system prompt før personlighet
- Implementert i både `chatgpt_voice.py` og `duck-control.py`

**Resultat**: Anda vet alltid nøyaktig hvilken dato og tid det er! 🕐📅

#### 🎵 Sang-avspilling med Nebb og LED Synkronisering

**Beskrivelse**: Anda kan nå synge sanger med synkronisert nebb-bevegelse og LED-pulsing!

**Funksjoner**:
- **Dual-file system**:
  - `duck_mix.wav`: Full mix av sang for avspilling
  - `vocals_duck.wav`: Isolert vokal-track for nebb-synkronisering
- **LED-pulsing**: LED pulser i takt med musikkens amplitude
- **Nebb-synkronisering**: Nebbet følger vokalens amplitude i sangtid
- **Artist/tittel-annonsering**: Anda sier artist og sangtittel før avspilling
- **Stereo/mono auto-detection**: Håndterer automatisk forskjellige audioformater
- **Sanntids synkronisering**: Progressbasert synkronisering av nebb og LED
- **Web-kontroll**: Start og stopp sanger via kontrollpanelet

**Teknisk implementering**:
- Separate threads for playback, LED-kontroll og nebb-kontroll
- Progressbasert mapping: `vocals_pos = (mix_idx / total_frames) * vocals_length`
- LED konverterer stereo til mono for amplitude-deteksjon
- Chunk size: 30ms (BEAK_CHUNK_MS) for smooth bevegelse
- IPC via `/tmp/duck_song_request.txt` og `/tmp/duck_song_stop.txt`

**Sangtilgang**: Web-kontrollpanel viser liste over alle tilgjengelige sanger i `musikk/` mappen.

**Resultat**: Anda synger med perfekt synkronisert nebb og pulserende LED!

### Forbedringer

#### 🎤 Audio Resampling for Porcupine

**Beskrivelse**: Implementert audio resampling for å håndtere forskjell mellom USB-mikrofon (48kHz) og Porcupine (16kHz).

**Endringer**:
- **scipy.signal.resample**: Konverterer 48000 Hz → 16000 Hz (3:1 ratio)
- **Buffer-størrelse**: 6144 samples (4x Porcupine frame length)
- **Stabilitetsgevinst**: Reduserer buffer overflow problemer
- **Logging**: Viser resampling-detaljer ved oppstart

**Resultat**: Porcupine wake word detection fungerer stabilt med USB-mikrofoner.

#### 🔇 Buffer Overflow Håndtering

**Beskrivelse**: Undertrykt buffer overflow advarsler som ikke påvirker funksjonalitet.

**Endringer**:
- Økt buffer-størrelse fra 1536 til 6144 samples
- Undertrykt PortAudio overflow warnings (`err_code = -9981`)
- Logging kun hvis ikke overflow (unngår logg-spam)

**Resultat**: Renere logger uten funksjonalitetstap.

#### 🎨 Stereo/Mono Auto-Detection

**Beskrivelse**: Automatisk håndtering av stereo og mono audio-filer.

**Endringer**:
- Detekterer antall kanaler i mix og vocals
- Åpner OutputStream med korrekt antall kanaler
- Konverterer vocals til mono for amplitude-deteksjon
- Konverterer mix til mono for LED-kontroll

**Resultat**: Sanger spilles med korrekt hastighet uavhengig av format.

### Dokumentasjonsoppdateringer

- **ARCHITECTURE.md**: Dokumentert sang-avspilling arkitektur
- **DOCUMENTATION.md**: Oppdatert statistikk og sist oppdatert dato
- **requirements.txt**: Lagt til scipy for resampling
- **README.md**: Dokumentert sang-funksjonalitet

## [2.1.1] - 2026-01-06

### Forbedringer

#### 🎤 Wake Word-teknologi Oppgradering

**Beskrivelse**: Byttet fra Vosk til Porcupine for mer pålitelig wake word-deteksjon.

**Endringer**:
- **Wake word endret**: Fra "Anda" til "Samantha"
- **Engine**: Picovoice Porcupine (erstatter Vosk)
- **Fordeler**:
  - Mer pålitelig deteksjon av wake word
  - Lavere CPU-bruk
  - Raskere responstid
  - Bedre støyreduksjon
- **Konfigurasjon**: Krever Picovoice API-nøkkel i `.env`
- **Uttale**: "Samantha" er lettere å gjenkjenne enn "Anda"

**Si "Samantha" for å starte en samtale!**

#### 🌐 Nettverksdeteksjon ved Oppstart

**Beskrivelse**: Anda annonserer nå tydeligere hvis den ikke klarer å koble til nettverket ved oppstart.

**Endringer**:
- Oppdatert oppstartsmelding når nettverket ikke er tilgjengelig
- **Gammel melding**: "Kvakk kvakk! Jeg er nå klar for andeprat. Nettverket er ikke tilgjengelig ennå, men jeg kan fortsatt snakke med deg."
- **Ny melding**: "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"
- Prøver å koble til nettverket i opptil 10 sekunder (5 forsøk × 2 sekunder)
- Gir tydeligere brukertilbakemelding om nettverksproblemer

#### 📚 Dokumentasjonsoppdateringer

**USB-C PD-trigger dokumentasjon**:
- Dokumentert bruken av USB-C PD-trigger med avklippet USB-C kabel for servo-strøm
- PCA9685 servo-kontroller kobles til PD-trigger for å få 5V strøm
- Dette unngår at servoen trekker strøm direkte fra Pi'en (forhindrer reboots)
- Oppdatert dokumentasjon i:
  - **README.md**: Hardware-seksjon og oppsett-diagram
  - **PINOUT.md**: Detaljert PD-trigger tilkoblings-informasjon
  - **INSTALL.md**: Installasjonsveiledning med PD-trigger oppsett
  - **ARCHITECTURE.md**: Hardware-arkitektur og strømforsyning
  - **DOCUMENTATION.md**: Søkeindeks oppdatert

**Fordeler med PD-trigger**:
- Kompakt løsning for servo-strøm
- Stabil 5V output
- Ingen eksterne strømforsyninger nødvendig
- Perfekt for integrasjon i lekeand

## [2.1.0] - 2025-11-11

### Ny funksjonalitet

#### 🌀 Automatisk Viftekontroll

**Beskrivelse**: Intelligent temperaturbasert kjøling for Raspberry Pi med 5V vifte på GPIO 13.

**Funksjoner**:
- **Automatisk modus**: 
  - Starter vifte når CPU-temperatur ≥ 55°C
  - Stopper vifte når CPU-temperatur ≤ 50°C
  - 5°C hysterese for å unngå flapping
- **Manuell overstyring**:
  - Auto: Automatisk temperaturbasert kontroll
  - På: Tving vifte til å alltid gå
  - Av: Tving vifte til å alltid stå
- **Web-kontrollpanel integrasjon**:
  - Tre knapper: Auto/På/Av
  - Sanntids temperaturvisning
  - Fargekodet temperatur (grønn < 55°C, orange < 60°C, rød ≥ 60°C)
  - Live status: Se om vifta går akkurat nå
  - Automatisk oppdatering hvert 5. sekund

**Teknisk implementering**:
- Ny service: `fan-control.service`
- Python-script: `fan_control.py`
- GPIO 13 (blå ledning fra Pi 5 vifte)
- IPC via `/tmp/duck_fan.txt` (modus) og `/tmp/duck_fan_status.txt` (status)
- API endpoints: `/fan-status` (GET) og `/set-fan-mode` (POST)

**Installasjon**: Inkludert i `install-services.sh`

## [2.0.1] - 2025-11-10

### Bugfixes

#### 🐛 Volumkontroll

**Problem**: Volumslideren i kontrollpanelet hadde ingen effekt på lydavspilling. Slideren kunne justeres, men volumet endret seg ikke når anda snakket.

**Årsak**: 
1. HTML slider mangler `oninput` event handler - visningen oppdaterte seg ikke under draing
2. `chatgpt_voice.py` leste aldri volumet fra `/tmp/duck_volume.txt`
3. Volumet ble ikke anvendt på lydsamplene før avspilling

**Løsning**:
- Lagt til `oninput="updateVolumeValue()"` i HTML slider for sanntidsoppdatering av visning
- Lagt til `VOLUME_FILE = "/tmp/duck_volume.txt"` konstant i `chatgpt_voice.py`
- Implementert volumlesing i `speak()` funksjonen (0-100, hvor 50 = normal)
- Konverterer volumverdien til gain multiplier (0.0-2.0 hvor 1.0 = normal)
- Anvender volumet på lydsamplene etter fade-in/fade-out: `samples = samples * volume_gain`
- Lagt til voluminfo i TTS-logging: `Volum: 50% (gain: 1.00)`

**Resultat**: Volumkontroll fungerer nå som forventet - 0% = stille, 50% = normalt, 100% = dobbelt lydstyrke.

## [2.0.0] - 2025-11-10

### Major Release: Web Control Panel & Enhanced Features

#### 🎉 Nye hovedfunksjoner

##### Web Kontrollpanel (Port 3000)
- **Komplett web-basert kontrollpanel** for fjernstyring av alle funksjoner
- **Sanntids statusvisning** med automatisk oppdatering hvert 5. sekund
- **Live systemlogger** med fargekodet output (grønn/rød/orange)
- **Smart scroll** i logger - auto-scroll kun hvis bruker er nederst
- **Service-kontroll** via web (start/stopp/restart chatgpt-duck.service)
- **Responsive design** med gradient styling og smooth animasjoner

##### Talehastighet-kontroll
- **Justerbar talehastighet** via slider (0-100%)
  - 0%: Veldig sakte (–50% hastighet)
  - 50%: Normal hastighet
  - 100%: Dobbel hastighet (+100%)
- **SSML prosody rate** implementering i Azure TTS
- **Synkron nebb-bevegelse** justeres automatisk til hastighet
- **Persistent lagring** via `/tmp/duck_speed.txt`

##### Volumkontroll
- **Sanntids volumjustering** (0-100%)
- **Visuell slider** med "Lavt 🔉" og "Høyt 🔊" labels
- **Persistent lagring** via `/tmp/duck_volume.txt`
- **Live preview** av volumnivå i prosent

##### AI og Stemmeinnstillinger
- **Modellvalg** (gpt-3.5-turbo, gpt-4, gpt-4-turbo)
- **5 personligheter**:
  - Normal (balansert og høflig)
  - Entusiastisk (energisk og positiv)
  - Filosofisk (reflekterende og dyp)
  - Humoristisk (morsom og spøkefull)
  - Kort (konsise svar)
- **3 norske Azure TTS stemmer**:
  - nb-NO-FinnNeural (mann, dyp)
  - nb-NO-PernilleNeural (kvinne, klar)
  - nb-NO-IselinNeural (kvinne, varm)

##### Direktemeldinger
- **Tre moduser** for sending:
  - 🔊 Bare si det (TTS uten AI)
  - 🤖 Send til ChatGPT (stille respons)
  - 🎯 Full behandling (AI + TTS + nebb)
- **Stort tekstfelt** med gradient styling
- **Real-time feedback** ved sending

##### System-administrasjon
- **WiFi-scanning** med visning av tilgjengelige nettverk
- **Hotspot-switch** for WiFi-konfigurasjon
- **System reboot** via web
- **System shutdown** via web
- **Nebb-test** funksjon

#### 🔧 Tekniske forbedringer

##### Backend (duck-control.py)
- **15 nye REST API endpoints**:
  - GET `/duck-status` - Service running status
  - GET `/status` - Alle innstillinger
  - GET `/logs` - Systemlogger via journalctl
  - GET `/current-model`, `/current-personality`, `/current-voice`, etc.
  - GET `/wifi-networks` - Scan WiFi (nmcli integration)
  - POST `/control` - Service-kontroll
  - POST `/change-speed`, `/change-volume`, etc.
  - POST `/speak`, `/ask`, `/full-response` - Meldings-moduser
  - POST `/test-beak` - Test nebb-bevegelse
  - POST `/reboot`, `/shutdown` - System-kontroll
- **BaseHTTPRequestHandler** implementering (ingen eksterne web-dependencies)
- **JSON response format** standardisering
- **Error handling** med detaljerte feilmeldinger
- **Sudo-rettigheter** konfigurert via `/etc/sudoers.d/duck-control`

##### Frontend (JavaScript)
- **Async/await** for alle API-kall
- **Error handling** med user-friendly meldinger
- **Smart UI updates**:
  - Auto-refresh status (5s interval)
  - Color-coded log lines (regex-basert parsing)
  - Smooth scroll behavior
  - Form validation
- **No external dependencies** - vanilla JavaScript

##### IPC (Inter-Process Communication)
- **Tmp-fil basert kommunikasjon** mellom services:
  - `/tmp/duck_personality.txt` - AI-personlighet
  - `/tmp/duck_voice.txt` - Azure TTS stemme
  - `/tmp/duck_volume.txt` - Lydvolum (0-100)
  - `/tmp/duck_beak.txt` - Nebb on/off
  - `/tmp/duck_speed.txt` - Talehastighet (0-100)
  - `/tmp/duck_model.txt` - ChatGPT-modell
  - `/tmp/duck_message.txt` - Direktemeldinger
- **Atomic file writes** for race condition prevention
- **Default values** hvis filer mangler

##### Hovedapplikasjon (chatgpt_voice.py)
- **Speed parameter** i TTS-funksjon med SSML prosody
- **Volume control** integrering
- **Dynamic config loading** fra tmp-filer
- **Improved error handling** med retry logic

#### 🎨 UI/UX Forbedringer

##### Styling
- **Gradient backgrounds** (purple/blue theme)
- **Smooth animations** på buttons og hover
- **Color-coded status badges**:
  - Grønn: Duck kjører ✅
  - Rød: Duck stoppet ⏸️
  - Gul: Ukjent status ❓
- **Terminal-style logger** med monospace font og #1e1e1e bakgrunn
- **Full-width sliders** med emoji labels
- **Responsive layout** for mobile og desktop

##### Interaktivitet
- **Real-time feedback** på alle handlinger
- **Loading states** under API-kall
- **Confirmation dialogs** for critical actions
- **Auto-update** av UI etter endringer

#### 📚 Dokumentasjon

##### Nye dokumenter
- **ARCHITECTURE.md** - Komplett teknisk arkitektur
  - Komponentbeskrivelse
  - Data flow diagrammer
  - IPC-protokoll detaljer
  - API endpoint dokumentasjon
  - Sikkerhet og rettigheter
  - Feilhåndtering
  - Performance metrics
  - Debugging guide

- **INSTALL.md** - Detaljert installasjonsveiledning
  - Hardware-oppsett med wiring-diagrammer
  - Software-installasjon steg-for-steg
  - API-nøkkel konfigurasjon
  - Systemd service setup
  - Test og verifisering
  - Feilsøkingsseksjon
  - Vedlikeholdsinstruksjoner

- **PORTS.md** - Nettverks- og port-konfigurasjon
  - Detaljert port-dokumentasjon
  - GPIO pin mapping
  - Brannmur-konfigurasjon
  - Ekstern tilgang via VPN
  - Feilsøking nettverksproblemer

##### Oppdaterte dokumenter
- **README.md** - Komplett omskriving
  - Hovedfunksjoner oversikt
  - Web kontrollpanel guide
  - RGB LED status-tabell
  - Stemmekommandoer
  - Systemkrav
  - IPC-protokoll tabell
  - API endpoint oversikt

- **requirements.txt** - Med kommentarer og versjoner
  - Gruppering per funksjon
  - Minimum versjoner spesifisert
  - Forklaringer for hver pakke

#### 🔒 Sikkerhet

- **Sudo-restriksjoner** via sudoers-fil
- **API-nøkkel isolasjon** i .env (ikke committet)
- **Input validation** på alle POST endpoints
- **Timeout protection** på subprocess-kall
- **Error sanitization** i responses

#### 🐛 Bugfixes

- **Fixed: JavaScript response checking** (data.status → data.success)
- **Fixed: Double scrollbars** i logger
- **Fixed: Log auto-scroll** interrupting reading
- **Fixed: Box width alignment** med box-sizing: border-box
- **Fixed: Missing favicon** (404 error)
- **Fixed: Status ikke oppdatert** ved pageload
- **Fixed: Newline escaping** i JavaScript-generert kode

#### ⚡ Performance

- **Reduced API calls** med caching av innstillinger
- **Debounced slider updates** for mindre disk I/O
- **Efficient log fetching** med journalctl -n 50
- **Minimal JavaScript** (no frameworks overhead)

#### 🔄 Breaking Changes

Ingen breaking changes - bakoverkompatibel med versjon 1.x.

Eksisterende installasjoner kan oppgraderes med:
```bash
git pull
sudo systemctl restart duck-control.service
sudo systemctl restart chatgpt-duck.service
```

---

## [1.0.0] - 2025-10-XX

### Initial Release

#### Core Features
- Wake word detection med Porcupine ("Samantha")
- Azure Speech-to-Text for stemmegjenkjenning
- ChatGPT integration via OpenAI API
- Azure Text-to-Speech med norske stemmer
- Servo-kontrollert nebb med amplitude-synkronisering
- RGB LED status-indikatorer
- Systemd service for auto-start

#### Hardware Support
- Raspberry Pi 4/5/400
- Monk Makes RGB LED
- SG90/MG90 servo
- USB mikrofon
- 3.5mm/HDMI/USB høyttaler

#### AI Capabilities
- Contextual conversation med historikk
- Single personality (normal)
- Single voice (nb-NO-FinnNeural)
- gpt-3.5-turbo modell

#### Configuration
- Environment variables via .env
- Manual configuration av innstillinger
- Command-line scripts for setup

---

## Versjonsnummerering

Prosjektet følger [Semantic Versioning](https://semver.org/):
- **MAJOR** version for inkompatible API-endringer
- **MINOR** version for nye funksjoner (bakoverkompatibel)
- **PATCH** version for bugfixes (bakoverkompatibel)

---

## Kommende funksjoner (Roadmap)

### Version 2.1.0 (Planlagt)
- [ ] WebSocket for real-time log streaming (no polling)
- [ ] Custom wake word training
- [ ] Conversation history database (SQLite)
- [ ] Export/import av innstillinger
- [ ] Voice activity detection (VAD) forbedringer
- [ ] Multi-language support (engelsk, tysk, etc.)

### Version 2.2.0 (Planlagt)
- [ ] MQTT integration for smart home
- [ ] Scheduled tasks (reminders, alarms)
- [ ] Weather integration
- [ ] Calendar integration
- [ ] News reading capability

### Version 3.0.0 (Fremtidig)
- [ ] Local LLM support (Ollama, LLaMA)
- [ ] Whisper STT (lokal stemmegjenkjenning)
- [ ] Docker deployment option
- [ ] Multi-user profiles
- [ ] Voice authentication
- [ ] Mobile app (iOS/Android)

---

**Bidrag velkommen!** Se [CONTRIBUTING.md](CONTRIBUTING.md) for retningslinjer.
