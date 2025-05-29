from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.anthropic import ask_claude_stream
import json
import logging

"""
WebSocket Chat Router for the Halo Application.

This module provides real-time chat functionality through WebSocket connections.
It handles message streaming from Claude AI and provides error handling for
connection management.

Key features:
- WebSocket connection handling with support for multiple concurrent connections
- Real-time streaming responses from Claude AI
- JSON message formatting for client communication
- Error handling and logging for chat operations

The router allows multiple WebSocket connections simultaneously, with each
connection being independently managed.
"""

router = APIRouter()

@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """
    Handle WebSocket connections for real-time chat functionality.
    
    This endpoint manages WebSocket connections for chat sessions. It processes
    incoming messages, streams responses from Claude AI, and handles connection
    lifecycle. Multiple connections can be active simultaneously.
    
    Args:
        websocket (WebSocket): The WebSocket connection instance.
        
    Note:
        - Supports multiple concurrent connections
        - Streams responses in real-time using Claude AI
        - Handles JSON message parsing and error responses
        
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
    await websocket.accept()
    
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
        logging.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": f"WebSocket error: {str(e)}"}))
        except:
            pass