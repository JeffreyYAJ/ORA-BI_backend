from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/pipelines/{pipeline_id}")
async def pipeline_websocket(pipeline_id: UUID, websocket: WebSocket) -> None:
    await ws_manager.connect(pipeline_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(pipeline_id, websocket)
