from pydub import AudioSegment
from scipy.signal import resample
import sounddevice as sd
import time
import random
from duck_beak import Beak, CLOSE_DEG, OPEN_DEG, TRIM_DEG, JITTER, BEAT_MS_MIN, BEAT_MS_MAX
GPIO_SERVO = 12  # PWM-pin til servo (GPIO12 - fri fra I2S)
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
DEFAULT_VOICE = "nb-NO-FinnNeural"
# Fil for nebbet-kontroll
BEAK_FILE = "/tmp/duck_beak.txt"
# Fil for talehastighet (0-100, 50 = normal)
SPEED_FILE = "/tmp/duck_speed.txt"
# Filer for AI-query fra kontrollpanel
AI_QUERY_FILE = "/tmp/duck_ai_query.txt"
AI_RESPONSE_FILE = "/tmp/duck_ai_response.txt"

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
    """Finn sounddevice index for HifiBerry DAC"""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'hifiberry' in device['name'].lower() and device['max_output_channels'] > 0:
            print(f"Fant HifiBerry DAC: device {i} ({device['name']})", flush=True)
            return i
    # Fallback til default
    print("Fant ikke HifiBerry DAC, bruker default", flush=True)
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
    recognizer = vosk.KaldiRecognizer(VOSK_MODEL, 48000)  # Bruk 48000 Hz (USB mikrofon støtter dette)
    print("Si 'Ulrika', 'Alexa', 'Siri' eller 'Oscar' for å vekke anda!")
    
    # Finn USB mikrofon dynamisk
    usb_mic_device = find_usb_microphone()
    
    # Prøv å åpne mikrofon-input i en retry-loop slik at tjenesten ikke krasjer ved boot
    # hvis ALSA-enheten ikke er klar umiddelbart. Vi vil forsøke igjen hvert par sekunder
    # til vi lykkes.
    while True:
        try:
            with sd.RawInputStream(samplerate=48000, blocksize=24000, dtype='int16', channels=1, device=usb_mic_device) as stream:
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
                    
                    data = stream.read(24000)[0]
                    if recognizer.AcceptWaveform(bytes(data)):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").lower().strip()
                        # Ignorer tomme eller veldig korte resultater (støy)
                        if len(text) > 2:  # Bare print hvis det er mer enn 2 tegn
                            print(f"Gjenkjent: {text}")
                            if "alexa" in text or "ulrika" in text or "siri" in text or "oskar" in text or "anders" in text or "astrid" in text:
                                print("Wake word oppdaget!")
                                return None  # Wake word, ingen direkte melding
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
    
    # Konverter speed_value (0-100) til rate percentage
    # 0 = -50%, 50 = 0%, 100 = +50%
    rate_percent = (speed_value - 50)
    rate_str = f"{rate_percent:+d}%" if rate_percent != 0 else "0%"
    
    print(f"Bruker TTS-stemme: {voice_name}, Nebbet: {'på' if beak_enabled else 'av'}, Hastighet: {rate_str}", flush=True)
    
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
            # Last inn og gjør pitch-shift
            sound = AudioSegment.from_wav(tmpfile.name)
            octaves = 1.5  # Mye høyere for ekte and-stemme
            new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
            shifted = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
            shifted = shifted.set_frame_rate(48000)  # Sett til 48kHz direkte
            
            import io
            shifted_io = io.BytesIO()
            shifted.export(shifted_io, format="wav")
            shifted_io.seek(0)
            
            with wave.open(shifted_io, 'rb') as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                audio = wf.readframes(n_frames)
            
            print(f"After pitch-shift: {framerate} Hz, {n_channels} ch, {sampwidth*8} bit")
            
            if sampwidth == 2:
                dtype = np.int16
            elif sampwidth == 1:
                dtype = np.uint8
            else:
                raise ValueError("Bare 8/16-bit wav støttes")
            
            samples = np.frombuffer(audio, dtype=dtype)
            if n_channels > 1:
                samples = samples[::n_channels]
            samples = samples.astype(np.float32) / np.iinfo(dtype).max

            # Legg til fade-in/fade-out for å unngå klikkelyd
            fade_samples = int(framerate * 0.01)  # 10ms fade
            if len(samples) > fade_samples * 2:
                # Fade in
                fade_in = np.linspace(0, 1, fade_samples)
                samples[:fade_samples] *= fade_in
                # Fade out
                fade_out = np.linspace(1, 0, fade_samples)
                samples[-fade_samples:] *= fade_out

            # Skal allerede være 48000 Hz etter pitch-shift
            target_rate = 48000
            if framerate != target_rate:
                print(f"Resampling fra {framerate} Hz til {target_rate} Hz...")
                num_samples_new = int(len(samples) * target_rate / framerate)
                samples = resample(samples, num_samples_new)
                framerate = target_rate

            # Større blocksize for jevnere lyd (64ms som original)
            blocksize = int(framerate * 0.064)
            
            def callback(outdata, frames, time_info, status):
                nonlocal idx
                if status:
                    print(f"Audio status: {status}")
                
                chunk = samples[idx:idx+frames]
                
                # Oppdater nebb umiddelbart basert på faktisk lyd (original metode)
                if beak_enabled and len(chunk) > 0:
                    amp = np.sqrt(np.mean(chunk**2))
                    beak.open_pct(min(max(amp * 3.5, 0.05), 1.0))  # Min 5% for å unngå kollisjon
                
                # Støtt både mono (1 kanal) og stereo (2 kanaler)
                num_channels = outdata.shape[1] if len(outdata.shape) > 1 else 1
                if len(chunk) < frames:
                    for ch in range(num_channels):
                        outdata[:len(chunk),ch] = chunk
                        outdata[len(chunk):,ch] = 0
                else:
                    for ch in range(num_channels):
                        outdata[:,ch] = chunk
                idx += frames
            
            idx = 0
            
            # Finn HifiBerry DAC dynamisk (card-nummer kan endre seg ved reboot)
            tried_device = find_hifiberry_output()
            stream_started = False
            max_attempts = 3
            retry_delay = 1.0
            
            for attempt in range(max_attempts):
                try:
                    # Prøv HifiBerry med 2 kanaler
                    with sd.OutputStream(samplerate=framerate, device=tried_device, channels=2, dtype='float32', 
                                       blocksize=blocksize, callback=callback):
                        stream_started = True
                        while idx < len(samples):
                            sd.sleep(int(1000 * blocksize / framerate))
                    break  # Suksess, avslutt loop
                except Exception as e:
                    print(f"Audio device {tried_device} feil (forsøk {attempt+1}/{max_attempts}): {e}")
                    if attempt < max_attempts - 1:
                        print(f"Venter {retry_delay}s før nytt forsøk...")
                        time.sleep(retry_delay)
                    else:
                        # Siste forsøk: prøv default device
                        print("Prøver default device...")
                        try:
                            with sd.OutputStream(samplerate=framerate, device=None, channels=2, dtype='float32', 
                                               blocksize=blocksize, callback=callback):
                                stream_started = True
                                while idx < len(samples):
                                    sd.sleep(int(1000 * blocksize / framerate))
                        except Exception as e2:
                            print(f"Default device også feilet: {e2}")
            
            if not stream_started:
                print("Kunne ikke starte lydstrøm. Avslutter tale-funksjon uten å spille av.")
            
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
    beak = Beak(GPIO_SERVO, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
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
    time.sleep(2)  # Vent litt for at systemet skal være klart
    try:
        # Hent IP-adresse
        import socket
        ip_address = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except:
            pass
        
        if ip_address and ip_address != "127.0.0.1":
            greeting = f"Kvakk kvakk! Jeg er nå klar for andeprat. Min IP-adresse er {ip_address.replace('.', ' punkt ')}. Du finner kontrollpanelet på port 3000. Si navnet mitt for å starte en samtale!"
        else:
            greeting = "Kvakk kvakk! Jeg er nå klar for andeprat. Si navnet mitt for å starte en samtale!"
        
        speak(greeting, speech_config, beak)
        print("Oppstartshilsen ferdig", flush=True)
    except Exception as e:
        print(f"Oppstartshilsen mislyktes (audio ikke klar ennå): {e}", flush=True)
    
    print("Anda venter på wake word... (si 'quack quack')", flush=True)
    while True:
        external_message = wait_for_wake_word()
        
        # Hvis det er en ekstern melding, sjekk om det er en samtale-trigger
        if external_message:
            if external_message == '__START_CONVERSATION__':
                # Start samtale direkte uten hilsen
                print("Starter samtale via web-interface", flush=True)
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