# ChatGPT Andenebb-prosjekt

Dette prosjektet lar deg snakke til en "and" (robot med nebb styrt av servo) via mikrofon, få svar fra ChatGPT, og høre svaret lest opp med norsk stemme og "Donald Duck"-effekt. Nebbet beveger seg synkront med talen. Systemet støtter nå også wake word ("quack quack") med lokal Porcupine wake word-detektering.

## Funksjoner

- **Wake word**: Si "quack quack" for å aktivere anda (Porcupine, lokalt).
- **Tale-til-tekst**: Azure Speech-to-Text (STT) for norsk tale.
- **ChatGPT-integrasjon**: Spørsmål sendes til OpenAI ChatGPT (gpt-3.5-turbo).
- **Tekst-til-tale**: Azure TTS (neural norsk stemme, region westeurope).
- **Donald Duck-effekt**: Pitch-shifting på tale for andepreg.
- **Synkront nebb**: Nebbet beveger seg i takt med lydstyrken i svaret.
- **Støtte for Raspberry Pi (Pi 400, Pi 5 anbefalt)**

## Maskinvarekrav

- Raspberry Pi 400, Pi 4 eller Pi 5 (anbefalt)
- Servo koblet til GPIO 14 (pin 8)
- USB-headset eller mikrofon
- (Valgfritt) Høyttaler

## Programvarekrav

- Python 3.8+
- Azure-konto med Speech-tjeneste i både `westeurope` (TTS) og `norwayeast` (STT)
- OpenAI API-nøkkel
- Picovoice-konto for Porcupine wake word og AccessKey

## Installasjon

1. **Installer systemavhengigheter:**
    ```bash
    sudo apt update
    sudo apt install python3-pyaudio portaudio19-dev ffmpeg pigpio
    sudo systemctl enable pigpiod
    sudo systemctl start pigpiod
    ```

2. **Installer Python-pakker:**
    ```bash
    pip install -r requirements.txt
    ```
    Hvis du ikke har en `requirements.txt`, installer disse:
    ```bash
    pip install pydub scipy sounddevice numpy pvporcupine pyaudio python-dotenv azure-cognitiveservices-speech requests
    ```

3. **Sett opp .env-fil:**
    Kopier `.env.example` til `.env` og fyll inn dine nøkler:
    ```
    AZURE_TTS_KEY=din_tts_nokkel
    AZURE_TTS_REGION=westeurope
    AZURE_STT_KEY=din_stt_nokkel
    AZURE_STT_REGION=norwayeast
    OPENAI_API_KEY=din_openai_api_nokkel
    ```

4. **Porcupine wake word:**
    - Registrer deg på [picovoice.ai](https://console.picovoice.ai/) og last ned wake word-filen (f.eks. `quack_quack.ppn`) og AccessKey.
    - Legg filen i samme mappe som `chatgpt_voice.py`.
    - Lim inn AccessKey i koden.

5. **Koble til servo og mikrofon.**

## Bruk

Start programmet:
```bash
python3 chatgpt_voice.py
```
- Si "quack quack" for å vekke anda.
- Still spørsmål med stemmen.
- Anda svarer med ChatGPT og beveger nebbet i takt med svaret.

## Sikkerhet

**Ikke sjekk inn .env-filer med ekte nøkler i offentlige repo!**  
Bruk `.gitignore` for å utelate `.env` og andre sensitive filer.

## Feilsøking

- Hvis du får feil med `pyaudio`, installer `portaudio19-dev` og `python3-pyaudio` via apt.
- Hvis wake word ikke fungerer, sjekk at AccessKey og `.ppn`-fil er riktig.
- Hvis servo ikke beveger seg, sjekk at `pigpiod` kjører og at du bruker riktig GPIO.

---

**Lykke til med andeprosjektet!**