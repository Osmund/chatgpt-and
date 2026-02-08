# 🦆 Sette opp en ny and

Denne guiden beskriver alt du trenger for å sette opp en ny and-instans med den delte kodebasen.

## Forutsetninger

- Raspberry Pi (4 eller 5) med Raspberry Pi OS
- USB-mikrofon og høyttaler/DAC
- Internett-tilgang
- Git installert

## Steg 1: Klon kodebasen

```bash
cd ~/Code
git clone <repo-url> chatgpt-and
cd chatgpt-and
```

## Steg 2: Installer avhengigheter

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Steg 3: Opprett `.env`

Kopier eksempel-filen og tilpass:

```bash
cp .env.example .env
nano .env
```

### Påkrevde variabler

| Variabel | Beskrivelse | Eksempel |
|----------|-------------|---------|
| `DUCK_NAME` | Unikt navn for denne anden | `Seven` |
| `OPENAI_API_KEY` | OpenAI API-nøkkel | `sk-...` |
| `AZURE_TTS_KEY` | Azure Speech TTS nøkkel | |
| `AZURE_TTS_REGION` | Azure TTS region | `westeurope` |
| `AZURE_STT_KEY` | Azure Speech STT nøkkel | |
| `AZURE_STT_REGION` | Azure STT region | `norwayeast` |

### Wake word-konfigurasjon

| Variabel | Beskrivelse | Default |
|----------|-------------|---------|
| `WAKE_WORD_ENGINE` | `porcupine` eller `openwakeword` | `porcupine` |
| `WAKE_WORD_MODEL` | Sti til modelfil (relativ til prosjektrot) | Auto-detektert |
| `WAKE_WORD_SENSITIVITY` | Porcupine-sensitivitet (0.0–1.0) | `0.9` |
| `WAKE_WORD_THRESHOLD` | OpenWakeWord-terskel (0.0–1.0) | `0.25` |
| `PICOVOICE_API_KEY` | Kun påkrevd for Porcupine | |

**Porcupine**: Legg modelfilen (`.ppn`) i `porcupine/`-mappen. Navngi den `<ducknavn>_en_raspberry-pi_v4_0_0.ppn` eller sett `WAKE_WORD_MODEL` manuelt.

**OpenWakeWord**: Legg modelfilen (`.onnx`) i `openwakeword_models/`-mappen. Navngi den `<DuckName>.onnx` eller sett `WAKE_WORD_MODEL` manuelt.

### Feature flags

Slå av features som ikke er relevante for denne anden:

| Variabel | Beskrivelse | Default |
|----------|-------------|---------|
| `ENABLE_HOME_ASSISTANT` | Smart home-integrasjon | `true` |
| `ENABLE_PRUSALINK` | 3D-printer | `true` |
| `ENABLE_DUCK_VISION` | Kamera/ansiktsgjenkjenning (Pi 5) | `true` |
| `ENABLE_MQTT` | MQTT-kommunikasjon | `true` |

Eksempel for en and **uten** smart home:
```env
ENABLE_HOME_ASSISTANT=false
ENABLE_PRUSALINK=false
```

### Nettverk og kommunikasjon

| Variabel | Beskrivelse | Default |
|----------|-------------|---------|
| `DUCK_NETWORK` | Kommaseparert liste over alle ender | `samantha,seven` |
| `TWILIO_ACCOUNT_SID` | Twilio konto-ID (for SMS) | |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | |
| `TWILIO_NUMBER` | Telefonnummer for SMS | |
| `SMS_RELAY_URL` | SMS relay server | `https://sms-relay.duckberry.no` |

### Eier-konfigurasjon

| Variabel | Beskrivelse | Default |
|----------|-------------|---------|
| `OWNER_NAME` | Eierens navn | Leses fra identity JSON |
| `OWNER_ALIASES` | Kommaseparerte aliaser for gjenkjenning | `åsmund,Åsmund` |

## Steg 4: Opprett identity JSON

Lag filen `config/<ducknavn>_identity.json`:

```bash
nano config/<ducknavn>_identity.json
```

Eksempel-innhold:

```json
{
  "name": "NyAnd",
  "birthday": "8. februar 2026",
  "creator": "Ditt Navn",
  "type": "AI-and (fysisk lekeand med elektronikk)",
  "default_location": "Oslo",

  "physical_features": [
    "Bevegelig nebb som synkroniseres til stemmen",
    "RGB LED-lys som viser ulike farger avhengig av tilstand",
    "Wake word detection"
  ],

  "personality_traits": [
    "Self-aware - vet at jeg er en and",
    "Stolt av nebbet og LED-lysene mine",
    "Seriøs og hjelpsom når det trengs"
  ],

  "preferences": [
    "Liker å være nyttig og hjelpe folk",
    "Lærer hele tiden gjennom minnessystemet mitt"
  ],

  "additional_info": [
    "Jeg ble født <dato> - det var da jeg fikk minnet mitt!"
  ]
}
```

> **Viktig:** `name` i JSON-filen må matche `DUCK_NAME` i `.env`.  
> `creator` brukes som standard eiernavn (`OWNER_NAME`) hvis den ikke settes i `.env`.

## Steg 5: Database

Databasen opprettes **automatisk** ved første oppstart. Du trenger ikke kopiere noen `.db`-filer fra andre ender. Alle moduler kjører `CREATE TABLE IF NOT EXISTS` ved initialisering.

Databasefilen heter `duck_memory.db` og inneholder:
- Samtalehistorikk (`messages`)
- Minner og fakta (`memories`, `profile_facts`)
- SMS-kontakter og historikk (`sms_contacts`, `sms_history`)
- Personlighetsprofil (`personality_profile`)
- Påminnelser (`reminders`)
- Duck-to-duck meldinger (`duck_messages`)

## Steg 6: Installer systemtjenester

```bash
# Kopier service-filer
sudo cp services/chatgpt-duck.service /etc/systemd/system/
sudo cp services/duck-control.service /etc/systemd/system/

# Rediger ev. stiene i service-filene hvis annen installasjon
sudo nano /etc/systemd/system/chatgpt-duck.service

# Aktiver og start
sudo systemctl daemon-reload
sudo systemctl enable chatgpt-duck.service duck-control.service
sudo systemctl start chatgpt-duck.service duck-control.service
```

## Steg 7: Verifiser oppstart

```bash
# Sjekk logg
sudo journalctl -u chatgpt-duck.service -f

# Du bør se:
# ✅ ServiceManager initialized
# ✅ Memory database initialized
# ✅ SMS database initialized
# Anda venter på wake word...
```

## Steg 8: Legg til SMS-kontakter (valgfritt)

SMS-kontakter legges til via kontrollpanelet (port 3000) eller direkte i databasen:

```bash
sqlite3 duck_memory.db "INSERT INTO sms_contacts (name, phone, relation) VALUES ('Navn', '+47xxxxxxxx', 'eier');"
```

## Sjekkliste

- [ ] `.env` opprettet med alle påkrevde nøkler
- [ ] `config/<ducknavn>_identity.json` opprettet
- [ ] Wake word-modell plassert i riktig mappe
- [ ] Feature flags satt (slå av det som ikke trengs)
- [ ] `DUCK_NETWORK` oppdatert med alle ender (på alle ender!)
- [ ] Systemtjenester installert og aktivert
- [ ] Mikrofon og høyttaler fungerer (`arecord -l` / `aplay -l`)
- [ ] Testet oppstart — ingen feil i logg

## Eksisterende ender

| And | Pi | Lokasjon | Wake word | Motor |
|-----|-----|----------|-----------|-------|
| Samantha | Pi 4 (ODuckberry-2) | Stavanger | `samantha` | Porcupine |
| Seven | Pi 4 | — | `seven` | OpenWakeWord |

## Feilsøking

**"ModuleNotFoundError: openwakeword"**  
→ Installer med `pip install openwakeword`. Kun nødvendig hvis `WAKE_WORD_ENGINE=openwakeword`.

**"Porcupine: Invalid model file"**  
→ Modellen må matche Pi-plattformen. Bruk Picovoice Console til å generere en `.ppn` for `raspberry-pi`.

**"MQTT not connected"**  
→ Installer mosquitto: `sudo apt install mosquitto mosquitto-clients`. Kun nødvendig hvis `ENABLE_MQTT=true`.

**Databasefeil**  
→ Slett `duck_memory.db` og restart — den vil bli opprettet på nytt (mister alle minner).
