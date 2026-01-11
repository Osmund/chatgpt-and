#!/usr/bin/env python3
"""
Test script for analyzing beak movement amplitude
Generates speech and logs amplitude values to see behavior
"""

import os
import tempfile
import wave
import numpy as np
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment
from scipy.signal import resample
from dotenv import load_dotenv

load_dotenv()

def analyze_speech_amplitude(text, config_name, threshold, multiplier, ceiling, alpha, amp_window):
    """Generate speech and analyze amplitude distribution"""
    
    tts_key = os.getenv("AZURE_TTS_KEY")
    tts_region = os.getenv("AZURE_TTS_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, region=tts_region)
    
    # Same settings as main script
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
    )
    
    ssml = f'<speak version="1.0" xml:lang="nb-NO"><voice name="nb-NO-FinnNeural">{text}</voice></speak>'
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmpfile:
        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmpfile.name)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("TTS failed!")
            return
        
        # Load and pitch shift (same as main script)
        sound = AudioSegment.from_wav(tmpfile.name)
        octaves = 1.5
        new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
        shifted = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
        shifted = shifted.set_frame_rate(48000)
        
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
        else:
            dtype = np.uint8
        
        samples = np.frombuffer(audio, dtype=dtype)
        if n_channels > 1:
            samples = samples[::n_channels]
        samples = samples.astype(np.float32) / np.iinfo(dtype).max
        
        # Fade in/out
        fade_samples = int(framerate * 0.01)
        if len(samples) > fade_samples * 2:
            fade_in = np.linspace(0, 1, fade_samples)
            samples[:fade_samples] *= fade_in
            fade_out = np.linspace(1, 0, fade_samples)
            samples[-fade_samples:] *= fade_out
        
        # Calculate amplitude (use parameter)
        amplitudes = []
        for i in range(0, len(samples), amp_window):
            chunk = samples[i:i+amp_window]
            amp = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0
            amplitudes.extend([amp] * amp_window)
        amplitudes = amplitudes[:len(samples)]
        
        # Apply smoothing (same as main script)
        smoothed = []
        prev = 0
        for amp in amplitudes:
            smoothed_amp = alpha * amp + (1 - alpha) * prev
            smoothed.append(smoothed_amp)
            prev = smoothed_amp
        amplitudes = smoothed
        
        # Apply same transformations as main script
        
        processed = []
        for amp in amplitudes:
            if amp < threshold:
                beak_pos = 0.0
            else:
                adjusted = (amp - threshold) * multiplier
                clamped = ceiling * np.tanh(adjusted / ceiling)
                beak_pos = max(clamped, 0.0)
            processed.append(beak_pos)
        
        # Analyze the results
        amplitudes_array = np.array(amplitudes)
        processed_array = np.array(processed)
        
        print(f"\n{'='*60}")
        print(f"Config: {config_name}")
        print(f"Text: '{text}'")
        print(f"Parameters: threshold={threshold}, multiplier={multiplier}, ceiling={ceiling}, alpha={alpha}")
        print(f"{'='*60}")
        print(f"\nRAW AMPLITUDE STATS:")
        print(f"  Min:     {amplitudes_array.min():.6f}")
        print(f"  Max:     {amplitudes_array.max():.6f}")
        print(f"  Mean:    {amplitudes_array.mean():.6f}")
        print(f"  Median:  {np.median(amplitudes_array):.6f}")
        print(f"  Std:     {amplitudes_array.std():.6f}")
        
        print(f"\nPROCESSED BEAK POSITION STATS:")
        print(f"  Min:     {processed_array.min():.6f}")
        print(f"  Max:     {processed_array.max():.6f}")
        print(f"  Mean:    {processed_array.mean():.6f}")
        print(f"  Median:  {np.median(processed_array):.6f}")
        print(f"  Std:     {processed_array.std():.6f}")
        
        # Count how often beak is in different ranges
        below_threshold = np.sum(processed_array == 0.0)
        low_range = np.sum((processed_array > 0.0) & (processed_array <= 0.3))
        mid_range = np.sum((processed_array > 0.3) & (processed_array <= 0.6))
        high_range = np.sum((processed_array > 0.6) & (processed_array < 0.7))
        at_ceiling = np.sum(processed_array >= 0.69)  # Close to ceiling
        
        total = len(processed_array)
        print(f"\nBEAK POSITION DISTRIBUTION:")
        print(f"  Closed (0.0):        {below_threshold:6d} samples ({100*below_threshold/total:5.1f}%)")
        print(f"  Low (0.0-0.3):       {low_range:6d} samples ({100*low_range/total:5.1f}%)")
        print(f"  Mid (0.3-0.6):       {mid_range:6d} samples ({100*mid_range/total:5.1f}%)")
        print(f"  High (0.6-0.7):      {high_range:6d} samples ({100*high_range/total:5.1f}%)")
        print(f"  At ceiling (≥0.69):  {at_ceiling:6d} samples ({100*at_ceiling/total:5.1f}%) ⚠️")
        
        # Sample some specific points
        print(f"\nSAMPLE VALUES (time | raw_amp | beak_pos):")
        sample_points = [int(i * len(amplitudes) / 20) for i in range(20)]
        for i, idx in enumerate(sample_points):
            if idx < len(amplitudes):
                time_sec = idx / framerate
                print(f"  {time_sec:5.2f}s | {amplitudes[idx]:8.6f} | {processed[idx]:6.4f}")
        
        print(f"\n{'='*60}\n")
        
        # Warning if too much peaking
        if at_ceiling / total > 0.1:  # More than 10% at ceiling
            print("⚠️  WARNING: Beak is at ceiling more than 10% of the time!")
            print("    This may cause 'peaking' behavior and audio disturbances.")
            print(f"    Consider reducing multiplier (currently {multiplier}) or ceiling (currently {ceiling})")
        
        if below_threshold / total > 0.7:  # More than 70% closed
            print("⚠️  WARNING: Beak is closed more than 70% of the time!")
            print("    This may cause insufficient movement.")
            print(f"    Consider reducing threshold (currently {threshold}) or increasing multiplier")

if __name__ == "__main__":
    # Test with different window sizes for resolution
    configs = [
        ("Current (window=128)", 0.035, 16.0, 0.65, 0.7, 128),
        ("Higher resolution (window=64)", 0.035, 16.0, 0.65, 0.7, 64),
        ("Even higher (window=32)", 0.035, 16.0, 0.65, 0.7, 32),
    ]
    
    test_text = "Dette er en test av nebbet med endel forskjellig tale."
    
    print("\n" + "="*60)
    print("TESTING DIFFERENT WINDOW SIZES (RESOLUTION)")
    print("="*60)
    
    for config_name, threshold, multiplier, ceiling, alpha, window in configs:
        analyze_speech_amplitude(test_text, config_name, threshold, multiplier, ceiling, alpha, window)
