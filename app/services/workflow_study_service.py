"""Phase initiale du workflow : étude des données puis questions contextuelles."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AgentRole, PipelineRunEventType, WorkflowPhase
from app.models.pipeline import Pipeline
from app.models.pipeline_run import PipelineRun
from app.services.run_event_service import add_run_event
from app.services.user_input_service import (
    ask_contextual_questions,
    list_pending_questions,
    pause_run_for_questions,
)
from app.services.data_source_service import get_live_profile, introspect_pipeline_sources
from app.services.pipeline_service import get_pipeline_or_404
from app.services.workflow_context import build_execution_context, merge_user_answers


async def run_initial_study(
    db: AsyncSession,
    run: PipelineRun,
    pipeline: Pipeline,
) -> bool:
    """
    Étude des données au début du run. Retourne True si des questions bloquent la suite.
    """
    ctx = dict(run.context or {})
    if ctx.get("initial_study_done"):
        return False

    live = None
    try:
        await introspect_pipeline_sources(db, pipeline.id)
        pipeline = await get_pipeline_or_404(db, pipeline.id)
        live = get_live_profile(pipeline)
    except Exception:
        pass

    execution_context = build_execution_context(pipeline, phase=WorkflowPhase.INITIAL_STUDY.value)
    if live is None:
        live = get_live_profile(pipeline)
    if live:
        execution_context["live_data_profile"] = live
        execution_context["data_summary_md"] = live.get("summary_md", "")
    ctx["data_study"] = execution_context
    run.context = ctx
    await db.flush()

    await add_run_event(
        db,
        run,
        PipelineRunEventType.STEP_STARTED,
        f"**Étude initiale** — {pipeline.name} ({execution_context['node_count']} nœud(s), "
        f"{execution_context.get('pii_total', 0)} PII détecté(s)).",
        {
            "phase": "INITIAL_STUDY",
            "gaps": execution_context.get("gaps", []),
            "source_connected": bool(live and live.get("primary_source")),
        },
    )

    study_ctx = {**execution_context, "studying_agent": AgentRole.PROFILER.value}
    if ctx.get("user_answers"):
        study_ctx = merge_user_answers(
            study_ctx,
            [{"question_id": k, "answer": v} for k, v in ctx["user_answers"].items()],
        )
    await ask_contextual_questions(
        db,
        pipeline.id,
        AgentRole.PROFILER,
        WorkflowPhase.INITIAL_STUDY,
        study_ctx,
        instruction="Étude initiale : structure, colonnes clés, qualité des données",
        run_id=run.id,
        max_questions=2,
    )
    if execution_context.get("pii_total", 0) > 0:
        await ask_contextual_questions(
            db,
            pipeline.id,
            AgentRole.GUARDIAN,
            WorkflowPhase.INITIAL_STUDY,
            {**study_ctx, "studying_agent": AgentRole.GUARDIAN.value},
            instruction="Étude initiale : conformité RGPD et choix de masquage",
            run_id=run.id,
            max_questions=2,
        )

    pending_count = len(await list_pending_questions(db, pipeline.id, run_id=run.id))
    if pending_count > 0:
        await pause_run_for_questions(db, run, pipeline.id)
        return True

    ctx["initial_study_done"] = True
    run.context = ctx
    await db.flush()
    await add_run_event(
        db,
        run,
        PipelineRunEventType.STEP_COMPLETED,
        "Étude initiale terminée — aucune question utilisateur requise.",
        {"phase": "INITIAL_STUDY"},
    )
    return False


async def finalize_initial_study_if_ready(db: AsyncSession, run: PipelineRun, pipeline: Pipeline) -> None:
    ctx = dict(run.context or {})
    if ctx.get("initial_study_done"):
        return
    from app.services.user_input_service import all_run_questions_answered

    if await all_run_questions_answered(db, pipeline.id, run.id):
        ctx["initial_study_done"] = True
        run.context = ctx
        await db.flush()
        await add_run_event(
            db,
            run,
            PipelineRunEventType.STEP_COMPLETED,
            "Étude initiale terminée — réponses utilisateur intégrées au contexte.",
            {"phase": "INITIAL_STUDY"},
        )
