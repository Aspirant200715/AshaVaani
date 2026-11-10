import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "models" in data
    assert data["models"]["stt"] == "prisma-v3.0"
    assert data["models"]["tts"] == "timbre-v2.5"

def test_list_samples():
    response = client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) >= 3
    assert any("pediatric" in s["id"] for s in samples)

def test_triage_clinical_text():
    payload = {
        "transcript": "नमस्ते दीदी, बच्चे को दो दिन से बहुत तेज़ बुखार और उल्टी है।",
        "language_code": "hi-IN"
    }
    response = client.post("/api/triage", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["triage_level"] in ["Green", "Yellow", "Red"]
    assert len(data["chief_complaints"]) > 0
    assert len(data["prescriptions"]) > 0
    assert "spoken_advice" in data

def test_triage_red_flag_emergency():
    payload = {
        "transcript": "दीदी तुरंत मदद चाहिए, बच्चे को सुबह से दस बार पतले दस्त हो चुके हैं और आँखें धंस गई हैं।",
        "language_code": "hi-IN"
    }
    response = client.post("/api/triage", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["triage_level"] == "Red"
    assert "आपातकालीन" in data["triage_reason"] or "hospital" in data["triage_reason"].lower() or "एम्बुलेंस" in data["triage_reason"]

def test_synthesize_voice():
    payload = {
        "text": "नमस्ते दीदी, मरीज को ओआरएस का घोल दें।",
        "voice": "Devika",
        "language": "hi-IN"
    }
    response = client.post("/api/synthesize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "audio_url" in data

def test_process_sample():
    payload = {
        "sample_id": "sample_1_noisy_pediatric_fever",
        "voice": "Devika"
    }
    response = client.post("/api/process-sample", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "stt" in data
    assert "clinical_record" in data
    assert "tts" in data
    assert data["stt"]["success"] is True
