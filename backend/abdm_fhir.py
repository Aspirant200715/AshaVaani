import uuid
from datetime import datetime, timezone
from typing import Dict, Any

def generate_abdm_fhir_bundle(record_id: str, clinical_data: Dict[str, Any], transcript: str) -> Dict[str, Any]:
    """
    Generates an authentic Ayushman Bharat Digital Mission (ABDM) FHIR R4 Document Bundle.
    Specification: ABDM Health Facility / Teleconsultation Record Profile.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    bundle_id = f"abdm-bundle-{record_id}"
    patient_id = f"pat-{uuid.uuid4().hex[:8]}"
    practitioner_id = f"asha-worker-did1042"
    encounter_id = f"enc-{record_id}"

    # Vitals Observations
    observations = []
    vitals = clinical_data.get("vitals_estimate", {})
    if "temperature" in vitals:
        observations.append({
            "resourceType": "Observation",
            "id": f"obs-temp-{record_id}",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "8310-5",
                    "display": "Body temperature"
                }]
            },
            "valueString": vitals["temperature"]
        })
    if "pulse" in vitals:
        observations.append({
            "resourceType": "Observation",
            "id": f"obs-pulse-{record_id}",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "8867-4",
                    "display": "Heart rate"
                }]
            },
            "valueString": vitals["pulse"]
        })

    # Conditions from chief complaints
    conditions = []
    for idx, c in enumerate(clinical_data.get("chief_complaints", [])):
        conditions.append({
            "resourceType": "Condition",
            "id": f"cond-{record_id}-{idx}",
            "clinicalStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]
            },
            "verificationStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "provisional"}]
            },
            "category": [{
                "coding": [{"system": "http://snomed.info/sct", "code": "439401001", "display": "Diagnosis"}]
            }],
            "code": {
                "text": c.get("symptom", "Symptom")
            },
            "severity": {
                "text": c.get("severity", "Mild")
            }
        })

    # Medication Requests
    med_requests = []
    for idx, p in enumerate(clinical_data.get("prescriptions", [])):
        med_requests.append({
            "resourceType": "MedicationRequest",
            "id": f"med-{record_id}-{idx}",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "text": p.get("medicine", "Medication")
            },
            "dosageInstruction": [{
                "text": f"{p.get('dosage')} - {p.get('frequency')} ({p.get('instructions')})"
            }]
        })

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {
            "versionId": "1.0",
            "lastUpdated": now_iso,
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle"]
        },
        "identifier": {
            "system": "https://abdm.gov.in/teleconsultation",
            "value": f"ABDM-ASHA-{record_id}"
        },
        "type": "document",
        "timestamp": now_iso,
        "entry": [
            {
                "fullUrl": f"urn:uuid:{bundle_id}",
                "resource": {
                    "resourceType": "Composition",
                    "id": f"comp-{record_id}",
                    "status": "final",
                    "type": {
                        "coding": [{
                            "system": "http://snomed.info/sct",
                            "code": "371530004",
                            "display": "Clinical consultation report"
                        }]
                    },
                    "title": f"AshaVaani Voice Consultation Record - Triage {clinical_data.get('triage_level')}",
                    "date": now_iso,
                    "section": [
                        {
                            "title": "Verbatim Indic Voice Narrative (Gnani Prisma v3.0)",
                            "text": {"status": "generated", "div": f"<div>{transcript}</div>"}
                        },
                        {
                            "title": "Triage Urgency & Referral",
                            "text": {"status": "generated", "div": f"<div>Level: {clinical_data.get('triage_level')} - Reason: {clinical_data.get('triage_reason')}</div>"}
                        }
                    ]
                }
            },
            {
                "fullUrl": f"urn:uuid:{patient_id}",
                "resource": {
                    "resourceType": "Patient",
                    "id": patient_id,
                    "identifier": [{
                        "system": "https://healthid.ndhm.gov.in",
                        "value": "91-XXXX-XXXX-1042" # Anonymized ABHA ID
                    }],
                    "gender": "female" if "Maternal" in clinical_data.get("patient_category", "") else "other"
                }
            },
            *([{"fullUrl": f"urn:uuid:{obs['id']}", "resource": obs} for obs in observations]),
            *([{"fullUrl": f"urn:uuid:{cond['id']}", "resource": cond} for cond in conditions]),
            *([{"fullUrl": f"urn:uuid:{med['id']}", "resource": med} for med in med_requests])
        ]
    }
    return bundle
