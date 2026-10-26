import logging
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("aquora.websocket")

class ConnectionManager:
    """
    Manages active WebSocket client connections for real-time telemetry streaming.
    Supports local network broadcast without internet.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                self.disconnect(connection)

    def broadcast_sync(self, message: Dict[str, Any]):
        """Helper to broadcast from synchronous router contexts."""
        if not self.active_connections:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast(message))
            else:
                loop.run_until_complete(self.broadcast(message))
        except RuntimeError:
            pass

ws_manager = ConnectionManager()
