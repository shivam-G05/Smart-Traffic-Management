from fastapi import WebSocket


class ConnectionManager:
    """Tracks connected dashboard clients and fans out simulation snapshots."""

    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast_json(self, payload: dict) -> None:
        # Iterate a snapshot, not the live set: send_json awaits, which yields
        # to the event loop, and a client connecting/disconnecting mid-await
        # mutates self._connections — iterating it directly raises
        # "RuntimeError: Set changed size during iteration".
        stale: list[WebSocket] = []
        for connection in list(self._connections):
            try:
                await connection.send_json(payload)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
