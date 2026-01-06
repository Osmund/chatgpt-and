from pydub import AudioSegment
from scipy.signal import resample
import sounddevice as sd
import time
import random
from duck_beak import Beak, CLOSE_DEG, OPEN_DEG, TRIM_DEG, JITTER, BEAT_MS_MIN, BEAT_MS_MAX, SERVO_CHANNEL
import requests                                                                                                                                                                                           
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import numpy as np
from rgb_duck import set_blue, set_red, set_green, off, blink_yellow, stop_blink,blink_yellow_purple
import vosk
import json
import sys
import signal
import atexit

# Flush stdout umiddelbart slik at print vises i journalctl
sys.stdout.reconfigure(line_buffering=True)

# MAX98357A SD pin skal kobles til fast 3.3V (pin 1 eller 17)
# Dette holder forsterkeren alltid på for rask respons
print("MAX98357A SD pin skal være koblet til 3.3V - forsterker alltid på", flush=True)

# Last inn Vosk-modellen GLOBALT, kun én gang
VOSK_MODEL = vosk.Model("vosk-model-small-sv-rhasspy-0.15")

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

# Wake words som støttes
WAKE_WORDS = ['anda', 'vakna', 'hej', 'hallå', 'assistent', 'alfred', 'alexa', 'ulrika', 'siri', 'oskar']

def wait_for_wake_word():
    set_blue()
    recognizer = vosk.KaldiRecognizer(VOSK_MODEL, 48000)  # Bruk 48000 Hz (USB mikrofon støtter dette)
    recognizer.SetWords(True)  # Aktiver word-level timestamps
    wake_words_display = ', '.join([f"'{w.capitalize()}'" for w in WAKE_WORDS[:6]])
    print(f"Si {wake_words_display} eller flere for å vekke anda!")
    
    # Finn USB mikrofon dynamisk
    usb_mic_device = find_usb_microphone()
    
    # Prøv å åpne mikrofon-input i en retry-loop slik at tjenesten ikke krasjer ved boot
    # hvis ALSA-enheten ikke er klar umiddelbart. Vi vil forsøke igjen hvert par sekunder
    # til vi lykkes.
    while True:
        try:
            # Mindre blocksize (8000 = 0.17s) gir bedre respons for korte wake words
            with sd.RawInputStream(samplerate=48000, blocksize=8000, dtype='int16', channels=1, device=usb_mic_device) as stream:
                while True:
                    # Sjekk om det finnes en ekstern melding
                    if os.path.exists(MESSAGE_FILE):
                        try:
                            with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
                                message = f.read().strip()
                            os.remove(MESSAGE_FILE)
                            if message:
                                print(f"Ekstern melding mottatt: {message}", flush=True)
                                # Sjekk om det er en trigger for å starte samtale
                                if message == '__START_CONVERSATION__':
                                    return '__START_CONVERSATION__'  # Spesiell trigger for samtale
                                else:
                                    return message  # Returner meldingen direkte
                        except Exception as e:
                            print(f"Feil ved lesing av meldingsfil: {e}", flush=True)
                    
                    data = stream.read(8000)[0]
                    if recognizer.AcceptWaveform(bytes(data)):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").lower().strip()
                        if text:  # Bare sjekk om ikke tom
                            print(f"Gjenkjent: {text}")
                            # Sjekk om noen av wake words er i teksten
                            if any(wake_word in text for wake_word in WAKE_WORDS):
                                print("Wake word oppdaget!")
                                return None  # Wake word, ingen direkte melding
                    else:
                        # Sjekk partial results for raskere respons
                        partial = json.loads(recognizer.PartialResult())
                        partial_text = partial.get("partial", "").lower().strip()
                        if partial_text and any(wake_word in partial_text for wake_word in WAKE_WORDS):
                            print(f"Wake word oppdaget i partial: {partial_text}")
                            recognizer.Reset()  # Reset for neste deteksjon
                            return None
        except StopIteration:
            return None  # Wake word oppdaget via StopIteration
        except Exception as e:
            print(f"Input-enhet ikke klar ennå (prøver igjen om 2s): {e}")
            time.sleep(2)
            continue
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
    
    # Legg til system-prompt hvis personlighet er valgt
    final_messages = messages.copy()
    if personality_prompt:
        final_messages.insert(0, {"role": "system", "content": personality_prompt})
        print(f"Bruker personlighet: {personality}", flush=True)
    
    data = {
        "model": model,
        "messages": final_messages
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

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
        
        # Hvis det er en ekstern melding, sjekk om det er en samtale-trigger
        if external_message:
            if external_message == '__START_CONVERSATION__':
                # Start samtale direkte med en kort hilsen
                print("Starter samtale via web-interface", flush=True)
                speak("Hei på du, hva kan jeg hjelpe deg med?", speech_config, beak)
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