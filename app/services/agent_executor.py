from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_task import AgentTask
from app.models.enums import AgentRole, AgentTaskStatus
from app.schemas.agent_task import AgentTaskRead
from app.services.agent_runner import execute_agent_with_context
from app.services.pipeline_service import get_pipeline_or_404
from app.websocket.events import WsEvent, WsEventType
from app.websocket.manager import ws_manager


async def get_task_or_404(db: AsyncSession, pipeline_id: UUID, task_id: UUID) -> AgentTask:
    await get_pipeline_or_404(db, pipeline_id)
    result = await db.execute(
        select(AgentTask).where(AgentTask.id == task_id, AgentTask.pipeline_id == pipeline_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Agent task not found")
    return task


async def list_agent_tasks(db: AsyncSession, pipeline_id: UUID) -> list[AgentTaskRead]:
    await get_pipeline_or_404(db, pipeline_id)
    result = await db.execute(
        select(AgentTask).where(AgentTask.pipeline_id == pipeline_id).order_by(AgentTask.created_at.desc())
    )
    return [AgentTaskRead.model_validate(t) for t in result.scalars().all()]


async def execute_agent_task(db: AsyncSession, pipeline_id: UUID, task_id: UUID) -> AgentTaskRead:
    task = await get_task_or_404(db, pipeline_id, task_id)
    if task.status not in (AgentTaskStatus.PENDING, AgentTaskStatus.FAILED):
        raise HTTPException(status_code=409, detail=f"Task status is {task.status.value}, cannot execute")

    await execute_agent_with_context(db, task)

    read = AgentTaskRead.model_validate(task)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(
            type=WsEventType.AGENT_TASK_UPDATED,
            pipeline_id=str(pipeline_id),
            payload=read.model_dump(mode="json"),
        ),
    )
    return read


async def execute_pending_guardian_tasks(db: AsyncSession, pipeline_id: UUID) -> list[AgentTaskRead]:
    result = await db.execute(
        select(AgentTask).where(
            AgentTask.pipeline_id == pipeline_id,
            AgentTask.agent_role == AgentRole.GUARDIAN,
            AgentTask.status == AgentTaskStatus.PENDING,
        )
    )
    tasks = list(result.scalars().all())
    reads: list[AgentTaskRead] = []
    for task in tasks:
        reads.append(await execute_agent_task(db, pipeline_id, task.id))
    return reads
