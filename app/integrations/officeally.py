import requests
from typing import Tuple
from app.services.logging import logger
from datetime import datetime
from typing import List, Dict, Optional


SANDBOX_BASE_URL = "https://sandbox.integuru.ai"
INTEGURU_SECRET = "972E16B5A8F4879C5573A16963334"

INSTRUCTIONS = """
Generate everything to the best of your ability.
"""
JSON_SCHEMA = """
{
   "soap_notes": {
    "ChiefComplaint": "string",
    "HOPI": "string",
    "MedicalHistory": "string",
    "SurgicalHistory": "string",
    "FamilyHistory": "string",
    "SocialHistory": "string",
    "Allergies": "string",
    "CurrentMedications": "string",
    "ROS_Constitutional": "string",
    "ROS_Head": "string",
    "ROS_Neck": "string",
    "ROS_Eyes": "string",
    "ROS_Ears": "string",
    "ROS_Nose": "string",
    "ROS_Mouth": "string",
    "ROS_Throat": "string",
    "ROS_Cardiovascular": "string",
    "ROS_Respiratory": "string",
    "ROS_Gastrointestinal": "string",
    "ROS_Genitourinary": "string",
    "ROS_Musculoskeletal": "string",
    "ROS_Integumentary": "string",
    "ROS_Neurological": "string",
    "ROS_Psychiatric": "string",
    "ROS_Endocrine": "string",
    "ROS_Hematologic": "string",
    "ROS_Allergic": "string",
    "PE_General": "string",
    "PE_ENMT": "string",
    "PE_Neck": "string",
    "PE_Respiratory": "string",
    "PE_Cardiovascular": "string",
    "PE_Lungs": "string",
    "PE_Chest": "string",
    "PE_Heart": "string",
    "PE_Abdomen": "string",
    "PE_Genitourinary": "string",
    "PE_Lymphatic": "string",
    "PE_Musculoskeletal": "string",
    "PE_Skin": "string",
    "PE_Extremities": "string",
    "PE_Neurological": "string",
    "TestResults_ECG": "string",
    "TestResults_Imaging": "string",
    "TestResults_Lab": "string",
    "AssessmentNotes_ICD10": "string",
    "PlanNotes": "string",
    "PatientInstructions": "string"
  },
  "vital_signs": {
    "Height_in": "string",
    "Weight_lb": "string",
    "Pulse": "string",
    "RespiratoryRate": "string"
  },
  "diagnosis_codes": [
    {
      "code": "string",
      "description": "string"
    }
  ],
  "procedure_codes": [
    {
      "code": "string",
      "description": "string",
      "pos": "11",
      "fee": "string",
      "units": "1"
    }
  ],
  "encounter_details": {
    "EncounterDate_Month": "string",
    "EncounterDate_Day": "string",
    "EncounterDate_Year": "string",
    "TreatingProvider": "198417",
    "Office": "166396",
    "EncounterType": "1"
  }
}
"""

def initialize_token() -> Tuple[str, str]:
    """
    Initialize the Integuru token for sandbox environment.
    Returns a tuple of (access_token, user_id)
    """
    response = requests.get(f"{SANDBOX_BASE_URL}/initialize-token", headers={"INTEGURU-SECRET": INTEGURU_SECRET})
    if response.status_code == 200:
        data = response.json()
        return data["access_token"], data["user_id"]
    logger.error(f"Failed to initialize token: {response.text}")
    return None, None

def verify(username: str, password: str) -> bool:
    """
    Verify Office Ally credentials.
    
    Args:
        username: Office Ally username
        password: Office Ally password
    
    Returns:
        True if credentials are valid, False otherwise
    """
    try:
        access_token, user_id = initialize_token()
        if not access_token or not user_id:
            return False
        
        response = requests.post(
            f"{SANDBOX_BASE_URL}/ally/add-credentials",
            headers={"INTEGURU-TOKEN": access_token, "INTEGURU-USER-ID": user_id, "Content-Type": "application/json"},
            json={"username": username, "password": password, "validate_creds": True}
        )
        
        if response.json().get('status'):
            return True
        logger.error(f"Failed to verify credentials: {response.json().get('message')}")
        return False
    except Exception as e:
        logger.error(f"Error verifying credentials: {str(e)}")
        return False

def get_patients(username: str, password: str, target_date: Optional[str] = None) -> List[Dict]:
    """
    Get list of patients from appointments.
    
    Args:
        username: Office Ally username
        password: Office Ally password
        target_date: Date in MM/DD/YYYY format (optional, defaults to today)
    
    Returns:
        List of dictionaries containing:
        - patient_id: Patient ID
        - patient_name: Patient name
        - patient_details: Appointment date and time
    """
    try:
        access_token, user_id = initialize_token()
        headers = {"INTEGURU-TOKEN": access_token, "INTEGURU-USER-ID": user_id, "Content-Type": "application/json"}
        
        response = requests.post(f"{SANDBOX_BASE_URL}/ally/add-credentials", headers=headers, 
                               json={"username": username, "password": password, "validate_creds": True})
        if response.status_code != 200:
            raise Exception(f"Failed to add credentials: {response.text}")
        
        target_date = target_date or datetime.now().strftime("%m/%d/%Y")
        response = requests.get(f"{SANDBOX_BASE_URL}/ally/fetch-appointments", 
                              headers=headers, params={"target_date": target_date})
        
        if response.status_code == 200:
            return [{"patient_id": appt.get("patient_id", ""), "patient_name": appt.get("patient_name", ""),
                    "patient_details": f"{appt.get('date', '')} at {appt.get('time', '')}"} for appt in response.json()]
        elif response.status_code == 404:
            return []
        else:
            raise Exception(f"Failed to fetch appointments: {response.text}")
    except Exception as e:
        logger.error(f"Error getting patients: {str(e)}")
        return []

def create_note(username: str, password: str, patient_id: str, payload: Dict) -> bool:
    """
    Create a progress note for a patient.
    
    Args:
        username: Office Ally username
        password: Office Ally password
        patient_id: Patient ID
        payload: Dictionary containing all progress note data including:
            - diagnosis_codes: List of diagnosis codes with 'code' and 'description'
            - procedure_codes: List of procedure codes with 'code', 'description', 'pos', 'fee', 'units'
            - vital_signs: Dictionary of vital signs
            - soap_notes: Dictionary containing all SOAP note fields
            - encounter_details: Dictionary with encounter date, provider, office, and type
    
    Returns:
        True if note created successfully, False otherwise
    """
    try:
        access_token, user_id = initialize_token()
        headers = {"INTEGURU-TOKEN": access_token, "INTEGURU-USER-ID": user_id, "Content-Type": "application/json"}
        
        response = requests.post(f"{SANDBOX_BASE_URL}/ally/add-credentials", headers=headers,
                               json={"username": username, "password": password, "validate_creds": True})
        if response.status_code != 200:
            raise Exception(f"Failed to add credentials: {response.text}")
        
        note_payload = {"patient_id": patient_id, **{k: payload.get(k, {} if k in ["vital_signs", "soap_notes", "encounter_details"] else []) 
                       for k in ["diagnosis_codes", "procedure_codes", "vital_signs", "soap_notes", "encounter_details"]}}
        
        response = requests.post(f"{SANDBOX_BASE_URL}/ally/create-progressnotes", 
                               headers={"INTEGURU-TOKEN": access_token, "Content-Type": "application/json"}, 
                               json=note_payload)
        
        if response.status_code == 200:
            logger.info(f"Progress note created successfully: {response.json()}")
            return True
        logger.error(f"Failed to create progress note: {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error creating note: {str(e)}")
        return False