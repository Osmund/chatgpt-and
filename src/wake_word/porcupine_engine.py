"""
Porcupine Wake Word Engine
Tuned for optimal detection on Raspberry Pi with USB microphone.
Uses Picovoice Porcupine for wake word detection.
"""

import sounddevice as sd
import numpy as np
import pvporcupine
import time
import os
from dotenv import load_dotenv

from scripts.hardware.rgb_duck import set_blue, pulse_blue, pulse_yellow, stop_blink
from src.duck_config import (
    DUCK_NAME, WAKE_WORD_MODEL_PATH, WAKE_WORD_SENSITIVITY
)
from src.duck_audio import find_usb_microphone
from src.duck_sleep import is_sleeping


def wait_for_wake_word():
    """
    Venter på wake word via Porcupine og eksterne meldinger.
    Returnerer None ved wake word, tekst ved ekstern melding.
    """
    set_blue()
    
    load_dotenv()
    access_key = os.getenv('PICOVOICE_API_KEY')
    if not access_key:
        print("⚠️  PICOVOICE_API_KEY mangler i .env - Porcupine kan ikke starte!", flush=True)
        print("Legg til: PICOVOICE_API_KEY=din_api_nøkkel i .env", flush=True)
        time.sleep(5)
        return None
    
    # Porcupine modell sti fra config
    keyword_path = WAKE_WORD_MODEL_PATH
    if not os.path.exists(keyword_path):
        print(f"⚠️  Porcupine modell ikke funnet: {keyword_path}", flush=True)
        time.sleep(5)
        return None
    
    duck_name = DUCK_NAME
    print(f"Si '{duck_name}' for å vekke anda!", flush=True)
    
    # Finn USB mikrofon dynamisk
    usb_mic_device = find_usb_microphone()
    
    # Initialiser Porcupine
    porcupine = None
    audio_stream = None
    
    try:
        # Les sensitivity fra konfigurasjonsfil, fallback til config, fallback til 0.9
        sensitivity = WAKE_WORD_SENSITIVITY
        sensitivity_file = "wake_word_sensitivity.txt"
        if os.path.exists(sensitivity_file):
            try:
                with open(sensitivity_file, 'r') as f:
                    sensitivity = float(f.read().strip())
                    print(f"Loaded wake word sensitivity: {sensitivity}", flush=True)
            except Exception as e:
                print(f"⚠️ Error reading sensitivity file, using default {WAKE_WORD_SENSITIVITY}: {e}", flush=True)
        
        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[keyword_path],
            sensitivities=[sensitivity]
        )
        
        print(f"Porcupine startet! Sample rate: {porcupine.sample_rate} Hz, Frame length: {porcupine.frame_length}", flush=True)
        
        # USB mikrofon støtter 48000 Hz, men Porcupine trenger 16000 Hz
        mic_sample_rate = 48000
        porcupine_sample_rate = porcupine.sample_rate  # 16000 Hz
        ratio = mic_sample_rate / porcupine_sample_rate  # 3.0
        mic_frame_length = int(porcupine.frame_length * ratio)  # 512 * 3 = 1536
        
        # Bruk nøyaktig én frame per buffer for bedre deteksjon
        mic_buffer_size = mic_frame_length  # 1536 samples
        
        # CRITICAL: sounddevice trenger større latency buffer for å unngå overflow
        latency_setting = 0.5  # 500ms buffer
        
        print(f"Decimation: {mic_sample_rate} Hz -> {porcupine_sample_rate} Hz (ratio: {int(ratio)}:1), buffer: {mic_buffer_size}", flush=True)
        print(f"Audio latency: {latency_setting} (reduces overflow risk)", flush=True)
        
        # Prøv å åpne mikrofon-input i en retry-loop
        while True:
            try:
                audio_stream = sd.RawInputStream(
                    samplerate=mic_sample_rate,
                    blocksize=mic_buffer_size,
                    dtype='int16',
                    channels=1,
                    device=usb_mic_device,
                    latency=latency_setting
                )
                audio_stream.start()
                
                # Sleep mode tracking for LED
                sleep_led_started = False
                
                # Event bus sjekking
                event_check_counter = 0
                sleep_check_counter = 0
                
                while True:
                    # Sjekk sleep mode kun hver 100. iteration (~3.2s) for ytelse
                    sleep_check_counter += 1
                    if sleep_check_counter >= 100:
                        sleep_check_counter = 0
                        
                        if is_sleeping():
                            if not sleep_led_started:
                                from chatgpt_voice import is_hotspot_active
                                if is_hotspot_active():
                                    pulse_yellow()
                                else:
                                    pulse_blue()
                                sleep_led_started = True
                                print("💤 [wait_for_wake_word] Sleep mode detektert - starter pulsering", flush=True)
                        else:
                            if sleep_led_started:
                                stop_blink()
                                set_blue()
                                sleep_led_started = False
                                print("⏰ [wait_for_wake_word] Sleep mode deaktivert - blå LED", flush=True)
                    
                    # Sjekk event bus hver ~1.6s (50 frames × 32ms)
                    event_check_counter += 1
                    if event_check_counter >= 50:
                        event_check_counter = 0
                        
                        from src.duck_event_bus import get_event_bus, Event
                        bus = get_event_bus()
                        event = bus.get_nowait()
                        if event:
                            event_type, data = event
                            if event_type == Event.EXTERNAL_MESSAGE:
                                message = data if isinstance(data, str) else str(data)
                                print(f"Ekstern melding mottatt: {message}", flush=True)
                                if message == '__START_CONVERSATION__':
                                    return '__START_CONVERSATION__'
                                else:
                                    return message
                            elif event_type == Event.SMS_ANNOUNCEMENT:
                                print(f"📬 SMS announcement: {str(data)[:50]}...", flush=True)
                                return f"__SMS_ANNOUNCEMENT__{data}"
                            elif event_type == Event.DUCK_MESSAGE:
                                announcement = data.get('announcement') if isinstance(data, dict) else data
                                if announcement:
                                    print(f"🦆💬 Duck message: {announcement[:50]}...", flush=True)
                                    return f"__DUCK_MESSAGE__{announcement}"
                            elif event_type == Event.HUNGER_ANNOUNCEMENT:
                                print(f"😋 Hunger announcement: {str(data)[:50]}...", flush=True)
                                return f"__HUNGER_ANNOUNCEMENT__{data}"
                            elif event_type == Event.HUNGER_FED:
                                print(f"😋 Fed from control panel: {data}", flush=True)
                                return f"__HUNGER_FED__{data}"
                            elif event_type == Event.HOTSPOT_ANNOUNCEMENT:
                                print(f"📡 Hotspot announcement: {str(data)[:50]}...", flush=True)
                                return f"__HOTSPOT_ANNOUNCEMENT__{data}"
                            elif event_type == Event.REMINDER:
                                announcement = data.get('announcement') if isinstance(data, dict) else data
                                is_alarm = data.get('is_alarm', False) if isinstance(data, dict) else False
                                if announcement:
                                    emoji = "⏰" if is_alarm else "🔔"
                                    print(f"{emoji} Reminder mottatt i wake word loop: {announcement[:50]}...", flush=True)
                                    return f"__REMINDER__{announcement}"
                            elif event_type == Event.PLAY_SONG:
                                song_path = data.get('path') if isinstance(data, dict) else data
                                if song_path:
                                    print(f"Sang-forespørsel mottatt: {song_path}", flush=True)
                                    return f'__PLAY_SONG__{song_path}'
                    
                    # Les audio fra mikrofon
                    pcm_48k, overflowed = audio_stream.read(mic_buffer_size)
                    
                    if overflowed:
                        print("⚠️ Audio buffer overflow - frames lost! Wake word may be missed.", flush=True)
                    
                    # Skip wake word detection i sleep mode
                    if sleep_led_started:
                        continue
                    
                    # Konverter til numpy array
                    pcm_48k_array = np.frombuffer(pcm_48k, dtype=np.int16)
                    
                    # Decimation 48kHz -> 16kHz (ratio 3:1)
                    pcm_16k = pcm_48k_array[::3]
                    
                    # Sjekk for wake word
                    keyword_index = porcupine.process(pcm_16k)
                    if keyword_index >= 0:
                        print(f"Wake word '{duck_name}' oppdaget!", flush=True)
                        return None
                        
            except Exception as e:
                print(f"Input-enhet ikke klar ennå (prøver igjen om 2s): {e}", flush=True)
                time.sleep(2)
                continue
                
    finally:
        if audio_stream is not None:
            audio_stream.stop()
            audio_stream.close()
        if porcupine is not None:
            porcupine.delete()
