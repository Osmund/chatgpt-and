#!/usr/bin/env python3
"""
Generer forhåndsinnspilt audio for hotspot-melding
Kjør dette scriptet mens du har WiFi for å lage audio-filen
"""

import os
import sys
from pathlib import Path
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Azure TTS config
tts_key = os.getenv("AZURE_TTS_KEY")
tts_region = os.getenv("AZURE_TTS_REGION")

if not tts_key or not tts_region:
    print("❌ Azure TTS credentials ikke funnet i .env")
    sys.exit(1)

# Hotspot message
HOTSPOT_MESSAGE = "Jeg kunne ikke koble til WiFi, så jeg starter en hotspot du kan koble til med telefonen. Koble til nettverket Chat G P T bindestrek Duck. Altså hot spotten heter Chat G P T bindestrek duck. Passord til hot spotten er kvakk kvakk, jeg gjentar kvakk kvakk . Gå deretter til ip adressen 192 punkt 168 punkt 50 punkt 1 i nettleseren på mobilen for å sette anda opp med WiFi."

# Output file
OUTPUT_DIR = Path("/home/admog/Code/chatgpt-and/audio")
OUTPUT_FILE = OUTPUT_DIR / "hotspot_announcement.wav"

# Create audio directory if it doesn't exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configure speech
speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
speech_config.speech_synthesis_voice_name = "nb-NO-PernilleNeural"

# Set output to WAV file
audio_config = speechsdk.audio.AudioOutputConfig(filename=str(OUTPUT_FILE))

# Create synthesizer
synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

print(f"🎤 Genererer hotspot-melding...")
print(f"   Melding: {HOTSPOT_MESSAGE[:50]}...")
print(f"   Output: {OUTPUT_FILE}")

# Synthesize
result = synthesizer.speak_text_async(HOTSPOT_MESSAGE).get()

if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print(f"✅ Audio generert vellykket!")
    print(f"   Filstørrelse: {OUTPUT_FILE.stat().st_size} bytes")
    print(f"\nFilen vil bli brukt når Anda starter i hotspot-modus uten internett.")
elif result.reason == speechsdk.ResultReason.Canceled:
    cancellation = result.cancellation_details
    print(f"❌ Audio-generering feilet: {cancellation.reason}")
    if cancellation.error_details:
        print(f"   Detaljer: {cancellation.error_details}")
    sys.exit(1)
