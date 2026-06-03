from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent_task import AgentTask
from app.models.chat_message import ChatMessage
from app.models.enums import AgentRole, AgentTaskStatus, ChatSender
from app.models.pipeline import Pipeline
from app.schemas.agent_task import AgentTaskRead
from app.schemas.chat import ChatMessageRead, ChatResponse
from app.services.pipeline_service import get_pipeline_or_404, pipeline_to_read
from app.mcp.master_agent import MasterAgentRunner
from app.websocket.events import WsEvent, WsEventType
from app.websocket.manager import ws_manager


def chat_message_to_read(msg: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=msg.id,
        pipeline_id=msg.pipeline_id,
        sender=msg.sender,
        content_md=msg.content_md,
        metadata=msg.metadata_ or {},
        created_at=msg.created_at,
    )


async def list_chat_messages(db: AsyncSession, pipeline_id: UUID) -> list[ChatMessageRead]:
    await get_pipeline_or_404(db, pipeline_id)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.pipeline_id == pipeline_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return [chat_message_to_read(m) for m in result.scalars().all()]


async def create_agent_task(
    db: AsyncSession,
    pipeline_id: UUID,
    agent_role: AgentRole,
    instruction: str,
    node_id: UUID | None = None,
    input_payload: dict | None = None,
) -> AgentTask:
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


async def handle_chat_message(db: AsyncSession, pipeline_id: UUID, content: str) -> ChatResponse:
    await get_pipeline_or_404(db, pipeline_id)

    user_msg = ChatMessage(
        pipeline_id=pipeline_id,
        sender=ChatSender.USER,
        content_md=content,
    )
    db.add(user_msg)
    await db.flush()

    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.nodes), selectinload(Pipeline.edges))
    )
    pipeline = result.scalar_one()
    pipeline_read = pipeline_to_read(pipeline)

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.pipeline_id == pipeline_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history = list(reversed(history_result.scalars().all()))

    runner = MasterAgentRunner(db=db, pipeline_id=pipeline_id)
    agent_reply, new_tasks = await runner.run(
        user_content=content,
        pipeline_context=pipeline_read.model_dump(mode="json"),
        history=[{"sender": m.sender.value, "content": m.content_md} for m in history],
    )

    agent_msg = ChatMessage(
        pipeline_id=pipeline_id,
        sender=ChatSender.MASTER_AGENT,
        content_md=agent_reply["content"],
        metadata_=agent_reply.get("metadata", {}),
    )
    db.add(agent_msg)
    await db.flush()

    task_reads: list[AgentTaskRead] = []
    for task in new_tasks:
        task_reads.append(AgentTaskRead.model_validate(task))
        await ws_manager.broadcast(
            pipeline_id,
            WsEvent(
                type=WsEventType.AGENT_TASK_UPDATED,
                pipeline_id=str(pipeline_id),
                payload=task_reads[-1].model_dump(mode="json"),
            ),
        )

    user_read = chat_message_to_read(user_msg)
    agent_read = chat_message_to_read(agent_msg)

    for msg_read in (user_read, agent_read):
        await ws_manager.broadcast(
            pipeline_id,
            WsEvent(
                type=WsEventType.CHAT_MESSAGE,
                pipeline_id=str(pipeline_id),
                payload=msg_read.model_dump(mode="json"),
            ),
        )

    return ChatResponse(user_message=user_read, agent_message=agent_read, agent_tasks=task_reads)
