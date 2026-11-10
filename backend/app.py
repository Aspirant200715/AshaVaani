import os
import shutil
import uuid
import time
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
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
from backend.audio_utils import convert_to_wav, inject_telephony_noise
from backend.abdm_fhir import generate_abdm_fhir_bundle
from backend.db import save_consultation, get_consultations, get_analytics

app = FastAPI(
    title="AshaVaani API | Sovereign Voice AI Copilot",
    description="Sovereign Indic Voice Clinical Assistant powered by Gnani AI (Prisma v3.0 & Timbre v2.5)",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gnani_service = GnaniService()

# Mount static asset directories
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

class NoiseSimulationRequest(BaseModel):
    audio_url: str

class FHIRExportRequest(BaseModel):
    record_id: str
    clinical_data: dict
    transcript: str

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
    raw_filename = f"raw_{uuid.uuid4().hex}_{file.filename}"
    raw_path = AUDIO_OUTPUT_DIR / raw_filename
    
    with open(raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Normalize to 16kHz mono WAV for guaranteed STT compatibility
    norm_path = AUDIO_OUTPUT_DIR / f"norm_{uuid.uuid4().hex}.wav"
    if not convert_to_wav(raw_path, norm_path):
        norm_path = raw_path

    stt_result = gnani_service.transcribe(norm_path, language_code=language_code)
    return stt_result

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
    End-to-end pipeline: Audio -> Gnani Prisma v3.0 STT -> ABDM Clinical Scribing -> Gnani Timbre v2.5 TTS -> DB Persistence
    """
    record_id = uuid.uuid4().hex[:12]
    raw_filename = f"consult_{record_id}_{file.filename}"
    raw_path = AUDIO_OUTPUT_DIR / raw_filename

    with open(raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. Normalize audio format
    norm_filename = f"consult_norm_{record_id}.wav"
    norm_path = AUDIO_OUTPUT_DIR / norm_filename
    if not convert_to_wav(raw_path, norm_path):
        norm_path = raw_path
        norm_filename = raw_filename

    # 2. Transcribe with Gnani Prisma v3.0
    stt_res = gnani_service.transcribe(norm_path, language_code=language_code)
    transcript = stt_res.get("transcript", "")
    detected_lang = stt_res.get("detected_language", "hi-IN")

    # 3. Extract clinical entities & triage
    clinical_res = parse_clinical_record(transcript, detected_language=detected_lang)

    # 4. Voice guidance synthesis via Gnani Timbre v2.5
    advice_text = clinical_res.get("spoken_advice", "")
    tts_res = gnani_service.synthesize(
        text=advice_text,
        voice=voice,
        language=detected_lang if detected_lang in ["hi-IN", "bn-IN", "ta-IN", "te-IN", "kn-IN"] else "hi-IN"
    )

    audio_web_url = f"/static/audio/{norm_filename}"

    # 5. Save to local SQLite database
    save_consultation(record_id, clinical_res, stt_res, tts_res, audio_web_url)

    # 6. Generate ABDM FHIR bundle
    fhir_bundle = generate_abdm_fhir_bundle(record_id, clinical_res, transcript)

    return {
        "record_id": record_id,
        "stt": stt_res,
        "clinical_record": clinical_res,
        "tts": tts_res,
        "fhir_bundle": fhir_bundle,
        "input_audio_url": audio_web_url
    }

@app.post("/api/process-sample")
def process_preset_sample(req: SampleProcessRequest):
    """Processes a preset sample file for judges and instant demonstration."""
    sample_file = SAMPLE_DIR / f"{req.sample_id}.wav"
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Sample not found")

    record_id = uuid.uuid4().hex[:12]
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

    audio_web_url = f"/samples-media/{req.sample_id}.wav"
    save_consultation(record_id, clinical_res, stt_res, tts_res, audio_web_url)
    fhir_bundle = generate_abdm_fhir_bundle(record_id, clinical_res, transcript)

    return {
        "record_id": record_id,
        "stt": stt_res,
        "clinical_record": clinical_res,
        "tts": tts_res,
        "fhir_bundle": fhir_bundle,
        "input_audio_url": audio_web_url
    }

@app.post("/api/simulate-telephony-noise")
def simulate_noise_route(req: NoiseSimulationRequest):
    """
    Applies PSTN 8kHz telephone bandpass filter to demonstrate Gnani's Noise Canceller capability.
    """
    clean_path = None
    if req.audio_url.startswith("/static/audio/"):
        clean_path = AUDIO_OUTPUT_DIR / Path(req.audio_url).name
    elif req.audio_url.startswith("/samples-media/"):
        clean_path = SAMPLE_DIR / Path(req.audio_url).name
    
    if not clean_path or not clean_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    noisy_filename = f"telephony_{uuid.uuid4().hex[:8]}.wav"
    noisy_path = AUDIO_OUTPUT_DIR / noisy_filename

    success = inject_telephony_noise(clean_path, noisy_path)
    if not success:
        raise HTTPException(status_code=500, detail="Noise injection failed")

    return {
        "success": True,
        "noisy_audio_url": f"/static/audio/{noisy_filename}",
        "description": "8kHz PSTN Telephonic bandpass filter (300Hz-3400Hz) applied"
    }

@app.post("/api/export-fhir")
def export_fhir(req: FHIRExportRequest):
    """Exports ABDM FHIR R4 Document Bundle JSON for Ayushman Bharat integration."""
    return generate_abdm_fhir_bundle(req.record_id, req.clinical_data, req.transcript)

@app.get("/api/consultations")
def list_consultations(
    limit: int = Query(20, ge=1, le=100),
    triage: Optional[str] = Query(None)
):
    """Returns recent consultation history stored in the local SQLite database."""
    return get_consultations(limit=limit, triage_filter=triage)

@app.get("/api/analytics")
def get_analytics_metrics():
    """Returns clinical triage metrics, total consultations, and time saved."""
    return get_analytics()

@app.get("/studio")
@app.get("/app")
def serve_studio():
    studio_file = BASE_DIR / "static" / "studio.html"
    if studio_file.exists():
        return FileResponse(studio_file)
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/")
def serve_home():
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "AshaVaani API running. Visit /docs for Swagger UI."}
