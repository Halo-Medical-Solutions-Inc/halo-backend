from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import os
import time
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from fastapi.middleware.cors import CORSMiddleware
import certifi
from fastapi import File

router = APIRouter()

@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    await websocket.accept()
    dg_connection = None
    print(f"WebSocket connection accepted at {time.time()}")

    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    
    import asyncio
    main_loop = asyncio.get_running_loop()

    async def send_json_to_websocket(data):
        await websocket.send_json(data)
        
    import wave
    from io import BytesIO
    audio_data = BytesIO()
    is_recording = True
    
    def save_audio_to_wav(audio_bytes, sample_rate=16000, channels=1):
        timestamp = int(time.time())
        filename = f"recording_{timestamp}.wav"
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
        print(f"Audio saved to {filename}")
        return filename

    try:
        deepgram = DeepgramClient(api_key="451f9f03c579dcee65854d2740824652dfd7e77e")
        dg_connection = deepgram.listen.websocket.v("1")
        print("Deepgram client initialized")
        
        options = LiveOptions(
            model="nova-3",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            endpointing=300,
        )
        
        is_finals = []
        
        def handle_transcript(self, result, **kwargs):
            nonlocal is_finals, main_loop
            print(f"TRANSCRIPT RECEIVED: {result}")
            try:
                if hasattr(result, 'channel') and result.channel and hasattr(result.channel, 'alternatives') and len(result.channel.alternatives) > 0:
                    transcript_text = result.channel.alternatives[0].transcript
                    if len(transcript_text) > 0:
                        print(f"Sending transcript: '{transcript_text}', is_final: {result.is_final}")
                        
                        if result.is_final:
                            is_finals.append(transcript_text)
                            
                            if getattr(result, "speech_final", False):
                                utterance = " ".join(is_finals)
                                print(f"Complete utterance: {utterance}")
                                is_finals = []
                        
                        asyncio.run_coroutine_threadsafe(
                            send_json_to_websocket({
                                "transcript": transcript_text,
                                "is_final": result.is_final,
                                "speech_final": getattr(result, "speech_final", False)
                            }), 
                            main_loop
                        )
                else:
                    print(f"Transcript structure issue: {result}")
            except Exception as e:
                print(f"Error in handle_transcript: {e}")
                asyncio.run_coroutine_threadsafe(
                    send_json_to_websocket({"error": f"Transcript handling error: {str(e)}"}),
                    main_loop
                )
        
        def handle_error(self, error, **kwargs):
            nonlocal main_loop
            print(f"DEEPGRAM ERROR: {error}")
            asyncio.run_coroutine_threadsafe(
                send_json_to_websocket({"error": str(error)}),
                main_loop
            )
            
        def handle_metadata(self, metadata, **kwargs):
            print(f"DEEPGRAM METADATA: {metadata}")
            
        def handle_connected(self, connected, **kwargs):
            nonlocal main_loop
            print(f"DEEPGRAM CONNECTED: {connected}")
            asyncio.run_coroutine_threadsafe(
                send_json_to_websocket({"status": "deepgram_connected"}),
                main_loop
            )
            
        def handle_utterance_end(self, utterance_end, **kwargs):
            nonlocal is_finals
            print(f"UTTERANCE END: {utterance_end}")
            if len(is_finals) > 0:
                utterance = " ".join(is_finals)
                print(f"Utterance end event, complete utterance: {utterance}")
                is_finals = []
        
        dg_connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)
        dg_connection.on(LiveTranscriptionEvents.Error, handle_error)
        dg_connection.on(LiveTranscriptionEvents.Metadata, handle_metadata)
        dg_connection.on(LiveTranscriptionEvents.Open, handle_connected)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, handle_utterance_end)
        
        addons = {"no_delay": "true"}
        connection_started = dg_connection.start(options, addons=addons)
        print(f"Deepgram connection started: {connection_started}")
        
        await websocket.send_json({"status": "ready_for_audio"})
        
        packet_count = 0
        last_packet_time = time.time()
        
        while True:
            try:
                message = await websocket.receive()
                
                if "text" in message and message["text"] == "stop_recording":
                    print("Stop recording command received")
                    is_recording = False
                    
                    audio_bytes = audio_data.getvalue()
                    if audio_bytes:
                        filename = save_audio_to_wav(audio_bytes)
                        await websocket.send_json({"status": "recording_saved", "filename": filename})
                    
                    if dg_connection:
                        dg_connection.finish()
                    break
                
                elif "bytes" in message:
                    data = message["bytes"]
                    current_time = time.time()
                    packet_size = len(data)
                    packet_count += 1
                    
                    audio_data.write(data)
                    
                    if packet_count % 50 == 0:
                        time_diff = current_time - last_packet_time
                        rate = 50 / time_diff if time_diff > 0 else 0
                        print(f"Audio packet #{packet_count}: {packet_size} bytes, {rate:.2f} packets/sec")
                        last_packet_time = current_time
                    
                    if dg_connection:
                        dg_connection.send(data)
                    else:
                        print("Warning: dg_connection is None when trying to send data")
                        
            except WebSocketDisconnect:
                print("WebSocket disconnected")
                break
            except Exception as e:
                print(f"Error receiving/processing audio data: {e}")
                await websocket.send_json({"error": f"Audio processing error: {str(e)}"})
    
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"General error in WebSocket handler: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
    finally:
        if audio_data.getvalue():
            try:
                filename = save_audio_to_wav(audio_data.getvalue())
                print(f"Audio saved on connection close: {filename}")
            except Exception as e:
                print(f"Error saving audio on close: {e}")
                
        if dg_connection:
            dg_connection.finish()
            print("Deepgram connection finished")

            
@router.post("/transcribe")
async def transcribe(file: bytes = File(...)):
    try:
        deepgram = DeepgramClient(api_key="451f9f03c579dcee65854d2740824652dfd7e77e")

        payload = {
            "buffer": file,
        }

        options = PrerecordedOptions(
            model="nova-3",
            smart_format=True,
        )

        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        
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
        
        return {"transcript": transcript}

    except Exception as e:
        print(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
