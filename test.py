import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv

load_dotenv()
speech_config = speechsdk.SpeechConfig(
    subscription=os.getenv("AZURE_SPEECH_KEY"),
    region=os.getenv("AZURE_SPEECH_REGION")
)
speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"
audio_config = speechsdk.audio.AudioOutputConfig(filename="azure_test.wav")
synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
result = synthesizer.speak_text_async("Dette er en test av norsk Azure tale.").get()

if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("TTS-feil:", result.reason)
    if hasattr(result, "cancellation_details"):
        print("Detaljer:", result.cancellation_details.reason, result.cancellation_details.error_details)
else:
    print("Filen ble generert OK.")