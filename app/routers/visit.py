from app.database.database import db
from app.services.connection import manager
from app.services.logging import logger
from fastapi import HTTPException
from app.services.prompts import get_instructions
from app.services.anthropic import ask_claude_stream, ask_claude
from datetime import datetime
from fastapi import APIRouter
import asyncio
import re
from app.integrations import officeally, advancemd
from app.models.requests import CreateVisitRequest

"""
Visit Router for managing visits.
This router is responsible for creating, updating, and deleting visits for a user.
It also handles the generation of notes for a visit using Claude AI.
"""

router = APIRouter()

@router.post("/create")
async def create_visit(request: CreateVisitRequest):
    """
    Create a new visit for a user with specified name and context.
    
    Args:
        request (CreateVisitRequest): The request containing user_email, visit_name, and visit_additional_context.
        
    Returns:
        dict: The newly created visit document.
        
    Raises:
        HTTPException: If user is not found or there's an error during visit creation.
    """
    try:
        user = db.get_user_by_email(request.user_email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_id = user['user_id']
        visit = db.create_visit(user_id)
        
        if request.visit_name or request.visit_additional_context:
            visit = db.update_visit(
                visit_id=visit['visit_id'],
                name=request.visit_name,
                additional_context=request.visit_additional_context
            )
        
        return visit
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating visit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        sections = parse_sections(template.get("instructions"))

        if (len(visit.get("transcript").split()) + len(visit.get("additional_context").split())) < 10:
            db.update_visit(visit_id=data["visit_id"], status="FINISHED", note="Insufficient transcript, please record again.")
            await manager.broadcast(websocket_session_id, user_id, {
                "type": "note_generated",
                "data": {
                    "visit_id": data["visit_id"],
                    "status": "FINISHED",
                    "note": "Insufficient transcript, please record again."
                }
            })
            return
        
        db.update_visit(visit_id=data["visit_id"], status="GENERATING_NOTE")
        section_responses = {}
        response_lock = asyncio.Lock()
        
        async def handle_section_response(section_name, response):
            async with response_lock:
                section_responses[section_name] = response
                combined_note = ""
                for section in sections:
                    if section['name'] in section_responses:
                        if section['name']:
                            combined_note += f"**{section['name']}**\n{section_responses[section['name']]}\n\n"
                        else:
                            combined_note += f"{section_responses[section['name']]}\n\n"
                
                await manager.broadcast(websocket_session_id, user_id, {
                    "type": "note_generated",
                    "data": {
                        "visit_id": data["visit_id"],
                        "status": "GENERATING_NOTE",
                        "note": combined_note.strip()
                    }
                })
        
        tasks = []
        for section in sections:
            section_message = get_instructions(
                admin.get("master_note_generation_instructions"),
                visit.get("transcript"),
                visit.get("additional_context"),
                section['content'],
                user.get("user_specialty"),
                user.get("name")
            )
            tasks.append(generate_section(section['name'], section_message, handle_section_response, user.get("note_generation_quality")))
        await asyncio.gather(*tasks)
        
        final_note = ""
        for section in sections:
            if section['name'] in section_responses:
                if section['name']:
                    final_note += f"**{section['name']}**\n{section_responses[section['name']]}\n\n"
                else:
                    final_note += f"{section_responses[section['name']]}\n\n"
        
        final_note = final_note.strip()
        template_modified_at = str(datetime.utcnow())
        db.update_visit(visit_id=data["visit_id"], note=final_note, status="FINISHED", template_modified_at=template_modified_at)
        
        await manager.broadcast(websocket_session_id, user_id, {
            "type": "note_generated",
            "data": {
                "visit_id": data["visit_id"],
                "status": "FINISHED",
                "note": final_note,
                "template_modified_at": template_modified_at
            }
        })

    except Exception as e:
        logger.error(f"Error generating note: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def parse_sections(template_instructions):
    """
    Parse sections from template instructions.
    Sections are identified by text surrounded by ##.
    
    Args:
        template_instructions (str): The template instructions containing sections.
        
    Returns:
        list: A list of dictionaries containing section name and content.
    """
    sections = []
    pattern = r'##([^#]+)##'
    matches = list(re.finditer(pattern, template_instructions))
    
    if not matches:
        sections.append({'name': '','content': template_instructions.strip()})
        return sections
    
    for i, match in enumerate(matches):
        section_name = match.group(1).strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i < len(matches) - 1 else len(template_instructions)
        section_content = template_instructions[start_pos:end_pos].strip()
        sections.append({
            'name': section_name,
            'content': section_content
        })
    
    return sections

async def generate_section(section_name, message, callback, quality='BASIC'):
    """
    Generate a single section using Claude AI.
    
    Args:
        section_name (str): The name of the section being generated.
        message (str): The message to send to Claude.
        callback (function): Callback function to handle the response.
    """
    model = "claude-3-7-sonnet-20250219"
    tokens = 64000
    thinking = False

    if quality == 'BASIC':
        model = "claude-3-7-sonnet-20250219"
        tokens = 64000
        thinking = False
    elif quality == 'PRO':
        model = "claude-sonnet-4-20250514"
        tokens = 64000
        thinking = False
    elif quality == 'PREMIUM':
        model = "claude-opus-4-20250514"
        tokens = 64000
        thinking = False

    return await ask_claude_stream(
        message,
        lambda text: callback(section_name, text),
        model=model,
        max_tokens=tokens,
        thinking=thinking
    )

async def handle_generate_visit_name(websocket_session_id: str, user_id: str, data: dict):
    """
    Handle automatic visit name generation based on the transcript.
    
    Generates a descriptive name for the visit if it doesn't already have one
    or if it has a default name. Uses Claude to analyze the transcript and
    create an appropriate name.
    
    Args:
        websocket_session_id (str): The WebSocket session ID for broadcasting.
        user_id (str): The ID of the user.
        data (dict): Dictionary containing visit_id and other relevant data.
        
    Note:
        Only generates a name if the current name is empty, None, or "New Visit".
        Broadcasts the updated name to all connected clients.
    """
    try:
        visit = db.get_visit(data["visit_id"])
        if not visit.get("name") or visit.get("name") == "" or visit.get("name") == "New Visit":
            name = await ask_claude(f"Generate a name for the visit based on the transcript: {visit.get('transcript')} and additional context: {visit.get('additional_context')}. The name should be a single word or phrase that captures the name of the patient that is coming in for the visit. If no patient name can be found in the transcript or additional context, return exactly 'New Visit'.")
            db.update_visit(data["visit_id"], name=name)
            broadcast_message = {
                "type": "update_visit",
                "data": {
                    "visit_id": data["visit_id"],
                    "name": name
                }
            }
            await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error generating visit name: {str(e)}")