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
                template = db.create_template(user_id)
                await manager.broadcast_to_all(websocket, {
                    "type": "create_template",
                    "data": template
                })
            elif message.type == "update_template":
                if "_id" in message.data:
                    template = db.update_template(_id=message.data["_id"], name=message.data.get("name", None), instructions=message.data.get("instructions", None))
                    await manager.broadcast_to_all_except_sender(websocket, {
                        "type": "update_template",
                        "data": template
                    })
            elif message.type == "delete_template":
                db.delete_template(message.data["template_id"], user_id)
                await manager.broadcast_to_all(websocket, {
                    "type": "delete_template",
                    "data": {"template_id": message.data["template_id"]}
                })
            elif message.type == "create_visit":
                visit = db.create_visit(user_id)
                await manager.broadcast_to_all(websocket, {
                    "type": "create_visit",
                    "data": visit
                })
            elif message.type == "update_visit":
                if "_id" in message.data:
                    # Create a dictionary with only the fields that were provided
                    update_fields = {}
                    if "name" in message.data:
                        update_fields["name"] = message.data["name"]
                    if "template_id" in message.data:
                        update_fields["template_id"] = message.data["template_id"]
                    if "language" in message.data:
                        update_fields["language"] = message.data["language"]
                    if "additional_context" in message.data:
                        update_fields["additional_context"] = message.data["additional_context"]
                    if "recording_started_at" in message.data:
                        update_fields["recording_started_at"] = message.data["recording_started_at"]
                    if "recording_duration" in message.data:
                        update_fields["recording_duration"] = message.data["recording_duration"]
                    if "recording_finished_at" in message.data:
                        update_fields["recording_finished_at"] = message.data["recording_finished_at"]
                    if "transcript" in message.data:
                        update_fields["transcript"] = message.data["transcript"]
                    if "note" in message.data:
                        update_fields["note"] = message.data["note"]
                    
                    # Pass only the fields that need to be updated
                    visit = db.update_visit(_id=message.data["_id"], **update_fields)
                    
                    # Broadcast only the updated fields
                    broadcast_data = {"_id": message.data["_id"]}
                    for key in update_fields:
                        broadcast_data[key] = visit.get(key)
                    # Always include modified_at
                    broadcast_data["modified_at"] = visit.get("modified_at")
                    
                    await manager.broadcast_to_all_except_sender(websocket, {
                        "type": "update_visit",
                        "data": broadcast_data
                    })
            elif message.type == "delete_visit":
                db.delete_visit(message.data["visit_id"], user_id)
                await manager.broadcast_to_all(websocket, {
                    "type": "delete_visit",
                    "data": {"visit_id": message.data["visit_id"]}
                })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print('ERROR', e)
        await websocket.close(code=1011, reason=str(e))

