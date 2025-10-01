from pydub import AudioSegment
from scipy.signal import resample
import sounddevice as sd
import time
import random
from duck_beak import Beak, CLOSE_DEG, OPEN_DEG, TRIM_DEG, JITTER, BEAT_MS_MIN, BEAT_MS_MAX
GPIO_SERVO = 14  # PWM-pin til servo (GPIO14/pin 8)
import requests
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import pvporcupine
import pyaudio
import numpy as np

# --- Azure Speech to Text ---
import time as _time
def recognize_speech_from_mic(device_name=None):
    stt_key = os.getenv("AZURE_STT_KEY")
    stt_region = os.getenv("AZURE_STT_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=stt_key, region=stt_region)
    audio_config = None
    if device_name:
        audio_config = speechsdk.audio.AudioConfig(device_name=device_name)
    else:
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config, language="nb-NO")
    # Sett end silence timeout (default er 0.5s, vi setter til 0.8s for robusthet)
    prop = speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs
    speech_recognizer.properties.set_property(prop, "800")
    print("Snakk nå (trykk Ctrl+C for å avbryte)...")
    t0 = _time.time()
    result = speech_recognizer.recognize_once()
    t1 = _time.time()
    elapsed = t1 - t0
    print(f"Azure STT tid: {elapsed:.2f} sekunder")
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"Du sa: {result.text}")
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("Ingen tale gjenkjent.")
        return None
    else:
        print(f"Talegjenkjenning feilet: {result.reason}")
        return None

def chatgpt_query(messages, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": messages
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def wait_for_wake_word():
    access_key = os.getenv("PICOVOICE_ACCESS_KEY")
    wake_word_path = "Quack-quack.ppn"  # eller det faktiske filnavnet
    porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[wake_word_path])
    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )
    print("Si 'quack quack' for å vekke anda!")
    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = np.frombuffer(pcm, dtype=np.int16)
            result = porcupine.process(pcm)
            if result >= 0:
                print("Wake word oppdaget!")
                break
    finally:
        audio_stream.stop_stream()
        audio_stream.close()
        pa.terminate()
        porcupine.delete()

def speak(text, speech_config, beak):
    import tempfile
    import wave
    # Forenklet SSML, ingen linjeskift
    ssml = f'<speak version="1.0" xml:lang="nb-NO"><voice name="nb-NO-FinnNeural"><prosody rate="-40%">{text}</prosody></voice></speak>'
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmpfile:
        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmpfile.name)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            sound = AudioSegment.from_wav(tmpfile.name)
            octaves = 0.7  # Juster for mer/ mindre "quack"
            new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
            shifted = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
            shifted = shifted.set_frame_rate(sound.frame_rate)
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

            blocksize = int(framerate * 0.03)  # 30 ms
            def callback(outdata, frames, time_info, status):
                nonlocal idx
                chunk = samples[idx:idx+frames]
                if len(chunk) < frames:
                    outdata[:len(chunk),0] = chunk
                    outdata[len(chunk):,0] = 0
                else:
                    outdata[:,0] = chunk
                amp = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0
                beak.open_pct(min(max(amp * 2.5, 0.0), 1.0))
                idx += frames
            idx = 0
            with sd.OutputStream(samplerate=framerate, channels=1, dtype='float32', blocksize=blocksize, callback=callback):
                while idx < len(samples):
                    sd.sleep(int(1000 * blocksize / framerate))
            beak.open_pct(0.0)
        else:
            print("TTS-feil:", result.reason)
            if hasattr(result, "cancellation_details"):
                print("Detaljer:", result.cancellation_details.reason, result.cancellation_details.error_details)

def main():
    beak = Beak(GPIO_SERVO, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    tts_key = os.getenv("AZURE_TTS_KEY")
    tts_region = os.getenv("AZURE_TTS_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
    speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"
    device_name = None

    print("Anda venter på wake word... (si 'quack quack')")
    while True:
        wait_for_wake_word()
        # Anda svarer med velkomstmelding
        speak("Hei på du, hva kan jeg hjelpe deg med?", speech_config, beak)
        messages = []
        while True:
            prompt = recognize_speech_from_mic(device_name)
            if not prompt:
                speak("Beklager, jeg hørte ikke hva du sa. Prøv igjen.", speech_config, beak)
                continue
            messages.append({"role": "user", "content": prompt})
            try:
                reply = chatgpt_query(messages, api_key)
                print("ChatGPT svar:", reply, flush=True)
                speak(reply, speech_config, beak)
                messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                print("Feil:", e)
                speak("Beklager, det oppstod en feil.", speech_config, beak)
            # Etter svar, spør om brukeren vil fortsette eller vente på nytt wake word
            speak("Vil du spørre om noe mer? Si ja for å fortsette, eller nei for å avslutte samtalen.", speech_config, beak)
            cont = recognize_speech_from_mic(device_name)
            if cont and "ja" in cont.strip().lower():
                continue  # Fortsett samtalen
            else:
                speak("Da venter jeg til du sier navnet mitt igjen.", speech_config, beak)
                break
if __name__ == "__main__":
    main()