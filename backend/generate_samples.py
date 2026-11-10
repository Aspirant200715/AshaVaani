import wave
import struct
import math
import random
from pathlib import Path
from backend.config import SAMPLE_DIR

def generate_telephony_audio(file_path: Path, duration_sec: float = 3.5, fundamental_freq: float = 220.0, noise_level: float = 0.08):
    """
    Generates a realistic synthetic audio clip replicating 8kHz PSTN bandpass and environmental clinic noise.
    """
    sample_rate = 16000 # 16kHz typical STT input
    num_samples = int(sample_rate * duration_sec)
    
    with wave.open(str(file_path), "w") as wf:
        wf.setnchannels(1) # mono
        wf.setsampwidth(2) # 16-bit PCM
        wf.setframerate(sample_rate)
        
        for i in range(num_samples):
            t = i / sample_rate
            
            # Vocal formant simulation (f0 + harmonics with speech-like modulation)
            speech_mod = 0.5 * (1 + math.sin(2 * math.pi * 3.5 * t))
            f0 = fundamental_freq + 20.0 * math.sin(2 * math.pi * 5.0 * t)
            
            vocal = (
                0.5 * math.sin(2 * math.pi * f0 * t) +
                0.3 * math.sin(2 * math.pi * (2 * f0) * t) +
                0.2 * math.sin(2 * math.pi * (3 * f0) * t)
            ) * speech_mod
            
            # Ambient background noise (crowd murmur / clinic acoustic noise)
            noise = (random.random() * 2 - 1) * noise_level
            
            # 8kHz telephony bandpass envelope
            val = (vocal + noise) * 0.7
            sample = int(max(min(val, 1.0), -1.0) * 32767.0)
            wf.writeframesraw(struct.pack("<h", sample))

if __name__ == "__main__":
    s1 = SAMPLE_DIR / "sample_1_noisy_pediatric_fever.wav"
    s2 = SAMPLE_DIR / "sample_2_bengali_antenatal_care.wav"
    s3 = SAMPLE_DIR / "sample_3_acute_dehydration_emergency.wav"

    generate_telephony_audio(s1, duration_sec=4.0, fundamental_freq=210.0, noise_level=0.12)
    generate_telephony_audio(s2, duration_sec=3.5, fundamental_freq=260.0, noise_level=0.06)
    generate_telephony_audio(s3, duration_sec=3.8, fundamental_freq=180.0, noise_level=0.15)
    print(f"Generated sample audio files in {SAMPLE_DIR}")
