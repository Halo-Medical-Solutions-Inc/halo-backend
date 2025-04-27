from fastapi import WebSocket
from app.database.database import database
from app.services.connection import manager
from app.services.anthropic import generate_note_stream
from datetime import datetime
db = database()

async def handle_create_visit(websocket: WebSocket, user_id: str, data: dict):
    visit = db.create_visit(user_id)
    await manager.broadcast_to_all(websocket, user_id,  {
        "type": "create_visit",
        "data": visit
    })

async def handle_update_visit(websocket: WebSocket, user_id: str, data: dict):
    if "visit_id" in data:
        valid_fields = [
            "name", "template_id", "language", "additional_context",
            "recording_started_at", "recording_duration", "recording_finished_at",
            "transcript", "note"
        ]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        visit = db.update_visit(visit_id=data["visit_id"], **update_fields)
        broadcast_data = {"visit_id": data["visit_id"], **{k: visit.get(k) for k in update_fields}}
        broadcast_data["modified_at"] = visit.get("modified_at")
        await manager.broadcast_to_all_except_sender(websocket, user_id, {
            "type": "update_visit",
            "data": broadcast_data
        })
        await manager.broadcast_to_user(websocket, user_id, {
            "type": "update_visit",
            "data": {
                "visit_id": data["visit_id"],
                "modified_at": visit.get("modified_at")
            }
        })
        
async def handle_delete_visit(websocket: WebSocket, user_id: str, data: dict):
    if "visit_id" in data:
        db.delete_visit(data["visit_id"], user_id)
        await manager.broadcast_to_all(websocket, user_id, {
            "type": "delete_visit",
            "data": {"visit_id": data["visit_id"]}
        })

async def handle_regenerate_note(websocket: WebSocket, user_id: str, data: dict):
    if "visit_id" in data:
        visit = db.get_visit(data["visit_id"])
        if visit:
            visit = db.update_visit(visit_id=data["visit_id"], status="GENERATING_NOTE")
            note = await generate_note_stream(
                template=db.get_template(visit["template_id"])['instructions'], 
                transcript=visit["transcript"], 
                additional_context=visit["additional_context"],
                websocket=websocket,
                user_id=user_id,
                visit_id=visit["visit_id"]
            )
            visit = db.update_visit(visit["visit_id"], note=note, status="FINISHED", template_modified_at=datetime.now())
