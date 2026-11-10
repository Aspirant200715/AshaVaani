import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_list_campaigns():
    response = client.get("/api/campaigns")
    assert response.status_code == 200
    campaigns = response.json()
    assert len(campaigns) >= 4
    camp_ids = [c["id"] for c in campaigns]
    assert "camp_mission_indradhanush" in camp_ids
    assert "camp_anc_high_risk" in camp_ids
    assert "camp_tb_dots_adherence" in camp_ids

def test_trigger_campaign_call():
    payload = {
        "campaign_id": "camp_mission_indradhanush",
        "recipient_name": "सुनीता देवी",
        "recipient_phone": "+91 98765 43210"
    }
    response = client.post("/api/campaigns/trigger", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "call_log" in data
    assert "dialog" in data
    assert data["dialog"]["clinical_intent"]["attendance_confirmed"] is True

def test_campaign_calls_history():
    response = client.get("/api/campaigns/calls")
    assert response.status_code == 200
    calls = response.json()
    assert isinstance(calls, list)
    assert len(calls) >= 1

def test_generate_voice_slip():
    payload = {
        "text": "नमस्ते दीदी! आशावाणी की वॉयस पर्ची: बच्चे को पैरासिटामोल 2.5ml दिन में दो बार दें।",
        "voice": "Devika",
        "language": "hi-IN"
    }
    response = client.post("/api/generate-voice-slip", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "audio_url" in data
    assert "whatsapp_url" in data
    assert "whatsapp.com" in data["whatsapp_url"]

def test_clarify_question():
    payload = {
        "question_text": "क्या बच्चे को झटके या दौरे तो नहीं आए हैं?",
        "voice": "Devika",
        "language": "hi-IN"
    }
    response = client.post("/api/clarify-question", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "audio_url" in data
