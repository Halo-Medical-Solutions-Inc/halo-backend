from fastapi import APIRouter, HTTPException
from app.database.database import db
from app.services.logging import logger
from app.models.requests import VerifyEMRIntegrationRequest, GetPatientsEMRIntegrationRequest, CreateNoteEMRIntegrationRequest
from app.integrations import officeally, advancemd
from app.services.connection import manager
import json
from app.services.anthropic import ask_claude_json
from datetime import datetime

router = APIRouter()

@router.post("/verify")
async def verify(request: VerifyEMRIntegrationRequest):
    """
    Verify EMR integration credentials for a user.
    
    Args:
        request (VerifyEMRIntegrationRequest): Request containing session ID, EMR name, and credentials.
        
    Returns:
        dict: Verification result with status and updated user information.
        
    Raises:
        HTTPException: If session is invalid with 401 status code.
                      If EMR verification fails with 400 status code.
        
    Note:
        Currently supports OFFICE_ALLY EMR system.
        Stores encrypted credentials upon successful verification.
    """
    user_id = db.is_session_valid(request.session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    try:
        if request.emr == "OFFICE_ALLY":
            verified = officeally.verify(request.credentials["username"], request.credentials["password"])
        elif request.emr == "ADVANCEMD":
            verified = advancemd.verify(request.credentials["username"], request.credentials["password"], request.credentials["office_key"], request.credentials["app_name"])
        else:
            logger.error(f"Unsupported EMR: {request.emr}")
            raise HTTPException(status_code=400, detail="Unsupported EMR")
            return

        emr_integration = {
            "emr": request.emr,
            "verified": verified,
            "credentials": request.credentials if verified else {}
        }
        user = db.update_user(user_id=user_id, emr_integration=emr_integration)
        broadcast_message = {
            "type": "update_user",
            "data": user
        }
        await manager.broadcast('', user_id, broadcast_message)

        return user
    except Exception as e:
        logger.error(f"Error verifying EMR integration: {e}")
        raise HTTPException(status_code=500, detail=f"EMR verification failed: {str(e)}")

@router.post("/get_patients")
async def get_patients(request: GetPatientsEMRIntegrationRequest):
    """
    Get patients from EMR integration.
    """
    user_id = db.is_session_valid(request.session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    try:
        user = db.get_user(user_id)

        if user.get("emr_integration").get("emr") == "OFFICE_ALLY":
            patients = officeally.get_patients(user.get("emr_integration").get("credentials").get("username"), user.get("emr_integration").get("credentials").get("password"))
        elif user.get("emr_integration").get("emr") == "ADVANCEMD":
            patients = advancemd.get_patients(user.get("emr_integration").get("credentials").get("username"), user.get("emr_integration").get("credentials").get("password"), user.get("emr_integration").get("credentials").get("office_key"), user.get("emr_integration").get("credentials").get("app_name"))
        else:
            logger.error(f"Unsupported EMR: {user.get('emr_integration').get('emr')}")
            raise HTTPException(status_code=400, detail="Unsupported EMR")
            return []

        return patients
    except Exception as e:
        logger.error(f"Error getting patients from EMR integration: {e}")
        raise HTTPException(status_code=500, detail=f"EMR integration failed: {str(e)}")


@router.post("/create_note")
async def create_note(request: CreateNoteEMRIntegrationRequest):
    """
    Create a note for a patient.
    """
    user_id = db.is_session_valid(request.session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    try:
        user = db.get_user(user_id)
        visit = db.get_visit(request.visit_id)

        instructions = "Today's date and time: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + "\n\n" + "Take the existing SOAP note and do NOT edit or concise down any of the words, move the corresponding parts of the note into the Office Ally JSON schema. Keep the content and formatting pretty much exactly the same. Just map the parts.  Ie: Chief complaint content goes into the chief complaint part of the JSON"
        instructions += visit.get("note")

        if user.get("emr_integration").get("emr") == "OFFICE_ALLY":
            json_schema = officeally.JSON_SCHEMA
            note = await ask_claude_json(instructions, json_schema, model="claude-sonnet-4-20250514", max_tokens=64000)
            officeally.create_note(user.get("emr_integration").get("credentials").get("username"), user.get("emr_integration").get("credentials").get("password"), request.patient_id, note)
        elif user.get("emr_integration").get("emr") == "ADVANCEMD":
            json_schema = advancemd.JSON_SCHEMA
            note = await ask_claude_json(instructions, json_schema, model="claude-sonnet-4-20250514", max_tokens=64000)
            advancemd.create_note(user.get("emr_integration").get("credentials").get("username"), user.get("emr_integration").get("credentials").get("password"), user.get("emr_integration").get("credentials").get("office_key"), user.get("emr_integration").get("credentials").get("app_name"), request.patient_id, note)
        else:
            logger.error(f"Unsupported EMR: {user.get('emr_integration').get('emr')}")
            raise HTTPException(status_code=400, detail="Unsupported EMR")
            return False

        return True
    except Exception as e:
        logger.error(f"Error creating note: {e}")
        raise HTTPException(status_code=500, detail=f"EMR integration failed: {str(e)}")
        return False
