import json
from uuid import UUID

from fastapi import WebSocket

from app.websocket.events import WsEvent


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, pipeline_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        key = str(pipeline_id)
        self._rooms.setdefault(key, []).append(websocket)

    def disconnect(self, pipeline_id: UUID, websocket: WebSocket) -> None:
        key = str(pipeline_id)
        if key in self._rooms:
            self._rooms[key] = [ws for ws in self._rooms[key] if ws is not websocket]
            if not self._rooms[key]:
                del self._rooms[key]

    async def broadcast(self, pipeline_id: UUID, event: WsEvent) -> None:
        key = str(pipeline_id)
        message = event.model_dump_json()
        for websocket in list(self._rooms.get(key, [])):
            try:
                await websocket.send_text(message)
            except Exception:
                self.disconnect(pipeline_id, websocket)


ws_manager = ConnectionManager()
