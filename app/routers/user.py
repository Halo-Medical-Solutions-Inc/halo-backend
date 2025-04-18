from app.models.requests import (
    SignInRequest, SignUpRequest, GetUserRequest, 
    UpdateUserRequest, DeleteUserRequest, GetTemplatesRequest, GetVisitsRequest,
    WebSocketMessage, WebSocketResponse
)
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from app.database.database import database
from app.services.connection import manager

router = APIRouter()
db = database()

@router.post("/signin")
def signin(request: SignInRequest):
    user = db.verify_user(request.email, request.password)
    if user:
        session = db.create_session(user['_id'])
        return session
    else:
        raise HTTPException(status_code=401, detail="Invalid email or password")

@router.post("/signup")
def signup(request: SignUpRequest):
    user = db.create_user(request.name, request.email, request.password)
    if user:
        session = db.create_session(user['_id'])
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

@router.post("/update")
def update_user(request: UpdateUserRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        user = db.update_user(request.update_user.user_id, request.update_user.name, request.update_user.email, request.update_user.password, request.update_user.default_template_id, request.update_user.default_language, request.update_user.template_ids, request.update_user.visit_ids)
        return user
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/delete")
def delete_user(request: DeleteUserRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        db.delete_user(user_id)
        return None
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

async def handle_create_template(websocket: WebSocket, user_id: str, data: dict):
    template = db.create_template(user_id)
    await manager.broadcast_to_all(websocket, {
        "type": "create_template",
        "data": template
    })

async def handle_update_template(websocket: WebSocket, user_id: str, data: dict):
    if "_id" in data:
        valid_fields = [    
            "name", "instructions"
        ]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        template = db.update_template(_id=data["_id"], **update_fields)
        broadcast_data = {"_id": data["_id"], **{k: template.get(k) for k in update_fields}}
        await manager.broadcast_to_all_except_sender(websocket, {
            "type": "update_template",
            "data": broadcast_data
        })

async def handle_delete_template(websocket: WebSocket, user_id: str, data: dict):
    db.delete_template(data["template_id"], user_id)
    await manager.broadcast_to_all(websocket, {
        "type": "delete_template",
        "data": {"template_id": data["template_id"]}
    })

async def handle_create_visit(websocket: WebSocket, user_id: str, data: dict):
    visit = db.create_visit(user_id)
    await manager.broadcast_to_all(websocket, {
        "type": "create_visit",
        "data": visit
    })

async def handle_update_visit(websocket: WebSocket, user_id: str, data: dict):
    if "_id" in data:
        valid_fields = [
            "name", "template_id", "language", "additional_context",
            "recording_started_at", "recording_duration", "recording_finished_at",
            "transcript", "note"
        ]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        visit = db.update_visit(_id=data["_id"], **update_fields)
        broadcast_data = {"_id": data["_id"], **{k: visit.get(k) for k in update_fields}}
        broadcast_data["modified_at"] = visit.get("modified_at")
        await manager.broadcast_to_all_except_sender(websocket, {
            "type": "update_visit",
            "data": broadcast_data
        })

async def handle_delete_visit(websocket: WebSocket, user_id: str, data: dict):
    db.delete_visit(data["visit_id"], user_id)
    await manager.broadcast_to_all(websocket, {
        "type": "delete_visit",
        "data": {"visit_id": data["visit_id"]}
    })


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    user_id = db.is_session_valid(session_id)
    if not user_id:
        await websocket.close(code=1008, reason="Invalid session")
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            message = WebSocketMessage(**data)

            if message.type == "create_template":
                await handle_create_template(websocket, user_id, message.data)
            elif message.type == "update_template":
                await handle_update_template(websocket, user_id, message.data)
            elif message.type == "delete_template":
                await handle_delete_template(websocket, user_id, message.data)
            elif message.type == "create_visit":
                await handle_create_visit(websocket, user_id, message.data)
            elif message.type == "update_visit":
                await handle_update_visit(websocket, user_id, message.data)
            elif message.type == "delete_visit":
                await handle_delete_visit(websocket, user_id, message.data)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print('ERROR', e)
        await websocket.close(code=1011, reason=str(e))

