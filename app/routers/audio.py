from fastapi.websockets import WebSocket
from app.database.database import database
from datetime import datetime

db = database()

async def handle_start_recording(websocket: WebSocket, user_id: str, data: dict):
    db.update_visit(visit_id=data["visit_id"], status="recording", recording_started_at=datetime.now())
    # TODO: create deepgram client
    pass

async def handle_pause_recording(websocket: WebSocket, user_id: str, data: dict):
    db.update_visit(visit_id=data["visit_id"], status="paused")
    # TODO: end deepgram client
    pass

async def handle_resume_recording(websocket: WebSocket, user_id: str, data: dict):
    db.update_visit(visit_id=data["visit_id"], status="recording")
    # TODO: create deepgram client
    pass

async def handle_finish_recording(websocket: WebSocket, user_id: str, data: dict):
    db.update_visit(visit_id=data["visit_id"], status="finished", recording_finished_at=datetime.now())
    # TODO: end deepgram client
    pass

async def handle_audio_chunk(websocket: WebSocket, user_id: str, data: dict):
    # TODO: process audio chunk
    # TODO: update database
    pass

async def handle_transcribe_audio(websocket: WebSocket, user_id: str, data: dict):
    # TODO: create deepgram client
    # TODO: transcribe audio
    # TODO: update database
    pass


