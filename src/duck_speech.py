"""
Duck Speech Module
Handles wake word detection and speech recognition (STT).
"""

import sounddevice as sd
import numpy as np
from scipy.signal import resample
import pvporcupine
import time
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

from scripts.hardware.rgb_duck import set_blue, set_green, off, pulse_blue, stop_blink
from src.duck_config import (
    MESSAGE_FILE, SONG_REQUEST_FILE,
    PORCUPINE_ACCESS_KEY_ENV, WAKE_WORD_PATH,
    AZURE_SPEECH_KEY_ENV, AZURE_SPEECH_REGION_ENV
)
from src.duck_audio import find_usb_microphone, find_usb_mic_alsa_card
from src.duck_sleep import is_sleeping


def wait_for_wake_word():
    """
    Venter på wake word 'Samantha' og eksterne meldinger/sang-forespørsler.
    Returnerer None ved wake word, tekst ved ekstern melding, '__PLAY_SONG__path' ved sang.
    """
    set_blue()
    
    # Last inn Picovoice API-nøkkel fra .env
    load_dotenv()
    access_key = os.getenv('PICOVOICE_API_KEY')
    if not access_key:
        print("⚠️  PICOVOICE_API_KEY mangler i .env - Porcupine kan ikke starte!", flush=True)
        print("Legg til: PICOVOICE_API_KEY=din_api_nøkkel i .env", flush=True)
        time.sleep(5)
        return None
    
    # Porcupine modell sti
    keyword_path = "porcupine/samantha_en_raspberry-pi_v4_0_0.ppn"
    if not os.path.exists(keyword_path):
        print(f"⚠️  Porcupine modell ikke funnet: {keyword_path}", flush=True)
        time.sleep(5)
        return None
    
    print("Si 'Samantha' for å vekke anda!", flush=True)
    
    # Finn USB mikrofon dynamisk
    usb_mic_device = find_usb_microphone()
    
    # Initialiser Porcupine
    porcupine = None
    audio_stream = None
    
    try:
        # Les sensitivity fra konfigurasjonsfil hvis den finnes
        sensitivity = 0.9  # Default
        sensitivity_file = "wake_word_sensitivity.txt"
        if os.path.exists(sensitivity_file):
            try:
                with open(sensitivity_file, 'r') as f:
                    sensitivity = float(f.read().strip())
                    print(f"Loaded wake word sensitivity: {sensitivity}", flush=True)
            except Exception as e:
                print(f"⚠️ Error reading sensitivity file, using default 0.9: {e}", flush=True)
        
        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[keyword_path],
            sensitivities=[sensitivity]  # 0.0 til 1.0, høyere = mer sensitiv
        )
        
        print(f"Porcupine startet! Sample rate: {porcupine.sample_rate} Hz, Frame length: {porcupine.frame_length}", flush=True)
        
        # USB mikrofon støtter 48000 Hz, men Porcupine trenger 16000 Hz
        # Vi må resample
        mic_sample_rate = 48000
        porcupine_sample_rate = porcupine.sample_rate  # 16000 Hz
        ratio = mic_sample_rate / porcupine_sample_rate  # 3.0
        mic_frame_length = int(porcupine.frame_length * ratio)  # 512 * 3 = 1536
        
        # Bruk nøyaktig én frame per buffer for bedre deteksjon
        # Dette unngår at wake word blir delt over chunk-grenser
        mic_buffer_size = mic_frame_length  # 1536 samples
        
        print(f"Resampling: {mic_sample_rate} Hz -> {porcupine_sample_rate} Hz (ratio: {ratio}), buffer: {mic_buffer_size}", flush=True)
        
        # Prøv å åpne mikrofon-input i en retry-loop
        while True:
            try:
                audio_stream = sd.RawInputStream(
                    samplerate=mic_sample_rate,
                    blocksize=mic_buffer_size,
                    dtype='int16',
                    channels=1,
                    device=usb_mic_device
                )
                audio_stream.start()
                
                # Sleep mode tracking for LED
                sleep_led_started = False
                
                # Optimization counters for reduced file I/O
                file_check_counter = 0
                sleep_check_counter = 0
                
                while True:
                    # Sjekk sleep mode kun hver 100. iteration (~3.2s) for ytelse
                    sleep_check_counter += 1
                    if sleep_check_counter >= 100:
                        sleep_check_counter = 0
                        
                        if is_sleeping():
                            # Start blå pulsering hvis ikke allerede startet
                            if not sleep_led_started:
                                pulse_blue()
                                sleep_led_started = True
                                print("💤 [wait_for_wake_word] Sleep mode detektert - starter blå pulsering", flush=True)
                        else:
                            # Stopp LED hvis sleep mode deaktiveres
                            if sleep_led_started:
                                stop_blink()
                                set_blue()  # Tilbake til blå LED (klar for wake word)
                                sleep_led_started = False
                                print("⏰ [wait_for_wake_word] Sleep mode deaktivert - blå LED", flush=True)
                    
                    # Sjekk eksterne meldinger kun hver 50. iteration (~1.6s) for minimal disk I/O
                    file_check_counter += 1
                    check_files = file_check_counter >= 50
                    if check_files:
                        file_check_counter = 0
                    
                    # Sjekk om det finnes en ekstern melding
                    if check_files and os.path.exists(MESSAGE_FILE):
                        try:
                            with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
                                message = f.read().strip()
                            os.remove(MESSAGE_FILE)
                            if message:
                                print(f"Ekstern melding mottatt: {message}", flush=True)
                                if message == '__START_CONVERSATION__':
                                    return '__START_CONVERSATION__'
                                else:
                                    return message
                        except Exception as e:
                            print(f"Feil ved lesing av meldingsfil: {e}", flush=True)
                    
                    # Sjekk om det finnes SMS-annonseringer
                    sms_announcement_file = '/tmp/duck_sms_announcement.txt'
                    if os.path.exists(sms_announcement_file):
                        try:
                            with open(sms_announcement_file, 'r', encoding='utf-8') as f:
                                announcement = f.read().strip()
                            os.remove(sms_announcement_file)
                            if announcement:
                                print(f"📬 SMS announcement: {announcement[:50]}...", flush=True)
                                return f"__SMS_ANNOUNCEMENT__{announcement}"
                        except Exception as e:
                            print(f"⚠️ Error reading SMS announcement: {e}", flush=True)
                    
                    # Sjekk om det finnes hunger-annonseringer
                    hunger_announcement_file = '/tmp/duck_hunger_announcement.txt'
                    if check_files and os.path.exists(hunger_announcement_file):
                        try:
                            with open(hunger_announcement_file, 'r', encoding='utf-8') as f:
                                announcement = f.read().strip()
                            os.remove(hunger_announcement_file)
                            if announcement:
                                print(f"😋 Hunger announcement: {announcement[:50]}...", flush=True)
                                return f"__HUNGER_ANNOUNCEMENT__{announcement}"
                        except Exception as e:
                            print(f"⚠️ Error reading hunger announcement: {e}", flush=True)
                    
                    # Sjekk om Anda ble matet fra kontrollpanelet
                    hunger_fed_file = '/tmp/duck_hunger_fed.txt'
                    if check_files and os.path.exists(hunger_fed_file):
                        try:
                            with open(hunger_fed_file, 'r', encoding='utf-8') as f:
                                announcement = f.read().strip()
                            os.remove(hunger_fed_file)
                            if announcement:
                                print(f"😋 Fed from control panel: {announcement}", flush=True)
                                return f"__HUNGER_FED__{announcement}"
                        except Exception as e:
                            print(f"⚠️ Error reading hunger fed announcement: {e}", flush=True)
                    
                    # Sjekk om det finnes hotspot-annonseringer
                    hotspot_announcement_file = '/tmp/duck_hotspot_announcement.txt'
                    if check_files and os.path.exists(hotspot_announcement_file):
                        try:
                            with open(hotspot_announcement_file, 'r', encoding='utf-8') as f:
                                announcement = f.read().strip()
                            os.remove(hotspot_announcement_file)
                            if announcement:
                                print(f"📡 Hotspot announcement: {announcement[:50]}...", flush=True)
                                return f"__HOTSPOT_ANNOUNCEMENT__{announcement}"
                        except Exception as e:
                            print(f"⚠️ Error reading hotspot announcement: {e}", flush=True)
                    
                    # Sjekk om det finnes en sang-forespørsel
                    if check_files and os.path.exists(SONG_REQUEST_FILE):
                        try:
                            with open(SONG_REQUEST_FILE, 'r', encoding='utf-8') as f:
                                song_path = f.read().strip()
                            os.remove(SONG_REQUEST_FILE)
                            if song_path:
                                print(f"Sang-forespørsel mottatt: {song_path}", flush=True)
                                return f'__PLAY_SONG__{song_path}'  # Spesiell trigger for sang
                        except Exception as e:
                            print(f"Feil ved lesing av sang-forespørsel: {e}", flush=True)
                    
                    # Les audio fra mikrofon (gjøres hver iterasjon for kontinuerlig deteksjon)
                    pcm_48k, overflowed = audio_stream.read(mic_buffer_size)
                    
                    # Skip wake word detection hvis vi er i sleep mode
                    if sleep_led_started:  # Raskere sjekk enn is_sleeping() hver gang
                        continue  # Hopp over wake word prosessering
                    
                    # Konverter til numpy array
                    pcm_48k_array = np.frombuffer(pcm_48k, dtype=np.int16)
                    
                    # Resample til 16000 Hz (én frame per buffer nå)
                    pcm_16k_array = resample(pcm_48k_array, porcupine.frame_length)
                    pcm_16k = pcm_16k_array.astype(np.int16)
                    
                    # Sjekk for wake word
                    keyword_index = porcupine.process(pcm_16k)
                    if keyword_index >= 0:
                        print("Wake word 'Samantha' oppdaget!", flush=True)
                        return None  # Wake word oppdaget
                        
            except Exception as e:
                print(f"Input-enhet ikke klar ennå (prøver igjen om 2s): {e}", flush=True)
                time.sleep(2)
                continue
                
    finally:
        # Cleanup
        if audio_stream is not None:
            audio_stream.stop()
            audio_stream.close()
        if porcupine is not None:
            porcupine.delete()


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
