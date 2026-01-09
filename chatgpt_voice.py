from pydub import AudioSegment
from scipy.signal import resample
import sounddevice as sd
import time
import random
import threading
from duck_beak import Beak, CLOSE_DEG, OPEN_DEG, TRIM_DEG, JITTER, BEAT_MS_MIN, BEAT_MS_MAX, SERVO_CHANNEL
import requests                                                                                                                                                                                           
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import numpy as np
from rgb_duck import set_blue, set_red, set_green, off, blink_yellow, stop_blink, blink_yellow_purple, set_intensity
import pvporcupine
import json
import sys
import signal
import atexit
import struct
import traceback
from datetime import datetime

# Flush stdout umiddelbart slik at print vises i journalctl
sys.stdout.reconfigure(line_buffering=True)

# MAX98357A SD pin skal kobles til fast 3.3V (pin 1 eller 17)
# Dette holder forsterkeren alltid på for rask respons
print("MAX98357A SD pin skal være koblet til 3.3V - forsterker alltid på", flush=True)

# Fil for eksterne meldinger
MESSAGE_FILE = "/tmp/duck_message.txt"
# Fil for AI-modell konfigurering
MODEL_CONFIG_FILE = "/tmp/duck_model.txt"
DEFAULT_MODEL = "gpt-3.5-turbo"
# Fil for personlighet
PERSONALITY_FILE = "/tmp/duck_personality.txt"
# Fil for TTS-stemme
VOICE_FILE = "/tmp/duck_voice.txt"
DEFAULT_VOICE = "nb-NO-IselinNeural"
# Fil for nebbet-kontroll
BEAK_FILE = "/tmp/duck_beak.txt"
# Fil for talehastighet (0-100, 50 = normal)
SPEED_FILE = "/tmp/duck_speed.txt"
# Fil for volum (0-100, 50 = normal)
VOLUME_FILE = "/tmp/duck_volume.txt"
# Filer for AI-query fra kontrollpanel
AI_QUERY_FILE = "/tmp/duck_ai_query.txt"
AI_RESPONSE_FILE = "/tmp/duck_ai_response.txt"
# Filer for sang-forespørsler
SONG_REQUEST_FILE = "/tmp/duck_song_request.txt"
SONG_STOP_FILE = "/tmp/duck_song_stop.txt"

# Fade in/out lengde i millisekunder (for å redusere knepp ved start/slutt)
# Sett til 0 for å deaktivere fade
FADE_MS = 150  # 150ms fade in/out

# Nebb-synkronisering (juster for bedre timing)
BEAK_CHUNK_MS = 30  # Hvor ofte nebbet oppdateres (mindre = mer responsivt)
BEAK_PRE_START_MS = 0  # Start nebb før aplay (negativ = etter aplay starter)
# Sett BEAK_PRE_START_MS = -150 hvis nebb starter for tidlig

# Finn USB mikrofon dynamisk (unngå hardkodede device-numre som endrer seg ved reboot)
def find_usb_microphone():
    """Finn sounddevice index for USB PnP Sound Device"""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'USB PnP Sound Device' in device['name'] and device['max_input_channels'] > 0:
            print(f"Fant USB mikrofon: device {i} ({device['name']})", flush=True)
            return i
    # Fallback til default
    print("Fant ikke USB mikrofon, bruker default", flush=True)
    return None

def find_hifiberry_output():
    """Finn sounddevice index for Google Voice HAT / MAX98357A"""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        # Søk etter Google Voice HAT eller voicehat i navnet
        if ('googlevoicehat' in device['name'].lower() or 
            'voicehat' in device['name'].lower() or
            'hifiberry' in device['name'].lower()) and device['max_output_channels'] > 0:
            print(f"Fant I2S DAC: device {i} ({device['name']})", flush=True)
            return i
    # Fallback til default
    print("Fant ikke I2S DAC, bruker default", flush=True)
    return None

def find_usb_mic_alsa_card():
    """Finn ALSA card nummer for USB PnP Sound Device"""
    import re
    try:
        with open('/proc/asound/cards', 'r') as f:
            content = f.read()
            # Søk etter "USB PnP Sound Device" og finn card-nummeret
            match = re.search(r'^\s*(\d+)\s+\[.*?\]:\s+USB-Audio.*?USB PnP Sound Device', content, re.MULTILINE | re.IGNORECASE)
            if match:
                card_num = match.group(1)
                print(f"Fant USB mikrofon ALSA card: {card_num}", flush=True)
                return f"plughw:{card_num},0"
    except Exception as e:
        print(f"Kunne ikke lese /proc/asound/cards: {e}", flush=True)
    return "plughw:1,0"  # Fallback

# Cleanup-funksjon som slår av alle LED ved avslutning
def cleanup():
    print("Slår av LED og rydder opp...", flush=True)
    stop_blink()
    off()

# Registrer cleanup ved normal exit og ved signaler
atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), sys.exit(0)))

def wait_for_wake_word():
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
        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[keyword_path],
            sensitivities=[0.5]  # 0.0 til 1.0, høyere = mer sensitiv (flere false positives)
        )
        
        print(f"Porcupine startet! Sample rate: {porcupine.sample_rate} Hz, Frame length: {porcupine.frame_length}", flush=True)
        
        # USB mikrofon støtter 48000 Hz, men Porcupine trenger 16000 Hz
        # Vi må resample
        mic_sample_rate = 48000
        porcupine_sample_rate = porcupine.sample_rate  # 16000 Hz
        ratio = mic_sample_rate / porcupine_sample_rate  # 3.0
        mic_frame_length = int(porcupine.frame_length * ratio)  # 512 * 3 = 1536
        
        # Øk buffer størrelse for å unngå overflows under resampling
        # Bruk 4x større buffer for å gi nok tid til prosessering
        mic_buffer_size = mic_frame_length * 4  # 1536 * 4 = 6144
        
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
                
                while True:
                    # Sjekk om det finnes en ekstern melding
                    if os.path.exists(MESSAGE_FILE):
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
                    
                    # Sjekk om det finnes en sang-forespørsel
                    if os.path.exists(SONG_REQUEST_FILE):
                        try:
                            with open(SONG_REQUEST_FILE, 'r', encoding='utf-8') as f:
                                song_path = f.read().strip()
                            os.remove(SONG_REQUEST_FILE)
                            if song_path:
                                print(f"Sang-forespørsel mottatt: {song_path}", flush=True)
                                return f'__PLAY_SONG__{song_path}'  # Spesiell trigger for sang
                        except Exception as e:
                            print(f"Feil ved lesing av sang-forespørsel: {e}", flush=True)
                    
                    # Les audio fra mikrofon (større buffer)
                    pcm_48k, overflowed = audio_stream.read(mic_buffer_size)
                    # Ignorer overflow warnings - forventet ved resampling
                    
                    # Konverter til numpy array
                    pcm_48k_array = np.frombuffer(pcm_48k, dtype=np.int16)
                    
                    # Prosesser flere frames (buffer inneholder flere porcupine frames)
                    # Split bufferen i chunks på mic_frame_length
                    for i in range(0, len(pcm_48k_array), mic_frame_length):
                        chunk = pcm_48k_array[i:i+mic_frame_length]
                        if len(chunk) < mic_frame_length:
                            break  # Siste chunk er for liten, skip
                        
                        # Resample til 16000 Hz
                        pcm_16k_array = resample(chunk, porcupine.frame_length)
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
def speak(text, speech_config, beak):
    stop_blink()  # Stopp eventuell blinking
    set_red()  # LED rød FØR anda begynner å snakke
    import tempfile
    import wave
    
    # Les valgt stemme fra konfigurasjonsfil
    voice_name = DEFAULT_VOICE
    try:
        if os.path.exists(VOICE_FILE):
            with open(VOICE_FILE, 'r') as f:
                voice = f.read().strip()
                if voice:
                    voice_name = voice
    except Exception as e:
        print(f"Feil ved lesing av stemme-konfigurasjon: {e}, bruker default", flush=True)
    
    # Les nebbet-status
    beak_enabled = True
    try:
        if os.path.exists(BEAK_FILE):
            with open(BEAK_FILE, 'r') as f:
                beak_status = f.read().strip()
                beak_enabled = (beak_status != 'off')
    except Exception as e:
        print(f"Feil ved lesing av nebbet-konfigurasjon: {e}, nebbet aktivert", flush=True)
    
    # Les talehastighet (0-100, hvor 50 = normal)
    speed_value = 50
    try:
        if os.path.exists(SPEED_FILE):
            with open(SPEED_FILE, 'r') as f:
                speed_str = f.read().strip()
                if speed_str:
                    speed_value = int(speed_str)
    except Exception as e:
        print(f"Feil ved lesing av hastighet-konfigurasjon: {e}, bruker normal hastighet", flush=True)
    
    # Les volum (0-100, hvor 50 = normal)
    volume_value = 50
    try:
        if os.path.exists(VOLUME_FILE):
            with open(VOLUME_FILE, 'r') as f:
                volume_str = f.read().strip()
                if volume_str:
                    volume_value = int(volume_str)
    except Exception as e:
        print(f"Feil ved lesing av volum-konfigurasjon: {e}, bruker normal volum", flush=True)
    
    # Konverter volume_value (0-100) til gain multiplier (0.0-2.0, hvor 1.0 = normal)
    volume_gain = volume_value / 50.0
    
    # Konverter speed_value (0-100) til rate percentage
    # 0 = -50%, 50 = 0%, 100 = +50%
    rate_percent = (speed_value - 50)
    rate_str = f"{rate_percent:+d}%" if rate_percent != 0 else "0%"
    
    print(f"Bruker TTS-stemme: {voice_name}, Nebbet: {'på' if beak_enabled else 'av'}, Hastighet: {rate_str}, Volum: {volume_value}% (gain: {volume_gain:.2f})", flush=True)
    
    # Sett høyere lydkvalitet fra Azure (48kHz)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
    )
    
    # Bruk SSML med prosody for hastighetskontroll
    ssml = f'<speak version="1.0" xml:lang="nb-NO"><voice name="{voice_name}"><prosody rate="{rate_str}">{text}</prosody></voice></speak>'
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmpfile:
        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmpfile.name)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # Last inn original lyd
            sound = AudioSegment.from_wav(tmpfile.name)
            
            # Konverter til numpy array
            samples_original = np.array(sound.get_array_of_samples(), dtype=np.float32)
            samples_original = samples_original / (2**15)  # Normaliser til -1.0 til 1.0
            
            # Gjør pitch-shift MED tempo endring (for and-stemme)
            # Høyere pitch = raskere tempo (som Alvin og gjengen)
            octaves = 0.5  # And-stemme (moderat høyere pitch, fortsatt forståelig)
            pitch_factor = 2.0 ** octaves  # ca 1.41x
            
            # Resample til færre samples = høyere pitch når spilt på original sample rate
            new_length = int(len(samples_original) / pitch_factor)
            samples = resample(samples_original, new_length)
            
            # VIKTIG: Vi beholder original framerate, men med færre samples
            # Dette gir høyere pitch (lyden spilles raskere)
            
            framerate = sound.frame_rate
            n_channels = sound.channels
            sampwidth = sound.sample_width
            
            print(f"After pitch-shift: {framerate} Hz, {n_channels} ch, {sampwidth*8} bit, {len(samples)} samples (var {len(samples_original)})")

            
            # samples er allerede float32 fra pitch-shift
            
            # Sjekk for clipping og normaliser hvis nødvendig
            peak = np.max(np.abs(samples))
            if peak > 0.95:  # Nesten clipping
                print(f"Peak: {peak:.2f} - normaliserer for å unngå clipping", flush=True)
                samples = samples / peak * 0.95
            
            # Anvend volum (gain multiplier fra volume_value)
            samples = samples * volume_gain
            
            # Sjekk igjen for clipping etter volum
            peak_after = np.max(np.abs(samples))
            if peak_after > 1.0:
                print(f"Clipping detektert ({peak_after:.2f}) - reduserer volum", flush=True)
                samples = np.clip(samples, -0.99, 0.99)
            
            # Legg til fade-in/fade-out for å redusere knepp ved start/slutt
            # Sett FADE_MS = 0 i toppen av filen for å deaktivere
            if FADE_MS > 0:
                fade_samples = int(framerate * FADE_MS / 1000.0)
                if len(samples) > fade_samples * 2:
                    # Fade in
                    fade_in = np.linspace(0, 1, fade_samples)
                    samples[:fade_samples] *= fade_in
                    # Fade out
                    fade_out = np.linspace(1, 0, fade_samples)
                    samples[-fade_samples:] *= fade_out
                    print(f"Anvendt {FADE_MS}ms fade in/out", flush=True)

            # Skal allerede være 48000 Hz etter pitch-shift
            target_rate = 48000
            if framerate != target_rate:
                print(f"Resampling fra {framerate} Hz til {target_rate} Hz...")
                num_samples_new = int(len(samples) * target_rate / framerate)
                samples = resample(samples, num_samples_new)
                framerate = target_rate
            
            # Low-pass filter deaktivert - kan introdusere artefakter
            # from scipy.signal import butter, filtfilt
            # nyquist = framerate / 2
            # cutoff = 8000  # Kutt av over 8kHz (tale er under dette)
            # b, a = butter(4, cutoff / nyquist, btype='low')
            # samples = filtfilt(b, a, samples)

            # Bruk aplay med dmixer (definert i ~/.asoundrc) for click/pop reduction
            stream_started = False
            
            try:
                # Konverter float32 samples til int16 og lag stereo
                samples_int16 = (samples * 32767).astype(np.int16)
                stereo_samples = np.column_stack([samples_int16, samples_int16])
                
                # Bruk pydub for å lage WAV
                audio_segment = AudioSegment(
                    stereo_samples.tobytes(),
                    frame_rate=framerate,
                    sample_width=2,  # 16-bit = 2 bytes
                    channels=2
                )
                
                # Eksporter til temp fil og spill med aplay (bruker dmixer fra ~/.asoundrc)
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpwav:
                    audio_segment.export(tmpwav.name, format='wav')
                    import subprocess
                    import threading
                    
                    # Oppdater nebb i takt med lydnivå mens aplay kjører
                    if beak_enabled and beak:
                        # Beregn chunk size for å synkronisere med lyd
                        chunk_size = int(framerate * BEAK_CHUNK_MS / 1000.0)
                        
                        # Start både aplay og nebb-thread samtidig
                        nebb_stop = threading.Event()
                        
                        def update_beak():
                            if BEAK_PRE_START_MS > 0:
                                time.sleep(BEAK_PRE_START_MS / 1000.0)
                            
                            idx = 0
                            start_time = time.time()
                            
                            # Lyden er pitch-shifted (1.41x raskere), så juster timing
                            # Faktisk varighet i sekunder
                            actual_duration = len(samples) / framerate
                            
                            while not nebb_stop.is_set() and idx < len(samples):
                                chunk = samples[idx:idx+chunk_size]
                                if len(chunk) > 0:
                                    amp = np.sqrt(np.mean(chunk**2))
                                    open_pct = min(max(amp * 3.5, 0.05), 1.0)
                                    beak.open_pct(open_pct)
                                
                                idx += chunk_size
                                
                                # Beregn når neste oppdatering skal skje basert på faktisk tid
                                elapsed = time.time() - start_time
                                target_time = (idx / len(samples)) * actual_duration
                                sleep_time = target_time - elapsed
                                
                                if sleep_time > 0:
                                    time.sleep(sleep_time)
                            
                            # Lukk nebbet når ferdig
                            if not nebb_stop.is_set():
                                beak.open_pct(0.05)
                        
                        # Start nebb-thread
                        beak_thread = threading.Thread(target=update_beak, daemon=True)
                        beak_thread.start()
                    
                    # Start aplay
                    process = subprocess.Popen(['aplay', '-q', tmpwav.name], 
                                              stdout=subprocess.PIPE, 
                                              stderr=subprocess.PIPE)
                    
                    # Vent på at aplay er ferdig
                    process.wait()
                    
                    # Stopp nebb-thread
                    if beak_enabled and beak:
                        nebb_stop.set()
                        beak_thread.join(timeout=1.0)
                    
                    os.unlink(tmpwav.name)
                    
                    if process.returncode == 0:
                        stream_started = True
                    else:
                        stderr = process.stderr.read().decode()
                        print(f"aplay error: {stderr}")
                    
            except Exception as e:
                print(f"dmixer playback error: {e}")
            
            if not stream_started:
                print("Kunne ikke starte lydstrøm. Avslutter tale-funksjon uten å spille av.")
            
            if beak:  # Kun hvis servo er tilgjengelig
                beak.open_pct(0.05)  # Minst 5% åpen når ferdig
        else:
            print("TTS-feil:", result.reason)
            if hasattr(result, "cancellation_details"):
                print("Detaljer:", result.cancellation_details.reason, result.cancellation_details.error_details)
    # Ikke kall off() eller endre LED her!

def play_song(song_path, beak, speech_config):
    """Spill av en sang med synkronisert nebb-bevegelse"""
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
    
    # Annonser sangen før avspilling
    if ' - ' in song_folder_name:
        artist, song_title = song_folder_name.split(' - ', 1)
        announcement = f"Nå skal jeg synge {song_title} av {artist}!"
    else:
        announcement = f"Nå skal jeg synge {song_folder_name}!"
    
    print(f"Annonserer sang: {announcement}", flush=True)
    speak(announcement, speech_config, beak)
    
    # Litt pause før sang starter
    time.sleep(0.5)
    
    set_red()  # LED rød når anda synger
    
    # Les nebbet-status
    beak_enabled = True
    try:
        if os.path.exists(BEAK_FILE):
            with open(BEAK_FILE, 'r') as f:
                beak_status = f.read().strip()
                beak_enabled = (beak_status != 'off')
    except Exception as e:
        print(f"Feil ved lesing av nebbet-konfigurasjon: {e}, nebbet aktivert", flush=True)
    
    # Les volum (0-100, 50 = normal)
    volume_value = 50
    try:
        if os.path.exists(VOLUME_FILE):
            with open(VOLUME_FILE, 'r') as f:
                vol = f.read().strip()
                if vol:
                    volume_value = int(vol)
    except Exception as e:
        print(f"Feil ved lesing av volum-konfigurasjon: {e}, bruker normal volum", flush=True)
    
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
        # mix_samples kan være (N, 2) for stereo eller (N, 1) for mono
        # vocals_samples er alltid flat mono array
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
                # mix_idx er frame index, vocals trenger sample index
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
                # (mix_idx oppdateres av playback thread)
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

def recognize_speech_from_mic(device_name=None):
    set_green()  # LED grønn mens bruker snakker
    stt_key = os.getenv("AZURE_STT_KEY")
    stt_region = os.getenv("AZURE_STT_REGION")
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
            speech_recognizer.properties.set_property(prop, "800")
            print(f"Snakk nå (device {dev})...", flush=True)
            t0 = time.time()
            result = speech_recognizer.recognize_once()
            t1 = time.time()
            elapsed = t1 - t0
            print(f"Azure STT tid: {elapsed:.2f} sekunder", flush=True)
            off()  # Slå av LED etter bruker har snakket
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
                off()
                return None

def get_coordinates(location_name):
    """Hent koordinater for et stedsnavn via Nominatim (OpenStreetMap)"""
    try:
        # Legg til Norge i søket for bedre nøyaktighet
        search_query = f"{location_name}, Norge"
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': search_query,
            'format': 'json',
            'limit': 1
        }
        headers = {
            'User-Agent': 'ChatGPTDuck/2.1.2 (contact: github.com/osmund/chatgpt-and)'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            display_name = data[0].get('display_name', location_name)
            return lat, lon, display_name
        return None
    except Exception as e:
        print(f"Geocoding feil for '{location_name}': {e}", flush=True)
        return None

def get_weather(location_name):
    """
    Hent værmelding fra yr.no (MET Norway API)
    Returnerer nåværende temperatur og værbeskrivelse
    """
    try:
        # Først: Finn koordinater for stedet
        coords = get_coordinates(location_name)
        if not coords:
            return f"Beklager, jeg fant ikke stedet '{location_name}'."
        
        lat, lon, display_name = coords
        print(f"Værdata for {display_name} (lat: {lat}, lon: {lon})", flush=True)
        
        # Hent værdata fra MET Norway locationforecast API
        url = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
        params = {'lat': lat, 'lon': lon}
        headers = {
            'User-Agent': 'ChatGPTDuck/2.1.2 (contact: github.com/osmund/chatgpt-and)'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse værdata
        timeseries = data['properties']['timeseries']
        
        # Nåværende vær (første tidspunkt)
        current = timeseries[0]['data']['instant']['details']
        current_temp = current['air_temperature']
        
        # Finn symbolkode for nåværende vær (fra neste 1h hvis tilgjengelig)
        current_symbol = "ukjent"
        if 'next_1_hours' in timeseries[0]['data']:
            current_symbol = timeseries[0]['data']['next_1_hours']['summary']['symbol_code']
        elif 'next_6_hours' in timeseries[0]['data']:
            current_symbol = timeseries[0]['data']['next_6_hours']['summary']['symbol_code']
        
        # Oversett symbolkoder til norsk
        symbol_translations = {
            'clearsky': 'klarvær',
            'cloudy': 'overskyet',
            'fair': 'lettskyet',
            'fog': 'tåke',
            'heavyrain': 'kraftig regn',
            'heavyrainandthunder': 'kraftig regn og torden',
            'heavyrainshowers': 'kraftige regnbyger',
            'heavysleet': 'kraftig sludd',
            'heavysleetandthunder': 'kraftig sludd og torden',
            'heavysnow': 'kraftig snø',
            'heavysnowandthunder': 'kraftig snø og torden',
            'heavysnowshowers': 'kraftige snøbyger',
            'lightrain': 'lett regn',
            'lightrainandthunder': 'lett regn og torden',
            'lightrainshowers': 'lette regnbyger',
            'lightsleet': 'lett sludd',
            'lightsleetandthunder': 'lett sludd og torden',
            'lightsnow': 'lett snø',
            'lightsnowandthunder': 'lett snø og torden',
            'lightsnowshowers': 'lette snøbyger',
            'partlycloudy': 'delvis skyet',
            'rain': 'regn',
            'rainandthunder': 'regn og torden',
            'rainshowers': 'regnbyger',
            'sleet': 'sludd',
            'sleetandthunder': 'sludd og torden',
            'sleetshowers': 'sluddbyger',
            'snow': 'snø',
            'snowandthunder': 'snø og torden',
            'snowshowers': 'snøbyger'
        }
        
        # Fjern _day/_night/_polartwilight suffix
        symbol_base = current_symbol.split('_')[0]
        weather_desc = symbol_translations.get(symbol_base, current_symbol)
        
        # Hent prognose for resten av dagen (neste 6-12 timer)
        forecast_summary = []
        for i in range(1, min(13, len(timeseries))):  # Neste 12 timer
            ts = timeseries[i]
            time_str = ts['time']
            temp = ts['data']['instant']['details']['air_temperature']
            
            # Hent hver 3. time for å ikke overbelaste
            if i % 3 == 0:
                hour = time_str.split('T')[1][:5]
                forecast_summary.append(f"{hour}: {temp}°C")
        
        # Bygg svar
        result = f"Værmelding for {display_name}:\n"
        result += f"Nå: {current_temp}°C, {weather_desc}\n"
        
        if forecast_summary:
            result += f"Prognose i dag: {', '.join(forecast_summary[:4])}"  # Max 4 tidspunkt
        
        return result
        
    except Exception as e:
        print(f"Værhenting feil: {e}", flush=True)
        return f"Beklager, jeg kunne ikke hente værdata akkurat nå. Feil: {str(e)}"

def chatgpt_query(messages, api_key, model=None):
    if model is None:
        # Prøv å lese modell fra konfigurasjonsfil
        try:
            if os.path.exists(MODEL_CONFIG_FILE):
                with open(MODEL_CONFIG_FILE, 'r') as f:
                    model = f.read().strip()
                    if not model:
                        model = DEFAULT_MODEL
            else:
                model = DEFAULT_MODEL
        except Exception as e:
            print(f"Feil ved lesing av modellkonfigurasjon: {e}, bruker default", flush=True)
            model = DEFAULT_MODEL
    
    print(f"Bruker AI-modell: {model}", flush=True)
    
    # Les personlighet fra konfigurasjonsfil
    personality_prompt = None
    try:
        if os.path.exists(PERSONALITY_FILE):
            with open(PERSONALITY_FILE, 'r', encoding='utf-8') as f:
                personality = f.read().strip()
                if personality == "frekk":
                    personality_prompt = "Du er en frekk og sarkastisk and som elsker å svare med ironi, spydige kommentarer og humoristiske stikk. Du er morsom, men aldri direkte uhøflig. Du bruker norsk humor og liker å tulle litt med brukeren."
                elif personality == "vennlig":
                    personality_prompt = "Du er en veldig vennlig, hjelpsom og entusiastisk and som alltid er i godt humør. Du oppmuntrer og støtter brukeren, og svarer alltid med en positiv innstilling."
                elif personality == "akademisk":
                    personality_prompt = "Du er en veldig kunnskapsrik og akademisk and som svarer nøyaktig og detaljert. Du liker å gi grundige forklaringer og refererer til fakta og kilder når det er relevant."
                elif personality == "filosof":
                    personality_prompt = "Du er en filosofisk and som liker å stille dype spørsmål og reflektere over meningen med ting. Du svarer med visdom og får brukeren til å tenke."
                elif personality == "barnlig":
                    personality_prompt = "Du er en leken og entusiastisk and som snakker enkelt og barnlig. Du blir veldig excited og bruker mange utropstegn! Du liker å bruke morsomme ord og lyder som 'kvakk' og 'jippi'!"
                elif personality == "senior":
                    personality_prompt = "Du er en gammel, sur and på 60+ som klager over alt. Alt var bedre før! Ryggen gjør vondt, knærne knirker, og de unge forstår ingenting i dag. Du snakker nostalgisk om gamle dager og er besatt av klassiske norske godterier: Kongen av Danmark, gullbrød, lakrisbåter og kremtopper. Du relaterer det meste til godteri eller hvor vondt noe gjør. Sukker og klager over moderne teknologi og nye trender. 'I min tid...' er din favorittfrase."
                # "normal" eller ingen fil = ingen spesiell personlighet
    except Exception as e:
        print(f"Feil ved lesing av personlighet: {e}", flush=True)
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Hent nåværende dato og tid fra system
    now = datetime.now()
    date_time_info = f"Nåværende dato og tid: {now.strftime('%A %d. %B %Y, klokken %H:%M')}. "
    
    # Legg til dato/tid + personlighet i system-prompt
    final_messages = messages.copy()
    system_content = date_time_info
    
    if personality_prompt:
        system_content += personality_prompt
        print(f"Bruker personlighet: {personality}", flush=True)
    else:
        system_content += "Du er en hjelpsom assistent."
    
    final_messages.insert(0, {"role": "system", "content": system_content})
    
    # Definer værmelding function tool
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Hent nåværende værmelding og temperatur for et spesifikt sted i Norge. Bruk denne når brukeren spør om været.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Navnet på stedet/byen i Norge, f.eks. 'Oslo', 'Sokndal', 'Bergen'"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]
    
    data = {
        "model": model,
        "messages": final_messages,
        "tools": tools,
        "tool_choice": "auto"  # La modellen velge når den skal bruke tools
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    response_data = response.json()
    
    # Sjekk om modellen vil kalle en funksjon
    message = response_data["choices"][0]["message"]
    
    if message.get("tool_calls"):
        # Modellen vil kalle værfunksjonen
        tool_call = message["tool_calls"][0]
        function_name = tool_call["function"]["name"]
        function_args = json.loads(tool_call["function"]["arguments"])
        
        print(f"ChatGPT kaller funksjon: {function_name} med args: {function_args}", flush=True)
        
        # Kall faktisk værfunksjon
        if function_name == "get_weather":
            location = function_args.get("location", "")
            weather_result = get_weather(location)
            
            # Legg til function call og resultat i conversation
            final_messages.append(message)
            final_messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": weather_result
            })
            
            # Kall API igjen med værdata
            data["messages"] = final_messages
            response2 = requests.post(url, headers=headers, json=data)
            response2.raise_for_status()
            return response2.json()["choices"][0]["message"]["content"]
    
    # Ingen function call, returner vanlig svar
    return message["content"]

def check_ai_queries(api_key, speech_config, beak):
    """Bakgrunnstråd som sjekker for AI-queries fra kontrollpanelet"""
    import threading
    while True:
        try:
            if os.path.exists(AI_QUERY_FILE):
                with open(AI_QUERY_FILE, 'r', encoding='utf-8') as f:
                    query = f.read().strip()
                
                # Slett filen umiddelbart etter lesing for å unngå gjentakelse
                os.remove(AI_QUERY_FILE)
                
                if query:
                    print(f"AI-query fra kontrollpanel: {query}", flush=True)
                    
                    # Spør ChatGPT
                    messages = [{"role": "user", "content": query}]
                    response = chatgpt_query(messages, api_key)
                    
                    # Skriv respons til fil
                    with open(AI_RESPONSE_FILE, 'w', encoding='utf-8') as f:
                        f.write(response)
                    
                    # Si svaret
                    speak(response, speech_config, beak)
                    
                    print(f"AI-respons: {response}", flush=True)
        except Exception as e:
            print(f"Feil i AI-query tråd: {e}", flush=True)
        
        time.sleep(0.5)  # Sjekk hver halve sekund

def main():
    # Prøv å initialisere servo, men fortsett uten hvis den ikke finnes
    beak = None
    try:
        beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
        print("Servo initialisert OK", flush=True)
    except Exception as e:
        print(f"Advarsel: Kunne ikke initialisere servo (fortsetter uten): {e}", flush=True)
        beak = None
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    tts_key = os.getenv("AZURE_TTS_KEY")
    tts_region = os.getenv("AZURE_TTS_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
    speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"

    # Start bakgrunnstråd for AI-queries fra kontrollpanelet
    import threading
    ai_thread = threading.Thread(target=check_ai_queries, args=(api_key, speech_config, beak), daemon=True)
    ai_thread.start()
    print("AI-query tråd startet", flush=True)

    # Oppstartshilsen (ikke la en TTS-feil stoppe tjenesten ved boot)
    time.sleep(3)  # Vent litt lenger for at systemet skal være klart
    try:
        # Hent IP-adresse (prøv flere ganger)
        import socket
        ip_address = None
        for attempt in range(5):  # Prøv 5 ganger
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2)
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
                s.close()
                if ip_address and ip_address != "127.0.0.1":
                    break  # Vellykket, avslutt loop
            except:
                if attempt < 4:  # Ikke vent etter siste forsøk
                    time.sleep(2)  # Vent 2 sekunder før neste forsøk
        
        if ip_address and ip_address != "127.0.0.1":
            greeting = f"Kvakk kvakk! Jeg er nå klar for andeprat. Min IP-adresse er {ip_address.replace('.', ' punkt ')}. Du finner kontrollpanelet på port 3000. Si navnet mitt for å starte en samtale!"
            print(f"Oppstartshilsen med IP: {ip_address}", flush=True)
        else:
            greeting = "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"
            print("Oppstartshilsen uten IP (nettverk ikke klart)", flush=True)
        
        speak(greeting, speech_config, beak)
        print("Oppstartshilsen ferdig", flush=True)
    except Exception as e:
        print(f"Oppstartshilsen mislyktes (audio ikke klar ennå): {e}", flush=True)
        # Prøv en enklere hilsen uten TTS
        try:
            print("Prøver forenklet oppstart...", flush=True)
            time.sleep(2)
        except:
            pass
    
    print("Anda venter på wake word... (si 'quack quack')", flush=True)
    while True:
        external_message = wait_for_wake_word()
        
        # Hvis det er en ekstern melding, sjekk type
        if external_message:
            if external_message == '__START_CONVERSATION__':
                # Start samtale direkte med en kort hilsen
                print("Starter samtale via web-interface", flush=True)
                speak("Hei på du, hva kan jeg hjelpe deg med?", speech_config, beak)
            elif external_message.startswith('__PLAY_SONG__'):
                # Spill av en sang
                song_path = external_message.replace('__PLAY_SONG__', '', 1)
                play_song(song_path, beak, speech_config)
                continue  # Gå tilbake til wake word etter sang
            else:
                # Bare si meldingen og gå tilbake til wake word
                speak(external_message, speech_config, beak)
                continue
        else:
            # Normal wake word - si hilsen
            speak("Hei på du, hva kan jeg hjelpe deg med?", speech_config, beak)
        
        # Start samtale (enten fra wake word eller samtale-trigger)
        messages = []
        no_response_count = 0  # Teller antall ganger uten svar
        
        while True:
            prompt = recognize_speech_from_mic()  # Ingen device_name argument, bruker hw:1,0 internt
            if not prompt:
                no_response_count += 1
                if no_response_count >= 2:
                    speak("Jeg hører deg ikke. Da venter jeg til du sier navnet mitt igjen.", speech_config, beak)
                    break
                speak("Beklager, jeg hørte ikke hva du sa. Prøv igjen.", speech_config, beak)
                continue
            
            # Reset teller når vi får svar
            no_response_count = 0
            
            # Sjekk for stopp-kommando (fjern tegnsetting først)
            prompt_clean = prompt.strip().lower().replace(".", "").replace(",", "").replace("!", "")
            if "stopp" in prompt_clean:
                speak("Da venter jeg til du sier navnet mitt igjen.", speech_config, beak)
                break
            messages.append({"role": "user", "content": prompt})
            try:
                blink_yellow_purple()  # Start blinkende gul LED under tenkepause
                reply = chatgpt_query(messages, api_key)
                off()           # Slå av blinking når svaret er klart
                print("ChatGPT svar:", reply, flush=True)
                speak(reply, speech_config, beak)
                messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                off()
                print("Feil:", e)
                speak("Beklager, det oppstod en feil.", speech_config, beak)
            #blink_yellow()  # Start blinkende gul LED under "tenkepause"
            set_green()  # Eller annen farge for neste fase

if __name__ == "__main__":
    main()