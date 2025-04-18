from fastapi import WebSocket
from app.database.database import database
from app.services.connection import manager

db = database()

async def handle_create_visit(websocket: WebSocket, user_id: str, data: dict):
    visit = db.create_visit(user_id)
    await manager.broadcast_to_all(websocket, {
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
        await manager.broadcast_to_all_except_sender(websocket, {
            "type": "update_visit",
            "data": broadcast_data
        })

async def handle_delete_visit(websocket: WebSocket, user_id: str, data: dict):
    if "visit_id" in data:
        db.delete_visit(data["visit_id"], user_id)
        await manager.broadcast_to_all(websocket, {
            "type": "delete_visit",
            "data": {"visit_id": data["visit_id"]}
        })

