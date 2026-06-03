"""Exécution des agents spécialisés avec contexte d'étude et questions adaptatives."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.guardian.pii import findings_summary, mask_structure, scan_structure
from app.models.agent_task import AgentTask
from app.models.enums import AgentRole, AgentTaskStatus, WorkflowPhase
from app.models.pipeline import Pipeline
from app.services.guardian_service import execute_guardian_task
from app.services.user_input_service import ask_contextual_questions
from app.services.workflow_context import build_execution_context


async def _load_pipeline(db: AsyncSession, pipeline_id: UUID) -> Pipeline:
    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.nodes), selectinload(Pipeline.edges))
    )
    return result.scalar_one()


async def execute_agent_with_context(db: AsyncSession, task: AgentTask) -> dict:
    if task.agent_role == AgentRole.GUARDIAN:
        return await execute_guardian_task(db, task)

    pipeline = await _load_pipeline(db, task.pipeline_id)
    task.status = AgentTaskStatus.RUNNING
    await db.flush()

    execution_context = build_execution_context(pipeline, phase=WorkflowPhase.AGENT_TASK.value)
    if task.node_id:
        node = next((n for n in pipeline.nodes if n.id == task.node_id), None)
        if node:
            execution_context["focus_node"] = {
                "id": str(node.id),
                "label": node.label,
                "type": node.type.value,
                "masked_data": mask_structure(node.internal_data or {})[0],
            }

    questions = await ask_contextual_questions(
        db,
        task.pipeline_id,
        task.agent_role,
        WorkflowPhase.AGENT_TASK,
        execution_context,
        instruction=task.instruction,
        agent_task_id=task.id,
        node_id=task.node_id,
        max_questions=2,
    )

    role_output: dict = {
        "execution_context_summary": {
            "pipeline_name": pipeline.name,
            "node_count": len(pipeline.nodes),
            "pii_total": execution_context.get("pii_total"),
            "gaps": execution_context.get("gaps"),
        },
        "questions_raised": len(questions),
        "question_ids": [str(q.id) for q in questions],
    }

    live = (pipeline.architecture_design or {}).get("live_data_profile")
    if live:
        role_output["live_data_profile"] = live

    if task.agent_role == AgentRole.PROFILER:
        role_output["profiler_report"] = (
            f"Étude : {len(pipeline.nodes)} nœud(s). "
            f"{execution_context.get('pii_summary', '')}\n"
            f"{(live or {}).get('summary_md', '')}"
        )
    elif task.agent_role == AgentRole.ENGINEER:
        from app.services.etl_workflow_service import execute_user_etl

        try:
            etl = await execute_user_etl(db, task.pipeline_id, task.instruction)
            role_output["etl_result"] = etl.model_dump(mode="json")
        except Exception as exc:
            role_output["etl_error"] = str(exc)
    else:
        role_output["message"] = (
            f"Agent {task.agent_role.value} : analyse contextuelle effectuée. "
            f"{len(questions)} question(s) posée(s) si nécessaire."
        )

    task.status = AgentTaskStatus.COMPLETED
    task.output_payload = role_output
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return role_output
