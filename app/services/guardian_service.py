from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.guardian.pii import findings_summary, mask_structure, scan_structure
from app.guardian.policy import analyze_node_data_change, operation_requires_approval
from app.models.agent_task import AgentTask
from app.models.chat_message import ChatMessage
from app.models.enums import (
    AgentRole,
    AgentTaskStatus,
    ApprovalStatus,
    ChatSender,
    GuardianOperationType,
)
from app.models.guardian_approval import GuardianApproval
from app.models.node import Node
from app.schemas.guardian import GuardianApprovalRead
from app.models.enums import WorkflowPhase
from app.services.pipeline_service import get_pipeline_or_404
from app.services.user_input_service import ask_contextual_questions
from app.services.workflow_context import build_execution_context
from app.websocket.events import WsEvent, WsEventType
from app.websocket.manager import ws_manager


def approval_to_read(approval: GuardianApproval) -> GuardianApprovalRead:
    return GuardianApprovalRead.model_validate(approval)


async def create_approval(
    db: AsyncSession,
    pipeline_id: UUID,
    operation_type: GuardianOperationType,
    title: str,
    description: str,
    *,
    run_id: UUID | None = None,
    node_id: UUID | None = None,
    agent_task_id: UUID | None = None,
    pending_action: dict | None = None,
    preview_data: dict | None = None,
    risk_level: str = "HIGH",
) -> GuardianApproval:
    preview = preview_data or {}
    masked, findings = mask_structure(preview)
    approval = GuardianApproval(
        pipeline_id=pipeline_id,
        run_id=run_id,
        node_id=node_id,
        agent_task_id=agent_task_id,
        operation_type=operation_type,
        title=title,
        description=description,
        risk_level=risk_level,
        status=ApprovalStatus.PENDING,
        masked_preview=masked if isinstance(masked, dict) else {"preview": masked},
        pii_findings=findings,
        pending_action=pending_action or {},
    )
    db.add(approval)
    await db.flush()
    read = approval_to_read(approval)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(
            type=WsEventType.GUARDIAN_APPROVAL_REQUIRED,
            pipeline_id=str(pipeline_id),
            payload=read.model_dump(mode="json"),
        ),
    )
    return approval


async def get_approval_or_404(db: AsyncSession, pipeline_id: UUID, approval_id: UUID) -> GuardianApproval:
    result = await db.execute(
        select(GuardianApproval).where(
            GuardianApproval.id == approval_id,
            GuardianApproval.pipeline_id == pipeline_id,
        )
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


async def list_approvals(
    db: AsyncSession,
    pipeline_id: UUID,
    status: ApprovalStatus | None = None,
) -> list[GuardianApprovalRead]:
    await get_pipeline_or_404(db, pipeline_id)
    q = select(GuardianApproval).where(GuardianApproval.pipeline_id == pipeline_id)
    if status is not None:
        q = q.where(GuardianApproval.status == status)
    q = q.order_by(GuardianApproval.created_at.desc())
    result = await db.execute(q)
    return [approval_to_read(a) for a in result.scalars().all()]


async def _apply_pending_node_update(db: AsyncSession, approval: GuardianApproval) -> None:
    action = approval.pending_action or {}
    if action.get("type") != "node_update":
        return
    node_id = action.get("node_id")
    if not node_id:
        return
    result = await db.execute(
        select(Node).where(Node.id == UUID(str(node_id)), Node.pipeline_id == approval.pipeline_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        return
    patch = action.get("patch", {})
    if "data" in patch:
        node.internal_data = patch["data"]
    await db.flush()
    from app.services.pipeline_service import node_to_read

    await ws_manager.broadcast(
        approval.pipeline_id,
        WsEvent(
            type=WsEventType.NODE_UPDATED,
            pipeline_id=str(approval.pipeline_id),
            payload=node_to_read(node).model_dump(mode="json"),
        ),
    )


async def decide_approval(
    db: AsyncSession,
    pipeline_id: UUID,
    approval_id: UUID,
    approved: bool,
    comment: str | None = None,
) -> GuardianApprovalRead:
    approval = await get_approval_or_404(db, pipeline_id, approval_id)
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="Approval already resolved")

    approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
    approval.user_comment = comment
    approval.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    if approved:
        await _apply_pending_node_update(db, approval)

    read = approval_to_read(approval)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(
            type=WsEventType.GUARDIAN_APPROVAL_RESOLVED,
            pipeline_id=str(pipeline_id),
            payload=read.model_dump(mode="json"),
        ),
    )

    if approved and approval.run_id:
        from app.services.execution_service import resume_pipeline_run

        pending_result = await db.execute(
            select(GuardianApproval).where(
                GuardianApproval.run_id == approval.run_id,
                GuardianApproval.status == ApprovalStatus.PENDING,
            )
        )
        if not list(pending_result.scalars().all()):
            try:
                await resume_pipeline_run(db, pipeline_id, approval.run_id)
            except HTTPException:
                pass

    return read


async def check_node_update(
    db: AsyncSession,
    pipeline_id: UUID,
    node_id: UUID,
    old_data: dict,
    new_data: dict,
) -> GuardianApproval | None:
    ops = analyze_node_data_change(old_data, new_data)
    blocking = [(op, meta) for op, meta in ops if operation_requires_approval(op)]
    if not blocking:
        return None

    op, meta = blocking[0]
    title_map = {
        GuardianOperationType.DELETE_COLUMN: "Suppression de colonnes",
        GuardianOperationType.EXPORT_DATA: "Export de données",
        GuardianOperationType.BULK_TRANSFORM: "Transformation massive",
    }
    title = title_map.get(op, op.value)
    description = (
        f"Action sensible détectée sur le nœud. **Approbation humaine obligatoire** "
        f"conformément à la politique RGPD / Guardian.\n\nDétail : `{meta}`"
    )
    return await create_approval(
        db,
        pipeline_id,
        op,
        title,
        description,
        node_id=node_id,
        pending_action={
            "type": "node_update",
            "node_id": str(node_id),
            "patch": {"data": new_data},
        },
        preview_data=new_data,
    )


async def _emit_guardian_chat(
    db: AsyncSession,
    pipeline_id: UUID,
    content_md: str,
    metadata: dict,
) -> ChatMessage:
    msg = ChatMessage(
        pipeline_id=pipeline_id,
        sender=ChatSender.GUARDIAN_AGENT,
        content_md=content_md,
        metadata_=metadata,
    )
    db.add(msg)
    await db.flush()
    from app.services.chat_service import chat_message_to_read

    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(
            type=WsEventType.CHAT_MESSAGE,
            pipeline_id=str(pipeline_id),
            payload=chat_message_to_read(msg).model_dump(mode="json"),
        ),
    )
    return msg


async def execute_guardian_task(db: AsyncSession, task: AgentTask) -> dict:
    """Exécute une tâche GUARDIAN : scan PII, rapport, questions contextuelles."""
    from sqlalchemy.orm import selectinload
    from app.models.pipeline import Pipeline

    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == task.pipeline_id)
        .options(selectinload(Pipeline.nodes), selectinload(Pipeline.edges))
    )
    pipeline = result.scalar_one()
    task.status = AgentTaskStatus.RUNNING
    await db.flush()

    execution_context = build_execution_context(pipeline, phase=WorkflowPhase.AGENT_TASK.value)
    scan_target: dict = {"instruction": task.instruction, **(task.input_payload or {})}
    if task.node_id:
        node_result = await db.execute(select(Node).where(Node.id == task.node_id))
        node = node_result.scalar_one_or_none()
        if node:
            scan_target["node"] = {
                "id": str(node.id),
                "label": node.label,
                "data": node.internal_data,
            }
            execution_context["focus_node"] = scan_target["node"]

    findings = [f.to_dict() for f in scan_structure(scan_target)]
    masked, _ = mask_structure(scan_target)
    summary = findings_summary(findings)
    execution_context["guardian_scan"] = {"findings": findings, "masked_preview": masked}

    question_reads = await ask_contextual_questions(
        db,
        task.pipeline_id,
        AgentRole.GUARDIAN,
        WorkflowPhase.AGENT_TASK,
        execution_context,
        instruction=task.instruction,
        agent_task_id=task.id,
        node_id=task.node_id,
        max_questions=2,
    )
    questions = [{"id": str(q.id), "text": q.question_text} for q in question_reads]

    if question_reads:
        await _emit_guardian_chat(
            db,
            task.pipeline_id,
            f"**Gardien** — {summary}\n\n"
            + "\n".join(f"❓ {q.question_text}" for q in question_reads)
            + "\n\nRépondez via `POST .../questions/{{id}}/answer`.",
            {
                "requires_user_input": True,
                "pii_count": len(findings),
                "question_ids": [str(q.id) for q in question_reads],
            },
        )

    approvals_created: list[str] = []
    if task.node_id and findings:
        approval = await create_approval(
            db,
            task.pipeline_id,
            GuardianOperationType.PII_EXPOSURE,
            "Exposition potentielle de PII",
            summary,
            node_id=task.node_id,
            agent_task_id=task.id,
            preview_data=masked if isinstance(masked, dict) else {"scan": masked},
            risk_level="CRITICAL" if len(findings) > 3 else "HIGH",
        )
        approvals_created.append(str(approval.id))

    output = {
        "pii_findings": findings,
        "masked_preview": masked,
        "summary_md": summary,
        "questions": questions,
        "approval_ids": approvals_created,
        "rgpd_masking_applied": True,
    }

    task.status = AgentTaskStatus.COMPLETED
    task.output_payload = output
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return output
