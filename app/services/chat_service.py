from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat_message import ChatMessage
from app.models.enums import ChatSender
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
    ctx = pipeline_read.model_dump(mode="json")
    design = pipeline.architecture_design or {}
    if design.get("live_data_profile"):
        ctx["live_data_profile"] = design["live_data_profile"]
    if design.get("last_etl_result"):
        ctx["last_etl_result"] = design["last_etl_result"]

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
        pipeline_context=ctx,
        history=[{"sender": m.sender.value, "content": m.content_md} for m in history],
    )

    agent_metadata = dict(agent_reply.get("metadata", {}))
    task_reads: list[AgentTaskRead] = []
    from app.models.enums import AgentRole
    from app.services.agent_executor import execute_agent_task

    from app.services.etl_workflow_service import execute_user_etl

    for task in new_tasks:
        if task.agent_role in (AgentRole.GUARDIAN, AgentRole.PROFILER, AgentRole.ENGINEER):
            task_read = await execute_agent_task(db, pipeline_id, task.id)
        else:
            task_read = AgentTaskRead.model_validate(task)

        if task.agent_role == AgentRole.ENGINEER and _looks_like_etl_request(content):
            try:
                etl_result = await execute_user_etl(db, pipeline_id, content)
                task_read.output_payload = {
                    **(task_read.output_payload or {}),
                    "etl_result": etl_result.model_dump(mode="json"),
                }
            except Exception as exc:
                task_read.output_payload = {
                    **(task_read.output_payload or {}),
                    "etl_error": str(exc),
                }
        task_reads.append(task_read)
        await ws_manager.broadcast(
            pipeline_id,
            WsEvent(
                type=WsEventType.AGENT_TASK_UPDATED,
                pipeline_id=str(pipeline_id),
                payload=task_read.model_dump(mode="json"),
            ),
        )

    if _looks_like_etl_request(content) and not any(t.agent_role == AgentRole.ENGINEER for t in new_tasks):
        try:
            etl_result = await execute_user_etl(db, pipeline_id, content)
            agent_metadata["last_etl_result"] = etl_result.model_dump(mode="json")
            agent_metadata["etl_summary_md"] = etl_result.summary_md
            agent_reply_content = (
                f"{agent_reply['content']}\n\n---\n\n## Résultat ETL exécuté\n\n{etl_result.summary_md}"
            )
        except Exception as exc:
            agent_reply_content = f"{agent_reply['content']}\n\n⚠️ ETL non exécuté : {exc}"
    else:
        agent_reply_content = agent_reply["content"]

    await db.refresh(pipeline)
    design = pipeline.architecture_design or {}
    if design.get("last_etl_result") and "last_etl_result" not in agent_metadata:
        agent_metadata["last_etl_result"] = design["last_etl_result"]

    agent_msg = ChatMessage(
        pipeline_id=pipeline_id,
        sender=ChatSender.MASTER_AGENT,
        content_md=agent_reply_content,
        metadata_=agent_metadata,
    )
    db.add(agent_msg)
    await db.flush()

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


def _looks_like_etl_request(text: str) -> bool:
    t = text.lower()
    keywords = (
        "agrég", "agreg", "group", "somme", "total", "filtr", "select", "etl",
        "transform", "devise", "currency", "catégor", "top ", "montant", "affich",
    )
    return any(k in t for k in keywords)
