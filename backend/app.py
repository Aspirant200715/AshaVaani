import os
import shutil
import uuid
import time
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from backend.config import (
    BASE_DIR,
    STATIC_DIR,
    SAMPLE_DIR,
    AUDIO_OUTPUT_DIR,
    STT_MODEL_DEFAULT,
    TTS_MODEL_DEFAULT
)
from backend.gnani_service import GnaniService
from backend.clinical_extractor import parse_clinical_record

app = FastAPI(
    title="AshaVaani API | Sovereign Voice AI Copilot",
    description="Sovereign Indic Voice Clinical Assistant powered by Gnani AI (Prisma v3.0 & Timbre v2.5)",
    version="1.0.0"
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gnani_service = GnaniService()

# Serve static audio files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/samples-media", StaticFiles(directory=str(SAMPLE_DIR)), name="samples_media")

class TriageRequest(BaseModel):
    transcript: str
    language_code: Optional[str] = "hi-IN"

class SynthesizeRequest(BaseModel):
    text: str
    voice: Optional[str] = "Devika"
    language: Optional[str] = "hi-IN"
    speed: Optional[float] = 1.0

class SampleProcessRequest(BaseModel):
    sample_id: str
    voice: Optional[str] = "Devika"

@app.get("/api/status")
def get_system_status():
    """Returns active model details, credentials status, and supported languages/voices."""
    return {
        "status": "online",
        "app_name": "AshaVaani (आशावाणी)",
        "gnani_api_key_configured": gnani_service.has_active_key(),
        "models": {
            "stt": STT_MODEL_DEFAULT,
            "tts": TTS_MODEL_DEFAULT
        },
        "supported_languages": gnani_service.get_supported_languages(),
        "supported_voices": gnani_service.get_supported_voices()
    }

@app.get("/api/samples")
def list_samples():
    """Returns preset sample audio files for zero-friction testing by judges."""
    return [
        {
            "id": "sample_1_noisy_pediatric_fever",
            "title": "Case 1: Noisy Pediatric Fever Consultation",
            "language": "Hinglish / Hindi (indic-auto)",
            "voice": "Devika",
            "audio_url": "/samples-media/sample_1_noisy_pediatric_fever.wav",
            "description": "Simulates 8kHz phone audio from a rural village with infant crying and Hinglish speech.",
            "target_awards": ["Real Deal", "Noise Canceller", "Mixed Vibes"]
        },
        {
            "id": "sample_2_bengali_antenatal_care",
            "title": "Case 2: Antenatal Pregnancy Care & Anemia",
            "language": "Bengali (বাংলা) (bn-IN)",
            "voice": "Mehuli",
            "audio_url": "/samples-media/sample_2_bengali_antenatal_care.wav",
            "description": "Rural pregnancy checkup; patient reporting dizziness, fatigue, and blood pressure concerns.",
            "target_awards": ["Real Deal", "Main Character"]
        },
        {
            "id": "sample_3_acute_dehydration_emergency",
            "title": "Case 3: Acute Diarrhea & Red Triage Alert",
            "language": "Hindi (हिंदी) (hi-IN)",
            "voice": "Devika",
            "audio_url": "/samples-media/sample_3_acute_dehydration_emergency.wav",
            "description": "Urgent infant dehydration case triggering high-priority hospital referral and ORS triage.",
            "target_awards": ["Real Deal", "Noise Canceller"]
        }
    ]

@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language_code: str = Form("indic-auto")
):
    """Transcribes an uploaded audio file using Gnani Prisma v3.0."""
    temp_filename = f"upload_{uuid.uuid4().hex}_{file.filename}"
    temp_path = AUDIO_OUTPUT_DIR / temp_filename
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        stt_result = gnani_service.transcribe(temp_path, language_code=language_code)
        return stt_result
    finally:
        # Keep uploaded file or clean up if needed
        pass

@app.post("/api/triage")
def triage_clinical_text(req: TriageRequest):
    """Extracts ABDM clinical entities, vitals, prescriptions, and triage level."""
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript text is required")
    
    clinical_data = parse_clinical_record(req.transcript, detected_language=req.language_code)
    return clinical_data

@app.post("/api/synthesize")
def synthesize_voice(req: SynthesizeRequest):
    """Synthesizes speech guidance via Gnani Timbre v2.5."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    
    tts_result = gnani_service.synthesize(
        text=req.text,
        voice=req.voice or "Devika",
        language=req.language or "hi-IN",
        speed=req.speed or 1.0
    )
    return tts_result

@app.post("/api/process-consultation")
async def process_full_consultation(
    file: UploadFile = File(...),
    language_code: str = Form("indic-auto"),
    voice: str = Form("Devika")
):
    """
    End-to-end pipeline: Audio -> Gnani Prisma v3.0 STT -> ABDM Clinical Scribing -> Gnani Timbre v2.5 TTS
    """
    ext = Path(file.filename or "audio.wav").suffix or ".wav"
    temp_filename = f"consult_{uuid.uuid4().hex}{ext}"
    temp_path = AUDIO_OUTPUT_DIR / temp_filename

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. Transcribe with Gnani Prisma v3.0
    stt_res = gnani_service.transcribe(temp_path, language_code=language_code)
    transcript = stt_res.get("transcript", "")
    detected_lang = stt_res.get("detected_language", "hi-IN")

    # 2. Extract clinical entities & triage
    clinical_res = parse_clinical_record(transcript, detected_language=detected_lang)

    # 3. Voice guidance synthesis via Gnani Timbre v2.5
    advice_text = clinical_res.get("spoken_advice", "")
    tts_res = gnani_service.synthesize(
        text=advice_text,
        voice=voice,
        language=detected_lang if detected_lang in ["hi-IN", "bn-IN", "ta-IN", "te-IN", "kn-IN"] else "hi-IN"
    )

    return {
        "stt": stt_res,
        "clinical_record": clinical_res,
        "tts": tts_res,
        "input_audio_url": f"/static/audio/{temp_filename}"
    }

@app.post("/api/process-sample")
def process_preset_sample(req: SampleProcessRequest):
    """Processes a preset sample file for judges and instant demonstration."""
    sample_file = SAMPLE_DIR / f"{req.sample_id}.wav"
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Sample not found")

    lang = "bn-IN" if "bengali" in req.sample_id else "hi-IN"
    voice = req.voice or ("Mehuli" if "bengali" in req.sample_id else "Devika")

    stt_res = gnani_service.transcribe(sample_file, language_code=lang)
    transcript = stt_res.get("transcript", "")
    detected_lang = stt_res.get("detected_language", lang)

    clinical_res = parse_clinical_record(transcript, detected_language=detected_lang)
    advice_text = clinical_res.get("spoken_advice", "")

    tts_res = gnani_service.synthesize(
        text=advice_text,
        voice=voice,
        language=detected_lang
    )

    return {
        "stt": stt_res,
        "clinical_record": clinical_res,
        "tts": tts_res,
        "input_audio_url": f"/samples-media/{req.sample_id}.wav"
    }

# Serve root index html if available
@app.get("/")
def serve_home():
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "AshaVaani API running. Visit /docs for Swagger UI or open the web dashboard."}
