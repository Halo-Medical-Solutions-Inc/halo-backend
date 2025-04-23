from app.models.requests import (
    SignInRequest, SignUpRequest, GetUserRequest, GetTemplatesRequest, GetVisitsRequest
)
from fastapi import APIRouter, HTTPException
from app.database.database import database
from app.services.connection import manager
from fastapi.websockets import WebSocket, WebSocketDisconnect
from app.models.requests import WebSocketMessage
from app.routers.template import handle_create_template, handle_update_template, handle_delete_template, handle_duplicate_template
from app.routers.visit import handle_create_visit, handle_update_visit, handle_delete_visit
from app.routers.audio import handle_start_recording, handle_pause_recording, handle_resume_recording, handle_finish_recording, handle_audio_chunk, handle_transcribe_audio

router = APIRouter()
db = database()

@router.post("/signin")
def signin(request: SignInRequest):
    user = db.verify_user(request.email, request.password)
    print(user)
    if user:
        session = db.create_session(user['user_id'])
        return session
    else:
        raise HTTPException(status_code=401, detail="Invalid email or password")

@router.post("/signup")
def signup(request: SignUpRequest):
    user = db.create_user(request.name, request.email, request.password)
    if user:
        session = db.create_session(user['user_id'])
        return session
    else:
        raise HTTPException(status_code=400, detail="Failed to create user")

@router.post("/get")
def get_user(request: GetUserRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        user = db.get_user(user_id)
        return user
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/get_templates")
def get_templates(request: GetTemplatesRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        templates = db.get_user_templates(user_id)
        return templates
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/get_visits")
def get_visits(request: GetVisitsRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        visits = db.get_user_visits(user_id)
        return visits
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

async def handle_update_user(websocket: WebSocket, user_id: str, data: dict):
    if "user_id" in data:
        valid_fields = [
            "name", "user_specialty", "default_template_id", "default_language"
        ]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        user = db.update_user(user_id=data["user_id"], **update_fields)
        broadcast_data = {"user_id": data["user_id"], **{k: user.get(k) for k in update_fields}}
        broadcast_data["modified_at"] = user.get("modified_at")
        await manager.broadcast_to_all_except_sender(websocket, user_id, {
            "type": "update_user",
            "data": broadcast_data
        })
        await manager.broadcast_to_user(websocket, user_id, {
            "type": "update_user",
            "data": {
                "user_id": data["user_id"],
                "modified_at": user.get("modified_at")
            }
        })

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    user_id = db.is_session_valid(session_id)
    if not user_id:
        await websocket.close()
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            message = WebSocketMessage(**data)

            if db.is_session_valid(message.session_id) is None:
                await manager.broadcast_to_user(websocket, user_id, {
                    "type": "error",
                    "data": {"message": "Invalid session"}
                })
                await websocket.close()
                return

            if message.type == "create_template":
                await handle_create_template(websocket, user_id, message.data)
            elif message.type == "update_template":
                await handle_update_template(websocket, user_id, message.data)
            elif message.type == "delete_template":
                await handle_delete_template(websocket, user_id, message.data)
            elif message.type == "duplicate_template":
                await handle_duplicate_template(websocket, user_id, message.data)
            elif message.type == "create_visit":
                await handle_create_visit(websocket, user_id, message.data)
            elif message.type == "update_visit":
                await handle_update_visit(websocket, user_id, message.data)
            elif message.type == "delete_visit":
                await handle_delete_visit(websocket, user_id, message.data)
            elif message.type == "update_user":
                await handle_update_user(websocket, user_id, message.data)
            elif message.type == "start_recording":
                await handle_start_recording(websocket, user_id, message.data)
            elif message.type == "pause_recording":
                await handle_pause_recording(websocket, user_id, message.data)
            elif message.type == "resume_recording":
                await handle_resume_recording(websocket, user_id, message.data)
            elif message.type == "finish_recording":
                await handle_finish_recording(websocket, user_id, message.data)
            elif message.type == "audio_chunk":
                await handle_audio_chunk(websocket, user_id, message.data)
            elif message.type == "transcribe_audio":
                await handle_transcribe_audio(websocket, user_id, message.data)

            

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print('ERROR', e)
        await websocket.close(code=1011, reason=str(e))