from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, File, Form
import os
import time
import asyncio
import json
from io import BytesIO
from datetime import datetime
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
)
from app.database.database import database
router = APIRouter()

# Updated database_transcript to use timestamps as keys
database_transcript = {}
db = database()

@router.get("/get_transcript")
async def get_transcript():
    """Return all transcripts in reverse chronological order (latest first)"""
    # Sort the keys (timestamps) in reverse order to get latest first
    sorted_keys = sorted(database_transcript.keys(), reverse=True)
    sorted_transcripts = {k: database_transcript[k] for k in sorted_keys}
    return sorted_transcripts

@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket, session_id: str, visit_id: str):
    await websocket.accept()
    print(f"[INFO] WebSocket connection accepted at {time.time()}")
    
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    
    dg_connection = None
    main_loop = asyncio.get_running_loop()
    audio_data = BytesIO()
    is_finals = []
    
    try:
        
        deepgram = DeepgramClient(api_key="451f9f03c579dcee65854d2740824652dfd7e77e")
        dg_connection = deepgram.listen.websocket.v("1")
        print("[INFO] Deepgram client initialized")
        # Configure Deepgram options
        options = LiveOptions(
            model="nova-3-medical",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            punctuate=True,
            diarize=True,
            channels=1,
            sample_rate=16000,
        )
        
        async def send_json_to_websocket(data):
            await websocket.send_json(data)
        
        def handle_transcript(self, result, **kwargs):
            nonlocal is_finals, main_loop
            if not hasattr(result, 'channel') or not result.channel or not hasattr(result.channel, 'alternatives') or not result.channel.alternatives:
                return
                
            transcript_text = result.channel.alternatives[0].transcript
            if not transcript_text:
                return
            
            
            if result.is_final:
                is_finals.append(transcript_text)
                
                if getattr(result, "speech_final", False):
                    utterance = " ".join(is_finals)
                    timestamp = datetime.now().isoformat()
                    database_transcript[timestamp] = utterance    
                    visit_transcript = db.get_visit(visit_id).get("transcript", "")
                    db.update_visit(visit_id, transcript=f"{visit_transcript}[{timestamp}]: {utterance}\n\n")
                    is_finals = []
            
            asyncio.run_coroutine_threadsafe(
                send_json_to_websocket({
                    "transcript": transcript_text,
                    "is_final": result.is_final,
                    "speech_final": getattr(result, "speech_final", False)
                }), 
                main_loop
            )
        
        def handle_error(self, error, **kwargs):
            print(f"[ERROR] Deepgram error: {error}")
            asyncio.run_coroutine_threadsafe(
                send_json_to_websocket({"error": str(error)}),
                main_loop
            )
            
        def handle_connected(self, connected, **kwargs):
            print(f"[INFO] Deepgram connected")
            asyncio.run_coroutine_threadsafe(
                send_json_to_websocket({"status": "deepgram_connected"}),
                main_loop
            )
            
        def handle_utterance_end(self, utterance_end, **kwargs):
            nonlocal is_finals
            if is_finals:
                utterance = " ".join(is_finals)
                timestamp = datetime.now().isoformat()
                database_transcript[timestamp] = utterance
                print(f"[INFO] Utterance ended: {utterance}")
                is_finals = []
        
        dg_connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)
        dg_connection.on(LiveTranscriptionEvents.Error, handle_error)
        dg_connection.on(LiveTranscriptionEvents.Open, handle_connected)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, handle_utterance_end)
        
        dg_connection.start(options, addons={"no_delay": "true"})
        
        await websocket.send_json({"status": "ready_for_audio"})
        
        packet_count = 0
        last_packet_time = time.time()
        last_activity_time = time.time()
        last_deepgram_time = time.time()
        
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=5.0)
                last_activity_time = time.time()

                if "text" in message:
                    text_data = message["text"]
                    
                    if isinstance(text_data, str) and "ping" in text_data.lower():
                        await websocket.send_json({"status": "pong", "time": time.time()})
                        continue
                    
                    try:
                        json_data = json.loads(text_data)
                        
                        if "ping" in json_data:
                            await websocket.send_json({"status": "pong", "time": time.time()})
                            continue
                            
                        if json_data.get("text") == "stop_recording":
                            print("[INFO] Stop recording command received")
                            if dg_connection:
                                dg_connection.finish()
                            break
                    except json.JSONDecodeError:
                        print(f"[ERROR] Received non-JSON text message: {text_data}")
                
                elif "bytes" in message:
                    data = message["bytes"]
                    current_time = time.time()
                    packet_count += 1
                    
                    audio_data.write(data)
                    
                    if packet_count % 50 == 0:
                        time_diff = current_time - last_packet_time
                        rate = 50 / time_diff if time_diff > 0 else 0
                        print(f"[INFO] Audio packet #{packet_count}: {len(data)} bytes, {rate:.2f} packets/sec")
                        last_packet_time = current_time
                    
                    if dg_connection:
                        try:
                            dg_connection.send(data)
                            last_deepgram_time = current_time
                        except Exception as e:
                            print(f"[ERROR] Error sending to Deepgram: {e}")
                            await websocket.send_json({"error": f"Deepgram send error: {str(e)}"})
                
                current_time = time.time()
                
                # Send keep-alive packet to Deepgram if no data sent in last 8 seconds
                if dg_connection and current_time - last_deepgram_time > 8:
                    print("[INFO] Sending keep-alive packet to Deepgram")
                    # Create a small silent audio packet (a few samples of zeros)
                    # Linear16 format: 2 bytes per sample at 16kHz
                    keep_alive_data = bytes(16)  # 8 samples of silence (16 bytes)
                    dg_connection.send(keep_alive_data)
                    last_deepgram_time = current_time
                
                # Check client connection
                if current_time - last_activity_time > 15:
                    print("[INFO] Connection inactive for 15 seconds, sending ping")
                    await websocket.send_json({"status": "checking_connection"})
                    last_activity_time = current_time
                        
            except asyncio.TimeoutError:
                await websocket.send_json({"status": "waiting_for_audio"})
                
                # Also send keep-alive to Deepgram on timeout if needed
                current_time = time.time()
                if dg_connection and current_time - last_deepgram_time > 8:
                    print("[INFO] Sending keep-alive packet to Deepgram during timeout")
                    keep_alive_data = bytes(16)
                    dg_connection.send(keep_alive_data)
                    last_deepgram_time = current_time
                    
            except WebSocketDisconnect:
                print("[INFO] WebSocket disconnected")
                break
            except Exception as e:
                print(f"[ERROR] Error processing audio data: {e}")
                await websocket.send_json({"error": f"Audio processing error: {str(e)}"})
    
    except WebSocketDisconnect:
        print("[INFO] WebSocket disconnected")
    except Exception as e:
        print(f"[ERROR] WebSocket handler error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
    finally:
        if dg_connection:
            dg_connection.finish()
            print("[INFO] Deepgram connection finished")

            
@router.post("/transcribe")
async def transcribe(file: bytes = File(...), timestamp: str = Form(None), session_id: str = Form(None), visit_id: str = Form(None)):
    try:     
        # Process with Deepgram
        deepgram = DeepgramClient(api_key="451f9f03c579dcee65854d2740824652dfd7e77e")

        payload = {
            "buffer": file,
        }

        options = PrerecordedOptions(
            model="nova-3",
            smart_format=True,
        )

        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        
        if not isinstance(response, dict):
            response_dict = response.to_dict()
        else:
            response_dict = response
            
        
        transcript = ""
        if (isinstance(response_dict, dict) and
            "results" in response_dict and 
            isinstance(response_dict["results"], dict) and
            "channels" in response_dict["results"] and 
            len(response_dict["results"]["channels"]) > 0 and
            "alternatives" in response_dict["results"]["channels"][0] and
            len(response_dict["results"]["channels"][0]["alternatives"]) > 0):
            
            transcript = response_dict["results"]["channels"][0]["alternatives"][0].get("transcript", "")
            
            # Store the transcript in our database with provided timestamp or current timestamp
            if transcript:
                # Use provided timestamp if available, otherwise use current time
                entry_timestamp = timestamp if timestamp else datetime.now().isoformat()
                database_transcript[entry_timestamp] = transcript
                visit_transcript = db.get_visit(visit_id).get("transcript", "")
                db.update_visit(visit_id, transcript=f"{visit_transcript}[{entry_timestamp}]: {transcript}\n\n")
                
        # Return the transcript
        return transcript

    except Exception as e:
        print(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")