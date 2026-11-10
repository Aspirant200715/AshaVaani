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

def test_process_sample_and_persistence():
    payload = {
        "sample_id": "sample_1_noisy_pediatric_fever",
        "voice": "Devika"
    }
    response = client.post("/api/process-sample", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "record_id" in data
    assert "fhir_bundle" in data
    assert data["fhir_bundle"]["resourceType"] == "Bundle"
    assert len(data["fhir_bundle"]["entry"]) >= 3

    # Check consultation list endpoint
    hist_resp = client.get("/api/consultations")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert len(hist) > 0

    # Check analytics endpoint
    analytics_resp = client.get("/api/analytics")
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    assert analytics["total_consultations"] >= 1
    assert "hours_saved" in analytics

def test_noise_simulation():
    # Use preset sample
    sample_url = "/samples-media/sample_1_noisy_pediatric_fever.wav"
    resp = client.post("/api/simulate-telephony-noise", json={"audio_url": sample_url})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "noisy_audio_url" in data
