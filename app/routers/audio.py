import asyncio
from app.database.database import db
from app.services.logging import logger
from fastapi import HTTPException
import os
import time
import certifi
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File
import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)
from app.config import settings
from app.services.connection import manager
from app.routers.visit import handle_generate_note
import PyPDF2
import docx
import chardet

"""
Audio Processing and Real-time Transcription Module for the Halo Application.

This module provides real-time audio transcription capabilities using AssemblyAI's API.
It handles WebSocket connections for live audio streaming, transcription processing,
and recording state management.

Key features:
- Real-time audio transcription using AssemblyAI
- WebSocket-based audio streaming
- Automatic reconnection and error handling
- Recording state management (start, pause, resume, finish)
- Keep-alive mechanism for stable connections
- Transcript storage and formatting

The module integrates with the database layer to store transcripts and manage
visit recording states, broadcasting updates to connected clients.
"""

router = APIRouter()

class Transcriber:
    """
    Real-time audio transcription handler using AssemblyAI's Streaming API.
    
    This class manages the connection to AssemblyAI's transcription service,
    handles audio data streaming, processes transcription results, and manages
    connection stability through automatic reconnection.
    
    Features:
    - Real-time audio transcription with turn detection
    - Automatic reconnection on connection failures
    - Transcript formatting and storage
    - Error handling and logging
    """
    def __init__(self, api_key: str, visit_id: str):
        """
        Initialize the Transcriber with AssemblyAI API credentials and visit information.
        
        Args:
            api_key (str): The AssemblyAI API key for authentication.
            visit_id (str): The ID of the visit this transcription session belongs to.
            
        Note:
            Sets up SSL certificates and initializes connection state variables.
            Configures automatic reconnection parameters and async task management.
        """
        self.api_key = api_key
        self.visit_id = visit_id
        self.client = None
        self.loop = asyncio.get_event_loop()
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1
        self.reconnecting = False
        self.running_transcript = ""
        
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        
    async def connect(self):
        """
        Establish connection to AssemblyAI's Streaming API with configured options.
        
        Sets up the WebSocket connection with transcription options including:
        - 16kHz sample rate
        - PCM16 encoding
        - Turn formatting enabled
        
        Raises:
            Exception: If connection to AssemblyAI fails, triggers automatic reconnection.
        """
        try:
            await self._cleanup_connection()
            
            self.client = StreamingClient(
                StreamingClientOptions(
                    api_key=settings.ASSEMBLY_API_KEY,
                    api_host="streaming.assemblyai.com",
                )
            )
            
            self.client.on(StreamingEvents.Begin, self._on_begin)
            self.client.on(StreamingEvents.Turn, self._on_turn)
            self.client.on(StreamingEvents.Termination, self._on_terminated)
            self.client.on(StreamingEvents.Error, self._on_error)
            
            self.client.connect(
                StreamingParameters(
                    sample_rate=16000,
                    format_turns=True,
                    encoding="pcm_s16le",
                    end_of_turn_confidence_threshold=0.7,
                    min_end_of_turn_silence_when_confident=160,
                    max_turn_silence=2400
                )
            )
            
            self.is_connected = True
            self.reconnect_attempts = 0
            self.reconnect_delay = 1
            
        except Exception as e:
            logger.error(f"Failed to connect to AssemblyAI: {str(e)}")
            self.is_connected = False
            await self._attempt_reconnect()
            
    async def _cleanup_connection(self):
        """
        Clean up and close the current AssemblyAI connection.
        
        Safely terminates the connection and resets connection state.
        This method is called before establishing new connections or during shutdown.
        
        Note:
            Handles exceptions during cleanup to prevent cascading errors.
        """
        self.is_connected = False
        if self.client:
            try:
                self.client.disconnect(terminate=True)
            except Exception as e:
                logger.debug(f"Error disconnecting: {e}")
            finally:
                self.client = None
            
    async def _attempt_reconnect(self): 
        """
        Attempt to reconnect to AssemblyAI with exponential backoff.
        
        Implements a retry mechanism with increasing delays between attempts.
        Stops attempting after reaching the maximum number of reconnection attempts.
        
        Note:
            Uses exponential backoff with a maximum delay cap of 30 seconds.
            Logs reconnection attempts and final failure if all attempts are exhausted.
        """
        if self.reconnecting or self.reconnect_attempts >= self.max_reconnect_attempts:
            return
        self.reconnecting = True
        self.reconnect_attempts += 1
        try:
            await asyncio.sleep(self.reconnect_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, 30)
            await self.connect()
        except Exception as e:
            logger.error(f"Reconnection attempt {self.reconnect_attempts} failed: {str(e)}")
        finally:
            self.reconnecting = False
            
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Failed to reconnect to AssemblyAI after {self.max_reconnect_attempts} attempts")
    
    def _on_begin(self, client: StreamingClient, event: BeginEvent):
        """
        Handle session begin event from AssemblyAI.
        
        Args:
            client (StreamingClient): The StreamingClient instance.
            event (BeginEvent): The session begin event containing session ID.
        """
        pass
    
    def _on_turn(self, client: StreamingClient, event: TurnEvent):
        """
        Handle incoming transcription turns from AssemblyAI.
        
        Processes real-time transcription data, handling both unformatted
        and formatted transcripts. Stores complete turns when detected.
        
        Args:
            client (StreamingClient): The StreamingClient instance.
            event (TurnEvent): The turn event containing transcript data and metadata.
            
        Note:
            Only stores formatted transcripts to avoid duplicates.
            Accumulates running transcript for voice agent use cases.
        """
        if not event.transcript:
            return
            
        if event.end_of_turn and event.turn_is_formatted:
            asyncio.run_coroutine_threadsafe(
                self._store_transcript(event.transcript, datetime.utcnow().isoformat()),
                self.loop
            )
        
        if event.end_of_turn and not event.turn_is_formatted:
            self.running_transcript = event.transcript
    
    async def _store_transcript(self, transcript_text, timestamp):
        """
        Store transcribed text in the database with timestamp formatting.
        
        Args:
            transcript_text (str): The transcribed text to store.
            timestamp (str): ISO formatted timestamp of when the transcript was created.
            
        Note:
            Appends new transcripts to existing ones with formatted timestamps.
            Handles database errors gracefully with proper logging.
        """
        try:
            current_transcript = db.get_visit(self.visit_id)["transcript"]
            timestamp_formatted = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            new_transcript = f"[{timestamp_formatted}] {transcript_text}"
            if current_transcript: 
                new_transcript = f"{current_transcript}\n{new_transcript}"
            db.update_visit(self.visit_id, transcript=new_transcript)
        except Exception as e:
            logger.error(f"Error storing transcript: {str(e)}")
    
    def _on_error(self, client: StreamingClient, error: StreamingError):
        """
        Handle errors from the AssemblyAI connection.
        
        Args:
            client (StreamingClient): The StreamingClient instance.
            error (StreamingError): The error object containing error details.
            
        Note:
            Logs the error and triggers automatic reconnection attempt.
        """
        logger.error(f"AssemblyAI error: {error}")
        self.is_connected = False
        
        asyncio.run_coroutine_threadsafe(
            self._attempt_reconnect(),
            self.loop
        )
        
    def _on_terminated(self, client: StreamingClient, event: TerminationEvent):
        """
        Handle session termination event from AssemblyAI.
        
        Args:
            client (StreamingClient): The StreamingClient instance.
            event (TerminationEvent): The termination event containing session summary.
        """
        self.is_connected = False
    
    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to AssemblyAI for real-time transcription.
        
        Args:
            audio_data (bytes): Raw audio data to be transcribed.
            
        Note:
            Audio must be PCM16 encoded at 16kHz sample rate.
            Triggers reconnection if the connection is not available.
        """
        if self.client and self.is_connected:
            try:
                self.client.stream(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio data: {str(e)}")
                self.is_connected = False
                await self._attempt_reconnect()
        elif not self.is_connected and not self.reconnecting:
            await self._attempt_reconnect()
                    
    async def disconnect(self):
        """
        Gracefully disconnect from AssemblyAI and clean up resources.
        
        This method should be called when transcription is no longer needed.
        
        Note:
            Logs successful disconnection for debugging purposes.
        """
        await self._cleanup_connection()

@router.websocket("/ws/{visit_id}")
async def transcribe(websocket: WebSocket, visit_id: str):
    """
    WebSocket endpoint for real-time audio transcription.
    
    Accepts WebSocket connections for streaming audio data to be transcribed
    in real-time using AssemblyAI's API. Manages the transcription session
    lifecycle and handles connection cleanup.
    
    Args:
        websocket (WebSocket): The WebSocket connection for audio streaming.
        visit_id (str): The ID of the visit this transcription session belongs to.
        
    Note:
        Sends a "ready" status message once the connection is established.
        Automatically cleans up resources when the connection is closed.
    """
    await websocket.accept()
    transcriber = Transcriber(settings.ASSEMBLY_API_KEY, visit_id)
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
    """
    Handle the start recording request and update visit status.
    
    Updates the visit status to "RECORDING" and sets the recording start timestamp.
    Broadcasts the status change to all connected clients for real-time updates.
    
    Args:
        websocket_session_id (str): The WebSocket session ID for broadcasting.
        user_id (str): The ID of the user starting the recording.
        data (dict): Dictionary containing visit_id and other relevant data.
        
    Raises:
        HTTPException: If there's an error updating the visit or broadcasting the message.
        
    Note:
        Sets recording_started_at to the current UTC timestamp.
        Broadcasts the updated visit information to maintain client synchronization.
    """
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
    """
    Handle the pause recording request and calculate recording duration.
    
    Updates the visit status to "PAUSED" and calculates the total recording duration
    by adding the current session time to any previous recording time.
    
    Args:
        websocket_session_id (str): The WebSocket session ID for broadcasting.
        user_id (str): The ID of the user pausing the recording.
        data (dict): Dictionary containing visit_id and other relevant data.
        
    Raises:
        HTTPException: If there's an error updating the visit or broadcasting the message.
        
    Note:
        Accumulates recording duration across multiple recording sessions.
        Handles cases where recording_started_at might not be set.
    """
    try:
        old_visit = db.get_visit(data["visit_id"])
        old_duration = int(old_visit["recording_duration"] if old_visit["recording_duration"] else 0)
        if old_visit.get("recording_started_at"):
            time_diff = int((datetime.utcnow() - datetime.fromisoformat(old_visit["recording_started_at"])).total_seconds())
            new_duration = old_duration + time_diff
        else:
            new_duration = old_duration
        visit = db.update_visit(data["visit_id"], status="PAUSED", recording_duration=str(new_duration))
        broadcast_message = {
            "type": "pause_recording",
            "data": {
                "visit_id": data["visit_id"],
                "status": "PAUSED",
                "modified_at": visit["modified_at"],
                "recording_duration": visit["recording_duration"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error in pause recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_resume_recording(websocket_session_id: str, user_id: str, data: dict):
    """
    Handle the resume recording request and restart timing.
    
    Updates the visit status back to "RECORDING" and sets a new recording start timestamp
    for calculating additional recording duration when paused again.
    
    Args:
        websocket_session_id (str): The WebSocket session ID for broadcasting.
        user_id (str): The ID of the user resuming the recording.
        data (dict): Dictionary containing visit_id and other relevant data.
        
    Raises:
        HTTPException: If there's an error updating the visit or broadcasting the message.
        
    Note:
        Sets a new recording_started_at timestamp for duration tracking.
        Maintains accumulated recording duration from previous sessions.
    """
    try:
        recording_started_at = str(datetime.utcnow())
        visit = db.update_visit(data["visit_id"], status="RECORDING", recording_started_at=recording_started_at)
        broadcast_message = {
            "type": "resume_recording",
            "data": {
                "visit_id": data["visit_id"],
                "status": "RECORDING",
                "modified_at": visit["modified_at"],
                "recording_started_at": recording_started_at
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
    except Exception as e:
        logger.error(f"Error in resume recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_finish_recording(websocket_session_id: str, user_id: str, data: dict):
    """
    Handle the finish recording request and finalize the visit.
    
    Updates the visit status to "FINISHED", calculates the final recording duration,
    and triggers automatic note generation. Broadcasts the final visit state with
    complete transcript and recording information.
    
    Args:
        websocket_session_id (str): The WebSocket session ID for broadcasting.
        user_id (str): The ID of the user finishing the recording.
        data (dict): Dictionary containing visit_id and other relevant data.
        
    Raises:
        HTTPException: If there's an error updating the visit or broadcasting the message.
        
    Note:
        Sets recording_finished_at timestamp and calculates final duration.
        Triggers asynchronous note generation process.
        Includes complete transcript in the broadcast for immediate access.
    """
    try:
        recording_finished_at = str(datetime.utcnow())
        old_visit = db.get_visit(data["visit_id"])
        old_duration = int(old_visit.get("recording_duration") or 0)
        if old_visit.get("recording_started_at"):
            time_diff = int((datetime.utcnow() - datetime.fromisoformat(old_visit["recording_started_at"])).total_seconds())
            new_duration = old_duration + time_diff
        else:
            new_duration = old_duration
        visit = db.update_visit(data["visit_id"], status="FINISHED", recording_finished_at=recording_finished_at, recording_duration=str(new_duration))
        broadcast_message = {
            "type": "finish_recording",
            "data": {
                "visit_id": data["visit_id"],
                "status": "FINISHED",
                "recording_finished_at": recording_finished_at,
                "modified_at": visit["modified_at"],
                "transcript": visit["transcript"],
                "recording_duration": visit["recording_duration"]
            }
        }
        await manager.broadcast(websocket_session_id, user_id, broadcast_message)
        asyncio.create_task(handle_generate_note(websocket_session_id, user_id, data))
    except Exception as e:
        logger.error(f"Error in finishing recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_file")
async def process_file(file: UploadFile = File(...)):
    """
    Process any type of file and return its text content.
    
    Args:
        file (UploadFile): The uploaded file to process.
        
    Returns:
        str: The extracted text content from the file.
        
    Raises:
        HTTPException: If file processing fails.
        
    Note:
        - Audio files (.mp3, .wav) are transcribed using AssemblyAI
        - PDF files are extracted using PyPDF2
        - Word documents (.docx) are extracted using python-docx
        - Text files are read directly with encoding detection
        - Other file types return an error
    """
    try:
        file_content = await file.read()
        file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        if file_extension in ['mp3', 'wav', 'm4a']:
            transcriber = aai.Transcriber()
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name
            
            try:
                transcript = transcriber.transcribe(tmp_file_path)
                return transcript.text
            finally:
                os.unlink(tmp_file_path)
        
        elif file_extension == 'pdf':
            import io
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            return "\n".join(page.extract_text() for page in pdf_reader.pages).strip()
        
        elif file_extension == 'docx':
            import io
            doc = docx.Document(io.BytesIO(file_content))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)
        
        elif file_extension in ['txt', 'md', 'csv', 'log']:
            detected = chardet.detect(file_content)
            encoding = detected['encoding'] or 'utf-8'
            return file_content.decode(encoding)
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_extension}. Supported types: mp3, wav, pdf, docx, txt, md, csv, log"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing {file_extension} file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process {file_extension}: {str(e)}")