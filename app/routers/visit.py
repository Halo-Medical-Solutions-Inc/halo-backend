from app.database.database import db
from app.services.connection import manager
from app.services.logging import logger
from fastapi import HTTPException
from app.services.prompts import get_instructions
from app.services.anthropic import ask_claude_stream
from datetime import datetime
from fastapi import APIRouter

"""
Visit Router for managing visits.
This router is responsible for creating, updating, and deleting visits for a user.
It also handles the generation of notes for a visit using Claude AI.
"""

router = APIRouter()

async def handle_create_visit(websocket_session_id: str, user_id: str, data: dict):
    """
    Create a new visit for a user and broadcast the creation event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user creating the visit.
        data (dict): Additional data for visit creation.
        
    Raises:
        HTTPException: If there's an error during visit creation.
        
    Note:
        Broadcasts the created visit to all connected clients for the user.
    """
    try:
        visit = db.create_visit(user_id)
        broadcast_message = {
            "type": "create_visit",
            "data": visit
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error creating visit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_update_visit(websocket_session_id: str, user_id: str, data: dict):
    """
    Update an existing visit and broadcast the update event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user updating the visit.
        data (dict): The data containing fields to update, must include visit_id.
        
    Raises:
        HTTPException: If there's an error during visit update.
        
    Note:
        Only valid fields are extracted from the data for update.
        Broadcasts only the updated fields to all connected clients.
    """
    try:
        valid_fields = ["name", "status", "template_id", "language", "additional_context", "recording_started_at", "recording_duration", "recording_finished_at", "transcript", "note"]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        visit = db.update_visit(visit_id=data["visit_id"], **update_fields)
        broadcast_message = {
            "type": "update_visit",
            "data": {
                "visit_id": data["visit_id"],
                "modified_at": visit.get("modified_at"),
                **{k: visit.get(k) for k in update_fields}
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error updating visit: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
async def handle_delete_visit(websocket_session_id: str, user_id: str, data: dict):
    """
    Delete a visit for a user and broadcast the deletion event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user deleting the visit.
        data (dict): The data containing visit_id to delete.
        
    Raises:
        HTTPException: If there's an error during visit deletion.
        
    Note:
        Broadcasts the deletion event to all connected clients for the user.
    """
    try:
        db.delete_visit(visit_id=data["visit_id"], user_id=user_id)
        broadcast_message = {
            "type": "delete_visit",
            "data": {
                "visit_id": data["visit_id"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error deleting visit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_generate_note(websocket_session_id: str, user_id: str, data: dict):
    """
    Generate a note for a visit using Claude AI and broadcast updates.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user generating the note.
        data (dict): The data containing visit_id for note generation.
        
    Raises:
        HTTPException: If there's an error during note generation.
        
    Note:
        1. Retrieves relevant user, visit, and template data
        2. Creates instructions for Claude based on transcript, context and template
        3. Updates visit status to "GENERATING_NOTE"
        4. Streams the generated note to connected clients
        5. Updates the visit with the completed note and changes status to "FINISHED"
    """
    try:
        admin = db.get_admin()
        user = db.get_user(user_id=user_id)
        visit = db.get_visit(visit_id=data["visit_id"])
        template = db.get_template(template_id=visit.get("template_id"))

        message = get_instructions(admin.get("master_note_generation_instructions"), visit.get("transcript"), visit.get("additional_context"), template.get("instructions"), user.get("user_specialty"), user.get("name"))

        db.update_visit(visit_id=data["visit_id"], status="GENERATING_NOTE")
        async def handle_response(response):
            broadcast_message = {
                "type": "note_generated",
                "data": {
                    "visit_id": data["visit_id"],
                    "status": "GENERATING_NOTE",
                    "note": response
                }
            }
            await manager.broadcast(websocket_session_id, user_id, broadcast_message)
        response = await ask_claude_stream(message, handle_response)

        template_modified_at = str(datetime.utcnow())
        db.update_visit(visit_id=data["visit_id"], note=response, status="FINISHED", template_modified_at=template_modified_at)
        broadcast_message = {
            "type": "note_generated",
            "data": {
                "visit_id": data["visit_id"],
                "status": "FINISHED",
                "note": response,
                "template_modified_at": template_modified_at
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)

    except Exception as e:
        logger.error(f"Error generating note: {e}")
        raise HTTPException(status_code=500, detail=str(e))