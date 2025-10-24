# Anda-prosjektet

Dette prosjektet lar en "and" (med bevegelsesnebb og RGB LED) snakke med deg via ChatGPT og Azure TTS/STT, og vise status med RGB-lys. Du kan vekke anda med wake word, snakke med den, og den svarer med tale og nebb-bevegelse.

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

## Funksjoner

- **Wake word**: Si "alexa" eller "ulrika" for å vekke anda (Vosk offline speech recognition).
- **Samtale**: Snakk med anda, den svarer med ChatGPT og Azure TTS (norsk stemme: nb-NO-FinnNeural).
- **Nebb-bevegelse**: Nebbet beveger seg synkront med tale basert på lydamplitude.
- **RGB LED-status**:
  - **Blå**: Venter på wake word
  - **Grønn**: Venter på at du skal snakke
  - **Blinkende gul/lilla**: "Tenkepause" (venter på svar fra ChatGPT)
  - **Rød**: Anda snakker
  - **Av**: Idle
- **Stopp samtale**: Si "stopp" for å gå tilbake til wake word.

## Kjøring

Aktiver venv og start anda:
```bash
source .venv/bin/activate
python chatgpt_voice.py
```

Eller direkte:
```bash
/home/admog/Code/MyFirst/.venv/bin/python /home/admog/Code/MyFirst/chatgpt_voice.py
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

## Komplett filstruktur

```
/home/admog/Code/MyFirst/
├── .venv/
├── .env
├── .gitignore
├── requirements.txt
├── README.md
├── chatgpt_voice.py
├── duck_beak.py
├── rgb_duck.py
└── vosk-model-small-sv-rhasspy-0.15/
```

---

**God andeprat!**