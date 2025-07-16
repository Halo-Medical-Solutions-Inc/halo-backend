import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.services.logging import logger

INSTRUCTIONS = """
Generate everything to the best of your ability.
"""

JSON_SCHEMA = """
{
    "note": "string; use \\n to separate paragraphs"
}
"""

def verify(access_token: str, refresh_token: str, expires_at: str) -> bool:
    """
    Verify Dr. Chrono credentials by checking if the access token is valid.
    
    Args:
        access_token: Dr. Chrono access token
        refresh_token: Dr. Chrono refresh token
        expires_at: Token expiration timestamp
        
    Returns:
        True if credentials are valid, False otherwise
    """
    try:
        # Check if token is expired
        expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        if datetime.utcnow() > expires_at_dt:
            logger.info("Dr. Chrono token is expired")
            return False
        
        # Test the access token by making a simple API call
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        response = requests.get('https://app.drchrono.com/api/users/current', headers=headers, timeout=30)
        
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            logger.error("Dr. Chrono access token is invalid")
            return False
        else:
            logger.error(f"Dr. Chrono API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error verifying Dr. Chrono credentials: {str(e)}")
        return False

def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> Optional[Dict]:
    """
    Refresh an expired access token.
    
    Args:
        refresh_token: Dr. Chrono refresh token
        client_id: Dr. Chrono client ID
        client_secret: Dr. Chrono client secret
        
    Returns:
        Dict with new access_token, refresh_token, and expires_in, or None if refresh failed
    """
    try:
        response = requests.post('https://drchrono.com/o/token/', data={
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
        })
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to refresh Dr. Chrono token: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error refreshing Dr. Chrono token: {str(e)}")
        return None

def get_patients(access_token: str, refresh_token: str, expires_at: str, target_date: Optional[str] = None) -> List[Dict]:
    """
    Get patients with appointments for a specific date.
    
    Args:
        access_token: Dr. Chrono access token
        refresh_token: Dr. Chrono refresh token (for potential refresh)
        expires_at: Token expiration timestamp
        target_date: Date string in format "YYYY-MM-DD". If None, uses today's date.
        
    Returns:
        List of dictionaries with patient_id, patient_name, and patient_details
    """
    try:
        # Use today's date if not specified
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        # Get appointments for the specified date
        appointments_url = f'https://app.drchrono.com/api/appointments?date={target_date}'
        appointments_response = requests.get(appointments_url, headers=headers, timeout=30)
        
        if appointments_response.status_code != 200:
            logger.error(f"Failed to fetch appointments: {appointments_response.status_code}")
            return []
        
        appointments = appointments_response.json().get('results', [])
        patients = []
        seen_patient_ids = set()
        
        for appointment in appointments:
            patient_id = str(appointment.get('patient'))
            
            # Skip if we've already added this patient
            if patient_id in seen_patient_ids:
                continue
                
            seen_patient_ids.add(patient_id)
            
            # Get patient details
            patient_url = f'https://app.drchrono.com/api/patients/{patient_id}'
            patient_response = requests.get(patient_url, headers=headers, timeout=30)
            
            if patient_response.status_code == 200:
                patient_data = patient_response.json()
                patient_name = f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip()
                
                # Format appointment time
                scheduled_time = appointment.get('scheduled_time', '')
                if scheduled_time:
                    try:
                        dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                        appointment_time = dt.strftime("%I:%M %p")
                    except:
                        appointment_time = scheduled_time
                else:
                    appointment_time = 'Unknown time'
                
                patients.append({
                    "patient_id": patient_id,
                    "patient_name": patient_name or "Unknown",
                    "patient_details": f"{target_date} at {appointment_time}"
                })
        
        return patients
        
    except Exception as e:
        logger.error(f"Error getting patients from Dr. Chrono: {str(e)}")
        return []

def create_note(access_token: str, refresh_token: str, expires_at: str, patient_id: str, payload: dict) -> bool:
    """
    Create a clinical note for a patient in Dr. Chrono.
    
    Args:
        access_token: Dr. Chrono access token
        refresh_token: Dr. Chrono refresh token (for potential refresh)
        expires_at: Token expiration timestamp
        patient_id: Patient ID to attach the note to
        payload: Payload containing note content
        
    Returns:
        bool: True if note was created successfully, False otherwise
    """
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Create clinical note
        note_data = {
            'patient': patient_id,
            'text': payload.get('note', ''),
            'created': datetime.utcnow().isoformat() + 'Z'
        }
        
        response = requests.post(
            'https://app.drchrono.com/api/clinical_notes',
            headers=headers,
            json=note_data,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"Clinical note created successfully for patient {patient_id}")
            return True
        else:
            logger.error(f"Failed to create clinical note: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error creating note in Dr. Chrono: {str(e)}")
        return False
