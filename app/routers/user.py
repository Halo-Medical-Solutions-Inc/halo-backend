from app.models.requests import (
    SignInRequest, SignUpRequest, GetUserRequest, GetTemplatesRequest, GetVisitsRequest, 
    WebSocketMessage, VerifyEmailRequest, ResendVerificationRequest, 
    RequestPasswordResetRequest, VerifyResetCodeRequest, ResetPasswordRequest,
    CreateCheckoutSessionRequest, CheckSubscriptionRequest, StartFreeTrialRequest
)
from fastapi import APIRouter, HTTPException
from fastapi.websockets import WebSocket, WebSocketDisconnect
from app.database.database import db
from app.services.connection import manager
from app.services.email import email_service
from app.routers.template import handle_create_template, handle_update_template, handle_delete_template, handle_duplicate_template, handle_polish_template
from app.routers.visit import handle_create_visit, handle_update_visit, handle_delete_visit, handle_generate_note
from app.routers.audio import handle_start_recording, handle_pause_recording, handle_resume_recording, handle_finish_recording
from app.services.logging import logger
import asyncio
import uuid
from datetime import datetime, timedelta
from pydantic import BaseModel
from bson import ObjectId

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
        dict: Session information for the authenticated user or verification needed response.
        
    Raises:
        HTTPException: If authentication fails with 401 status code.
        
    Note:
        If user is unverified, sends new verification code and returns verification needed status.
        Creates a new session for the user upon successful authentication.
    """
    user = db.verify_user(request.email, request.password)
    if user:
        if user['status'] == 'UNVERIFIED':
            code = email_service.generate_code()
            db.set_verification_code(user['user_id'], code)
            email_service.send_verification_email(user['email'], code)
            
            session = db.create_session(user['user_id'])
            return {
                **session,
                "verification_needed": True
            }
        else:
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
        dict: Session information with verification needed flag.
        
    Raises:
        HTTPException: If user creation fails with 400 status code.
        
    Note:
        Sends verification email to the user upon successful registration.
        User status is set to UNVERIFIED until email is verified.
    """
    user = db.create_user(request.name, request.email, request.password)
    if user:
        code = email_service.generate_code()
        db.set_verification_code(user['user_id'], code)
        email_service.send_verification_email(user['email'], code)
        
        session = db.create_session(user['user_id'])
        return {
            **session,
            "verification_needed": True
        }
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
        Allows access for unverified users (they need to get their info to check verification status).
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
        HTTPException: If session is invalid (401) or user is unverified (403).
        
    Note:
        Requires a verified user to access templates.
    """
    user_id = require_verified_user(request.session_id)
    templates = db.get_user_templates(user_id)
    return templates

@router.post("/get_visits")
def get_visits(request: GetVisitsRequest):
    """
    Retrieve visits for a user.
    
    Args:
        request (GetVisitsRequest): Request containing session ID and pagination params.
        
    Returns:
        list: List of visits associated with the user.
        
    Raises:
        HTTPException: If session is invalid (401) or user is unverified (403).
        
    Note:
        Requires a verified user to access visits.
        Supports pagination when subset is False.
    """
    user_id = require_verified_user(request.session_id)
    visits = db.get_user_visits(user_id, request.subset, request.offset, request.limit)
    return visits

@router.post("/verify-email")
def verify_email(request: VerifyEmailRequest):
    """
    Verify email with the provided code.
    
    Args:
        request (VerifyEmailRequest): Request containing session ID and verification code.
        
    Returns:
        dict: Success message if verification is successful.
        
    Raises:
        HTTPException: If session is invalid (401) or verification fails (400).
    """
    user_id = db.is_session_valid(request.session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    if db.verify_email_code(user_id, request.code):
        return {"message": "Email verified successfully"}
    else:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

@router.post("/resend-verification")
def resend_verification(request: ResendVerificationRequest):
    """
    Resend verification email to the user.
    
    Args:
        request (ResendVerificationRequest): Request containing session ID.
        
    Returns:
        dict: Success message if email is sent.
        
    Raises:
        HTTPException: If session is invalid (401) or user is already verified (400).
    """
    user_id = db.is_session_valid(request.session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user = db.get_user(user_id)
    if user['status'] != 'UNVERIFIED':
        raise HTTPException(status_code=400, detail="User is already verified")
    
    code = email_service.generate_code()
    db.set_verification_code(user_id, code)
    email_service.send_verification_email(user['email'], code)
    
    return {"message": "Verification email sent"}

@router.post("/request-password-reset")
def request_password_reset(request: RequestPasswordResetRequest):
    """
    Request password reset for the given email.
    
    Args:
        request (RequestPasswordResetRequest): Request containing email address.
        
    Returns:
        dict: Success message (always returns success for security).
        
    Note:
        Always returns success to prevent email enumeration attacks.
    """
    user = db.get_user_by_email(request.email)
    
    if user and user['status'] == 'ACTIVE':
        code = email_service.generate_code()
        db.set_reset_code(user['user_id'], code)
        email_service.send_password_reset_email(user['email'], code)
    
    return {"message": "If the email exists, a reset code has been sent"}

@router.post("/verify-reset-code")
def verify_reset_code(request: VerifyResetCodeRequest):
    """
    Verify password reset code.
    
    Args:
        request (VerifyResetCodeRequest): Request containing email and reset code.
        
    Returns:
        dict: Success message if code is valid.
        
    Raises:
        HTTPException: If code is invalid or expired (400).
    """
    user_id = db.verify_reset_code(request.email, request.code)
    if user_id:
        return {"message": "Reset code verified", "valid": True}
    else:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    """
    Reset password with the provided reset code.
    
    Args:
        request (ResetPasswordRequest): Request containing email, reset code, and new password.
        
    Returns:
        dict: Success message if password is reset.
        
    Raises:
        HTTPException: If code is invalid (400) or reset fails (500).
    """
    user_id = db.verify_reset_code(request.email, request.code)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    if db.reset_password(user_id, request.new_password):
        return {"message": "Password reset successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to reset password")

@router.post("/start-free-trial")
def start_free_trial(request: StartFreeTrialRequest):
    """
    Start free trial for a user.
    
    Args:
        request (StartFreeTrialRequest): Request containing user_id.
        
    Returns:
        dict: Updated user information.
        
    Raises:
        HTTPException: If user not found or trial already used.
    """
    try:
        user = db.get_user(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.get('subscription', {}).get('free_trial_used'):
            raise HTTPException(status_code=400, detail="Free trial already used")
        
        updated_user = db.start_free_trial(request.user_id)
        if not updated_user:
            raise HTTPException(status_code=500, detail="Failed to start free trial")
        
        return {"message": "Free trial started successfully", "user": updated_user}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start free trial error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start free trial")

@router.post("/check-subscription")
def check_subscription(request: CheckSubscriptionRequest):
    """
    Check if user has an active subscription or valid free trial.
    
    Args:
        request (CheckSubscriptionRequest): Request containing user_id.
        
    Returns:
        dict: Contains subscription status information.
    """
    try:
        user = db.get_user(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        subscription = user.get('subscription', {})
        plan = subscription.get('plan', 'NO_PLAN')
        has_active_subscription = plan in ['MONTHLY', 'YEARLY', 'FREE', 'CUSTOM']
        
        if plan == 'FREE':
            trial_expired = db.check_trial_expired(request.user_id)
            if trial_expired:
                db.update_user_subscription(request.user_id, 'NO_PLAN')
                has_active_subscription = False
                plan = 'NO_PLAN'
            else:
                has_active_subscription = True
        
        return {
            "has_active_subscription": has_active_subscription,
            "subscription": {
                "plan": plan,
                "free_trial_used": subscription.get('free_trial_used', False),
                "free_trial_expiration_date": subscription.get('free_trial_expiration_date')
            }
        }
        
    except Exception as e:
        logger.error(f"Check subscription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check subscription")

def require_verified_user(session_id: str):
    """
    Helper function to validate that a session belongs to a verified user with active subscription or valid trial.
    
    Args:
        session_id (str): The session ID to validate.
        
    Returns:
        str: The user_id if valid and verified.
        
    Raises:
        HTTPException: If session is invalid (401) or user is unverified (403) or subscription required (402).
    """
    user_id = db.is_session_valid(session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user = db.get_user(user_id)
    if user['status'] != 'ACTIVE':
        raise HTTPException(status_code=403, detail="Email verification required")
    
    subscription = user.get('subscription', {})
    plan = subscription.get('plan', 'NO_PLAN')
    if plan in ['MONTHLY', 'YEARLY', 'CUSTOM']:
        return user_id
    elif plan == 'FREE':
        if db.check_trial_expired(user_id):
            db.update_user_subscription(user_id, 'NO_PLAN')
            raise HTTPException(status_code=402, detail="Free trial expired. Subscription required.")
        return user_id
    else:
        raise HTTPException(status_code=402, detail="Active subscription required")

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