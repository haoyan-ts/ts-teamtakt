"""
WebSocket connection manager for real-time broadcasts.

Channels:
  - "team:{team_id}"  — scoped to one team
  - "all"             — all authenticated users

Visibility: callers MUST apply the same REST visibility filter before
broadcasting. This manager does no filtering itself.
"""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # channel → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket, channels: list[str]) -> None:
        await ws.accept()
        for channel in channels:
            self._connections[channel].add(ws)

    def disconnect(self, ws: WebSocket, channels: list[str]) -> None:
        for channel in channels:
            self._connections[channel].discard(ws)
            if not self._connections[channel]:
                del self._connections[channel]

    async def broadcast(self, channel: str, payload: dict) -> None:
        """Send JSON payload to all connections subscribed to channel."""
        dead: set[WebSocket] = set()
        for ws in list(self._connections.get(channel, [])):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:  # noqa: BLE001
                dead.add(ws)
        for ws in dead:
            self._connections[channel].discard(ws)

    async def broadcast_multi(self, channels: list[str], payload: dict) -> None:
        """Broadcast to multiple channels, deduplicating connections."""
        seen: set[WebSocket] = set()
        for channel in channels:
            for ws in list(self._connections.get(channel, [])):
                if ws not in seen:
                    seen.add(ws)
                    try:
                        await ws.send_text(json.dumps(payload))
                    except Exception:  # noqa: BLE001
                        pass


# Singleton used across the application
ws_manager = ConnectionManager()
