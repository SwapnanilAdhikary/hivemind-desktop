from __future__ import annotations

import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections to the Electron frontend."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.remove(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        payload = json.dumps({"type": event_type, "data": data})
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    async def send_personal(self, websocket: WebSocket, event_type: str, data: dict[str, Any]) -> None:
        payload = json.dumps({"type": event_type, "data": data})
        await websocket.send_text(payload)

    @property
    def active_count(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()
