"""Broadcast hub pushing live occupancy and events to connected panels."""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message_type: str, payload: Any) -> None:
        if not self._connections:
            return

        message = json.dumps({"type": message_type, "payload": payload}, default=str)
        async with self._lock:
            targets = list(self._connections)

        dead: list[WebSocket] = []
        for connection in targets:
            try:
                await connection.send_text(message)
            except Exception:  # client vanished mid-send
                dead.append(connection)

        if dead:
            async with self._lock:
                for connection in dead:
                    self._connections.discard(connection)


manager = ConnectionManager()
