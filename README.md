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

Prosjektet bruker **Vosk** for offline wake word detection.

### Sett opp Vosk-modell:

1. **Last ned en liten engelsk modell:**
   ```bash
   wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
   unzip vosk-model-small-en-us-0.15.zip
   ```

2. **Plasser mappen i prosjektmappen** eller spesifiser riktig sti i koden.

3. **Standard wake word er "alexa"** – du kan endre dette i `wait_for_wake_word()`-funksjonen.

## Funksjoner

- **Wake word**: Si "alexa" for å vekke anda (Vosk offline speech recognition).
- **Samtale**: Snakk med anda, den svarer med ChatGPT og Azure TTS.
- **Nebb-bevegelse**: Nebbet beveger seg synkront med tale.
- **RGB LED-status**:
  - **Blå**: Venter på wake word
  - **Grønn**: Venter på at du skal snakke
  - **Blinkende gul/lilla**: "Tenkepause" (venter på svar fra ChatGPT/Azure)
  - **Rød**: Anda snakker
  - **Av**: Idle
- **Stopp samtale**: Si "stopp" for å gå tilbake til wake word.
- **(Valgfritt) Temperatur/klokke**: Kan annonseres automatisk hvis aktivert i `.env`.

## Siste endringer

- Byttet fra Picovoice/OpenWakeWord til **Vosk** for wake word detection (offline, gratis, pålitelig).
- RGB LED-styring flyttet til egen fil `rgb_duck.py` med funksjoner for farger og blinking.
- Blinkingen under "tenkepause" veksler nå mellom gul og lilla.
- LED-styring er robust: `stop_blink()` venter alltid på at blinketråden er ferdig før ny farge settes.
- Samtaleflyt: Samtalen fortsetter automatisk til du sier "stopp".
- DHT11 og temperaturkode er gjort valgfritt og kan enkelt fjernes.
- Kode for TFT-skjerm og DHT11 er ikke lenger påkrevd for hovedfunksjon.
- **Servo må ha separat strømforsyning for å unngå flikring/støy på LED og Pi.**
- NumPy nedgradert til <2.0 for kompatibilitet med tflite_runtime.

## Oppsett av .env

Eksempel på `.env`:
```
OPENAI_API_KEY=din_openai_nøkkel
AZURE_TTS_KEY=din_azure_tts_nøkkel
AZURE_TTS_REGION=westeurope
AZURE_STT_KEY=din_azure_stt_nøkkel
AZURE_STT_REGION=westeurope
ANNOUNCE_ENV=0
```

**NB:** Du trenger ikke lenger `PICOVOICE_ACCESS_KEY`.

## Kjøring

Aktiver venv og start anda:
```bash
source .venv/bin/activate
python chatgpt_voice.py
```

## Tips

- Hvis LED eller Pi flikrer/rebooter: **bruk separat strøm til servoen!**
- Hvis du bruker DHT11 eller TFT, se egne seksjoner i koden for oppsett.
- For å endre LED-blink, juster i `rgb_duck.py`.
- For å endre wake word, endre i `wait_for_wake_word()`-funksjonen.
- Vosk støtter flere språk – last ned norsk modell hvis du vil bruke norske wake words.

---

**God andeprat!** 