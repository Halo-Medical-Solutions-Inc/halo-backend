import requests
from typing import Tuple
from app.services.logging import logger
from datetime import datetime
from typing import List, Dict, Optional


SANDBOX_BASE_URL = "https://sandbox.integuru.ai"
INTEGURU_SECRET = "972E16B5A8F4879C5573A16963334"
OFFICEALLY_INSTRUCTIONS = """
Generate everything to the best of your ability.
"""
OFFICEALLY_JSON_SCHEMA = """
{
  "diagnosis_codes": [
    {
      "code": "string",
      "description": "string"
    }
  ],
  "procedure_codes": [
    {
      "code": "string",
      "description": "",
      "pos": "11",
      "fee": "",
      "units": "1"
    }
  ],
  "vital_signs": {
    "Height_in": "string",
    "Weight_lb": "string",
    "BP_Systolic": "string",
    "BP_Diastolic": "string",
    "Temperature_F": "string",
    "Pulse": "string",
    "RespiratoryRate": "string",
    "HeadCircumference_in": "string",
    "Waist_in": "string",
    "Glucose": "string"
  },
  "soap_notes": {
    "ChiefComplaint": "string",
    "HOPI": "string",
    "OnsetDate_Month": "string",
    "OnsetDate_Day": "string",
    "OnsetDate_Year": "string",
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
    "Objective": "string",
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
    "AssessmentNotes_ICD9": "string",
    "PlanNotes": "string",
    "PatientInstructions": "string",
    "Procedures": "string",
    "AdministeredMedication": "string"
  },
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
    else:
        logger.error(f"Failed to initialize token: {response.text}")
        return None, None

def verify_credentials(username: str, password: str) -> bool:
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
        if access_token is None or user_id is None:
            return False
        response = requests.post(
            f"{SANDBOX_BASE_URL}/ally/add-credentials",
            headers={
                "INTEGURU-TOKEN": access_token,
                "INTEGURU-USER-ID": user_id,
                "Content-Type": "application/json"
            },
            json={
                "username": username,
                "password": password,
                "validate_creds": True
            }
        )
        if response.json().get('status') is True:
            return True
        else:
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
        
        headers = {
            "INTEGURU-TOKEN": access_token,
            "INTEGURU-USER-ID": user_id,
            "Content-Type": "application/json"
        }
        
        payload = {"username": username, "password": password, "validate_creds": True}
        response = requests.post(f"{SANDBOX_BASE_URL}/ally/add-credentials", headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Failed to add credentials: {response.text}")
        
        target_date = target_date or datetime.now().strftime("%m/%d/%Y")
        response = requests.get(f"{SANDBOX_BASE_URL}/ally/fetch-appointments", 
                              headers=headers, params={"target_date": target_date})
        
        if response.status_code == 200:
            appointments = response.json()
            return [{
                "patient_id": appt.get("patient_id", ""),
                "patient_name": appt.get("patient_name", ""),
                "patient_details": f"{appt.get('date', '')} at {appt.get('time', '')}"
            } for appt in appointments]
        elif response.status_code == 404:
            return [] 
        else:
            raise Exception(f"Failed to fetch appointments: {response.text}")
    except Exception as e:
        print(f"Error getting patients: {str(e)}")
        return []


def create_note(
    username: str,
    password: str,
    patient_id: str,
    payload: Dict
) -> bool:
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
        # Initialize token
        access_token, user_id = initialize_token()
        
        # Add credentials
        url = f"{SANDBOX_BASE_URL}/ally/add-credentials"
        
        headers = {
            "INTEGURU-TOKEN": access_token,
            "INTEGURU-USER-ID": user_id,
            "Content-Type": "application/json"
        }
        
        cred_payload = {
            "username": username,
            "password": password,
            "validate_creds": True
        }
        
        response = requests.post(url, headers=headers, json=cred_payload)
        
        if response.status_code != 200:
            raise Exception(f"Failed to add credentials: {response.text}")
        
        # Create progress note
        url = f"{SANDBOX_BASE_URL}/ally/create-progressnotes"
        
        headers = {
            "INTEGURU-TOKEN": access_token,
            "Content-Type": "application/json"
        }
        
        # Build the complete payload with patient_id
        note_payload = {
            "patient_id": patient_id,
            "diagnosis_codes": payload.get("diagnosis_codes", []),
            "procedure_codes": payload.get("procedure_codes", []),
            "vital_signs": payload.get("vital_signs", {}),
            "soap_notes": payload.get("soap_notes", {}),
            "encounter_details": payload.get("encounter_details", {})
        }
        
        response = requests.post(url, headers=headers, json=note_payload)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Progress note created successfully: {result}")
            return True
        else:
            print(f"Failed to create progress note: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error creating note: {str(e)}")
        return False
