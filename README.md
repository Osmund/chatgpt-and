# Anda-prosjektet

Dette prosjektet lar en "and" (med bevegelsesnebb og RGB LED) snakke med deg via ChatGPT og Azure TTS/STT, og vise status med RGB-lys. Du kan vekke anda med wake word, snakke med den, og den svarer med tale og nebb-bevegelse.

## Maskinvare

- Raspberry Pi (testet på Pi 400 og Pi 5)
- Monk Makes RGB LED (koblet: R=GPIO17, G=GPIO27, B=GPIO22)
- Servo til nebb (koblet til f.eks. GPIO14) - **NB: Bruk separat strømforsyning til servoen!**
- (Valgfritt) DHT11 på GPIO4 for temperatur
- (Valgfritt) TFT-skjerm for tekstutskrift

## Programvare

- Python 3.11+
- Virtuelt miljø anbefales (`python3 -m venv .venv`)
- Installer avhengigheter:
  ```bash
  pip install -r requirements.txt
  ```

## Wake Word med Vosk

Prosjektet bruker **Vosk** for offline wake word detection (svensk modell).

### Sett opp Vosk-modell:

1. **Last ned svensk modell:**
   ```bash
   wget https://alphacephei.com/vosk/models/vosk-model-small-sv-rhasspy-0.15.zip
   unzip vosk-model-small-sv-rhasspy-0.15.zip
   ```

2. **Plasser mappen i prosjektmappen** (`/home/admog/Code/MyFirst/vosk-model-small-sv-rhasspy-0.15/`)

3. **Standard wake words er "alexa" eller "ulrika"** – du kan endre dette i `wait_for_wake_word()`-funksjonen.

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

## Siste endringer

- Byttet fra Picovoice/OpenWakeWord til **Vosk** for wake word detection (offline, gratis, pålitelig).
- Bruker svensk Vosk-modell (`vosk-model-small-sv-rhasspy-0.15`) for wake words "alexa" og "ulrika".
- RGB LED-styring flyttet til egen fil `rgb_duck.py` med funksjoner for farger og blinking.
- Blinkingen under "tenkepause" veksler mellom gul og lilla.
- LED-styring er robust: `stop_blink()` venter på at blinketråden er ferdig før ny farge settes.
- Samtaleflyt: Samtalen fortsetter automatisk til du sier "stopp".
- Lagt til `lgpio` for bedre GPIO-støtte på nyere Raspberry Pi-modeller.
- **Servo må ha separat strømforsyning for å unngå flikring/støy på LED og Pi.**

## Oppsett av .env

Eksempel på `.env`:
```
OPENAI_API_KEY=din_openai_nøkkel
AZURE_TTS_KEY=din_azure_tts_nøkkel
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=din_azure_stt_nøkkel
AZURE_STT_REGION=westeurope
```

**NB:** Du trenger ikke lenger `PICOVOICE_ACCESS_KEY` eller `ANNOUNCE_ENV`.

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

## Tips

- Hvis LED eller Pi flikrer/rebooter: **bruk separat strøm til servoen!**
- For å endre LED-blink, juster i `rgb_duck.py`.
- For å endre wake words, endre sjekken i `wait_for_wake_word()`-funksjonen.
- Vosk støtter flere språk – last ned norsk modell (`vosk-model-small-no-0.22`) hvis du vil bruke norske wake words.
- Hvis du får GPIO-advarsler, installer `lgpio`: `pip install lgpio`

---

**God andeprat!**