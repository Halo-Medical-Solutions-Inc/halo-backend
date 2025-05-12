from fastapi import WebSocket
from typing import Dict, List, Set, Optional

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
    
    def is_connection_active(self, websocket: Optional[WebSocket]) -> bool:
        """Check if a websocket is still active in any user's connections"""
        if not websocket:
            return False
        
        for user_connections in self.active_connections.values():
            if websocket in user_connections:
                return True
        return False
                
    async def broadcast_to_user(self, sender_websocket: Optional[WebSocket], user_id: str, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    message_copy = message.copy()
                    # Only set was_requested if the sender is still active
                    if self.is_connection_active(sender_websocket):
                        message_copy["was_requested"] = (connection == sender_websocket)
                    else:
                        message_copy["was_requested"] = False
                    await connection.send_json(message_copy)
                except Exception as e:
                    print(f"Error sending message to user {user_id}:", e)
            
    async def broadcast_to_all(self, sender_websocket: Optional[WebSocket], user_id: str, message: dict):
        connection_count = 0
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    message_copy = message.copy()
                    # Only set was_requested if the sender is still active
                    if self.is_connection_active(sender_websocket):
                        message_copy["was_requested"] = (connection == sender_websocket)
                    else:
                        message_copy["was_requested"] = False
                    
                    await connection.send_json(message_copy)
                    connection_count += 1
                except Exception as e:
                    print(f"Error sending message to user {user_id}:", e)

    async def broadcast_to_all_except_sender(self, sender_websocket: Optional[WebSocket], user_id: str, message: dict):
        connection_count = 0
        if user_id in self.active_connections:
            sender_active = self.is_connection_active(sender_websocket)
            for connection in self.active_connections[user_id]:
                # Skip the sender only if it's still active
                if sender_active and connection == sender_websocket:
                    continue
                
                try:
                    await connection.send_json(message)
                    connection_count += 1
                except Exception as e:
                    print(f"Error sending message to user {user_id}:", e)

# Create a global instance
manager = ConnectionManager() 