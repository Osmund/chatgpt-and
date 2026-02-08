"""
Duck Speech Module
Handles wake word detection and speech recognition (STT).
Wake word engine is selected via WAKE_WORD_ENGINE in .env.
"""

import sounddevice as sd
import numpy as np
import time
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

from scripts.hardware.rgb_duck import set_blue, set_green, off, pulse_blue, pulse_yellow, stop_blink
from src.duck_config import (
    PORCUPINE_ACCESS_KEY_ENV, WAKE_WORD_PATH,
    AZURE_SPEECH_KEY_ENV, AZURE_SPEECH_REGION_ENV
)
from src.duck_audio import find_usb_microphone, find_usb_mic_alsa_card
from src.duck_sleep import is_sleeping
from src.wake_word import get_wait_for_wake_word


# Delegate to the configured wake word engine
_engine_wait = get_wait_for_wake_word()


def wait_for_wake_word():
    """
    Venter på wake word og eksterne meldinger.
    Delegerer til konfigurert engine (Porcupine eller OpenWakeWord).
    Returnerer None ved wake word, tekst ved ekstern melding.
    """
    return _engine_wait()


def recognize_speech_from_mic(device_name=None):
    """
    Gjenkjenner tale fra mikrofon med Azure Speech-to-Text.
    Returnerer gjenkjent tekst eller None ved feil.
    """
    set_green()  # LED grønn mens bruker snakker
    stt_key = os.getenv("AZURE_STT_KEY")
    stt_region = os.getenv("AZURE_STT_REGION")
    silence_timeout = os.getenv("AZURE_STT_SILENCE_TIMEOUT_MS", "1200")  # Default 1200ms hvis ikke satt
    speech_config = speechsdk.SpeechConfig(subscription=stt_key, region=stt_region)
    
    # Finn USB mikrofon dynamisk (ALSA card kan endre seg ved reboot)
    usb_alsa_device = find_usb_mic_alsa_card()
    devices_to_try = [usb_alsa_device, "default"]  # plughw gir bedre kompatibilitet enn hw
    
    for attempt, dev in enumerate(devices_to_try):
        try:
            print(f"Prøver Azure STT med device: {dev}", flush=True)
            audio_config = speechsdk.audio.AudioConfig(device_name=dev)
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config, language="nb-NO")
            prop = speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs
            speech_recognizer.properties.set_property(prop, silence_timeout)
            print(f"Snakk nå (device {dev}, timeout {silence_timeout}ms)...", flush=True)
            t0 = time.time()
            result = speech_recognizer.recognize_once()
            t1 = time.time()
            elapsed = t1 - t0
            print(f"Azure STT tid: {elapsed:.2f} sekunder", flush=True)
            # IKKE slå av LED her - la hovedløkken håndtere LED-overgangen
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                print(f"Du sa: {result.text}", flush=True)
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                print("Ingen tale gjenkjent.", flush=True)
                return None
            else:
                print(f"Talegjenkjenning feilet: {result.reason}", flush=True)
                return None
        except Exception as e:
            print(f"Azure STT feil med device {dev}: {e}", flush=True)
            if attempt < len(devices_to_try) - 1:
                print(f"Prøver neste device...", flush=True)
                time.sleep(0.5)
                continue
            else:
                print("Alle devices feilet", flush=True)
                # IKKE slå av LED her - la hovedløkken håndtere det
                return None
