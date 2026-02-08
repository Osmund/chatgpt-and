"""
Duck Audio Module
Handles TTS (Text-to-Speech), audio playback, and beak control.
Supports Azure TTS and OpenAI TTS engines (configured via TTS_ENGINE).
"""

import sounddevice as sd
import numpy as np
from pydub import AudioSegment
from scipy.signal import resample
import tempfile
import os
import time
import threading
import subprocess
from scripts.hardware.rgb_duck import set_red, off, stop_blink, set_intensity
import azure.cognitiveservices.speech as speechsdk

from src.duck_config import (
    DEFAULT_VOICE, FADE_MS, BEAK_CHUNK_MS, BEAK_PRE_START_MS,
    TTS_ENGINE, OPENAI_TTS_VOICE, OPENAI_TTS_MODEL, DUCK_PITCH_OCTAVES
)
from src.duck_settings import get_settings


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


def control_beak(enabled):
    """Slå nebb on/off via DuckSettings (persisteres automatisk til JSON)."""
    try:
        value = 'on' if enabled else 'off'
        get_settings().beak = value
        return {"status": "success", "beak_enabled": enabled}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def speak(text, speech_config, beak):
    """
    Konverter tekst til tale ved hjelp av Azure TTS.
    Kontrollerer nebbet eller LED basert på lydamplitude.
    """
    # La gul/lilla blinking fortsette under TTS-prosessering
    # set_red() vil stoppe blinking når lyden starter
    
    # Mute Duck-Vision mikrofon mens Samantha snakker
    try:
        from src.duck_services import get_services
        vision_svc = get_services().get_vision_service()
        vision_svc.notify_speaking(True)
    except Exception:
        pass
    
    try:
        _speak_internal(text, speech_config, beak)
    finally:
        # Unmute Duck-Vision mikrofon når Samantha er ferdig
        try:
            from src.duck_services import get_services
            vision_svc = get_services().get_vision_service()
            vision_svc.notify_speaking(False)
        except Exception:
            pass


def _synthesize_azure(text, speech_config, voice_name, rate_str):
    """Synthesize speech using Azure TTS. Returns (wav_path, success)."""
    # Sett høyere lydkvalitet fra Azure (48kHz)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
    )
    
    # Bruk SSML med prosody for hastighetskontroll
    ssml = f'<speak version="1.0" xml:lang="nb-NO"><voice name="{voice_name}"><prosody rate="{rate_str}">{text}</prosody></voice></speak>'
    tmpfile = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmpfile.close()
    
    try:
        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmpfile.name)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return tmpfile.name, True
        else:
            print("TTS-feil:", result.reason)
            if hasattr(result, "cancellation_details"):
                print("Detaljer:", result.cancellation_details.reason, result.cancellation_details.error_details)
            os.unlink(tmpfile.name)
            return None, False
    except Exception as e:
        print(f"Azure TTS feil: {e}", flush=True)
        try:
            os.unlink(tmpfile.name)
        except:
            pass
        return None, False


def _synthesize_openai(text, speed_factor=1.0):
    """Synthesize speech using OpenAI TTS. Returns (wav_path, success)."""
    try:
        from openai import OpenAI
        client = OpenAI()
        
        voice = OPENAI_TTS_VOICE
        model = OPENAI_TTS_MODEL
        
        print(f"🔊 OpenAI TTS: model={model}, voice={voice}, speed={speed_factor:.2f}", flush=True)
        
        # OpenAI TTS returnerer audio direkte
        # Bruk wav format for enkel prosessering
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed_factor,
            response_format="wav",
        )
        
        # Skriv til temp-fil
        tmpfile = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmpfile.close()
        
        response.stream_to_file(tmpfile.name)
        
        print(f"✅ OpenAI TTS ferdig: {tmpfile.name}", flush=True)
        return tmpfile.name, True
        
    except Exception as e:
        print(f"OpenAI TTS feil: {e}", flush=True)
        return None, False


def _speak_internal(text, speech_config, beak):
    """Internal TTS implementation. Supports Azure and OpenAI TTS engines."""
    # Fjern Markdown-formatering før TTS
    text = clean_markdown_for_tts(text)
    
    # Hent alle TTS-settings atomisk fra DuckSettings
    tts = get_settings().get_tts_settings()
    voice_name = tts['voice']
    beak_enabled = tts['beak_enabled']
    speed_value = tts['speed']
    volume_value = tts['volume']
    
    # Konverter volume_value (0-100) til gain multiplier (0.0-2.0, hvor 1.0 = normal)
    volume_gain = volume_value / 50.0
    
    # Konverter speed_value (0-100) til rate percentage
    # 0 = -50%, 50 = 0%, 100 = +50%
    rate_percent = (speed_value - 50)
    rate_str = f"{rate_percent:+d}%" if rate_percent != 0 else "0%"
    
    # Velg TTS-engine
    engine = TTS_ENGINE
    
    if engine == 'openai':
        # OpenAI speed: 0.25 til 4.0, standard=1.0
        # Konverter fra vår 0-100 skala: 0→0.5, 50→1.0, 100→2.0
        openai_speed = 0.5 + (speed_value / 100.0) * 1.5
        
        # Kompenser for tempo-økningen fra pitch-shift
        # Pitch-shift via resampling øker også tempo med pitch_factor
        # Så vi senker OpenAI-hastigheten tilsvarende for å bevare naturlig taleritme
        pitch_factor = 2.0 ** DUCK_PITCH_OCTAVES
        openai_speed = openai_speed / pitch_factor
        openai_speed = max(0.25, min(4.0, openai_speed))  # Clamp til OpenAI-grenser
        
        print(f"Bruker OpenAI TTS: voice={OPENAI_TTS_VOICE}, Nebbet: {'på' if beak_enabled else 'av'}, Hastighet: {openai_speed:.2f}x (kompensert for {DUCK_PITCH_OCTAVES} okt pitch), Volum: {volume_value}% (gain: {volume_gain:.2f})", flush=True)
        wav_path, success = _synthesize_openai(text, speed_factor=openai_speed)
    else:
        print(f"Bruker Azure TTS: voice={voice_name}, Nebbet: {'på' if beak_enabled else 'av'}, Hastighet: {rate_str}, Volum: {volume_value}% (gain: {volume_gain:.2f})", flush=True)
        wav_path, success = _synthesize_azure(text, speech_config, voice_name, rate_str)
    
    if not success or not wav_path:
        print("TTS-syntese feilet.", flush=True)
        return
    
    try:
        _process_and_play(wav_path, beak, beak_enabled, volume_gain)
    finally:
        # Rydd opp WAV-fil
        try:
            if os.path.exists(wav_path):
                os.unlink(wav_path)
        except:
            pass


def _process_and_play(wav_path, beak, beak_enabled, volume_gain):
    """Andifiser og spill av WAV-fil med nebb/LED-synkronisering."""
    # Last inn original lyd
    sound = AudioSegment.from_wav(wav_path)
    
    # Konverter til numpy array
    samples_original = np.array(sound.get_array_of_samples(), dtype=np.float32)
    samples_original = samples_original / (2**15)  # Normaliser til -1.0 til 1.0
    
    # Normaliser amplitude til konsistent nivå uavhengig av TTS-engine
    # (OpenAI har lavere amplitude enn Azure - dette fikser både volum og nebb)
    peak_before = np.max(np.abs(samples_original))
    if peak_before > 0.01:  # Unngå divisjon med 0 for stille lyd
        samples_original = samples_original / peak_before * 0.90
        print(f"Normalisert fra peak {peak_before:.3f} til 0.90", flush=True)
    
    # Gjør pitch-shift MED tempo endring (for and-stemme)
    # Høyere pitch = raskere tempo (som Alvin og gjengen)
    octaves = DUCK_PITCH_OCTAVES
    pitch_factor = 2.0 ** octaves
    print(f"Andifisering: {octaves} oktaver opp (pitch_factor: {pitch_factor:.2f}x)", flush=True)
    
    # Resample til færre samples = høyere pitch når spilt på original sample rate
    new_length = int(len(samples_original) / pitch_factor)
    samples = resample(samples_original, new_length)
    
    # VIKTIG: Vi beholder original framerate, men med færre samples
    # Dette gir høyere pitch (lyden spilles raskere)
    
    framerate = sound.frame_rate
    n_channels = sound.channels
    sampwidth = sound.sample_width
    
    print(f"After pitch-shift: {framerate} Hz, {n_channels} ch, {sampwidth*8} bit, {len(samples)} samples (var {len(samples_original)})")
    
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
            set_red()  # LED rød NÅR anda begynner å snakke (synkronisert med lyd)
            control_thread = threading.Thread(target=update_beak_or_led, daemon=True)
            control_thread.start()
            
            # Start aplay
            process = subprocess.Popen(['aplay', '-q', tmpwav.name], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE)
            
            # Vent på at aplay er ferdig (med timeout)
            # Beregn forventet varighet basert på lydlengde + 5 sekunder buffer
            expected_duration = len(samples) / framerate
            timeout = expected_duration + 5.0
            
            try:
                process.wait(timeout=timeout)
                stream_started = True
            except subprocess.TimeoutExpired:
                print(f"⚠️ aplay timeout etter {timeout:.1f}s - dreper prosess", flush=True)
                process.kill()
                process.wait()  # Vent på at den faktisk dør
                stream_started = False
            
            # Stopp nebb/LED-thread
            control_stop.set()
            control_thread.join(timeout=1.0)
            
            os.unlink(tmpwav.name)
            
            if process.returncode == 0:
                stream_started = True
            elif process.returncode != -9:  # -9 = SIGKILL (vår timeout)
                try:
                    stderr = process.stderr.read().decode()
                    if stderr:
                        print(f"aplay error: {stderr}", flush=True)
                except:
                    pass
                
    except Exception as e:
        print(f"dmixer playback error: {e}")
    
    if not stream_started:
        print("Kunne ikke starte lydstrøm. Avslutter tale-funksjon uten å spille av.")
    
    if beak:  # Kun hvis servo er tilgjengelig
        beak.open_pct(0.05)  # Minst 5% åpen når ferdig
