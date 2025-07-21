from app.database.database import db
from app.services.connection import manager
from app.services.logging import logger
from app.services.prompts import get_template_instructions
from app.services.anthropic import ask_claude_stream
from fastapi import HTTPException

"""
Template Router for managing templates.
This router is responsible for creating, updating, and deleting templates for a user.
It also handles duplicating templates and provides template polishing functionality.
"""

async def handle_create_template(websocket_session_id: str, user_id: str, data: dict):
    """
    Create a new template for a user and broadcast the creation event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user creating the template.
        data (dict): Additional data for template creation.
        
    Raises:
        HTTPException: If there's an error during template creation.
        
    Note:
        Broadcasts the created template to all connected clients for the user.
    """
    try:
        template = db.create_template(user_id)
        broadcast_message = {
            "type": "create_template",
            "data": template
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_update_template(websocket_session_id: str, user_id: str, data: dict):
    """
    Update an existing template and broadcast the update event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user updating the template.
        data (dict): The data containing fields to update, must include template_id.
        
    Raises:
        HTTPException: If there's an error during template update.
        
    Note:
        Only valid fields are extracted from the data for update.
        Broadcasts only the updated fields to all connected clients.
    """
    try:
        valid_fields = ["name", "instructions", "header", "footer", "print", "note_generation_quality"]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        template = db.update_template(template_id=data["template_id"], **update_fields)
        broadcast_message = {
            "type": "update_template",
            "data": {
                "template_id": data["template_id"], 
                "modified_at": template.get("modified_at"),
                **{k: template.get(k) for k in update_fields}
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
     
    except Exception as e:
        logger.error(f"Error updating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_delete_template(websocket_session_id: str, user_id: str, data: dict):
    """
    Delete a template for a user and broadcast the deletion event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user deleting the template.
        data (dict): The data containing template_id to delete.
        
    Raises:
        HTTPException: If there's an error during template deletion.
        
    Note:
        Broadcasts the deletion event to all connected clients for the user.
    """
    try:
        db.delete_template(template_id=data["template_id"], user_id=user_id)
        broadcast_message = {
            "type": "delete_template",
            "data": {
                "template_id": data["template_id"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_duplicate_template(websocket_session_id: str, user_id: str, data: dict):
    """
    Duplicate an existing template for a user and broadcast the duplication event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user duplicating the template.
        data (dict): The data containing template_id to duplicate.
        
    Raises:
        HTTPException: If there's an error during template duplication.
        
    Note:
        Creates a new template with the same instructions as the original,
        appending "(Copy)" to the name. Broadcasts the new template to all 
        connected clients for the user.
    """
    try:
        old_template = db.get_template(data["template_id"])
        new_template = db.create_template(user_id)
        new_template = db.update_template(new_template["template_id"], name=old_template["name"] + " (Copy)", instructions=old_template["instructions"])
        broadcast_message = {
            "type": "duplicate_template",
            "data": new_template
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error duplicating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_polish_template(websocket_session_id: str, user_id: str, data: dict):
    """
    Polish a template's instructions (placeholder for future implementation).
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user polishing the template.
        data (dict): The data containing template information.
        
    Raises:
        HTTPException: If there's an error during template polishing.
        
    Note:
        This function is currently a placeholder for future implementation.
    """
    try:
        admin = db.get_admin()
        template = db.get_template(template_id=data["template_id"])
        
        message = get_template_instructions(admin.get("master_template_polish_instructions"), template.get("instructions"))
        
        db.update_template(template_id=data["template_id"], status="GENERATING_TEMPLATE")
        async def handle_response(response):
            broadcast_message = {
                "type": "template_generated",
                "data": {
                    "template_id": data["template_id"],
                    "status": "GENERATING_TEMPLATE",
                    "instructions": response
                }
            }
            await manager.broadcast(websocket_session_id, user_id, broadcast_message)
        response = await ask_claude_stream(message, handle_response)
        
        template = db.update_template(template_id=data["template_id"], instructions=response, status="FINISHED")
        broadcast_message = {
            "type": "template_generated",
            "data": {
                "template_id": data["template_id"],
                "status": "FINISHED",
                "instructions": response,
                "modified_at": template.get("modified_at")
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error polishing template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
