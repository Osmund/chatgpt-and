#!/usr/bin/env python3
"""
Send en melding til anda for å si høyt
"""
import sys
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from duck_beak import Beak
from rgb_duck import set_red, off
import sounddevice as sd
from pydub import AudioSegment
import tempfile
import numpy as np
import time

# Last miljøvariabler
load_dotenv()

def find_hifiberry_output():
    """Finn sounddevice index for HifiBerry DAC"""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'hifiberry' in device['name'].lower() and device['max_output_channels'] > 0:
            return i
    return None

def speak(text):
    """Si en melding med andstemme"""
    set_red()
    
    # Init Azure TTS
    tts_key = os.getenv("AZURE_TTS_KEY")
    tts_region = os.getenv("AZURE_TTS_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
    speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
    )
    
    # Init beak
    beak = Beak(gpio_pin=12)
    beak.open_pct(0.05)
    
    # Syntetiser til fil
    ssml = f'<speak version="1.0" xml:lang="nb-NO"><voice name="nb-NO-FinnNeural">{text}</voice></speak>'
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmpfile:
        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmpfile.name)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # Pitch-shift
            sound = AudioSegment.from_wav(tmpfile.name)
            octaves = 1.5
            new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
            shifted = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
            shifted = shifted.set_frame_rate(48000)
            
            # Spill av med nebbbevegelse
            audio = shifted.raw_data
            framerate = 48000
            n_channels = shifted.channels
            sampwidth = shifted.sample_width
            
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
            
            # Finn HifiBerry
            output_device = find_hifiberry_output()
            
            blocksize = int(framerate * 0.064)
            idx = 0
            
            def callback(outdata, frames, time_info, status):
                nonlocal idx
                chunk = samples[idx:idx+frames]
                
                if len(chunk) > 0:
                    amp = np.sqrt(np.mean(chunk**2))
                    beak.open_pct(min(max(amp * 3.5, 0.05), 1.0))
                
                num_channels = outdata.shape[1] if len(outdata.shape) > 1 else 1
                if len(chunk) < frames:
                    for ch in range(num_channels):
                        outdata[:len(chunk),ch] = chunk
                        outdata[len(chunk):,ch] = 0
                else:
                    for ch in range(num_channels):
                        outdata[:,ch] = chunk
                idx += frames
            
            with sd.OutputStream(samplerate=framerate, device=output_device, channels=2, 
                               dtype='float32', blocksize=blocksize, callback=callback):
                while idx < len(samples):
                    sd.sleep(int(1000 * blocksize / framerate))
            
            beak.open_pct(0.05)
        else:
            print(f"TTS feil: {result.reason}")
    
    off()
    beak.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Bruk: duck_speak.py 'tekst å si'")
        sys.exit(1)
    
    text = ' '.join(sys.argv[1:])
    speak(text)
