from fastapi import WebSocket
from app.database.database import database
from app.services.connection import manager

db = database()

async def handle_create_template(websocket: WebSocket, user_id: str, data: dict):
    template = db.create_template(user_id)
    await manager.broadcast_to_all(websocket, {
        "type": "create_template",
        "data": template
    })

async def handle_update_template(websocket: WebSocket, user_id: str, data: dict):
    if "template_id" in data:
        valid_fields = [    
            "name", "instructions"
        ]
        update_fields = {k: v for k, v in data.items() if k in valid_fields}
        template = db.update_template(template_id=data["template_id"], **update_fields)
        broadcast_data = {"template_id": data["template_id"], **{k: template.get(k) for k in update_fields}}
        broadcast_data["modified_at"] = template.get("modified_at")
        await manager.broadcast_to_all_except_sender(websocket, {
            "type": "update_template",
            "data": broadcast_data
        })
        await manager.broadcast_to_user(websocket, {
            "type": "update_template",
            "data": {
                "template_id": data["template_id"],
                "modified_at": template.get("modified_at")
            }
        })

async def handle_delete_template(websocket: WebSocket, user_id: str, data: dict):
    if "template_id" in data:
        db.delete_template(data["template_id"], user_id)
        await manager.broadcast_to_all(websocket, {
            "type": "delete_template",
            "data": {"template_id": data["template_id"]}
        })
