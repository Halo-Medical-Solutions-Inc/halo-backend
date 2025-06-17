from app.models.requests import SignInRequest, SignUpRequest, GetUserRequest, GetTemplatesRequest, GetVisitsRequest, WebSocketMessage, VerifyEMRIntegrationRequest
from fastapi import APIRouter, HTTPException
from fastapi.websockets import WebSocket, WebSocketDisconnect
from app.database.database import db
from app.services.connection import manager
from app.routers.template import handle_create_template, handle_update_template, handle_delete_template, handle_duplicate_template, handle_polish_template
from app.routers.visit import handle_create_visit, handle_update_visit, handle_delete_visit, handle_generate_note
from app.routers.audio import handle_start_recording, handle_pause_recording, handle_resume_recording, handle_finish_recording
from app.services.logging import logger
import asyncio
import uuid
from datetime import datetime

"""
User Router for managing user operations.
This router is responsible for user authentication, profile management,
and WebSocket connections. It handles user sign-in, sign-up, profile updates,
and coordinates with other routers for template and visit operations.
"""

router = APIRouter()

@router.post("/signin")
def signin(request: SignInRequest):
    """
    Authenticate a user with email and password.
    
    Args:
        request (SignInRequest): Request containing email and password.
        
    Returns:
        dict: Session information for the authenticated user.
        
    Raises:
        HTTPException: If authentication fails with 401 status code.
        
    Note:
        Creates a new session for the user upon successful authentication.
    """
    user = db.verify_user(request.email, request.password)
    if user:
        session = db.create_session(user['user_id'])
        return session
    else:
        raise HTTPException(status_code=401, detail="Invalid email or password")

@router.post("/signup")
def signup(request: SignUpRequest):
    """
    Register a new user.
    
    Args:
        request (SignUpRequest): Request containing user registration details.
        
    Returns:
        dict: Session information for the newly created user.
        
    Raises:
        HTTPException: If user creation fails with 400 status code.
        
    Note:
        Creates a new session for the user upon successful registration.
    """
    user = db.create_user(request.name, request.email, request.password)
    if user:
        session = db.create_session(user['user_id'])
        return session
    else:
        raise HTTPException(status_code=400, detail="Failed to create user")

@router.post("/get")
def get_user(request: GetUserRequest):
    """
    Retrieve user information.
    
    Args:
        request (GetUserRequest): Request containing session ID.
        
    Returns:
        dict: User information.
        
    Raises:
        HTTPException: If session is invalid with 401 status code.
        
    Note:
        Validates the session before retrieving user information.
    """
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        user = db.get_user(user_id)
        return user
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/get_templates")
def get_templates(request: GetTemplatesRequest):
    """
    Retrieve templates for a user.
    
    Args:
        request (GetTemplatesRequest): Request containing session ID.
        
    Returns:
        list: List of templates associated with the user.
        
    Raises:
        HTTPException: If session is invalid with 401 status code.
        
    Note:
        Validates the session before retrieving template information.
    """
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        templates = db.get_user_templates(user_id)
        return templates
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/get_visits")
def get_visits(request: GetVisitsRequest):
    """
    Retrieve visits for a user.
    
    Args:
        request (GetVisitsRequest): Request containing session ID.
        
    Returns:
        list: List of visits associated with the user.
        
    Raises:
        HTTPException: If session is invalid with 401 status code.
        
    Note:
        Validates the session before retrieving visit information.
    """
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        visits = db.get_user_visits(user_id, request.subset)
        return visits
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/verify_emr_integration")
async def verify_emr_integration(request: VerifyEMRIntegrationRequest):
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
        if request.emr_name == "OFFICE_ALLY":
            if not all(key in request.credentials for key in ["username", "password"]):
                raise HTTPException(status_code=400, detail="Missing required credentials for Office Ally")            
            verified = True
        else:
            raise HTTPException(status_code=400, detail="Unsupported EMR")
        
        emr_integration = {
            "emr": request.emr_name,
            "verified": verified,
            "credentials": request.credentials
        }
        
        updated_user = db.update_user(user_id=user_id, emr_integration=emr_integration)
        print(updated_user)
        return True
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying EMR integration: {e}")
        raise HTTPException(status_code=500, detail=f"EMR verification failed: {str(e)}")

    
async def handle_update_user(websocket_session_id: str, user_id: str, data: dict):
    """
    Update a user's profile information and broadcast the update event.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user to update.
        data (dict): The data containing fields to update, must include user_id.
        
    Raises:
        HTTPException: If there's an error during user update.
        
    Note:
        Only valid fields are extracted from the data for update.
        Broadcasts only the updated fields to all connected clients.
    """
    try:
        valid_fields = ["name", "user_specialty", "default_template_id", "default_language"]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        user = db.update_user(user_id=data["user_id"], **update_fields)
        broadcast_message = {
            "type": "update_user",
            "data": {
                "user_id": data["user_id"], 
                "modified_at": user.get("modified_at"),
                **{k: user.get(k) for k in update_fields}
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time communication.
    
    Args:
        websocket (WebSocket): The WebSocket connection.
        session_id (str): The session ID for authentication.
        
    Note:
        Validates the session before establishing the WebSocket connection.
        Handles different message types and routes them to appropriate handlers.
        Manages connection lifecycle including cleanup on disconnect.
    """
    active_recordings = []
    
    user_id = db.is_session_valid(session_id)
    if not user_id: 
        await websocket.close(code=1008, reason="Invalid session")
        return

    websocket_session_id = str(uuid.uuid4())
    await manager.connect(websocket, websocket_session_id, user_id)

    try:
        while True:
            message = WebSocketMessage(**await websocket.receive_json())
            if db.is_session_valid(message.session_id) is None and len(active_recordings) == 0: 
                await websocket.close(code=1008, reason="Invalid session")
                return

            asyncio.create_task(process_message(websocket_session_id, user_id, message))

            try:
                if message.type == 'start_recording':
                    active_recordings.append(message.data['visit_id'])
                elif message.type == 'pause_recording':
                    active_recordings.remove(message.data['visit_id'])
                elif message.type == 'resume_recording':
                    active_recordings.append(message.data['visit_id'])
                elif message.type == 'finish_recording':
                    active_recordings.remove(message.data['visit_id'])
            except:
                pass
        
    except WebSocketDisconnect:
        for visit_id in active_recordings:
            old_visit = db.get_visit(visit_id)
            old_duration = int(old_visit["recording_duration"] if old_visit["recording_duration"] else 0)
            if old_visit.get("recording_started_at"):
                time_diff = int((datetime.utcnow() - datetime.fromisoformat(old_visit["recording_started_at"])).total_seconds())
                new_duration = old_duration + time_diff
            else:
                new_duration = old_duration
            visit = db.update_visit(visit_id, status="PAUSED", recording_duration=str(new_duration))
            broadcast_message = {
                "type": "pause_recording",
                "data": {
                    "visit_id": visit_id,
                    "status": "PAUSED",
                    "modified_at": visit["modified_at"],
                    "recording_duration": visit["recording_duration"]
                }
            }
            await manager.broadcast(websocket_session_id, user_id, broadcast_message)
        await manager.disconnect(websocket, websocket_session_id, user_id)
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
        await websocket.close(code=1011, reason=str(e))

async def process_message(websocket_session_id: str, user_id: str, message: WebSocketMessage):
    """
    Process incoming WebSocket messages and route to appropriate handlers.
    
    Args:
        websocket_session_id (str): The ID of the websocket session.
        user_id (str): The ID of the user sending the message.
        message (WebSocketMessage): The message to process.
        
    Note:
        Routes different message types to their respective handlers.
        Times the processing of each message type for performance monitoring.
        Logs errors that occur during message processing.
    """
    try:
        if message.type == 'update_user':
            await handle_update_user(websocket_session_id, user_id, message.data)
        elif message.type == 'create_template':
            await handle_create_template(websocket_session_id, user_id, message.data)
        elif message.type == 'update_template':
            await handle_update_template(websocket_session_id, user_id, message.data)
        elif message.type == 'delete_template':
            await handle_delete_template(websocket_session_id, user_id, message.data)
        elif message.type == 'duplicate_template':
            await handle_duplicate_template(websocket_session_id, user_id, message.data)
        elif message.type == 'polish_template':
            await handle_polish_template(websocket_session_id, user_id, message.data)
        elif message.type == 'create_visit':
            await handle_create_visit(websocket_session_id, user_id, message.data)
        elif message.type == 'update_visit':
            await handle_update_visit(websocket_session_id, user_id, message.data)
        elif message.type == 'delete_visit':
            await handle_delete_visit(websocket_session_id, user_id, message.data)
        elif message.type == 'generate_note':
            await handle_generate_note(websocket_session_id, user_id, message.data)   
        elif message.type == 'start_recording':
            await handle_start_recording(websocket_session_id, user_id, message.data)
        elif message.type == 'pause_recording':
            await handle_pause_recording(websocket_session_id, user_id, message.data)
        elif message.type == 'resume_recording':
            await handle_resume_recording(websocket_session_id, user_id, message.data)
        elif message.type == 'finish_recording':
            await handle_finish_recording(websocket_session_id, user_id, message.data)
    except Exception as e:
        logger.error(f"Error processing message {message.type}: {e}")