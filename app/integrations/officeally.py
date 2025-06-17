import requests
from typing import Tuple
from app.services.logging import logger


SANDBOX_BASE_URL = "https://sandbox.integuru.ai"
INTEGURU_SECRET = "972E16B5A8F4879C5573A16963334"

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