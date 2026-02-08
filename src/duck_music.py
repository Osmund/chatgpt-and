"""
Duck Music Module
Handles song playback with synchronized beak movement.
"""

import os
import time
import threading
import numpy as np
from pydub import AudioSegment
import sounddevice as sd

from scripts.hardware.rgb_duck import set_red, stop_blink, set_intensity
from src.duck_config import (
    BEAK_CHUNK_MS, SONG_STOP_FILE
)
from src.duck_audio import find_hifiberry_output
from src.duck_settings import get_settings


def play_song(song_path, beak, speech_config, announce=True):
    """
    Spiller av en sang med synkronisert nebb-bevegelse og LED-effekter.
    
    Args:
        song_path: Sti til sangmappe med duck_mix.wav og vocals_duck.wav
        beak: Beak objekt for nebb-kontroll
        speech_config: Azure speech config for annonsering
        announce: Om sangen skal annonseres med TTS før avspilling (default: True)
    """
    from src.duck_audio import speak  # Import her for å unngå circular import
    
    print(f"Spiller sang: {song_path}", flush=True)
    stop_blink()
    
    # Sjekk at mappen finnes
    if not os.path.exists(song_path):
        print(f"Sangmappe finnes ikke: {song_path}", flush=True)
        return
    
    # Finn filene
    mix_file = os.path.join(song_path, "duck_mix.wav")
    vocals_file = os.path.join(song_path, "vocals_duck.wav")
    
    if not os.path.exists(mix_file) or not os.path.exists(vocals_file):
        print(f"Mangler duck_mix.wav eller vocals_duck.wav i {song_path}", flush=True)
        return
    
    # Ekstraher artistnavn og sangtittel fra mappesti
    # Format: "Artist - Sangtittel"
    song_folder_name = os.path.basename(song_path)
    
    # Annonser sangen før avspilling (hopp over hvis allerede annonsert, f.eks. av AI)
    if announce:
        if ' - ' in song_folder_name:
            artist, song_title = song_folder_name.split(' - ', 1)
            announcement = f"Nå skal jeg synge {song_title} av {artist}!"
        else:
            announcement = f"Nå skal jeg synge {song_folder_name}!"
        
        print(f"Annonserer sang: {announcement}", flush=True)
        speak(announcement, speech_config, beak)
    else:
        print(f"Hopper over annonsering (allerede annonsert)", flush=True)
    
    # Litt pause før sang starter
    time.sleep(0.5)
    
    set_red()  # LED rød når anda synger
    
    # Les nebb og volum fra DuckSettings
    settings = get_settings()
    beak_enabled = settings.beak_enabled
    volume_value = settings.volume
    
    volume_gain = volume_value / 50.0
    
    print(f"Spiller sang med volum: {volume_value}% (gain: {volume_gain:.2f}), Nebbet: {'på' if beak_enabled else 'av'}", flush=True)
    
    try:
        # Last inn begge filer
        mix_sound = AudioSegment.from_wav(mix_file)
        vocals_sound = AudioSegment.from_wav(vocals_file)
        
        # Sjekk at de er like lange (ca)
        if abs(len(mix_sound) - len(vocals_sound)) > 1000:  # 1 sekund toleranse
            print(f"Advarsel: Mix og vocals har ulik lengde ({len(mix_sound)}ms vs {len(vocals_sound)}ms)", flush=True)
        
        # Konverter mix til numpy array for avspilling
        mix_samples = np.array(mix_sound.get_array_of_samples(), dtype=np.float32)
        mix_samples = mix_samples / (2**15)  # Normaliser til -1.0 til 1.0
        
        # Anvend volum
        mix_samples = mix_samples * volume_gain
        
        # Sjekk om audio er stereo og reshape hvis nødvendig
        n_channels = mix_sound.channels
        framerate = mix_sound.frame_rate
        
        print(f"Audio format: {framerate} Hz, {n_channels} kanal(er), {len(mix_samples)} samples", flush=True)
        
        # Hvis stereo, reshape til (samples, 2)
        if n_channels == 2:
            mix_samples = mix_samples.reshape(-1, 2)
        else:
            # Mono, reshape til (samples, 1) for konsistens
            mix_samples = mix_samples.reshape(-1, 1)
        
        # Konverter vocals til numpy array for amplitude detection
        vocals_samples = np.array(vocals_sound.get_array_of_samples(), dtype=np.float32)
        vocals_samples = vocals_samples / (2**15)
        
        # Vocals skal alltid være mono for amplitude detection
        if vocals_sound.channels == 2:
            # Konverter stereo til mono (gjennomsnitt av venstre og høyre)
            vocals_samples = vocals_samples.reshape(-1, 2).mean(axis=1)
        
        # Finn output device
        output_device = find_hifiberry_output()
        
        # Avspilling med sounddevice
        chunk_size = int(framerate * BEAK_CHUNK_MS / 1000.0)
        mix_idx = 0
        
        # Beregn lengder for synkronisering
        total_frames = len(mix_samples)  # Antall frames i mix
        vocals_length = len(vocals_samples)  # Antall samples i vocals
        
        # Flag for stopp
        song_stopped = False
        
        # Nebb-tråd
        nebb_stop = threading.Event()
        led_stop = threading.Event()
        
        def beak_controller():
            nonlocal mix_idx, song_stopped
            while not nebb_stop.is_set() and not song_stopped:
                # Sjekk for stopp-forespørsel
                if os.path.exists(SONG_STOP_FILE):
                    try:
                        os.remove(SONG_STOP_FILE)
                        print("Sang stoppet av bruker", flush=True)
                        song_stopped = True
                        nebb_stop.set()
                        break
                    except:
                        pass
                
                # Beregn vocals position basert på mix playback progress
                if total_frames > 0:
                    progress = min(mix_idx / total_frames, 1.0)
                    vocals_pos = int(progress * vocals_length)
                    vocals_pos = min(vocals_pos, vocals_length - chunk_size)
                    
                    if vocals_pos >= 0 and vocals_pos < vocals_length:
                        chunk = vocals_samples[vocals_pos:vocals_pos+chunk_size]
                        if len(chunk) > 0:
                            amp = np.sqrt(np.mean(chunk**2))
                            open_pct = min(max(amp * 3.5, 0.05), 1.0)
                            beak.open_pct(open_pct)
                
                time.sleep(BEAK_CHUNK_MS / 1000.0)
        
        def led_controller():
            """LED blinker i takt med musikken"""
            nonlocal mix_idx, song_stopped
            
            # For LED, bruk mix audio (kan være stereo)
            # Hvis stereo, konverter til mono for amplitude
            if n_channels == 2:
                mix_mono = mix_samples.mean(axis=1)  # Gjennomsnitt av venstre og høyre
            else:
                mix_mono = mix_samples.flatten()
            
            while not led_stop.is_set() and mix_idx < len(mix_mono):
                # Sjekk for stopp
                if song_stopped:
                    break
                
                # Bruk mix_idx for å lese riktig posisjon
                current_pos = min(mix_idx, len(mix_mono) - 1)
                chunk = mix_mono[current_pos:current_pos+chunk_size]
                if len(chunk) > 0:
                    amp = np.sqrt(np.mean(np.abs(chunk)**2))
                    # Skaler amplitude til 0.0-1.0 range, med litt boost
                    intensity = min(amp * 4.0, 1.0)
                    # Sett minimum intensitet så LED ikke slukker helt
                    intensity = max(intensity, 0.1)
                    set_intensity(intensity)
                
                time.sleep(BEAK_CHUNK_MS / 1000.0)
        
        # Start nebb og LED tråder
        if beak_enabled and beak:
            beak_thread = threading.Thread(target=beak_controller, daemon=True)
            beak_thread.start()
        
        led_thread = threading.Thread(target=led_controller, daemon=True)
        led_thread.start()
        
        # Spill av mix med sounddevice (blocking)
        with sd.OutputStream(samplerate=framerate, channels=n_channels, device=output_device, dtype='float32') as stream:
            while mix_idx < len(mix_samples) and not song_stopped:
                # Sjekk for stopp-forespørsel i main thread også
                if os.path.exists(SONG_STOP_FILE):
                    try:
                        os.remove(SONG_STOP_FILE)
                        print("Sang stoppet av bruker (main thread)", flush=True)
                        song_stopped = True
                        break
                    except:
                        pass
                
                chunk = mix_samples[mix_idx:mix_idx+4096]
                if len(chunk) < 4096:
                    # Pad siste chunk med stillhet
                    if n_channels == 2:
                        chunk = np.pad(chunk, ((0, 4096 - len(chunk)), (0, 0)), mode='constant')
                    else:
                        chunk = np.pad(chunk, ((0, 4096 - len(chunk)), (0, 0)), mode='constant')
                
                stream.write(chunk)
                mix_idx += 4096
        
        # Stopp nebb og LED tråder
        if beak_enabled and beak:
            nebb_stop.set()
            beak_thread.join(timeout=1.0)
        
        led_stop.set()
        led_thread.join(timeout=1.0)
        
        # Lukk nebbet litt og reset LED til rød
        if beak:
            beak.open_pct(0.05)
        set_red()  # Tilbake til rød LED
        if beak:
            beak.open_pct(0.05)
        
        print("Sang ferdig!", flush=True)
        
    except Exception as e:
        print(f"Feil ved avspilling av sang: {e}", flush=True)
        import traceback
        traceback.print_exc()
