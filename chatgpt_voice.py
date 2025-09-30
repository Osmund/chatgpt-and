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

def chatgpt_query(messages, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4-turbo",
        "messages": messages
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def main():
    # Sett opp andenebb
    beak = Beak(GPIO_SERVO, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
    load_dotenv()  # Leser .env-filen automatisk
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = input("Skriv inn din OpenAI API-nøkkel: ")
    print("Skriv 'exit' eller 'quit' for å avslutte.")

    # Sett opp Azure Speech TTS
    azure_key = os.getenv("AZURE_SPEECH_KEY")
    azure_region = os.getenv("AZURE_SPEECH_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
    speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"  # Norsk, naturlig kvinnestemme
    # Bruk filbasert output for å sikre lyd på Raspberry Pifort
    import tempfile

    messages = []
    while True:
        prompt = input("Skriv inn din melding til ChatGPT: ")
        if prompt.lower() in ["exit", "quit"]:
            print("Avslutter...")
            break
        messages.append({"role": "user", "content": prompt})
        try:
            reply = chatgpt_query(messages, api_key)
            # Skriv ut svaret først, så spill av lyd, så gå videre
            print("ChatGPT svar:", reply, flush=True)
            import wave
            import numpy as np
            # Bruk SSML for å sette talehastighet
            ssml = f'''<speak version=\"1.0\" xml:lang=\"nb-NO\">\n  <voice name=\"nb-NO-FinnNeural\">\n    <prosody rate=\"-40%\">{reply}</prosody>\n  </voice>\n</speak>'''
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmpfile:
                audio_config = speechsdk.audio.AudioOutputConfig(filename=tmpfile.name)
                speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
                result = speech_synthesizer.speak_ssml_async(ssml).get()
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    # Donald Duck-effekt: pitch-shift oppover
                    duckfile = tmpfile.name + '_duck.wav'
                    sound = AudioSegment.from_wav(tmpfile.name)
                    octaves = 0.7  # Juster for mer/ mindre "quack"
                    new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
                    # Endre pitch
                    shifted = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
                    shifted = shifted.set_frame_rate(sound.frame_rate)
                    shifted.export(duckfile, format='wav')

                    with wave.open(duckfile, 'rb') as wf:
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
            messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            print("Feil:", e)

if __name__ == "__main__":
    main()