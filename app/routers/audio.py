import asyncio
from app.database.database import db
from app.services.logging import logger
from fastapi import HTTPException
import os
import time
import certifi
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from app.config import settings
from app.services.connection import manager
from app.routers.visit import handle_generate_note

router = APIRouter()

class Transcriber:
    def __init__(self, api_key: str, visit_id: str):
        self.api_key = api_key
        self.visit_id = visit_id
        self.connection = None
        self.client = None
        self.last_audio_time = time.time()
        self.keep_alive_task = None
        self.is_finals = []
        self.loop = asyncio.get_event_loop()
        
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        
    async def connect(self):
        self.client = DeepgramClient(self.api_key)
        self.connection = self.client.listen.websocket.v("1")
        self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
        self.connection.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)
        options = LiveOptions(
            model="nova-3",
            language="multi",
            smart_format=True,
            encoding="linear16",
            punctuate=True,
            diarize=True,
            channels=1,
            sample_rate=16000
        )
        self.connection.start(options, addons={"no_delay": "true"})
        self.keep_alive_task = asyncio.create_task(self._keep_alive())
        
    def _on_transcript(self, connection, result, **kwargs):
        if not result.channel or not result.channel.alternatives: return   
        transcript = result.channel.alternatives[0].transcript
        if not transcript: return
        if result.is_final:
            self.is_finals.append(transcript)
            if getattr(result, "speech_final", False):
                utterance = " ".join(self.is_finals)
                self.is_finals = []
                asyncio.run_coroutine_threadsafe(
                    self._store_transcript(utterance, datetime.utcnow().isoformat()),
                    self.loop
                )
    
    async def _store_transcript(self, transcript_text, timestamp):
        print(f"[TRANSCRIPT] {transcript_text}")
        try:
            current_transcript = db.get_visit(self.visit_id)["transcript"]
            timestamp_formatted = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            new_transcript = f"[{timestamp_formatted}] {transcript_text}"
            if current_transcript: new_transcript = f"{current_transcript}\n{new_transcript}"
            db.update_visit(self.visit_id, transcript=new_transcript)
        except Exception as e:
            logger.error(f"Error storing transcript: {str(e)}")
    
    def _on_error(self, connection, error, **kwargs):
        logger.error(f"Deepgram error: {error}")
        
    def _on_utterance_end(self, connection, utterance_end, **kwargs):
        if self.is_finals:
            utterance = " ".join(self.is_finals)
            self.is_finals = []
            asyncio.run_coroutine_threadsafe(
                self._store_transcript(utterance, datetime.utcnow().isoformat()),
                self.loop
            )
    
    async def send_audio(self, audio_data: bytes):
        if self.connection:
            self.connection.send(audio_data)
            self.last_audio_time = time.time()
    
    async def _keep_alive(self):
        while self.connection:
            await asyncio.sleep(1)  
            if time.time() - self.last_audio_time > 2: 
                silence = bytes(16)
                if self.connection:
                    self.connection.send(silence)
                    self.last_audio_time = time.time()
                    
    async def disconnect(self):
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                self.keep_alive_task = None
            except:
                pass
        if self.connection:
            try:
                self.connection.finish()
            except:
                pass
            self.connection = None

@router.websocket("/ws/{visit_id}")
async def transcribe(websocket: WebSocket, visit_id: str):
    await websocket.accept()
    
    transcriber = Transcriber(settings.DEEPGRAM_API_KEY, visit_id)
    
    try:
        await transcriber.connect()
        await websocket.send_json({"status": "ready"})
        
        while True:
            data = await websocket.receive_bytes()
            await transcriber.send_audio(data)
            
    except WebSocketDisconnect:
        await transcriber.disconnect()
    except Exception as e:
        logger.error(f"WebSocket transcription error: {e}")
        await transcriber.disconnect()

async def handle_start_recording(websocket_session_id: str, user_id: str, data: dict):
    try:
        recording_started_at = str(datetime.utcnow())
        visit = db.update_visit(data["visit_id"], status="RECORDING", recording_started_at=recording_started_at)
        broadcast_message = {
            "type": "start_recording",
            "data": {
                "visit_id": data["visit_id"],
                "status": "RECORDING",
                "recording_started_at": recording_started_at,
                "modified_at": visit["modified_at"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error in starting recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_pause_recording(websocket_session_id: str, user_id: str, data: dict):
    try:
        visit = db.update_visit(data["visit_id"], status="PAUSED")
        broadcast_message = {
            "type": "pause_recording",
            "data": {
                "visit_id": data["visit_id"],
                "status": "PAUSED",
                "modified_at": visit["modified_at"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error in pause recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_resume_recording(websocket_session_id: str, user_id: str, data: dict):
    try:
        visit = db.update_visit(data["visit_id"], status="RECORDING")
        broadcast_message = {
            "type": "resume_recording",
            "data": {
                "visit_id": data["visit_id"],
                "status": "RECORDING",
                "modified_at": visit["modified_at"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error in resume recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_finish_recording(websocket_session_id: str, user_id: str, data: dict):
    try:
        recording_finished_at = str(datetime.utcnow())
        visit = db.update_visit(data["visit_id"], status="FINISHED", recording_finished_at=recording_finished_at)
        broadcast_message = {
            "type": "finish_recording",
            "data": {
                "visit_id": data["visit_id"],
                "status": "FINISHED",
                "recording_finished_at": recording_finished_at,
                "modified_at": visit["modified_at"],
                "transcript": visit["transcript"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
        asyncio.create_task(handle_generate_note(websocket_session_id, user_id, data))
    except Exception as e:
        logger.error(f"Error in finishing recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))