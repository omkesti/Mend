"""WebSocket connection manager and broadcast helper.

Clients connect to /ws/{run_id} (route added in the API layer) and receive
live `status` / `complete` / `error` events for that run. The runner service
calls `broadcast()` to push events; it never touches a WebSocket directly.
"""

from __future__ import annotations

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks live WebSocket connections keyed by run_id."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(run_id, []).append(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        conns = self.active_connections.get(run_id)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active_connections.pop(run_id, None)

    async def broadcast(self, run_id: str, event: str, data: dict) -> None:
        """Send `{event, data}` to every socket subscribed to run_id.

        Send errors are ignored — the client may have disconnected — and the
        dead socket is dropped from the registry.
        """
        payload = {"event": event, "data": data}
        dead: list[WebSocket] = []
        for websocket in list(self.active_connections.get(run_id, [])):
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001 — client gone; drop it silently
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(run_id, websocket)


manager = ConnectionManager()


async def broadcast(run_id: str, event: str, data: dict) -> None:
    """Module-level convenience wrapper around the singleton manager."""
    await manager.broadcast(run_id, event, data)
