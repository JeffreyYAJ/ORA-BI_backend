from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.guardian.pii import findings_summary, mask_structure, scan_structure
from app.guardian.policy import detect_node_execution_risks, operation_requires_approval
from app.models.enums import (
    ApprovalStatus,
    NodeStatus,
    PipelineRunEventType,
    PipelineRunStatus,
)
from app.models.guardian_approval import GuardianApproval
from app.models.node import Node
from app.models.pipeline import Pipeline
from app.models.enums import GuardianOperationType
from app.models.pipeline_run import PipelineRun
from app.models.pipeline_run_event import PipelineRunEvent
from app.schemas.execution import PipelineRunEventRead, PipelineRunRead
from app.schemas.guardian import GuardianApprovalRead
from app.schemas.user_question import UserQuestionRead
from app.models.enums import AgentRole, WorkflowPhase
from app.services.guardian_service import approval_to_read, create_approval
from app.services.run_event_service import add_run_event
from app.services.pipeline_service import get_pipeline_or_404
from app.services.user_input_service import (
    all_run_questions_answered,
    answer_question,
    ask_contextual_questions,
    list_pending_questions,
    pause_run_for_questions,
)
from app.services.workflow_context import build_execution_context
from app.services.workflow_study_service import finalize_initial_study_if_ready, run_initial_study
from app.websocket.events import WsEvent, WsEventType
from app.websocket.manager import ws_manager


def _topological_order(pipeline: Pipeline) -> list[Node]:
    nodes_by_id = {n.id: n for n in pipeline.nodes}
    in_degree = {n.id: 0 for n in pipeline.nodes}
    adj: dict[UUID, list[UUID]] = {n.id: [] for n in pipeline.nodes}
    for edge in pipeline.edges:
        if edge.source_node_id in adj and edge.target_node_id in in_degree:
            adj[edge.source_node_id].append(edge.target_node_id)
            in_degree[edge.target_node_id] += 1
    queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
    order: list[Node] = []
    while queue:
        nid = queue.popleft()
        order.append(nodes_by_id[nid])
        for tgt in adj.get(nid, []):
            in_degree[tgt] -= 1
            if in_degree[tgt] == 0:
                queue.append(tgt)
    if len(order) != len(pipeline.nodes):
        order = list(pipeline.nodes)
    return order


def run_to_read(
    run: PipelineRun,
    events: list | None = None,
    approvals: list | None = None,
    questions: list | None = None,
) -> PipelineRunRead:
    return PipelineRunRead(
        id=run.id,
        pipeline_id=run.pipeline_id,
        status=run.status,
        current_node_id=run.current_node_id,
        context=run.context or {},
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        events=[PipelineRunEventRead.model_validate(e) for e in (events or [])],
        pending_approvals=[approval_to_read(a) for a in (approvals or [])],
        pending_questions=[UserQuestionRead.model_validate(q) for q in (questions or [])],
    )


async def _pending_approvals_for_run(db: AsyncSession, run_id: UUID) -> list[GuardianApproval]:
    result = await db.execute(
        select(GuardianApproval).where(
            GuardianApproval.run_id == run_id,
            GuardianApproval.status == ApprovalStatus.PENDING,
        )
    )
    return list(result.scalars().all())


async def _approval_exists_for_step(
    db: AsyncSession,
    run_id: UUID,
    node_id: UUID,
    operation_type: GuardianOperationType,
) -> bool:
    """Évite de recréer une approbation déjà en attente ou validée pour ce nœud."""
    result = await db.execute(
        select(GuardianApproval.id).where(
            GuardianApproval.run_id == run_id,
            GuardianApproval.node_id == node_id,
            GuardianApproval.operation_type == operation_type,
            GuardianApproval.status.in_([ApprovalStatus.PENDING, ApprovalStatus.APPROVED]),
        )
    )
    return result.scalar_one_or_none() is not None


async def get_run(db: AsyncSession, pipeline_id: UUID, run_id: UUID) -> PipelineRunRead:
    await get_pipeline_or_404(db, pipeline_id)
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.pipeline_id == pipeline_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    events_result = await db.execute(
        select(PipelineRunEvent).where(PipelineRunEvent.run_id == run_id).order_by(PipelineRunEvent.created_at.asc())
    )
    pending = await _pending_approvals_for_run(db, run_id)
    pending_q = await list_pending_questions(db, pipeline_id, run_id=run_id)
    return run_to_read(run, list(events_result.scalars().all()), pending, pending_q)


async def start_pipeline_run(db: AsyncSession, pipeline_id: UUID) -> PipelineRunRead:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    if not pipeline.nodes:
        raise HTTPException(status_code=400, detail="Pipeline has no nodes to execute")

    active = await db.execute(
        select(PipelineRun).where(
            PipelineRun.pipeline_id == pipeline_id,
            PipelineRun.status.in_(
                [
                    PipelineRunStatus.PENDING,
                    PipelineRunStatus.RUNNING,
                    PipelineRunStatus.AWAITING_APPROVAL,
                    PipelineRunStatus.AWAITING_USER_INPUT,
                ]
            ),
        )
    )
    if active.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress")

    run = PipelineRun(
        pipeline_id=pipeline_id,
        status=PipelineRunStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        context={"node_order": [], "completed_nodes": [], "open_questions": []},
    )
    db.add(run)
    await db.flush()

    await create_approval(
        db,
        pipeline_id,
        GuardianOperationType.PIPELINE_RUN,
        "Exécution du pipeline",
        f"Lancement de l'exécution du pipeline **{pipeline.name}**.",
        run_id=run.id,
        preview_data={"nodes": len(pipeline.nodes), "edges": len(pipeline.edges)},
        risk_level="MEDIUM",
    )
    run.status = PipelineRunStatus.AWAITING_APPROVAL
    await db.flush()

    await add_run_event(
        db,
        run,
        PipelineRunEventType.RUN_STARTED,
        f"Exécution démarrée — approbation requise pour **{pipeline.name}**.",
        {"nodes_count": len(pipeline.nodes)},
    )
    await add_run_event(
        db,
        run,
        PipelineRunEventType.APPROVAL_REQUIRED,
        "Approbation humaine requise avant exécution des nœuds.",
        {"reason": "PIPELINE_RUN"},
    )

    read = await get_run(db, pipeline_id, run.id)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(
            type=WsEventType.PIPELINE_RUN_UPDATED,
            pipeline_id=str(pipeline_id),
            payload=read.model_dump(mode="json"),
        ),
    )
    return read


async def _advance_run(db: AsyncSession, run: PipelineRun, pipeline: Pipeline) -> PipelineRunRead:
    ctx = dict(run.context or {})
    if not ctx.get("initial_study_done"):
        blocked = await run_initial_study(db, run, pipeline)
        if blocked:
            read = await get_run(db, pipeline.id, run.id)
            await ws_manager.broadcast(
                pipeline.id,
                WsEvent(
                    type=WsEventType.PIPELINE_RUN_UPDATED,
                    pipeline_id=str(pipeline.id),
                    payload=read.model_dump(mode="json"),
                ),
            )
            return read

    completed = set(UUID(x) for x in ctx.get("completed_nodes", []) if x)
    order = _topological_order(pipeline)
    ctx["node_order"] = [str(n.id) for n in order]
    base_context = build_execution_context(pipeline, phase=WorkflowPhase.NODE_EXECUTION.value)
    if ctx.get("user_answers"):
        base_context["user_answers"] = ctx["user_answers"]
    if ctx.get("data_study"):
        base_context["data_study"] = ctx["data_study"]

    for node in order:
        if node.id in completed:
            continue
        run.current_node_id = node.id
        run.status = PipelineRunStatus.RUNNING
        await db.flush()

        await add_run_event(
            db,
            run,
            PipelineRunEventType.STEP_STARTED,
            f"Étape : **{node.label}** ({node.type.value})",
            {"node_id": str(node.id)},
        )

        findings = [f.to_dict() for f in scan_structure(node.internal_data or {})]
        if findings:
            masked, _ = mask_structure(node.internal_data or {})
            await add_run_event(
                db,
                run,
                PipelineRunEventType.PII_DETECTED,
                findings_summary(findings),
                {"node_id": str(node.id), "masked_preview": masked},
            )

        if findings and not ctx.get(f"answered_pii_{node.id}"):
            node_ctx = {
                **base_context,
                "current_node": {
                    "id": str(node.id),
                    "label": node.label,
                    "type": node.type.value,
                    "pii_count": len(findings),
                    "masked_preview": mask_structure(node.internal_data or {})[0],
                },
            }
            created = await ask_contextual_questions(
                db,
                pipeline.id,
                AgentRole.GUARDIAN,
                WorkflowPhase.NODE_EXECUTION,
                node_ctx,
                instruction="Validation RGPD avant exécution de l'étape",
                run_id=run.id,
                node_id=node.id,
                max_questions=1,
            )
            if created:
                run.context = ctx
                await pause_run_for_questions(db, run, pipeline.id)
                await db.flush()
                read = await get_run(db, pipeline.id, run.id)
                await ws_manager.broadcast(
                    pipeline.id,
                    WsEvent(
                        type=WsEventType.PIPELINE_RUN_UPDATED,
                        pipeline_id=str(pipeline.id),
                        payload=read.model_dump(mode="json"),
                    ),
                )
                return read

        risks = detect_node_execution_risks(node)
        for op, meta, desc in risks:
            if not operation_requires_approval(op):
                continue
            if op == GuardianOperationType.PII_EXPOSURE and ctx.get(f"answered_pii_{node.id}"):
                continue
            if await _approval_exists_for_step(db, run.id, node.id, op):
                continue
            await create_approval(
                db,
                pipeline.id,
                op,
                desc,
                f"Le Gardien bloque l'étape jusqu'à validation : {meta}",
                run_id=run.id,
                node_id=node.id,
                preview_data=node.internal_data,
            )
            await add_run_event(
                db,
                run,
                PipelineRunEventType.APPROVAL_REQUIRED,
                f"⏸ Approbation requise — {desc}",
                {"node_id": str(node.id), "operation": op.value},
            )

        pending = await _pending_approvals_for_run(db, run.id)
        if pending:
            run.status = PipelineRunStatus.AWAITING_APPROVAL
            await add_run_event(
                db,
                run,
                PipelineRunEventType.RUN_PAUSED,
                "Exécution en pause — en attente d'approbation(s).",
                {"pending_count": len(pending)},
            )
            await db.flush()
            return await get_run(db, pipeline.id, run.id)

        node.status = NodeStatus.VALID
        completed.add(node.id)
        ctx["completed_nodes"] = [str(x) for x in completed]
        run.context = ctx
        await add_run_event(
            db,
            run,
            PipelineRunEventType.STEP_COMPLETED,
            f"Étape terminée : **{node.label}**",
            {"node_id": str(node.id)},
        )
        await db.flush()

    run.status = PipelineRunStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.current_node_id = None
    await add_run_event(
        db,
        run,
        PipelineRunEventType.RUN_COMPLETED,
        "Pipeline exécuté avec succès (simulation — pas d'exécution Python distante).",
        {},
    )
    await db.flush()
    read = await get_run(db, pipeline.id, run.id)
    await ws_manager.broadcast(
        pipeline.id,
        WsEvent(
            type=WsEventType.PIPELINE_RUN_UPDATED,
            pipeline_id=str(pipeline.id),
            payload=read.model_dump(mode="json"),
        ),
    )
    return read


async def resume_pipeline_run(db: AsyncSession, pipeline_id: UUID, run_id: UUID) -> PipelineRunRead:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.pipeline_id == pipeline_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    if run.status not in (
        PipelineRunStatus.AWAITING_APPROVAL,
        PipelineRunStatus.AWAITING_USER_INPUT,
        PipelineRunStatus.RUNNING,
    ):
        raise HTTPException(status_code=409, detail=f"Run cannot be resumed from status {run.status.value}")

    pending = await _pending_approvals_for_run(db, run.id)
    if pending:
        raise HTTPException(
            status_code=409,
            detail=f"{len(pending)} approval(s) still pending",
        )
    if not await all_run_questions_answered(db, pipeline_id, run.id):
        raise HTTPException(status_code=409, detail="Unanswered user questions remain")

    await add_run_event(
        db,
        run,
        PipelineRunEventType.RUN_RESUMED,
        "Reprise de l'exécution.",
        {},
    )
    run.status = PipelineRunStatus.RUNNING
    return await _advance_run(db, run, pipeline)


async def continue_run_after_answer(
    db: AsyncSession,
    pipeline_id: UUID,
    run_id: UUID,
) -> None:
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.pipeline_id == pipeline_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    await finalize_initial_study_if_ready(db, run, pipeline)
    if await all_run_questions_answered(db, pipeline_id, run_id):
        run.status = PipelineRunStatus.RUNNING
        await db.flush()
        await _advance_run(db, run, pipeline)


async def answer_guardian_question(
    db: AsyncSession,
    pipeline_id: UUID,
    run_id: UUID,
    question_id: str,
    answer: str,
) -> PipelineRunRead:
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.pipeline_id == pipeline_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    try:
        q_uuid = UUID(question_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Question not found") from exc

    await answer_question(db, pipeline_id, q_uuid, answer)
    await continue_run_after_answer(db, pipeline_id, run_id)
    return await get_run(db, pipeline_id, run_id)
