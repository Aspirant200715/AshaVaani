import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GNANI_API_KEY = os.getenv("GNANI_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Models
STT_MODEL_DEFAULT = "prisma-v3.0"
STT_MODEL_FALLBACK = "gnani-prisma-v2.5"
TTS_MODEL_DEFAULT = "timbre-v2.5"

# Accuracy hints for rural healthcare domain
CLINICAL_KEYWORDS = [
    "Paracetamol", "ORS", "ORS ghol", "Bukhar", "Sardi", "Khasi", "Dast",
    "Hemoglobin", "ASHA", "Anganwadi", "Didi", "BP", "Sugar", "Tika",
    "Vaccine", "Garbhavastha", "Iron Folic Acid", "Zinc", "Vomiting",
    "Pet dard", "Chakkar", "Kamzori", "PHC", "CHC", "Sub-center", "ABHA"
]

CLINICAL_TOPIC = "Rural primary healthcare, maternal health, infant immunization, and fever consultations with ASHA worker"

SAMPLE_DIR = BASE_DIR / "samples"
STATIC_DIR = BASE_DIR / "static"
AUDIO_OUTPUT_DIR = STATIC_DIR / "audio"
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
