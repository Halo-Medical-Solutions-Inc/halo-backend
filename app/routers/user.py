from app.models.requests import (
    SignInRequest, SignUpRequest, GetUserRequest, GetTemplatesRequest, GetVisitsRequest, DeleteAllVisitsForUserRequest
)
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.database.database import database
from app.services.connection import manager
from fastapi.websockets import WebSocket, WebSocketDisconnect
from app.models.requests import WebSocketMessage
from app.routers.template import handle_create_template, handle_update_template, handle_delete_template, handle_duplicate_template
from app.routers.visit import handle_create_visit, handle_update_visit, handle_delete_visit
from app.routers.audio import handle_start_recording, handle_pause_recording, handle_resume_recording, handle_finish_recording, handle_audio_chunk
from app.services.deepgram import DeepgramTranscriber
from app.routers.visit import handle_regenerate_note

import asyncio
import threading
import concurrent.futures
import functools

router = APIRouter()
db = database()
# Thread pool for handling websocket messages
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)

@router.post("/signin")
def signin(request: SignInRequest):
    user = db.verify_user(request.email, request.password)
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
    
@router.post("/delete_all_visits_for_user")
def delete_all_visits_for_user(request: DeleteAllVisitsForUserRequest):
    user = db.get_user(request.user_id)
    if user:
        for visit_id in user['visit_ids']:
            db.delete_visit(visit_id, request.user_id)
        return {"message": "All visits deleted"}
    else:
        raise HTTPException(status_code=401, detail="Invalid user")
    
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

async def run_in_threadpool(func, *args, **kwargs):
    """Run a function in a thread pool and await its result."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool,
        lambda: func(*args, **kwargs)
    )

async def process_message_async(websocket, user_id, message_type, data, deepgram=None):
    """Process a message asynchronously without blocking the main WebSocket loop."""
    try:
        if message_type == "create_template":
            await handle_create_template(websocket, user_id, data)
        elif message_type == "update_template":
            await handle_update_template(websocket, user_id, data)
        elif message_type == "delete_template":
            await handle_delete_template(websocket, user_id, data)
        elif message_type == "duplicate_template":
            await handle_duplicate_template(websocket, user_id, data)
        elif message_type == "create_visit":
            await handle_create_visit(websocket, user_id, data)
        elif message_type == "update_visit":
            await handle_update_visit(websocket, user_id, data)
        elif message_type == "delete_visit":
            await handle_delete_visit(websocket, user_id, data)
        elif message_type == "update_user":
            await handle_update_user(websocket, user_id, data)
        elif message_type == "start_recording" and deepgram:
            await handle_start_recording(websocket, user_id, data, deepgram)
        elif message_type == "pause_recording" and deepgram:
            await handle_pause_recording(websocket, user_id, data, deepgram)
        elif message_type == "resume_recording" and deepgram:
            await handle_resume_recording(websocket, user_id, data, deepgram)
        elif message_type == "finish_recording" and deepgram:
            await handle_finish_recording(websocket, user_id, data, deepgram)
        elif message_type == "audio_chunk" and deepgram:
            await handle_audio_chunk(websocket, user_id, data, deepgram)
        elif message_type == "regenerate_note":
            await handle_regenerate_note(websocket, user_id, data)

    except Exception as e:
        print(f"Error processing message {message_type}: {e}")
        await manager.broadcast_to_user(websocket, user_id, {
            "type": "error",
            "data": {"message": f"Error processing {message_type}: {str(e)}"}
        })

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    user_id = db.is_session_valid(session_id)
    if not user_id:
        await websocket.close()
        return

    await manager.connect(websocket, user_id)

    deepgram = DeepgramTranscriber(websocket)

    print("Client connected")
    
    message_queue = asyncio.Queue()
    
    async def process_queue():
        while True:
            try:
                message_type, data = await message_queue.get()
                asyncio.create_task(process_message_async(websocket, user_id, message_type, data, deepgram))
                message_queue.task_done()
            except Exception as e:
                print(f"Error in queue processor: {e}")
    
    queue_processor = asyncio.create_task(process_queue())

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
            
            if message.type in ["audio_chunk"]:
                await process_message_async(websocket, user_id, message.type, message.data, deepgram)
            else:
                await message_queue.put((message.type, message.data))

    except WebSocketDisconnect:
        print("Client disconnected")
        
        if deepgram.current_recording_visit_id:
            visit = db.get_visit(deepgram.current_recording_visit_id)
            if visit and visit["status"] == "RECORDING":
                db.update_visit(deepgram.current_recording_visit_id, status="PAUSED")
            await manager.broadcast_to_all(websocket, user_id, {
                "type": "pause_recording",
                "data": {
                    "visit_id": deepgram.current_recording_visit_id,
                    "status": "PAUSED"
                }
            })
        deepgram.close_connection()
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print('ERROR', e)            
        if deepgram.current_recording_visit_id:
            visit = db.get_visit(deepgram.current_recording_visit_id)
            if visit and visit["status"] == "RECORDING":
                db.update_visit(deepgram.current_recording_visit_id, status="PAUSED")
                await manager.broadcast_to_all(websocket, user_id, {
                    "type": "pause_recording",
                    "data": {
                        "visit_id": deepgram.current_recording_visit_id,
                        "status": "PAUSED"
                    }
                })
        deepgram.close_connection()
        await websocket.close(code=1011, reason=str(e))

