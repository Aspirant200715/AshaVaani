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
from backend.campaigns import (
    get_campaigns_list,
    get_campaign_by_id,
    log_campaign_call,
    get_recent_campaign_calls
)
import urllib.parse

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

# Dynamic audio serving route (supports serverless /tmp/audio and local static/audio)
@app.get("/static/audio/{filename}")
def serve_static_audio(filename: str):
    generated_file = AUDIO_OUTPUT_DIR / filename
    if generated_file.exists():
        return FileResponse(generated_file)
    static_file = STATIC_DIR / "audio" / filename
    if static_file.exists():
        return FileResponse(static_file)
    raise HTTPException(status_code=404, detail="Audio file not found")

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

class CampaignTriggerRequest(BaseModel):
    campaign_id: str
    recipient_name: Optional[str] = "सुनीता देवी"
    recipient_phone: Optional[str] = "+91 98765 43210"

class VoiceSlipRequest(BaseModel):
    text: str
    language: Optional[str] = "hi-IN"
    voice: Optional[str] = "Devika"

class ClarifyQuestionRequest(BaseModel):
    question_text: str
    voice: Optional[str] = "Devika"
    language: Optional[str] = "hi-IN"

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

@app.get("/api/campaigns")
def list_outbound_campaigns():
    """Returns public health outbound voice campaigns (inspired by autonomous agent workflows)."""
    return get_campaigns_list()

@app.get("/api/campaigns/calls")
def list_recent_campaign_calls(limit: int = Query(15, ge=1, le=50)):
    """Returns recent autonomous outbound call logs."""
    return get_recent_campaign_calls(limit=limit)

@app.post("/api/campaigns/trigger")
def trigger_outbound_campaign_call(req: CampaignTriggerRequest):
    """
    Executes a simulated or live outbound PSTN telephonic voice agent call.
    Synthesizes conversational prompts with Gnani Timbre v2.5 and logs outcome to SQLite.
    """
    camp = get_campaign_by_id(req.campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    lang_code = "bn-IN" if "Bengali" in camp["language"] else "hi-IN"
    voice_name = camp.get("voice", "Devika")

    # Synthesize the opening agent prompt via Gnani Timbre v2.5
    agent_tts = gnani_service.synthesize(
        text=camp["agent_prompt"],
        voice=voice_name,
        language=lang_code
    )

    # Log to SQLite
    clinical_summary = camp["clinical_intent"].get("abdm_registry_action", "Adherence Logged")
    call_log = log_campaign_call(
        campaign_id=camp["id"],
        recipient_name=req.recipient_name or "सुनीता देवी",
        recipient_phone=req.recipient_phone or "+91 98765 43210",
        status="Completed",
        agent_speech=camp["agent_prompt"],
        patient_reply=camp["simulated_reply"],
        clinical_outcome=clinical_summary,
        audio_url=agent_tts.get("audio_url", ""),
        duration_sec=38
    )

    return {
        "success": True,
        "campaign": camp,
        "call_log": call_log,
        "agent_audio_url": agent_tts.get("audio_url", ""),
        "tts_latency_ms": agent_tts.get("latency_ms", 120),
        "dialog": {
            "agent_prompt": camp["agent_prompt"],
            "patient_reply": camp["simulated_reply"],
            "agent_acknowledgement": camp["agent_acknowledgement"],
            "clinical_intent": camp["clinical_intent"]
        }
    }

@app.post("/api/generate-voice-slip")
def generate_patient_voice_slip(req: VoiceSlipRequest):
    """
    Generates an audio prescription slip via Gnani Timbre v2.5 for illiterate / rural patients.
    Returns direct audio player URL and 1-click WhatsApp web dispatch link.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required for voice slip")

    tts_res = gnani_service.synthesize(
        text=req.text,
        voice=req.voice or "Devika",
        language=req.language or "hi-IN"
    )

    encoded_text = urllib.parse.quote(f"🩺 *AshaVaani (आशावाणी) Voice Slip*\n\n{req.text}\n\n🎧 ऑडियो सुनें: {tts_res.get('audio_url', '')}")
    whatsapp_url = f"https://api.whatsapp.com/send?text={encoded_text}"

    return {
        "success": True,
        "audio_url": tts_res.get("audio_url", ""),
        "transcript": req.text,
        "voice": req.voice or "Devika",
        "latency_ms": tts_res.get("latency_ms", 140),
        "whatsapp_url": whatsapp_url
    }

@app.post("/api/clarify-question")
def clarify_clinical_blindspot(req: ClarifyQuestionRequest):
    """
    Synthesizes clinical blindspot question on demand via Gnani Timbre v2.5 for ASHA worker.
    """
    if not req.question_text.strip():
        raise HTTPException(status_code=400, detail="Question text required")

    tts_res = gnani_service.synthesize(
        text=req.question_text,
        voice=req.voice or "Devika",
        language=req.language or "hi-IN"
    )
    return {
        "success": True,
        "audio_url": tts_res.get("audio_url", ""),
        "latency_ms": tts_res.get("latency_ms", 110)
    }

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
