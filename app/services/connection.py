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
                
    async def broadcast_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    self.disconnect(connection, user_id)
                    
    async def broadcast_to_all(self, message: dict):
        for user_connections in self.active_connections.values():
            for connection in user_connections:
                try:
                    await connection.send_json(message)
                except:
                    pass

    async def broadcast_to_all_except_sender(self, sender_websocket: WebSocket, message: dict):
        for user_connections in self.active_connections.values():
            for connection in user_connections:
                if connection != sender_websocket: 
                    try:
                        await connection.send_json(message)
                    except:
                        pass

# Create a global instance
manager = ConnectionManager() 