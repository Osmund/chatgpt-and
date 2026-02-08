"""
OpenWakeWord Engine
Tuned for optimal detection on Raspberry Pi with USB microphone.
Uses OpenWakeWord for wake word detection (no API key needed).
"""

import sounddevice as sd
import numpy as np
import time
import os
from dotenv import load_dotenv

from scripts.hardware.rgb_duck import set_blue, pulse_blue, pulse_yellow, stop_blink
from src.duck_config import (
    DUCK_NAME, WAKE_WORD_MODEL_PATH, WAKE_WORD_THRESHOLD
)
from src.duck_audio import find_usb_microphone
from src.duck_sleep import is_sleeping


def wait_for_wake_word():
    """
    Venter på wake word via OpenWakeWord og eksterne meldinger.
    Returnerer None ved wake word, tekst ved ekstern melding.
    """
    set_blue()
    
    # Import openWakeWord her for å unngå import-feil på ender som bruker Porcupine
    try:
        from openwakeword.model import Model
    except ImportError:
        print("⚠️  openwakeword ikke installert! Kjør: pip install openwakeword", flush=True)
        time.sleep(5)
        return None
    
    # openWakeWord modell sti fra config
    model_path = WAKE_WORD_MODEL_PATH
    if not os.path.exists(model_path):
        print(f"⚠️  openWakeWord modell ikke funnet: {model_path}", flush=True)
        time.sleep(5)
        return None
    
    duck_name = DUCK_NAME
    print(f"Si '{duck_name}' for å vekke anda!", flush=True)
    
    # Finn USB mikrofon dynamisk
    usb_mic_device = find_usb_microphone()
    
    # Initialiser openWakeWord
    oww_model = None
    audio_stream = None
    
    try:
        oww_model = Model(
            wakeword_model_paths=[model_path]
        )
        
        print(f"openWakeWord startet! Modell: {duck_name}", flush=True)
        
        # USB mikrofonen støtter 48kHz, men openWakeWord trenger 16kHz
        mic_sample_rate = 48000
        oww_sample_rate = 16000
        downsample_ratio = mic_sample_rate // oww_sample_rate  # 3
        
        # openWakeWord prosesserer multiples av 80ms
        # 240ms (3x80ms) - optimal balanse mellom kontekst og respons
        chunk_duration_ms = 240
        oww_frame_length = int(oww_sample_rate * chunk_duration_ms / 1000)  # 3840 samples @ 16kHz
        mic_frame_length = oww_frame_length * downsample_ratio  # 11520 samples @ 48kHz
        
        mic_buffer_size = mic_frame_length
        
        # Latency buffer for å unngå overflow
        latency_setting = 0.5  # 500ms buffer
        
        print(f"Audio: {mic_sample_rate} Hz -> {oww_sample_rate} Hz (downsample 3:1)", flush=True)
        print(f"Chunk: {chunk_duration_ms}ms ({oww_frame_length} samples @ 16kHz)", flush=True)
        print(f"Audio latency: {latency_setting}", flush=True)
        
        # Wake word detection threshold
        wake_threshold = WAKE_WORD_THRESHOLD
        
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
                    # Sjekk sleep mode kun hver 100. iteration
                    sleep_check_counter += 1
                    if sleep_check_counter >= 100:
                        sleep_check_counter = 0
                        
                        if is_sleeping():
                            if not sleep_led_started:
                                try:
                                    from chatgpt_voice import is_hotspot_active
                                    if is_hotspot_active():
                                        pulse_yellow()
                                    else:
                                        pulse_blue()
                                except ImportError:
                                    pulse_blue()
                                sleep_led_started = True
                                print("💤 [wait_for_wake_word] Sleep mode detektert - starter pulsering", flush=True)
                        else:
                            if sleep_led_started:
                                stop_blink()
                                set_blue()
                                sleep_led_started = False
                                print("⏰ [wait_for_wake_word] Sleep mode deaktivert - blå LED", flush=True)
                    
                    # Sjekk event bus hver ~50 frames
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
                        print("⚠️ Audio buffer overflow", flush=True)
                    
                    # Skip hvis sleep mode
                    if sleep_led_started:
                        continue
                    
                    # Konverter til numpy array
                    pcm_48k_array = np.frombuffer(pcm_48k, dtype=np.int16)
                    
                    # Enkel downsample: ta hver 3. sample (48kHz -> 16kHz)
                    pcm_16k = pcm_48k_array[::downsample_ratio]
                    
                    # Sjekk for wake word
                    prediction = oww_model.predict(pcm_16k)
                    
                    # Debug: vis scores over 0.01
                    if duck_name in prediction and prediction[duck_name] > 0.01:
                        print(f"🔍 {duck_name} score: {prediction[duck_name]:.3f} (threshold: {wake_threshold})", flush=True)
                    
                    # Sjekk om wake word ble detektert
                    if duck_name in prediction and prediction[duck_name] >= wake_threshold:
                        print(f"✅ Wake word '{duck_name}' oppdaget! (score: {prediction[duck_name]:.3f})", flush=True)
                        return None
                        
            except Exception as e:
                print(f"Input-enhet ikke klar ennå (prøver igjen om 2s): {e}", flush=True)
                time.sleep(2)
                continue
                
    finally:
        if audio_stream is not None:
            audio_stream.stop()
            audio_stream.close()
        if oww_model is not None:
            del oww_model
