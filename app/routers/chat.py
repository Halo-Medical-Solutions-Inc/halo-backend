from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.anthropic import ask_claude_stream
import json
import logging
from typing import Dict, Set
import asyncio

"""
WebSocket Chat Router for the Halo Application.

This module provides real-time chat functionality through WebSocket connections.
It manages active WebSocket sessions, handles message streaming from Claude AI,
and provides error handling for connection management.

Key features:
- WebSocket session management with concurrent connection handling
- Real-time streaming responses from Claude AI
- JSON message formatting for client communication
- Automatic cleanup of disconnected sessions
- Error handling and logging for chat operations

The router maintains a global dictionary of active sessions to ensure
only one connection per session ID and proper resource cleanup.
"""

router = APIRouter()

active_sessions: Dict[str, WebSocket] = {}
session_lock = asyncio.Lock()

@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    Handle WebSocket connections for real-time chat functionality.
    
    This endpoint manages WebSocket connections for chat sessions, ensuring only
    one active connection per session ID. It processes incoming messages,
    streams responses from Claude AI, and handles connection lifecycle.
    
    Args:
        websocket (WebSocket): The WebSocket connection instance.
        session_id (str): Unique identifier for the chat session.
        
    Note:
        - Automatically closes existing connections for the same session_id
        - Streams responses in real-time using Claude AI
        - Handles JSON message parsing and error responses
        - Cleans up session tracking on disconnection
        
    Message Format:
        Incoming: {"message": "user message text"}
        Outgoing: 
            - {"type": "chunk", "content": "partial response"}
            - {"type": "complete", "content": "full response"}
            - {"type": "error", "message": "error description"}
            
    Raises:
        WebSocketDisconnect: When the client disconnects from the WebSocket.
        Exception: For any other errors during message processing.
    """
    async with session_lock:
        if session_id in active_sessions:
            existing_ws = active_sessions[session_id]
            try:
                await existing_ws.close()
            except:
                pass
            
        await websocket.accept()
        active_sessions[session_id] = websocket
    
    try:
        while True:
            try:
                message_data = json.loads(await websocket.receive_text())
                message = message_data.get("message", "")
                
                if not message:
                    await websocket.send_text(json.dumps({"type": "error", "message": "No message provided"}))
                    continue
                
                async def stream_callback(partial_response):
                    await websocket.send_text(json.dumps({"type": "chunk", "content": partial_response}))
                
                full_response = await ask_claude_stream(message, stream_callback, model="claude-3-5-haiku-latest", max_tokens=8192)
                await websocket.send_text(json.dumps({"type": "complete", "content": full_response}))
                
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON format"}))
            except Exception as e:
                logging.error(f"Error processing message: {str(e)}")
                await websocket.send_text(json.dumps({"type": "error", "message": f"Error processing message: {str(e)}"}))
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.error(f"WebSocket error for session {session_id}: {str(e)}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": f"WebSocket error: {str(e)}"}))
        except:
            pass
    finally:
        async with session_lock:
            if session_id in active_sessions and active_sessions[session_id] == websocket:
                del active_sessions[session_id]