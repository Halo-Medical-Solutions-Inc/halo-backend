import asyncio
import os
import time
import certifi
from datetime import datetime
from typing import Callable, Any
from fastapi import WebSocket
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents, PrerecordedOptions
from app.config import settings

class DeepgramTranscriber:
    """
    Handles real-time audio transcription using Deepgram's WebSocket API.
    
    This class sets up a connection to Deepgram and processes audio chunks
    received from a WebSocket, passing transcription results to a callback function.
    """
    
    def __init__(
        self, 
        websocket: WebSocket, 
        callback: Callable[[dict, Any], None] = None,
        api_key: str = settings.DEEPGRAM_API_KEY,
        model: str = "nova-3",
        **options
    ):
        """
        Initialize the transcriber with a WebSocket and callback function.
        
        Args:
            websocket: The WebSocket connection where audio chunks will be received from
            callback: Function to call with transcription results
            api_key: Deepgram API key
            model: Deepgram model to use for transcription
            options: Additional options to pass to Deepgram
        """
        self.websocket = websocket
        self.callback = callback
        self.api_key = api_key
        self.model = model
        self.options = options
        self.dg_connection = None
        self.main_loop = None
        self.is_finals = []
        self.last_audio_sent_time = time.time()
        self.keep_alive_task = None
        self.current_recording_visit_id = None
        
        # Set up SSL certificates
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        
        # Initialize Deepgram client
        self.deepgram = DeepgramClient(api_key=self.api_key)
        
    async def setup_connection(self, callback: Callable[[dict, Any], None], visit_id: str):
        """Set up the connection to Deepgram"""
        self.callback = callback
        self.main_loop = asyncio.get_running_loop()
        self.dg_connection = self.deepgram.listen.websocket.v("1")
        self.current_recording_visit_id = visit_id
        
        # Configure Deepgram options
        dg_options = LiveOptions(
            model=self.model,
            language="multi",
            smart_format=True,
            encoding="linear16",
            punctuate=True,
            diarize=True,
            channels=1,
            sample_rate=16000,
            **self.options
        )
        
        # Set up event handlers
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self._handle_transcript)
        self.dg_connection.on(LiveTranscriptionEvents.Error, self._handle_error)
        self.dg_connection.on(LiveTranscriptionEvents.Open, self._handle_connected)
        self.dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, self._handle_utterance_end)
        
        # Start the connection
        self.dg_connection.start(dg_options, addons={"no_delay": "true"})
        
        # Start keep-alive task
        self.keep_alive_task = asyncio.create_task(self._keep_alive_loop())
        
        # Notify client that we're ready for audio
        await self.websocket.send_json({"status": "ready_for_audio"})
        
    def _handle_transcript(self, self_connection, result, **kwargs):
        """Handle transcript events from Deepgram"""
        if not hasattr(result, 'channel') or not result.channel or not hasattr(result.channel, 'alternatives') or not result.channel.alternatives:
            return
                
        transcript_text = result.channel.alternatives[0].transcript
        if not transcript_text:
            return
                
        if result.is_final:
            self.is_finals.append(transcript_text)
            
            if getattr(result, "speech_final", False):
                utterance = " ".join(self.is_finals)
                timestamp = datetime.utcnow().isoformat()
                self.is_finals = []
                
                # Call the callback with the result
                asyncio.run_coroutine_threadsafe(
                    self.callback({
                        "transcript": utterance,
                        "timestamp": timestamp,
                        "is_final": True,
                        "speech_final": True
                    }, self.main_loop), 
                    self.main_loop
                )
        else:
            asyncio.run_coroutine_threadsafe(
                self.callback({
                    "transcript": transcript_text,
                    "is_final": result.is_final,
                    "speech_final": getattr(result, "speech_final", False)
                }, self.main_loop), 
                self.main_loop
            )
    
    def _handle_error(self, self_connection, error, **kwargs):
        """Handle error events from Deepgram"""
        asyncio.run_coroutine_threadsafe(
            self.callback({"error": str(error)}, self.main_loop),
            self.main_loop
        )
        
    def _handle_connected(self, self_connection, connected, **kwargs):
        """Handle connected events from Deepgram"""
        asyncio.run_coroutine_threadsafe(
            self.callback({"status": "deepgram_connected"}, self.main_loop),
            self.main_loop
        )
        
    def _handle_utterance_end(self, self_connection, utterance_end, **kwargs):
        """Handle utterance end events from Deepgram"""
        if self.is_finals:
            utterance = " ".join(self.is_finals)
            timestamp = datetime.utcnow().isoformat()
            self.is_finals = []
            
            # Call the callback with the utterance
            asyncio.run_coroutine_threadsafe(
                self.callback({
                    "transcript": utterance,
                    "timestamp": timestamp,
                    "is_final": True,
                    "utterance_end": True
                }, self.main_loop),
                self.main_loop
            )
    
    async def process_audio_chunk(self, chunk):
        """Process an audio chunk by sending it to Deepgram"""
        if self.dg_connection:
            try:
                self.dg_connection.send(chunk)
                self.last_audio_sent_time = time.time()
                return True
            except Exception as e:
                await self.callback({"error": f"Deepgram send error: {str(e)}"}, None)
                return False
        return False
    
    async def _keep_alive_loop(self):
        """Send keep-alive packets to prevent connection timeout"""
        try:
            while self.dg_connection:
                await asyncio.sleep(2)  # Check every 2 seconds
                
                # Send keep-alive packet if no data sent in last 8 seconds
                current_time = time.time()
                if current_time - self.last_audio_sent_time > 8:
                    print("[INFO] Sending keep-alive packet to Deepgram")
                    # Create a small silent audio packet (8 samples of zeros)
                    # Linear16 format: 2 bytes per sample at 16kHz
                    keep_alive_data = bytes(16)  # 8 samples of silence (16 bytes)
                    if self.dg_connection:
                        self.dg_connection.send(keep_alive_data)
                        self.last_audio_sent_time = current_time
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[ERROR] Keep-alive loop error: {e}")
    
    async def close_connection(self):
        """Close the Deepgram connection"""
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            
        if self.dg_connection:
            self.dg_connection.finish() 

    async def process_audio_buffer(self, buffer):
        payload = {
            "buffer": buffer,
        }
        options = PrerecordedOptions(
            model="nova-3",
            smart_format=True,
        )
        response = self.deepgram.listen.rest.v("1").transcribe_file(payload, options)
        return response

