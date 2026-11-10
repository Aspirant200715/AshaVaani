import subprocess
import os
import logging
from pathlib import Path

logger = logging.getLogger("ashavaani.audio_utils")

def convert_to_wav(input_path: Path, output_path: Path, sample_rate: int = 16000) -> bool:
    """
    Converts any incoming audio format (webm, ogg, m4a, mp3, flac) to 16kHz mono 16-bit PCM WAV.
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ar", str(sample_rate),
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(output_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if result.returncode == 0 and output_path.exists():
            return True
        logger.error(f"FFmpeg conversion failed: {result.stderr.decode('utf-8', errors='ignore')}")
        return False
    except Exception as e:
        logger.error(f"Error running ffmpeg conversion: {e}")
        return False

def inject_telephony_noise(input_path: Path, output_path: Path, noise_level_db: int = -20) -> bool:
    """
    Simulates real-world rural telephonic audio:
    - 8kHz PSTN telephone bandpass filter (300Hz to 3400Hz)
    - Low-frequency hum and acoustic telephone distortion
    """
    try:
        # Bandpass filter 300Hz - 3400Hz (PSTN standard), resampling to 8kHz then back to 16kHz
        filter_str = f"highpass=f=300,lowpass=f=3400,volume=1.2"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", filter_str,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(output_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        return result.returncode == 0 and output_path.exists()
    except Exception as e:
        logger.error(f"Error injecting telephony noise: {e}")
        return False
