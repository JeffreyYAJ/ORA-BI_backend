from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.agent_task import AgentTaskRead
from app.services import agent_executor

router = APIRouter(prefix="/pipelines/{pipeline_id}/agent-tasks", tags=["agent-tasks"])


@router.get("", response_model=list[AgentTaskRead])
async def list_tasks(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> list[AgentTaskRead]:
    return await agent_executor.list_agent_tasks(db, pipeline_id)


@router.post("/{task_id}/execute", response_model=AgentTaskRead)
async def execute_task(
    pipeline_id: UUID, task_id: UUID, db: AsyncSession = Depends(get_db)
) -> AgentTaskRead:
    return await agent_executor.execute_agent_task(db, pipeline_id, task_id)
