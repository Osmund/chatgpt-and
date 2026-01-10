# Dokumentasjonsoversikt

Denne filen gir en oversikt over all prosjektdokumentasjon for ChatGPT Duck.

## 📊 Statistikk

- **Totalt antall linjer dokumentasjon**: ~2500 linjer
- **Antall markdown-filer**: 5 filer
- **Total dokumentasjonsstørrelse**: ~65 KB
- **Sist oppdatert**: 9. januar 2026

## 📚 Dokumentasjonsstruktur

### Brukerdokumentasjon

#### 1. [README.md](README.md) - 📖 Hovedveiledning (15 KB, ~400 linjer)
**Målgruppe**: Alle brukere

**Innhold**:
- Prosjektoversikt og hovedfunksjoner
- Quick Start guide (5 minutter)
- Web kontrollpanel funksjonalitet
- RGB LED status-indikatorer
- Stemmekommandoer
- IPC-arkitektur (tmp-filer)
- API endpoints oversikt
- Systemkrav (hardware og software)
- Talehastighet-implementering
- Komplett filstruktur

**Når brukes**: 
- Første gang du ser på prosjektet
- Oversikt over alle funksjoner
- Referanse for daglig bruk

#### 2. [INSTALL.md](INSTALL.md) - 🔧 Installasjonsveiledning (16 KB, ~650 linjer)
**Målgruppe**: Nye brukere, system-administratorer

**Innhold**:
- **Del 1**: Hardware-oppsett
  - RGB LED wiring med testing
  - Servo-tilkobling (VIKTIG: separat strøm!)
  - Audio-konfigurasjon (mikrofon + høyttaler)
- **Del 2**: Software-installasjon
  - System-pakker
  - Python virtual environment
  - Porcupine wake word modell (samantha_en_raspberry-pi_v4_0_0.ppn)
- **Del 3**: API-nøkler
  - OpenAI setup og pricing
  - Azure Speech Service setup
  - .env konfigurasjon og testing
- **Del 4**: Systemd Services
  - Sudo-rettigheter konfigurasjon
  - Service-installasjon
  - Oppstart og verifisering
- **Del 5**: Test og verifisering
  - Wake word testing
  - Web-panel testing
  - Personlighets-testing
- **Del 6**: Konfigurasjon og tilpasning
  - Endre wake words
  - GPIO pin mapping
  - Nebb-følsomhet
  - Standard innstillinger
- **Del 7**: Autostart ved oppstart
- **Del 8**: Feilsøking (omfattende)
- **Del 9**: Vedlikehold
- **Del 10**: Sikkerhetstips

**Når brukes**:
- Første gangs installasjon
- Troubleshooting hardware-problemer
- Oppsett av nye Raspberry Pi
- API-konfigurasjon

#### 3. [CHANGELOG.md](CHANGELOG.md) - 📝 Versionshistorikk (9 KB, ~400 linjer)
**Målgruppe**: Utviklere, power-users

**Innhold**:
- **Version 2.0.0** (10. november 2025):
  - Web kontrollpanel (komplett feature-liste)
  - Talehastighet-kontroll
  - Volumkontroll
  - AI og stemmeinnstillinger
  - Direktemeldinger (3 moduser)
  - System-administrasjon
  - Backend API endpoints (15 nye)
  - Frontend JavaScript features
  - IPC-implementering (7 tmp-filer)
  - UI/UX forbedringer
  - Dokumentasjon (alle nye filer)
  - Sikkerhetsforbedringer
  - Bugfixes (8 fixes)
  - Performance-optimalisering
- **Version 1.0.0**: Initial release
- **Roadmap**: Planlagte funksjoner for 2.1, 2.2, 3.0

**Når brukes**:
- Se hva som er nytt i hver versjon
- Planlegge oppgraderinger
- Forstå breaking changes
- Bidra til utvikling (roadmap)

### Teknisk dokumentasjon

#### 4. [ARCHITECTURE.md](ARCHITECTURE.md) - 🏗️ Teknisk arkitektur (15 KB, ~700 linjer)
**Målgruppe**: Utviklere, tekniske brukere

**Innhold**:
- **Oversikt**: System-arkitektur diagram
- **Komponentbeskrivelse**:
  - chatgpt_voice.py (wake word, STT, ChatGPT, TTS)
  - duck-control.py (HTTP server, REST API)
  - duck_beak.py (servo-kontroll)
  - rgb_duck.py (LED status)
- **Data Flow**:
  - Brukerinitialisert samtale (flow diagram)
  - Web-initialisert melding
  - Innstillingsendring
- **Sikkerhet og rettigheter**:
  - Sudo-konfigurasjon
  - API-nøkler
  - Filrettigheter
- **Feilhåndtering**:
  - Retry logic
  - Timeout handling
  - Error responses
- **Performance**:
  - Latency breakdown
  - Memory usage
  - CPU usage
  - Storage requirements
- **Skalering og utvidelser**:
  - Mulige utvidelser (8 ideer)
  - Hardware-utvidelser (4 ideer)
- **Debugging og logging**:
  - Systematisk debugging
  - Common issues tabell (8 problemer)
- **Teknologivalg**:
  - Begrunnelser for Python, BaseHTTPRequestHandler, tmp-filer, Porcupine, Azure, systemd

**Når brukes**:
- Forstå hvordan systemet fungerer
- Utvikle nye funksjoner
- Debugging komplekse problemer
- Bidra til prosjektet
- Optimalisering

#### 5. [PORTS.md](PORTS.md) - 🌐 Nettverks-konfigurasjon (6 KB, ~300 linjer)
**Målgruppe**: Nettverksadministratorer, avanserte brukere

**Innhold**:
- **Port 3000**: Duck Control Panel
  - Funksjoner (8 kategorier)
  - Tilgang (3 metoder)
  - Service-kontroll
  - Tekniske detaljer
- **Port 80**: WiFi Configuration Portal
  - Funksjoner
  - Tilgang i hotspot-modus
  - Captive portal
- **Utgående forbindelser**:
  - OpenAI API (443)
  - Azure Speech (443)
  - NTP (123)
- **GPIO Pins**: Oversikt (ikke nettverks-porter)
- **Brannmur-konfigurasjon**:
  - ufw setup
  - Port forwarding
  - VPN (Tailscale) anbefaling
- **Port-bruk tabell**: Alle porter med detaljer
- **Feilsøking**:
  - Port 3000 ikke tilgjengelig
  - Kan ikke nå fra annen enhet
  - WiFi-portal fungerer ikke

**Når brukes**:
- Nettverkskonfigurasjon
- Åpne porter i brannmur
- Ekstern tilgang setup
- Debugging tilkoblingsproblemer

### Konfigurasjonsfiler

#### 6. [requirements.txt](requirements.txt) - 📦 Python Dependencies (~30 linjer)
**Målgruppe**: Utviklere, installatører

**Innhold**:
- AI og Speech Services (openai, azure-cognitiveservices-speech)
- Audio Processing (pydub, sounddevice, pyaudio, numpy, scipy)
- Wake Word Detection (Porcupine)
- Hardware Control (gpiozero, RPi.GPIO, lgpio)
- Utilities (python-dotenv, requests)
- Alle med minimum versjonsnumre
- Kommentarer for hver kategori

**Når brukes**:
- `pip install -r requirements.txt`
- Sjekke avhengigheter
- Oppdatere pakker

#### 7. [.gitignore](.gitignore) - 🔒 Git Ignore (~100 linjer)
**Målgruppe**: Utviklere

**Innhold**:
- KRITISK: .env (API-nøkler)
- Python artifacts
- Virtual environments
- Audio/Media files
- Logs
- OS-spesifikke filer
- Backup files
- Porcupine wake word models (.ppn)
- Test output
- Legacy files
- Alle med kommentarer og kategorisering

**Når brukes**:
- Automatisk ved `git add`
- Sikre at sensitive filer ikke committes
- Holde repository rent

## 📖 Leserekkefølge

### For nye brukere:
1. **README.md** - Få oversikt over prosjektet
2. **INSTALL.md** - Følg installasjonsveiledningen trinn-for-trinn
3. **README.md** (Web Kontrollpanel seksjon) - Lær å bruke kontrollen
4. **PORTS.md** (kun hvis nettverksproblemer)

### For utviklere:
1. **README.md** - Oversikt
2. **ARCHITECTURE.md** - Forstå systemet
3. **CHANGELOG.md** - Se hva som er nytt
4. **INSTALL.md** - Development setup
5. **PORTS.md** - Nettverksforståelse

### For troubleshooting:
1. **INSTALL.md** (Del 8: Feilsøking)
2. **ARCHITECTURE.md** (Debugging seksjon)
3. **PORTS.md** (Feilsøking nettverks-seksjonen)

## 🔍 Søk i dokumentasjonen

### Finne informasjon om...

| Tema | Dokument | Søkeord |
|------|----------|---------|
| Installasjon | INSTALL.md | "hardware-oppsett", "system-pakker", "API-nøkler" |
| API-nøkler | INSTALL.md, README.md | "OPENAI_API_KEY", ".env", "Azure" |
| Web-panel | README.md | "kontrollpanel", "3000", "web interface" |
| Talehastighet | README.md, ARCHITECTURE.md | "speed", "hastighet", "SSML prosody" |
| Nebb-kontroll | INSTALL.md, ARCHITECTURE.md | "servo", "beak", "amplitude" |
| USB-C PD-trigger | PINOUT.md, INSTALL.md | "PD-trigger", "strømforsyning", "servo strøm" |
| RGB LED | INSTALL.md, README.md | "RGB", "GPIO 17 27 22", "status-indikatorer" |
| Wake word | README.md, INSTALL.md | "Samantha", "Porcupine" |
| Oppstartsmelding | README.md, ARCHITECTURE.md | "oppstart", "IP-adresse", "nettverksdeteksjon" |
| Feilsøking | INSTALL.md, ARCHITECTURE.md | "troubleshooting", "feilsøking", "problem" |
| Nettverkskonfigurasjon | PORTS.md | "port", "brannmur", "firewall" |
| IPC | README.md, ARCHITECTURE.md | "tmp", "IPC", "/tmp/duck_" |
| Services | README.md, INSTALL.md | "systemd", "systemctl", "service" |

## 💡 Tips for bruk av dokumentasjonen

### Søk med grep
```bash
# Søk etter et ord i all dokumentasjon
grep -r "wake word" *.md

# Søk case-insensitive
grep -ri "azure" *.md

# Søk med kontekst (3 linjer før og etter)
grep -C 3 "API" README.md
```

### Vis spesifikk seksjon
```bash
# Vis kun "Installation" seksjonen
sed -n '/## Installation/,/^##/p' INSTALL.md | head -n -1

# Vis alle overskrifter
grep "^##" README.md
```

### Konverter til PDF (hvis ønsket)
```bash
# Installer pandoc
sudo apt-get install pandoc

# Konverter til PDF
pandoc README.md -o README.pdf
pandoc INSTALL.md -o INSTALL.pdf
```

## 🤝 Bidra til dokumentasjonen

Dokumentasjonen er viktig! Hvis du finner:
- Feil eller utdatert informasjon
- Manglende forklaringer
- Uklare instruksjoner
- Grammatiske feil

Vennligst:
1. Opprett et issue på GitHub
2. Eller send en pull request med fix
3. Eller kontakt maintainer

## 📝 Dokumentasjonsstandard

All dokumentasjon følger:
- **Markdown** format (GitHub-flavored)
- **Klare overskrifter** med emojis for visuell navigasjon
- **Kodeblokker** med syntax highlighting
- **Tabeller** for strukturert data
- **Diagrammer** i ASCII art eller beskrivelser
- **Lenker** mellom relaterte dokumenter
- **Datoer** i ISO-format (YYYY-MM-DD)

## 🎯 Dokumentasjonsmål

Dokumentasjonen skal være:
- ✅ **Komplett**: Dekker alle aspekter av systemet
- ✅ **Nybegynnervennlig**: Forklarer alt trinn-for-trinn
- ✅ **Teknisk nøyaktig**: Korrekte detaljer for utviklere
- ✅ **Oppdatert**: Synkronisert med kodebase
- ✅ **Søkbar**: Lett å finne informasjon
- ✅ **Modulær**: Hver fil har et klart formål

---

**Total dokumentasjonsinnsats**: ~2400 linjer / ~60 KB
**Estimert lesetid**: 
- Quick Start: 5 minutter
- README: 15 minutter
- INSTALL: 45 minutter
- ARCHITECTURE: 30 minutter
- Alt: 2 timer

**Lykke til med ChatGPT Duck! 🦆💬**
