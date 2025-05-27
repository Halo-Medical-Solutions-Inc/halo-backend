from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from typing import Dict, List, Set
import asyncio
from datetime import datetime
from app.services.logging import logger

"""
WebSocket Connection Manager for the Halo Application.

This module provides a centralized connection management layer for WebSocket connections.
It includes functionality for managing connections, broadcasting messages, and 
performing health checks on open connections.

Key features:
- Connection lifecycle management (connect, disconnect)
- Message broadcasting to specific users
- Periodic health checks for stale connections
- Activity tracking for connections

All WebSocket operations are encapsulated in the ConnectionManager class,
with proper error handling and logging.
"""


class ConnectionManager:
    """
    Main connection manager class that handles all WebSocket connections.
    Provides methods for connection lifecycle, message broadcasting, and health checks.
    """
    def __init__(self, health_check_interval: int = 30):
        """
        Initialize the connection manager with connection tracking dictionaries.
        
        Args:
            health_check_interval (int): Interval in seconds between health checks. Defaults to 30.
            
        Note:
            Sets up dictionaries for tracking active connections and last activity timestamps.
        """
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.last_activity: Dict[str, Dict[str, datetime]] = {}
        self.health_check_interval = health_check_interval
        self.health_check_task = None
        
    async def start_health_check(self):
        """
        Start periodic health check for websocket connections.
        
        Creates an asyncio task that runs the health check loop in the background.
        """
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
    async def _health_check_loop(self):
        """
        Periodically check if websockets are still open.
        
        Runs continuously at the specified health check interval.
        """
        while True:
            await asyncio.sleep(self.health_check_interval)
            await self._check_connections()
            
    async def _check_connections(self):
        """
        Check all connections and remove closed ones.
        
        Iterates through all active connections and removes any that are in a disconnected state.
        """
        connections_copy = dict(self.active_connections)
        for user_id in connections_copy.keys():
            if user_id in self.active_connections:
                user_connections_copy = dict(self.active_connections[user_id])
                for websocket_session_id, websocket in user_connections_copy.items():
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        logger.info(f"Health check: Removing stale connection for user {user_id}, websocket session {websocket_session_id}")
                        await self._remove_connection(websocket, websocket_session_id, user_id)
        
    async def connect(self, websocket: WebSocket, websocket_session_id: str, user_id: str):
        """
        Connect a new websocket for a websocket session ID.
        
        Args:
            websocket (WebSocket): The WebSocket connection to register.
            websocket_session_id (str): The websocket session ID associated with this connection.
            user_id (str): The ID of the user who owns the connection.
            
        Note:
            Accepts the WebSocket connection and adds it to the active connections.
            Updates the last activity timestamp for the connection.
        """
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        if user_id not in self.last_activity:
            self.last_activity[user_id] = {}
            
        self.active_connections[user_id][websocket_session_id] = websocket
        self.last_activity[user_id][websocket_session_id] = datetime.now()
        logger.info(f"New connection established for websocket session {websocket_session_id}, user {user_id}")
        
    async def disconnect(self, websocket: WebSocket, websocket_session_id: str, user_id: str):
        """
        Disconnect a websocket for a websocket session.
        
        Args:
            websocket (WebSocket): The WebSocket connection to disconnect.
            websocket_session_id (str): The websocket session ID associated with this connection.
            user_id (str): The ID of the user who owns the connection.
            
        Note:
            Removes the connection from active connections and closes the WebSocket.
        """
        await self._remove_connection(websocket, websocket_session_id, user_id)
        
    async def _remove_connection(self, websocket: WebSocket, websocket_session_id: str, user_id: str):
        """
        Remove a connection from the active connections.
        
        Args:
            websocket (WebSocket): The WebSocket connection to remove.
            websocket_session_id (str): The websocket session ID associated with this connection.
            user_id (str): The ID of the user who owns the connection.
            
        Note:
            Cleans up any empty dictionaries in the tracking structures after removal.
            Handles exceptions if the WebSocket is already closed.
        """
        if user_id in self.active_connections and websocket_session_id in self.active_connections[user_id]:
            del self.active_connections[user_id][websocket_session_id]
            if user_id in self.last_activity and websocket_session_id in self.last_activity[user_id]:
                del self.last_activity[user_id][websocket_session_id]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                if user_id in self.last_activity:
                    del self.last_activity[user_id]
            try:
                await websocket.close()
            except Exception:
                pass
                
    async def broadcast(self, requesting_websocket_session_id: str, user_id: str, message: dict):
        """
        Broadcast a message to all connections for a user.
        
        Args:
            requesting_websocket_session_id (str, optional): The websocket session ID that requested this message.
            user_id (str): The ID of the user to broadcast to.
            message (dict): The message to broadcast.
            
        Returns:
            int: The number of connections that received the message.
            
        Note:
            Updates the last activity timestamp for each connection that receives the message.
            Sets was_requested=True for the websocket session that requested the message.
            Removes connections that fail to receive the message.
        """
        if user_id not in self.active_connections:
            logger.warning(f"No active connections for user {user_id}")
            return 0
            
        connection_count = 0
        failed_sessions = []

        connections_copy = dict(self.active_connections[user_id])        
        for websocket_session_id, websocket in connections_copy.items():
            if (user_id in self.active_connections and 
                websocket_session_id in self.active_connections[user_id]):
                try:
                    msg_copy = dict(message)
                    msg_copy["was_requested"] = (websocket_session_id == requesting_websocket_session_id)
                    await websocket.send_json(msg_copy)
                    connection_count += 1
                    if user_id in self.last_activity and websocket_session_id in self.last_activity[user_id]:
                        self.last_activity[user_id][websocket_session_id] = datetime.now()
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}, websocket session {websocket_session_id}: {str(e)}")
                    failed_sessions.append((websocket_session_id, websocket))
                
        for websocket_session_id, websocket in failed_sessions:
            logger.info(f"Removing failed connection for user {user_id}, websocket session {websocket_session_id}")
            await self._remove_connection(websocket, websocket_session_id, user_id)
            
        return connection_count

manager = ConnectionManager()

async def start_connection_manager():
    """
    Start the connection manager's health check task.
    
    Call this from your application startup to begin periodic health checks.
    """
    await manager.start_health_check() 