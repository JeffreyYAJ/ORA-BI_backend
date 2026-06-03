from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_task import AgentTask
from app.models.enums import AgentRole, AgentTaskStatus
from app.services.pipeline_service import get_pipeline_or_404


async def create_agent_task(
    db: AsyncSession,
    pipeline_id: UUID,
    agent_role: AgentRole,
    instruction: str,
    node_id: UUID | None = None,
    input_payload: dict | None = None,
) -> AgentTask:
    await get_pipeline_or_404(db, pipeline_id)
    task = AgentTask(
        pipeline_id=pipeline_id,
        agent_role=agent_role,
        instruction=instruction,
        node_id=node_id,
        input_payload=input_payload or {},
        status=AgentTaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()
    return task
