"""Événements de run pipeline (évite imports circulaires)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PipelineRunEventType
from app.models.pipeline_run import PipelineRun
from app.models.pipeline_run_event import PipelineRunEvent
from app.websocket.events import WsEvent, WsEventType
from app.websocket.manager import ws_manager


async def add_run_event(
    db: AsyncSession,
    run: PipelineRun,
    event_type: PipelineRunEventType,
    message_md: str,
    payload: dict | None = None,
) -> PipelineRunEvent:
    event = PipelineRunEvent(
        run_id=run.id,
        pipeline_id=run.pipeline_id,
        event_type=event_type,
        message_md=message_md,
        payload=payload or {},
    )
    db.add(event)
    await db.flush()
    await ws_manager.broadcast(
        run.pipeline_id,
        WsEvent(
            type=WsEventType.PIPELINE_RUN_EVENT,
            pipeline_id=str(run.pipeline_id),
            payload={
                "run_id": str(run.id),
                "event_type": event_type.value,
                "message_md": message_md,
                "payload": payload or {},
                "id": str(event.id),
            },
        ),
    )
    return event
