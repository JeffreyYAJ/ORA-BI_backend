"""Questions utilisateur unifiées — tous les agents, toutes les phases d'exécution."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.question_generator import generate_contextual_questions
from app.models.enums import (
    AgentRole,
    PipelineRunEventType,
    PipelineRunStatus,
    UserQuestionStatus,
    WorkflowPhase,
)
from app.models.pipeline_run import PipelineRun
from app.models.user_question import UserQuestion
from app.schemas.user_question import UserQuestionRead
from app.services.run_event_service import add_run_event
from app.services.pipeline_service import get_pipeline_or_404
from app.websocket.events import WsEvent, WsEventType
from app.websocket.manager import ws_manager


def question_to_read(q: UserQuestion) -> UserQuestionRead:
    return UserQuestionRead.model_validate(q)


async def list_pending_questions(
    db: AsyncSession,
    pipeline_id: UUID,
    *,
    run_id: UUID | None = None,
) -> list[UserQuestionRead]:
    await get_pipeline_or_404(db, pipeline_id)
    q = select(UserQuestion).where(
        UserQuestion.pipeline_id == pipeline_id,
        UserQuestion.status == UserQuestionStatus.PENDING,
    )
    if run_id is not None:
        q = q.where(UserQuestion.run_id == run_id)
    q = q.order_by(UserQuestion.created_at.asc())
    result = await db.execute(q)
    return [question_to_read(row) for row in result.scalars().all()]


async def create_questions_from_specs(
    db: AsyncSession,
    pipeline_id: UUID,
    agent_role: AgentRole,
    phase: WorkflowPhase,
    specs: list[dict],
    *,
    run_id: UUID | None = None,
    agent_task_id: UUID | None = None,
    node_id: UUID | None = None,
    context_snapshot: dict | None = None,
) -> list[UserQuestion]:
    created: list[UserQuestion] = []
    ctx = context_snapshot or {}
    for spec in specs:
        q = UserQuestion(
            pipeline_id=pipeline_id,
            run_id=run_id,
            agent_task_id=agent_task_id,
            node_id=node_id,
            agent_role=agent_role,
            phase=phase,
            question_text=spec["text"],
            context_snapshot=ctx,
            choices=[str(c) for c in spec.get("choices", [])],
            status=UserQuestionStatus.PENDING,
        )
        db.add(q)
        created.append(q)
    if created:
        await db.flush()
        for q in created:
            read = question_to_read(q)
            await ws_manager.broadcast(
                pipeline_id,
                WsEvent(
                    type=WsEventType.USER_INPUT_REQUIRED,
                    pipeline_id=str(pipeline_id),
                    payload=read.model_dump(mode="json"),
                ),
            )
    return created


async def ask_contextual_questions(
    db: AsyncSession,
    pipeline_id: UUID,
    agent_role: AgentRole,
    phase: WorkflowPhase,
    execution_context: dict,
    instruction: str | None = None,
    *,
    run_id: UUID | None = None,
    agent_task_id: UUID | None = None,
    node_id: UUID | None = None,
    max_questions: int = 3,
) -> list[UserQuestionRead]:
    specs = await generate_contextual_questions(
        agent_role, execution_context, phase, instruction, max_questions=max_questions
    )
    if not specs:
        return []
    rows = await create_questions_from_specs(
        db,
        pipeline_id,
        agent_role,
        phase,
        specs,
        run_id=run_id,
        agent_task_id=agent_task_id,
        node_id=node_id,
        context_snapshot=execution_context,
    )
    return [question_to_read(r) for r in rows]


async def pause_run_for_questions(db: AsyncSession, run: PipelineRun, pipeline_id: UUID) -> None:
    pending = await list_pending_questions(db, pipeline_id, run_id=run.id)
    if not pending:
        return
    run.status = PipelineRunStatus.AWAITING_USER_INPUT
    await db.flush()
    first = pending[0]
    await add_run_event(
        db,
        run,
        PipelineRunEventType.USER_QUESTION,
        f"❓ **{first.agent_role.value}** — {first.question_text}",
        {"question_id": str(first.id), "phase": first.phase.value, "pending_count": len(pending)},
    )


async def answer_question(
    db: AsyncSession,
    pipeline_id: UUID,
    question_id: UUID,
    answer: str,
) -> UserQuestionRead:
    result = await db.execute(
        select(UserQuestion).where(
            UserQuestion.id == question_id,
            UserQuestion.pipeline_id == pipeline_id,
        )
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if question.status != UserQuestionStatus.PENDING:
        raise HTTPException(status_code=409, detail="Question already answered")

    question.status = UserQuestionStatus.ANSWERED
    question.answer_text = answer
    question.answered_at = datetime.now(timezone.utc)
    await db.flush()

    read = question_to_read(question)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(
            type=WsEventType.USER_INPUT_ANSWERED,
            pipeline_id=str(pipeline_id),
            payload=read.model_dump(mode="json"),
        ),
    )

    if question.run_id:
        run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == question.run_id))
        run = run_result.scalar_one_or_none()
        if run:
            ctx = dict(run.context or {})
            answers = ctx.get("user_answers", {})
            answers[str(question.id)] = answer
            ctx["user_answers"] = answers
            if question.node_id:
                ctx[f"answered_pii_{question.node_id}"] = True
            run.context = ctx
            await add_run_event(
                db,
                run,
                PipelineRunEventType.USER_QUESTION,
                f"Réponse enregistrée ({question.agent_role.value}) : _{answer[:200]}_",
                {"question_id": str(question.id), "answered": True},
            )
            remaining = await list_pending_questions(db, pipeline_id, run_id=run.id)
            if not remaining:
                run.status = PipelineRunStatus.RUNNING
            await db.flush()

    return read


async def all_run_questions_answered(db: AsyncSession, pipeline_id: UUID, run_id: UUID) -> bool:
    pending = await list_pending_questions(db, pipeline_id, run_id=run_id)
    return len(pending) == 0
