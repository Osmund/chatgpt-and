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
from datetime import datetime, timedelta
from duck_memory import MemoryManager
from duck_user_manager import UserManager

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
# Konfigurasjonsfiler
MESSAGES_FILE = "/home/admog/Code/chatgpt-and/messages.json"
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

def clean_markdown_for_tts(text):
    """
    Fjerner Markdown-formatering fra tekst før TTS.
    Dette forhindrer at TTS sier 'asterisk asterisk' osv.
    """
    import re
    
    # Fjern bold/italic: **tekst** eller *tekst*
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
    
    # Fjern underline: __tekst__ eller _tekst_
    text = re.sub(r'__(.+?)__', r'\1', text)      # __underline__
    text = re.sub(r'_(.+?)_', r'\1', text)        # _underline_
    
    # Fjern kodeblokker: ```kode``` eller `kode`
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)  # ```code block```
    text = re.sub(r'`(.+?)`', r'\1', text)                   # `inline code`
    
    # Fjern lenker: [tekst](url) → tekst
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    
    # Fjern overskrifter: ### Overskrift → Overskrift
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Fjern liste-markører: - item eller * item eller 1. item
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    return text

def speak(text, speech_config, beak):
    stop_blink()  # Stopp eventuell blinking
    set_red()  # LED rød FØR anda begynner å snakke
    import tempfile
    import wave
    
    # Fjern Markdown-formatering før TTS
    text = clean_markdown_for_tts(text)
    
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
                    # Hvis nebb er av, bruk LED i stedet
                    chunk_size = int(framerate * BEAK_CHUNK_MS / 1000.0)
                    
                    # Start både aplay og nebb/LED-thread samtidig
                    control_stop = threading.Event()
                    
                    def update_beak_or_led():
                        if BEAK_PRE_START_MS > 0:
                            time.sleep(BEAK_PRE_START_MS / 1000.0)
                        
                        idx = 0
                        start_time = time.time()
                        
                        # Lyden er pitch-shifted (1.41x raskere), så juster timing
                        # Faktisk varighet i sekunder
                        actual_duration = len(samples) / framerate
                        
                        while not control_stop.is_set() and idx < len(samples):
                            chunk = samples[idx:idx+chunk_size]
                            if len(chunk) > 0:
                                amp = np.sqrt(np.mean(chunk**2))
                                
                                if beak_enabled and beak:
                                    # Normal nebb-bevegelse
                                    open_pct = min(max(amp * 3.5, 0.05), 1.0)
                                    beak.open_pct(open_pct)
                                else:
                                    # LED-pulsing når nebb er av
                                    intensity = min(amp * 4.0, 1.0)
                                    intensity = max(intensity, 0.1)  # Minimum intensitet
                                    set_intensity(intensity)
                            
                            idx += chunk_size
                            
                            # Beregn når neste oppdatering skal skje basert på faktisk tid
                            elapsed = time.time() - start_time
                            target_time = (idx / len(samples)) * actual_duration
                            sleep_time = target_time - elapsed
                            
                            if sleep_time > 0:
                                time.sleep(sleep_time)
                        
                        # Lukk nebbet eller slå av LED når ferdig
                        if not control_stop.is_set():
                            if beak_enabled and beak:
                                beak.open_pct(0.05)
                            else:
                                off()  # Slå av LED
                    
                    # Start nebb/LED-thread
                    control_thread = threading.Thread(target=update_beak_or_led, daemon=True)
                    control_thread.start()
                    
                    # Start aplay
                    process = subprocess.Popen(['aplay', '-q', tmpwav.name], 
                                              stdout=subprocess.PIPE, 
                                              stderr=subprocess.PIPE)
                    
                    # Vent på at aplay er ferdig
                    process.wait()
                    
                    # Stopp nebb/LED-thread
                    control_stop.set()
                    control_thread.join(timeout=1.0)
                    
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

def control_hue_lights(action, room=None, brightness=None, color=None):
    """
    Kontroller Philips Hue smarte lys
    
    Args:
        action: "on", "off", "dim", "brighten" 
        room: Navnet på rommet/lyset (None = alle lys)
        brightness: 0-100 (prosent)
        color: "rød", "blå", "grønn", "gul", "hvit", "rosa", "lilla", "oransje"
    """
    try:
        bridge_ip = os.getenv("HUE_BRIDGE_IP")
        api_key = os.getenv("HUE_API_KEY")
        
        if not bridge_ip or not api_key:
            return "Philips Hue er ikke konfigurert. Legg til HUE_BRIDGE_IP og HUE_API_KEY i .env"
        
        base_url = f"http://{bridge_ip}/api/{api_key}"
        
        # Hent alle lys
        response = requests.get(f"{base_url}/lights", timeout=5)
        response.raise_for_status()
        lights = response.json()
        
        if not lights:
            return "Fant ingen Philips Hue-lys på nettverket."
        
        # Finn hvilke lys som skal styres
        target_lights = []
        if room:
            # Søk etter lys som matcher romnavnet
            room_lower = room.lower()
            for light_id, light_data in lights.items():
                light_name = light_data.get('name', '').lower()
                if room_lower in light_name:
                    target_lights.append((light_id, light_data['name']))
            
            if not target_lights:
                return f"Fant ingen lys som matcher '{room}'. Tilgjengelige lys: {', '.join([lights[lid]['name'] for lid in lights])}"
        else:
            # Alle lys
            target_lights = [(lid, lights[lid]['name']) for lid in lights]
        
        # Fargekart (Hue format: 0-65535)
        color_map = {
            'rød': {'hue': 0, 'sat': 254},
            'oransje': {'hue': 5000, 'sat': 254},
            'gul': {'hue': 12000, 'sat': 254},
            'grønn': {'hue': 25500, 'sat': 254},
            'cyan': {'hue': 35000, 'sat': 254},
            'blå': {'hue': 46920, 'sat': 254},
            'lilla': {'hue': 50000, 'sat': 254},
            'rosa': {'hue': 56100, 'sat': 254},
            'hvit': {'sat': 0, 'ct': 366}  # Varm hvit
        }
        
        # Bygg state-objektet
        state = {}
        
        if action == "on":
            state['on'] = True
            if brightness is not None:
                state['bri'] = int(brightness * 254 / 100)  # Konverter 0-100 til 0-254
            if color and color.lower() in color_map:
                state.update(color_map[color.lower()])
        
        elif action == "off":
            state['on'] = False
        
        elif action == "dim":
            current_bri = 100  # Default
            state['on'] = True
            if brightness:
                state['bri'] = int(brightness * 254 / 100)
            else:
                state['bri'] = 50  # 20% lysstyrke
        
        elif action == "brighten":
            state['on'] = True
            if brightness:
                state['bri'] = int(brightness * 254 / 100)
            else:
                state['bri'] = 254  # Full lysstyrke
        
        # Utfør kommandoen på alle target lys
        results = []
        for light_id, light_name in target_lights:
            try:
                url = f"{base_url}/lights/{light_id}/state"
                resp = requests.put(url, json=state, timeout=5)
                resp.raise_for_status()
                results.append(light_name)
            except Exception as e:
                print(f"Feil ved kontroll av {light_name}: {e}", flush=True)
        
        # Bygg svar
        action_desc = {
            'on': 'skrudd på',
            'off': 'skrudd av',
            'dim': 'dimmet',
            'brighten': 'gjort lysere'
        }.get(action, action)
        
        if results:
            result_msg = f"Jeg har {action_desc} {len(results)} lys: {', '.join(results)}"
            if brightness:
                result_msg += f" til {brightness}%"
            if color:
                result_msg += f" ({color} farge)"
            return result_msg
        else:
            return f"Kunne ikke kontrollere noen lys."
        
    except Exception as e:
        print(f"Hue-kontroll feil: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Beklager, jeg kunne ikke kontrollere Hue-lysene akkurat nå. Feil: {str(e)}"

def control_beak(enabled):
    """Slå nebb på eller av"""
    try:
        status = "on" if enabled else "off"
        with open(BEAK_FILE, 'w') as f:
            f.write(status)
        
        action = "på" if enabled else "av"
        return f"Jeg har skrudd nebbet {action}. {'Jeg bruker LED-lys i stedet når jeg snakker.' if not enabled else 'Nå beveger nebbet seg når jeg snakker.'}"
    except Exception as e:
        print(f"Feil ved nebb-kontroll: {e}", flush=True)
        return f"Beklager, jeg kunne ikke endre nebb-innstillingen. Feil: {str(e)}"

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

def get_weather(location_name, timeframe="now"):
    """
    Hent værmelding fra yr.no (MET Norway API)
    Returnerer temperatur og værbeskrivelse for angitt tidsramme
    
    Args:
        location_name: Navn på stedet
        timeframe: "now" (nå), "today" (i dag), "tomorrow" (i morgen)
    """
    try:
        # Først: Finn koordinater for stedet
        coords = get_coordinates(location_name)
        if not coords:
            return f"Beklager, jeg fant ikke stedet '{location_name}'."
        
        lat, lon, display_name = coords
        print(f"Værdata for {display_name} (lat: {lat}, lon: {lon}), tidsramme: {timeframe}", flush=True)
        
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
        
        def get_weather_desc(symbol_code):
            symbol_base = symbol_code.split('_')[0]
            return symbol_translations.get(symbol_base, symbol_code)
        
        now = datetime.now()
        
        if timeframe == "tomorrow":
            # Finn værdatafor i morgen
            tomorrow_date = (now + timedelta(days=1)).date()
            
            # Samle data for morgendagen
            tomorrow_temps = []
            tomorrow_symbols = []
            tomorrow_winds = []
            
            for ts in timeseries:
                ts_time = datetime.fromisoformat(ts['time'].replace('Z', '+00:00'))
                if ts_time.date() == tomorrow_date:
                    temp = ts['data']['instant']['details']['air_temperature']
                    tomorrow_temps.append(temp)
                    
                    # Hent vindstyrke
                    wind = ts['data']['instant']['details'].get('wind_speed', 0)
                    tomorrow_winds.append(wind)
                    
                    # Hent værsymbol hvis tilgjengelig
                    if 'next_1_hours' in ts['data']:
                        tomorrow_symbols.append(ts['data']['next_1_hours']['summary']['symbol_code'])
                    elif 'next_6_hours' in ts['data']:
                        tomorrow_symbols.append(ts['data']['next_6_hours']['summary']['symbol_code'])
            
            if not tomorrow_temps:
                return f"Beklager, jeg har ikke værdata for i morgen for {display_name}."
            
            # Beregn min/max temp og gjennomsnittsvind
            min_temp = min(tomorrow_temps)
            max_temp = max(tomorrow_temps)
            avg_wind = sum(tomorrow_winds) / len(tomorrow_winds) if tomorrow_winds else 0
            max_wind = max(tomorrow_winds) if tomorrow_winds else 0
            
            # Beskriv vindstyrke på norsk
            def get_wind_description(speed_ms):
                if speed_ms < 1.6:
                    return "vindstille"
                elif speed_ms < 3.4:
                    return "svak vind"
                elif speed_ms < 5.5:
                    return "lett bris"
                elif speed_ms < 8.0:
                    return "laber bris"
                elif speed_ms < 10.8:
                    return "frisk bris"
                elif speed_ms < 13.9:
                    return "liten kuling"
                elif speed_ms < 17.2:
                    return "stiv kuling"
                elif speed_ms < 20.8:
                    return "sterk kuling"
                elif speed_ms < 24.5:
                    return "liten storm"
                elif speed_ms < 28.5:
                    return "full storm"
                else:
                    return "sterk storm"
            
            wind_desc = get_wind_description(avg_wind)
            
            # Finn mest vanlige værsymbol
            most_common_symbol = "ukjent"
            if tomorrow_symbols:
                from collections import Counter
                most_common_symbol = Counter(tomorrow_symbols).most_common(1)[0][0]
            
            weather_desc = get_weather_desc(most_common_symbol)
            
            # Hent total nedbør for morgendagen
            total_precipitation = 0
            for ts in timeseries:
                ts_time = datetime.fromisoformat(ts['time'].replace('Z', '+00:00'))
                if ts_time.date() == tomorrow_date:
                    if 'next_1_hours' in ts['data'] and 'details' in ts['data']['next_1_hours']:
                        precip = ts['data']['next_1_hours']['details'].get('precipitation_amount', 0)
                        total_precipitation += precip
            
            result = f"Værmelding for {display_name} i morgen:\n"
            result += f"Temperatur: {min_temp:.1f}°C til {max_temp:.1f}°C\n"
            result += f"Vær: {weather_desc}\n"
            result += f"Vind: {wind_desc} (gjennomsnitt {avg_wind:.1f} m/s, maks {max_wind:.1f} m/s)\n"
            
            # Legg til nedbør hvis relevant
            if total_precipitation > 0.1:
                result += f"Nedbør: {total_precipitation:.1f} mm"
            else:
                result += "Ingen nedbør ventet"
            
        else:  # "now" eller "today"
            # Nåværende vær (første tidspunkt)
            current = timeseries[0]['data']['instant']['details']
            current_temp = current['air_temperature']
            
            # Hent vinddata
            wind_speed = current.get('wind_speed', 0)  # m/s
            wind_from_direction = current.get('wind_from_direction', None)  # grader
            
            # Konverter vindretning fra grader til kompassretning
            def get_wind_direction(degrees):
                if degrees is None:
                    return ""
                directions = ["nord", "nordøst", "øst", "sørøst", "sør", "sørvest", "vest", "nordvest"]
                index = round(degrees / 45) % 8
                return directions[index]
            
            # Beskriv vindstyrke på norsk (basert på Beaufort-skala)
            def get_wind_description(speed_ms):
                if speed_ms < 1.6:
                    return "vindstille"
                elif speed_ms < 3.4:
                    return "svak vind"
                elif speed_ms < 5.5:
                    return "lett bris"
                elif speed_ms < 8.0:
                    return "laber bris"
                elif speed_ms < 10.8:
                    return "frisk bris"
                elif speed_ms < 13.9:
                    return "liten kuling"
                elif speed_ms < 17.2:
                    return "stiv kuling"
                elif speed_ms < 20.8:
                    return "sterk kuling"
                elif speed_ms < 24.5:
                    return "liten storm"
                elif speed_ms < 28.5:
                    return "full storm"
                else:
                    return "sterk storm"
            
            wind_desc = get_wind_description(wind_speed)
            wind_dir = get_wind_direction(wind_from_direction)
            wind_text = f"{wind_desc}"
            if wind_dir and wind_speed >= 1.6:  # Kun vis retning hvis det er vind
                wind_text += f" fra {wind_dir}"
            wind_text += f" ({wind_speed:.1f} m/s)"
            
            # Finn symbolkode for nåværende vær
            current_symbol = "ukjent"
            if 'next_1_hours' in timeseries[0]['data']:
                current_symbol = timeseries[0]['data']['next_1_hours']['summary']['symbol_code']
            elif 'next_6_hours' in timeseries[0]['data']:
                current_symbol = timeseries[0]['data']['next_6_hours']['summary']['symbol_code']
            
            weather_desc = get_weather_desc(current_symbol)
            
            # Hent nedbør neste time og neste 6 timer
            precip_1h = 0
            precip_6h = 0
            if 'next_1_hours' in timeseries[0]['data'] and 'details' in timeseries[0]['data']['next_1_hours']:
                precip_1h = timeseries[0]['data']['next_1_hours']['details'].get('precipitation_amount', 0)
            if 'next_6_hours' in timeseries[0]['data'] and 'details' in timeseries[0]['data']['next_6_hours']:
                precip_6h = timeseries[0]['data']['next_6_hours']['details'].get('precipitation_amount', 0)
            
            # Hent prognose for resten av dagen (neste 6-12 timer)
            forecast_summary = []
            for i in range(1, min(13, len(timeseries))):  # Neste 12 timer
                ts = timeseries[i]
                time_str = ts['time']
                temp = ts['data']['instant']['details']['air_temperature']
                
                # Hent hver 3. time for å ikke overbelaste
                if i % 3 == 0:
                    hour = time_str.split('T')[1][:5]
                    forecast_summary.append(f"{hour}: {temp:.1f}°C")
            
            # Bygg svar
            result = f"Værmelding for {display_name}:\n"
            result += f"Nå: {current_temp:.1f}°C, {weather_desc}\n"
            result += f"Vind: {wind_text}\n"
            
            # Legg til nedbør-informasjon
            if precip_1h > 0.1:
                result += f"Nedbør neste time: {precip_1h:.1f} mm\n"
            elif precip_6h > 0.1:
                result += f"Nedbør neste 6 timer: {precip_6h:.1f} mm\n"
            else:
                result += "Ingen nedbør ventet\n"
            
            if forecast_summary:
                result += f"Prognose i dag: {', '.join(forecast_summary[:4])}"  # Max 4 tidspunkt
        
        return result
        
    except Exception as e:
        print(f"Værhenting feil: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Beklager, jeg kunne ikke hente værdata akkurat nå. Feil: {str(e)}"

def chatgpt_query(messages, api_key, model=None, memory_manager=None, user_manager=None):
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
    
    # Hent nåværende bruker
    current_user = None
    if user_manager:
        try:
            current_user = user_manager.get_current_user()
            print(f"👤 Nåværende bruker: {current_user['display_name']} ({current_user['relation']})", flush=True)
        except Exception as e:
            print(f"⚠️ Kunne ikke hente current_user: {e}", flush=True)
    
    # Les personlighet fra konfigurasjonsfil
    personality_prompt = None
    try:
        # Last personligheter fra JSON-fil
        personalities_file = "/home/admog/Code/chatgpt-and/personalities.json"
        personalities = {}
        if os.path.exists(personalities_file):
            with open(personalities_file, 'r', encoding='utf-8') as f:
                personalities = json.load(f)
        
        # Les hvilken personlighet som skal brukes
        if os.path.exists(PERSONALITY_FILE):
            with open(PERSONALITY_FILE, 'r', encoding='utf-8') as f:
                personality = f.read().strip()
                personality_prompt = personalities.get(personality, "")
    except Exception as e:
        print(f"Feil ved lesing av personlighet: {e}", flush=True)
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Hent nåværende dato og tid fra system
    now = datetime.now()
    
    # Norske navn for dager og måneder
    norwegian_days = {
        'Monday': 'mandag',
        'Tuesday': 'tirsdag', 
        'Wednesday': 'onsdag',
        'Thursday': 'torsdag',
        'Friday': 'fredag',
        'Saturday': 'lørdag',
        'Sunday': 'søndag'
    }
    
    norwegian_months = {
        'January': 'januar',
        'February': 'februar',
        'March': 'mars',
        'April': 'april',
        'May': 'mai',
        'June': 'juni',
        'July': 'juli',
        'August': 'august',
        'September': 'september',
        'October': 'oktober',
        'November': 'november',
        'December': 'desember'
    }
    
    # Bygg norsk dato-string manuelt
    day_name = norwegian_days[now.strftime('%A')]
    month_name = norwegian_months[now.strftime('%B')]
    date_time_info = f"Nåværende dato og tid: {day_name} {now.day}. {month_name} {now.year}, klokken {now.strftime('%H:%M')}. "
    
    # Legg til brukerinfo hvis tilgjengelig
    user_info = ""
    if current_user:
        user_info = f"\n\n### Nåværende bruker ###\n"
        user_info += f"Du snakker nå med: {current_user['display_name']}\n"
        user_info += f"Relasjon til Osmund (primary user): {current_user['relation']}\n"
        
        if current_user['username'] != 'Osmund':
            timeout_sec = user_manager.get_time_until_timeout()
            if timeout_sec:
                timeout_min = timeout_sec // 60
                user_info += f"Viktig: Hvis brukeren ikke svarer på 30 minutter, vil systemet automatisk bytte tilbake til Osmund.\n"
    
    # Legg til dato/tid + personlighet i system-prompt
    final_messages = messages.copy()
    system_content = date_time_info + user_info
    
    # Samle memory context først (men legg til senere)
    memory_section = ""
    if memory_manager:
        try:
            # Hent brukerens siste melding for relevant søk
            user_query = messages[-1]["content"] if messages else ""
            context = memory_manager.build_context_for_ai(user_query, recent_messages=3)
            
            # Bygg memory section (legges til senere)
            memory_section = "\n\n### Ditt Minne ###\n"
            
            # Profile facts
            if context['profile_facts']:
                memory_section += "Fakta om brukeren:\n"
                for fact in context['profile_facts']:  # Vis alle facts (økt til 40)
                    memory_section += f"- {fact['key']}: {fact['value']}"
                    
                    # Vis metadata hvis tilgjengelig og relevant
                    if fact.get('metadata') and fact['metadata']:
                        meta = fact['metadata']
                        # Parse JSON hvis det er en string
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except:
                                meta = {}
                        
                        # Vis kun relevante metadata-felt
                        if 'learned_at' in meta:
                            learned_date = meta['learned_at'].split('T')[0]
                            memory_section += f" (lært {learned_date})"
                        if 'verified' in meta and meta['verified']:
                            memory_section += " [verifisert]"
                    
                    memory_section += "\n"
                
                memory_section += "\nViktig: Når du refererer til familiemedlemmer, ALLTID bruk deres navn i stedet for 'søster 1/2/3' eller 'din andre søster'. Dette gjør samtalen mer personlig og naturlig.\n"
                memory_section += "\nOBS: Datoer i formatet 'DD-MM' er dag-måned (f.eks. '21-11' = 21. november). Når du svarer om fødselsdager, inkluder både dag og måned.\n"
                
                # Bygg eksplisitt oversikt over søstrene direkte fra databasen (ikke kontekst) 
                # for å sikre at ALLE søstre inkluderes
                sisters = {}
                conn = memory_manager._get_connection()
                c = conn.cursor()
                c.execute("SELECT key, value FROM profile_facts WHERE key IN ('sister_1_name', 'sister_2_name', 'sister_3_name', 'sister_1_age_relation', 'sister_2_age_relation', 'sister_3_age_relation')")
                for row in c.fetchall():
                    key = row[0]
                    value = row[1]
                    sister_num = key.split('_')[1]
                    if sister_num not in sisters:
                        sisters[sister_num] = {}
                    if key.endswith('_name'):
                        sisters[sister_num]['name'] = value
                    elif key.endswith('_age_relation'):
                        sisters[sister_num]['age_relation'] = value
                conn.close()
                
                if sisters:
                    memory_section += "\nKRITISK - Søstrene (bruk ALLTID denne informasjonen):\n"
                    for num, info in sorted(sisters.items()):
                        if 'name' in info and 'age_relation' in info:
                            memory_section += f"- {info['name']} er den {info['age_relation']} søsteren\n"

            
            # Relevant memories
            if context['relevant_memories']:
                memory_section += "\n### Relevante minner ###\n"
                memory_section += "Dette husker du fra tidligere samtaler:\n\n"
                for mem_text, score in context['relevant_memories'][:5]:  # Top 5 memories
                    # Konverter tredjeperson til førsteperson for bedre forståelse
                    converted = mem_text
                    converted = converted.replace("Brukeren", "Du")
                    converted = converted.replace("brukeren", "du")
                    converted = converted.replace("Anda", "meg")
                    # Juster verbformer hvis nødvendig
                    if converted.startswith("Du "):
                        # "Du planlegger" -> OK
                        # "Du skal" -> OK
                        # "Du lastet" -> "Du lastet" (OK)
                        pass
                    memory_section += f"- {converted}\n"
                memory_section += "\nBruk denne informasjonen når du svarer!\n"
            
            # Recent topics
            if context['recent_topics']:
                topics = [t['topic'] for t in context['recent_topics'][:3]]
                memory_section += f"\nSiste emner vi har snakket om: {', '.join(topics)}\n"
            
            # IKKE legg til memory_section her ennå
            print(f"✅ Memory context bygget ({len(context['profile_facts'])} facts, {len(context['relevant_memories'])} minner)", flush=True)
        except Exception as e:
            print(f"⚠️ Kunne ikke bygge memory context: {e}", flush=True)
    
    # Legg til Samanthas identitet fra konfigurasjonsfil
    try:
        identity_file = "/home/admog/Code/chatgpt-and/samantha_identity.json"
        if os.path.exists(identity_file):
            with open(identity_file, 'r', encoding='utf-8') as f:
                identity = json.load(f)
            
            samantha_identity = f"""

### Din identitet ###
Du er {identity['name']} - {identity['type']}.
- Navn: {identity['name']}
- Bursdag: {identity['birthday']}
- Skapt av: {identity['creator']}

Dine fysiske egenskaper:
"""
            for feature in identity.get('physical_features', []):
                samantha_identity += f"- {feature}\n"
            
            samantha_identity += "\nDin personlighet:\n"
            for trait in identity.get('personality_traits', []):
                samantha_identity += f"- {trait}\n"
            
            samantha_identity += "\nDine preferanser:\n"
            for pref in identity.get('preferences', []):
                samantha_identity += f"- {pref}\n"
            
            if identity.get('additional_info'):
                samantha_identity += "\nEkstra info:\n"
                for info in identity['additional_info']:
                    samantha_identity += f"- {info}\n"
            
            system_content += samantha_identity
    except Exception as e:
        print(f"⚠️ Kunne ikke laste identitet: {e}", flush=True)
    
    if personality_prompt:
        system_content += "\n\n" + personality_prompt
        print(f"Bruker personlighet: {personality}", flush=True)
    
    # Legg til memory section HER - rett før TTS-instruksjon
    # Dette sikrer at minnene er det siste AI-en leser før den svarer
    if memory_section:
        system_content += memory_section
    
    # Viktig instruksjon for TTS-kompatibilitet
    system_content += "\n\n### VIKTIG: Formatering ###\nDu svarer med tale (text-to-speech), så:\n- IKKE bruk Markdown-formatering (**, *, __, _, -, •, ###)\n- IKKE bruk kulepunkter eller lister med symboler\n- Skriv naturlig tekst som høres bra ut når det leses opp\n- Bruk komma og punktum for pauser, ikke linjeskift eller symboler\n- Hvis du MÅ liste opp ting, bruk naturlig språk: 'For det første... For det andre...' eller 'Den første er X, den andre er Y'"
    
    final_messages.insert(0, {"role": "system", "content": system_content})
    
    # DEBUG: Logg om minner er inkludert
    if memory_section and "### Relevante minner ###" in memory_section:
        print(f"📝 DEBUG: Memory section er inkludert i prompt", flush=True)
        # Logg de første 200 tegnene av memory section
        mem_preview = memory_section[:200].replace('\n', ' ')
        print(f"📝 Preview: {mem_preview}...", flush=True)
    else:
        print(f"⚠️ DEBUG: Memory section mangler eller er tom!", flush=True)
    
    # Definer function tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Hent værmelding og temperatur for et spesifikt sted i Norge. Kan hente vær for nå, i dag eller i morgen.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Navnet på stedet/byen i Norge, f.eks. 'Oslo', 'Sokndal', 'Bergen'"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Tidsramme for værmeldingen",
                            "enum": ["now", "today", "tomorrow"],
                            "default": "now"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_hue_lights",
                "description": "Kontroller Philips Hue smarte lys i hjemmet. Kan skru på/av, dimme, eller endre farge.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["on", "off", "dim", "brighten"],
                            "description": "Hva som skal gjøres med lysene"
                        },
                        "room": {
                            "type": "string",
                            "description": "Navnet på rommet eller lyset (f.eks. 'stue', 'soverom'). La være None for alle lys."
                        },
                        "brightness": {
                            "type": "integer",
                            "description": "Lysstyrke i prosent (0-100). Valgfritt."
                        },
                        "color": {
                            "type": "string",
                            "enum": ["rød", "blå", "grønn", "gul", "hvit", "rosa", "lilla", "oransje"],
                            "description": "Farge på lyset. Valgfritt."
                        }
                    },
                    "required": ["action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "control_beak",
                "description": "Skru nebbet på eller av. Når nebbet er av, brukes LED-lys i stedet.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "description": "true for å skru på nebbet, false for å skru det av"
                        }
                    },
                    "required": ["enabled"]
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
        # Modellen vil kalle værfunksjonen eller Hue-funksjonen
        tool_call = message["tool_calls"][0]
        function_name = tool_call["function"]["name"]
        function_args = json.loads(tool_call["function"]["arguments"])
        
        print(f"ChatGPT kaller funksjon: {function_name} med args: {function_args}", flush=True)
        
        # Kall faktisk funksjon
        if function_name == "get_weather":
            location = function_args.get("location", "")
            timeframe = function_args.get("timeframe", "now")
            result = get_weather(location, timeframe)
        elif function_name == "control_hue_lights":
            action = function_args.get("action")
            room = function_args.get("room")
            brightness = function_args.get("brightness")
            color = function_args.get("color")
            result = control_hue_lights(action, room, brightness, color)
        elif function_name == "control_beak":
            enabled = function_args.get("enabled")
            result = control_beak(enabled)
        else:
            result = "Ukjent funksjon"
        
        # Legg til function call og resultat i conversation
        final_messages.append(message)
        final_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": function_name,
            "content": result
        })
        
        # Kall API igjen med værdata
        data["messages"] = final_messages
        response2 = requests.post(url, headers=headers, json=data)
        response2.raise_for_status()
        reply_content = response2.json()["choices"][0]["message"]["content"]
        
        # Sjekk om brukerens opprinnelige melding var en takk
        user_message = messages[-1]["content"].lower() if messages else ""
        is_thank_you = any(word in user_message for word in ["takk", "tusen takk", "mange takk", "takker"])
        
        return (reply_content, is_thank_you)
    
    # Ingen function call, returner vanlig svar
    user_message = messages[-1]["content"].lower() if messages else ""
    is_thank_you = any(word in user_message for word in ["takk", "tusen takk", "mange takk", "takker"])
    
    return (message["content"], is_thank_you)

def check_ai_queries(api_key, speech_config, beak, memory_manager=None, user_manager=None):
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
                    response = chatgpt_query(messages, api_key, memory_manager=memory_manager, user_manager=user_manager)
                    
                    # Håndter tuple response
                    if isinstance(response, tuple):
                        response_text = response[0]
                    else:
                        response_text = response
                    
                    # Skriv respons til fil
                    with open(AI_RESPONSE_FILE, 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    
                    # Si svaret
                    speak(response, speech_config, beak)
                    
                    print(f"AI-respons: {response}", flush=True)
        except Exception as e:
            print(f"Feil i AI-query tråd: {e}", flush=True)
        
        time.sleep(0.5)  # Sjekk hver halve sekund

def ask_for_user_switch(speech_config, beak, user_manager):
    """
    Håndter brukerbytte-dialog
    
    Returns:
        True hvis brukeren ble byttet vellykket
    """
    try:
        # Spør hvem som snakker
        speak("Hvem er du?", speech_config, beak)
        
        name_response = recognize_speech_from_mic()
        if not name_response:
            speak("Jeg hørte ikke navnet ditt. Prøv igjen ved å si mitt navn først.", speech_config, beak)
            return False
        
        # Ekstraher navnet (fjern "jeg er", "dette er", etc.)
        name_clean = name_response.strip().lower()
        name_clean = name_clean.replace("jeg er ", "").replace("dette er ", "").replace("jeg heter ", "")
        name_clean = name_clean.strip().title()  # Kapitalisér første bokstav
        
        print(f"👤 Bruker sa navnet: {name_clean}", flush=True)
        
        # Søk etter bruker i database
        found_user = user_manager.find_user_by_name(name_clean)
        
        if found_user:
            # Bruker funnet - bekreft
            relation_text = found_user['relation']
            if found_user['matched_key']:
                speak(f"Er du {found_user['display_name']}, Osmunds {relation_text}?", speech_config, beak)
            else:
                speak(f"Er du {found_user['display_name']}?", speech_config, beak)
            
            confirmation = recognize_speech_from_mic()
            if confirmation and ('ja' in confirmation.lower() or 'stemmer' in confirmation.lower() or 'riktig' in confirmation.lower()):
                # Bytt bruker
                user_manager.switch_user(
                    username=found_user['username'],
                    display_name=found_user['display_name'],
                    relation=found_user['relation']
                )
                
                speak(f"Velkommen {found_user['display_name']}! Hva kan jeg hjelpe deg med?", speech_config, beak)
                print(f"✅ Byttet til bruker: {found_user['display_name']}", flush=True)
                return True
            else:
                speak("Beklager, da misforsto jeg. Prøv igjen.", speech_config, beak)
                return False
        else:
            # Ny bruker - spør om relasjon
            speak(f"Hei {name_clean}! Jeg kjenner deg ikke fra før. Hva er din relasjon til Osmund?", speech_config, beak)
            
            relation_response = recognize_speech_from_mic()
            if not relation_response:
                speak("Jeg hørte ikke hva du sa. Prøv igjen senere.", speech_config, beak)
                return False
            
            relation_clean = relation_response.strip().lower()
            
            # Enkel mapping av vanlige svar
            relation_map = {
                'venn': 'venn',
                'venninne': 'venn',
                'kollega': 'kollega',
                'gjest': 'gjest',
                'besøkende': 'gjest',
                'familie': 'familie',
                'søster': 'søster',
                'bror': 'bror',
                'mor': 'mor',
                'far': 'far'
            }
            
            relation = 'gjest'  # Default
            for key, value in relation_map.items():
                if key in relation_clean:
                    relation = value
                    break
            
            # Opprett ny bruker
            username = name_clean.lower().replace(' ', '_')
            user_manager.switch_user(
                username=username,
                display_name=name_clean,
                relation=relation
            )
            
            speak(f"Velkommen {name_clean}! Hyggelig å møte deg. Hva kan jeg hjelpe deg med?", speech_config, beak)
            print(f"✅ Opprettet og byttet til ny bruker: {name_clean} ({relation})", flush=True)
            return True
            
    except Exception as e:
        print(f"⚠️ Feil under brukerbytte: {e}", flush=True)
        speak("Beklager, det oppstod en feil. Jeg fortsetter som Osmund.", speech_config, beak)
        return False

def main():
    # Prøv å initialisere servo, men fortsett uten hvis den ikke finnes
    beak = None
    try:
        beak = Beak(SERVO_CHANNEL, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
        print("Servo initialisert OK", flush=True)
    except Exception as e:
        print(f"Advarsel: Kunne ikke initialisere servo (fortsetter uten): {e}", flush=True)
        beak = None
    
    # Initialiser memory manager
    try:
        memory_manager = MemoryManager()
        print("✅ Memory system initialisert", flush=True)
    except Exception as e:
        print(f"⚠️ Memory system feilet (fortsetter uten): {e}", flush=True)
        memory_manager = None
    
    # Initialiser user manager
    try:
        user_manager = UserManager()
        current_user = user_manager.get_current_user()
        print(f"✅ User system initialisert - nåværende bruker: {current_user['display_name']} ({current_user['relation']})", flush=True)
    except Exception as e:
        print(f"⚠️ User system feilet (fortsetter uten): {e}", flush=True)
        user_manager = None
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    tts_key = os.getenv("AZURE_TTS_KEY")
    tts_region = os.getenv("AZURE_TTS_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
    speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"

    # Last meldinger fra konfigurasjonsfil
    messages_config = {}
    try:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                messages_config = json.load(f)
                print("✅ Lastet meldinger fra messages.json", flush=True)
    except Exception as e:
        print(f"⚠️ Kunne ikke laste messages.json: {e}", flush=True)
    
    # Fallback til hardkodede meldinger hvis fil mangler
    if not messages_config:
        messages_config = {
            "startup_messages": {
                "with_network": "Kvakk kvakk! Jeg er nå klar for andeprat. Min IP-adresse er {ip}. Du finner kontrollpanelet på port 3000. Si navnet mitt for å starte en samtale!",
                "without_network": "Kvakk kvakk! Jeg er klar, men jeg klarte ikke å koble til nettverket og har ingen IP-adresse ennå. Sjekk wifi-tilkoblingen din. Si navnet mitt for å starte en samtale!"
            },
            "conversation": {
                "greeting": "Hei på du, hva kan jeg hjelpe deg med?",
                "no_response_timeout": "Jeg hører deg ikke. Da venter jeg til du sier navnet mitt igjen.",
                "no_response_retry": "Beklager, jeg hørte ikke hva du sa. Prøv igjen.",
                "goodbye": "Da venter jeg til du sier navnet mitt igjen."
            },
            "web_interface": {
                "start_conversation": "Hei på du, hva kan jeg hjelpe deg med?"
            }
        }

    # Start bakgrunnstråd for AI-queries fra kontrollpanelet
    import threading
    ai_thread = threading.Thread(target=check_ai_queries, args=(api_key, speech_config, beak, memory_manager, user_manager), daemon=True)
    ai_thread.start()
    print("AI-query tråd startet", flush=True)

    # Oppstartshilsen (ikke la en TTS-feil stoppe tjenesten ved boot)
    time.sleep(3)  # Vent litt lenger for at systemet skal være klart
    
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
        greeting = messages_config['startup_messages']['with_network'].replace('{ip}', ip_address.replace('.', ' punkt '))
        print(f"Oppstartshilsen med IP: {ip_address}", flush=True)
    else:
        greeting = messages_config['startup_messages']['without_network']
        print("Oppstartshilsen uten IP (nettverk ikke klart)", flush=True)
    
    # Prøv å si oppstartshilsen flere ganger hvis TTS/nettverk ikke er klart
    greeting_success = False
    for greeting_attempt in range(3):  # Prøv opptil 3 ganger
        try:
            speak(greeting, speech_config, beak)
            print("Oppstartshilsen ferdig", flush=True)
            greeting_success = True
            break
        except Exception as e:
            print(f"Oppstartshilsen mislyktes (forsøk {greeting_attempt + 1}/3): {e}", flush=True)
            if greeting_attempt < 2:  # Ikke vent etter siste forsøk
                time.sleep(5)  # Vent 5 sekunder før neste forsøk
    
    if not greeting_success:
        print("Oppstartshilsen kunne ikke sies etter 3 forsøk - fortsetter uten hilsen", flush=True)
    
    print("Anda venter på wake word... (si 'quack quack')", flush=True)
    while True:
        external_message = wait_for_wake_word()
        
        # Sjekk timeout før ny samtale
        if user_manager:
            try:
                # Hent siste melding tidspunkt fra database
                last_message_time = None
                if memory_manager:
                    conn = memory_manager._get_connection()
                    c = conn.cursor()
                    c.execute("SELECT timestamp FROM messages ORDER BY timestamp DESC LIMIT 1")
                    row = c.fetchone()
                    if row:
                        last_message_time = datetime.fromisoformat(row['timestamp'])
                    conn.close()
                
                # Sjekk om timeout skal trigges
                if user_manager.check_timeout(last_message_time):
                    current_user = user_manager.get_current_user()
                    print(f"⏰ Timeout for {current_user['display_name']} - bytter til Osmund", flush=True)
                    
                    # Bytt til Osmund
                    user_manager.switch_user('Osmund', 'Osmund', 'owner')
                    
                    # Si beskjed til Osmund
                    speak("Hei Osmund, jeg har byttet tilbake til deg etter timeout.", speech_config, beak)
            except Exception as e:
                print(f"⚠️ Feil ved timeout-sjekk: {e}", flush=True)
        
        # Hvis det er en ekstern melding, sjekk type
        if external_message:
            if external_message == '__START_CONVERSATION__':
                # Start samtale direkte med en kort hilsen
                print("Starter samtale via web-interface", flush=True)
                greeting_msg = messages_config['web_interface']['start_conversation']
                
                # Hent nåværende bruker fra user_manager
                if user_manager:
                    current_user = user_manager.get_current_user()
                    user_name = current_user['display_name']
                    greeting_msg = greeting_msg.replace('{name}', user_name)
                else:
                    greeting_msg = greeting_msg.replace('{name}', 'på du')
                
                speak(greeting_msg, speech_config, beak)
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
            greeting_msg = messages_config['conversation']['greeting']
            
            # Hent nåværende bruker fra user_manager
            if user_manager:
                current_user = user_manager.get_current_user()
                user_name = current_user['display_name']
                greeting_msg = greeting_msg.replace('{name}', user_name)
            else:
                greeting_msg = greeting_msg.replace('{name}', 'på du')
            
            speak(greeting_msg, speech_config, beak)
        
        # Start samtale (enten fra wake word eller samtale-trigger)
        messages = []
        no_response_count = 0  # Teller antall ganger uten svar
        
        while True:
            prompt = recognize_speech_from_mic()  # Ingen device_name argument, bruker hw:1,0 internt
            if not prompt:
                no_response_count += 1
                if no_response_count >= 2:
                    speak(messages_config['conversation']['no_response_timeout'], speech_config, beak)
                    break
                speak(messages_config['conversation']['no_response_retry'], speech_config, beak)
                continue
            
            # Reset teller når vi får svar
            no_response_count = 0
            
            # Sjekk for stopp-kommando (fjern tegnsetting først)
            prompt_clean = prompt.strip().lower().replace(".", "").replace(",", "").replace("!", "")
            if "stopp" in prompt_clean:
                speak(messages_config['conversation']['goodbye'], speech_config, beak)
                break
            
            # Sjekk for brukerbytte-kommando
            if user_manager and ("bytt bruker" in prompt_clean or "skifte bruker" in prompt_clean or "bytte bruker" in prompt_clean):
                if ask_for_user_switch(speech_config, beak, user_manager):
                    # Vellykket brukerbytte - start ny samtale
                    break
                else:
                    # Mislykket - fortsett samtale
                    continue
            
            messages.append({"role": "user", "content": prompt})
            try:
                blink_yellow_purple()  # Start blinkende gul LED under tenkepause
                result = chatgpt_query(messages, api_key, memory_manager=memory_manager, user_manager=user_manager)
                off()           # Slå av blinking når svaret er klart
                
                # Håndter tuple-retur (svar, is_thank_you)
                if isinstance(result, tuple):
                    reply, is_thank_you = result
                else:
                    # Fallback for gammel kode
                    reply = result
                    is_thank_you = False
                
                print("ChatGPT svar:", reply, flush=True)
                speak(reply, speech_config, beak)
                messages.append({"role": "assistant", "content": reply})
                
                # Lagre melding til memory database (asynkront prosessert av worker)
                if memory_manager and user_manager:
                    try:
                        current_user = user_manager.get_current_user()
                        memory_manager.save_message(prompt, reply, user_name=current_user['username'])
                        
                        # Oppdater aktivitet og message count
                        user_manager.update_activity()
                        user_manager.increment_message_count(current_user['username'])
                    except Exception as e:
                        print(f"⚠️ Kunne ikke lagre melding: {e}", flush=True)
                
                # Hvis brukeren takket, gå tilbake til wake word
                if is_thank_you:
                    print("Bruker takket - går tilbake til wake word", flush=True)
                    break
            except Exception as e:
                off()
                print("Feil:", e)
                speak("Beklager, det oppstod en feil.", speech_config, beak)
            #blink_yellow()  # Start blinkende gul LED under "tenkepause"
            set_green()  # Eller annen farge for neste fase

if __name__ == "__main__":
    main()