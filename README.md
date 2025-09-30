# ChatGPT Andenebb-prosjekt

Dette prosjektet lar deg styre et mekanisk andenebb (servo) med en Raspberry Pi, hvor nebbet beveger seg synkront med tale generert av ChatGPT og Azure Speech (norsk stemme). Systemet bruker OpenAI for tekstgenerering, Azure for tekst-til-tale, og analyserer lydfilen for å styre nebbet i sanntid.

## Funksjoner
- Skriv inn spørsmål til ChatGPT i terminalen
- Få svar lest opp på norsk med "Donald Duck"-effekt (pitch-shift)
- Andenebbet beveger seg synkront med talevolumet
- Støtter både GPIO 14 (pin 8) for servo og alle Raspberry Pi-modeller

## Maskinvare
- Raspberry Pi (med nettverk)
- SG90 eller lignende servo koblet til GPIO 14 (pin 8)
- 5V og GND til servo
- (Anbefalt) Ekstern strøm til servo hvis du bruker kraftig servo

## Programvare og avhengigheter
Installer følgende pakker i ditt virtuelle miljø:

```bash
sudo apt update
sudo apt install python3-pip python3-venv pigpio libportaudio2 ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install requests python-dotenv azure-cognitiveservices-speech sounddevice numpy pydub pigpio
```

Start pigpio-daemon før du kjører scriptet:
```bash
sudo systemctl start pigpiod
```

## Konfigurasjon
Legg inn følgende i `.env`-filen i prosjektmappen:
```
OPENAI_API_KEY=din_openai_api_nokkel
AZURE_SPEECH_KEY=din_azure_speech_key
AZURE_SPEECH_REGION=westeurope
```

## Kjøring
Start scriptet med:
```bash
python chatgpt_voice.py
```

Skriv inn spørsmål i terminalen. Svaret leses opp og andenebbet beveger seg synkront med talen.

## Filer
- `chatgpt_voice.py` – Hovedscript for ChatGPT, TTS og nebb
- `duck_beak.py` – Klasse og logikk for å styre andenebbet
- `.env` – Dine API-nøkler

## Tips
- Juster variabelen `octaves` i `chatgpt_voice.py` for mer/mindre "Donald Duck"-effekt
- Du kan endre stemme eller talehastighet i SSML-delen av koden
- Husk å bruke riktig GPIO-pin for servo

## Feilsøking
- Får du ikke lyd? Sjekk at PortAudio og ffmpeg er installert, og at du bruker riktig lydutgang
- Får du ikke bevegelse? Sjekk at pigpio kjører og at servoen er koblet riktig
- API-feil? Sjekk at nøklene og regionene i `.env` er korrekte

---
Lykke til med snakkende andeprosjekt! 🦆