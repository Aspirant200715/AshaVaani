import time
import uuid
import json
import logging
from typing import Dict, Any, List, Optional
from backend.db import get_connection

logger = logging.getLogger("ashavaani.campaigns")

DEFAULT_CAMPAIGNS = [
    {
        "id": "camp_mission_indradhanush",
        "name": "Mission Indradhanush: Measles Immunization Due",
        "hindi_title": "मिशन इंद्रधनुष: 9-माह खसरा टीकाकरण अनुस्मारक",
        "trigger": "Scheduled Campaign &bull; 24h Pre-Session",
        "target_cohort": "Mothers of infants (9-12 months)",
        "language": "Hindi (hi-IN)",
        "voice": "Devika",
        "integrations": ["U-WIN Portal", "ABDM RCH", "SMS Gateway"],
        "status": "Active",
        "total_queued": 142,
        "completed": 128,
        "success_rate": "90.1%",
        "agent_prompt": "नमस्ते सुनीता जी, मैं आशावाणी डिजिटल स्वास्थ्य सहायक बोल रही हूँ। कल रामपुर प्राथमिक उप-केंद्र पर आरव के 9 महीने के खसरा (Measles) एवं विटामिन-ए के टीके का दिन है। क्या आप सुबह 10 बजे केंद्र पर आ सकेंगी?",
        "simulated_reply": "हाँ दीदी, हम कल सुबह 10 बजे आरव को लेकर उप-केंद्र पहुंच जाएंगे। टीका कार्ड भी साथ लाएंगे।",
        "agent_acknowledgement": "बहुत बढ़िया सुनीता जी। आरव का एमसीपी कार्ड साथ जरूर लाइएगा। कल सुबह 10 बजे मिलते हैं। धन्यवाद।",
        "clinical_intent": {
            "vaccine_type": "Measles-Rubella (MR-1) + Vitamin A",
            "attendance_confirmed": True,
            "danger_signs_reported": False,
            "abdm_registry_action": "U-WIN Slot Booked &bull; ASHA Home-Visit Cleared"
        }
    },
    {
        "id": "camp_anc_high_risk",
        "name": "Pradhan Mantri Matru Vandana: High-Risk Pregnancy Monitor",
        "hindi_title": "मातृ वंदना: उच्च जोखिम गर्भावस्था टेली-जांच",
        "trigger": "Weekly Scheduled &bull; 28-34 Weeks ANC",
        "target_cohort": "High-risk pregnant mothers (Hb < 9g/dL)",
        "language": "Bengali / Hindi",
        "voice": "Mehuli",
        "integrations": ["Poshan Tracker", "ABDM ABHA", "108 Emergency"],
        "status": "Active",
        "total_queued": 86,
        "completed": 79,
        "success_rate": "91.8%",
        "agent_prompt": "নমস্কার রুমা দিদি, আশাবাণী থেকে বলছি। আপনি কি আজকের লাল আয়রন ও ফলিক অ্যাসিড ট্যাবলেট খেয়েছেন? আপনার কি মাথা ঘোরা বা পায়ে কোনো ফোলাভাব আছে?",
        "simulated_reply": "নমস্কার দিদি, আয়রন ট্যাবলেট খেয়েছি। কিন্তু আজ সকাল থেকে একটু মাথা ঘুরছে আর শরীর দুর্বল লাগছে।",
        "agent_acknowledgement": "রুমা দিদি, আপনি এখনই পর্যাপ্ত জল খেয়ে বিশ্রাম নিন। আমি এএনএম দিদিকে এখনই আপনার বাড়ি ভিজিটের জন্য সতর্কবার্তা পাঠাচ্ছি।",
        "clinical_intent": {
            "vaccine_type": "IFA & Calcium Adherence",
            "attendance_confirmed": True,
            "danger_signs_reported": True,
            "danger_reason": "Gestational Dizziness / Mild Anemia flare-up",
            "abdm_registry_action": "Yellow Flag &bull; Immediate ANM Home Visit Dispatched"
        }
    },
    {
        "id": "camp_tb_dots_adherence",
        "name": "Ni-kshay TB Elimination: Daily DOTS Medication Adherence",
        "hindi_title": "निक्षय टीबी उन्मूलन: दैनिक डॉट्स दवा पुष्टि",
        "trigger": "Daily 09:00 AM Adherence Check",
        "target_cohort": "Active pulmonary TB patients (Intensive Phase)",
        "language": "Hindi (hi-IN)",
        "voice": "Devika",
        "integrations": ["Ni-kshay Portal", "DBT Direct Benefit Transfer"],
        "status": "Active",
        "total_queued": 64,
        "completed": 61,
        "success_rate": "95.3%",
        "agent_prompt": "नमस्ते राम सिंह जी, आशावाणी टीबी केयर से कॉल है। क्या आपने आज सुबह नाश्ते के बाद अपनी चारों निर्धारित दवाइयां खा ली हैं?",
        "simulated_reply": "हाँ आशा दीदी, सुबह नाश्ता करके 8 बजे चारों गोलियां खा ली थीं। कोई उल्टी या परेशानी नहीं हुई।",
        "agent_acknowledgement": "बहुत अच्छा राम सिंह जी! आपकी नियमित खुराक से आप जल्द स्वस्थ होंगे। आज की खुराक निक्षय पोर्टल पर दर्ज कर दी गई है।",
        "clinical_intent": {
            "vaccine_type": "4-FDC Anti-Tubercular Therapy",
            "attendance_confirmed": True,
            "danger_signs_reported": False,
            "abdm_registry_action": "Ni-kshay Adherence Logged (Day 38/180) &bull; Rs. 500 DBT Credit Triggered"
        }
    },
    {
        "id": "camp_monsoon_diarrhea_alert",
        "name": "IDSP Early Warning: Monsoon Diarrhea & Dengue Surveillance",
        "hindi_title": "महामारी निगरानी: मानसून बुखार एवं डायरिया पूर्व चेतावनी",
        "trigger": "Outbreak Trigger &bull; Cluster Alert in Gram Panchayat",
        "target_cohort": "Households in Rampur & Shivpur Wards",
        "language": "Hindi (hi-IN)",
        "voice": "Devika",
        "integrations": ["IDSP Portal", "PHC Medical Officer", "Water Board"],
        "status": "Completed",
        "total_queued": 210,
        "completed": 198,
        "success_rate": "94.2%",
        "agent_prompt": "नमस्ते, स्वास्थ्य विभाग की ओर से जरूरी सूचना। क्या आपके घर में किसी को पिछले 48 घंटों से तेज़ बुखार, उल्टी या पतले दस्त की शिकायत है?",
        "simulated_reply": "हाँ, मेरे छोटे बेटे को कल शाम से 3-4 बार दस्त हुए हैं लेकिन बुखार नहीं है।",
        "agent_acknowledgement": "कृपया तुरंत उबला हुआ पानी और ओआरएस का घोल देना शुरू करें। आशा दीदी आज दोपहर 1 बजे आपके घर ओआरएस पैकेट लेकर पहुँच रही हैं।",
        "clinical_intent": {
            "vaccine_type": "ORS & Water Safety Protocol",
            "attendance_confirmed": True,
            "danger_signs_reported": True,
            "danger_reason": "Mild Pediatric Diarrhea detected during surveillance sweep",
            "abdm_registry_action": "ORS Home Kit Dispatched &bull; Water Sample Test Queued"
        }
    }
]

def init_campaigns_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaign_calls (
        call_id TEXT PRIMARY KEY,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        campaign_id TEXT,
        campaign_name TEXT,
        recipient_name TEXT,
        recipient_phone TEXT,
        language TEXT,
        status TEXT,
        agent_speech TEXT,
        patient_reply TEXT,
        clinical_outcome TEXT,
        audio_url TEXT,
        duration_sec INTEGER
    )
    """)
    conn.commit()
    conn.close()

def get_campaigns_list() -> List[Dict[str, Any]]:
    init_campaigns_table()
    return DEFAULT_CAMPAIGNS

def get_campaign_by_id(camp_id: str) -> Optional[Dict[str, Any]]:
    for c in DEFAULT_CAMPAIGNS:
        if c["id"] == camp_id:
            return c
    return None

def log_campaign_call(
    campaign_id: str,
    recipient_name: str,
    recipient_phone: str,
    status: str,
    agent_speech: str,
    patient_reply: str,
    clinical_outcome: str,
    audio_url: str = "",
    duration_sec: int = 42
) -> Dict[str, Any]:
    init_campaigns_table()
    camp = get_campaign_by_id(campaign_id)
    camp_name = camp["name"] if camp else "Public Health Campaign"

    call_id = f"call_{uuid.uuid4().hex[:10]}"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO campaign_calls (
        call_id, campaign_id, campaign_name, recipient_name,
        recipient_phone, language, status, agent_speech,
        patient_reply, clinical_outcome, audio_url, duration_sec
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        call_id, campaign_id, camp_name, recipient_name,
        recipient_phone, camp["language"] if camp else "Hindi",
        status, agent_speech, patient_reply, clinical_outcome,
        audio_url, duration_sec
    ))
    conn.commit()
    conn.close()

    return {
        "call_id": call_id,
        "campaign_id": campaign_id,
        "campaign_name": camp_name,
        "recipient_name": recipient_name,
        "recipient_phone": recipient_phone,
        "status": status,
        "duration_sec": duration_sec,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def get_recent_campaign_calls(limit: int = 15) -> List[Dict[str, Any]]:
    init_campaigns_table()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM campaign_calls ORDER BY timestamp DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results

init_campaigns_table()
