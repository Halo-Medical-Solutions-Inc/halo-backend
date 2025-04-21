from fastapi import WebSocket
from typing import Dict, List, Set

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
    async def broadcast_to_user(self, sender_websocket: WebSocket, message: dict):
        try:
            message_copy = message.copy()
            message_copy["was_requested"] = True
            await sender_websocket.send_json(message_copy)
        except Exception as e:
            print(f"Error sending message to websocket:", e)
            
    async def broadcast_to_all(self, sender_websocket: WebSocket, message: dict, ):
        connection_count = 0
        for user_id, user_connections in self.active_connections.items():
            for connection in user_connections:
                try:
                    message_copy = message.copy()
                    message_copy["was_requested"] = (connection == sender_websocket)
                    
                    await connection.send_json(message_copy)
                    connection_count += 1
                except Exception as e:
                    print(f"Error sending message to user {user_id}:", e)

    async def broadcast_to_all_except_sender(self, sender_websocket: WebSocket, message: dict):
        connection_count = 0
        for user_id, user_connections in self.active_connections.items():
            for connection in user_connections:
                if connection != sender_websocket: 
                    try:
                        await connection.send_json(message)
                        connection_count += 1
                    except Exception as e:
                        print(f"Error sending message to user {user_id}:", e)
# Create a global instance
manager = ConnectionManager() 